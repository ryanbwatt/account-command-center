---
name: value-story
description: Quarterly customer value story. 3 core slides showing how the video platform helped the customer's business Stabilize, Compete and Grow, in money saved and money made. Adapts per account by industry, internal vs. external audience, live vs. VOD, and AI use. Blends what the customer says they value with what we want them to see. Not contract utilization. Use for "/value-story <customer>", "quarterly value story", "value slides for <customer>", "how are we helping <customer>'s business".
argument-hint: "<customer> [quarter, default = last complete quarter]"
---

# Value Story (`/value-story <customer> [quarter]`)

One question: **how did the video platform help this business stabilize, compete and grow this quarter?** Answered in the
customer's own priorities, with money saved and money made. Run once a quarter per account. Read-only on every system.

Not this skill: commit vs. use, overages, rightsizing → `/account-audit`. Trailing-12 usage ROI and untapped
entitlements → `/value-id`. Full QBR agenda → `/business-review`. Forward-looking deal case → `/vbf`.
**Never put contract utilization, commits, MRR, spend or ROI multiples on these slides.**

## Rules

- **Their priorities first.** Every outcome row starts from something the customer said matters (Gong, Granola notes,
  opp descriptions, the 10-K / Account IQ). A vendor-favored point (AI adoption, consolidation, new product) goes in
  only when it ties to one of their priorities. If it doesn't, it goes in the companion as a talking point.
- **Never estimate a metric.** Every `$` figure has a `basis`:
  `customer` (they told us) > `measured` (our data × a cited rate from `value_map.md` or value-id `RATES`) >
  `benchmark` (an industry average with no customer metric). Only `customer` and `measured` count toward the
  money-saved and money-made totals. `benchmark` rows show as "est." and fall back to qualitative when in doubt.
  A missing metric goes on the data-warehouse ask or the validate list. Never fill it in.
- **Conservative over impressive.** Use the low end of a benchmark range. Count each dollar once: one outcome, one lever.
- No usage tables. Usage is evidence for an outcome, never the outcome.
- Customer data goes in `issues/<account>/` (gitignored). Decks go to `<accounts_root>/<Account>/Value Reports/` (`paths.accounts_root` in `config.local.json`).

## 1. Profile the account

Use `value_map.md` to set the profile, which picks the levers and the language:
**industry** · **audience** (internal / external / both) · **modality** (live / VOD / both) · **AI** (on / off, and which:
captions, translation, dubbing, AI content tools, agents, avatars) · **buyer persona** (who reads this: CLO, CMO, CIO, comms, compliance).

Set it from the SF account (industry, products), contract lines (`<accounts_root>/<Account>/Contracts/_active_contract_lines.csv`),
and the last story file if one exists. **If a prior `issues/<account>/value-story_*.json` exists, load it.** The profile carries
forward, and this quarter's slide shows the change ("2nd quarter running", "up from X").

## 2. Gather (in parallel)

1. **What they value**: Gong calls via `gong_search_calls(account, days_back=120)` + `gong_get_call_highlights`, and
   Granola (`search_meetings` participant/keyword, then `get_meetings`). Also filed `<accounts_root>/<Account>/Notes/` and SF opp
   descriptions / Next Steps (`sf_get_opportunities`). Pull exact quotes on goals, pains, wins and exec priorities.
   For enterprise accounts, add the latest 10-K / Account IQ themes (via `/account-brief`).
2. **What happened**: usage for the quarter (`/account-report` method or `Usage & Reports/` workbooks). Count events run,
   live hours, views, caption minutes and languages, and AI features used. Add support cases or incidents (SF cases,
   `jira_search` text~"<account>"). Note any launch, migration or consolidation delivered in the quarter.
3. **What we want them to see**: agentic solutions you sell (agentic learning solutions for learning/enablement,
   agentic revenue solutions for marketing/pipeline). Add roadmap items that match their priorities (`/customer-product-updates` log) and
   the reference/case-study ask if health is good.
