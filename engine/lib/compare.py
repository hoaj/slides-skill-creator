"""Compare one Brand pack's Sample deck on two Engines.

    deck.py compare <old-engine> <new-engine> --brand <slug> [--out <dir>] [--json]

Both Engines run in this one command, on this machine and with this Chrome, and no reference
image is stored. The deck is the OLD Engine's Sample deck, built by both Engines, so a slide the
new Engine adds to its Sample deck is not reported as a regression.

| Format | Compared | Tolerance |
|---|---|---|
| HTML, each slide in its end state | Pixels | At most 0.01% of pixels differ by more than 2/255 |
| HTML | Text boxes | At most 0.5 px |
| PDF | Page count and pixels | Same count, same pixel limit |
| PowerPoint | Text | Exact |
| PowerPoint | Position, size, colour | 1 pt, 0.6 pt, 8/255 |
| PowerPoint | Background image | Same pixel limit |

"Size" is the font size of each run. A text box's left, top, width and height are positions.

Exit 0 for no difference, 1 for a difference, 2 when the comparison could not run. Images and
the report are written only to --out. The printed summary names only the brand, the slide and
the measured difference: never slide text, file paths or image data.
"""
import html as htmllib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

from . import packs
from .common import DeckError, ensure_outside_skill

PIXEL_CHANNEL_TOLERANCE = 2             # out of 255
PIXEL_RATIO_LIMIT = 0.0001              # 0.01% of a slide's pixels
TEXT_BOX_TOLERANCE_PX = 0.5
PPTX_POSITION_TOLERANCE_PT = 1.0
PPTX_SIZE_TOLERANCE_PT = 0.6
PPTX_COLOUR_TOLERANCE = 8               # out of 255
EMU_PER_PT = 12700
PICTURE = 13                            # MSO_SHAPE_TYPE.PICTURE
INSTALL = "python3 -m pip install playwright python-pptx pymupdf numpy pillow"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".git")

SETTLE_CSS = (".deck-chrome{display:none!important}"
              "*,*::before,*::after{transition:none!important;animation:none!important}")
PREPARE_JS = """() => {
  const count = DeckWidgets._count.bind(DeckWidgets);
  DeckWidgets._count = el => count(el, true);
}"""
SHOW_SLIDE_JS = """async i => {
  deck.go(i);
  const slide = deck.slides[i];
  slide.querySelectorAll('[data-step]').forEach(el => el.classList.add('step-shown'));
  DeckWidgets.activate(slide, { instant: true });
  if (window.DeckContrast) DeckContrast.guard(slide, deck.stage);
  await Promise.all(Array.from(slide.querySelectorAll('iframe')).map(f => new Promise(done => {
    if (f.dataset.sampleLoaded) return done();
    f.dataset.sampleLoaded = '1';
    f.addEventListener('load', done, { once: true });
    setTimeout(done, 1500);
  })));
  await document.fonts.ready;
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
}"""
TEXT_BOXES_JS = """i => {
  const boxes = [];
  const roots = [deck.slides[i], document.querySelector('.deck-stage > .deck-frame')];
  roots.forEach(root => {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.nodeValue.trim()) continue;
      const parent = node.parentElement;
      if (!parent || parent.closest('script,style')) continue;
      const css = getComputedStyle(parent);
      if (css.display === 'none' || css.visibility === 'hidden') continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const r = range.getBoundingClientRect();
      if (!r.width && !r.height) continue;
      boxes.push({ text: node.nodeValue.trim(), x: r.x, y: r.y, w: r.width, h: r.height });
    }
  });
  return boxes;
}"""


class Difference:
    """One measured difference. It holds no slide text."""

    def __init__(self, slide, kind, measured, limit):
        self.slide, self.kind, self.measured, self.limit = slide, kind, measured, limit

    def as_dict(self):
        return {"slide": self.slide, "check": self.kind, "measured": self.measured, "limit": self.limit}

    def __str__(self):
        where = f"slide {self.slide}" if self.slide else "deck"
        return f"{where}: {self.kind}: {self.measured} (limit {self.limit})"


