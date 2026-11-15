---
name: account-brief
description: Pull one consolidated brief for a customer account across every source — Salesforce (account, opps, contacts), Gong call history, filed OneDrive notes, open JIRA tickets, and relevant Confluence docs — into a single markdown view. The quick "what's the latest on X" retrieval surface and the pre-call prep surface. Use when the user says "brief me on [customer]", "what's the latest on [customer]", "pull everything on [customer]", "account brief for [customer]", or "prep me for the [customer] call".
argument-hint: "[customer name]"
disable-model-invocation: false
---

# /account-brief

Assembles a single consolidated brief for one account by fanning out across every connected
source, so the user gets the full picture in one place instead of tab-switching. This is the
query-time consolidation layer described in `docs/projects/notes-hub-design.md` (§6).

Output is a markdown brief saved to `issues/{account}/brief-{YYYY-MM-DD}.md` (gitignored —
it contains customer data) and summarized in the terminal.

<turns>
<1>
## Resolve the account, then pull everything

Resolve the customer to a Salesforce Account ID with `sf_search_accounts(name=<customer>)`.
- If exactly one match, proceed immediately — do not pause.
- If multiple plausible matches, list them (name, type, owner, ARR) and ask the user which one.
  **Then end your turn and wait.**
- If zero matches, say so and ask for the exact SF account name. **Then end your turn.**

Once resolved, fan out in parallel:
1. `sf_get_account(account_id)` — ARR, tier, contract dates, owner
2. `sf_get_opportunities(account_id)` — open + recently closed opps (stage, close date, amount)
3. `sf_get_contacts(account_id)` — key contacts + titles
4. **Call notes** per `docs/call-notes.md`: `gong_search_calls(account_name, days_back=90)`, then
   `gong_get_call_highlights(call_id)` for the 2–3 most recent (briefs, key points, action items via
   Salesforce Gong sync). No verbatim transcript there; link the Gong `url` for exact wording.
5. **Filed notes** — `{paths.accounts_root}/{account}/Notes/` on the local OneDrive sync, newest first. May include
   a filed Granola export (summaries + timestamped transcripts, `*_granola_*.md`);
   grep it when the user needs exact quotes from that period. Granola MCP is fallback only.
6. `jira_search(jql='text ~ "<account>" ORDER BY updated DESC', limit=15)` — related tickets
7. `confluence_search(query='<account>')` — related reference docs
8. `onedrive_list` / `onedrive_read_excel` under `{paths.accounts_root}/{account}/` — the persistent notes
   layer (`Notes/`, `Commercial/`, `Contracts/`, `Business Reviews/`, `Usage & Reports/`,
   `Technical/`). The folder name is the SF account name; see `docs/account-folder-template.md`.

**Filed notes** (Granola export, other note-taker exports, OneNote dumps) live in `{paths.accounts_root}/{account}/Notes/`.
</1>
<2>
## Assemble and save the brief

Write the brief with exactly these sections. Every claim traces to a source; if a source
returned nothing, say so in that section — never pad.

1. **Snapshot** — ARR, tier, contract start/end, account owner (from SF)
2. **Open opportunities** — one line each: name · stage · close date · amount (from SF)
3. **Key contacts** — name · title (from SF)
4. **Recent calls & notes** — per call: date · title · 1–2 line highlight + any open action items.
   Sources: **Gong** (summaries and action items via Salesforce Gong sync) and filed `Notes/`
   (incl. the Granola export). Keep Gong recording links and note filenames.
   If neither has anything in the window, state it.
5. **Open JIRA** — key · status · summary (from JIRA). If none, state it.
6. **Reference docs** — title · link (from Confluence). If none, state it.
7. **Filed notes & docs** — from `{paths.accounts_root}/{account}/`: recent `Notes/` entries and any relevant
   `Commercial/` / `Contracts/` / `Business Reviews/` files (name · date). If the folder is empty, state it.
8. **Strategic solutions fit (optional)** — if you keep a strategic-solutions playbook
   (`paths.solutions_playbook`), each focus solution Fit/No/Unknown with the signal, the buyer to
   reach, and one discovery question for this meeting, scored against its "Opportunity signals".
   Skip this section if no playbook is configured.
9. **Gaps** — list any source that returned nothing or isn't wired. Gong (via SF sync) is the live
   call source. Note any missing coverage if an expected source had no data.

Save to `issues/{account}/brief-{YYYY-MM-DD}.md` (create the folder if needed — it's gitignored).
Print a 5–8 line summary to the terminal and report the saved path.
</2>
</turns>

## Modes

**Full brief (default)** — everything above: all eight sections, saved as
`brief-{YYYY-MM-DD}.md`. Use for "brief me on X" / "what's the latest on X".

**Call-prep (`/account-brief --prep <customer>`, or "prep me for the <customer> call")** — a
tighter, forward-looking cut for walking into a call. Same fan-out, but the output is:
1. **Since last time** — from the most recent call(s) (Gong, or a newer filed note): what was discussed, decided, and
   what's still open. Lead with open action items owned by either side. Keep citation links.
2. **Account snapshot** — MRR/ARR · next renewal date · open opps (name · stage · amount) — from SF.
3. **Live tickets** — open JIRA that could come up (key · status · summary).
4. **Talking points** — 3–5 bullets: what to raise, risks to get ahead of, the next step to land.

Save call-prep to `issues/{account}/prep-{YYYY-MM-DD}.md` (gitignored). This is the same surface
the weekday morning brief uses per external call — see `.claude/skills/morning-brief/`.

## Rules
- Never fabricate. Missing data is stated as missing, per source — no guessed ARR, dates, or amounts.
- Numbers (ARR, amounts, close dates) match Salesforce exactly; note any rounding.
- Attribute call insights to their call ("From {date} call: …").
- **Resolving a calendar event to an account:** the user's meeting titles follow "{Vendor} x {C}",
  "{C} and {Vendor}", or "{Vendor} <> {C}" (`{Vendor}` = your company name) — extract {C} as the customer and confirm against SF with
  `sf_search_accounts`. Use the external attendee's email domain as reinforcement when it's exposed
  (Exchange often shows display names, not emails, so title is the primary signal). Skip events
  marked INTERNAL, "Blocked", focus time, or with no external customer.
- Customer data stays in `issues/{account}/` (gitignored). Never commit it; never send externally.
- Read-only across all systems — this skill never writes to Salesforce or anywhere else.