4. **Data-warehouse ask** (the data source of truth, if you have a data warehouse assistant). Write
   `issues/<account>/value-story_data-ask_<Q>.md` using the template below and ask the user to paste it into the assistant.
   When they paste the answer back, use its numbers over anything inferred.
   On a conflict, list both and ask.

   ```
   Account: <SF account name> (SF Id <id>), partner IDs <list>. Period: <quarter start>–<end>, plus the same quarter last year.
   For a customer value story (not contract utilization), give me, with SQL and citations:
   1. Quarterly trend: plays/views, unique viewers, live events + live viewing hours, entries created, caption/translation minutes by service and language.
   2. AI usage: which AI features were used (captions, translation, dubbing, AI content tools, agents/avatars), volume, first-use date.
   3. Gong/SF evidence of business outcomes this quarter: quotes on savings, revenue, pipeline, compliance, time saved, tools replaced.
   4. Support: cases opened/closed, P1 incidents, uptime of their largest live events.
   5. Anything you see as valuable for this customer that I didn't ask for, ranked, with evidence.
   ```

## 3. Compose the story

Pick **3–4 outcomes** (one table row each), at least one per pillar if the evidence exists, ranked by what *they* care
about most. Each row:

| field | rule |
|---|---|
| `priority` | their words, ≤6 words ("Hit compliance training for all staff") |
| `pillar` | Stabilize / Compete / Grow (definitions in `value_map.md`) |
| `did` | what we did, concrete, ≤110 chars |
| `impact` | the business result, ≤40 chars (the $ line is added above it); `value`/`kind`/`basis` when there's a $ |
| `evidence` | where it came from ("Gong 10/14, champion", "Q3 usage × ATD rate"), ≤50 chars |

Then write:
- `headline`: one sentence in their language that names the biggest outcome. Not "the vendor delivered value".
- `pillars`: one line each (≤90 chars) for Stabilize, Compete and Grow. `featured` is an optional 4th block, usually AI.
- `stat`: one non-$ proof point (e.g. "14 languages", "99.99% event uptime").
- `next`: ≤3 "Label: text" plays for next quarter, each tied to a stated priority. One can be agentic (learning or revenue agents).
- `audiences`: which cover chips apply (Customers / Employees / Learners / Audiences).
- `notes`: speaker notes per slide with sources and anything to validate before presenting.

Save to `issues/<account>/value-story_<YYYY-Qn>.json` (shape: docstring of `scripts/build_story_pptx.py`).

## 4. Build

```
uv run --with python-pptx python $CC_DIR/.claude/skills/value-story/scripts/build_story_pptx.py \
  $CC_DIR/issues/<account>/value-story_<YYYY-Qn>.json \
  "<accounts_root>/<Account>/Value Reports/YYYY-MM-DD_<Account> - Value Story <Qn>.pptx"
```
Slides: Cover · At a glance (Stabilize/Compete/Grow blocks + money saved / money made / proof stat) · Your priorities
(outcome table) · Next quarter (≤3 rows) · Thank you. Template, brand colors, fonts and logo come from the same
config as `/value-id` (`paths.brand_dir` with optional `template.pptx` / `logo.png` / `fonts/`, plus `brand` colors and
fonts in `config.local.json`; see value-id SKILL.md "Brand and template" for the template contract). With no template it
draws a plain deck on a blank `Presentation()` in neutral default colors, skipping the logo if there is none. Self-check: run the builder with no args.

Verify exactly as `/value-id` step 3 does (python-pptx bounds check, PowerPoint PDF render via the container
copy, read every PNG). Also check that no slide contains MRR, commit, spend, ROI multiple or "utilization".

## 5. Companion (internal)

`issues/<account>/YYYY-MM-DD_value-story_internal.md` covers:
- the profile;
- quarter-over-quarter change vs. the last story;
- every candidate outcome, kept or cut, with the reason;
- vendor talking points that didn't tie to a priority;
- the baseline (first run: record the pre-platform or first-quarter figures as `baseline` in the spec; later runs reuse the same formulas);
- one honest "where value lagged" item, plus how to raise it in the room;
- the validate list, with the champion check: who confirms the numbers before the meeting;
- data-warehouse ask status (sent / answered / conflicts);
- source status (used / skipped / failed, with the reason).

## Report

Deck path, companion path, the headline, the money saved / money made totals with their basis mix, the validate list,
the data-warehouse ask path (and whether it's still unanswered), and each source's status.
