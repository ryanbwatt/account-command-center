---
name: vbf
description: Build a Value Based Framework (VBF) PowerPoint slide for an account by synthesizing Gong (via Salesforce), Salesforce, and banked account notes/decks (incl. the Granola export). Use when the user says "VBF", "value based framework", "value framework for <account>", or asks for an as-is / to-be / business-impact slide for a customer.
---

# Value Based Framework (VBF) skill

Produces executive-ready PowerPoint decks for an account by synthesizing Gong (via Salesforce), Salesforce, and banked account notes/decks (incl. the Granola export). Supports two formats:
1. **Single-slide VBF (Core)**: 2x2 grid (Before / Negative Business Impact / After / Positive Business Outcome) plus Proof Points.
2. **Extended Solution Overview Deck (5 slides)**: Slide 1 (VBF 2x2), Slide 2 (Workflow & Solution Overview), Slide 3 (UI Mock-up), Slide 4 (Roadmap Options & Pilot Plan), Slide 5 (Commercial Upside & Monetization).

Saved to `<accounts_root>/<Account>/VBF/` (`paths.accounts_root` in `config.local.json`). The VBF establishes the business justification: connecting quantifiable negative business impact ($ cost of inaction, engineering drag, delay, support load) to positive business outcome ROI.

## Inputs
- Account name (required).
- Format: `single` (1-slide core VBF) or `deck` (multi-slide solution overview; flexible slide count and sections).
- Mode: `deal` (default; forward-looking hypotheses to validate with the customer) or `win-study` (retrospective, anonymized vendors and customer, e.g. "Customer A / Customer B").
- Optional use-case focus (e.g. "AI video answers inside the customer's own software product").

**Format selection**: If the user does not specify whether they want a single slide or multi-slide version up front, **always ask before building**:
- Ask whether they want:
  1. The **1-slide core VBF** (2x2 grid + Proof Points), or
  2. A **multi-slide solution deck** (modular: e.g. the 5-slide pack—VBF 2x2, Solution Workflow, UI Mock-up, Roadmap Options & Pilot, Commercial Upside—or a tailored subset/custom set of slides).

## Sources and fallback order
Synthesize inclusively across all of them. Order of trust when a fact is missing or low-confidence:
1. **Gong via Salesforce sync** - account-hub `gong_search_calls`, `gong_get_call_highlights`, `gong_get_call_transcript`.
2. **Salesforce** - `sf_search_accounts`, `sf_get_account`, `sf_get_opportunities`, `sf_get_contacts`.
3. **Granola export** - `<accounts_root>/<Account>/Notes/*_granola_*.md` (full transcripts). Granola MCP is fallback only (`docs/call-notes.md`).
4. **Banked account notes and decks** - `<accounts_root>/<Account>/` (Notes/, Business Reviews/, Commercial/, Technical/, plus any extra folders). Read every file in Notes/; also look at prior decks and any `VBF/` already present.
5. Supplementary: Apple Mail (envelope search only), Jira/Confluence for product-status facts behind a claim.

If Gong (or any source) is unreachable, do not stop. Elevate the account notes (incl. the Granola export) and say so.

account-hub access: the local MCP server in `$CC_DIR/mcp-server/`. Read note content from the local sync folder, not via the hub.

