---
name: business-review
description: Prepare a QBR or EBR deck for a customer account. Pulls Salesforce account data, recent Gong call history, and open JIRA tickets, then builds a PowerPoint deck following your company's brand guidelines. Use when the user says "prep the business review", "build the QBR deck", "EBR prep", or "get ready for the [customer] review".
argument-hint: "[customer name] [optional: quarter or date]"
disable-model-invocation: false
---

# /business-review

Prepares a quarterly or executive business review deck for a customer. Produces a `.pptx` file saved to `~/Downloads/`.

Follow the turn structure below exactly. Do not skip turns or combine them.

<turns>
<1>
## Identify the account

Ask the user: which customer, and is this a QBR or EBR? What date or quarter does it cover?

Resolve the account to a Salesforce Account ID:
- Call `sf_search_accounts(name=<customer_name>)`
- If multiple results, list them and ask the user to confirm

State what you found and what you'll pull next.
**End your turn here. Wait for the user to reply.**
</1>
<await_user_input></await_user_input>
<2>
## Pull account data

Run in parallel:
1. `sf_get_account(account_id)` — full account details
2. `sf_get_opportunities(account_id)` — open and recent opps
3. `sf_get_contacts(account_id)` — key contacts
4. `gong_search_calls(account_name, days_back=180)` — recent calls

For the top 2–3 most recent Gong calls, call `gong_get_call_highlights(call_id)` to get AI summaries and action items.

Summarize what you found:
- Current ARR / contract tier (from SF account)
- Open opportunities and their stages
- Key contacts and their titles
- Themes from recent calls (wins, concerns, open items)
- Any outstanding action items from calls

State gaps plainly if data is missing from any system.
**End your turn here. Wait for the user to confirm or add context.**
</2>
<await_user_input></await_user_input>
<3>
## Build the deck

Construct a PowerPoint deck with these slides:

1. **Cover** — Customer name, "Business Review", quarter/date, company logo placeholder (from `paths.brand_dir`, if set)
2. **Agenda** — What this review covers
3. **Account Summary** — ARR, tier, contract dates, primary contacts
4. **Value Delivered** — Key outcomes and milestones from the period (from Gong summaries + SF activity)
5. **Platform Usage** — Usage highlights and engagement (note if data requires customer portal access)
6. **Open Items & Next Steps** — Outstanding action items, open opportunities, agreed next steps
7. **Roadmap Alignment** — Our platform capabilities relevant to the customer's stated priorities (from call highlights)
8. **12-Month Outlook** — Renewal or expansion trajectory

Use python-pptx to generate the file. Follow guidelines in `docs/brand.md` if it exists; otherwise use a clean professional template (dark blue header, white body, placeholder branding).

Save to: `~/Downloads/business-review-{account_name}-{date}.pptx`

### Quality gate
Before saving, verify:
- Every slide has a title and at least one substantive content item
- No placeholder text like "[INSERT]" remains
- Numbers (ARR, dates) match SF data exactly — no rounding without noting it
- Action items are attributed ("From [date] call with [contact]")

Report the file path when done. Flag any slide where data was missing or estimated.
</3>
</turns>

## Rules
- Never fabricate numbers. If ARR is unknown, write "ARR: not available in Salesforce — verify with the user."
- Never send the deck externally. Save locally and report the path.
- If Gong has no calls for this account in the lookback window, note it on slide 4 rather than omitting the slide.
- If the user provides context mid-turn (e.g., specific talking points, a known deal), incorporate it.
