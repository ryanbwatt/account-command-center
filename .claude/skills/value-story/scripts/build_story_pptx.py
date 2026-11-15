#!/usr/bin/env python3
"""Build the quarterly /value-story deck on value-id's template (or a plain deck when none is configured).

Usage:
  uv run --with python-pptx python build_story_pptx.py spec.json output.pptx
  uv run --with python-pptx python build_story_pptx.py          # self-check

Spec:
  {"customer", "period", "headline",
   "audiences": ["Employees", ...]            # cover chips kept: Customers / Employees / Learners / Audiences
   "pillars": {"Stabilize": text, "Compete": text, "Grow": text},
   "featured": [title, text],                 # optional 4th glance block (e.g. AI)
   "stat": [big, small],                      # optional 3rd stat after money saved / made
   "outcomes": [{"priority", "pillar", "did", "impact", "evidence",
                 "value": $ optional, "kind": "saved"|"made", "basis": "customer"|"measured"|"benchmark"}],  # max 4
   "next": ["Label: text", ...],              # max 3
   "notes": {slide_no: text}}
Totals count only customer-reported and measured values; benchmark-only values show as "est." and stay out.
"""
import copy
import importlib.util
import json
import os
import sys

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.realpath(__file__))
_p = os.path.join(HERE, "..", "..", "value-id", "scripts", "build_value_pptx.py")
_s = importlib.util.spec_from_file_location("build_value_pptx", _p)
vid = importlib.util.module_from_spec(_s)
_s.loader.exec_module(vid)
put, named, ph, money, rows_slide, layout = vid.put, vid.named, vid.ph, vid.money, vid.rows_slide, vid.layout

PILLARS = ("Stabilize", "Compete", "Grow")
MAX_ROWS = 4  # panel fits 4 two-line rows at 12pt


def totals(outcomes):
    t = {"saved": 0, "made": 0}
    for o in outcomes:
        if o.get("value") and o.get("basis") in ("customer", "measured"):
            t[o["kind"]] += o["value"]
    return t


def impact_text(o):
    if not o.get("value"):
        return o["impact"]
    est = " (est.)" if o.get("basis") == "benchmark" else ""
    return f"{money(o['value'])} {o['kind']}{est}\n{o['impact']}"


def drop(shp):
    shp._element.getparent().remove(shp._element)