def _need_modules():
    missing = []
    for module in ("numpy", "PIL", "fitz", "pptx", "playwright"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        raise DeckError(f"compare needs {', '.join(missing)}. Install with: {INSTALL}")


def find_engine(value):
    path = pathlib.Path(value).resolve()
    if (path / "deck.py").is_file():
        return path
    if (path / "engine" / "deck.py").is_file():
        return path / "engine"
    raise DeckError(f"no Engine at {value}: expected a folder that holds deck.py or engine/deck.py")


def stage(engine, pack_root, slug, dest):
    """A private Slides skill: this Engine with the one Brand pack under test."""
    skill = dest / "skill"
    target = skill / "engine"
    shutil.copytree(str(engine), str(target), ignore=IGNORE)
    if slug == packs.HIDDEN_PACK:
        fixture = target / "fixtures" / packs.HIDDEN_PACK
        if fixture.exists():
            shutil.rmtree(str(fixture))
        shutil.copytree(str(pack_root), str(fixture), ignore=IGNORE)
        (skill / "brands").mkdir()
    else:
        shutil.copytree(str(pack_root), str(skill / "brands" / slug), ignore=IGNORE)
    return target / "deck.py"


def _tool(deck_py, label, *args):
    cmd = [sys.executable, str(deck_py), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(deck_py.parent.parent.parent))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise DeckError(f"{label}: `deck.py {args[0]}` failed: {detail[-1] if detail else 'no output'}")
    return result


# --- measuring ----------------------------------------------------------------------------

def pixel_difference(a, b):
    """(share of pixels that differ by more than the channel tolerance, largest difference)."""
    import numpy as np
    if a.shape != b.shape:
        return 1.0, 255
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    largest = int(delta.max()) if delta.size else 0
    differing = int((delta > PIXEL_CHANNEL_TOLERANCE).any(axis=2).sum())
    return differing / float(a.shape[0] * a.shape[1]), largest


def _over(value, limit):
    """value > limit, without counting floating-point noise at exactly the limit."""
    return value > limit + 1e-9


def pixels_over_limit(share):
    return share > PIXEL_RATIO_LIMIT


def _pixels_entry(slide, kind, a, b):
    share, largest = pixel_difference(a, b)
    if not pixels_over_limit(share):
        return None
    size = "" if a.shape == b.shape else f", image size {a.shape[1]}x{a.shape[0]} vs {b.shape[1]}x{b.shape[0]}"
    return Difference(slide, kind, f"{share * 100:.4f}% of pixels differ, by up to {largest}/255{size}",
                      f"{PIXEL_RATIO_LIMIT * 100:.2f}% over {PIXEL_CHANNEL_TOLERANCE}/255")


def text_box_differences(slide, old, new):
    """Text boxes in two renders of one slide, compared in order."""
    if len(old) != len(new):
        return [Difference(slide, "HTML text boxes", f"{len(old)} vs {len(new)} boxes", "same count")]
    worst, changed = 0.0, 0
    for a, b in zip(old, new):
        if a["text"] != b["text"]:
            changed += 1
        worst = max(worst, abs(a["x"] - b["x"]), abs(a["y"] - b["y"]),
                    abs(a["w"] - b["w"]), abs(a["h"] - b["h"]))
    out = []
    if changed:
        out.append(Difference(slide, "HTML text", f"{changed} text box(es) differ", "exact"))
    if _over(worst, TEXT_BOX_TOLERANCE_PX):
        out.append(Difference(slide, "HTML text boxes", f"moved or resized by {worst:.2f} px",
                              f"{TEXT_BOX_TOLERANCE_PX} px"))
    return out


def _rgb(run):
    try:
        value = run.font.color.rgb
    except AttributeError:
        return None
    return tuple(value) if value is not None else None


def read_pptx(path):
    """Per slide: the background PNG bytes and each text box's measurable values."""
    from pptx import Presentation
    slides = []
    for slide in Presentation(str(path)).slides:
        picture, boxes = None, []
        for shape in slide.shapes:
            if shape.shape_type == PICTURE and picture is None:
                picture = shape.image.blob
            elif shape.has_text_frame:
                runs = []
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        size = run.font.size.pt if run.font.size is not None else None
                        runs.append({"text": run.text, "size": size, "colour": _rgb(run),
                                     "font": run.font.name, "bold": bool(run.font.bold),
                                     "italic": bool(run.font.italic)})
                boxes.append({"text": shape.text_frame.text, "runs": runs,
                              "left": shape.left / EMU_PER_PT, "top": shape.top / EMU_PER_PT,
                              "width": shape.width / EMU_PER_PT, "height": shape.height / EMU_PER_PT})
        slides.append({"picture": picture, "boxes": boxes})
    return slides


def pptx_differences(slide, old, new):
    """The PowerPoint checks on one slide's text layer."""
    if len(old) != len(new):
        return [Difference(slide, "PowerPoint text", f"{len(old)} vs {len(new)} text boxes", "exact")]
    moved = sized = coloured = 0.0
    text_changed = styled = 0
    for a, b in zip(old, new):
        if a["text"] != b["text"] or [r["text"] for r in a["runs"]] != [r["text"] for r in b["runs"]]:
            text_changed += 1
            continue
        for key in ("left", "top", "width", "height"):
            moved = max(moved, abs(a[key] - b[key]))
        for ra, rb in zip(a["runs"], b["runs"]):
            if (ra["font"], ra["bold"], ra["italic"]) != (rb["font"], rb["bold"], rb["italic"]):
                styled += 1
            if ra["size"] is not None and rb["size"] is not None:
                sized = max(sized, abs(ra["size"] - rb["size"]))
            elif ra["size"] != rb["size"]:
                sized = max(sized, float("inf"))
            if ra["colour"] and rb["colour"]:
                coloured = max(coloured, max(abs(x - y) for x, y in zip(ra["colour"], rb["colour"])))
            elif ra["colour"] != rb["colour"]:
                coloured = 255
    out = []
    if text_changed:
        out.append(Difference(slide, "PowerPoint text", f"{text_changed} text box(es) differ", "exact"))
    if styled:
        out.append(Difference(slide, "PowerPoint text style", f"{styled} run(s) changed font or weight", "exact"))
    if _over(moved, PPTX_POSITION_TOLERANCE_PT):
        out.append(Difference(slide, "PowerPoint position", f"moved or resized by {moved:.2f} pt",
                              f"{PPTX_POSITION_TOLERANCE_PT} pt"))
    if _over(sized, PPTX_SIZE_TOLERANCE_PT):
        out.append(Difference(slide, "PowerPoint size", f"font size differs by {sized:.2f} pt",
                              f"{PPTX_SIZE_TOLERANCE_PT} pt"))
    if coloured > PPTX_COLOUR_TOLERANCE:
        out.append(Difference(slide, "PowerPoint colour", f"colour differs by {int(coloured)}/255",
                              f"{PPTX_COLOUR_TOLERANCE}/255"))
    return out


def _png_array(data):
    import numpy as np
    from PIL import Image
    return np.array(Image.open(io.BytesIO(data)).convert("RGB"))


def render_deck(browser, deck):
    """(slide PNG bytes, text boxes per slide, PDF bytes) for one built deck."""
    context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(pathlib.Path(deck).resolve().as_uri())
    page.wait_for_function("() => window.deck && window.DeckContrast && window.DeckWidgets")
    page.evaluate("() => document.fonts.ready")
    page.add_style_tag(content=SETTLE_CSS)
    page.evaluate(PREPARE_JS)
    pngs, boxes = [], []
    for i in range(page.evaluate("() => deck.slides.length")):
        page.evaluate(SHOW_SLIDE_JS, i)
        pngs.append(page.screenshot())
        boxes.append(page.evaluate(TEXT_BOXES_JS, i))
    page.evaluate("() => { deck.go(0); deck._pdfPrep(); }")
    page.emulate_media(media="print")
    page.wait_for_timeout(300)
    pdf = page.pdf(prefer_css_page_size=True, print_background=True)
    context.close()
    if errors:
        raise DeckError(f"the deck threw {len(errors)} script error(s) in Chrome")
    return pngs, boxes, pdf


def pdf_pages(pdf):
    """Each PDF page as an RGB array at the stage's 1920x1080."""
    import fitz
    import numpy as np
    out = []
    with fitz.open(stream=pdf, filetype="pdf") as document:
        for page in document:
            zoom = 1920 / page.rect.width
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            out.append(np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy())
    return out


# --- the report -----------------------------------------------------------------------------

class Report:
    """Writes before, after and difference images, only to the --out folder."""

    def __init__(self, out):
        self.out = pathlib.Path(out) if out else None
        self.images = []
        if self.out:
            ensure_outside_skill(self.out, "the comparison report")
            (self.out / "images").mkdir(parents=True, exist_ok=True)

    def add(self, name, slide, old, new):
        if not self.out:
            return
        import numpy as np
        from PIL import Image
        stem = f"{name}-slide-{slide:03d}"
        Image.fromarray(old).save(self.out / "images" / f"{stem}-before.png")
        Image.fromarray(new).save(self.out / "images" / f"{stem}-after.png")
        if old.shape == new.shape:
            mask = (np.abs(old.astype(np.int16) - new.astype(np.int16)) > PIXEL_CHANNEL_TOLERANCE).any(axis=2)
            shown = (old * 0.25 + 170).astype(np.uint8)
            shown[mask] = (220, 20, 60)
            Image.fromarray(shown).save(self.out / "images" / f"{stem}-diff.png")
        self.images.append((name, slide, stem, old.shape == new.shape))

    def finish(self, summary):
        if not self.out:
            return
        (self.out / "report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        rows = "".join(
            f"<tr><td>{d['slide'] or 'deck'}</td><td>{htmllib.escape(d['check'])}</td>"
            f"<td>{htmllib.escape(d['measured'])}</td><td>{htmllib.escape(d['limit'])}</td></tr>"
            for d in summary["differences"]) or '<tr><td colspan="4">No difference.</td></tr>'
        figures = ""
        for name, slide, stem, has_diff in self.images:
            cells = [("Before", f"{stem}-before.png"), ("After", f"{stem}-after.png")]
            if has_diff:
                cells.append(("Difference", f"{stem}-diff.png"))
            imgs = "".join(f'<figure><figcaption>{label}</figcaption><img src="images/{src}" alt="{label}">'
                           "</figure>" for label, src in cells)
            figures += f"<h2>{htmllib.escape(name)}, slide {slide}</h2><div class=row>{imgs}</div>"
        (self.out / "report.html").write_text(
            "<!doctype html><meta charset=utf-8><title>Engine comparison</title><style>"
            "body{font:16px system-ui,sans-serif;margin:24px}table{border-collapse:collapse}"
            "td,th{border:1px solid #bbb;padding:6px 10px;text-align:left}"
            ".row{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}"
            "img{width:100%;border:1px solid #ccc}figure{margin:0}</style>"
            f"<h1>Engine comparison: {htmllib.escape(summary['brand'])}</h1>"
            f"<p>{htmllib.escape(summary['result'])}</p>"
            "<table><tr><th>Slide</th><th>Check</th><th>Measured</th><th>Limit</th></tr>"
            f"{rows}</table>{figures}", encoding="utf-8")


# --- the comparison -------------------------------------------------------------------------

def compare_decks(old_html, new_html, old_pptx, new_pptx, report):
    """Every check in the tolerance table, as a list of Difference."""
    from playwright.sync_api import sync_playwright
    from .pptx_export import _launch

    with sync_playwright() as pw:
        browser = _launch(pw)
        try:
            old_pngs, old_boxes, old_pdf = render_deck(browser, old_html)
            new_pngs, new_boxes, new_pdf = render_deck(browser, new_html)
        finally:
            browser.close()

    out = []
    if len(old_pngs) != len(new_pngs):
        out.append(Difference(0, "HTML slide count", f"{len(old_pngs)} vs {len(new_pngs)}", "same count"))
    for i, (a, b) in enumerate(zip(old_pngs, new_pngs), 1):
        old_img, new_img = _png_array(a), _png_array(b)
        entry = _pixels_entry(i, "HTML pixels", old_img, new_img)
        if entry:
            out.append(entry)
            report.add("html", i, old_img, new_img)
    for i, (a, b) in enumerate(zip(old_boxes, new_boxes), 1):
        out += text_box_differences(i, a, b)

    old_pages, new_pages = pdf_pages(old_pdf), pdf_pages(new_pdf)
    if len(old_pages) != len(new_pages):
        out.append(Difference(0, "PDF page count", f"{len(old_pages)} vs {len(new_pages)}", "same count"))
    for i, (a, b) in enumerate(zip(old_pages, new_pages), 1):
        entry = _pixels_entry(i, "PDF pixels", a, b)
        if entry:
            out.append(entry)
            report.add("pdf", i, a, b)

    old_slides, new_slides = read_pptx(old_pptx), read_pptx(new_pptx)
    if len(old_slides) != len(new_slides):
        out.append(Difference(0, "PowerPoint slide count", f"{len(old_slides)} vs {len(new_slides)}", "same count"))
    for i, (a, b) in enumerate(zip(old_slides, new_slides), 1):
        out += pptx_differences(i, a["boxes"], b["boxes"])
        if a["picture"] and b["picture"]:
            if a["picture"] != b["picture"]:
                old_img, new_img = _png_array(a["picture"]), _png_array(b["picture"])
                entry = _pixels_entry(i, "PowerPoint background", old_img, new_img)
                if entry:
                    out.append(entry)
                    report.add("pptx", i, old_img, new_img)
        elif a["picture"] or b["picture"]:
            out.append(Difference(i, "PowerPoint background", "image present in only one export", "same"))
    return out, len(old_pngs)


def run(args):
    _need_modules()
    old_engine, new_engine = find_engine(args.old_engine), find_engine(args.new_engine)
    pack = packs.read(args.brand)
    report = Report(args.out)
    with tempfile.TemporaryDirectory(prefix="deck-compare-") as tmp:
        work = pathlib.Path(tmp).resolve()
        (work / "old").mkdir()
        (work / "new").mkdir()
        (work / "out").mkdir()
        old_py = stage(old_engine, pack.root, args.brand, work / "old")
        new_py = stage(new_engine, pack.root, args.brand, work / "new")

        template = work / "out" / "sample.template.html"
        _tool(old_py, "old Engine", "sample", "--brand", args.brand, str(template), "--template-only")
        decks = {}
        for label, deck_py in (("old", old_py), ("new", new_py)):
            html = work / "out" / f"{label}.html"
            pptx = work / "out" / f"{label}.pptx"
            _tool(deck_py, f"{label} Engine", "build", "--brand", args.brand, str(template), str(html))
            _tool(deck_py, f"{label} Engine", "export-pptx", str(html), str(pptx), "--scale", "1")
            decks[label] = (html, pptx)
        found, slides = compare_decks(decks["old"][0], decks["new"][0], decks["old"][1], decks["new"][1], report)

    same = not found
    result = (f"{args.brand}: no difference across {slides} slides" if same else
              f"{args.brand}: {len(found)} difference(s) across {slides} slides")
    summary = {"brand": args.brand, "same": same, "slides": slides, "result": result,
               "differences": [d.as_dict() for d in found]}
    report.finish(summary)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(result)
        for difference in found:
            print(f"  {difference}")
    return 0 if same else 1
