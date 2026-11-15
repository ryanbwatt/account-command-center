"""Append slides 2-5 (solution overview, UI mock-up, options + pilot, commercial upside) to a VBF slide.

Usage:
  uv run --with python-pptx python build_overview_pptx.py vbf_slide.pptx output.pptx

ILLUSTRATIVE EXAMPLE. Every name and number below is fictional: "Acme Corp" (a made-up maker of
construction-management software) and its "Site Assist" AI assistant, the presenters, the prices and
the seat counts are invented round numbers that show the shape of each slide. For a real account, copy this file to scratch and replace the strings with
sourced content (see ../SKILL.md). Brand comes from build_vbf_pptx.load_brand().
"""
import importlib.util, os, sys
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

SK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_vbf_pptx.py")
sp = importlib.util.spec_from_file_location("vbf", SK)
vbf = importlib.util.module_from_spec(sp)
sp.loader.exec_module(vbf)

NAVY, GREY, LINE, DARK, MUTED, WHITE, EGG = vbf.NAVY, vbf.GREY, vbf.LINE, vbf.DARK, vbf.MUTED, vbf.WHITE, vbf.BG
LIGHT = RGBColor(0xEE, 0xF3, 0xFA)
MID = RGBColor(0x88, 0x88, 0x88)
BAR_TITLE = "ACME CORP x VIDEO PLATFORM: SITE ASSIST SOLUTION OVERVIEW (ILLUSTRATIVE)"
I = Inches


def box(s, x, y, w, h, fill=None, line=LINE, shape=1):
    shp = s.shapes.add_shape(shape, I(x), I(y), I(w), I(h))
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


def P(text, size=10.5, bold=False, color=DARK, title=False, after=3, before=0, align=None):
    return {"runs": [(text, size, bold, color, title)], "after": after, "before": before, "align": align}


def PR(runs, after=3, before=0, align=None):
    return {"runs": runs, "after": after, "before": before, "align": align}


def fill_tf(tf, paras):
    first = True
    for pd in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        for (t, size, bold, color, title) in pd["runs"]:
            r = p.add_run()
            r.text = t
            vbf.set_run(r, size, bold=bold, color=color, title=title)
        p.space_after = Pt(pd["after"])
        p.space_before = Pt(pd["before"])
        if pd["align"]:
            p.alignment = pd["align"]


