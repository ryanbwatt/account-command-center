"""One-off: give a /value-id template mixed theme accents (cards and rows cycle accent1-5, charcoal accent6 backgrounds).

Usage:
  python3 recolor_template.py [template.pptx] [out.pptx]
  defaults: <paths.brand_dir>/template.pptx (config.local.json) -> <same dir>/template.recolored.pptx

Uses theme colors only (schemeClr accent1..6, tx1, bg1), so the result follows whatever palette the
template's theme defines. The template must have the layout and shape names listed in ../SKILL.md
("Template contract"). If a layout has a white-logo picture shape (name starting "Logo"), it is reused on the
charcoal "What's next" layout; otherwise that step is skipped.
"""
import importlib.util
import os
import sys

from lxml import etree
from pptx import Presentation

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
DARK, LIGHT = "tx1", "bg1"
ON = {"accent1": LIGHT, "accent2": DARK, "accent3": DARK, "accent4": LIGHT, "accent5": DARK}


def fill_el(clr):
    f = etree.SubElement(etree.Element("x"), f"{{{A}}}solidFill")
    etree.SubElement(f, f"{{{A}}}schemeClr", val=clr)
    return f


def set_fill(el, clr):
    sppr = el.find(f"{{{P}}}spPr")
    for old in sppr.findall(f"{{{A}}}solidFill") + sppr.findall(f"{{{A}}}noFill") + sppr.findall(f"{{{A}}}gradFill"):
        sppr.remove(old)
    geom = sppr.find(f"{{{A}}}prstGeom")
    geom.addnext(fill_el(clr)) if geom is not None else sppr.append(fill_el(clr))


def set_text(el, clr):
    """Every text colour inside the shape's txBody (layout defaults and runs) -> clr."""
    body = el.find(f"{{{P}}}txBody")
    for f in body.iter(f"{{{A}}}solidFill"):
        for c in list(f):
            f.remove(c)
        etree.SubElement(f, f"{{{A}}}schemeClr", val=clr)
    for tag in ("defRPr", "rPr", "endParaRPr"):
        for r in body.iter(f"{{{A}}}{tag}"):
            if r.find(f"{{{A}}}solidFill") is None:
                r.insert(0, fill_el(clr))


def set_bg(layout, clr):
    bg = layout._element.find(f".//{{{P}}}bg")
    bgpr = bg.find(f"{{{P}}}bgPr")
    old = bgpr.find(f"{{{A}}}solidFill")
    old.addprevious(fill_el(clr))
    bgpr.remove(old)


def shape(container, name, idx=None):
    for s in container.shapes:
        if (idx is not None and s.is_placeholder and s.placeholder_format.idx == idx) or (idx is None and s.name.startswith(name)):
            return s._element
    raise KeyError(name or idx)


HERE = os.path.dirname(os.path.realpath(__file__))
_v = importlib.util.spec_from_file_location("build_vbf_pptx", os.path.join(HERE, "..", "..", "vbf", "scripts", "build_vbf_pptx.py"))
_vbf = importlib.util.module_from_spec(_v)
_v.loader.exec_module(_vbf)
src = sys.argv[1] if len(sys.argv) > 1 else _vbf.BRAND["template"]
if not src or not os.path.isfile(src):
    sys.exit("No template: pass a path, or put template.pptx in paths.brand_dir (config.local.json).")
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + ".recolored.pptx"
p = Presentation(src)
L = {l.name: l for l in p.slide_layouts}
cover, glance, _ = p.slides

# Cover: chips sit on layout shapes. Customers / Employees / Audiences, plus two filler shapes.
c = L["3_Title Slide"]
for name, clr in [("Rounded Rectangle 14", "accent2"), ("Rounded Rectangle 15", "accent4"),
                  ("Rounded Rectangle 16", "accent1"), ("Oval 17", "accent3"),
                  ("Rounded Rectangle 18", "accent3"), ("Rounded Rectangle 32", "accent2")]:
    set_fill(shape(c, name), clr)
for chip, clr in [("Journey Customers", DARK), ("Journey Employees", LIGHT), ("Journey Audiences", LIGHT)]:
    set_text(shape(cover, chip), clr)

# At a glance: charcoal background, four mixed blocks, green stat strip.
set_bg(L["10_text with image"], "accent6")
set_text(shape(glance, None, 17), LIGHT)
blocks = ["Storage", "Content management", "Global delivery and cloud", "Compute and AI"]
for b, clr in zip(blocks, ["accent2", "accent4", "accent3", "accent1"]):
    set_fill(shape(glance, f"Block {b}"), clr)
    set_text(shape(glance, f"Block title {b}"), ON[clr])
    set_text(shape(glance, f"Block text {b}"), ON[clr])
set_fill(shape(glance, "Proof strip"), "accent5")
for s in glance.shapes:
    if s.name.startswith("Stat "):
        set_text(s._element, DARK)

# Untapped (4 rows, charcoal bg): pink, blue, yellow, red.
u = L["14_3 text box"]
for row, (lab, txt), clr in zip(["Rounded Rectangle 2", "Rounded Rectangle 3", "Rounded Rectangle 1", "Rounded Rectangle 4"],
                                [(12, 20), (18, 21), (19, 22), (23, 24)], ["accent2", "accent4", "accent3", "accent1"]):
    set_fill(shape(u, row), clr)
    set_text(shape(u, None, lab), ON[clr])
    set_text(shape(u, None, txt), ON[clr])

# What's next (3 rows): charcoal bg, yellow, pink, blue.
n = L["3_3 text box"]
set_bg(n, "accent6")
set_text(shape(n, None, 16), LIGHT)
set_text(shape(n, None, 23), LIGHT)
for row, (lab, txt), clr in zip(["Rounded Rectangle 2", "Rounded Rectangle 3", "Rounded Rectangle 1"],
                                [(12, 20), (18, 21), (19, 22)], ["accent3", "accent2", "accent4"]):
    set_fill(shape(n, row), clr)
    set_text(shape(n, None, lab), ON[clr])
    set_text(shape(n, None, txt), ON[clr])

# On charcoal, swap the next layout's logo for the light logo from the untapped layout (if both have one).
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
try:
    white = shape(u, "Logo").find(f".//{{{A}}}blip").get(f"{{{R}}}embed")
    rid = n.part.relate_to(u.part.related_part(white), RT.IMAGE)
    shape(n, "Logo").find(f".//{{{A}}}blip").set(f"{{{R}}}embed", rid)
except (KeyError, AttributeError):
    print("no Logo picture shape on both row layouts; logo swap skipped")
try:
    set_text(shape(n, "Slide Number Placeholder"), LIGHT)
except (KeyError, AttributeError):
    pass

p.save(dst)
print("saved", dst)
