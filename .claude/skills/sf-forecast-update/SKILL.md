---
name: sf-forecast-update
description: Update Salesforce opportunity forecast fields (stage, close date, forecast category, probability, next step) for the user's open opportunities. Shows a before/after table for every change and requires explicit approval before writing anything. Use when the user says "update my forecast", "SF forecast update", "update the pipeline", or "update my opps for [time period]".
argument-hint: "[optional: account or stage filter]"
disable-model-invocation: false
---

# /sf-forecast-update

Updates open Salesforce opportunities owned by the user. **Nothing is written to Salesforce until the user explicitly approves each change.**

<turns>
<1>
## Pull current pipeline

Call `sf_get_my_opportunities()` to get all open opportunities the user owns.

Present a table:

| # | Account | Opportunity | Stage | Close Date | Forecast | Amount | Next Step |
|---|---|---|---|---|---|---|---|
| 1 | ... | ... | ... | ... | ... | ... | ... |

Ask the user: which opportunities need updating? They can say "all of them", name specific accounts, or describe a filter (e.g., "everything closing this quarter").

Also ask: do they want to go through them one at a time, or give all updates up front?
**End your turn here. Wait for the user.**
</1>
<await_user_input></await_user_input>
<2>
## Collect the updates

For each opportunity the user wants to update, ask for the new values. Fields that can change:

| Field | Salesforce field name | Valid values / format |
|---|---|---|
| Stage | StageName | Your org's stage picklist values (Setup → Object Manager → Opportunity → Stage). Salesforce defaults: Prospecting / Qualification / Needs Analysis / Value Proposition / Proposal/Price Quote / Negotiation/Review / Closed Won / Closed Lost. Orgs often use a separate stage set per opportunity type (new business, renewal, at-risk); read the current stage from the record and offer only values from the same set. Stages are only set in SF; quotes live in the quoting tool (e.g. DealHub) |
| Close Date | CloseDate | YYYY-MM-DD |
| Forecast Category | ForecastCategory | Pipeline / Best Case / Commit / Closed |
| Probability | Probability | 0–100 |
| Next Step | NextStep | Free text |

If the user gives informal values ("moving to commit", "push the close to September"), translate them to the correct SF field values and confirm the translation before proceeding.

Build a complete change list. **Do not write anything yet.**
**End your turn here. Wait for the user to review the translation.**
</2>
<await_user_input></await_user_input>
<3>
## Show before/after and get approval

Present a before/after table for every proposed change:

| Account | Opportunity | Field | Before | After |
|---|---|---|---|---|
| Acme Corp | Renewal FY27 | StageName | Qualification | Value Proposition |
| Acme Corp | Renewal FY27 | CloseDate | 2026-12-31 | 2026-09-30 |
| Widget Co | Expansion - Voice | ForecastCategory | Pipeline | Best Case |

Ask: "Does this look right? Type 'yes' to apply all, or tell me which ones to change."

**Do not call sf_update_opportunity until the user says yes.**
**End your turn here. Wait for the user.**
</3>
<await_user_input></await_user_input>
<4>
## Apply updates

For each approved change, call `sf_update_opportunity(opportunity_id, fields)`.

Report results as they complete:
- ✓ Acme Corp / Renewal FY27 — updated
- ✗ Widget Co / Expansion — failed: [error message]

If any update fails, report the raw error and the opportunity ID so the user can investigate in Salesforce directly.

Summarize: N updated, N failed.
</4>
</turns>

## Rules
- Never call `sf_update_opportunity` without explicit approval from the user in turn 3.
- Never update opportunities the user does not own (filter enforced by `sf_get_my_opportunities`).
- Never infer a stage from a description and apply it without confirming the translation in turn 2.
- If the user says "update everything to commit," show the full before/after table for all affected records before writing — never batch-apply without showing the scope.
- If an update fails, do not retry silently. Surface the error.
