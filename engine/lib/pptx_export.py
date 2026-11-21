"""Export a built deck to .pptx with a rendered background and live text.

Each slide becomes one PowerPoint page:

  * a full-bleed PNG of the slide rendered by Chrome with the editable text made
    invisible, so gradients, icons, chart widgets and every CSS effect land exactly, and
  * one native text box per editable text element, placed and styled from the browser's
    own measurements, so the text is still selectable, searchable and editable.

"Editable text" means what it means in the deck's edit mode. The measurement and layout
live in runtime/pptx-export.js, the code the deck's own Export button runs, so the button
and this command cannot drift apart. A 1920x1080 stage maps onto PowerPoint's 16:9 slide
(960x540pt) at exactly 2 px per pt.

Needs playwright and python-pptx, plus fonttools and brotli for --fonts. Uses the
installed Chrome, or Playwright's Chromium.
"""
import json
import pathlib
import sys

from . import packs
from .common import RUNTIME, DeckError, ensure_outside_skill

SLIDE_W_EMU, SLIDE_H_EMU = 12192000, 6858000
EMU_PER_PT = 12700
INSTALL = "python3 -m pip install playwright python-pptx"


def _launch(pw):
    try:
        return pw.chromium.launch(channel="chrome")
    except Exception:
        pass
    try:
        return pw.chromium.launch()
    except Exception as e:
        raise DeckError("no browser for the export. Install Google Chrome, or run: "
                        f"python3 -m playwright install chromium ({e})")


def measure_and_render(deck_html, png_dir, scale=2, render=True):
    """(layout plan, text-free PNG per slide, whether the deck has a PowerPoint calibration)."""
    from playwright.sync_api import sync_playwright

    png_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = _launch(pw)
        page = browser.new_page(viewport={"width": 1920, "height": 1080},
                                device_scale_factor=scale)
        page.goto(deck_html.resolve().as_uri())
        # Print media is where every slide is laid out at exactly 1920x1080, stacked and
        # untransformed; _pdfPrep puts build-steps and widgets into their end state.
        page.emulate_media(media="print")
        page.evaluate("() => { if (window.deck && window.deck._pdfPrep) window.deck._pdfPrep(); }")
        page.wait_for_timeout(300)                      # webfonts and widgets settle
        try:
            page.evaluate("() => document.fonts.ready")
        except Exception:
            pass

        if not page.evaluate("() => !!window.DeckPPTX"):
            page.add_script_tag(content=(RUNTIME / "pptx-export.js").read_text(encoding="utf-8"))
        slides = page.evaluate("() => window.DeckPPTX.plan()")
        calibrated = page.evaluate("() => !!(window.DeckBrand && window.DeckBrand.pptxLead"
                                   " && window.DeckBrand.pptxNaturalLineHeight)")
        # The runtime owns this rule; read it back rather than keeping a copy in sync.
        page.add_style_tag(content=page.evaluate("() => window.DeckPPTX.HIDE_CSS"))
        page.wait_for_timeout(60)

        pngs = []
        for i, el in enumerate(page.query_selector_all(".slide") if render else []):
            out = png_dir / f"slide{i + 1:03d}.png"
            el.screenshot(path=str(out))
            pngs.append(out)
        browser.close()
    return slides, pngs, calibrated


