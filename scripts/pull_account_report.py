#!/usr/bin/env python3
"""
Pull API usage metrics for one customer across their video platform partner IDs.

Metrics:
  - Entries (count)
  - Plays / Streams (count)
  - Live Viewing (hours)
  - Bandwidth (GB)
  - Storage (GB)
  - Captioning credits used

Usage:
  python3 pull_account_report.py --ks <KS> [--partner-id <PID>] [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD]
  python3 pull_account_report.py --secret <ADMIN_SECRET> --partner-id <PID>
  python3 pull_account_report.py --ks <KS> --all                  # all partner IDs from config
  python3 pull_account_report.py --ks <KS> --all --csv report.csv # monthly CSV output

Config ($CC_DIR/config.local.json, gitignored):
  "platform_api_base":      "https://api.example-video.com/v1/service"
  "platform_object_prefix": API objectType prefix, e.g. "Vendor" -> "VendorReportInputFilter"
  "account_report": {
      "account_name":    "Acme Corp",
      "partner_ids":     [1000001, 1000002],
      "dev_partner_ids": [1000002],        # dropped with --exclude-dev
      "from_date":       "2026-01-01"      # optional default start date
  }
"""

import argparse
import base64
import csv
import getpass
import json
import os
import sys
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path
import urllib.request
import urllib.parse

_CFG_PATH = Path(__file__).resolve().parent.parent / "config.local.json"
try:
    _LOCAL = json.loads(_CFG_PATH.read_text())
except (OSError, ValueError):
    _LOCAL = {}

PLATFORM_API = _LOCAL.get("platform_api_base", "").rstrip("/")
OBJ_PREFIX = _LOCAL.get("platform_object_prefix", "")
_AR = _LOCAL.get("account_report", {})
ACCOUNT_NAME = _AR.get("account_name", "")
ACCOUNT_PIDS = {int(p): f"PID {p}" for p in _AR.get("partner_ids", [])}
DEV_PIDS = {int(p) for p in _AR.get("dev_partner_ids", [])}
DEFAULT_FROM = _AR.get("from_date", f"{date.today().year}-01-01")

REPORT_TYPES = {
    "API_USAGE":     "26",
    "PARTNER_USAGE": "201",
    "CAPTION_USAGE": "55",   # captioning credits (captions, transcription, translation)
}


def decode_ks_partner(ks: str) -> int:
    """Extract partner ID from a platform session (KS) string (v2 format: base64('v2|pid|...'))."""
    try:
        pad = ks + "=" * (4 - len(ks) % 4)
        decoded = base64.b64decode(pad.replace("-", "+").replace("_", "/"), validate=False).decode("utf-8", errors="ignore")
        parts = decoded.split("|")
        if parts[0] == "v2" and len(parts) > 1:
            return int(parts[1])
    except Exception:
        pass
    return 0


def platform_post(service: str, action: str, params: dict) -> dict:
    if not PLATFORM_API:
        sys.exit(f"platform_api_base missing in {_CFG_PATH}")
    url = f"{PLATFORM_API}/{service}/action/{action}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def get_ks(secret: str, partner_id: int) -> str:
    result = platform_post("session", "start", {
        "format": 1,
        "partnerId": partner_id,
        "secret": secret,
        "type": 2,  # ADMIN
        "expiry": 86400,
    })
    if isinstance(result, str):
        return result
    raise RuntimeError(f"KS generation failed: {result}")


def get_ks_by_login(email: str, partner_id: int = 0) -> str:
    """Generate a KS using platform email/password login (same credentials as the management console)."""
    password = os.environ.get("PLATFORM_PASSWORD") or getpass.getpass(f"Platform password for {email}: ")
    result = platform_post("user", "loginByLoginId", {
        "format": 1,
        "loginId": email,
        "password": password,
        "partnerId": partner_id,
        "expiry": 86400,
    })
    if isinstance(result, str) and result:
        return result
    raise RuntimeError(f"Login failed: {result}")


def get_report_total(ks: str, report_type: str, partner_id: int,
                     from_ts: int, to_ts: int) -> dict:
    params = {
        "format": 1,
        "ks": ks,
        "partnerId": partner_id,  # impersonate target partner using caller's privileged KS
        "reportType": report_type,
        "reportInputFilter[objectType]": f"{OBJ_PREFIX}ReportInputFilter",
        "reportInputFilter[fromDate]": from_ts,
        "reportInputFilter[toDate]": to_ts,
        "pager[objectType]": f"{OBJ_PREFIX}FilterPager",
    }
    return platform_post("report", "getTotal", params)


