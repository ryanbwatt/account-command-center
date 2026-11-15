---
name: account-report
description: Pull API usage metrics for any customer across all their active video platform partner IDs. Fetches Entries, Plays/Streams, Live Viewing (hrs), Bandwidth (GB), Storage (GB), Unique Users, and captioning credits via the platform report API. Produces a per-PID summary table and a monthly CSV. Use when the user asks for an API usage report, usage metrics, or bandwidth/storage usage for a customer.
argument-hint: "<account name> [from <date>] [to <date>]"
disable-model-invocation: false
---

# /account-report

Pull API usage metrics across all active video platform partner IDs for a given customer. Produces a per-PID breakdown, a rolled-up total, and a monthly CSV.

## Metrics

| Metric | Script field | Platform API field(s) | Unit |
|---|---|---|---|
| Entries | `entries` | `total_media_entries`, `count_entries`, `added_entries` | count |
| Plays / Streams | `plays` | `total_plays`, `count_plays`, `play_evt_plays` | count |
| Live Viewing | `live_hrs` | `live_view_time`, `sum_live_view_time` (÷60) | hours |
| Bandwidth | `bw_gb` | `bandwidth_consumption`, `origin_bandwidth_consumption` (÷1024, already in MB) | GB |
| Storage | `storage_gb` | `average_storage`, `total_storage` (÷1024, already in MB) | GB |
| Unique Users | `users` | `total_end_users`, `unique_known_users`, `count_users` | count |
| Captioning Credits | `caption_credits` | `total_credit_used`, `credit_used` | credits |

**Report types called per PID:** API_USAGE (type 26), PARTNER_USAGE (type 201), CAPTION_USAGE (type 55 — unverified, may be wrong).

**Known gaps:**
- Live hours = 0 is common for accounts that don't use the platform's webcasting product, or if live data lives in a separate report type not yet confirmed.
- Captioning credits = `—` means either the account doesn't use captioning, or report type 55 is incorrect. Verify in the management console analytics if in doubt.

## Default date range

`account_report.from_date` from config (else January 1 of this year) → today, unless the user specifies otherwise.

---

<turns>
<1>
## Identify account and PIDs

If the user named an account, search Salesforce with `sf_search_accounts`. When multiple matches exist, confirm — there are often parent + division accounts for the same customer. Use the parent MRR and active-RR fields (`sf_fields.parent_total_agg_mrr`, `sf_fields.total_active_rr` in `config.local.json`) to identify the billing account.

Once you have the right SF account, collect video platform partner IDs:
1. Check the partner-ID fields (`sf_fields.platform_partner_id`, `sf_fields.main_platform_partner_id`) on the account.
2. Call `sf_get_account` on related accounts (same `sf_fields.parent_enrichment` value) to find additional PIDs.
3. Search Confluence: `confluence_search(query="<account name> partner ID PID")`.
4. Check the account `Description` field for embedded PID references.

Show the user the PID list with any notes (dev/test flags, paid dates, etc.) and confirm before proceeding.

**Configured account** — if the account matches `account_report.account_name` in `config.local.json`, use its `partner_ids` (and `dev_partner_ids` for dev/test flags) directly; do not re-derive. Run with `--all`.

Parse the user's date range if provided. Default: `from_date = account_report.from_date` (config), `to_date = today`.

**End your turn here. Wait for confirmation.**
</1>
<await_user_input></await_user_input>
<2>
## Get a KS for each PID

Each Partner ID requires its own platform session (KS). KS tokens are short-lived (hours), so they must be obtained fresh for each run.

### Current manual flow (vendor admin console)

For each PID:
1. Go to the vendor **admin console** → search the partner ID → click **Login as partner**.
2. A new management-console tab opens scoped to that partner.
3. Open DevTools (F12) → Network tab → filter on the platform API host → click any request → look in **Payload** for `ks=`.
4. Copy that value.

Repeat for every PID. A KS from a *different* partner's session does **not** grant access to another partner's data — each KS is scoped to exactly one partner.

**Do not use a KS from your own admin-console tab** — that KS is scoped to your internal account, not the customer's partner. Use the KS from the new management-console tab that opens after clicking "Login as".

Ask the user to paste all KS strings in one message — the script auto-detects which PID each belongs to by decoding the KS.

**Known friction:** This flow is manual and requires admin access for every partner. Future improvement: automate via the platform's admin impersonation API once we identify the right approach.

**End your turn here. Wait for the user to paste the KS strings.**
</2>
<await_user_input></await_user_input>
<3>
## Run the report

### Single PID

```bash
python3 scripts/pull_account_report.py \
  --ks "<KS>" \
  --partner-id <PID> \
  --from-date <YYYY-MM-DD> \
  --to-date <YYYY-MM-DD> \
  --csv ~/Downloads/<Account>_usage_monthly_<YYYY-MM-DD>.csv
```

### Multiple PIDs (paste all KS strings — script auto-detects PID from each)

```bash
python3 scripts/pull_account_report.py \
  --ks-list "KS_for_PID1" "KS_for_PID2" "KS_for_PID3" \
  --from-date <YYYY-MM-DD> \
  --to-date <YYYY-MM-DD> \
  --csv ~/Downloads/<Account>_usage_monthly_<YYYY-MM-DD>.csv
```

For the configured account use `--all`; add `--exclude-dev` to drop `account_report.dev_partner_ids`.

If a PID returns INVALID_PARTNER or PERMISSION_DENIED, note it and ask the user to obtain a fresh KS for that partner.

Always generate the monthly CSV for customer meetings — save to `~/Downloads/` with account name and today's date.

**End your turn after showing progress.**
</3>
<await_user_input></await_user_input>
<4>
## Present and sanity-check

Show the per-PID summary table:

| PID | Label | Entries | Plays/Streams | Unique Users | Live (hrs) | Bandwidth (GB) | Storage (GB) | Caption Credits |
|---|---|---|---|---|---|---|---|---|
| ... | | | | | | | | |
| **TOTAL** | | | | | | | | |

Then run a sanity check before handing to the user:

1. **All expected PIDs present?** Flag any that are missing or errored.
2. **Zeros suspicious?** Flag if a PID shows 0 plays/entries on what should be an active account.
3. **Units reasonable?** BW in the hundreds to thousands of GB is normal for active API accounts. Storage in the tens of thousands of GB is normal for large libraries.
4. **Live hours = 0?** Normal if the account is VoD-only. If the account has a webcasting PID, flag it — live data may be in a separate report type.
5. **Captioning credits = `—`?** Note it. Could be correct (no captioning usage) or could be wrong report type. Verify in the management console analytics if this matters for the meeting.
6. **Date range correct?** Confirm the period shown matches what was requested.

Confirm the CSV was saved: `~/Downloads/<Account>_usage_monthly_<date>.csv`.

Ask: "Would you like to update Salesforce, draft anything for the meeting, or review the monthly CSV?"
</4>
</turns>

## Rules
- Never hard-code `to_date` — always use today's date.
- KS strings must never be committed to git. They go in terminal commands only, never in files.
- If a PID returns an error, note it and continue with the others — don't abort.
- Raw field names from the API may not map 1:1 to billing labels. If there's ambiguity, show the raw field name alongside the value.
- For accounts with dev/test PIDs, surface them but let the user decide whether to include in billing numbers.
- The script auto-detects PIDs from `--ks-list` by base64-decoding each KS. No need to tell it which KS belongs to which PID.
