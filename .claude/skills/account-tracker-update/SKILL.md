---
name: account-tracker-update
description: Update a customer's shared master tracker workbook before the recurring account sync. Synthesizes Jira, Salesforce, Gong, and filed/manual call notes, updates AI update, and clears Next Action for fresh meeting notes. Account, workbook, meeting, contacts, and Jira projects come from config key `account_tracker`.
---

# Account Tracker Update Skill

Automatically prepares and updates the account's **master tracker workbook**. Everything account-specific is read from `config.local.json` → `account_tracker`:

| Key | Meaning | Example (fictional) |
|---|---|---|
| `account_name` | SF account name, also used for Gong search | `Acme Corp` |
| `workbook_path` | Workbook path relative to `paths.accounts_root` | `Acme Corp/Acme Corp - MASTER Tracker.xlsx` |
| `sheet` | Sheet holding active issue rows | `Active Issues` |
| `meeting_title` | Calendar title of the recurring sync | `Acme Bi-weekly status meeting` |
| `contacts` | Names whose mail/notes feed the AI update | `["Jordan Lee", "Sam Rivera"]` |
| `jira_projects` | Jira project keys tracked in the workbook | `["ABC", "XYZ"]` |
| `lead_minutes` | How long before the meeting to run | `60` |

Below, `{workbook}` means `{paths.accounts_root}/{account_tracker.workbook_path}` and `{account}` means `account_tracker.account_name`.

Run this:
1. **On demand:** When prepping for the account sync or when ticket status changes need to be reflected in the tracker.
2. **Scheduled routine:** `lead_minutes` before the sync via launchd (`com.commandcenter.accounttracker` → `scripts/run_draft_job.sh account-tracker`). Logs: `logs/account-tracker/`. Install/remove steps are in `scripts/launchd/com.commandcenter.accounttracker.plist`.

---

## 1. Operating Rules & Safety Protocol

1. **Check Excel Application First:**
   - Verify that the `{workbook}` file is **not currently open** in Microsoft Excel before running any write operations (Excel silently overwrites on-disk changes).
   - Run:
     ```bash
     osascript -e 'tell application "Microsoft Excel" to return name of every workbook'
     ```
   - If open, prompt the user or close it to avoid silent file overwrite collisions.

2. **Pre-edit Backup:**
   - Always archive a copy of the workbook to `Archive/<workbook name>_backup_YYYYMMDD_HHMMSS.xlsx` (next to `{workbook}`) before modifying cells.

3. **Column Logic (Crucial Workflow):**
   - **Column 8 (`Next Action` / Next Steps):** READ any manual text the user entered during or after the last call. Then **CLEAR** Column 8 so the user has clean, blank cells to take fresh notes during the upcoming call.
   - **Column 9 (`AI update`):** Synthesize the latest data from:
     - The manual notes captured from Column 8 prior to clearing.
     - Live Jira issue statuses for every project key in `account_tracker.jira_projects` via `mcp__account-hub__jira_*`.
     - Salesforce Case & Opportunity context via `mcp__account-hub__sf_*`.
     - Recent Gong calls (`gong_search_calls("{account}")`), filed `Notes/` and Apple Mail communications from anyone in `account_tracker.contacts`.
     - Format: `MM/DD - [Headline status]: [Details and next step]`.

4. **Call Log Maintenance:**
   - Append a new summary row in the `Call Log` sheet whenever a recurring call or major customer interaction occurred since the last entry.

---

## 2. Trigger Syntax

```bash
/account-tracker-update
```

### Options:
- `--dry-run`: Inspect current manual notes and latest Jira/SF statuses without writing to Excel.
- `--preserve-next-steps`: Updates AI update without wiping the Next Action column.

---

## 3. Workflow Steps

1. **Calendar Verification:**
   - Verify the exact start time of the next sync from EventKit:
     ```bash
     swift -e '...check Calendar.app for "{account_tracker.meeting_title}"...'
     ```
2. **Ingest Active Tickets:**
   - Read all active issue rows from the `account_tracker.sheet` sheet in `{workbook}`.
   - Query Jira for each ticket key in columns C, D, E.
3. **Capture Manual Notes:**
   - Save any user-typed text from Column 8 (`Next Action`).
4. **Synthesize & Update:**
   - Update Column 7 (`Status / Notes`) with high-level phase.
   - Update Column 9 (`AI update`) with today's date prefix, integrating the user's manual notes and the latest technical reality.
   - Clear Column 8 (`Next Action`) to `None`/empty string.
5. **Save & Report:**
   - Save the workbook back to `{workbook}`.
   - Output a concise summary of changes in chat so the user can glance over the state in 60 seconds before the call.