def parse_report(result: dict) -> dict:
    """Parse getTotal response into {field: value} dict."""
    if "objectType" in result and "Exception" in result.get("objectType", ""):
        raise RuntimeError(result.get("message", str(result)))
    if "header" in result and "data" in result:
        headers = [h.strip() for h in result["header"].split(",")]
        values  = [v.strip() for v in result["data"].split(",")]
        return dict(zip(headers, values))
    return {}


def to_gb(val: str) -> float:
    try:
        return float(val) / 1024 / 1024 / 1024
    except Exception:
        return 0.0


def to_mb(val: str) -> float:
    """Convert MB (as returned by PARTNER_USAGE) to GB."""
    try:
        return float(val) / 1024
    except Exception:
        return 0.0


def to_hrs(val: str) -> float:
    try:
        return float(val) / 60.0
    except Exception:
        return 0.0


def to_int(val: str) -> int:
    try:
        return int(float(val))
    except Exception:
        return 0


ENTRY_FIELDS   = {"total_media_entries", "count_entries", "added_entries", "count_videos"}
PLAY_FIELDS    = {"total_plays", "count_plays", "sum_plays", "play_evt_plays", "total_views"}
LIVE_FIELDS    = {"live_view_time", "sum_live_view_time"}
BW_FIELDS      = {"bandwidth_consumption", "origin_bandwidth_consumption"}
STORAGE_FIELDS = {"average_storage", "total_storage"}
USER_FIELDS    = {"total_end_users", "unique_known_users", "count_users"}
CAPTION_FIELDS = {"total_credit_used", "credit_used", "caption_credit_used", "total_credits_used"}


def extract_metrics(raw: dict) -> dict:
    """Extract billing metrics + unique users + captioning credits from a raw API field dict."""
    m = {"entries": 0, "plays": 0, "live_hrs": 0.0, "bw_gb": 0.0, "storage_gb": 0.0,
         "users": 0, "caption_credits": 0.0}
    for field, val in raw.items():
        fl = field.lower()
        if fl in ENTRY_FIELDS:
            m["entries"] = max(m["entries"], to_int(val))
        elif fl in PLAY_FIELDS:
            m["plays"] = max(m["plays"], to_int(val))
        elif fl in LIVE_FIELDS:
            m["live_hrs"] = max(m["live_hrs"], to_hrs(val))
        elif fl in BW_FIELDS:
            m["bw_gb"] = max(m["bw_gb"], to_mb(val))
        elif fl in STORAGE_FIELDS:
            m["storage_gb"] = max(m["storage_gb"], to_mb(val))
        elif fl in USER_FIELDS:
            m["users"] = max(m["users"], to_int(val))
        elif fl in CAPTION_FIELDS:
            try:
                m["caption_credits"] = max(m["caption_credits"], float(val))
            except Exception:
                pass
    return m


def pull_pid_metrics(ks: str, partner_id: int, label: str,
                     from_ts: int, to_ts: int) -> dict:
    """Pull both report types for one PID and merge into a metrics dict."""
    metrics = {
        "pid": partner_id, "label": label,
        "entries": 0, "plays": 0, "live_hrs": 0.0, "bw_gb": 0.0, "storage_gb": 0.0,
        "users": 0, "caption_credits": 0.0, "errors": [], "raw": {},
    }

    for rtype_name, rtype_id in REPORT_TYPES.items():
        try:
            result = get_report_total(ks, rtype_id, partner_id, from_ts, to_ts)
            raw = parse_report(result)
            metrics["raw"][rtype_name] = raw
            m = extract_metrics(raw)
            for k in ("entries", "plays", "users"):
                metrics[k] = max(metrics[k], m[k])
            for k in ("live_hrs", "bw_gb", "storage_gb", "caption_credits"):
                metrics[k] = max(metrics[k], m[k])
        except RuntimeError as e:
            metrics["errors"].append(f"{rtype_name}: {e}")
        except Exception as e:
            metrics["errors"].append(f"{rtype_name}: unexpected error — {e}")

    return metrics


