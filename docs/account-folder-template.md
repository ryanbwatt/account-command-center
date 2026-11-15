# Account Folder Template

Standard layout for every account, so notes and docs are consistent and fast to find — for the
user and for `/account-brief`. This is the persistent notes layer of the notes-hub project
(`docs/projects/notes-hub-design.md`).

## Location & naming

- Path: `{paths.accounts_root}/{account}/` (`paths.accounts_root` in `config.local.json`).
- **Folder name = the Salesforce account name** (e.g. `Acme Corp`, `Globex Inc`,
  `Northwind Traders, Inc.`) — not short forms.
- Exception: when one customer has several SF accounts (e.g. a corporate account plus a separate
  training account), they share one consolidated folder named for the parent.

## Subfolders (every account)

| Folder | Holds |
|---|---|
| `Notes` | Call & meeting notes. Granola export (with `screenshots/`) and Wispr history live here. |
| `Contracts` | Active-term order forms, MSAs, POs (`_salesforce_` files from `scripts/pull_contracts.py` + `_active_contract_lines.csv`). Prior terms in `Contracts/Expired/`, unsigned redlines in `Contracts/Drafts/`. |
| `Commercial` | Quotes, pricing, proposals, ROI / right-sizing, forecasts. |
| `Business Reviews` | QBR / EBR decks and prep. |
| `Usage & Reports` | Platform usage reports, CSVs. |
| `Technical` | Implementation, integrations, JIRA references, architecture. |
| `Archive` | One-time OneNote / Wispr dump and legacy docs. |

The account **MASTER tracker** xlsx stays at the account root (the index doc). Contacts, ARR, and
opps are **not** copied here — those come live from Salesforce via `/account-brief`.

## File naming

`YYYY-MM-DD_source_topic.ext` — e.g. `2026-09-09_granola_renewal-call.md`,
`2026-08-25_usage_rightsizing.xlsx`. Date-first sorts chronologically and greps by date; `source`
is one of `granola` / `gong` / `wispr` / `internal` / `email`.

## Operating notes

- The `onedrive_*` MCP tools can list, search and read `.xlsx` only — they cannot upload, rename, move, or
  delete. Structural changes (renames, moves, consolidation) are done on the local OneDrive sync
  folder directly — scoped to `paths.accounts_root`.
- Customer data lives here and in Salesforce; never commit it to git or share externally without
  the user's approval.
