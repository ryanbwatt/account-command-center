#!/usr/bin/env python3
"""Build a one-slide Value Based Framework (VBF) deck from a JSON spec.

Usage:
  uv run --with python-pptx python build_vbf_pptx.py spec.json output.pptx

Spec: see ../template.md. Bullet items are either a string or
{"text": "...", "hypothesis": true}; hypotheses render italic with "(validate)".
Sources, validation list and gaps go into the speaker notes.
Brand (colors, fonts, logo) comes from config.local.json; see ../SKILL.md "Branding".
"""
import json
import os
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = os.path.dirname(os.path.realpath(__file__))
DEFAULT_COLORS = {  # neutral defaults; override in config.local.json -> brand.colors (hex, no #)
    "primary": "1F5FAD",     # accent / title bar
    "light": "D6E4F5",       # cell headers
    "line": "BFBFBF",
    "dark": "2B2B2B",        # body text
    "muted": "595959",
    "background": "F5F6F8",
}


def load_brand():
    """Brand from $CC_DIR/config.local.json: brand.{colors,title_font,body_font} + paths.brand_dir
    (logo.png, optional template.pptx, optional fonts/). Anything missing falls back to neutral defaults."""
    root = os.environ.get("CC_DIR") or os.path.join(HERE, "..", "..", "..", "..")
    try:
        with open(os.path.join(root, "config.local.json")) as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    b = cfg.get("brand", {})
    d = os.path.expanduser(os.path.expandvars(cfg.get("paths", {}).get("brand_dir", "") or ""))
    found = lambda name: os.path.join(d, name) if d and os.path.isfile(os.path.join(d, name)) else None
    return {"colors": DEFAULT_COLORS | b.get("colors", {}),
            "title_font": b.get("title_font", "Calibri"), "body_font": b.get("body_font", "Calibri"),
            "logo": found("logo.png"), "template": found("template.pptx")}


BRAND = load_brand()
_c = {k: RGBColor.from_string(v.lstrip("#").upper()) for k, v in BRAND["colors"].items()}
NAVY = _c["primary"]
GREY = _c["light"]
LINE = _c["line"]
DARK = _c["dark"]
INK = DARK
MUTED = _c["muted"]
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BG = _c["background"]

FONT = BRAND["body_font"]
TITLE_FONT = BRAND["title_font"]
LOGO = BRAND["logo"]  # None -> no logo


def add_box(slide, x, y, w, h, fill=None, line=LINE):
    shp = slide.shapes.add_shape(1, x, y, w, h)
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    shp.shadow.inherit = False
    return shp


def set_run(run, size, bold=False, italic=False, color=DARK, title=False):
    run.font.name = TITLE_FONT if title else FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color


def text_box(slide, x, y, w, h, margin=0.06):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    m = Inches(margin)
    tf.margin_left = tf.margin_right = m
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    return tb, tf


def norm(item):
    if isinstance(item, str):
        return item, False
    return item["text"], bool(item.get("hypothesis"))