def month_ranges(from_date: date, to_date: date):
    """Yield (month_label, from_ts, to_ts) for each calendar month in range."""
    y, m = from_date.year, from_date.month
    end_y, end_m = to_date.year, to_date.month
    while (y, m) <= (end_y, end_m):
        last_day = monthrange(y, m)[1]
        month_start = date(y, m, 1)
        month_end = date(y, m, last_day)
        if month_end > to_date:
            month_end = to_date
        from_ts = int(datetime(y, m, 1).timestamp())
        to_ts   = int(datetime(y, m, month_end.day, 23, 59, 59).timestamp())
        yield f"{y}-{m:02d}", from_ts, to_ts
        m += 1
        if m > 12:
            m = 1
            y += 1


def pull_monthly_csv(ks_map: dict, pid_map: dict, from_date: date, to_date: date,
                     csv_path: str):
    """Pull monthly totals (summed across all PIDs) and write to CSV."""
    fieldnames = ["month", "entries", "plays", "users", "live_hrs", "bw_gb", "storage_gb", "caption_credits"]
    rows = []

    months = list(month_ranges(from_date, to_date))
    total_calls = len(months) * len(pid_map) * len(REPORT_TYPES)
    done = 0

    for month_label, from_ts, to_ts in months:
        totals = {"month": month_label, "entries": 0, "plays": 0, "users": 0,
                  "live_hrs": 0.0, "bw_gb": 0.0, "storage_gb": 0.0, "caption_credits": 0.0}
        for pid, label in pid_map.items():
            for rtype_name, rtype_id in REPORT_TYPES.items():
                done += 1
                print(f"\r  [{done}/{total_calls}] {month_label} / PID {pid} / {rtype_name}  ", end="", flush=True)
                try:
                    result = get_report_total(ks_map[pid], rtype_id, pid, from_ts, to_ts)
                    raw = parse_report(result)
                    m = extract_metrics(raw)
                    totals["entries"]      += m["entries"]        # sum across PIDs
                    totals["plays"]        += m["plays"]          # sum across PIDs
                    totals["users"]         = max(totals["users"], m["users"])   # unique users can overlap
                    totals["live_hrs"]     += m["live_hrs"]
                    totals["bw_gb"]        += m["bw_gb"]
                    totals["storage_gb"]    = max(totals["storage_gb"],    m["storage_gb"])
                    totals["caption_credits"] = max(totals["caption_credits"], m["caption_credits"])
                except Exception as e:
                    print(f"\n  ⚠ {month_label} PID {pid} {rtype_name}: {e}")
        rows.append(totals)

    print()  # newline after progress

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "month":         row["month"],
                "entries":       row["entries"],
                "plays":         row["plays"],
                "users":         row["users"],
                "live_hrs":      f"{row['live_hrs']:.2f}",
                "bw_gb":         f"{row['bw_gb']:.4f}",
                "storage_gb":    f"{row['storage_gb']:.4f}",
                "caption_credits": f"{row['caption_credits']:.1f}",
            })

    print(f"  CSV written → {csv_path}")


def print_table(rows: list, period: str):
    print(f"\n{'='*90}")
    print(f"  API Usage Report")
    print(f"  Period: {period}")
    print(f"{'='*90}")
    hdr = (f"{'PID':<10} {'Label':<20} {'Entries':>10} {'Plays':>12} {'Users':>10} "
           f"{'Live (hrs)':>12} {'BW (GB)':>12} {'Storage (GB)':>13} {'Caption Credits':>14}")
    print(f"\n{hdr}")
    print("-" * len(hdr))

    totals = {"entries": 0, "plays": 0, "users": 0, "live_hrs": 0.0,
              "bw_gb": 0.0, "storage_gb": 0.0, "caption_credits": 0.0}
    for r in rows:
        rc = f"{r['caption_credits']:>14.1f}" if r['caption_credits'] else f"{'—':>14}"
        print(f"{r['pid']:<10} {r['label']:<20} {r['entries']:>10,} {r['plays']:>12,} "
              f"{r['users']:>10,} {r['live_hrs']:>12.2f} {r['bw_gb']:>12.4f} {r['storage_gb']:>13.4f} {rc}")
        for k in totals:
            totals[k] += r[k]
        for e in r.get("errors", []):
            print(f"           ⚠ {e}")

    print("-" * len(hdr))
    rc_total = f"{totals['caption_credits']:>14.1f}" if totals['caption_credits'] else f"{'—':>14}"
    print(f"{'TOTAL':<10} {'':<20} {totals['entries']:>10,} {totals['plays']:>12,} "
          f"{totals['users']:>10,} {totals['live_hrs']:>12.2f} {totals['bw_gb']:>12.4f} "
          f"{totals['storage_gb']:>13.4f} {rc_total}")
    print(f"\n{'='*90}\n")


