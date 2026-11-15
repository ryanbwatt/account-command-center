---
name: account-forecast
description: Build a strategic growth forecast for a customer account with 3, 6, 9, and 12 month outlooks. Analyzes Salesforce opportunities, Gong conversation signals, and account history to surface expansion potential, renewal risk, and recommended plays. Use when the user says "forecast for [customer]", "growth strategy", "what's the outlook on [account]", or "where can we grow with [customer]".
argument-hint: "[customer name]"
disable-model-invocation: false
---

# /account-forecast

Builds a structured strategic forecast for a single account. Output is a written analysis saved to `issues/{account}/forecast-{date}.md` plus a summary deck section the user can paste into a PowerPoint or Salesforce.

<turns>
<1>
## Identify the account and scope

Ask the user: which account? Any specific horizon or concern driving this (renewal coming up, expansion push, at-risk signal)?

Resolve the account via `sf_search_accounts`. Confirm with the user if ambiguous.
**End your turn here. Wait for the user.**
</1>
<await_user_input></await_user_input>
<2>
## Gather signals

Pull in parallel:
1. `sf_get_account(account_id)` — baseline: ARR, contract dates, segment, region
2. `sf_get_opportunities(account_id, limit=30)` — full opp history: won, lost, open
3. `sf_get_contacts(account_id)` — champion map, economic buyer, detractors
4. `gong_search_calls(account_name, days_back=365)` — all calls in the last year

For every Gong call found (up to 6 most recent), call `gong_get_call_highlights(call_id)`.

Compile:
- **Current state:** ARR, product footprint, contract end date
- **Expansion signals:** mentions of new use cases, new teams, new regions, budget cycles, exec sponsorship
- **Risk signals:** complaints, competitor mentions, budget pressure, champion departure, low engagement
- **Relationship map:** who is the champion, economic buyer, blocker; last interaction with each
- **Open opps:** stage, amount, close date, probability

State gaps plainly.
**End your turn here. Wait for the user to add context or correct anything.**
</2>
<await_user_input></await_user_input>
<3>
## Build the forecast

Produce a structured forecast with four horizon blocks:

### 3-Month Outlook
- Immediate priority: renewal, active opp close, or relationship maintenance?
- Recommended next action and owner
- Probability assessment with reasoning

### 6-Month Outlook
- Expansion vector most likely to close (new team, new product, volume increase)
- Blocker to address and suggested play
- Target ARR delta with assumptions stated

### 9-Month Outlook
- Second expansion vector or land-and-expand milestone
- Key stakeholder to develop or risk to mitigate
- Dependencies (product GA, procurement cycle, exec sponsor)

### 12-Month Outlook
- Full ARR target and growth thesis
- Renewal risk assessment (Low / Medium / High) with rationale
- Strategic positioning: what do we need to be to this account in 12 months?

### Recommended plays
List 3–5 specific actions ranked by expected impact:
- What to do
- Who initiates
- Target date
- Success metric

### Quality gate
Before saving, ask yourself:
- Are all ARR numbers sourced from Salesforce data (not estimates)?
- Is every expansion claim grounded in a Gong signal or SF activity, not assumption?
- Are the 3/6/9/12 month outlooks internally consistent (12M builds on 9M, etc.)?
- Have risk signals been weighted as heavily as positive signals?

If any answer is no, flag it in the output rather than hiding it.

Save to: `issues/{account_name}/forecast-{date}.md`
Report the path and a 3-sentence summary for the user to copy into Salesforce notes.
</3>
</turns>

## Rules
- All ARR figures must come from Salesforce. Label any estimate clearly as "estimated."
- Ground every claim in a data source: "(SF opp #X)", "(Gong call, [date])", "(contact title, from SF)."
- If an account has no Gong calls in the past year, flag it as a relationship risk — don't omit it.
- Do not recommend plays that require budget the user doesn't control without noting that dependency.
