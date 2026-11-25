"""Calibrate a Brand pack's PowerPoint export: the `pptxLead` coefficients in brand.json.

PowerPoint and Chrome place text vertically by different rules, and the difference depends on
the face's own metrics, so each pack with font files is calibrated once. See the Engine's
docs/pptx-export.md for the model:

    shift = fs x natural line height x font size - lh x line height - c

Two steps, with real PowerPoint in between:

1. `prepare` builds a probe deck in the Slides skill, exports it to .pptx with its layout plan,
   and writes the pack's fonts as installable TTFs.
2. The maintainer installs those fonts, opens the .pptx in PowerPoint and exports it as PDF.
   On macOS `--powerpoint` asks PowerPoint to do the export.
3. `fit` matches every planned text box to its PDF text span, regresses the baseline error on
   font size and line height, and prints the corrected coefficients (`--write` stores them).

prepare needs the Engine's export dependencies; fit needs pymupdf and fonttools.
"""
import json
import math
import pathlib
import re
import subprocess
import sys

from .common import GenError, need, read_json, write_json, write_text

SIZES = (20, 27, 34, 44, 60, 80, 112)
LEADINGS = (1.0, 1.15, 1.3, 1.5)
WEIGHTS = (400, 700)
PER_SLIDE = 8
MIN_MATCHES = 20
BRAND_CONFIG = re.compile(r"window\.DeckBrand = (\{.*?\});\n")

SKELETON = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PowerPoint calibration</title>
<style>
/*__FONTS__*/
/*__TOKENS__*/
/*__GRADIENTS__*/
/*__VIEWPORT__*/
/*__WIDGETS_CSS__*/
/*__CHROME__*/
.probe {{ position:absolute; margin:0; white-space:nowrap; font-family:var(--font-body); color:var(--text); }}
</style>
</head>
<body>
  <div class="deck-viewport">
    <main class="deck-stage" id="deckStage" data-deck-id="calibration" data-deck-rev="c1"
          data-date="2026-01-15" data-theme="{theme}" data-classification="none" data-header="" lang="en">
      <div class="deck-frame">
        <span class="deck-logo"><!--__LOGO__--></span>
        <span class="deck-date"></span>
        <span class="deck-pagenum"></span>
        <span class="deck-classification"></span>
        <span class="deck-header"></span>
      </div>
{slides}
    </main>
  </div>