def main():
    parser = argparse.ArgumentParser(description="Pull video platform API usage report")

    auth = parser.add_mutually_exclusive_group(required=True)
    auth.add_argument("--ks",      help="Pre-generated platform session (KS) string")
    auth.add_argument("--ks-list", nargs="+", metavar="KS",
                      help="Multiple KS strings (one per PID) — partner ID auto-detected from each")
    auth.add_argument("--secret",  help="Admin secret (used with --partner-id to generate KS)")
    auth.add_argument("--login",   metavar="EMAIL",
                      help="Platform account email — prompts for password, generates KS via user.loginByLoginId")

    parser.add_argument("--partner-id",   type=int,
                        help="Platform partner ID (required when not using --ks-list)")
    parser.add_argument("--all",          action="store_true",
                        help="Pull all account_report.partner_ids from config")
    parser.add_argument("--exclude-dev",  action="store_true",
                        help="Exclude account_report.dev_partner_ids")
    parser.add_argument("--from-date",    default=DEFAULT_FROM,
                        help=f"Start date YYYY-MM-DD (default: {DEFAULT_FROM})")
    parser.add_argument("--to-date",      default=date.today().isoformat(),
                        help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--csv",          metavar="FILE",
                        help="Also write monthly breakdown to this CSV path")
    parser.add_argument("--raw",          action="store_true",
                        help="Also print raw API response fields")
    args = parser.parse_args()

    from_date = datetime.strptime(args.from_date, "%Y-%m-%d").date()
    to_date   = datetime.strptime(args.to_date,   "%Y-%m-%d").date()
    from_ts   = int(datetime(from_date.year, from_date.month, from_date.day).timestamp())
    to_ts     = int(datetime(to_date.year,   to_date.month,   to_date.day, 23, 59, 59).timestamp())
    period    = f"{args.from_date} → {args.to_date}"

    if args.all:
        if not ACCOUNT_PIDS:
            parser.error(f"--all needs account_report.partner_ids in {_CFG_PATH}")
        if ACCOUNT_NAME:
            print(f"Account: {ACCOUNT_NAME}")
        pid_map = {pid: label for pid, label in ACCOUNT_PIDS.items()
                   if not (args.exclude_dev and pid in DEV_PIDS)}
    elif args.partner_id:
        pid_map = {args.partner_id: f"PID {args.partner_id}"}
    elif args.ks_list:
        pid_map = {}  # will be populated from decoded KS strings below
    else:
        parser.error("Specify --partner-id <PID>, --all, or --ks-list <KS ...>")

    # Build a {pid: ks} map for the run
    ks_map = {}
    if args.ks_list:
        for ks_val in args.ks_list:
            pid = decode_ks_partner(ks_val)
            if pid:
                ks_map[pid] = ks_val
                print(f"  Decoded KS → PID {pid}")
            else:
                print(f"  ⚠ Could not decode PID from KS: {ks_val[:30]}...")
        if not ks_map:
            parser.error("No valid KS strings decoded — check inputs")
        # Override pid_map to only include PIDs we have a KS for
        pid_map = {pid: pid_map.get(pid, f"PID {pid}") for pid in ks_map}
    else:
        ks = args.ks
        if not ks and args.login:
            print(f"Logging in as {args.login}...")
            ks = get_ks_by_login(args.login, partner_id=args.partner_id or 0)
            print(f"KS obtained: {ks[:40]}...\n")
        elif not ks:
            if not args.partner_id:
                parser.error("--secret requires --partner-id to generate a KS")
            print(f"Generating KS for partner {args.partner_id}...")
            ks = get_ks(args.secret, args.partner_id)
            print(f"KS generated: {ks[:40]}...\n")
        ks_map = {pid: ks for pid in pid_map}

    rows = []
    for pid, label in pid_map.items():
        print(f"Pulling PID {pid} ({label})...")
        row = pull_pid_metrics(ks_map[pid], pid, label, from_ts, to_ts)
        rows.append(row)

        if args.raw:
            for rtype, fields in row["raw"].items():
                print(f"  {rtype}:")
                for k, v in fields.items():
                    print(f"    {k}: {v}")

    print_table(rows, period)

    if args.csv:
        print(f"Building monthly CSV ({len(list(month_ranges(from_date, to_date)))} months × {len(pid_map)} PIDs)...")
        pull_monthly_csv(ks_map, pid_map, from_date, to_date, args.csv)


if __name__ == "__main__":
    main()
