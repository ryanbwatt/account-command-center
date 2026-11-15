---
name: kickoff
description: Start-of-day follow-up pass. Reads the user's follow-up list (_Daily/Follow-ups.md under the accounts root), checks mail and Gong calls for replies, finds new things people owe us, and presents bumps to approve or skip, then stages the approved drafts. Also does yesterday's carry-over to-dos. Use for "/kickoff", "let's kick off the day", "kick off", "what follow-ups are due".
---

# /kickoff

The user's day: **kickoff** (follow-ups, this skill), then **closeout** (`/closeout`, to-dos).
Claude owns every follow-up: anything anyone, internal or external, owes us.
The list lives in one file:

`{paths.accounts_root}/_Daily/Follow-ups.md` (`paths.accounts_root` in `config.local.json`)

## 1. Refresh the list

For each row under **Open**:
- Check whether the other side replied since **Last touch**. Mail: apple-mail MCP `search_emails`
  (the work account) if loaded, else AppleScript on Mail.app. Calls: `gong_search_calls(account_name=<account>,
  days_back=<days since Last touch>)` (see `docs/call-notes.md`).
- Replied and resolved → propose **Close**. Replied with a new ask of the user → that's a to-do:
  do it in step 3. Replied but still owes something → update **Waiting on** / **Last touch**.
- Fill any `?` cells from what you find. Still unknown → leave `?`; don't guess.

Then look for **new** follow-ups: the user's work Sent Items from the last 3 business days where
they asked for something and got no reply, and action items owned by someone else in the last
business day's Gong call next steps (`gong_get_call_highlights`). Skip anything already on the list.

## 2. Present (one numbered list, short)

```
Kickoff — <Weekday Mon D>
Bump
 1. <Account> · <follow-up> · waiting <n>d on <who> — "<first line of proposed bump>"
New
 4. <Account> · <what they owe> (from <email/call, date>) — add, bump on <date>
Close
 6. <Account> · <follow-up> — <why resolved>
Carry-over to-dos: <n> (doing these now)
```

Only rows whose **Next bump** ≤ today, plus New and Close. The user answers per number with
approve or skip. **Skip means "excessive"**: don't argue, push that row's Next bump out 3
business days.

## 3. Act on approvals

- Before drafting, apply your draft-vs-sent lessons memory (`feedback-draft-vs-sent-lessons.md`)
  if you keep one.
- Bumps go in-thread: `$CC_DIR/scripts/stage_draft.sh reply <mail_id> body.html`. Use
  `new` only when no thread exists. **Stage only, never send.** Keep bumps to 1–3 sentences
  with one direct ask ("can you…") and a date.
- Do each **carry-over to-do** now (it's a to-do, not a follow-up). If you can't do it, say what
  blocks it and leave it in carry-over.

## 4. Write back

Update `Follow-ups.md`: Last touch = today on bumped rows; Next bump = +3 business days
(external) or +2 (internal); add New rows; move Close rows to **Closed** with date and outcome;
clear carry-over items you finished. Report: drafts staged (subjects), rows added/closed.