<script>
/*__BRAND_CONFIG__*/
/*__WIDGETS_JS__*/
/*__CONTROLLER_JS__*/
/*__CONTRAST_JS__*/
/*__ICONS_JS__*/
/*__EDIT_ICONS_JS__*/
/*__PPTXGEN_JS__*/
/*__PPTX_EXPORT_JS__*/
</script>
</body>
</html>
"""


def probes():
    """[(text, size px, line height, weight)]: every size with every line height, in both weights."""
    out, n = [], 0
    for weight in WEIGHTS:
        for size in SIZES:
            for lead in LEADINGS:
                n += 1
                # Short, so even 112px bold stays one line in its column; the number keeps it unique.
                out.append((f"Hxg {n:02d}", size, lead, weight))
    return out


def template(theme):
    items = probes()
    slides = []
    for start in range(0, len(items), PER_SLIDE):
        rows = []
        for i, (text, size, lead, weight) in enumerate(items[start:start + PER_SLIDE]):
            # Two columns, four rows of 220px: room for 112px at line height 1.5, well apart.
            left, top = 120 + (i % 2) * 860, 110 + (i // 2) * 220
            rows.append(f'        <p class="probe" style="left:{left}px;top:{top}px;font-size:{size}px;'
                        f'line-height:{lead};font-weight:{weight}">{text}</p>')
        # Only text inside .slide-content is editable, and only editable text is exported as text.
        slides.append(f'      <section class="slide" data-theme="{theme}" data-title="Probes '
                      f'{start // PER_SLIDE + 1}">\n      <div class="slide-content" '
                      'style="position:absolute;inset:0;padding:0">\n' + "\n".join(rows)
                      + "\n      </div>\n      </section>")
    return SKELETON.format(theme=theme, slides="\n".join(slides))


def _skill_pack(skill_dir, brand):
    skill = pathlib.Path(skill_dir).resolve()
    deck = skill / "engine" / "deck.py"
    pack = skill / "brands" / brand
    if not deck.is_file():
        raise GenError(f"not a Slides skill (no engine/deck.py): {skill}")
    if not (pack / "brand.json").is_file():
        raise GenError(f"the skill has no Brand pack {brand!r}")
    if not list(pack.glob("fonts/*.woff2")):
        raise GenError(f"Brand pack {brand!r} has no font files, so PowerPoint uses system fonts and "
                       "there is nothing to calibrate")
    return skill, deck, pack


def _run(cmd):
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode:
        raise GenError(f"deck.py {cmd[2]} failed", output=(done.stdout + done.stderr).strip())
    return done.stdout + done.stderr


def prepare(skill_dir, brand, out, powerpoint=False):
    skill, deck, pack = _skill_pack(skill_dir, brand)
    out = pathlib.Path(out).resolve()
    if out == skill or skill in out.parents:
        raise GenError("the calibration files must go outside the skill folder")
    out.mkdir(parents=True, exist_ok=True)
    manifest = read_json(pack / "brand.json")
    write_text(out / "calibration.template.html", template(manifest["defaultTheme"]))
    py = sys.executable
    _run([py, str(deck), "build", "--brand", brand, str(out / "calibration.template.html"),
          str(out / "calibration.html")])
    config = _brand_config(out / "calibration.html")
    if not config.get("pptxNaturalLineHeight"):
        raise GenError("the built deck has no natural line height, so fonttools is missing or the "
                       "fonts are unreadable. Install it with: python3 -m pip install fonttools brotli")
    _run([py, str(deck), "export-pptx", str(out / "calibration.html"), str(out / "calibration.pptx"),
          "--brand", brand, "--fonts", str(out / "fonts"), "--json", str(out / "plan.json")])
    result = {"pack": str(pack), "out": str(out), "probes": len(probes()),
              "written": ["calibration.template.html", "calibration.html", "calibration.pptx",
                          "plan.json", "fonts/"]}
    if powerpoint:
        export_pdf(out / "calibration.pptx", out / "calibration.pdf")
        result["written"].append("calibration.pdf")
        result["next"] = [f"python3 <gen>/tools/gen.py calibrate fit --skill-dir {skill} --brand {brand} "
                          f"--out {out} --write"]
    else:
        result["next"] = [
            f"install every font in {out / 'fonts'} on this machine, then restart PowerPoint",
            f"open {out / 'calibration.pptx'} in PowerPoint and export it as PDF to "
            f"{out / 'calibration.pdf'}",
            f"python3 <gen>/tools/gen.py calibrate fit --skill-dir {skill} --brand {brand} --out {out} --write",
        ]
    return result


def export_pdf(pptx, pdf):
    """Ask Microsoft PowerPoint on macOS to save the .pptx as PDF."""
    if sys.platform != "darwin":
        raise GenError("--powerpoint works only on macOS; export the PDF from PowerPoint by hand")
    # AppleScript's default AppleEvent timeout is two minutes, shorter than a slow PDF save.
    script = f'''
with timeout of 600 seconds
  tell application "Microsoft PowerPoint"
    open POSIX file {json.dumps(str(pptx))}
    set deck to active presentation
    save deck in POSIX file {json.dumps(str(pdf))} as save as PDF
    close deck saving no
  end tell
end timeout'''
    try:
        done = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=660)
    except subprocess.TimeoutExpired:
        raise GenError("PowerPoint did not finish the PDF in 10 minutes; check it for a dialog, or "
                       "export the PDF by hand")
    if done.returncode or not pathlib.Path(pdf).is_file():
        raise GenError("PowerPoint did not export the PDF; export it by hand",
                       output=(done.stdout + done.stderr).strip())


def _brand_config(deck_html):
    hit = BRAND_CONFIG.search(pathlib.Path(deck_html).read_text(encoding="utf-8"))
    if not hit:
        raise GenError(f"{deck_html} has no window.DeckBrand; build it with deck.py build")
    return json.loads(hit.group(1))


def _ascent(pack):
    """The face the build reads the natural line height from: its hhea ascender per em."""
    ttlib = need("fontTools.ttLib", "fonttools brotli")
    for path in sorted((pack / "fonts").glob("*.woff2")):
        try:
            font = ttlib.TTFont(str(path))
            sub = font["name"].getDebugName(2) or ""
            if sub.endswith("Italic"):
                continue
            return font["hhea"].ascender / font["head"].unitsPerEm
        except Exception:
            continue
    raise GenError("no readable upright font in the pack's fonts/")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def rows(plan, pdf_path, ascent, natural):
    """[(natural x size px, line height px, baseline error px)] for every matched text box."""
    fitz = need("fitz", "pymupdf")
    out = []
    doc = fitz.open(str(pdf_path))
    for i, page in enumerate(doc):
        if i >= len(plan):
            break
        spans = [{"t": _norm(s["text"]), "x": s["bbox"][0], "base": s["origin"][1]}
                 for block in page.get_text("dict")["blocks"] for line in block.get("lines", [])
                 for s in line.get("spans", []) if _norm(s["text"])]
        for box in plan[i].get("boxes", []):
            text = _norm("".join(r["text"] for r in box["runs"]))
            found = [s for s in spans if s["t"] == text] or \
                [s for s in spans if s["t"].replace(" ", "") == text.replace(" ", "")]
            if not found:
                continue
            span = min(found, key=lambda s: abs(s["x"] - box["x"]))
            spans.remove(span)
            size = box["fontSize"]                                   # points
            error = (span["base"] - (box["yText"] + ascent * size)) * 2  # stage px
            out.append((natural * size * 2, box["lineSpacing"] * 2, error))
    return out


def _solve(a, b):
    """Gaussian elimination for a small square system."""
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            raise GenError("the probes cannot separate font size from line height; is the PDF from "
                           "this probe deck?")
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [m[i][n] / m[i][i] for i in range(n)]


def fit_rows(data, base):
    """(new pptxLead, residual stats). The error is regressed on [N x F, L, 1]."""
    x = [(nf, lh, 1.0) for nf, lh, _ in data]
    y = [e for _, _, e in data]
    ata = [[sum(r[i] * r[j] for r in x) for j in range(3)] for i in range(3)]
    aty = [sum(r[i] * v for r, v in zip(x, y)) for i in range(3)]
    k = _solve(ata, aty)
    residual = [v - sum(ki * ri for ki, ri in zip(k, r)) for r, v in zip(x, y)]
    mean = sum(residual) / len(residual)
    sd = math.sqrt(sum((r - mean) ** 2 for r in residual) / len(residual))
    lead = [round(base[0] - k[0], 4), round(base[1] + k[1], 4), round(base[2] + k[2], 4)]
    before = max(abs(v) for v in y)
    return lead, {"n": len(data), "meanPx": round(mean, 3), "sdPx": round(sd, 3),
                  "maxPx": round(max(abs(r) for r in residual), 3), "maxBeforePx": round(before, 3)}


def fit(skill_dir, brand, out, write=False):
    _, _, pack = _skill_pack(skill_dir, brand)
    out = pathlib.Path(out).resolve()
    for name in ("calibration.html", "plan.json", "calibration.pdf"):
        if not (out / name).is_file():
            raise GenError(f"{out / name} is missing; run `calibrate prepare` and export the PDF first")
    config = _brand_config(out / "calibration.html")
    natural = config.get("pptxNaturalLineHeight")
    if not natural:
        raise GenError("the probe deck has no natural line height; run `calibrate prepare` again")
    base = config.get("pptxLead") or [0.0, 0.0, 0.0]
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    data = rows(plan, out / "calibration.pdf", _ascent(pack), natural)
    if len(data) < MIN_MATCHES:
        raise GenError(f"only {len(data)} text boxes matched the PDF; export the PDF from "
                       "calibration.pptx with the pack's fonts installed")
    lead, stats = fit_rows(data, base)
    result = {"pack": str(pack), "pptxLead": lead, "base": base, "residual": stats, "written": []}
    if write:
        manifest = read_json(pack / "brand.json")
        manifest["pptxLead"] = lead
        write_json(pack / "brand.json", manifest)
        result["written"].append("brand.json")
    return result
