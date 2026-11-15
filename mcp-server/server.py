import calendar
import html
import json
import os
import re
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import httpx
import openpyxl
from fastmcp import FastMCP
from pydantic_settings import BaseSettings

CC_DIR = Path(__file__).resolve().parent.parent
mcp = FastMCP("account-hub")


def _load_local_config() -> dict:
    """Machine-local identity (SF username, user ID, instance host) lives in the
    gitignored config.local.json — never hardcoded — so the repo is portable and
    safe to share. See README → First-time setup."""
    p = CC_DIR / "config.local.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


_LOCAL = _load_local_config()

# Org-specific Salesforce custom field API names, keyed by stable names
# (config.local.json "sf_fields"; config.example.json lists every key).
F = _LOCAL.get("sf_fields", {})


def _f(key: str) -> str:
    """API name for an org-specific Salesforce field; clear error if unmapped."""
    try:
        return F[key]
    except KeyError:
        raise RuntimeError(
            f"Salesforce field '{key}' is not mapped: add sf_fields.{key} "
            f"(the field's API name in your org) to config.local.json."
        ) from None


class Settings(BaseSettings):
    """Reads from environment / gitignored .env — never from a tracked file."""

    # Salesforce identity is NOT read here — it lives in config.local.json
    # (sf_username / sf_user_id / sf_instance); auth is fetched live via the SF CLI.

    # Gong
    gong_access_key: str = ""
    gong_access_key_secret: str = ""

    # Microsoft Graph
    ms_tenant_id: str = ""
    ms_client_id: str = ""
    ms_client_secret: str = ""

    # Atlassian (JIRA + Confluence)
    atlassian_base_url: str = ""   # e.g. https://your-site.atlassian.net
    atlassian_email: str = ""
    atlassian_api_token: str = ""

    class Config:
        env_file = str(CC_DIR / ".env.mcp")
        env_file_encoding = "utf-8"
        extra = "ignore"   # tolerate stale/unused vars (e.g. legacy SF_* token entries)


settings = Settings()


def _secret(ref: str) -> str:
    r = subprocess.run(["op", "read", ref], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"1Password read failed for {ref}: {r.stderr.strip()}")
    return r.stdout.strip()


# Salesforce identity — sourced from config.local.json (gitignored), never hardcoded.
_SF_TARGET_ORG = _LOCAL.get("sf_username", "")   # SF CLI --target-org (your SF login)
_SF_OWNER_ID = _LOCAL.get("sf_user_id", "")      # your SF User Id — scopes "my opps" + write ownership
_SF_INSTANCE_URL = (
    _LOCAL.get("sf_instance_url")
    or (f"https://{_LOCAL['sf_instance']}" if _LOCAL.get("sf_instance") else "")
)
_SF_API_VERSION = "v59.0"


def _require_sf_identity() -> None:
    """Fail with a clear, portable message if SF identity isn't configured locally."""
    missing = [k for k, v in (("sf_username", _SF_TARGET_ORG), ("sf_user_id", _SF_OWNER_ID)) if not v]
    if missing:
        raise RuntimeError(
            f"Salesforce identity not configured: add {missing} to config.local.json "
            f"(see README → First-time setup). The hub needs to know which org and user to act as."
        )

# ── Salesforce write guardrails ─────────────────────────────────────────────────
# Enforced in code, not just by prompt rules, so the write tools stay safe for
# regular use and eventual automation. The hub only ever writes to opps owned by
# the configured user (_SF_OWNER_ID, from config.local.json).

# Two field tiers. Auto-safe fields don't move the forecast number; forecast-
# sensitive fields do. Everything currently requires human approval; the split lets
# us later flip auto-safe fields to unattended writes without a rebuild.
_SF_AUTOSAFE_FIELDS = {"NextStep", "Description"}
_SF_FORECAST_FIELDS = {"StageName", "CloseDate", "ForecastCategory", "Amount", "Probability"}
_SF_WRITABLE_FIELDS = _SF_AUTOSAFE_FIELDS | _SF_FORECAST_FIELDS

# Create-only allowlist. Deliberately SEPARATE from _SF_WRITABLE_FIELDS: the update
# path stays narrow as a forecast guardrail, and widening it for create must not
# loosen what an update may touch. These are the fields this org's validation rules
# require on insert (see docs/scope-sf-create-opportunity-template.md).
# Standard fields here; org-specific custom fields are sf_fields keys, resolved via _f().
_SF_CREATE_ONLY_STANDARD = {"Name", "AccountId", "RecordTypeId", "Type", "ForecastCategoryName"}
_SF_CREATE_ONLY_KEYS = (
    "contract_length", "start_date", "journey", "usecases", "primary_business_contact_o",
    "sub_type", "buyers", "incumbents", "what_type_of_deal_is_this",
)


def _sf_create_fields() -> set[str]:
    return _SF_WRITABLE_FIELDS | _SF_CREATE_ONLY_STANDARD | {_f(k) for k in _SF_CREATE_ONLY_KEYS}


# Boilerplate for placeholder upsell opps: org-specific picklist values (opportunity
# Type, sub type, buyers, incumbents, deal type) and the record type, from
# config.local.json "sf_defaults.placeholder_opportunity". Keys are standard field
# names or sf_fields keys. RecordTypeId must be explicit: record types filter
# picklists, so a valid restricted-picklist value is rejected on insert unless the
# record type is set.
def _sf_placeholder_defaults() -> dict:
    cfg = (_LOCAL.get("sf_defaults") or {}).get("placeholder_opportunity") or {}
    if not cfg:
        raise RuntimeError(
            "sf_defaults.placeholder_opportunity is not set in config.local.json "
            "(boilerplate Type / picklist values / RecordTypeId for placeholder opps)."
        )
    out = {"ForecastCategoryName": "Pipeline"}
    for k, v in cfg.items():
        out[_f(k) if k in _SF_CREATE_ONLY_KEYS else k] = v
    return out


# Opportunity.Type value for renewals in this org.
_SF_RENEWAL_TYPE = (_LOCAL.get("sf_defaults") or {}).get("renewal_type", "Renewal")

# ForecastCategory picklist observed in this org (standard + org values). Reject
# anything else before it reaches Salesforce.
_SF_FORECAST_CATEGORIES = {
    "Omitted", "Pipeline", "BestCase", "Forecast", "MostLikely", "Commit", "Closed",
}

# Write audit trail — gitignored (CLAUDE.md: no customer data in git).
_SF_AUDIT_LOG = CC_DIR / "issues" / ".sf-audit.log"

# Fields fetched as the "before" image on any opp write (diff + ownership check).
_SF_OPP_SNAPSHOT = [
    "Id", "Name", "OwnerId", "StageName", "CloseDate",
    "ForecastCategory", "Amount", "Probability", "NextStep", "Description",
]


def _sf_opp_snapshot() -> list[str]:
    return _SF_OPP_SNAPSHOT + [_f("dealhub_quote_id")]

# DealHub replaced Salesforce CPQ for quoting. Its quote syncs line items onto the
# opp, so recurring revenue/Amount on a DealHub-quoted opp come from the quote, and
# renewal + upsell/downgrade ride ONE quote on the renewal opp, split into these.
def _sf_dealhub_opp_fields() -> str:
    return ", ".join(_f(k) for k in ("dealhub_quote_id", "dh_renewal_mrr", "dh_upsell_downgrade_mrr"))


def _sf_get_record(sobject: str, record_id: str, fields: list[str]) -> dict:
    """Fetch specific fields of one record via SOQL. Raises if it doesn't exist."""
    cols = ", ".join(fields)
    recs = _sf_query(f"SELECT {cols} FROM {sobject} WHERE Id = '{record_id}'").get("records", [])
    if not recs:
        raise RuntimeError(f"{sobject} {record_id} not found.")
    return recs[0]


