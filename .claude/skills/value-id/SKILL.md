---
name: value-id
description: Show a customer the ROI they got from the video platform. Turns measured usage into dollar value with published benchmark rates, shows untapped entitlements, and points to the next value step. Outputs a customer-facing "Value Delivered" deck plus an internal companion with the ROI multiple and a green/amber/red value-health signal. Use for "/value-id <customer>", "what value has <customer> gotten", "ROI for <customer>", "value story before renewal".
---

# Value ID (`/value-id <customer>`)

Three answers for one account: **value delivered** (proven, in $), **untapped value** (paid but unused),
**what's next** (agentic / AI fit). Read-only on every system.

Not this skill: forward-looking deal ROI → `/vbf`. Commit math and upsell/churn verdicts → `/account-audit`
(this skill reuses its rules and data, it doesn't redo them).

## Rules

- **Never estimate a metric.** The calculator marks a lever "needs input" when its metric is missing and
  leaves it out of the total. Ask the user or list it in the companion; never fill it in.
- **Spend and the ROI multiple never go on the deck.** They go in the internal companion only (same rule as MRR).
- Rates are published list prices or benchmarks (`RATES` in `scripts/value_calc.py`), cited on the
  Assumptions slide. Override per run with `"rates"` in the inputs only when the user gives a customer figure.
- Use complete months only: drop the current or partial month. Default period = trailing 12 complete months.
- Use the Operations vs. End user lens on the value table (the builder sorts by it).
- Customer data goes in `issues/<account>/` (gitignored), never in the repo.

## 1. Gather (in parallel)

1. **Usage** (most trusted first):
   a. Usage workbooks in `<accounts_root>/<Account>/Usage & Reports/` (`paths.accounts_root` in `config.local.json`).
      Read them with `onedrive_read_excel`. Sum monthly views, live viewing hours, bandwidth GB and storage GB
      (storage = sum of monthly averages = GB-months).
   b. The SF per-partner monthly usage object (`sf_fields.pid_monthly_usage` in `config.local.json`) for bandwidth
      and storage (query in `/account-audit` step 1.4). This is the only SF usage to trust.
   c. Numbers the user supplies (avg minutes per on-demand view, caption minutes, captioning-credit burn).
   If the vendor's analytics API is not available for customer accounts, skip it and say so.
2. **Contract**: `<accounts_root>/<Account>/Contracts/_active_contract_lines.csv` (refresh with
   `scripts/pull_contracts.py` per `/account-audit`). Annual spend = sum of `annual_line_total` for
   the current contract year. Commits feed the untapped slide.
3. **Story**: Gong (via SF) + filed `Notes/` (incl. the Granola export) for the last ~180 days: wins, consolidation,
   growth quotes. Use the `/account-brief` fan-out.
4. **Next**: any agentic-solution ROI sheets you keep (learning & enablement, revenue engagement) and any `VBF/`
   already in the account folder. Learning agents fit training/enablement use; revenue agents fit marketing/pipeline use.

## 2. Compute

Write `$CC_DIR/issues/<account>/value-id_spec.json` (shape: docstring of `scripts/build_value_pptx.py`;
`inputs` = `scripts/value_calc.py` inputs incl. `annual_spend`). Check the numbers:
`python3 $CC_DIR/.claude/skills/value-id/scripts/value_calc.py <inputs.json>` (no args = self-check).

Untapped = commit vs. trailing-12 use per pool. Anything under 50% is headroom for the deck and a churn
flag for the companion. Anything over 100% is overage/upsell, and goes in the companion only.
Unmeasured paid lines go on the manual-check list, ranked by $.

## 3. Build

```
uv run --with python-pptx python $CC_DIR/.claude/skills/value-id/scripts/build_value_pptx.py \
  $CC_DIR/issues/<account>/value-id_spec.json "<account folder>/Value Reports/YYYY-MM-DD_<Account> - Value Delivered.pptx"
```
Slides: Cover · At a glance (lever blocks + stat strip) · Value by lever (table with rate and source) ·
Untapped (≤4 rows) · What's next (≤3 rows) · Thank you. Sources and VALIDATE items go in speaker notes (`notes`).
Keep `untapped` and `next` items as `"Label: text"` and keep the text under about 130 characters, or it overflows its row.

### Brand and template

No template or brand assets ship with this skill. The builder reads `config.local.json`
(`$CC_DIR/config.local.json`; `$CC_DIR` defaults to the repo root):

- `paths.brand_dir`: a local folder with `template.pptx` (optional), `logo.png` (optional) and `fonts/` (optional;
  install them on the viewing machine, PowerPoint needs a restart to pick them up).
- `brand.colors` (`primary`, `light`, `line`, `dark`, `muted`, `background`; hex), `brand.title_font`, `brand.body_font`.
  Missing keys fall back to a neutral blue/charcoal palette and Calibri. See `/vbf` SKILL.md "Branding" for the shape.

**With no `template.pptx`** the builder draws the same six slides on a blank 16:9 `Presentation()` in the brand colors,
adding the logo to the title bar only if `logo.png` exists. This is the default for a fresh checkout.

**With a `template.pptx`** the builder only fills text into it; it draws no shapes. Template contract:
- Exactly three slides: cover, at-a-glance, table panel.
- Cover: placeholders 0 (title) and 1 (subtitle); optional chip shapes named `Journey <Audience>`.
- At a glance: placeholder 17 (headline); shapes `Block <name>`, `Block title <name>`, `Block text <name>` (up to 4), `Stat *` (3).
- Table panel: placeholders 17 and 22, a shape named `Table label`, one table (rows: header, base, alt, total).
- Layouts named `14_3 text box` (4 rows: label placeholders 12/18/19/23, text 20/21/22/24, footer 25, title 16),
  `3_3 text box` (3 rows: 12/18/19, 20/21/22, footer 23, title 16) and `2_Section Header` (close).

`scripts/recolor_template.py [template] [out]` is an optional one-off that recolors such a template to mixed theme
accents (charcoal backgrounds, cards and rows cycling accent1-5), using theme colors only. It expects the shape and
layout names above plus the template's own decorative shape names listed in the script; adjust those for your template.

`<account folder>` = `<accounts_root>/<Account>/` (create `Value Reports/` if missing). The companion stays in `issues/`.

Verify:
1. Reopen with python-pptx: 6 slides, no shape out of bounds, and no spend/ROI/INTERNAL text on any slide.
2. Render and look at every slide. On macOS with PowerPoint (sandboxed: opening a file from a folder it hasn't been
   granted raises a hidden "Grant File Access" dialog and later AppleScript calls fail with -9074), copy the deck into
   its container first:
   ```
   C=~/Library/Containers/com.microsoft.Powerpoint/Data/tmp_valueid; mkdir -p $C; cp "<pptx>" $C/deck.pptx
   osascript -e 'with timeout of 600 seconds' -e 'tell application "Microsoft PowerPoint"' -e "open POSIX file \"$C/deck.pptx\"" \
     -e "save active presentation in POSIX file \"$C/deck.pdf\" as save as PDF" -e 'close active presentation saving no' -e 'end tell' -e 'end timeout'
   pdftoppm -png -r 60 $C/deck.pdf <scratch>/slide
   ```
   Read each PNG. Fix any overflow, overlap or clipped text before reporting. If a call still fails with -9074,
   check for the dialog with `osascript -e 'tell application "System Events" to tell process "Microsoft PowerPoint" to get name of every window'`
   and click Cancel on it. Without PowerPoint, LibreOffice (`soffice --headless --convert-to pdf`) works too.

## 4. Companion (internal)

`$CC_DIR/issues/<account>/YYYY-MM-DD_value-id_internal.md`: value health (green ≥3×, amber 1–3×, red <1×),
hard savings vs. total, a lever table with sources, a commit-vs-use table, a validate list, and source
availability (used / skipped / failed, with the reason).

## Report

Deck path, companion path, the health line, top validate items, and each source's status.
