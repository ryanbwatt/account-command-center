---
name: account-audit
description: Audit one customer's contracted commits against actual Salesforce usage — what to upsell, whether there's churn risk, and which paid components need a manual check. Optionally builds the customer-facing rightsizing spreadsheet. Use for "/account-audit <customer>", "what should we upsell <customer>", "is <customer> a churn risk", overage/rightsizing requests.
---

# Account Audit (`/account-audit <customer>`)

Answers three questions for one account: **Upsell?** **Churn risk?** **What can't we see?**
Read-only on every system. Absorbs the former `/overages-upsell` skill (customer spreadsheet is step 6).

## Rules (non-negotiable)

- **Usage source of truth:** trust Salesforce only for **bandwidth** and **storage**. Streams,
  transcoding, plays, seats, AI interactions, captioning credits etc. → ask the user for the number, or list under
  Manual check. Never use SF's streams/transcoding figures in a verdict.
- **Commits come from the contract, never SF allowance fields.** Allowances on the account-usage object (`sf_fields.account_usage`) and
  the account usage-status field (`sf_fields.usage_status`) are stale (often years out of date vs. the signed order form). Show the usage-status field only as "SF says:" and note disagreement.
- **Unit price** = annual line total ÷ quantity (`annual_unit_price` in the CSV). CPQ net prices are
  for the whole term — a 3-year line's `term_line_total` is 3× the annual cost — so always use the
  `annual_*` columns. Several priced lines for one
  metric → **quantity-weighted blend** of the paid lines (exclude $0 "Included" lines). No line price
  → **overage rate × 0.75**. If the overage rate is *below* the committed unit price, say so — the customer is cheaper on overage than on commit.
- **Target utilization: 80%** of committed volume.

## 1. Inputs

Below, `{x}` means the value of `sf_fields.x` in `config.local.json`, and `{x}__r` means that field's
relationship name (swap its `__c` suffix for `__r`).

1. Account: `sf data query -o {sf_username} -q "SELECT Id, Name, {closest_renewal_date}, {usage_status} FROM Account WHERE Name LIKE '%<customer>%'" --json`
2. Folder: `{paths.accounts_root}/<folder>/Contracts/` (folder name rules: `scripts/pull_contracts.py` `folder_for`).
   If `_active_contract_lines.csv` is missing or older than the latest won opp, run
   `python3 scripts/pull_contracts.py --account "<customer>"` first.
3. Commits: `_active_contract_lines.csv` for quantities/prices. If `source` says
   `quote ... (not contracted)`, the renewal was won but never contracted in CPQ — the lines come from
   the primary quote, so confirm them against the signed order form and note "SF needs realignment"
   in the output. Then read the active order form PDF
   (top level of `Contracts/`, not `Expired/`) with `pdftotext -layout` → the **TOTAL USAGE RIGHTS**
   table gives the authoritative pools, cycles and overage fees. Pools stack (included + every
   add-on line). "Bandwidth + Storage" is a separate combined pool that absorbs overflow from either.
4. Usage (SF, monthly):
   ```
   SELECT {account_usage}__r.{month}, {partner_id}__r.Name, {bandwidth_combined_gb}, {average_storage_gb}
   FROM {pid_monthly_usage} WHERE {account_usage}__r.{account} = '<AccountId>'
   ```
   Sum across all PIDs per month and list the PIDs (a missing/mis-mapped PID shows up here).
   The month field (`{month}`) is text (`MM/1/YYYY`) — parse it, don't sort on it. **Drop the current month (partial).**

## 2. Compute (per measurable pool, current contract year)

- Contract year = the 12-month cycle from the contract Start Date containing today.
- Need ≥3 complete months in the contract year; otherwise "insufficient data" for that pool.
- **Bandwidth usage** = sum of monthly GB. **Storage usage** = sum of monthly *average* GB
  (contract definition: avg 10 GB × 12 months = 120 GB).
- Run rate = average of the last 3 complete months.
- **Projected year-end** = YTD + run rate × months remaining.
- **Projected utilization** = projected ÷ pool. Overflow beyond a single pool spills into the
  combined pool before it counts as overage.
- **Trend** = last 3 complete months vs the same 3 months a year earlier.

## 3. Verdicts (binary)

**Upsell — Yes** if any measurable pool has projected utilization > 90% or any overage. Size it:
new pool = projected annual usage ÷ 0.80, round up to the product's sell increment;
add-on = new pool − current pool; price = add-on × unit price (rules above). Show alongside: the
same volume at overage rates (that's the pitch). Timing: >180 days to the renewal date (`{closest_renewal_date}`) →
co-termed mid-term add-on; ≤180 days → fold into the renewal.

**Churn risk — Yes** if any of:
- projected utilization < 50% on any measurable pool
- trend down > 25% on bandwidth or storage
- a paid, measurable line shows zero usage

Name every trigger that fired, with the numbers. (Thresholds are tunable defaults.)

## 4. Manual check

Every contract line that isn't bandwidth/storage and has a price or an allowance: streams,
transcoding, seats/users, AI/conversational-agent interactions, captioning credits, live, PS hours. Rank by
annual line total, highest first, so the biggest blind spots lead. Ask the user for streams /
transcoding numbers if the contract has those pools.

## 4b. Strategic solutions fit (optional)

If you keep a strategic-solutions playbook (`paths.solutions_playbook`, e.g. agentic learning / revenue
solutions), every audit also scores each focus solution against its "Opportunity signals" section.
Evidence comes from the contract lines (which products they own:
video portal, LMS/LTI, events/webinars, AI content tools, AI avatar/agents), `Notes/` (incl. filed Granola notes) and
Gong. Give each a verdict of **Fit / No / Unknown**, name the signal that fired, the buyer to reach (by title,
plus a name if one is known), and the entry play from the playbook. Fit is pipeline, not a usage verdict:
keep it separate from Upsell. At ≤180 days to renewal, say whether to fold the play into the renewal
quote.

## 5. Output (chat, short)

```
<Account> — contract <#> (<start>–<end>), renewal <date>
Upsell: Yes/No — <one line>
Churn risk: Yes/No — <triggers>
<Solution>: Fit/No/Unknown — <signal> → <buyer> · <entry play>   (one line per solution)

Pool | Commit | YTD | Projected | Util | Trend YoY | Unit price | Overage fee
...
SF says: <usage-status field, stripped of HTML> (<agrees/disagrees>)
Manual check ($/yr): <line> $X · <line> $Y ...
PIDs: <list>
```

## 6. Customer spreadsheet (only if Upsell = Yes and the user asks)

Position overages as adoption to celebrate, not a compliance problem: rightsizing saves the customer
money vs. paying overage. Save to `{paths.accounts_root}/<folder>/Commercial/YYYY-MM-DD_internal_rightsizing.xlsx`
(confirm the file isn't open in Excel first).

- **Tab 1 "Our Contract":** title / AM / contract ref / term · one-sentence summary (adoption has
  exceeded contracted limits; rightsizing avoids overage exposure) · table: Metric, Unit, Allowance,
  YTD, Projected, Variance, Overage rate, Projected overage cost (total row `#FDE8E8`) · options:
  A Status quo (pay overage), B Growth pack to 80% (recommended), C Multi-year lock with buffer;
  savings row `#E9EFF5`.
- **Tab 2 "Usage":** monthly bandwidth + storage rows from SF, with `SUM` / `AVERAGE` and the
  trailing-12 total as native formulas that Tab 1 references.
- Format: Calibri 11 everywhere (bold headers/totals only), default row heights, no borders,
  headers `#334D6E` with white text, subtotals `#F2F4F7`.
