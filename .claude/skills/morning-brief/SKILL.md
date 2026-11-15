---
name: morning-brief
description: Build and send the user's weekday morning account brief. Reads today's work calendar, keeps only external customer-facing calls, and for each one produces prep from Gong call notes + Salesforce (MRR, next renewal, open opps) — a full prep block when it's been >2 weeks since the last call with that account, a one-liner when contact is recent. Composes one HTML email and sends it to the user's own address (config `user_email`) via the hard-locked self-send script. Runs unattended each weekday morning via launchd; also invokable as /morning-brief to preview. Use when the user says "morning brief", "run my morning brief", or "what do I have today".
argument-hint: "[--draft to preview without sending]"
disable-model-invocation: false
---

# /morning-brief

The weekday-morning automation: prep the user on the customer calls they have *today* before
they happen, pulling the latest from Gong calls, filed notes, and Salesforce. Built on the same
per-account prep surface as `/account-brief --prep` (see `.claude/skills/account-brief/`).

**Delivery is a scoped, pre-authorized exception** to the CLAUDE.md "never send email
without approval" rule: this skill may send **one** email, **only** to
the user's own address (`user_email` in `config.local.json`), via `scripts/send_self_brief.sh` (recipient hard-locked in code to that value).
It never emails anyone else and never sends anything but this brief.

Modes:
- **send** (default, used by the launchd job) — compose and send the email.
- **`--draft`** — compose, save the HTML locally, and open it as an Outlook draft without
  sending. Use this to preview. When invoked interactively without a clear send instruction,
  prefer `--draft` and show the user the result.

## 1. Read today's calendar

Run `scripts/todays_calendar.sh`. It emits `===EVENT===` records (time · title · attendees ·
location · trimmed note) from the user's Exchange work calendar, `NO_EVENTS`, or `CALENDAR_ERROR`.

- If `CALENDAR_ERROR` (or the script exits non-zero): the calendar is **unreadable**, not empty.
  Do not treat it as a clear day. Send a short alert as this run's one email — subject
  "Morning brief failed: calendar unreadable", body = the error line plus the fix it names —
  via `scripts/send_self_brief.sh` (honoring `--draft` mode), print the error, and stop.

- If `NO_EVENTS`, or no event survives classification in step 2 as external customer-facing:
  **do not send anything.** Print "No external calls today — no brief sent." and stop. (The
  launchd runner already guards weekends; this guards empty/internal-only days.)

## 2. Classify each event

Decide, per event, whether it is an **external customer-facing call** the user should be prepped for.

**Keep (external, customer-facing):**
- Title names a customer in the user's conventions: `{Vendor} x {C}`, `{Vendor} <> {C}`, `{C} and
  {Vendor}`, `{Vendor} | {C}`, `{Vendor} {C} | …` (where `{Vendor}` is your company name), or `{C} Support Call` / `{C} Cadence` /
  `{C} Touchpoint` / `{C} Bi-weekly status`, etc.
- …reinforced by at least one clearly **external** attendee (a name that isn't a known internal
  colleague). Exchange usually shows display names, not emails, so treat the title as the primary
  signal and attendees as confirmation.

**Skip (do not prep, do not count):**
- Title starts with `INTERNAL` or `[Internal]`.
- `Blocked`, `Blocked (…)`, OOO, focus time, personal holds.
- 1:1s and internal syncs: `{you}/{name}`, `{name}/{you}`, `{you}/… Weekly`, team meetings where
  every attendee is an internal colleague (e.g. "Team Bi-Weekly").
- Anything with no identifiable customer and only internal attendees (e.g. an internal
  "prep/strategy" sync about an account — note it under "Not prepped" in step 6, don't prep it).

When genuinely ambiguous, lean on the attendee list; if still unclear, include it with a short
"(couldn't confirm external — verify)" flag rather than dropping a real customer call.

**Group by account.** If two events map to the same customer (e.g. "Vendor x Acme Corp |
check in" and "Acme Support Call"), produce **one** prep block for that account covering both,
and list both meeting times.

## 3. Resolve each account to Salesforce

For each distinct customer, `sf_search_accounts(name=<customer>)`.
- One clear match → use it. Map common short forms (example: ACME → Acme Corp, GLX → Globex Inc,
  NWT → Northwind Traders) but confirm against the SF result.
- No match → keep the call in the brief as a **calendar-only** block (time + title + attendees),
  and note "no SF account matched" so the user can fix the name. Don't invent account data.

## 4. Recency gate → full prep vs one-liner

For each resolved account, find the **most recent call** per `docs/call-notes.md`:
`gong_search_calls(account_name=<account>, days_back=90)` (newest first), then
`gong_get_call_highlights` on the latest one or two. Also check the newest file in
`{paths.accounts_root}/<account>/Notes/` (it may be newer than Gong, e.g. an in-person meeting).

- **Last call > 2 weeks ago, or no call on record → FULL prep block:**
  1. **Since last time** — from the most recent call(s): what was discussed/decided and what's
     still open; lead with open action items. Link each call's Gong `url`. If there is
     genuinely no prior call on record, say so.
  2. **Account snapshot** — MRR (and ARR) · next renewal date · open opps (name · stage · amount).
     From `sf_get_account` + `sf_get_opportunities`. Numbers match SF exactly.
  3. **Live tickets** — open JIRA that could surface: `jira_search(jql='text ~ "<account>" AND
     statusCategory != Done ORDER BY updated DESC', limit=8)` — key · status · summary. If none, skip.
  4. **Talking points** — 3–5 crisp bullets: what to raise, risks to get ahead of, the next step
     to land.

- **Last call ≤ 2 weeks ago → one-liner:** `Last spoke {date} — {one-line state + open item /
  next step}.` Plus MRR + next renewal if quick. No full block — recent contact means the user has
  the context fresh.

Gong (via Salesforce Gong sync) is the call-notes source; Granola is fallback only (`docs/call-notes.md`).

## 5. Data-integrity rules

- Never fabricate. If a source returns nothing, say so in that block. No guessed MRR, dates, or amounts.
- All numbers trace to Salesforce and match it exactly.
- Attribute call insights to their call ("From {date} call: …") and link the Gong call.
- Read-only everywhere except (a) writing the local HTML file and (b) the one authorized self-send.

## 6. Compose the email

Build one mobile-readable HTML email. House style: headers in `#1F4E78`, plenty of whitespace,
no clever colors.

- **Subject:** `☕ Morning brief — {N} external call{s} today · {Weekday} {Mon D}`
- **Top line:** date, and a one-line agenda: the external calls in time order
  (example: `9:00 Acme Corp · 10:00 Globex Inc · 10:30 Initech …`).
- **Per call, in chronological order:** a section headed `{time} · {Customer} — {meeting title}`,
  then either the full prep block (step 4) or the one-liner. For a grouped account, list all its
  times in the heading.
- **Footer:**
  - **Not prepped today** — one line listing internal/blocked/1:1 items that were skipped (titles only).
  - **Gaps** — anything worth flagging: accounts with no SF match, calls with no Gong history.

Save the HTML to `issues/_morning-brief/brief-{YYYY-MM-DD}.html` (create the folder; it's
gitignored). This is the artifact and the email body.

## 7. Send (or draft)

- **send mode:** `scripts/send_self_brief.sh "<subject>" issues/_morning-brief/brief-{YYYY-MM-DD}.html`
- **--draft mode:** append `--draft` to that command (opens an Outlook draft, sends nothing).

The recipient is hard-locked to `user_email` (from `config.local.json`) inside the script — this skill passes only
a subject and the body file, never a recipient. Report what was sent/drafted and the saved path.
