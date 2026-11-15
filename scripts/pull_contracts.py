#!/usr/bin/env python3
"""
Download every contract file (order forms, renewals, MSAs, POs) attached in Salesforce for
your accounts and file it into the per-account folders: <accounts_root>/<account>/Contracts/.

  - Accounts = the Account's account-manager field (sf_fields.account_manager) = sf_user_id (config.local.json), minus any names in
    config.local.json "exclude_accounts"; or --account NAME.
  - Files come from won opps, Contract records and the Account itself (ContentDocumentLink).
  - Active-term files (and anything titled MSA / Master (Services) Agreement) land in Contracts/;
    prior-term files land in Contracts/Expired/. Files filed in the wrong place are moved.
  - "Active term" = an Activated Contract that hasn't ended. If there is none but the newest won
    renewal was never contracted in CPQ (account shows "Needs Realignment"), its primary quote
    defines the active term instead.
  - Contracts/_active_contract_lines.csv is rewritten every run from the account's active
    DealHub subscription lines (DealHub replaced CPQ; prices are already annual).
    Only if DealHub has none does it fall back to the legacy CPQ quote's lines, annualized
    (term total ÷ prorate multiplier).
  - Idempotent: a file whose name already exists under Contracts/ is not downloaded again.

Usage:
  python3 scripts/pull_contracts.py --dry-run              # all accounts, print plan only
  python3 scripts/pull_contracts.py --account "Acme Corp"  # one account
  python3 scripts/pull_contracts.py --self-test
"""

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SUBFOLDERS = ["Notes", "Contracts", "Commercial", "Business Reviews", "Usage & Reports", "Technical", "Archive"]
KEEP_EXT = {"pdf", "docx", "doc"}
EVERGREEN = re.compile(r"\bMSA\b|master (services )?agreement", re.I)
# Upsell opps on a renewal usually close a day or a few weeks before the contract starts.
ACTIVE_LOOKBACK = timedelta(days=90)
CSV_COLS = ["account", "source", "product", "quantity", "annual_unit_price", "annual_line_total",
            "term_line_total", "term_years", "list_unit_price", "start", "end"]


def load_config() -> dict:
    # Walk up so this works from the main checkout and from .claude/worktrees/*.
    for d in Path(__file__).resolve().parents:
        p = d / "config.local.json"
        if p.exists():
            return json.loads(p.read_text())
    sys.exit("config.local.json not found (needs sf_username, sf_user_id)")


CFG = load_config()
ORG = CFG["sf_username"]
# Root of the per-account folders (config.local.json paths.accounts_root; ~ allowed).
ACCOUNTS_ROOT = Path(CFG.get("paths", {}).get("accounts_root", "~/Accounts")).expanduser()
# SF account name -> folder, where it isn't the plain name (see docs/account-folder-template.md)
FOLDER_OVERRIDES = dict(CFG.get("folder_overrides", {}))
_F = CFG.get("sf_fields", {})


def fld(key: str) -> str:
    """Org-specific Salesforce field API name from config.local.json sf_fields."""
    if key not in _F:
        sys.exit(f"config.local.json sf_fields.{key} is missing (Salesforce field API name)")
    return _F[key]


def rel(key: str) -> str:
    """Relationship name for a mapped lookup field (swap the trailing "c" of a custom field for "r")."""
    return fld(key)[:-1] + "r"


