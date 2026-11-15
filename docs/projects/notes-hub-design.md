# Consolidated Notes Hub — Design

**Status:** Partly built (`/account-brief` aggregator + per-account folder layer)

## 1. The goal

Build one consolidated "bucket" that captures everything said and written about an
account, across every tool, so nothing important is lost and any of it is retrievable
in one place. Call notes move from Wispr Flow → Granola, keeping **Gong** for recordings
(Teams/Zoom). Salesforce stays the source of truth; the bucket is *working memory* on top of it.

## 2. Sources and their role

| Source | Role in the bucket | Tool status (account-hub MCP) |
|---|---|---|
| Salesforce | Source of truth — accounts, opps, contacts, activity | `sf_*` (read + guardrailed write) |
| Gong | Call **recordings** (Teams/Zoom), briefs, highlights | `gong_*`, via the Salesforce Gong sync when no direct API key is set (see `docs/systems.md`) |
| Granola | Call **notes** (replaces Wispr) | official Granola MCP — see §5 |
| Wispr Flow | Legacy note-taker | `wispr_*` exists; retire after Granola lands |
| JIRA | Implementation tickets | `jira_*` |
| Confluence | Shared reference docs | `confluence_*` |
| Vendor KB | Product knowledge | `kb_*` |
| OneDrive / SharePoint | Tracker + files (local sync) | `onedrive_*` |
| Outlook | Email | draft-only (local AppleScript) |

## 3. Starting state (before this project)

- All sources except Granola and Gong were reachable individually through the hub. Gong
  lacked an API key (a missing credential, not a design gap; later solved via the Salesforce
  Gong sync).
- There was **no consolidation layer** — nothing merged the sources into a per-account
  view. `/business-review` was the closest (fans out SF + Gong + JIRA into a deck) but is
  deck-shaped and one-shot, not a queryable notes store.
- No account-matching convention: Gong calls / Granola notes weren't mapped to SF accounts.

## 4. Gaps (priority order)

1. **Granola integration** — the one true source gap (§5).
2. **Consolidation layer** — the merge/retrieval surface (§6).
3. **Account-matching convention** — how a call/note resolves to an SF account.
4. **Retire Wispr** — cutover + remove `wispr_*`.
5. **Gong credentials** — no direct API key available to a non-admin user; the Salesforce Gong
   sync covers briefs, key points and next steps (no verbatim transcript).

## 5. Granola integration — findings

- The Granola desktop app keeps local data under `~/Library/Application Support/Granola/`.
- **Store is encrypted at rest.** `granola.db` → sqlite3 reports "file is not a database";
  the cache file is ciphertext. Auth/session is also encrypted (Supabase backend).
- ⇒ The easy "read local SQLite like OneDrive" path is **closed**. Do not build on
  scraping/decrypting the local store — fragile and gray-area.

**Options considered:**

- **A. Granola-native export → a folder the hub already reads.** Point Granola's export /
  integration at a OneDrive folder (or a dedicated mailbox). Hub reads it via `onedrive_*`
  (or Outlook). No reverse engineering, fits the local-first pattern.
- **B. Official Granola API / MCP**, if the plan includes it — cleanest if available.
- **C. Unofficial API via the app's Supabase token** — works but brittle and ToS-gray. Avoid.

**Chosen: Option B, via the official Granola MCP.** Granola is wired as a remote MCP server
(`https://mcp.granola.ai/mcp`, OAuth, in `~/.claude.json`), authed as the configured
`user_email`. Tools: `query_granola_meetings`, `search_meetings`, `list_meeting_folders`,
`get_meetings`, `get_meeting_transcript`, `get_account_info`. `/account-brief` reads it live and
the weekday `morning-brief` automation can use it. Constraints learned: the MCP exposes only
**past recorded notes/transcripts — no calendar / upcoming-events surface**, and it lists **only
the note owner as participant**, so notes are matched to accounts by **title/content**, not an
attendee list. Today's-calendar reading is handled separately by `scripts/todays_calendar.sh`
(icalBuddy over the macOS calendar) — the two are complementary. The local-store path stays
closed (encrypted at rest).

On the free plan the MCP shows only the last 30 days and no transcripts, so `/granola-sync`
files each note into the per-account folders before it ages out.

## 6. Consolidation layer — design

Two shapes:

- **Query-time aggregator** — a skill/tool (`/account-brief <name>`) that fans out across
  SF + Gong + Granola + JIRA + Confluence on demand and returns one merged view. No storage;
  always fresh; cheap to build; reuses existing tools.
- **Persistent store** — sync each source into a per-account record (markdown or SQLite under
  a notes store) on a schedule. Enables history/search offline, but adds sync + staleness +
  a customer-data-at-rest surface to govern.

**Chosen: hybrid.** The live systems (Salesforce, Gong, Granola, JIRA) stay the sources and
`/account-brief` aggregates them at query time — but there is also a **persistent, organized
per-account layer in OneDrive**: `{paths.accounts_root}/{SF account name}/` with a fixed
7-folder template. It holds the one-time historical dump (OneNote + Wispr exports) and, going
forward, filed notes (Granola exports → `Notes/`). Standard is documented in
`docs/account-folder-template.md`; `/account-brief` reads this layer alongside the live systems.

## 7. Profiles / tool access — findings

If you run two Claude Code launches (e.g. a work alias on a claude.ai subscription login and a
personal launch on a raw Anthropic API key), they are **auth identities**, not folders:

- **The account-hub MCP registered at global scope** in `~/.claude.json` is shared by every
  launch that shares `~/.claude` ⇒ **all hub tools (Gong, SF, JIRA, Confluence, KB, OneDrive)
  are available in both.**
- **claude.ai-hosted connectors** (Gmail, Google Cal/Drive, Atlassian Rovo, Microsoft 365) ride
  the **claude.ai login**, not the API key. Under a raw API-key launch they generally won't
  appear. There is no toggle that attaches hosted connectors to an API-key session — the only
  way to share them is to have both launches use a claude.ai login.

**The one real choice:** accept that hosted connectors live in the subscription launch only
(hub tools are already everywhere), OR make every launch use a claude.ai login.

## 8. Value

- **One retrieval surface per account** → faster QBR/EBR prep, forecasts, and manager 1:1s;
  feeds the skills already in the hub.
- **Capture assurance via redundancy** — recording (Gong) *plus* notes (Granola) means nothing
  is lost when a call isn't recorded or a bot doesn't join.
- **Cheaper SF hygiene** — notes → next steps → opp updates flow into the guardrailed writes.
- **Cross-tool agent context** — "latest on account X" answered across calls, notes, tickets,
  docs in one shot instead of tab-switching.

## 9. Next actions

- [x] Choose the Granola path (§5) → official Granola MCP.
- [x] Choose consolidation shape (§6) → hybrid, aggregator first.
- [x] Build `/account-brief` aggregator skill (SF + Gong + JIRA + Confluence + OneDrive + Granola).
- [x] Wire Granola (§5) into `/account-brief`; file notes with `/granola-sync`.
- [ ] Decide profiles (§7).
- [ ] Retire Wispr after Granola cutover.

---
*No customer data in this file. Lands on `main` via PR per CLAUDE.md.*
