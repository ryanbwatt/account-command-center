---
name: closeout
description: End-of-day closure. Catches every to-do from today's calls and mail and does it now. Anything Claude can't do yet becomes a skill or memory so it can next time. Unfinished items roll into tomorrow's /kickoff, and anything others owe us goes on the follow-up list. Use for "/closeout", "close out the day", "end of day", "wrap up".
---

# /closeout

Pairs with `/kickoff`. To-dos aren't listed; they're **done now**. The only lists are the
follow-ups and carry-over in:

`{paths.accounts_root}/_Daily/Follow-ups.md` (`paths.accounts_root` in `config.local.json`)

## 1. Catch today's to-dos

- Calls: today's calendar (`scripts/todays_calendar.sh`) → `gong_search_calls(account, days_back=1)`
  → `gong_get_call_highlights` for next steps (see `docs/call-notes.md`; Granola only for calls
  Gong didn't record). Split them into **you own** (to-do) and **someone else owes** (follow-up).
- Mail: today's work inbox and sent mail. Asks of you are to-dos; asks you made with no
  answer yet are follow-ups.
- Anything the user lists in chat.

Show one numbered list (to-dos, then follow-ups to add) and get one go-ahead.

## 2. Do each to-do now

Use the existing skills and tools: emails via `$CC_DIR/scripts/stage_draft.sh` (after applying
your draft-vs-sent lessons memory if you keep one; stage only, never send), SF via the
`account-hub` MCP, `/account-audit`, `/value-id`, `/post-call`, `/sf-forecast-update`, etc.

**Can't do it?** Build the way to do it going forward:
- A repeatable workflow → a new skill in `$CC_DIR/.claude/skills/<name>/`, symlinked into
  `{paths.claude_config_dir}/skills/` (and any other Claude profile you use).
- A fact, rule or access gap → memory in every profile you use (universal memory):
  `{paths.claude_config_dir}/projects/<project>/memory/` (+ its MEMORY.md index).
- Needs the user (auth, a choice only they can make, their voice on a call) → say exactly what,
  in one line.

## 3. Roll forward

- Not finished today → **Carry-over to-dos** as `- [ ] <YYYY-MM-DD> <Account>: <to-do> (<blocker>)`.
  `/kickoff` does these first thing.
- Someone else owes us → new **Open** row, Next bump = +3 business days (external) or +2 (internal).

## 4. Report

Short: done (with draft subjects / links), skills or memories created, carried over, follow-ups added.