def query(soql: str) -> list[dict]:
    r = subprocess.run(["sf", "data", "query", "-o", ORG, "-q", soql, "--json"], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    if d.get("status") != 0:
        raise RuntimeError(f"SOQL failed: {d.get('message')}\n{soql}")
    return d["result"]["records"]


def ids_in(ids) -> str:
    return ",".join(f"'{i}'" for i in ids)


def folder_for(sf_name: str) -> str:
    # OneDrive can't end a folder name with '.', so "Inc." is stored as "Inc_".
    return FOLDER_OVERRIDES.get(sf_name) or re.sub(r"\.$", "_", sf_name)


def safe(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", title).strip()


def is_active(linked: set[str], active_ids: set[str], opp_close: dict[str, date], active_start: date | None, title: str) -> bool:
    if EVERGREEN.search(title) or linked & active_ids:
        return True
    return active_start is not None and any(
        opp_close.get(i) and opp_close[i] >= active_start - ACTIVE_LOOKBACK for i in linked
    )


def line_row(account, source, product, qty, term_total, multiplier, list_price, start, end) -> dict:
    qty, term_total, mult = qty or 0, term_total or 0, multiplier or 1
    annual = term_total / mult
    return {"account": account, "source": source, "product": product, "quantity": qty,
            "annual_unit_price": round(annual / qty, 6) if qty else 0, "annual_line_total": round(annual, 2),
            "term_line_total": round(term_total, 2), "term_years": mult, "list_unit_price": list_price,
            "start": start, "end": end}


def pull_account(acct: dict, dry: bool) -> dict:
    name, aid = acct["Name"], acct["Id"]
    root = ACCOUNTS_ROOT / folder_for(name)
    contracts_dir = root / "Contracts"
    today = date.today()
    (c_opp, contracted, q_start, q_term, q_opp2, q_primary, q_prod, q_qty, q_net, q_mult, q_list,
     q_estart, q_eend, q_obj, ql_obj, q_quote) = map(fld, [
        "sbqq_opportunity", "sbqq_contracted", "sbqq_startdate", "sbqq_subscriptionterm", "sbqq_opportunity2",
        "sbqq_primary", "sbqq_productname", "sbqq_quantity", "sbqq_nettotal", "sbqq_proratemultiplier",
        "sbqq_listprice", "sbqq_effectivestartdate", "sbqq_effectiveenddate", "sbqq_quote", "sbqq_quoteline",
        "sbqq_quote"])
    dh_qty, dh_total, dh_sales, dh_start, dh_end, dh_obj, dh_acct, dh_status = map(fld, [
        "dealhub_quantity", "dealhub_total_price", "dealhub_sales_price", "dealhub_subscription_start_date",
        "dealhub_subscription_end_date", "dealhub_subscription", "dealhub_account", "dealhub_status"])

    contracts = query(
        f"SELECT Id, ContractNumber, Status, StartDate, EndDate, {c_opp} FROM Contract WHERE AccountId = '{aid}'"
    )
    opps = query(
        f"SELECT Id, Name, Type, CloseDate, {contracted} FROM Opportunity WHERE AccountId = '{aid}' AND IsWon = true"
    )
    opp_close = {o["Id"]: date.fromisoformat(o["CloseDate"]) for o in opps}
    active = [c for c in contracts if c["Status"] == "Activated" and c["EndDate"] and date.fromisoformat(c["EndDate"]) >= today]
    active_ids = {c["Id"] for c in active} | {c[c_opp] for c in active if c[c_opp]}
    active_start = min((date.fromisoformat(c["StartDate"]) for c in active), default=None)
    term_label = ", ".join(f"contract {c['ContractNumber']} {c['StartDate']}..{c['EndDate']}" for c in active)

    # DealHub replaced CPQ; its subscription lines are the live book, CPQ lines migrated in.
    # The DealHub total price is already annual (matched CPQ term/multiplier on most migrated
    # lines; most misses were corrupt CPQ prices), so multiplier = 1.
    dh_rows = [
        line_row(name, f"dealhub {s[rel('dealhub_opportunity')]['Name'] if s[rel('dealhub_opportunity')] else 'subscription'}",
                 s[rel("dealhub_product")]["Name"] if s[rel("dealhub_product")] else None, s[dh_qty],
                 s[dh_total], 1, s[dh_sales], s[dh_start], s[dh_end])
        for s in query(
            f"SELECT {rel('dealhub_opportunity')}.Name, {rel('dealhub_product')}.Name, {dh_qty}, {dh_total}, "
            f"{dh_sales}, {dh_start}, {dh_end} "
            f"FROM {dh_obj} WHERE {dh_acct} = '{aid}' AND {dh_status} = 'Active' "
            f"AND {dh_end} >= TODAY ORDER BY {rel('dealhub_product')}.Name"
        )
    ]
    rows = []
    if not active:
        # Won renewal never contracted in CPQ -> no Contract row yet; its primary quote is the live term.
        renewals = [o for o in opps if o["Type"] == CFG.get("sf_defaults", {}).get("renewal_type", "Renewal") and not o[contracted]]
        latest_end = max((date.fromisoformat(c["EndDate"]) for c in contracts if c["EndDate"]), default=date.min)
        ren = max(renewals, key=lambda o: o["CloseDate"], default=None)
        if ren and date.fromisoformat(ren["CloseDate"]) >= latest_end - timedelta(days=180):
            quote = next(iter(query(
                f"SELECT Id, Name, {q_start}, {q_term} FROM {q_obj} "
                f"WHERE {q_opp2} = '{ren['Id']}' AND {q_primary} = true LIMIT 1"
            )), None)
            if quote and quote[q_start]:
                active_ids.add(ren["Id"])
                active_start = date.fromisoformat(quote[q_start])
                term_label = (f"quote {quote['Name']} from {quote[q_start]}, "
                              f"{quote[q_term]} mo — renewal won but NOT contracted in CPQ")
                for l in query(
                    f"SELECT {q_prod}, {q_qty}, {q_net}, {q_mult}, "
                    f"{q_list}, {q_estart}, {q_eend} FROM {ql_obj} "
                    f"WHERE {q_quote} = '{quote['Id']}' ORDER BY {q_prod}"
                ):
                    rows.append(line_row(name, f"quote {quote['Name']} (not contracted)", l[q_prod],
                                         l[q_qty], l[q_net], l[q_mult],
                                         l[q_list], l[q_estart], l[q_eend]))
    # Legacy CPQ quote lines only when DealHub has nothing for the account.
    rows = dh_rows or rows

    entities = [aid] + [c["Id"] for c in contracts] + list(opp_close)
    docs: dict[str, dict] = {}
    for i in range(0, len(entities), 100):
        for l in query(
            "SELECT LinkedEntityId, ContentDocumentId, ContentDocument.Title, ContentDocument.FileExtension, "
            "ContentDocument.CreatedDate, ContentDocument.LatestPublishedVersionId "
            f"FROM ContentDocumentLink WHERE LinkedEntityId IN ({ids_in(entities[i:i + 100])})"
        ):
            cd = l["ContentDocument"]
            if (cd["FileExtension"] or "").lower() not in KEEP_EXT:
                continue
            doc = docs.setdefault(l["ContentDocumentId"], {**cd, "linked": set()})
            doc["linked"].add(l["LinkedEntityId"])

    existing = {p.name.lower(): p for p in contracts_dir.rglob("*") if p.is_file()} if contracts_dir.exists() else {}
    planned, moves, seen, skipped = [], [], set(), 0
    for doc in sorted(docs.values(), key=lambda d: d["CreatedDate"]):
        fname = f"{doc['CreatedDate'][:10]}_salesforce_{safe(doc['Title'])}.{doc['FileExtension'].lower()}"
        # ponytail: the same PDF attached to several opps has the same name+date, so name-dedupe catches it;
        # two different docs with identical title and date would collide (first wins).
        if fname.lower() in seen:  # macOS/OneDrive names are case-insensitive
            skipped += 1
            continue
        seen.add(fname.lower())
        sub = contracts_dir if is_active(doc["linked"], active_ids, opp_close, active_start, doc["Title"]) else contracts_dir / "Expired"
        if fname.lower() in existing:
            skipped += 1
            if existing[fname.lower()].parent != sub:
                moves.append((existing[fname.lower()], sub / fname))
            continue
        planned.append((sub / fname, doc["LatestPublishedVersionId"]))

    print(f"\n{name} -> {root.relative_to(ACCOUNTS_ROOT.parent)}{'' if root.exists() else '  (new folder)'}")
    print(f"  active term: {term_label or 'none'}")
    for path, _ in planned:
        print(f"  + {path.relative_to(contracts_dir)}")
    for src, dst in moves:
        print(f"  ~ {src.relative_to(contracts_dir)} -> {dst.relative_to(contracts_dir)}")
    print(f"  {len(planned)} to download, {len(moves)} to move, {skipped} already filed or duplicate, {len(rows)} contract lines")

    if not dry:
        for s in SUBFOLDERS:
            (root / s).mkdir(parents=True, exist_ok=True)
        for src, dst in moves:
            dst.parent.mkdir(exist_ok=True)
            src.rename(dst)
        for path, vid in planned:
            path.parent.mkdir(exist_ok=True)
            r = subprocess.run(
                ["sf", "api", "request", "rest", f"/services/data/v62.0/sobjects/ContentVersion/{vid}/VersionData",
                 "-o", ORG, "--stream-to-file", str(path)],
                capture_output=True, text=True,
            )
            if r.returncode != 0 or not path.exists() or path.stat().st_size == 0:
                path.unlink(missing_ok=True)
                print(f"  ! failed: {path.name}: {r.stderr.strip()[:200]}")
    return {"account": name, "folder": root, "downloaded": len(planned), "moved": len(moves),
            "active": bool(term_label), "fallback": "NOT contracted" in term_label, "rows": rows}


def write_lines(results: list[dict]):
    # One CSV per folder, so accounts sharing a folder (via folder_overrides) don't overwrite each other.
    by_folder = defaultdict(list)
    for r in results:
        by_folder[r["folder"]].extend(r["rows"])
    for folder, rows in by_folder.items():
        path = folder / "Contracts" / "_active_contract_lines.csv"
        if not rows:
            path.unlink(missing_ok=True)
            continue
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_COLS)
            w.writeheader()
            w.writerows(rows)


def self_test():
    assert folder_for("Initech Inc.") == "Initech Inc_"
    assert folder_for("Globex Co., Inc.") == "Globex Co., Inc_"
    FOLDER_OVERRIDES["Globex Inc L&D"] = "Globex Inc"   # example override
    assert folder_for("Globex Inc L&D") == "Globex Inc"
    assert folder_for("Acme Corp") == "Acme Corp"
    start, close = date(2026, 4, 1), {"o_up": date(2026, 3, 31), "o_old": date(2025, 5, 8)}
    assert is_active({"o_up"}, set(), close, start, "renewal - signed")        # co-termed upsell
    assert not is_active({"o_old"}, set(), close, start, "2025 renewal")       # prior term
    assert is_active({"o_old"}, set(), close, start, "Vendor MSA")            # evergreen
    assert is_active({"c1"}, {"c1"}, close, start, "x")                        # on active contract
    assert not is_active({"o_old"}, set(), close, None, "x")                   # no active contract
    assert not is_active({"o_old"}, set(), close, start, "went back on their agreement")
    assert safe('a/b: "c"') == "a_b_ _c_"
    # Example 3-year line: 30,000 GB at $1.00 for the term -> $10,000/yr, ~$0.3333/GB/yr
    r = line_row("A", "c", "BW", 30000, 30000 * 1.0, 3, 0.5, None, None)
    assert r["annual_line_total"] == 10000.0 and abs(r["annual_unit_price"] - 0.333333) < 1e-6
    assert line_row("A", "c", "x", 0, 0, None, 0, None, None)["annual_unit_price"] == 0
    print("self-test ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", help="SF account name (LIKE match); default = all accounts you manage")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test()
        sys.exit()
    # --account narrows within your book; it never reaches other reps' same-named accounts.
    where = f"{fld('account_manager')} = '{CFG['sf_user_id']}'"
    if a.account:
        where += f" AND Name LIKE '%{a.account.replace(chr(39), chr(92) + chr(39))}%'"
    excluded = set(CFG.get("exclude_accounts", []))
    accounts = [x for x in query(f"SELECT Id, Name FROM Account WHERE {where} ORDER BY Name") if x["Name"] not in excluded]
    if not accounts:
        sys.exit(f"No accounts matched: {where}")
    results = [pull_account(acct, a.dry_run) for acct in accounts]
    if not a.dry_run:
        write_lines(results)
    print(f"\n{'DRY RUN — ' if a.dry_run else ''}{sum(r['downloaded'] for r in results)} files, "
          f"{sum(r['moved'] for r in results)} moved, across {len(results)} accounts")
    for r in results:
        if not r["active"]:
            print(f"  no active contract: {r['account']}")
        elif r["fallback"]:
            print(f"  renewal not contracted in CPQ (using primary quote): {r['account']}")