def _sf_assert_owner(opportunity_id: str) -> dict:
    """Refuse to write unless the opp is owned by the configured user. Returns the before-image."""
    _require_sf_identity()
    rec = _sf_get_record("Opportunity", opportunity_id, _sf_opp_snapshot())
    if rec.get("OwnerId") != _SF_OWNER_ID:
        raise PermissionError(
            f"Refusing to write: opportunity {opportunity_id} is not owned by you "
            f"(OwnerId={rec.get('OwnerId')}, configured owner={_SF_OWNER_ID}). "
            f"This hub only writes to opps you own."
        )
    return rec


def _sf_validate_write(fields: dict) -> dict:
    """Filter to writable fields and validate types/ranges/picklists. Raises
    ValueError on bad input; silently drops non-writable fields (Owner, Id, …)."""
    payload: dict = {}
    for k, v in fields.items():
        if k not in _SF_WRITABLE_FIELDS:
            continue
        if k == "Probability":
            iv = int(v)
            if not 0 <= iv <= 100:
                raise ValueError(f"Probability must be 0–100, got {v!r}")
            payload[k] = iv
        elif k == "Amount":
            fv = float(v)
            if fv < 0:
                raise ValueError(f"Amount must be ≥ 0, got {v!r}")
            payload[k] = fv
        elif k == "ForecastCategory":
            if str(v) not in _SF_FORECAST_CATEGORIES:
                raise ValueError(
                    f"ForecastCategory {v!r} not in {sorted(_SF_FORECAST_CATEGORIES)}"
                )
            payload[k] = v
        elif k == "CloseDate":
            try:
                d = datetime.strptime(str(v), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"CloseDate must be YYYY-MM-DD, got {v!r}")
            if d < date.today():
                raise ValueError(f"CloseDate {v} is in the past")
            payload[k] = str(v)
        else:
            payload[k] = v
    if not payload:
        raise ValueError(f"No writable fields provided. Allowed: {sorted(_SF_WRITABLE_FIELDS)}")
    return payload


_SF_PICKLIST_CACHE: dict[str, dict[str, list[str]]] = {}


def _sf_picklists(record_type_id: str = "") -> dict[str, list[str]]:
    """Active picklist values per field, cached per process.

    Never hardcode these: record types FILTER picklists, so a globally-valid
    restricted value can still be rejected on insert. When record_type_id is given,
    values are narrowed to that record type via the UI describe layout.
    """
    key = record_type_id or "_global"
    if key in _SF_PICKLIST_CACHE:
        return _SF_PICKLIST_CACHE[key]
    _, data = _sf_run(
        ["sf", "sobject", "describe", "--sobject", "Opportunity",
         "--target-org", _SF_TARGET_ORG, "--json"]
    )
    out: dict[str, list[str]] = {}
    for f in (data.get("result") or {}).get("fields", []):
        vals = [p["value"] for p in (f.get("picklistValues") or []) if p.get("active")]
        if vals:
            out[f["name"]] = vals
    _SF_PICKLIST_CACHE[key] = out
    return out


def _sf_validate_create(fields: dict) -> dict:
    """Validate every create field and raise ONCE listing all problems.

    The old behaviour — silently dropping unknown fields, then letting Salesforce
    reject the insert one validation rule at a time — cost a round trip per error.
    """
    errors: list[str] = []
    payload: dict = {}
    picklists = _sf_picklists(fields.get("RecordTypeId", ""))
    create_fields = _sf_create_fields()
    contract_length, start_date, usecases = _f("contract_length"), _f("start_date"), _f("usecases")

    for k, v in fields.items():
        if k not in create_fields:
            errors.append(f"{k}: not a permitted create field")
            continue
        if v is None or v == "":
            continue
        if k == "Probability":
            iv = int(v)
            if not 0 <= iv <= 100:
                errors.append(f"Probability must be 0-100, got {v!r}")
            else:
                payload[k] = iv
        elif k in ("Amount",):
            fv = float(v)
            if fv < 0:
                errors.append(f"Amount must be >= 0, got {v!r}")
            else:
                payload[k] = fv
        elif k == contract_length:
            iv = int(v)
            if iv < 1:
                errors.append(f"{k} must be >= 1, got {v!r}")
            else:
                payload[k] = iv
        elif k in ("CloseDate", start_date):
            try:
                datetime.strptime(str(v), "%Y-%m-%d").date()
                payload[k] = str(v)
            except ValueError:
                errors.append(f"{k} must be YYYY-MM-DD, got {v!r}")
        elif k in picklists and k != usecases:
            # The use-cases field is validated against the picklist too, but its values
            # contain commas/slashes that survive better unchecked than half-matched.
            if str(v) not in picklists[k]:
                near = [c for c in picklists[k] if str(v).lower() in c.lower()][:3]
                hint = f" Did you mean: {near}?" if near else f" Valid: {picklists[k][:8]}"
                errors.append(f"{k}: {v!r} is not an active picklist value.{hint}")
            else:
                payload[k] = v
        else:
            payload[k] = v

    if errors:
        raise ValueError(
            "Opportunity create rejected before sending to Salesforce:\n  - "
            + "\n  - ".join(errors)
        )
    return payload


def _months_between(start: date, end: date) -> int:
    """Whole months from start through end, counting the start month.

    2026-11-01 -> 2028-03-31 is 17, matching how the contract-length field is set on this
    org's mid-term add-ons.

    Caveat for mid-month starts: a term beginning 2023-08-31 and ending 2024-03-31
    computes as 8 here, but the real add-on was booked as 7 — a start that late in
    the month was treated as beginning in September. The caller warns when
    term_start is not the 1st so the number gets a human check.
    """
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _sf_values_arg(fields: dict) -> str:
    """Build the single --values string the SF CLI expects: space-separated
    field=value pairs, values containing spaces wrapped in single quotes."""
    parts = []
    for k, v in fields.items():
        s = str(v)
        parts.append(f"{k}={s}" if " " not in s else f"{k}='{s}'")
    return " ".join(parts)


def _sf_audit(action: str, record_id: str, before: dict, after: dict) -> None:
    """Append one write to the gitignored audit log (id, before/after, timestamp)."""
    _SF_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "record_id": record_id,
        "before": before,
        "after": after,
    }
    with _SF_AUDIT_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _sf_run(args: list[str]) -> tuple[subprocess.CompletedProcess, dict]:
    """Run an `sf` CLI command with --json and return (proc, parsed).

    sf >= 2.147 writes ANSI color codes into --json stdout even when not on a
    TTY, so json.loads fails at char 0. FORCE_COLOR=0 suppresses most of it;
    the regex strip covers CLI versions that ignore the env var.
    """
    r = subprocess.run(
        args, capture_output=True, text=True,
        env={**os.environ, "FORCE_COLOR": "0", "NO_COLOR": "1", "SF_NO_COLOR": "true"},
    )
    clean = _ANSI_RE.sub("", r.stdout).strip()
    if not clean:
        raise RuntimeError(f"SF CLI returned no output: {r.stderr.strip() or '(no stderr)'}")
    try:
        return r, json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Could not parse SF CLI JSON ({e}). First 200 chars: {clean[:200]!r}"
        ) from e


