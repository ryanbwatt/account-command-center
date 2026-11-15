---
name: customer-product-updates
description: Weekly (Fri 08:00) scan of product newsletters, release notes, and product-lead emails; match each new feature to a customer's contracts, notes, and open asks; stage one targeted Outlook draft per account with knowledge base links. Draft-only, never sends.
---

# Customer Product Updates

Keeps each account current on features that matter to *them*. One draft per account per run,
only when something new fits. No generic "what's new" blasts.

## Trigger

```
/customer-product-updates [account] [--dry-run]
```
- No account: run every entry in `config.local.json` → `product_update_accounts`, **plus** discovery (Step 3).
- `--dry-run`: print the drafts, don't stage them.
- Scheduled: `scripts/run_draft_job.sh product-updates` runs it via launchd `com.commandcenter.productupdates`, **Fridays 08:00**.

## Step 0: Learn from last week's edits (always first)

For each `(draft staged)` ledger entry from the previous run, pull the sent version (`search_emails`
mailbox `Sent Items`, same subject) and diff it against `issues/_product-updates/<date>_<slug>_update.html`.
Record new, generalizable edits (wording the user changed, bullets they cut, accounts they deleted) in
`issues/_product-updates/_learnings.md` and apply them in this run. If a pattern repeats twice, promote it
into this SKILL.md's writing rules.

## Step 1: Collect product updates (last 14 days, plus anything unshared from the last 45)

Use the apple-mail MCP `search_emails` / `get_email`. The sources (senders listed in `config.local.json` → `product_update_sources`):
- **Product newsletters:** the internal product newsletter sender(s) in `product_update_sources.newsletter_senders`, subject matching `product_update_sources.newsletter_subject`. These cover all product lines.
- **Product leads:** the per-product-line leads in `product_update_sources.product_leads` (name → product line).
- **Release-note and product-doc mail:** queries like `release notes`, `now available`, `GA`, `What's New`.
- **Internal wiki newsletter drafts** (wiki notification mail matching "product newsletter"). These are context only; never quote unreleased copy.

For each feature, record: name, product line, one-line value, status (Released / Upcoming + date), and source email id.

## Step 2: Find knowledge base URLs

Every bullet needs a working `{kb_base_url}/help/<slug>` link (`kb_base_url` in `config.local.json`).
- Find slugs with `kb_search` (it matches slugs in the sitemap, so try synonyms), or run `curl -sL {kb_base_url}/sitemap.xml | grep -i <word>`.
- Prefer the dated release-notes page (e.g. `<product>-release-notes-<month>-<day>-<year>`) or the feature how-to page. Fall back to the product's release-notes hub.
- Verify the slug exists in the sitemap before using it. Never invent a URL.
- Keep a feature-to-slug map of lookups that worked in `issues/_product-updates/_learnings.md` and reuse it. Features with no dedicated page link the product's release-notes hub.
- `get_emails_batch` on long threads overflows the tool limit; fetch 3–5 ids at a time and read the top
  message only (split on the first `From:` line). Gong lookups are per account (`gong_search_calls`); if one fails, fall back to mail + Notes and say so.

## Step 3: Discover accounts (not just the config list)

The config list is a floor, not a ceiling. Also scan Sent Items for the last 30 days for every external
domain the user emailed (`<Vendor> x <Account>` subjects are the strong signal) and treat each one with a
`{paths.accounts_root}/<Account>/` folder as a candidate. Candidates follow the same relevance filter. Skip accounts
with an **active escalation, renewal negotiation, or outage thread** this week; a product note there reads as noise.

## Step 4: Build each account's context

For each account (`{paths.accounts_root}/<folder>/`, with the folder name from config):
1. `Contracts/_active_contract_lines.csv`: what they own (events platform, video portal, captioning credits, player, AI avatar, …).
2. `Notes/` (newest first) plus Gong (`gong_search_calls` + `gong_get_call_highlights`, see `docs/call-notes.md`): pain points, open asks, pilots, and who is engaged.
3. Recent mail threads with the account's domain (`search_emails` with `from_addr`/`to_addr`): current issues and active people.
4. `issues/_product-updates/<account-slug>.md`: the ledger of features already sent. **Skip anything in it.**
5. The user's **Sent Items** to the account domain (last 45 days): skip any feature already named there, even
   in a non-product email (e.g. a mobile-app thread that already covered the web app).
   A product email found only in **Deleted Items** was a discarded draft; treat it as unsent.
6. **Reconcile the ledger first.** Entries marked `(draft staged)` from the previous run: if the subject is
   in Sent Items, mark it `sent`; if it is only in Deleted Items, mark it `discarded`. Discarded features
   become eligible again, but don't re-pitch the same angle to that account (see Step 0 learnings).

