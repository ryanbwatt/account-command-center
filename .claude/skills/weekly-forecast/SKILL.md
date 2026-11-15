---
name: weekly-forecast
description: Pull the user's open upsell/churn Salesforce opportunities for the current and next calendar quarter, ahead of their weekly 1:1 with their manager. Can update Amount, Stage, Close Date, Forecast Category, and Next Step on any of them, with the same before/after approval gate as /sf-forecast-update. Use when the user says "weekly forecast", "pull my forecast for my 1:1", or "what upsell/churn opps do I have this quarter".
argument-hint: ""
disable-model-invocation: false
---

# /weekly-forecast

Pulls the user's open upsell and churn Salesforce opportunities for the current calendar quarter plus the next one, for their weekly manager 1:1. **Nothing is written to Salesforce until the user explicitly approves each change.**

<turns>
<1>
## Pull upsell/churn pipeline

Call `sf_get_my_opportunities(type_filter=["Upsell", "Churn", "Renewal", "Downgrade", "Amendment"], quarters_ahead=2, limit=100)`. The type names here and below are generic examples; use your org's `Opportunity.Type` and stage values.

**Quoting tool (e.g. DealHub) model.** This mirrors the SF forecast tabs:
- **Renewal with a delta:** renewal + upsell/downgrade is ONE quote on the renewal opp. Show only the upsell/downgrade delta (`sf_fields.dh_upsell_downgrade_mrr` in `config.local.json`), never the full renewal Amount. Positive → upsell subtotal (Booking tab); negative → net-impact churn line (Churn tab).
- **Flat renewal** (delta 0, not at risk): drop it; it shows on neither tab.
- **At-risk renewal** (`StageName` = your org's at-risk stage, e.g. `At Risk`): this replaces a separate `Churn` opp. If closed-lost, the FULL renewal MRR (`sf_fields.dh_renewal_mrr`) counts as churn, so list it in the net-impact line at that value and label it "at risk".
- **Amendment:** an add-on or downgrade against the current contract; treat its delta like an upsell (positive) or churn (negative).
- **Legacy `Churn` / separate `Upsell` opps** created before the quoting tool went live still count until they close out; they are not converted.

**Quote status column.** Call `dealhub_get_quotes(opportunity_ids=[...])` once with every opp Id from the pull (before filtering) and add a `Quote` column: the syncing quote's `Status` and `GrandTotal` (e.g. "Draft · $12,000", example), or **"needs quote"** when it returns `quote: None`. Flag rows where the opp is at a late stage (e.g. `Negotiation/Review`) but the quote is still `Draft` or missing, since that will stall the close. The quote is read-only here; changing it happens in the quoting tool.

`quarters_ahead=2` always means the current calendar quarter through the end of next quarter, recomputed from today's date — do not hardcode quarter labels or dates.

**Exclude overage opportunities.** Drop any result whose `Name` contains "Overage" (case-insensitive) before doing anything else with the list. Overage right-sizing is handled by `/account-audit`, not this skill — in this org, overage line items are typed `Upsell` just like real upsell opps, so `Name` is the only reliable signal; there's no separate `Type` value to filter on.

Group the remaining results by calendar quarter, derived from each opportunity's `CloseDate` (e.g. a CloseDate in Jul–Sep 2026 is "Q3 2026"). For each quarter, render a table:

| Account | Opportunity | Type | Stage | Amount | Close Date | Forecast Category |
|---|---|---|---|---|---|---|

Below each quarter's table, show a subtotal. Call out any `Churn` rows separately from the subtotal math (they're negative and should read as "net impact," not folded silently into the upsell number) — same framing as: upsell subtotal, then "net of $X churn" underneath.

If a quarter has zero results, say so explicitly rather than omitting the section.

End the turn asking whether the user wants to update anything before their meeting.
**End your turn here. Wait for the user.**
</1>
<await_user_input></await_user_input>
<2>
## Collect the updates

For each opportunity the user wants to change, ask for the new values. Fields that can change:

| Field | Salesforce field name | Valid values / format |
|---|---|---|
| Amount | Amount | Number ≥ 0. If the opp has a quote ID (`sf_fields.dealhub_quote_id`), Amount syncs from the quoting tool's quote; tell the user to change the quote there instead of writing Amount |
| Stage | StageName | Must match a real stage value in this org (check via the opportunity's current StageName / ask the user rather than assuming standard SF defaults) |
| Close Date | CloseDate | YYYY-MM-DD, not in the past |
| Forecast Category | ForecastCategory | Omitted / Pipeline / BestCase / Forecast / MostLikely / Commit / Closed |
| Next Step | NextStep | Free text |

If the user gives informal values ("push it to next quarter", "moving to commit"), translate them to exact field values and confirm the translation before proceeding.

Only opportunities from the Turn 1 pull are in scope — if the user names something not in that list, re-pull or ask for the account/opp name to look it up before touching it.

Build a complete change list. **Do not write anything yet.**
**End your turn here. Wait for the user to review the translation.**
</2>
<await_user_input></await_user_input>
<3>
## Show before/after and get approval

Present a before/after diff table for every proposed change:

| Account | Opportunity | Field | Before | After |
|---|---|---|---|---|

Ask: "Does this look right? Type 'yes' to apply all, or tell me which ones to change."

**Do not call `sf_update_opportunity` until the user says yes.**
**End your turn here. Wait for the user.**
</3>
<await_user_input></await_user_input>
<4>
## Apply updates

For each approved change, call `sf_update_opportunity(opportunity_id, fields)`.

Report results as they complete:
- ✓ Account / Opportunity — updated
- ✗ Account / Opportunity — failed: [error message]

If any update fails, report the raw error and the opportunity ID so the user can investigate in Salesforce directly.

Summarize: N updated, N failed.
</4>
</turns>

## Rules
- Only pull opportunities via `sf_get_my_opportunities` — ownership is enforced there, not re-derived in this skill.
- Only show/update opportunities from the Turn 1 pull for this run — never expand scope mid-conversation without re-pulling.
- Never call `sf_update_opportunity` without explicit approval from the user in Turn 3.
- Never infer a stage or forecast category from a description and apply it without confirming the translation in Turn 2.
- If the user says "update everything," show the full before/after table for all affected records before writing — never batch-apply without showing the scope.
- If an update fails, do not retry silently. Surface the error.