def pick_size(groups, w, h, base=11.0, floor=7.5):
    """Largest font (<= base) whose estimated wrapped height fits the cell."""
    usable_w_pt = (w - Inches(0.2)) / 12700
    usable_h_pt = (h - Inches(0.4)) / 12700
    size = base
    while True:
        cpl = max(1, int(usable_w_pt / (size * 0.5)))
        lines = 0
        for g in groups:
            if g.get("label"):
                lines += 1
            for i in g.get("items", []):
                t = norm(i)[0] + (" (validate)" if norm(i)[1] else "")
                lines += -(-(len(t) + 2) // cpl)
        need = lines * size * 1.2 + lines * 2
        if need <= usable_h_pt or size <= floor:
            return size
        size -= 0.5


def fill_cell(slide, x, y, w, h, title, cell):
    add_box(slide, x, y, w, Inches(0.3), fill=GREY)
    _, tf = text_box(slide, x, y, w, Inches(0.3))
    p = tf.paragraphs[0]
    set_run(p.add_run(), 12, bold=True, color=INK, title=True)
    p.runs[0].text = title
    add_box(slide, x, y + Inches(0.3), w, h - Inches(0.3), fill=None)

    groups = [
        {"label": "Operations Experience", "items": cell.get("operations", [])},
        {"label": "End User Experience", "items": cell.get("end_user", [])},
    ]
    groups = [g for g in groups if g["items"]]
    if cell.get("summary"):
        groups.insert(0, {"label": None, "items": [cell["summary"]]})
    size = pick_size(groups, w, h)

    _, tf = text_box(slide, x, y + Inches(0.32), w, h - Inches(0.34))
    first = True
    for g in groups:
        if g["label"]:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            r = p.add_run()
            r.text = g["label"]
            set_run(r, size, bold=True, color=NAVY, title=True)
            p.space_before = Pt(2)
        for item in g["items"]:
            text, hyp = norm(item)
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            r = p.add_run()
            r.text = ("• " if g["label"] else "") + text
            set_run(r, size, italic=hyp)
            if hyp:
                r2 = p.add_run()
                r2.text = " (validate)"
                set_run(r2, size - 1, italic=True, color=MUTED)
            p.space_after = Pt(2)


def build(spec, out):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    W = prs.slide_width
    gutter = Inches(0.25)
    left = Inches(0.4)
    inner_w = W - 2 * left

    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = BG
    add_box(slide, 0, 0, W, Inches(0.5), fill=NAVY, line=None)
    if LOGO:
        slide.shapes.add_picture(LOGO, left, Inches(0.11), height=Inches(0.28))
    _, tf = text_box(slide, left, Inches(0.05), inner_w, Inches(0.4))
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = spec.get("title", "INSIGHTS TO ACTION: VALUE BASED FRAMEWORK")
    set_run(r, 16, bold=True, color=WHITE, title=True)

    _, tf = text_box(slide, left, Inches(0.58), inner_w, Inches(0.55))
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = spec.get("account_profile", spec.get("account", "")) + ": "
    set_run(r, 12, bold=True, title=True)
    r = p.add_run()
    r.text = spec.get("headline", "")
    set_run(r, 12)

    col_w = int((inner_w - gutter) / 2)
    row_h = Inches(2.15)
    top = Inches(1.2)
    x1, x2 = left, left + col_w + gutter
    y1 = top
    y2 = top + row_h + Inches(0.1)

    fill_cell(slide, x1, y1, col_w, row_h, spec.get("labels", {}).get("before", "Before Scenario (As-Is)"), spec["before"])
    fill_cell(slide, x2, y1, col_w, row_h, spec.get("labels", {}).get("negative", "Negative Business Impact"), spec["negative_impact"])
    fill_cell(slide, x1, y2, col_w, row_h, spec.get("labels", {}).get("after", "After Scenario (To-Be)"), spec["after"])
    fill_cell(slide, x2, y2, col_w, row_h, spec.get("labels", {}).get("positive", "Positive Business Outcome"), spec["positive_outcome"])

    y3 = y2 + row_h + Inches(0.1)
    h3 = Inches(7.5) - y3 - Inches(0.4)
    add_box(slide, left, y3, inner_w, Inches(0.28), fill=GREY)
    _, tf = text_box(slide, left, y3, inner_w, Inches(0.28))
    r = tf.paragraphs[0].add_run()
    r.text = "Proof Points"
    set_run(r, 12, bold=True, color=INK, title=True)
    add_box(slide, left, y3 + Inches(0.28), inner_w, h3 - Inches(0.28), fill=None)
    _, tf = text_box(slide, left, y3 + Inches(0.3), inner_w, h3 - Inches(0.3))
    pp = spec.get("proof_points", {})
    rows = [
        ("Critical Capabilities", pp.get("capabilities")),
        ("Customer Evidence", pp.get("evidence")),
        ("Applicable Use Cases", pp.get("use_cases")),
    ]
    first = True
    for label, val in rows:
        if not val:
            continue
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        r = p.add_run()
        r.text = label + ": "
        set_run(r, 10, bold=True, title=True)
        r = p.add_run()
        r.text = val if isinstance(val, str) else "; ".join(val)
        set_run(r, 10)
        p.space_after = Pt(1)

    _, tf = text_box(slide, left, Inches(7.5) - Inches(0.35), inner_w, Inches(0.3))
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = spec.get("footer", "Integration discussions.")
    set_run(r, 8, color=MUTED)

    notes = []
    if spec.get("validate"):
        notes.append("VALIDATE WITH CUSTOMER:\n" + "\n".join("- " + v for v in spec["validate"]))
    if spec.get("gaps"):
        notes.append("GAPS / DISCOVERY QUESTIONS:\n" + "\n".join("- " + v for v in spec["gaps"]))
    if spec.get("sources"):
        notes.append("SOURCES:\n" + "\n".join("- " + v for v in spec["sources"]))
    if spec.get("source_status"):
        notes.append("SOURCE STATUS:\n" + "\n".join("- " + v for v in spec["source_status"]))
    slide.notes_slide.notes_text_frame.text = "\n\n".join(notes)

    prs.save(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1]) as f:
        build(json.load(f), sys.argv[2])
    print(sys.argv[2])
