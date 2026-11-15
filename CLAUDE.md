# Account Command Center

AI-agent hub for an enterprise account manager. Open Claude Code here to research accounts, build forecasts, prepare business reviews, and update Salesforce, without switching between a dozen tabs.

## Portability

This file is the single source of truth for how this hub operates. It is checked into git. Machine-local values (identity, API tokens, paths, hostnames, Salesforce field names, account lists) go in `config.local.json` (gitignored), never here. `config.example.json` documents every key.

## Session Start

A SessionStart hook runs `scripts/bootstrap.sh`. **Read its output and act on every `MISSING` / `WARN` / `CONFIG_MISSING` line before proceeding.** Do not start work until all failures are resolved.

## Phase model

Three core workflows, each a slash command:

| Phase | Command | Output |
|---|---|---|
| 1 — Research | `/business-review` | QBR/EBR deck: SF account data + Gong call history + JIRA tickets → PowerPoint |
| 2 — Plan | `/account-forecast` | Strategic growth forecast: 3/6/9/12 month outlook with assumptions |
| 3 — Update | `/sf-forecast-update` | Salesforce opportunity updates: current stage, close date, forecast category |

Retrieval / prep skills: `/account-brief <customer>` (one consolidated view across SF + Gong + filed notes +
JIRA + Confluence + OneDrive; `--prep` for a call-prep cut) and `/morning-brief` (see Automations).

Audit skill: `/account-audit <customer>`: contracted commits vs. Salesforce bandwidth/storage usage →
binary Upsell / Churn-risk verdicts, plus a $-ranked manual-check list for components with no usage
feed; optionally builds the customer rightsizing spreadsheet. Its contract inputs come from
`scripts/pull_contracts.py`, which files every SF-attached contract/MSA/PO for the user's accounts
(account-manager field `sf_fields.account_manager`) into `<paths.accounts_root>/<account>/Contracts/`
(prior terms in `Contracts/Expired/`) and writes `_active_contract_lines.csv` from the quoting tool's
subscription lines (falls back to the legacy CPQ primary quote when the quoting tool has no lines).
Accounts wrongly tagged to the user go in `config.local.json` `exclude_accounts`. Rerun it after any
renewal or upsell closes.

Value skill: `/value-id <customer>`: realized ROI from measured usage × published benchmark rates →
customer-facing "Value Delivered" deck (no spend on slides) plus an internal companion with the ROI
multiple and a green/amber/red value-health signal.

## Automations

**Weekday morning brief:** each weekday morning a launchd job prepares the user for the day's
customer calls. Pieces (all read-only except the one authorized self-send):

| Piece | File | Role |
|---|---|---|
| Calendar reader | `scripts/todays_calendar.sh` | Dumps today's events from the work calendar via icalBuddy, meeting boilerplate stripped |
| Orchestration | `.claude/skills/morning-brief/SKILL.md` | Classify external calls, resolve to SF, Gong+SF prep with a >2-week recency gate, compose HTML |
| Self-send | `scripts/send_self_brief.sh` | Sends the one email, recipient **locked** to `user_email` in `config.local.json`; `--draft` opens a draft instead |
| Runner | `scripts/run_morning_brief.sh` | `claude -p` headless with a read-only tool allowlist + mutating-tool denylist; guards weekends; logs to `logs/morning-brief/` |
| Schedule | `scripts/launchd/com.commandcenter.morningbrief.plist` | Mon–Fri 08:30 trigger |

Preview any day with `MORNING_BRIEF_MODE=draft scripts/run_morning_brief.sh` (opens a mail
draft, sends nothing). Model is tunable via `MORNING_BRIEF_MODEL`.
Gong (via Salesforce Gong sync) supplies call notes and recordings; Granola notes are filed in each account's `Notes/` folder. Lookup order: `docs/call-notes.md`.

**Draft-only automations:** run through `scripts/run_draft_job.sh <job>` (`claude -p`,
read-only allowlist, SF writes and sends denied). Their only external effect is saving mail
drafts with `scripts/stage_draft.sh new`, which never sends. The user reviews and sends.

| Job | Skill | Schedule (plist in `scripts/launchd/`) | Output |
|---|---|---|---|
| `pulse-tip` | `.claude/skills/pulse-tip/SKILL.md` | `com.commandcenter.pulsetip` Mon 08:00 | One usage tip + KB link per pilot account (≤1 per 28 days) as drafts; churn signals listed for the user instead. Accounts: `config.local.json` `pulse_accounts` |
| `post-call` | `.claude/skills/post-call/SKILL.md` | `com.commandcenter.postcall` Mon–Fri 17:30 | Recap + next-steps follow-up drafts for today's external calls; Next Step proposals in `issues/_post-call/<date>.md`. `/post-call apply` writes them to SF after approval |
| `product-updates` | `.claude/skills/customer-product-updates/SKILL.md` | `com.commandcenter.productupdates` | Per-account product-update drafts. Accounts: `product_update_accounts` |
| `account-tracker` | `.claude/skills/account-tracker-update/SKILL.md` | `com.commandcenter.accounttracker` | Refreshes a shared account tracker before a recurring sync. Settings: `account_tracker` |