def T(s, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, margin=0.06):
    tb = s.shapes.add_textbox(I(x), I(y), I(w), I(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = I(margin)
    tf.margin_top = tf.margin_bottom = I(0.03)
    fill_tf(tf, paras)
    return tb


def S(s, x, y, w, h, paras, fill=None, line=LINE, shape=1, anchor=MSO_ANCHOR.MIDDLE, ml=0.08, mr=0.08):
    shp = box(s, x, y, w, h, fill, line, shape)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left, tf.margin_right = I(ml), I(mr)
    tf.margin_top = tf.margin_bottom = I(0.03)
    fill_tf(tf, paras)
    return shp


def panel(s, x, y, w, h, title, hdr_size=12):
    box(s, x, y, w, 0.3, fill=GREY)
    T(s, x, y, w, 0.3, [P(title, hdr_size, True, DARK, True, 0)], anchor=MSO_ANCHOR.MIDDLE)
    box(s, x, y + 0.3, w, h - 0.3, fill=None)


def bullets(items, size=10.5, after=4):
    return [P("• " + t, size, after=after) for t in items]


def frame(prs, bold, rest, footer, notes):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = EGG
    W = 13.333
    box(s, 0, 0, W, 0.5, fill=NAVY, line=None)
    if vbf.LOGO:
        s.shapes.add_picture(vbf.LOGO, I(0.4), I(0.11), height=I(0.28))
    T(s, 0.4, 0.05, 12.53, 0.4, [P(BAR_TITLE, 16, True, WHITE, True, 0, align=PP_ALIGN.CENTER)], anchor=MSO_ANCHOR.MIDDLE)
    T(s, 0.4, 0.58, 12.53, 0.55, [PR([(bold + ": ", 12, True, DARK, True), (rest, 12, False, DARK, False)], 0)])
    T(s, 0.4, 7.12, 12.53, 0.33, [P(footer, 8, color=MUTED, after=0)])
    s.notes_slide.notes_text_frame.text = notes
    return s


def build(src, out):
    prs = Presentation(src)

    # ---------------- Slide 2: solution overview ----------------
    s = frame(
        prs,
        "The solution",
        "Site Assist keeps its sourced answer; the video platform adds the short clip that shows how the task is done",
        "Illustrative example: fictional company, product and figures. Video platform capabilities shown are generic, not an existing Site Assist integration.",
        "ILLUSTRATIVE EXAMPLE: all content is fictional.\n\nSOURCES (what a real deck cites here):\n- The customer's public product pages and help documentation, with the date reviewed\n- The video platform's documentation for search, clip retrieval and in-video Q&A\n\nCAVEAT: Describe only what the public materials show (e.g. 'no playable clips appear in the published answer examples'), not what the product can or cannot do.\n\nVALIDATE WITH CUSTOMER:\n- Whether any current plan already shows video in answers (product owners)\n- Which video sources (manufacturer demos, safety talks, internal training) are approved for use first\n\nHYPOTHESES (not facts): fewer repeat questions, less rework, faster onboarding of new site staff.",
    )
    steps = [
        ("Question from the field", "A supervisor asks how to do or check a task on site"),
        ("Find the sources", "Site Assist searches project documents and manuals"),
        ("Compare and summarize", "Specs, drawings, checklists and manufacturer guides"),
        ("Sourced answer or checklist", "Links back to the page or drawing it came from"),
        ("Confirm and log", "Follow-ups and sign-off recorded on the project"),
    ]
    pills = {2: "Video: manufacturer demos and safety talks", 3: "Video: how-to clips beside the answer", 4: "Video: questions asked inside the clip"}
    for i, (t, sub) in enumerate(steps):
        x = 0.4 + i * 2.52
        S(s, x, 1.22, 2.45, 0.95, [P(t, 11, True, DARK, True, 2), P(sub, 9, color=MUTED, after=0)],
          fill=WHITE, line=LINE, shape=MSO_SHAPE.PENTAGON, ml=0.1, mr=0.3)
        if i in pills:
            S(s, x + 0.05, 2.25, 2.3, 0.42, [P(pills[i], 9, True, WHITE, False, 0, align=PP_ALIGN.CENTER)], fill=NAVY, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    T(s, 0.4, 2.3, 4.9, 0.3, [P("Blue marks where video plugs into the Site Assist workflow", 9, color=MUTED, after=0)])

    cw, gap, cy, ch = 4.04, 0.205, 2.82, 3.2
    cols = [
        ("Where video is missing today", [
            "Published Site Assist answer examples show text, checklists and links to documents",
            "No playable, timestamped clips appear in the public materials reviewed",
            "This describes the published examples only; whether newer plans handle video is a question for the product team",
        ]),
        ("The opportunity", [
            "Knowledge on film: installation demos, toolbox talks and recorded walkthroughs show steps that manuals describe poorly",
            "Shown in place: put the 90-second step in the answer so nobody sits through a 40-minute recording on a phone",
            "Example: the answer lists the pre-pour checks; a short clip shows a foreman doing each one, with the transcript one tap away",
        ]),
        ("What the video platform contributes", [
            "Search across a video library that returns playable clips, captions and on-screen text",
            "In-video Q&A: follow-up questions answered from the captioned video, with timestamps",
            "Source links: thumbnails, timestamps, and links to the related manual page",
            "Optional voice mode: hands-free questions over the same sources",
        ]),
    ]
    for i, (h, items) in enumerate(cols):
        x = 0.4 + i * (cw + gap)
        panel(s, x, cy, cw, ch, h)
        T(s, x, cy + 0.34, cw, ch - 0.38, bullets(items, 10.5, 5))
    S(s, 0.4, 6.12, 12.53, 0.9, [
        PR([("Design principles: ", 10.5, True, NAVY, True),
            ("keep Site Assist's sourced answer and add a small \"Watch how it's done\" section. Each clip shows title, presenter, date, length and start time. Demonstration video stays labeled apart from the governing specification. Video appears when useful and stays optional.", 10.5, False, DARK, False)], 0)],
      fill=WHITE, line=NAVY, anchor=MSO_ANCHOR.MIDDLE, ml=0.15, mr=0.15)

    # ---------------- Slide 3: mock-up ----------------
    s = frame(
        prs,
        "What the user sees",
        "Two experiences: how-to clips beside a sourced answer, and follow-up questions inside a selected clip",
        "Illustrative mock-up. Company, product, content, presenters, dates and timestamps are fictional; the controls do not play media.",
        "ILLUSTRATIVE EXAMPLE: all content on this slide is fictional. Build a clickable version before showing it to a customer.\n\nNOTES:\n- Experience A = search results rendered as a compact section under the sourced answer. Experience B = in-video Q&A with timestamp references.\n\nVALIDATE WITH CUSTOMER:\n- How the customer's engineers prefer to integrate on each product surface (API, MCP or embedded widget)\n- Whether clips render in the customer's own UI (Options 1 and 2) or in a vendor-provided widget (Option 3)",
    )
    panel(s, 0.4, 1.2, 7.2, 5.05, "Experience A: how-to clips beside a sourced answer")
    S(s, 0.55, 1.62, 6.9, 0.42, [P("What should the crew check before pouring the level 2 slab in cold weather?", 10, False, DARK, False, 0)], fill=LIGHT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    T(s, 0.55, 2.1, 6.9, 1.5, [P("Sourced answer", 10, True, NAVY, True, 2)] + bullets([
        "Confirm the concrete temperature requirement in the project specification [1]",
        "Check that insulating blankets and heaters are staged before the truck arrives [2]",
        "Record air and surface temperatures on the pour checklist [3]",
    ], 10, 3))
    box(s, 0.55, 3.72, 0.06, 0.25, fill=NAVY, line=None)
    T(s, 0.65, 3.69, 6.8, 0.3, [PR([("Watch how it's done", 10.5, True, NAVY, True), ("   from the video library, optional", 9, False, MUTED, False)], 0)])
    cards = [
        ("Cold-weather pour checklist", "2:10", "Sam Rivera, Foreman (fictional)", "Toolbox talk recording", "Starts 06:15 | Relevance: high"),
        ("Setting up curing blankets", "3:30", "Alex Chen, Supplier rep (fictional)", "Manufacturer demo", "Starts 01:40 | Relevance: medium"),
        ("Logging temperatures on site", "1:45", "Jordan Lee, Trainer (fictional)", "New-hire training", "Starts 09:00 | Relevance: medium"),
    ]
    for i, (t, dur, who, src, start) in enumerate(cards):
        x = 0.55 + i * 2.33
        box(s, x, 4.05, 2.28, 1.82, fill=WHITE)
        box(s, x + 0.07, 4.12, 2.14, 0.72, fill=DARK, line=None)
        tri = box(s, x + 0.98, 4.33, 0.26, 0.3, fill=WHITE, line=None, shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
        tri.rotation = 90
        T(s, x + 1.5, 4.6, 0.7, 0.22, [P(dur, 8, True, WHITE, False, 0, align=PP_ALIGN.RIGHT)])
        T(s, x + 0.03, 4.87, 2.22, 0.36, [P(t, 9, True, DARK, True, 0)])
        T(s, x + 0.03, 5.2, 2.22, 0.66, [P(who, 8, color=MUTED, after=0), P(src, 8, color=MUTED, after=0), P(start, 8, True, NAVY, False, 0)])
    S(s, 0.55, 5.93, 4.0, 0.26, [P("Demonstration video, labeled apart from the spec", 8.5, True, NAVY, False, 0, align=PP_ALIGN.CENTER)], fill=LIGHT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    S(s, 4.65, 5.93, 2.8, 0.26, [P("Transcript and context one tap away", 8.5, True, NAVY, False, 0, align=PP_ALIGN.CENTER)], fill=LIGHT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE)

    panel(s, 7.85, 1.2, 5.08, 5.05, "Experience B: follow-up questions inside a clip")
    T(s, 8.0, 1.6, 4.8, 0.3, [PR([("Setting up curing blankets", 10, True, DARK, True), ("  (fictional demo)", 9, False, MUTED, False)], 0)])
    box(s, 8.0, 1.92, 4.78, 1.55, fill=DARK, line=None)
    tri = box(s, 10.27, 2.28, 0.3, 0.36, fill=WHITE, line=None, shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
    tri.rotation = 90
    T(s, 8.1, 3.03, 2.0, 0.22, [P("01:40 / 12:00", 8.5, False, WHITE, False, 0)])
    box(s, 8.15, 3.3, 4.48, 0.04, fill=MID, line=None)
    box(s, 8.15, 3.3, 0.62, 0.04, fill=NAVY, line=None)
    box(s, 8.72, 3.25, 0.14, 0.14, fill=NAVY, line=WHITE, shape=MSO_SHAPE.OVAL)
    S(s, 9.0, 3.6, 3.78, 0.42, [P("How long do the blankets stay on?", 9.5, False, DARK, False, 0)], fill=GREY, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    box(s, 8.0, 4.12, 4.78, 1.4, fill=WHITE)
    T(s, 8.08, 4.16, 4.6, 1.0, [P("AI answer", 9, True, NAVY, True, 2),
                                P("The presenter says to follow the duration in the project specification and to leave the blankets in place until the site lead signs off.", 9.5, after=0)])
    for j, ts in enumerate(["01:40", "04:05"]):
        S(s, 8.13 + j * 0.7, 5.15, 0.62, 0.26, [P(ts, 8.5, True, WHITE, False, 0, align=PP_ALIGN.CENTER)], fill=NAVY, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    T(s, 9.6, 5.15, 3.1, 0.26, [P("Answered from the captioned video", 8.5, color=MUTED, after=0)], anchor=MSO_ANCHOR.MIDDLE)
    S(s, 8.0, 5.68, 4.78, 0.4, [P("Ask a question about this video...", 9.5, False, MUTED, False, 0)], fill=WHITE, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    S(s, 0.4, 6.4, 12.53, 0.62, [
        PR([("Measured in a pilot, not by views: ", 10.5, True, NAVY, True),
            ("answers with and without clips, compared on repeat questions, time to a confirmed answer, rework reports and user ratings.", 10.5, False, DARK, False)], 0)],
      fill=WHITE, line=NAVY, ml=0.15, mr=0.15)

    # ---------------- Slide 4: how we get there ----------------
    s = frame(
        prs,
        "How we get there",
        "Three ways to add video to Site Assist, from lightest to fullest, tested with one pilot crew before any wider rollout",
        "Illustrative example: fictional company and product.",
        "ILLUSTRATIVE EXAMPLE: all content is fictional.\n\nSOURCES (what a real deck cites here): the meeting where the options were discussed, any planning document the customer shared, and the vendor's availability status for each option.\n\nCAVEATS:\n- Mark which options are available today and which are planned.\n- 'Customer provides' lines are an assumed split of work; confirm with the customer's engineers.\n- No dates on this slide unless a source commits either side to one.\n\nVALIDATE WITH CUSTOMER:\n- Sponsor: which option to aim for, and who attends the kickoff session\n- Product team: which workflow to pilot; who owns the budget\n\nGAPS:\n- Baselines for the pilot measures are not set\n- Sign-in approach for the embedded option is open",
    )
    opts = [
        ("Option 1: RAG-only", "Lightest, available today", [
            ("Vendor provides", "Captions, timestamps and source links through a search API"),
            ("Customer provides", "The model that writes the answer, plus its own clip player and access rules"),
            ("User gets", "A text answer that links to the right moment in a video"),
        ]),
        ("Option 2: Packaged clips", "Agent-to-agent / MCP", [
            ("Vendor provides", "Ready-to-play clips that respect each user's access, with captions"),
            ("Customer provides", "A call to the vendor from the Site Assist flow, and a place for clips beside the answer"),
            ("User gets", "A sourced answer with clips they can play in place"),
        ]),
        ("Option 3: Full AI video answers (goal)", "Fullest, most work", [
            ("Vendor provides", "Answers, clips and summaries, plus an embeddable in-video Q&A widget"),
            ("Customer provides", "The screen it sits in, sign-in and menu placement"),
            ("User gets", "Ask in Site Assist; get clips and a summary, and keep asking inside the clip"),
        ]),
    ]
    cw, gap = 4.04, 0.205
    for i, (h, sub, rows) in enumerate(opts):
        x = 0.4 + i * (cw + gap)
        panel(s, x, 1.2, cw, 3.3, h)
        paras = [P(sub, 9.5, True, NAVY, True, 4)]
        for lab, txt in rows:
            paras.append(P(lab, 10, True, DARK, True, 1, before=2))
            paras.append(P(txt, 10, after=3))
        T(s, x, 1.54, cw, 2.94, paras)

    box(s, 0.4, 4.6, 12.53, 0.28, fill=GREY)
    T(s, 0.4, 4.6, 12.53, 0.28, [P("Work plan", 12, True, DARK, True, 0)], anchor=MSO_ANCHOR.MIDDLE)
    plan = [
        ("1  Kick off", "Half-day session with the product team; agree who funds the pilot"),
        ("2  Inventory", "List existing video; match it to the ten most-asked site questions"),
        ("3  Choose", "Pick one workflow and one crew; agree the integration approach"),
        ("4  Pilot", "Run answers with and without clips for the same crew"),
        ("5  Review", "Compare against the baseline; decide which option to build"),
    ]
    for i, (t, sub) in enumerate(plan):
        x = 0.4 + i * 2.52
        S(s, x, 4.95, 2.45, 0.85, [P(t, 10.5, True, NAVY, True, 1), P(sub, 8.5, after=0)], fill=WHITE, line=LINE, shape=MSO_SHAPE.PENTAGON, ml=0.1, mr=0.28)

    box(s, 0.4, 5.9, 12.53, 0.28, fill=GREY)
    T(s, 0.4, 5.9, 12.53, 0.28, [P("What the pilot measures", 12, True, DARK, True, 0)], anchor=MSO_ANCHOR.MIDDLE)
    vis = [
        ("Speed", "Time from question to a confirmed answer, with and without clips"),
        ("Quality", "Repeat questions and rework reports on the piloted workflow"),
        ("Adoption", "Share of answers where a clip is opened, and user ratings"),
    ]
    for i, (t, sub) in enumerate(vis):
        x = 0.4 + i * (cw + gap)
        box(s, x, 6.2, cw, 0.82, fill=WHITE)
        T(s, x, 6.22, cw, 0.8, [PR([(t + ": ", 10, True, NAVY, True), (sub, 10, False, DARK, False)], 0)])

    # ---------------- Slide 5: commercial upside ----------------
    s = frame(
        prs,
        "Commercial upside",
        "Site Assist is sold per seat; a video add-on gives Acme a higher-priced plan, and platform usage rises as crews adopt it",
        "Illustrative example: every figure on this slide is an invented round number. Scenario arithmetic, not a forecast: attach rates and the add-on price are assumptions.",
        "ILLUSTRATIVE EXAMPLE: all figures are invented round numbers.\n\nMATH (annual pool = 40,000 seats x attach x monthly price x 12):\n- 5%: $240K / $360K / $480K at $10 / $15 / $20\n- 10%: $480K / $720K / $960K\n- 20%: $960K / $1.44M / $1.92M\n- Each 1 point of vendor share at $15 = $3.6K / $7.2K / $14.4K per year at 5% / 10% / 20% attach\n- Add-on as a share of list: $120-240 per seat per year = 20-40% on Standard ($600), 10-20% on Pro ($1,200)\n\nWATCH-OUTS (pattern for a real deck):\n- Compare the add-on price with the customer's existing plan prices; an add-on that costs nearly as much as the plan will not sell.\n- Licensed seats are not all active users; attach rates are scenario inputs, not evidence.\n- Vendor share is a placeholder until a commercial model is discussed.",
    )
    panel(s, 0.4, 1.2, 3.85, 4.25, "Why Site Assist matters to Acme")
    tiles = [("40K", "licensed seats across contractors (example)"),
             ("60%", "of seats are field staff on mobile (example)"),
             ("$30M", "annual subscription revenue (example)")]
    for i, (big, cap) in enumerate(tiles):
        y = 1.58 + i * 0.86
        T(s, 0.45, y, 1.35, 0.78, [P(big, 24, True, NAVY, True, 0)], anchor=MSO_ANCHOR.MIDDLE)
        T(s, 1.8, y, 2.4, 0.78, [P(cap, 9.5, after=0)], anchor=MSO_ANCHOR.MIDDLE)
    T(s, 0.45, 4.2, 3.75, 1.2, [P("List price per seat per year (example)", 9.5, True, NAVY, True, 2),
                                P("Standard $600  |  Pro $1,200", 9.5, after=0)])

    panel(s, 4.45, 1.2, 4.2, 4.25, "Acme monetization levers")
    T(s, 4.45, 1.54, 4.2, 3.9, bullets([
        "Video add-on, roughly $10-20 per seat per month, priced to cover video processing cost",
        "Or a usage charge per video question above a monthly allowance",
        "Safety: find the moment in a recorded toolbox talk where a procedure was covered",
        "Onboarding: new site staff learn tasks from short clips instead of full courses",
        "Retention: features people can see demonstrated are features they keep using",
    ], 10.5, 5))

    panel(s, 8.85, 1.2, 4.08, 4.25, "Illustrative annual add-on pool")
    rows = [["Attach of 40K seats", "$10/mo", "$15/mo", "$20/mo"],
            ["5% (2,000)", "$240K", "$360K", "$480K"],
            ["10% (4,000)", "$480K", "$720K", "$960K"],
            ["20% (8,000)", "$960K", "$1.44M", "$1.92M"]]
    tbl = s.shapes.add_table(4, 4, I(8.95), I(1.62), I(3.88), I(1.6)).table
    tbl.columns[0].width = I(1.48)
    for c in (1, 2, 3):
        tbl.columns[c].width = I(0.8)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if r == 0 else (WHITE if r % 2 else LIGHT)
            tf = cell.text_frame
            tf.word_wrap = True
            cell.margin_left = cell.margin_right = I(0.05)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
            run = p.add_run()
            run.text = val
            vbf.set_run(run, 9.5 if r == 0 else 10.5, bold=(r == 0 or c == 0), color=WHITE if r == 0 else DARK, title=(r == 0))
    T(s, 8.85, 3.35, 4.08, 2.05, [
        P("Vendor share", 10, True, NAVY, True, 2),
        P("Each 1 point of share of the pool is about $3.6K, $7.2K and $14.4K a year at the 5%, 10% and 20% attach cases ($15 mid-price).", 10, after=4),
        P("The add-on would add roughly 20-40% to Standard and 10-20% to Pro list price.", 10, after=0)])

    box(s, 0.4, 5.55, 12.53, 0.28, fill=GREY)
    T(s, 0.4, 5.55, 12.53, 0.28, [P("Video platform upside", 12, True, DARK, True, 0)], anchor=MSO_ANCHOR.MIDDLE)
    ups = [
        ("Usage grows with adoption", "Plays, stored video and AI questions rise as more crews use Site Assist; usage-based agreements rise with them"),
        ("A second buyer", "Brings in the product team that owns Site Assist, alongside the training team that buys video today"),
        ("Part of the daily tool", "Video sits where site staff already work rather than in a separate training site, which supports renewal"),
    ]
    for i, (t, sub) in enumerate(ups):
        x = 0.4 + i * (cw + gap)
        box(s, x, 5.85, cw, 1.2, fill=WHITE)
        T(s, x, 5.88, cw, 1.15, [P(t, 10.5, True, NAVY, True, 2), P(sub, 10, after=0)])

    prs.save(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2])
    print(sys.argv[2])