def _sf_query(soql: str) -> dict:
    """Run a SOQL query via the SF CLI and return the parsed JSON result."""
    r, data = _sf_run(
        ["sf", "data", "query", "--query", soql, "--target-org", _SF_TARGET_ORG, "--json"]
    )
    if r.returncode != 0 or data.get("status") != 0:
        msg = data.get("message") or data.get("name") or r.stderr.strip()
        if "expired" in msg.lower() or "auth" in msg.lower():
            raise RuntimeError(
                f"Salesforce auth expired. Run: sf org login web --instance-url {_SF_INSTANCE_URL}"
            )
        raise RuntimeError(f"SF query failed: {msg}")
    return data.get("result", {})


def _quarter_bounds(quarters_ahead: int) -> tuple[str, str]:
    """Start of the current calendar quarter through the end of the
    (quarters_ahead-1)th quarter after it, as YYYY-MM-DD strings.
    Recomputed from today's date on every call — never cached."""
    today = date.today()
    q0 = (today.month - 1) // 3  # 0-indexed current quarter
    start = date(today.year, q0 * 3 + 1, 1)
    end_offset = q0 + quarters_ahead - 1
    end_year = today.year + end_offset // 4
    end_month = (end_offset % 4) * 3 + 3
    end_day = calendar.monthrange(end_year, end_month)[1]
    end = date(end_year, end_month, end_day)
    return start.isoformat(), end.isoformat()


def _sf_get(path: str, params: dict | None = None) -> dict:
    """Make a direct REST GET via the SF CLI (for non-SOQL endpoints)."""
    url = path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    r, data = _sf_run(
        ["sf", "api", "request", "rest", url, "--target-org", _SF_TARGET_ORG, "--json"]
    )
    if r.returncode != 0:
        raise RuntimeError(f"SF REST GET failed: {r.stderr.strip()}")
    return data


def _sf_patch(path: str, body: dict) -> dict:
    """PATCH a Salesforce record via the SF CLI."""
    r = subprocess.run(
        [
            "sf", "api", "request", "rest", path,
            "--method", "PATCH",
            "--body", json.dumps(body),
            "--target-org", _SF_TARGET_ORG, "--json",
        ],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"SF REST PATCH failed: {r.stderr.strip()}")
    out = r.stdout.strip()
    return json.loads(out) if out else {"status": "updated"}