def build(deck_html, out_pptx, image_only=False, scale=2, work=None):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
    from pptx.util import Emu, Pt

    work = work or out_pptx.parent / (out_pptx.stem + ".slides")
    layout, pngs, calibrated = measure_and_render(deck_html, work, scale)

    align = {"left": PP_ALIGN.LEFT, "right": PP_ALIGN.RIGHT,
             "center": PP_ALIGN.CENTER, "justify": PP_ALIGN.JUSTIFY}

    def set_paragraph(p, box):
        p.alignment = align.get(box["align"], PP_ALIGN.LEFT)
        p.line_spacing = Pt(box["lineSpacing"])
        p.space_before = p.space_after = Pt(0)

    def emu(pt):
        return Emu(int(round(pt * EMU_PER_PT)))

    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(SLIDE_W_EMU), Emu(SLIDE_H_EMU)
    blank = prs.slide_layouts[6]                        # no placeholders

    n_text = 0
    for meta, png in zip(layout, pngs):
        s = prs.slides.add_slide(blank)
        s.shapes.add_picture(str(png), 0, 0, width=Emu(SLIDE_W_EMU), height=Emu(SLIDE_H_EMU))
        if image_only:
            continue
        for b in meta["boxes"]:
            box = s.shapes.add_textbox(emu(b["x"]), emu(b["y"]), emu(b["w"]), emu(b["h"]))
            box.rotation = b.get("rotate", 0)
            tf = box.text_frame
            tf.word_wrap = False
            tf.auto_size = MSO_AUTO_SIZE.NONE
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            p = tf.paragraphs[0]
            set_paragraph(p, b)
            for rn in b["runs"]:
                o = rn["options"]
                r = p.add_run()
                r.text = rn["text"]
                r.font.name = o["fontFace"]
                r.font.size = Pt(o["fontSize"])
                r.font.bold, r.font.italic = bool(o["bold"]), bool(o["italic"])
                r.font.color.rgb = RGBColor.from_string(o["color"])
                if o.get("charSpacing"):
                    r.font._rPr.set("spc", str(int(round(o["charSpacing"] * 100))))
                if o.get("breakLine"):
                    p = tf.add_paragraph()
                    set_paragraph(p, b)
            n_text += 1

    out_pptx.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_pptx))
    return len(layout), n_text, work, layout, calibrated


def font_files(pack):
    return sorted(pack.path("fonts").glob("*.woff2")) if pack.path("fonts").is_dir() else []


def export_fonts(pack, dest):
    """woff2 to installable TTF, so PowerPoint can render the live text in the brand face."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        raise DeckError("--fonts needs fonttools and brotli. Install them with: "
                        "python3 -m pip install fonttools brotli")
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for p in font_files(pack):
        font = TTFont(p)
        font.flavor = None
        out = dest / (p.stem + ".ttf")
        font.save(out)
        written.append(out)
    return written


def run(args):
    try:
        import playwright  # noqa: F401
        import pptx  # noqa: F401
    except ImportError:
        raise DeckError(f"export-pptx needs playwright and python-pptx. Install them with: {INSTALL}\n"
                        "Then, unless Google Chrome is installed: python3 -m playwright install chromium")
    deck, out = pathlib.Path(args.deck), pathlib.Path(args.out)
    if not deck.is_file():
        raise DeckError(f"deck not found: {deck}")
    ensure_outside_skill(out, "the .pptx")
    work = out.parent / (out.stem + ".slides")
    ensure_outside_skill(work, "the slide renders")
    pack = None
    if args.fonts:
        if not args.brand:
            raise DeckError("--fonts needs --brand <slug>")
        ensure_outside_skill(args.fonts, "exported fonts")
        pack = packs.load(args.brand)
        if not font_files(pack):
            raise DeckError(f"Brand pack '{pack.slug}' has no font files to export")
    if args.json:
        ensure_outside_skill(args.json, "the layout plan")

    n, boxes, work, layout, calibrated = build(deck, out, args.image_only, args.scale, work)
    print(f"Wrote {out}: {n} slides, {boxes} live text boxes, backgrounds in {work}/")
    if not calibrated and not args.image_only:
        print("warning: this deck has no PowerPoint calibration (pptxLead), so no vertical "
              "correction was applied", file=sys.stderr)
    if pack:
        got = export_fonts(pack, pathlib.Path(args.fonts))
        print(f"Wrote {len(got)} TTFs to {args.fonts}: install them so PowerPoint renders "
              "the text layer in the brand face.")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(layout, indent=2), encoding="utf-8")
        print(f"Wrote the layout plan to {args.json}")