**Recipients:** people at the account who emailed with the user, or appeared in a call with them, in the last 90 days (from mail threads and Gong call parties), plus the config `to` list. Internal teammates on those threads (CSM/SE) go in Cc. Do not add SF contacts who show no recent activity.

## Step 5: Match (relevance filter)

Include a feature only if it has:
- **Operational fit:** it resolves or eases a documented pain point, open ask, or support thread. Name it in one clause ("this should cut down the login questions your team fields"), **or**
- **Owned-product fit:** they actively use the product line and the change is visible to them (UI rebrand, login change), **or**
- **Expansion fit:** it moves forward a pilot/POC or ties to an adjacent product we've discussed (e.g. conversational AI agents for an events customer). Use at most one expansion bullet, under "Worth a Look".

If nothing qualifies, skip the account and say why in the run summary.

**Strategic solutions check (every account, every run).** If you keep a strategic-solutions playbook
(path in `config.local.json` → `paths.solutions_playbook`, e.g. agentic learning / revenue solutions),
score the account against its "Opportunity signals" section using the Step 4 context.
- If a strong signal fires and a feature this week supports it (an AI avatar, conversational AI agents,
  AI content tools, or events release), use the "Worth a Look" slot for it. Frame it in the
  buyer's language from the playbook, not the solution name, and close with the playbook's entry offer (a short demo
  video or a working session). It still counts as the one expansion bullet.
- Never pitch two solutions in one email, and never pitch to an account that is skipped for an escalation or negotiation.
- Always record the verdict in the run summary, even when nothing is drafted: `<solution>: fit/no/unknown — <signal>`
  per solution, and the buyer to reach (who isn't on the thread yet).

**Bar is higher for prospects/negotiations.** An account mid-evaluation of a paid service (e.g. a customer
weighing audio description vendors) needs a feature that changes *their* choice, not a general
accessibility note. A generic accessibility/player note to such an account is a weak fit and tends to be
deleted unsent. When in doubt, skip and list it under "Considered, not drafted" so the user can override.

## Step 6: Write and stage the draft

Body HTML only (the script adds the font wrapper and signature): one `<div>` per line, `<div><br></div>` for blank lines, and real `<ul>`. Links are styled `color: rgb(0, 88, 104);` with `<u>`.

```
Hi <First> and <First>,

<1–2 sentences tied to their recent thread or call>

Recently Released:
• <b>Feature:</b> what changed + why it matters to them (<a>guide</a>)
Upcoming (Releasing <date>):          ← only if any
Worth a Look:                          ← max one expansion bullet + demo offer

Thanks, and Happy Friday!
<your first name>
```
- **Closing:** don't add the generic "Let me know what you think of these or if you'd like to take a
  look together." line when the last bullet already has a specific offer (demo, set it up in QA, walk
  you through it). Use it only when no bullet ends in an offer.
- **No double offers:** one call to action per email.
- **Open items, the user's voice:** when a bullet touches something the user is chasing (legal review, work
  order, budget approval), state the status as the user's action, not their blocker. Example rewrite: "I understand
  the AI tools are still with your risk review" → "I'm still waiting to hear back on where our AI review got
  caught up between legal teams, and will follow up accordingly."
- **Cross-product reuse is fine** (the same player release can go to several accounts), but each bullet's
  "why it matters" clause must be account-specific.
- Voice: see memory `user-email-style` and `feedback-enterprise-customer-email-formality`. Use full sentences, no fragments, no $ figures, and no internal names such as product-lead names or the internal wiki.
- Subject: `<Vendor> x <Short Name> | <Product> Updates: <top 1–2 features>`.
- Recipients: To = the account's active contacts; internal teammates who own the topic (accessibility lead on an
  accessibility tracker, SE on a QA env) go in To as well.
- Stage: write to `$CLAUDE_JOB_DIR/tmp/<slug>_update.html` (or `issues/_product-updates/`), then run
  `scripts/stage_draft.sh new "<to,cc>" "<subject>" <file>`. It never sends. Call it **once per account**;
  Exchange sync can leave a second, single-recipient copy in Drafts. After staging, list the work
  Drafts folder and report any duplicate subject so the user deletes the partial one.
- Append the features you drafted to the ledger as `- <date> (draft staged): "<subject>": <features>`.

## Step 7: Run summary

Write `issues/_product-updates/<YYYY-MM-DD>.md`: drafted accounts (recipients and features), skipped
accounts (with the reason), "considered, not drafted", the **strategic-solutions fit table** (account, verdict, signal,
buyer to reach, next move), learnings applied from last week, duplicate drafts
to delete, and features with no KB link found. Save each draft body as
`issues/_product-updates/<YYYY-MM-DD>_<slug>_update.html` so next week's diff has a baseline.