def _gong_get(path: str, params: dict | None = None) -> dict:
    if not settings.gong_access_key or not settings.gong_access_key_secret:
        raise RuntimeError(
            "Gong not configured. Add gong_access_key and gong_access_key_secret to .env.mcp"
        )
    r = httpx.get(
        f"https://api.gong.io{path}",
        params=params,
        auth=(settings.gong_access_key, settings.gong_access_key_secret),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _ms_token() -> str:
    if not settings.ms_tenant_id or not settings.ms_client_id or not settings.ms_client_secret:
        raise RuntimeError(
            "Microsoft Graph not configured. Add ms_tenant_id, ms_client_id, ms_client_secret to .env.mcp"
        )
    r = httpx.post(
        f"https://login.microsoftonline.com/{settings.ms_tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.ms_client_id,
            "client_secret": settings.ms_client_secret,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _ms_get(path: str, params: dict | None = None) -> dict:
    token = _ms_token()
    r = httpx.get(
        f"https://graph.microsoft.com/v1.0{path}",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ── Salesforce tools ──────────────────────────────────────────────────────────

@mcp.tool()
def sf_search_accounts(name: str, limit: int = 10) -> list[dict]:
    """Search Salesforce accounts by name. Returns [{id, name, type, owner, arr}]."""
    soql = f"SELECT Id, Name, Type, Owner.Name, AnnualRevenue FROM Account WHERE Name LIKE '%{name}%' LIMIT {min(limit, 50)}"
    result = _sf_query(soql)
    return [{"id": r["Id"], "name": r["Name"], "type": r.get("Type"), "owner": r.get("Owner", {}).get("Name"), "annual_revenue": r.get("AnnualRevenue")} for r in result.get("records", [])]


@mcp.tool()
def sf_get_account(account_id: str) -> dict:
    """Get full Salesforce account details including key fields and recent activity."""
    r, data = _sf_run(
        ["sf", "data", "get", "record", "--sobject", "Account", "--record-id", account_id,
         "--target-org", _SF_TARGET_ORG, "--json"]
    )
    if r.returncode != 0 or data.get("status") != 0:
        raise RuntimeError(f"SF get account failed: {data.get('message', r.stderr.strip())}")
    return data.get("result", {})


@mcp.tool()
def dealhub_get_quotes(opportunity_ids: list[str], include_lines: bool = False) -> list[dict]:
    """Read-only: the DealHub quotes on these opportunities, as synced into Salesforce.

    DealHub builds and approves quotes on its own servers and syncs each one to the SF
    Quote object (IsSyncing = true feeds the opp's Amount). Returns per quote: Status
    (Draft / approved / …), GrandTotal, MRR, delta MRR, term dates, billing terms, and
    with include_lines=True the line items. Opps with no quote are returned as
    {"OpportunityId": id, "quote": None} so callers can flag "needs a DealHub quote".
    Editing a quote is not possible here: changes must go through DealHub (approvals)."""
    if not opportunity_ids:
        return []
    ids = ", ".join(f"'{i}'" for i in opportunity_ids[:200])
    quote_cols = ", ".join(_f(k) for k in (
        "mrr", "delta_price_mrr", "tcv", "start_date", "end_date", "subscription_term",
        "billing_frequency", "payment_terms", "dealhub_quote_id"))
    quotes = _sf_query(
        "SELECT Id, Name, OpportunityId, Status, IsSyncing, GrandTotal, "
        f"{quote_cols}, LastModifiedDate FROM Quote WHERE OpportunityId IN ({ids}) "
        "ORDER BY IsSyncing DESC, LastModifiedDate DESC"
    ).get("records", [])
    if include_lines and quotes:
        qids = ", ".join(f"'{q['Id']}'" for q in quotes)
        lines: dict[str, list] = {}
        for l in _sf_query(
            "SELECT QuoteId, Product2.Name, Quantity, UnitPrice, Discount, TotalPrice "
            f"FROM QuoteLineItem WHERE QuoteId IN ({qids}) ORDER BY QuoteId, Product2.Name"
        ).get("records", []):
            lines.setdefault(l["QuoteId"], []).append(l)
        for q in quotes:
            q["lines"] = lines.get(q["Id"], [])
    seen = {q["OpportunityId"] for q in quotes}
    return quotes + [{"OpportunityId": i, "quote": None} for i in opportunity_ids if i not in seen]


@mcp.tool()
def sf_get_opportunities(account_id: str, limit: int = 20) -> list[dict]:
    """Get open and recently closed opportunities for an account."""
    soql = (
        f"SELECT Id, Name, StageName, Amount, CloseDate, ForecastCategory, "
        f"Probability, Owner.Name, Description, NextStep, Type, {_sf_dealhub_opp_fields()} "
        f"FROM Opportunity WHERE AccountId = '{account_id}' "
        f"AND (IsClosed = false OR CloseDate >= LAST_N_DAYS:90) "
        f"ORDER BY CloseDate ASC LIMIT {min(limit, 50)}"
    )
    result = _sf_query(soql)
    return result.get("records", [])


@mcp.tool()
def sf_get_contacts(account_id: str, limit: int = 20) -> list[dict]:
    """Get key contacts for an account."""
    soql = (
        f"SELECT Id, Name, Title, Email, Phone, LastActivityDate "
        f"FROM Contact WHERE AccountId = '{account_id}' "
        f"ORDER BY LastActivityDate DESC NULLS LAST LIMIT {min(limit, 50)}"
    )
    result = _sf_query(soql)
    return result.get("records", [])


@mcp.tool()
def sf_get_my_opportunities(
    stage_filter: str = "",
    type_filter: list[str] | None = None,
    quarters_ahead: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get all open opportunities owned by the configured user.

    stage_filter narrows by stage name substring.
    type_filter restricts to these Opportunity.Type values
      (e.g. ["Upsell", "Renewal"]; use your org's picklist values).
    quarters_ahead, if set, restricts CloseDate to the current calendar quarter
      through N-1 quarters ahead (quarters_ahead=2 -> this quarter + next quarter),
      recomputed from today's date on every call."""
    _require_sf_identity()
    where = f"OwnerId = '{_SF_OWNER_ID}' AND IsClosed = false"
    if stage_filter:
        where += f" AND StageName LIKE '%{stage_filter}%'"
    if type_filter:
        types = ", ".join(f"'{t}'" for t in type_filter)
        where += f" AND Type IN ({types})"
    if quarters_ahead:
        start, end = _quarter_bounds(quarters_ahead)
        where += f" AND CloseDate >= {start} AND CloseDate <= {end}"
    soql = (
        f"SELECT Id, Name, AccountId, Account.Name, Type, StageName, Amount, CloseDate, "
        f"ForecastCategory, Probability, NextStep, {_sf_dealhub_opp_fields()} "
        f"FROM Opportunity WHERE {where} ORDER BY CloseDate ASC LIMIT {min(limit, 200)}"
    )
    result = _sf_query(soql)
    return result.get("records", [])


@mcp.tool()
def sf_update_opportunity(opportunity_id: str, fields: dict, dry_run: bool = True) -> dict:
    """Update fields on a Salesforce opportunity YOU OWN.

    Guardrails (enforced in code, not just by prompt):
      • Refuses any opportunity not owned by the configured user.
      • Writes only allowed fields — forecast-sensitive: StageName, CloseDate,
        ForecastCategory, Amount, Probability; auto-safe: NextStep, Description.
      • Validates types, ranges, and picklist values before writing.
      • dry_run=True (default) returns the before/after diff WITHOUT writing.
        Set dry_run=False only after the user has approved the diff.
    Large Amount swings are surfaced as warnings for the reviewer (not blocked)."""
    before = _sf_assert_owner(opportunity_id)
    payload = _sf_validate_write(fields)

    diff = {k: {"before": before.get(k), "after": v} for k, v in payload.items()}
    warnings = []
    if "Amount" in payload and before.get("Amount"):
        old, new = float(before["Amount"]), float(payload["Amount"])
        if old > 0 and (new / old > 3 or new / old < 1 / 3):
            warnings.append(f"Amount swings {old:,.0f} → {new:,.0f} (>3x)")
    if "Amount" in payload and before.get(_f("dealhub_quote_id")):
        warnings.append(
            f"Opp has DealHub quote {before[_f('dealhub_quote_id')]}: Amount syncs from the quote, "
            f"so a manual Amount may be overwritten. Change the quote in DealHub instead."
        )

    if dry_run:
        return {
            "status": "dry_run", "opportunity_id": opportunity_id,
            "name": before.get("Name"), "diff": diff, "warnings": warnings,
        }

    r, data = _sf_run(
        ["sf", "data", "update", "record", "--sobject", "Opportunity",
         "--record-id", opportunity_id, "--target-org", _SF_TARGET_ORG, "--json",
         "--values", _sf_values_arg(payload)]
    )
    if r.returncode != 0 or data.get("status") != 0:
        raise RuntimeError(f"SF update failed: {data.get('message', r.stderr.strip())}")
    _sf_audit("update", opportunity_id, {k: before.get(k) for k in payload}, payload)
    return {"status": "updated", "opportunity_id": opportunity_id, "fields": payload, "warnings": warnings}


@mcp.tool()
def sf_create_opportunity(
    name: str,
    account_id: str,
    stage: str,
    close_date: str,
    amount: float | None = None,
    forecast_category: str = "",
    probability: int | None = None,
    next_step: str = "",
    description: str = "",
    dry_run: bool = True,
) -> dict:
    """Create a new Salesforce opportunity OWNED BY YOU.

    Guardrails (enforced in code):
      • OwnerId is forced to the configured user — cannot create an opp for anyone else.
      • Required: name, account_id, stage, close_date (YYYY-MM-DD, not in the past).
      • Optional fields (amount, forecast_category, probability, next_step,
        description) are validated the same way as updates.
      • dry_run=True (default) returns the record it WOULD create WITHOUT writing.
        Set dry_run=False only after the user has approved the new record."""
    _require_sf_identity()
    if not name.strip():
        raise ValueError("name is required")
    if not account_id.strip():
        raise ValueError("account_id is required")
    fields: dict = {"StageName": stage, "CloseDate": close_date}
    if amount is not None:
        fields["Amount"] = amount
    if forecast_category:
        fields["ForecastCategory"] = forecast_category
    if probability is not None:
        fields["Probability"] = probability
    if next_step:
        fields["NextStep"] = next_step
    if description:
        fields["Description"] = description
    payload = _sf_validate_write(fields)
    # Name/AccountId are create-only (not in the update allowlist); OwnerId is forced.
    record = {"Name": name, "AccountId": account_id, "OwnerId": _SF_OWNER_ID, **payload}

    if dry_run:
        return {"status": "dry_run", "action": "create", "record": record}

    try:
        r, data = _sf_run(
            ["sf", "data", "create", "record", "--sobject", "Opportunity",
             "--target-org", _SF_TARGET_ORG, "--json", "--values", _sf_values_arg(record)]
        )
    except RuntimeError as e:
        # The insert may have succeeded even though we cannot read the response,
        # so record the attempt rather than leaving an unaudited record behind.
        _sf_audit("create-unverified", "(unknown)", {}, record)
        raise RuntimeError(
            f"{e}\nThe record may or may not have been created - check Salesforce "
            f"for an Opportunity named {record.get('Name')!r} before retrying."
        ) from e
    if r.returncode != 0 or data.get("status") != 0:
        raise RuntimeError(f"SF create failed: {data.get('message', r.stderr.strip())}")
    new_id = (data.get("result") or {}).get("id") or (data.get("result") or {}).get("Id")
    _sf_audit("create", new_id or "(unknown)", {}, record)
    return {"status": "created", "opportunity_id": new_id, "record": record}


def _sf_insert_opportunity(record: dict) -> dict:
    """Insert an Opportunity and audit it. Shared by both create tools."""
    try:
        r, data = _sf_run(
            ["sf", "data", "create", "record", "--sobject", "Opportunity",
             "--target-org", _SF_TARGET_ORG, "--json", "--values", _sf_values_arg(record)]
        )
    except RuntimeError as e:
        _sf_audit("create-unverified", "(unknown)", {}, record)
        raise RuntimeError(
            f"{e}\nThe record may or may not have been created - check Salesforce "
            f"for an Opportunity named {record.get('Name')!r} before retrying."
        ) from e
    if r.returncode != 0 or data.get("status") != 0:
        detail = data.get("data") or data.get("message") or r.stderr.strip()
        raise RuntimeError(f"SF create failed: {detail}")
    new_id = (data.get("result") or {}).get("id") or (data.get("result") or {}).get("Id")
    _sf_audit("create", new_id or "(unknown)", {}, record)
    return {"status": "created", "opportunity_id": new_id, "record": record}


@mcp.tool()
def sf_create_placeholder_opportunity(
    account_id: str,
    name: str,
    mrr: float,
    term_start: str,
    term_end: str = "",
    stage: str = "Qualification",
    probability: int = 10,
    journey: str = "",
    usecases: str = "",
    description: str = "",
    dry_run: bool = True,
) -> dict:
    """Create a placeholder upsell opportunity OWNED BY YOU, deriving the boilerplate.

    Supply four things — account, name, monthly recurring revenue, term start — and
    the rest is derived so the record satisfies this org's validation rules without
    a trip to the Salesforce UI:

      • term_end   → the account's closest renewal date (sf_fields.closest_renewal_date),
                     so the add-on co-terminates with the contract (pass term_end to override).
      • Amount     → mrr × contract length in months. Amount is TOTAL CONTRACT VALUE in
                     this org; MRR itself (sf_fields.rr) is a rollup from line items and
                     cannot be written directly.
      • CloseDate  → end of the month before term_start, never earlier than today.
      • Contact    → primary business contact (sf_fields.primary_business_contact_o)
                     inherited from the account's most recent opportunity that has one.
      • Journey /  → inherited from the account's most recent opportunity that has them.
        Usecases     These describe what the customer does and vary by account, so if the
                     account has none, pass them explicitly rather than having them guessed.
      • Boilerplate→ Type, sub type, buyers, incumbents, deal type and record type from
                     config sf_defaults.placeholder_opportunity; Forecast Pipeline.

    Every field is validated up front and all problems are raised at once. dry_run=True
    (default) returns the record and its derivations WITHOUT writing — review the
    `derived` block, then call again with dry_run=False."""
    _require_sf_identity()
    if not name.strip():
        raise ValueError("name is required")
    if not account_id.strip():
        raise ValueError("account_id is required")

    try:
        start = datetime.strptime(term_start, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"term_start must be YYYY-MM-DD, got {term_start!r}")

    renewal_f, journey_f, usecases_f, contact_f = (
        _f(k) for k in ("closest_renewal_date", "journey", "usecases", "primary_business_contact_o"))
    defaults = _sf_placeholder_defaults()
    acct = _sf_get_record("Account", account_id, ["Id", "Name", renewal_f])

    if term_end:
        try:
            end = datetime.strptime(term_end, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"term_end must be YYYY-MM-DD, got {term_end!r}")
        end_source = "explicit"
    else:
        renewal = acct.get(renewal_f)
        if not renewal:
            raise ValueError(
                f"Account {acct.get('Name')!r} has no {renewal_f}, so the "
                f"term length cannot be derived. Pass term_end explicitly."
            )
        end = datetime.strptime(str(renewal)[:10], "%Y-%m-%d").date()
        end_source = f"Account.{renewal_f}"

    if end < start:
        raise ValueError(f"term_end {end} is before term_start {start}")

    months = _months_between(start, end)
    amount = round(float(mrr) * months, 2)

    # Close the month before the term starts, but never in the past.
    close = max(start - timedelta(days=1), date.today())

    # Inherit per-account context from the most recent opp that carries it.
    prior = _sf_query(
        f"SELECT {journey_f}, {usecases_f}, {contact_f} "
        f"FROM Opportunity WHERE AccountId = '{account_id}' "
        f"AND {journey_f} != null ORDER BY CreatedDate DESC LIMIT 1"
    ).get("records", [])
    contact_rec = _sf_query(
        f"SELECT {contact_f} FROM Opportunity "
        f"WHERE AccountId = '{account_id}' AND {contact_f} != null "
        "ORDER BY CreatedDate DESC LIMIT 1"
    ).get("records", [])

    inherited = prior[0] if prior else {}
    journey = journey or inherited.get(journey_f) or ""
    usecases = usecases or inherited.get(usecases_f) or ""
    contact = (
        inherited.get(contact_f)
        or (contact_rec[0].get(contact_f) if contact_rec else None)
    )

    missing = [
        label for label, val in
        (("journey", journey), ("usecases", usecases), ("primary business contact", contact))
        if not val
    ]
    if missing:
        raise ValueError(
            f"Account {acct.get('Name')!r} has no prior opportunity to inherit "
            f"{', '.join(missing)} from. Pass journey/usecases explicitly, or set a "
            f"primary business contact on an existing opportunity for this account."
        )

    fields = {
        "Name": name,
        "AccountId": account_id,
        "StageName": stage,
        "CloseDate": close.isoformat(),
        "Amount": amount,
        "Probability": probability,
        _f("contract_length"): months,
        _f("start_date"): start.isoformat(),
        journey_f: journey,
        usecases_f: usecases,
        contact_f: contact,
        "Description": description,
        **defaults,
    }
    payload = _sf_validate_create(fields)
    record = {**payload, "OwnerId": _SF_OWNER_ID}

    derived = {
        "account_name": acct.get("Name"),
        "term_start": start.isoformat(),
        "term_end": end.isoformat(),
        "term_end_source": end_source,
        "contract_length_months": months,
        "mrr": float(mrr),
        "amount_is_mrr_x_months": amount,
        "close_date": close.isoformat(),
        "journey_source": "inherited" if inherited.get(journey_f) else "argument",
    }
    if start.day != 1:
        derived["warning"] = (
            f"term_start is the {start.day}th, not the 1st. Contract length was computed "
            f"as {months} months by counting calendar months; a start this late in the "
            f"month is sometimes booked as starting the following month ({months - 1}). "
            f"Check the number before approving."
        )
    # DealHub: an upsell on an account with an open renewal goes on the renewal's quote,
    # not a separate opp. Warn rather than block; mid-term add-ons are still separate.
    renewals = _sf_query(
        "SELECT Id, Name, CloseDate FROM Opportunity "
        f"WHERE AccountId = '{account_id}' AND Type = '{_SF_RENEWAL_TYPE}' AND IsClosed = false"
    ).get("records", [])
    if renewals:
        derived["dealhub_warning"] = (
            "Account has an open renewal ("
            + "; ".join(f"{r['Name']} closing {r['CloseDate']}" for r in renewals)
            + "). Under DealHub, renewal + upsell is ONE quote on the renewal opp. If this is an "
            "add-on before that renewal, your org may book it as an amendment opp, not an upsell."
        )
    if dry_run:
        return {"status": "dry_run", "action": "create", "derived": derived, "record": record}
    return {**_sf_insert_opportunity(record), "derived": derived}


# ── Gong tools ────────────────────────────────────────────────────────────────

def _clean_html_text(text: str | None) -> str:
    """Strip HTML markup and unescape HTML entities from Salesforce rich text fields."""
    if not text:
        return ""
    s = re.sub(r"(?i)<br\s*/?>", "\n", text)
    s = re.sub(r"(?i)</?li>", "\n* ", s)
    s = re.sub(r"(?i)</?p>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return "\n".join(line.strip() for line in s.splitlines() if line.strip())


def _extract_url_text(text: str | None) -> str:
    """Extract first http/https URL from a string or HTML link."""
    if not text:
        return ""
    m = re.search(r"https?://[^\s\"<>]+", text)
    return m.group(0) if m else text.strip()


def _parse_duration_mins(duration_sec: float | int | None, duration_str: str | None) -> int:
    """Compute call duration in minutes."""
    if duration_sec:
        try:
            return round(float(duration_sec) / 60)
        except (ValueError, TypeError):
            pass
    if duration_str and ":" in str(duration_str):
        parts = str(duration_str).split(":")
        try:
            return round(int(parts[0]) + int(parts[1]) / 60)
        except (ValueError, TypeError, IndexError):
            pass
    return 0


def _gong_fields() -> dict[str, str]:
    """Gong-for-Salesforce sync field API names (sf_fields gong_* keys)."""
    return {k: _f(k) for k in (
        "gong_gong_call", "gong_call_id", "gong_call_start", "gong_call_duration",
        "gong_call_duration_sec", "gong_primary_account", "gong_call_brief",
        "gong_call_highlights_next_steps", "gong_call_key_points", "gong_view_call",
        "gong_participants_emails",
    )}


@mcp.tool()
def gong_search_calls(account_name: str, days_back: int = 90, limit: int = 10) -> list[dict]:
    """Search Gong for recent calls mentioning an account. Returns [{id, title, date, duration_mins, parties, brief, url}].
    Uses the Gong REST API if configured, otherwise falls back to Salesforce Gong sync."""
    if settings.gong_access_key and settings.gong_access_key_secret:
        from_dt = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = _gong_get("/v2/calls", {"fromDateTime": from_dt, "limit": min(limit, 50)})
        calls = result.get("calls", [])
        matched = [c for c in calls if account_name.lower() in (c.get("title") or "").lower()]
        return [
            {
                "id": c["id"],
                "title": c.get("title"),
                "date": c.get("started"),
                "duration_mins": round((c.get("duration") or 0) / 60),
                "parties": [p.get("name") for p in c.get("parties", [])],
                "source": "gong_api",
            }
            for c in matched
        ]

    # Fallback to Salesforce Gong sync
    G = _gong_fields()
    G_ACCT = G["gong_primary_account"][:-3] + "__r"   # relationship name of the account lookup
    safe_name = account_name.replace("'", "\\'")
    from_dt = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    soql = (
        f"SELECT Id, Name, {G['gong_call_id']}, {G['gong_call_start']}, {G['gong_call_duration']}, "
        f"{G['gong_call_duration_sec']}, {G['gong_primary_account']}, {G_ACCT}.Name, "
        f"{G['gong_call_brief']}, {G['gong_call_highlights_next_steps']}, {G['gong_view_call']}, "
        f"{G['gong_participants_emails']} "
        f"FROM {G['gong_gong_call']} "
        f"WHERE {G['gong_call_start']} >= {from_dt} "
        f"AND ({G_ACCT}.Name LIKE '%{safe_name}%' OR Name LIKE '%{safe_name}%') "
        f"ORDER BY {G['gong_call_start']} DESC LIMIT {min(limit, 50)}"
    )
    result = _sf_query(soql)
    records = result.get("records", [])
    out = []
    for r in records:
        parties_raw = r.get(G['gong_participants_emails']) or ""
        parties = [p.strip() for p in parties_raw.split(",") if p.strip()]
        duration = _parse_duration_mins(
            r.get(G['gong_call_duration_sec']), r.get(G['gong_call_duration'])
        )
        out.append({
            "id": r["Id"],
            "gong_id": r.get(G['gong_call_id']),
            "title": r.get("Name"),
            "date": r.get(G['gong_call_start']),
            "duration_mins": duration,
            "parties": parties,
            "account": (r.get(G_ACCT) or {}).get("Name"),
            "brief": r.get(G['gong_call_brief']),
            "url": _extract_url_text(r.get(G['gong_view_call'])),
            "source": "salesforce_gong_sync",
        })
    return out


@mcp.tool()
def gong_get_call_transcript(call_id: str) -> dict:
    """Get the full transcript and AI highlights for a Gong call."""
    if settings.gong_access_key and settings.gong_access_key_secret:
        transcript = _gong_get(f"/v2/calls/{call_id}/transcript")
        return transcript

    # Fallback to Salesforce Gong sync
    G = _gong_fields()
    G_ACCT = G["gong_primary_account"][:-3] + "__r"   # relationship name of the account lookup
    safe_id = call_id.replace("'", "\\'")
    soql = (
        f"SELECT Id, Name, {G['gong_call_id']}, {G['gong_call_start']}, "
        f"{G_ACCT}.Name, {G['gong_call_brief']}, {G['gong_call_key_points']}, "
        f"{G['gong_call_highlights_next_steps']}, {G['gong_view_call']} "
        f"FROM {G['gong_gong_call']} "
        f"WHERE Id = '{safe_id}' OR {G['gong_call_id']} = '{safe_id}' "
        f"LIMIT 1"
    )
    result = _sf_query(soql)
    records = result.get("records", [])
    if not records:
        return {"error": f"Call {call_id} not found in Salesforce Gong records"}
    rec = records[0]
    return {
        "call_id": rec.get(G['gong_call_id']) or rec["Id"],
        "title": rec.get("Name"),
        "date": rec.get(G['gong_call_start']),
        "account": (rec.get(G_ACCT) or {}).get("Name"),
        "transcript_available": False,
        "message": (
            "Verbatim word-for-word transcript is not stored in Salesforce Gong sync. "
            "Full recording and transcript can be viewed at the Gong URL."
        ),
        "url": _extract_url_text(rec.get(G['gong_view_call'])),
        "brief": rec.get(G['gong_call_brief']),
        "key_points": _clean_html_text(rec.get(G['gong_call_key_points'])),
        "highlights_next_steps": _clean_html_text(rec.get(G['gong_call_highlights_next_steps'])),
        "source": "salesforce_gong_sync",
    }


@mcp.tool()
def gong_get_call_highlights(call_id: str) -> dict:
    """Get AI-generated highlights, action items, and key moments for a Gong call."""
    if settings.gong_access_key and settings.gong_access_key_secret:
        result = _gong_get("/v2/calls/extensive", {"filter": json.dumps({"callIds": [call_id]})})
        calls = result.get("calls", [])
        return calls[0] if calls else {}

    # Fallback to Salesforce Gong sync
    G = _gong_fields()
    G_ACCT = G["gong_primary_account"][:-3] + "__r"   # relationship name of the account lookup
    safe_id = call_id.replace("'", "\\'")
    soql = (
        f"SELECT Id, Name, {G['gong_call_id']}, {G['gong_call_start']}, {G['gong_call_duration']}, "
        f"{G['gong_call_duration_sec']}, {G_ACCT}.Name, "
        f"{G['gong_call_brief']}, {G['gong_call_key_points']}, {G['gong_call_highlights_next_steps']}, "
        f"{G['gong_view_call']}, {G['gong_participants_emails']} "
        f"FROM {G['gong_gong_call']} "
        f"WHERE Id = '{safe_id}' OR {G['gong_call_id']} = '{safe_id}' "
        f"LIMIT 1"
    )
    result = _sf_query(soql)
    records = result.get("records", [])
    if not records:
        return {"error": f"Call {call_id} not found in Salesforce Gong records"}
    rec = records[0]
    parties_raw = rec.get(G['gong_participants_emails']) or ""
    parties = [p.strip() for p in parties_raw.split(",") if p.strip()]
    duration = _parse_duration_mins(
        rec.get(G['gong_call_duration_sec']), rec.get(G['gong_call_duration'])
    )
    brief = rec.get(G['gong_call_brief']) or ""
    key_points = _clean_html_text(rec.get(G['gong_call_key_points']))
    next_steps = _clean_html_text(rec.get(G['gong_call_highlights_next_steps']))
    url = _extract_url_text(rec.get(G['gong_view_call']))

    return {
        "id": rec["Id"],
        "gong_call_id": rec.get(G['gong_call_id']),
        "title": rec.get("Name"),
        "date": rec.get(G['gong_call_start']),
        "duration_mins": duration,
        "parties": parties,
        "account": (rec.get(G_ACCT) or {}).get("Name"),
        "brief": brief,
        "key_points": key_points,
        "highlights_next_steps": next_steps,
        "url": url,
        "highlights": {
            "brief": brief,
            "key_points": key_points,
            "action_items": next_steps,
        },
        "source": "salesforce_gong_sync",
    }


# ── OneDrive local tools (files synced via OneDrive desktop app) ──────────────

# Local OneDrive sync root (config.local.json paths.onedrive_root; ~ allowed).
ONEDRIVE_ROOT = Path((_LOCAL.get("paths") or {}).get("onedrive_root", "~/OneDrive")).expanduser()


@mcp.tool()
def onedrive_list(path: str = "", limit: int = 50) -> list[dict]:
    """List files and folders in OneDrive. path is relative to OneDrive root (e.g. 'Accounts' or 'Microsoft Teams Chat Files'). Empty path lists the root."""
    target = ONEDRIVE_ROOT / path if path else ONEDRIVE_ROOT
    if not target.exists():
        raise RuntimeError(f"Path not found in OneDrive: {path}. Root contains: {[p.name for p in ONEDRIVE_ROOT.iterdir()]}")
    items = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    result = []
    for item in items[:limit]:
        result.append({
            "name": item.name,
            "type": "folder" if item.is_dir() else "file",
            "path": str(item.relative_to(ONEDRIVE_ROOT)),
            "size_kb": round(item.stat().st_size / 1024, 1) if item.is_file() else None,
        })
    return result


@mcp.tool()
def onedrive_read_excel(path: str, sheet: str | None = None, max_rows: int = 200) -> dict:
    """Read an Excel file from OneDrive. path is relative to OneDrive root (e.g. 'Accounts/Account List.xlsx'). Returns sheet names and rows as list of dicts."""
    fpath = ONEDRIVE_ROOT / path
    if not fpath.exists():
        raise RuntimeError(f"File not found: {path}")
    wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
    sheet_names = wb.sheetnames
    ws = wb[sheet] if sheet and sheet in wb else wb.active
    rows = []
    headers = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(c) if c is not None else f"col_{j}" for j, c in enumerate(row)]
            continue
        if i > max_rows:
            break
        if any(c is not None for c in row):
            rows.append(dict(zip(headers, row)))
    return {"sheets": sheet_names, "active_sheet": ws.title, "headers": headers, "rows": rows, "row_count": len(rows)}


@mcp.tool()
def onedrive_search(query: str, extensions: list[str] | None = None, limit: int = 20) -> list[dict]:
    """Search OneDrive for files matching a name query. extensions filters by type e.g. ['xlsx', 'pptx', 'pdf']."""
    exts = {f".{e.lstrip('.')}" for e in extensions} if extensions else None
    matches = []
    for p in ONEDRIVE_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if exts and p.suffix.lower() not in exts:
            continue
        if query.lower() in p.name.lower():
            matches.append({
                "name": p.name,
                "path": str(p.relative_to(ONEDRIVE_ROOT)),
                "size_kb": round(p.stat().st_size / 1024, 1),
            })
        if len(matches) >= limit:
            break
    return matches


# ── Wispr Flow meeting notes ──────────────────────────────────────────────────

WISPR_MEETINGS = Path.home() / "Library/Application Support/Wispr Flow/meetings"


@mcp.tool()
def wispr_list_meetings(limit: int = 20) -> list[dict]:
    """List recent Wispr Flow meeting recordings. Returns [{id, duration_secs, has_transcript}]."""
    meetings = []
    for folder in sorted(WISPR_MEETINGS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue
        refined = folder / "refined.ndjson"
        has_transcript = refined.exists() and refined.stat().st_size > 0
        import os
        mtime = folder.stat().st_mtime
        from datetime import datetime
        meetings.append({
            "id": folder.name,
            "recorded_at": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
            "has_transcript": has_transcript,
        })
        if len(meetings) >= limit:
            break
    return meetings


@mcp.tool()
def wispr_get_transcript(meeting_id: str) -> dict:
    """Get the full transcript for a Wispr Flow meeting. Returns {meeting_id, lines: [{timestamp, speaker_id, text}]}."""
    refined = WISPR_MEETINGS / meeting_id / "refined.ndjson"
    if not refined.exists():
        raise RuntimeError(f"No transcript found for meeting {meeting_id}")
    lines = []
    for raw in refined.read_text().splitlines():
        entry = json.loads(raw)
        lines.append({
            "timestamp": entry.get("timestamp"),
            "speaker_id": entry.get("speaker", {}).get("id"),
            "speaker_name": entry.get("speaker", {}).get("name"),
            "text": entry.get("text", "").strip(),
        })
    full_text = " ".join(l["text"] for l in lines)
    return {"meeting_id": meeting_id, "line_count": len(lines), "lines": lines, "full_text": full_text}


# ── Atlassian (JIRA + Confluence) ─────────────────────────────────────────────

def _atlassian_auth() -> tuple[str, str]:
    if not settings.atlassian_email or not settings.atlassian_api_token:
        raise RuntimeError("Atlassian not configured. Add ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN to .env.mcp")
    return (settings.atlassian_email, settings.atlassian_api_token)


def _jira_get(path: str, params: dict | None = None) -> dict:
    base = settings.atlassian_base_url.rstrip("/")
    r = httpx.get(f"{base}/rest/api/3{path}", params=params, auth=_atlassian_auth(), timeout=30)
    r.raise_for_status()
    return r.json()


def _confluence_get(path: str, params: dict | None = None) -> dict:
    base = settings.atlassian_base_url.rstrip("/")
    r = httpx.get(f"{base}/wiki/rest/api{path}", params=params, auth=_atlassian_auth(), timeout=30)
    r.raise_for_status()
    return r.json()


def _confluence_post(path: str, body: dict) -> dict:
    base = settings.atlassian_base_url.rstrip("/")
    r = httpx.post(f"{base}/wiki/rest/api{path}", json=body, auth=_atlassian_auth(),
                   headers={"Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()


def _confluence_put(path: str, body: dict) -> dict:
    base = settings.atlassian_base_url.rstrip("/")
    r = httpx.put(f"{base}/wiki/rest/api{path}", json=body, auth=_atlassian_auth(),
                  headers={"Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def jira_search(jql: str, limit: int = 20) -> list[dict]:
    """Search JIRA with a JQL query. Returns [{key, summary, status, assignee, priority, updated}].
    Examples: jql='project=PROJ AND assignee=currentUser()' or jql='text~"Acme Corp" AND statusCategory!=Done'"""
    # Atlassian removed GET /rest/api/3/search on 2025-05-01; use /search/jql
    # (token-based pagination via nextPageToken; `fields` defaults to id only, so pass it).
    result = _jira_get("/search/jql", {"jql": jql, "maxResults": min(limit, 50),
                                       "fields": "summary,status,assignee,priority,updated"})
    out = []
    for issue in result.get("issues", []):
        f = issue["fields"]
        out.append({
            "key": issue["key"],
            "summary": f.get("summary"),
            "status": f.get("status", {}).get("name"),
            "assignee": (f.get("assignee") or {}).get("displayName"),
            "priority": (f.get("priority") or {}).get("name"),
            "updated": f.get("updated"),
        })
    return out


@mcp.tool()
def jira_get_issue(issue_key: str) -> dict:
    """Get full details for a JIRA issue including description and comments."""
    issue = _jira_get(f"/issue/{issue_key}")
    f = issue["fields"]
    comments = [(c["author"]["displayName"], c["body"]) for c in
                f.get("comment", {}).get("comments", [])[-5:]]
    return {
        "key": issue["key"],
        "summary": f.get("summary"),
        "status": f.get("status", {}).get("name"),
        "assignee": (f.get("assignee") or {}).get("displayName"),
        "description": f.get("description"),
        "comments": comments,
        "updated": f.get("updated"),
    }


@mcp.tool()
def confluence_search(query: str, space_key: str = "", limit: int = 10) -> list[dict]:
    """Search Confluence for pages matching a query. Returns [{id, title, space, url, excerpt}]."""
    cql = f'text~"{query}" AND type=page'
    if space_key:
        cql += f' AND space="{space_key}"'
    result = _confluence_get("/content/search", {"cql": cql, "limit": min(limit, 25),
                                                  "expand": "space,excerpt"})
    base = settings.atlassian_base_url.rstrip("/")
    return [{"id": p["id"], "title": p["title"],
             "space": p.get("space", {}).get("key"),
             "url": f"{base}/wiki{p.get('_links', {}).get('webui', '')}",
             "excerpt": p.get("excerpt", "")} for p in result.get("results", [])]


@mcp.tool()
def confluence_get_page(page_id: str) -> dict:
    """Get the full text content of a Confluence page."""
    result = _confluence_get(f"/content/{page_id}", {"expand": "body.storage,version,space"})
    import re
    raw_html = result.get("body", {}).get("storage", {}).get("value", "")
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = re.sub(r"\s+", " ", text).strip()
    return {
        "id": page_id,
        "title": result.get("title"),
        "space": result.get("space", {}).get("key"),
        "version": result.get("version", {}).get("number"),
        "text": text[:20000],
    }


@mcp.tool()
def confluence_create_page(space_key: str, title: str, content_html: str,
                            parent_page_id: str = "") -> dict:
    """Create a new Confluence page. content_html is the page body as HTML.
    Returns {id, url}. Only call after the user has approved the content."""
    body: dict = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": content_html, "representation": "storage"}},
    }
    if parent_page_id:
        body["ancestors"] = [{"id": parent_page_id}]
    result = _confluence_post("/content", body)
    base = settings.atlassian_base_url.rstrip("/")
    return {"id": result["id"], "title": result["title"],
            "url": f"{base}/wiki{result.get('_links', {}).get('webui', '')}"}


@mcp.tool()
def confluence_update_page(page_id: str, title: str, content_html: str) -> dict:
    """Update an existing Confluence page. Increments version automatically.
    Only call after the user has approved the content."""
    current = _confluence_get(f"/content/{page_id}", {"expand": "version"})
    new_version = current["version"]["number"] + 1
    body = {
        "type": "page",
        "title": title,
        "version": {"number": new_version},
        "body": {"storage": {"value": content_html, "representation": "storage"}},
    }
    result = _confluence_put(f"/content/{page_id}", body)
    base = settings.atlassian_base_url.rstrip("/")
    return {"id": result["id"], "title": result["title"],
            "url": f"{base}/wiki{result.get('_links', {}).get('webui', '')}"}


# ── Vendor knowledge base ─────────────────────────────────────────────────────

# Public help-center root (config.local.json kb_base_url), e.g. https://help.example.com
KB_BASE = (_LOCAL.get("kb_base_url") or "").rstrip("/")


_kb_sitemap: dict = {"at": 0.0, "urls": []}


def _kb_urls() -> list[tuple[str, str]]:
    """(url, lastmod) for every KB article, from the sitemap; refreshed daily per process.
    The KB is a single-page app with no public search API, but its sitemap lists every article
    by a descriptive slug, and articles are server-rendered."""
    import time
    if not KB_BASE:
        raise RuntimeError("kb_base_url is not set in config.local.json")
    if time.time() - _kb_sitemap["at"] > 86400 or not _kb_sitemap["urls"]:
        xml = httpx.get(f"{KB_BASE}/sitemap.xml", timeout=30).text
        _kb_sitemap["urls"] = re.findall(r"<loc>([^<]+)</loc>.*?<lastmod>([^<]+)</lastmod>", xml, re.S)
        _kb_sitemap["at"] = time.time()
    return _kb_sitemap["urls"]


@mcp.tool()
def kb_search(query: str, limit: int = 10) -> list[dict]:
    """Search the vendor's public knowledge base (config kb_base_url) by article slug.
    Matches query words against article URL slugs (e.g. 'session card' -> /help/session-card),
    ranked by words matched. Slug-only: try synonyms if nothing hits. Follow up with
    kb_get_article(url, match=...) to read just the relevant lines.
    Returns [{title, url, lastmod}]."""
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
    scored = []
    for url, lastmod in _kb_urls():
        slug = url.rsplit("/", 1)[-1].lower()
        score = sum(w in slug for w in words)
        if score:
            # most query words matched, then fewest unmatched slug words, then newest
            scored.append((score, -len(slug.split("-")), lastmod, url, slug))
    scored.sort(reverse=True)
    return [{"title": slug.replace("-", " ").capitalize(), "url": url, "lastmod": lastmod}
            for _, _, lastmod, url, slug in scored[:limit]]


@mcp.tool()
def kb_get_article(url: str, match: str = "") -> str:
    """Fetch a knowledge base article's body text (site navigation stripped).
    match: optional case-insensitive regex; when given, returns only the lines that match
    (much cheaper than the whole article)."""
    r = httpx.get(url, timeout=15, follow_redirects=True)
    r.raise_for_status()
    page = r.text
    m = re.search(r'class="hg-article-title"[^>]*>([^<]+)', page)  # <title> holds an excerpt, not the title
    title = html.unescape(m.group(1)).strip() if m else url
    start, end = page.find('class="hg-article-body"'), page.find('class="hg-article-body-footer"')
    if start != -1:
        page = page[start:end if end > start else None]
    page = re.sub(r"(?s)<(script|style)\b.*?</\1>", "", page)
    page = re.sub(r"<(br|p|li|h[1-6]|tr|div)\b[^>]*>", "\n", page)
    lines = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", l)).split()) for l in page.split("\n")]
    lines = [l for l in lines if l]
    if match:
        lines = [l for l in lines if re.search(match, l, re.I)]
    return (title + "\n" + "\n".join(lines))[:15000]


# ── Web search ────────────────────────────────────────────────────────────────
# Native WebSearch can fail behind some LLM gateways (providers that reject the
# server-side web_search tool), so search DuckDuckGo directly.

def _tls_context():
    import ssl
    import certifi
    ctx = ssl.create_default_context(cafile=certifi.where())
    # Optional extra root CA for a TLS-inspecting corporate proxy (config tls_extra_ca).
    p = os.path.expanduser(_LOCAL.get("tls_extra_ca") or "")
    if p and os.path.exists(p):
        ctx.load_verify_locations(p)
        # Some proxy roots lack a critical basicConstraints flag, which strict mode rejects.
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx


def _parse_ddg(page: str, limit: int) -> list[dict]:
    from urllib.parse import parse_qs, urlparse
    from lxml import html as lhtml
    out = []
    for body in lhtml.fromstring(page).xpath('//div[contains(@class, "result__body")]'):
        a = body.xpath('.//a[contains(@class, "result__a")]')
        if not a:
            continue
        href = a[0].get("href", "")
        if "duckduckgo.com/l/" in href:
            href = parse_qs(urlparse(href).query).get("uddg", [href])[0]
        if "duckduckgo.com/y.js" in href:
            continue
        snip = body.xpath('.//*[contains(@class, "result__snippet")]')
        out.append({"title": a[0].text_content().strip(), "url": href,
                    "snippet": snip[0].text_content().strip() if snip else ""})
        if len(out) >= limit:
            break
    return out


@mcp.tool()
def web_search(query: str, limit: int = 10) -> list[dict]:
    """Search the public web (DuckDuckGo). Use this instead of the built-in WebSearch,
    which can fail behind some LLM gateways. Returns [{title, url, snippet}];
    fetch a page with WebFetch for full content."""
    r = httpx.post("https://html.duckduckgo.com/html/", data={"q": query},
                   headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                   verify=_tls_context(), timeout=15, follow_redirects=True)
    r.raise_for_status()
    return _parse_ddg(r.text, max(1, min(limit, 25)))


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=19234)
