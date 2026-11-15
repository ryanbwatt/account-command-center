# Account Command Center

A [Claude Code](https://claude.com/claude-code) workspace that acts as an AI assistant for an enterprise account manager. You open Claude Code in this folder and ask for things like "brief me on Acme Corp before my 2pm", "audit Globex's usage against their contract", or "update my forecast". Slash-command skills do the work by reading from your CRM, call recorder, notes and ticketing systems through one local MCP server.

It was built by an account manager at an enterprise video company and is published as a working example of an agentic sales-ops setup. Nothing in it is specific to that company: hostnames, Salesforce field names, account lists and branding all come from a local config file you create.

## What it connects to

| System | How | Used for |
|---|---|---|
| Salesforce | Salesforce CLI (`sf`) auth, called from the MCP server | Accounts, opportunities, contacts, quotes, usage objects; guarded opportunity writes |
| Gong | Gong REST API, or Gong's Salesforce sync objects as a fallback | Call search, transcripts, highlights |
| Granola | Granola's hosted MCP (added in Claude Code, not in `.mcp.json`) | Meeting notes |
| Jira / Confluence | Atlassian REST API (`.env.mcp`) | Tickets, reference pages |
| OneDrive / SharePoint | Local sync folder (`paths.onedrive_root`) | Per-account folders, trackers, `.xlsx` reads |
| Microsoft Graph / Apple Mail | Graph app credentials, or local AppleScript | Draft emails (never sends, with one opt-in exception below) |
| Calendar | `icalBuddy` on macOS | Today's meetings for the morning brief |
| Vendor knowledge base | `kb_base_url` | Linking help articles in customer drafts |
| Video platform API | `platform_api_base` | Usage reports by partner ID |

The MCP server is `mcp-server/server.py` (FastMCP, registered in `.mcp.json` as `account-hub`). Skills live in `.claude/skills/`.

## How writes are gated

The hub is read-only by default. The rules are in `CLAUDE.md` and most are enforced in code, not just in the prompt:

- **Salesforce writes are owned-only.** `sf_update_opportunity` and `sf_create_opportunity` refuse any record not owned by `sf_user_id`, and create forces `OwnerId` to you.
- **Every write is a dry run first.** Write tools default to `dry_run=True` and return a before/after diff. Claude shows you the diff and only writes after you approve. Only an allowlist of fields can be written. Committed writes are logged to `issues/.sf-audit.log`.
- **Email is draft-only.** Skills save drafts; you send. The only exception is the optional morning brief, which can email **you** (the address in `user_email`) once per weekday, and that script refuses any other recipient.
- **Scheduled jobs run headless with a tool allowlist**: read tools and draft creation allowed, Salesforce writes and sends denied (`scripts/run_draft_job.sh`, `scripts/run_morning_brief.sh`).
- **Customer data stays out of git.** Per-account scratch goes in `issues/`, which is gitignored.

## Skills

| Command | What it does |
|---|---|
| `/account-brief <account>` | One consolidated view across Salesforce, Gong, notes, Jira, Confluence and OneDrive; `--prep` for a call-prep cut |
| `/business-review` | QBR/EBR deck from Salesforce + Gong + Jira |
| `/account-forecast` | 3/6/9/12-month growth outlook with stated assumptions |
| `/sf-forecast-update`, `/weekly-forecast` | Propose and apply (after approval) stage / close date / forecast category changes |
| `/account-audit <account>` | Contracted commits vs. measured usage → upsell / churn-risk verdicts and a rightsizing workbook |
| `/value-id`, `/value-story` | Customer ROI decks built from usage × published public benchmarks |
| `/vbf` | Value-based framework deck (ships with a fictional worked example) |
| `/account-report` | Usage report across an account's platform partner IDs |
| `/morning-brief`, `/post-call`, `/pulse-tip`, `/customer-product-updates`, `/account-tracker-update` | Scheduled or on-demand prep and follow-up drafts |
| `/kickoff`, `/closeout`, `/granola-sync` | Start/end-of-day follow-up passes and note filing |

## Setup

Requires macOS (the scheduled jobs and mail/calendar helpers use launchd, AppleScript and icalBuddy), Python 3.11+, [uv](https://docs.astral.sh/uv/), the Salesforce CLI and Claude Code.

1. **Clone** to `~/account-command-center` (the launchd installer assumes this path; edit `scripts/launchd/install.sh` to change it).

2. **Config.** Copy `config.example.json` to `config.local.json` (gitignored) and fill it in. It holds:
   - your Salesforce identity (`sf_instance`, `sf_username`, `sf_user_id`) and `user_email`;
   - `sf_fields`: a map from the logical names the code uses (e.g. `closest_renewal_date`) to **your org's** custom field API names. Every custom field the hub touches goes through this map; a missing key fails with an error naming it. Gong and CPQ managed-package names are pre-filled with their standard values;
   - `sf_defaults`: org-specific picklist values used when creating placeholder opportunities;
   - `paths` (account folders root, OneDrive root, brand assets, Claude config dir), hostnames (`kb_base_url`, `platform_api_base`) and per-skill settings (`account_report`, `account_tracker`, `pulse_accounts`, `product_update_accounts`, `product_update_sources`).

3. **Secrets.** Create `.env.mcp` (gitignored):
   ```
   GONG_ACCESS_KEY=...
   GONG_ACCESS_KEY_SECRET=...
   ATLASSIAN_BASE_URL=https://your-site.atlassian.net
   ATLASSIAN_EMAIL=...
   ATLASSIAN_API_TOKEN=...
   MS_TENANT_ID=...
   MS_CLIENT_ID=...
   MS_CLIENT_SECRET=...
   ```

4. **Salesforce login:** `sf org login web --instance-url https://your-instance.my.salesforce.com`

5. **Install and run:** `cd mcp-server && uv sync`, then open Claude Code in the repo root. The SessionStart hook (`scripts/bootstrap.sh`) checks config, auth and the MCP server and prints `MISSING` / `WARN` lines for anything not set up.

6. **Branding (optional).** No logos, fonts or templates ship here. Put your own in the folder named by `paths.brand_dir`: `logo.png`, an optional `template.pptx` and an optional `fonts/`. Set colors and font names under `brand`. Without them, decks build on a blank template with a neutral palette.

7. **Schedules (optional).** `scripts/launchd/install.sh` fills the repo path into the plists and loads them into `~/Library/LaunchAgents`. Each job can also be run by hand, e.g. `scripts/run_draft_job.sh pulse-tip`.

## Layout

```
├── CLAUDE.md            operating rules, read by every session
├── config.example.json  every machine-local setting, with fake values
├── .mcp.json            MCP server registry
├── .claude/skills/      slash-command skills
├── mcp-server/          local MCP server (Salesforce, Gong, Atlassian, OneDrive, KB)
├── scripts/             bootstrap, hooks, report pullers, draft/brief runners, launchd plists
├── docs/                systems map, folder template, design notes
└── issues/              per-account scratch (gitignored)
```
