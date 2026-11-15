# Systems Map

Reference for what each connected system holds and the exact `account-hub` MCP tools that
reach it. All data access goes through these tools — never compose raw API calls.

> Consolidation work (unifying these into one per-account view) is tracked in
> `docs/projects/notes-hub-design.md`.

## Salesforce — source of truth

**Holds:** Accounts, opportunities (stage, close date, forecast category, ARR), contacts,
activity history. System of record for all deal data.

**Tools:** `sf_search_accounts`, `sf_get_account`, `sf_get_opportunities`, `sf_get_contacts`,
`sf_get_my_opportunities`, `sf_update_opportunity`, `sf_create_opportunity`

**Auth:** CLI-based — the hub shells out to the Salesforce CLI (`sf`), which the SessionStart
bootstrap checks and re-auths. No SF token in `.env.mcp`. Identity in `config.local.json`
(`sf_instance`, `sf_username`, `sf_user_id`).

**Write rules:** owned-only (both write tools refuse any opp not owned by the configured user;
create forces `OwnerId` to that user) and approval-gated (`dry_run=True` by default returns a
before/after diff; only re-call with `dry_run=False` after the user approves). Committed writes
append to `issues/.sf-audit.log`. Known quirk: `sf_create_opportunity` `primary_contact_id`
fails on write — omit it and set the Contact Role manually.

## Gong — call recordings & AI summaries

**Status:** working via the Salesforce Gong sync. Gong call records (`sf_fields.gong_gong_call`)
sync in real time from Gong into Salesforce. When direct `GONG_ACCESS_KEY` /
`GONG_ACCESS_KEY_SECRET` are not set in `.env.mcp`, `gong_search_calls`,
`gong_get_call_highlights`, and `gong_get_call_transcript` automatically query the Salesforce
Gong sync records.

**Holds:** Synced AI call briefs (`sf_fields.gong_call_brief`), numbered key points
(`sf_fields.gong_call_key_points`), highlights & action items with assignees
(`sf_fields.gong_call_highlights_next_steps`), participant email lists, and direct links to the
full recording on Gong (`sf_fields.gong_view_call`). Field API names come from the `sf_fields`
map in `config.local.json`.

**Tools:** `gong_search_calls`, `gong_get_call_transcript`, `gong_get_call_highlights`

**Auth:** Automatically inherits Salesforce CLI authentication (the `user_email` /
`sf_username` identity in `config.local.json`). If direct Gong API credentials
(`GONG_ACCESS_KEY` + `GONG_ACCESS_KEY_SECRET`) are provided in `.env.mcp`, the tools prefer
direct Gong API access.

## JIRA — implementation tickets

**Holds:** Implementation/onboarding and technical project tickets.

**Tools:** `jira_search` (JQL), `jira_get_issue`

**Auth:** `ATLASSIAN_BASE_URL` (in `.env.mcp`) + `ATLASSIAN_EMAIL` +
`ATLASSIAN_API_TOKEN` in `.env.mcp`.

## Confluence — shared reference docs

**Holds:** Internal knowledge/reference pages. Also where new shared reference docs get
published (with approval).

**Tools:** `confluence_search`, `confluence_get_page`, `confluence_create_page`,
`confluence_update_page`

**Auth:** shares the Atlassian credentials above.

## Vendor knowledge base — product knowledge

**Holds:** The video platform vendor's public product docs, at the site in config key
`kb_base_url`.

**Tools:** `kb_search`, `kb_get_article`

**Note:** the site is a KnowledgeOwl SPA with no search API. `kb_search` matches query words
against article slugs from the sitemap (cached daily), so try synonyms if nothing hits. Read
with `kb_get_article(url, match="regex")` to get only the matching lines — far cheaper than a
browser or WebFetch.

## OneDrive / SharePoint — files & trackers (local sync)

**Holds:** OneDrive files synced locally via the desktop app: the master accounts tracker
workbook (`account_tracker.workbook_path` in `config.local.json`, relative to `paths.accounts_root`), Teams
chat files, account templates, historical docs.

**Local path:** the OneDrive sync folder; per-account folders live under `paths.accounts_root`
in `config.local.json`.

**Tools:** `onedrive_list`, `onedrive_read_excel`, `onedrive_search`, `onedrive_create_folder`,
`onedrive_upload_file`. Note the gap: no `onedrive_*` tool reads a PDF, Word doc, or other
non-`.xlsx` file — `onedrive_read_excel` is `.xlsx`-only, and there is no delete/rename/move
tool for any file type.

**Auth:** none — files are read directly from the local OneDrive sync. Default to the
`onedrive_*` tools so access resolves through the MCP layer. **Approved exception:** direct
filesystem Read/Bash on paths under the OneDrive sync folder is permitted when (a) the user has
explicitly asked for that specific file/folder to be read in the current conversation — e.g.
PDFs, screenshots, or other content no `onedrive_*` tool can read — or (b) a structural change
(rename/move/delete) is needed that the `onedrive_*` tools can't perform, scoped to
`paths.accounts_root`. This is a live, per-request exception, not a standing permission — don't
extend it to paths or actions the user hasn't actually asked for.

**Key files:** the master accounts tracker workbook (one sheet per segment plus goal/NRR
tracking sheets); `Microsoft Teams Chat Files/`.

## Outlook — email (draft only)

**Holds:** The user's Outlook mail.

**Tools:** `graph_create_draft_email` — creates a local Outlook draft via AppleScript.

**Auth:** none (local Outlook app). Never send without the user's explicit approval — draft and
wait.

## Granola — call notes (fallback only)

**Holds:** AI call notes + transcripts from the period a paid plan was active; Gong is the
recorder going forward. The full export (summaries, private notes, transcripts, screenshots) is
filed under `paths.accounts_root`: account meetings in `<Account>/Notes/*_granola_*.md`, the
rest plus `index.csv` in `_Archive/Granola/`. Granola MCP stays configured for the occasional
in-person meeting (free plan: last 30 days). Lookup order: `docs/call-notes.md`.

## Wispr Flow — legacy note-taker (retiring)

**Tools:** `wispr_list_meetings`, `wispr_get_transcript`. Keep until the Granola cutover, then remove.

## Credentials setup

`.env.mcp` (gitignored) provides:

```
SF_INSTANCE_URL=...
GONG_ACCESS_KEY=...          # optional — without it Gong reads go through the SF sync
GONG_ACCESS_KEY_SECRET=...   # optional
ATLASSIAN_BASE_URL=...
ATLASSIAN_EMAIL=...
ATLASSIAN_API_TOKEN=...
```

Salesforce auth is CLI-based (no token here). OneDrive and Outlook need no credentials.
Machine-local identity, paths, and hostnames live in `config.local.json` (also gitignored).