def build(spec, out):
    outcomes = spec.get("outcomes", [])
    assert len(outcomes) <= MAX_ROWS, f"max {MAX_ROWS} outcomes, got {len(outcomes)}"
    assert all(o.get("pillar") in PILLARS for o in outcomes), f"pillar must be one of {PILLARS}"
    t = totals(outcomes)
    notes = {int(k): v for k, v in spec.get("notes", {}).items()}
    footer = f"{spec['customer']}  |  {spec['period']}"
    blocks = [(p, spec["pillars"][p]) for p in PILLARS if spec.get("pillars", {}).get(p)]
    if spec.get("featured"):
        blocks.append(tuple(spec["featured"]))
    stats = [(money(t[k]), f"money {k}") for k in ("saved", "made") if t[k]]
    if spec.get("stat"):
        stats.append(tuple(spec["stat"]))
    header = ["Your priority", "Pillar", "What we did", "Impact", "Evidence"]
    if not vid.TEMPLATE:
        sub = f"{spec['customer']}  ·  {spec['period']}"
        if spec.get("audiences"):
            sub += "  ·  " + " / ".join(spec["audiences"])
        vid.plain_deck([
            {"title": "Your value story", "subtitle": sub},
            {"title": spec["headline"], "blocks": blocks[:4], "stats": stats[:3]},
            {"title": "Your priorities", "subtitle": "What you told us matters, and what moved this quarter",
             "table": [header] + [[o["priority"], o["pillar"], o["did"], impact_text(o), o["evidence"]] for o in outcomes]},
            {"title": "Next quarter's value", "rows": [vid.split(x) for x in spec.get("next", [])[:3]]},
            {"title": "Thank you"},
        ], out, notes, footer)
        return t
    prs = Presentation(vid.TEMPLATE)
    cover, glance, table_slide = prs.slides

    # 1. Cover: keep only the audience chips this customer serves
    put(ph(cover, 0), "Your value story")
    put(ph(cover, 1), f"{spec['customer']}  ·  {spec['period']}")
    keep = set(spec.get("audiences") or [])
    for chip in named(cover, "Journey "):
        name = chip.name.removeprefix("Journey ")
        put(chip.text_frame, name) if not keep or name in keep else drop(chip)

    # 2. At a glance: Stabilize / Compete / Grow (+ featured), stat strip = saved, made, custom
    put(ph(glance, 17), spec["headline"])
    for pic in [s for s in glance.shapes if s.shape_type == 13]:
        drop(pic)
    titles, texts = named(glance, "Block title "), named(glance, "Block text ")
    cards = [b for b in named(glance, "Block ") if not b.name.startswith(("Block title ", "Block text "))]
    for i, (card, ti, tx) in enumerate(zip(cards, titles, texts)):
        if i < len(blocks):
            put(ti.text_frame, blocks[i][0])
            put(tx.text_frame, blocks[i][1])
        else:
            for shp in (card, ti, tx):
                drop(shp)
    for i, shp in enumerate(named(glance, "Stat ")):
        put(shp.text_frame, *stats[i]) if i < len(stats) else put(shp.text_frame, "")

    # 3. Priorities -> outcomes table
    put(ph(table_slide, 17), "What you told us matters, and what moved this quarter")
    put(ph(table_slide, 22), footer)
    put(next(s for s in table_slide.shapes if s.name == "Table label").text_frame, "YOUR PRIORITIES")
    tbl = next(s for s in table_slide.shapes if s.has_table).table
    trs = tbl._tbl.tr_lst
    base = trs[1]
    for tr in trs[1:]:
        tbl._tbl.remove(tr)
    for col, w in zip(tbl.columns, (2.2, 1.2, 3.3, 2.1, 2.31)):  # 11.11" total, same as value-id
        col.width = Inches(w)
    for c, h in zip(tbl.rows[0].cells, header):
        put(c.text_frame, h)
    for c in tbl.rows[0].cells:
        c.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    for o in outcomes:
        tbl._tbl.append(copy.deepcopy(base))
        r = tbl.rows[len(tbl.rows) - 1]
        r.height = Inches(0.62)
        for c, v in zip(r.cells, [o["priority"], o["pillar"], o["did"], impact_text(o), o["evidence"]]):
            put(c.text_frame, *v.split("\n"))
            for p in c.text_frame.paragraphs:  # template rows are 16pt right-aligned numbers; ours are sentences
                p.alignment = PP_ALIGN.LEFT
                for run in p.runs:
                    run.font.size = Pt(12)

    # 4. Next quarter, 5. Close
    rows_slide(prs, "3_3 text box", [12, 18, 19], [20, 21, 22], 23, 16,
               spec.get("next", []), footer, "Next quarter's value")
    prs.slides.add_slide(layout(prs, "2_Section Header"))

    for i, s in enumerate(prs.slides, 1):
        s.notes_slide.notes_text_frame.text = notes.get(i, "")
        for shp in s.shapes:
            frames = [c.text_frame for r in shp.table.rows for c in r.cells] if shp.has_table else (
                [shp.text_frame] if shp.has_text_frame else [])
            for tf in frames:
                for p in tf.paragraphs:
                    for run in p.runs:
                        run.font.name = vid.FONT
    prs.save(out)
    return t


def _check():
    import tempfile
    spec = {"customer": "Acme Corp", "period": "Q4 2026", "headline": "h", "audiences": ["Employees"],
            "pillars": {"Stabilize": "a", "Compete": "b", "Grow": "c"},
            "outcomes": [
                {"priority": "p", "pillar": "Grow", "did": "d", "impact": "i", "evidence": "e",
                 "value": 50000, "kind": "made", "basis": "customer"},
                {"priority": "p", "pillar": "Stabilize", "did": "d", "impact": "i", "evidence": "e",
                 "value": 9000, "kind": "saved", "basis": "measured"},
                {"priority": "p", "pillar": "Stabilize", "did": "d", "impact": "i", "evidence": "e",
                 "value": 1e6, "kind": "saved", "basis": "benchmark"}],
            "next": ["A: b"]}
    out = os.path.join(tempfile.mkdtemp(), "t.pptx")
    t = build(spec, out)
    assert t == {"saved": 9000, "made": 50000}, t  # benchmark row excluded
    assert impact_text(spec["outcomes"][2]).startswith("$1.0M saved (est.)")
    prs = Presentation(out)
    assert len(prs.slides) == 5
    text = " ".join(sh.text_frame.text for s in prs.slides for sh in s.shapes if sh.has_text_frame)
    assert "Customers" not in text and "Employees" in text and "money made" in text
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        _check()
    elif len(sys.argv) == 3:
        with open(sys.argv[1]) as f:
            print(build(json.load(f), sys.argv[2]))
    else:
        sys.exit(__doc__)