## Workflow
1. Resolve format up front: If not stated in the prompt, ask whether to build a **1-slide core VBF** (2x2 grid + Proof Points) or a **multi-slide solution deck** (modular: e.g. the standard 5-slide pack—VBF 2x2, Solution Workflow, UI Mock-up, Roadmap Options & Pilot, Commercial Upside—or a tailored subset/custom slide count).
2. Resolve the account in Salesforce (`sf_search_accounts`). Pull account, opportunities, contacts.
3. Locate the account folder under `paths.accounts_root` (confirm with the user before creating anything outside it).
4. Gather evidence in parallel: Gong (last ~90 days), account Notes (incl. the Granola export) and decks.
5. Draft the content per `template.md`. Every bullet carries a source tag in the companion evidence table (call/date, note filename, SF field).
6. Structure and quality rules:
   - **Enforce the Operations vs. End User Experience breakdown**: Every quadrant must clearly distinguish the operational/buyer/admin/engineering perspective from the frontline end-user/viewer/professional experience.
   - **Quantify Negative Business Impact in dollars and operational drag**: Never stop at passive qualitative descriptions (e.g. "the customer builds its own packaging and clip rendering"). Answer: *What does that cost them?* Translate to dollar figures, engineering headcount/timeline drag (e.g. N FTEs at a loaded cost per year; days/weeks to build a bespoke pipeline vs. minutes with API/MCP), support escalation overhead, or user abandonment. If exact customer figures are not yet confirmed in discovery, model the impact using industry benchmarks or reasonable operational hypotheses, clearly noted as modeled baselines in the companion notes. Negative impact and positive outcomes must form a cohesive ROI business justification.
   - **Strategic Reframing**: Reposition the video platform from merely a "video vendor" to the enterprise digital content repository and single source of truth for digital learning and verified video intelligence.
   - **Roadmap Options & Option 3 Business Case (Slide 4)**: Label roadmap options "Options" (lowest to biggest lift: Option 1 RAG-only, Option 2 Packaged clips via MCP, Option 3 Full AI video answers), never Phase 1/2/3. For Option 1, explicitly warn of the **cannibalization risk**: if the customer builds custom UI/packaging on raw RAG timestamps, they entrench custom code and resist adopting the higher-value MCP / AI answer solutions. For Option 3, explicitly make the **business case for cited video clips**: workflow real estate stickiness (keeping users in the host app instead of bouncing out to external portals), direct lift to host platform daily active usage and retention, and verification speed with exact timestamp proof.
   - **Tiered Monetization & AI Agent Strategy**: Where commercial upside is analyzed (e.g. Slide 5), model tiered packaging: Base Tier (text/document search), Video-Augmented Tier (cited clips, verified timestamps, in-video AI Q&A), and Premium Assistant Tier (conversational AI agent or AI avatar that remembers earlier questions, grounded in the customer's approved content). In regulated industries, emphasize human expert provenance and non-hallucinatory grounding.
   - **Internal presentation readiness**: No italics, no "(validate)" or hypothesis markers on the slide. Keep only clean claims on the slide; put unverified items in the speaker notes under "VALIDATE WITH CUSTOMER" and "GAPS". Quantify scale from sources (users, queries, API calls). Check customer-shared docs and the web; WebFetch specific pages if search fails.
7. Build the JSON spec and run the appropriate generator:
   - Single slide: `uv run --with python-pptx python $CC_DIR/.claude/skills/vbf/scripts/build_vbf_pptx.py spec.json "<account folder>/VBF/<Account> - VBF - YYYY-MM-DD.pptx"`
   - 5-slide deck: build the single slide first, then `uv run --with python-pptx python $CC_DIR/.claude/skills/vbf/scripts/build_overview_pptx.py <vbf slide>.pptx "<account folder>/VBF/<Account> - Solution overview (VBF) - YYYY-MM-DD.pptx"`.
     `build_overview_pptx.py` is an **illustrative worked example** (fictional "Acme Corp", a construction-software company, and its "Site Assist" product, invented round numbers). Copy it to the scratch dir and replace its strings with the account's sourced content; never ship the example text.
   Create `VBF/` in the account folder if missing. Keep scratch files in `$CLAUDE_JOB_DIR/tmp`, not /tmp.
8. Write a companion markdown next to the pptx: source map per cell, validation list by stakeholder, gaps as discovery questions, modeling assumptions, and the **source availability report**.
9. Verify by reopening the pptx with python-pptx: slide count, shape count, no text frame outside slide bounds, notes present. If no renderer (PowerPoint/LibreOffice) is available, say a visual render was not done.

## Rules
- **Translate impact to business metrics ($ / time / FTEs).** Do not leave negative business impact as purely qualitative pain. If exact customer figures are unconfirmed in discovery, formulate reasonable, model-grounded hypotheses or industry benchmarks (e.g., dev headcount drag, ticket escalation cost, search abandonment rate) rather than writing "unquantified". Detail the modeling assumptions in the companion file.
- **Maintain dual Operations vs. End User Experience lens** across all four quadrants.
- Keep bullets short (one line to two lines each); 3-4 bullets per Operations / End User group. The slide is a summary; detail goes in the companion file.
- Say "integration discussions", not "opportunity", in anything shared internally. Build the vision first; do not lead with MRR justification.
- No pricing, MRR, close dates or other internal commercial detail on the slide (except Slide 5 in an internal solution deck). Those belong in the companion file.
- In `win-study` mode anonymize competitors (Vendor X / Vendor Y) and the customer.
- Name stakeholders only in the validation list, by role or name as in the sources.
- Never send anything externally. Any email summary is a draft only.
- Write only inside the account's `VBF/` folder (and scratch dir).

## Required report at the end
- Path of the pptx and companion file.
- Source availability: for each source, reachable / skipped / failed and why (e.g. "Gong via SF: no calls returned").
- Top gaps, plus the web URL of the file if the accounts folder is synced (`sharepoint_base_url` in `config.local.json`), and `open` it.

## Branding
Nothing brand-specific ships with this skill. Both generators read `$CC_DIR/config.local.json` (or `$CC_DIR` from the environment; defaults to the repo root):

```json
{
  "paths": {"brand_dir": "$HOME/brand"},
  "brand": {
    "colors": {"primary": "1F5FAD", "light": "D6E4F5", "line": "BFBFBF",
               "dark": "2B2B2B", "muted": "595959", "background": "F5F6F8"},
    "title_font": "Calibri",
    "body_font": "Calibri"
  }
}
```

- `paths.brand_dir` holds `logo.png` (drawn on the primary-color title bar, so a light/white variant reads best), optional `fonts/` (install them on the viewing machine; the deck only names the fonts) and optional `template.pptx` (used by `/value-id` and `/value-story`).
- Every key is optional. Missing colors fall back to the neutral blue/charcoal defaults above, fonts fall back to Calibri, and a missing logo is simply skipped.
