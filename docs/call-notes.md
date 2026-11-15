# Call notes: where to look

Gong is the meeting recorder; Granola is a fallback on its free plan. Every skill that needs
"what was said on a call" uses this order and never blocks on a missing source.

## 1. Gong (via Salesforce Gong sync)

- By account: `gong_search_calls(account_name="<account>", days_back=N)` → each result has
  `brief`, `url`, `date`, `parties`. Then `gong_get_call_highlights(call_id)` for key points and
  next steps (action items with owners).
- Today's calls: resolve today's external calls to accounts from the calendar
  (`scripts/todays_calendar.sh`), then `gong_search_calls(account, days_back=1)` per account.
  Don't find the user's calls by `parties`: the SF field holds only ~5 emails.
- Limits: the SF sync stores brief, key points, and next steps only, **no verbatim transcript**.
  For exact words, give the user the Gong `url`. Gong only records calls its bot joined (scheduled
  video calls), not in-person meetings or unrecorded internal calls.

## 2. Filed notes (OneDrive)

- `{paths.accounts_root}/<Account>/Notes/` — newest first. `*_granola_*.md` files are the full
  Granola export (notes, private notes, screenshot descriptions, full timestamped transcript)
  from the paid-plan period; screenshots in `Notes/screenshots/<file stem>/`.
- Non-account Granola meetings (internal, 1:1s, personal) and the full index:
  `{paths.accounts_root}/_Archive/Granola/` (`index.csv` maps every Granola meeting to its file).
- Search with `grep -ril "<term>"` on the local OneDrive sync folder.
- New Granola notes are filed automatically by `/granola-sync` (launchd, weekdays 18:00), same
  naming, with summary + screenshot descriptions but **no transcript** (free plan). Filed rows
  are appended to the same `index.csv`.

## 3. Granola (fallback only)

Only for a meeting the user recorded in Granola because Gong couldn't (in person, in-room meeting
systems, no bot). The free plan exposes the last 30 days at most and may stop answering; if it
errors, skip it and say so in Gaps. Granola lists only the user as participant, so match by
title/content.

Cite every insight to its source: Gong call (date + url), note filename, or Granola link.
