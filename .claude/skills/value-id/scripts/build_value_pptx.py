#!/usr/bin/env python3
"""Build the customer-facing /value-id deck, on your own template if you have one.

Usage:
  uv run --with python-pptx python build_value_pptx.py spec.json output.pptx

Spec: {"customer", "period", "inputs": <value_calc inputs>, "lever_notes": {lever_key: "what we measured"},
       "highlights": [[big, small], ...], "untapped": ["Label: text", ...] (max 4),
       "next": ["Label: text", ...] (max 3), "notes": {slide_no: text}}
Spend and the ROI multiple are never rendered; they belong in the internal companion.

Template: <paths.brand_dir>/template.pptx (config.local.json). It must hold three component slides
(cover, blocks + stat strip, table panel) and the layouts named below; the builder only fills text into them
(contract in ../SKILL.md). With no template, plain_deck() draws the same six slides on a blank
Presentation() in the brand colors from config (neutral defaults).
"""
import copy
import importlib.util
import json
import os
import sys

from pptx import Presentation
from pptx.util import Inches

HERE = os.path.dirname(os.path.realpath(__file__))  # realpath: skill may be symlinked into each Claude profile
_v = importlib.util.spec_from_file_location("build_vbf_pptx", os.path.join(HERE, "..", "..", "vbf", "scripts", "build_vbf_pptx.py"))
vbf = importlib.util.module_from_spec(_v)
_v.loader.exec_module(vbf)  # brand loader + colors shared with /vbf
TEMPLATE = vbf.BRAND["template"]  # None -> plain_deck()
FONT = vbf.FONT