Run once by hand with `scripts/run_draft_job.sh pulse-tip` (or another job name). Model via
`DRAFT_JOB_MODEL`. Logs in `logs/<job>/`. Install schedules with the steps in `scripts/launchd/`.

## Tool routing

Use the `account-hub` MCP tools for all data access. Never compose raw API calls directly.

| Prefix | System | Used for |
|---|---|---|
| `sf_*` | Salesforce | Accounts, opportunities, contacts, activity history |
| `gong_*` | Gong | Call recordings, AI summaries, conversation themes, live via Salesforce Gong sync (see `docs/systems.md`) |
| `graph_*` | Microsoft Graph | Outlook email, **draft-only** |
| `onedrive_*` | OneDrive / SharePoint (local sync) | List/search/read-`.xlsx`. No tool uploads, reads non-`.xlsx` content, or renames/moves/deletes. |
| `jira_*`, `confluence_*` | Atlassian | Implementation tickets, project status, reference pages |
| `kb_*` | Vendor knowledge base | Product help articles (`kb_base_url`) |

**Default to the `onedrive_*` tools for OneDrive/SharePoint, not Read/Bash on the local sync
path.** Direct filesystem Read/Bash under `paths.accounts_root` is fine only when (a) the user has
asked in the current conversation for that specific file/folder, e.g. a PDF no `onedrive_*` tool
can read, or (b) a structural change (rename/move/delete) is needed that the tools can't do.
This is per-request, not standing permission.
**Standing exception:** `scripts/pull_contracts.py` may create account folders and write files
under `<accounts_root>/*/Contracts/`, and `/account-audit` may read them and write its spreadsheet
to `<accounts_root>/*/Commercial/`.

## Data access

- Default to read-only on all systems.
- **Never send an email or chat message** without the user's explicit approval. Produce a draft and wait.
- **Scoped self-send exception:** the weekday `morning-brief` automation may send **one** email
  per run **only** to the configured `user_email`, via `scripts/send_self_brief.sh`. This is the
  *only* sanctioned auto-send. Every other email/chat message stays draft-and-approve.
- **Salesforce writes are owned-only.** `sf_update_opportunity` and `sf_create_opportunity` refuse in code any opportunity not owned by the configured user (`sf_user_id`), and `sf_create_opportunity` forces `OwnerId` to that user.
- **All SF writes are approval-gated.** Both write tools default to `dry_run=True`, returning a before/after diff (or the record they'd create) without writing. Show that diff to the user and only call again with `dry_run=False` after explicit approval. Every committed write is appended to `issues/.sf-audit.log` (gitignored).
- For `/sf-forecast-update`: show a before/after table for every field being changed and wait for confirmation before writing.
- Customer data (account names, contacts, revenue figures) must never be committed to git. Use `issues/{account}/` for per-account scratch work (gitignored).

## Outputs

- **Primary output format: PowerPoint (.pptx)**, saved to `~/Downloads/` with the account name and date in the filename. Report the path when done.
- **Secondary:** Confluence page, only when building a new shared reference document.
- **Never send externally** without explicit approval. Always save locally first.
- Customer-facing decks use the logo, fonts and template in `paths.brand_dir` and the colors in `brand` (see `config.example.json`). No brand assets ship in this repo.

## Local artifacts

- `docs/`: system maps, reference docs, account templates
- `issues/`: per-account scratch (gitignored; `git add -f issues/{account}/` to share one account's work)
- `.claude/skills/`: repeatable workflows as slash commands

## Style

- Direct and data-driven. Back claims with numbers from Salesforce or Gong.
- No filler. Every slide and every sentence earns its place.
- When data is missing or ambiguous, say so explicitly. Never substitute assumptions or invented numbers.
- Professional tone in all external-facing drafts.

## Execution discipline

- **Verify before claiming done.** If the output is a deck, confirm the file exists at the stated path.
- **Re-plan on failure.** If an API call fails or data is missing, stop and report. Do not fill gaps with guesses.
- **Corrections live here.** When the user corrects a recurring mistake, capture the rule in this file.

## Guardrails: never do these without explicit approval

1. Send email or chat messages (sole exception: the `morning-brief` self-send to `user_email`)
2. Bulk-update Salesforce records not owned by the user
3. Share customer data outside this hub
4. Commit credentials, tokens, or customer-identifiable data to git
5. Push directly to the main branch; all changes go via pull request