_spec = importlib.util.spec_from_file_location("value_calc", os.path.join(HERE, "value_calc.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
calc = _mod.calc


def money(v):
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e4:
        return f"${v / 1e3:.0f}K"
    return f"${v:,.0f}"


def put(tf, *lines):
    """Replace a text frame's text, keeping each paragraph's existing formatting."""
    paras = tf.paragraphs
    for i, line in enumerate(lines):
        if i >= len(paras):
            tf._txBody.append(copy.deepcopy(paras[-1]._p))
        p = tf.paragraphs[i]
        runs = p.runs
        if not runs:
            p.add_run()
            runs = p.runs
        runs[0].text = line
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
    for p in tf.paragraphs[len(lines):]:
        p._p.getparent().remove(p._p)


def named(slide, prefix):
    return sorted((s for s in slide.shapes if s.name.startswith(prefix)), key=lambda s: s.left)


def ph(slide, idx):
    return slide.placeholders[idx].text_frame


def split(item):
    label, _, text = item.partition(": ")
    return label, text


def layout(prs, name):
    return next(l for l in prs.slide_layouts if l.name == name)


def rows_slide(prs, layout_name, labels, texts, footer_idx, title_idx, items, footer, title):
    assert len(items) <= len(labels), f"{layout_name} holds {len(labels)} items, got {len(items)}"
    s = prs.slides.add_slide(layout(prs, layout_name))
    put(ph(s, title_idx), title)
    for (label, text), li, ti in zip(map(split, items), labels, texts):
        put(ph(s, li), label)
        put(ph(s, ti), text)
    for li, ti in zip(labels[len(items):], texts[len(items):]):  # unused rows
        for idx in (li, ti):
            e = s.placeholders[idx]._element
            e.getparent().remove(e)
    put(ph(s, footer_idx), footer)
    f = s.placeholders[footer_idx]  # layout's footer box is too narrow; widen to match the table slide's
    f.left, f.top, f.width, f.height = f.left, f.top, Inches(4.17), f.height
    return s


def _cards(s, y, h, items, fill, color):
    """A row of equal cards, each (big, small)."""
    n = len(items)
    w = (12.53 - 0.2 * (n - 1)) / n
    for j, (big, small) in enumerate(items):
        shp = vbf.add_box(s, Inches(0.4 + j * (w + 0.2)), Inches(y), Inches(w), Inches(h), fill=fill, line=None)
        tf = shp.text_frame
        tf.word_wrap = True
        for k, (t, size, bold) in enumerate([(big, 24, True), (small, 12, False)]):
            p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            vbf.set_run(p.add_run(), size, bold=bold, color=color, title=bold)
            p.runs[0].text = t


def plain_deck(slides, out, notes, footer):
    """No template: draw each slide dict {title, subtitle, blocks, stats, table, rows} on a blank 16:9 deck."""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    for i, sd in enumerate(slides, 1):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = vbf.BG
        vbf.add_box(s, 0, 0, prs.slide_width, Inches(0.5), fill=vbf.NAVY, line=None)
        if vbf.LOGO:
            s.shapes.add_picture(vbf.LOGO, Inches(0.4), Inches(0.11), height=Inches(0.28))
        _, tf = vbf.text_box(s, Inches(0.4), Inches(0.8), Inches(12.53), Inches(0.9))
        vbf.set_run(tf.paragraphs[0].add_run(), 28, bold=True, title=True)
        tf.paragraphs[0].runs[0].text = sd["title"]
        if sd.get("subtitle"):
            _, tf = vbf.text_box(s, Inches(0.4), Inches(1.65), Inches(12.53), Inches(0.5))
            vbf.set_run(tf.paragraphs[0].add_run(), 16, color=vbf.MUTED)
            tf.paragraphs[0].runs[0].text = sd["subtitle"]
        y = 2.4
        if sd.get("blocks"):
            _cards(s, y, 1.6, sd["blocks"], vbf.NAVY, vbf.WHITE)
            y += 1.8
        if sd.get("stats"):
            _cards(s, y, 1.2, sd["stats"], vbf.GREY, vbf.DARK)
            y += 1.4
        if sd.get("table"):
            rows = sd["table"]
            tbl = s.shapes.add_table(len(rows), len(rows[0]), Inches(0.4), Inches(y), Inches(12.53), Inches(0.5 * len(rows))).table
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    cell = tbl.cell(r, c)
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = vbf.NAVY if r == 0 else vbf.WHITE
                    cell.text_frame.word_wrap = True
                    for k, line in enumerate(str(val).split("\n")):
                        p = cell.text_frame.paragraphs[0] if k == 0 else cell.text_frame.add_paragraph()
                        vbf.set_run(p.add_run(), 11 if k == 0 else 9, bold=(r == 0), color=vbf.WHITE if r == 0 else vbf.DARK)
                        p.runs[0].text = line
        for j, (label, text) in enumerate(sd.get("rows", [])):
            shp = vbf.add_box(s, Inches(0.4), Inches(y + j * 1.1), Inches(12.53), Inches(0.95), fill=vbf.WHITE)
            tf = shp.text_frame
            tf.word_wrap = True
            vbf.set_run(tf.paragraphs[0].add_run(), 16, bold=True, color=vbf.NAVY, title=True)
            tf.paragraphs[0].runs[0].text = label
            p = tf.add_paragraph()
            vbf.set_run(p.add_run(), 13)
            p.runs[0].text = text
        _, tf = vbf.text_box(s, Inches(0.4), Inches(7.1), Inches(12.53), Inches(0.3))
        vbf.set_run(tf.paragraphs[0].add_run(), 9, color=vbf.MUTED)
        tf.paragraphs[0].runs[0].text = footer
        s.notes_slide.notes_text_frame.text = notes.get(i, "")
    prs.save(out)


RATE_OF = {"live_training": "cost_per_learning_hour", "ondemand_training": "cost_per_learning_hour",
           "delivery": "cdn_per_gb", "storage": "storage_per_gb_month", "captions": "caption_per_minute"}
UNITS = {"cost_per_learning_hour": "/ hour", "cdn_per_gb": "/ GB",
         "storage_per_gb_month": "/ GB/mo", "caption_per_minute": "/ minute"}
LEVER_HEADER = ["Value lever", "Lens", "Value", "Rate", "What we measured"]


def lever_rows(r, counted, spec):
    out = []
    for l in counted:
        rate = r["rates"][RATE_OF[l["key"]]]
        out.append([l["label"], l["lens"], money(l["value"]), f"${rate['value']:g} {UNITS[RATE_OF[l['key']]]}",
                    [spec.get("lever_notes", {}).get(l["key"], ""), "Source: " + rate["source"]]])
    return out


def build(spec, out):
    r = calc(spec["inputs"])
    counted = sorted((l for l in r["levers"] if l["value"] is not None), key=lambda l: -l["value"])
    notes = {int(k): v for k, v in spec.get("notes", {}).items()}
    footer = f"{spec['customer']}  |  {spec['period']}"
    highlights = [tuple(h) for h in spec.get("highlights", [])]
    blocks = [(money(l["value"]), l["label"]) for l in counted] + highlights[2:]
    stats = [(money(r["total"]), "estimated value delivered")] + highlights[:2]
    rows = lever_rows(r, counted, spec)
    if not TEMPLATE:
        table = [LEVER_HEADER] + [row[:4] + ["\n".join(row[4])] for row in rows] + [["Total", "", money(r["total"]), "", ""]]
        plain_deck([
            {"title": "Value delivered", "subtitle": f"{spec['customer']}  ·  {spec['period']}"},
            {"title": f"{money(r['total'])} in value delivered", "blocks": blocks[:4], "stats": stats},
            {"title": "Value by lever", "subtitle": "Each figure is a measured metric multiplied by a published rate", "table": table},
            {"title": "Capacity already in your agreement", "rows": [split(x) for x in spec.get("untapped", [])[:4]]},
            {"title": "Where the next value comes from", "rows": [split(x) for x in spec.get("next", [])[:3]]},
            {"title": "Thank you"},
        ], out, notes, footer)
        return r
    prs = Presentation(TEMPLATE)
    cover, glance, table_slide = prs.slides

    # 1. Cover
    put(ph(cover, 0), "Value delivered")
    put(ph(cover, 1), f"{spec['customer']}  ·  {spec['period']}")
    for chip in named(cover, "Journey "):
        put(chip.text_frame, chip.name.removeprefix("Journey "))

    # 2. At a glance: four blocks = levers then highlights; stat strip = total + first two highlights
    put(ph(glance, 17), f"{money(r['total'])} in value delivered")
    titles, texts = named(glance, "Block title "), named(glance, "Block text ")
    for pic in [s for s in glance.shapes if s.shape_type == 13]:  # template icons don't match our levers
        pic._element.getparent().remove(pic._element)
    cards = [b for b in named(glance, "Block ") if not b.name.startswith(("Block title ", "Block text "))]
    for i, (card, t, x) in enumerate(zip(cards, titles, texts)):
        if i < len(blocks):
            put(t.text_frame, blocks[i][0])
            put(x.text_frame, blocks[i][1])
        else:  # fewer than four things to show: drop the whole block
            for shp in (card, t, x):
                shp._element.getparent().remove(shp._element)
    for shp, (big, small) in zip(named(glance, "Stat "), stats):
        put(shp.text_frame, big, small)

    # 3. Value by lever: template table rows = header, base, alt, total, extra
    put(ph(table_slide, 17), "Each figure is a measured metric multiplied by a published rate")
    put(ph(table_slide, 22), footer)
    put(next(s for s in table_slide.shapes if s.name == "Table label").text_frame, "VALUE BY LEVER")
    tbl = next(s for s in table_slide.shapes if s.has_table).table
    trs = tbl._tbl.tr_lst
    base, total_tr = trs[1], trs[3]
    for tr in trs[1:]:
        tbl._tbl.remove(tr)
    for col, w in zip(tbl.columns, (2.5, 1.45, 1.05, 1.6, 4.51)):  # 11.11" total
        col.width = Inches(w)
    for c, h in zip(tbl.rows[0].cells, LEVER_HEADER):
        put(c.text_frame, h)
    for cells in rows:
        tbl._tbl.append(copy.deepcopy(base))
        for c, v in zip(tbl.rows[len(tbl.rows) - 1].cells, cells):
            put(c.text_frame, *(v if isinstance(v, list) else [v]))
    tbl._tbl.append(total_tr)
    for c, v in zip(tbl.rows[len(tbl.rows) - 1].cells, ["Total", "", money(r["total"]), "", ""]):
        put(c.text_frame, v)

    # 4-5. Untapped value (4 rows), what's next (3 rows): template layouts
    rows_slide(prs, "14_3 text box", [12, 18, 19, 23], [20, 21, 22, 24], 25, 16,
                    spec.get("untapped", []), footer, "Capacity already in your agreement")
    rows_slide(prs, "3_3 text box", [12, 18, 19], [20, 21, 22], 23, 16,
                    spec.get("next", []), footer, "Where the next value comes from")

    # 6. Close
    prs.slides.add_slide(layout(prs, "2_Section Header"))

    for i, s in enumerate(prs.slides, 1):
        s.notes_slide.notes_text_frame.text = notes.get(i, "")
        for shp in s.shapes:
            frames = [c.text_frame for row in shp.table.rows for c in row.cells] if shp.has_table else (
                [shp.text_frame] if shp.has_text_frame else [])
            for tf in frames:
                for p in tf.paragraphs:
                    for run in p.runs:
                        run.font.name = FONT
    prs.save(out)
    return r


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1]) as f:
        build(json.load(f), sys.argv[2])
    print(sys.argv[2])
