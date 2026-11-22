"""Assemble one self-contained deck from a template, the runtime and one Brand pack.

The template holds these marker comments, replaced in place:

    /*__FONTS__*/        /*__TOKENS__*/       /*__GRADIENTS__*/
    /*__VIEWPORT__*/     /*__WIDGETS_CSS__*/  /*__CHROME__*/
    /*__BRAND_CONFIG__*/ /*__WIDGETS_JS__*/   /*__CONTROLLER_JS__*/
    /*__PPTXGEN_JS__*/   /*__PPTX_EXPORT_JS__*/
    /*__CONTRAST_JS__*/  /*__ICONS_JS__*/     /*__EDIT_ICONS_JS__*/
    <!--__LOGO__-->      (inside <span class="deck-logo"> in the .deck-frame block)

Put the CSS markers inside one <style>, in that order, and the JS markers inside one
<script> before </body>, with /*__BRAND_CONFIG__*/ first. See docs/html-template.md.
"""
import json
import re
import sys

from . import packs, textchecks
from .common import RUNTIME, DeckError, display, ensure_outside_skill

# An inlined SVG's XML prolog means nothing inside an HTML document.
XML_PROLOG = re.compile(r"^\s*<\?xml[^>]*\?>\s*")
STAGE_OR_SLIDE = re.compile(r"<(?:main|section)\b[^>]*>", re.S)
THEME_ATTR = re.compile(r'\bdata-theme="([^"]*)"')
CLASSIFICATION_ATTR = re.compile(r'\bdata-classification="([^"]*)"')
FRAME = re.compile(r'class="[^"]*\bdeck-frame\b[^"]*"')

RUNTIME_MARKERS = {
    "/*__VIEWPORT__*/": "viewport-base.css",
    "/*__WIDGETS_CSS__*/": "widgets.css",
    "/*__CHROME__*/": "chrome.css",
    "/*__WIDGETS_JS__*/": "widgets.js",
    "/*__CONTROLLER_JS__*/": "deck-controller.js",
    "/*__CONTRAST_JS__*/": "contrast-guard.js",
    "/*__EDIT_ICONS_JS__*/": "edit-icons.js",
    "/*__PPTXGEN_JS__*/": "pptxgen.bundle.js",
    "/*__PPTX_EXPORT_JS__*/": "pptx-export.js",
}


def pptx_font_facts(pack, html=""):
    """Everything the PowerPoint export needs to know about a pack's font files.

    Returns (weight -> {name, bold}, natural line height, missing codepoints).

    * PowerPoint has only bold and italic flags, so a weight that is neither 400 nor 700
      must be addressed by its own family name, and the CSS family is not necessarily the
      font's real one.
    * The natural line height excludes hhea lineGap, because Chrome's em box does.
    * Missing codepoints are the non-ASCII characters this deck uses that no face in the
      pack can draw, taken from the cmaps. A width comparison gives false positives.

    Needs fontTools, and only for a pack with font files.
    """
    files = sorted(pack.path("fonts").glob("*.woff2")) if pack.path("fonts").is_dir() else []
    if not files:
        return {}, None, []
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print("warning: fonttools is not installed, so PowerPoint export cannot map this "
              "pack's font weights. Install it with: python3 -m pip install fonttools brotli",
              file=sys.stderr)
        return {}, None, []
    standard = {"Regular": (False, False), "Bold": (True, False),
                "Italic": (False, True), "Bold Italic": (True, True)}
    fonts, natural, covered = {}, None, set()
    for p in files:
        try:
            ft = TTFont(p)
            family, sub = ft["name"].getDebugName(1), ft["name"].getDebugName(2)
            weight = ft["OS/2"].usWeightClass
            hhea, upem = ft["hhea"], ft["head"].unitsPerEm
            covered |= set(ft.getBestCmap())
        except Exception:
            continue
        bold, italic = standard.get(sub, (False, sub.endswith("Italic")))
        if italic:
            continue                      # the map is keyed by weight; italic uses the flag
        fonts[str(weight)] = {"name": family if sub in standard
                              else f"{family} {sub}".replace(" Italic", "").strip(),
                              "bold": bold}
        if natural is None:
            natural = round((hhea.ascender - hhea.descender) / upem, 4)
    used = {ord(c) for c in html if ord(c) > 0x7F}
    return fonts, natural, sorted(used - covered) if covered else []


def brand_config_js(pack, html=""):
    """The window.DeckBrand script: the only brand data the runtime reads."""
    m = pack.manifest
    cfg = {
        "slug": m["slug"],
        "name": m["name"],
        "defaultTheme": m["defaultTheme"],
        "themes": [{"value": t["value"], "label": t["label"]} for t in m["themes"]],
        "bloomThemes": [t["value"] for t in m["themes"] if t.get("bloom")],
        "classifications": m["classifications"],
        "defaultClassification": m["defaultClassification"],
        "guard": m["guard"],
    }
    if m.get("numberFormat"):
        cfg["numberFormat"] = m["numberFormat"]
    if m.get("pptxLead"):
        cfg["pptxLead"] = m["pptxLead"]
    fonts, natural, missing = pptx_font_facts(pack, html)
    if fonts:
        cfg["pptxFonts"] = fonts
    if natural:
        cfg["pptxNaturalLineHeight"] = natural
    elif m.get("pptxLead"):
        print(f"warning: {display(pack.path('brand.json'))}: pptxLead needs the pack's font "
              "files and fonttools, so PowerPoint export applies no vertical correction",
              file=sys.stderr)
    if missing:
        cfg["pptxMissingGlyphs"] = missing
    # "<" is escaped so no value can close the surrounding <script>.
    payload = json.dumps(cfg, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    return "window.DeckBrand = " + payload + ";\n"


def _check_template(html, template, pack):
    m = pack.manifest
    name = display(template)
    if not FRAME.search(html):
        raise DeckError(f'{name}: no <div class="deck-frame"> block. See engine/docs/html-template.md')
    themes = {t["value"] for t in m["themes"]}
    for tag in STAGE_OR_SLIDE.findall(html):
        theme = THEME_ATTR.search(tag)
        if theme and theme.group(1) not in themes:
            raise DeckError(f"{name}: data-theme=\"{theme.group(1)}\" is not a theme of Brand "
                            f"pack '{pack.slug}'. Themes: {', '.join(sorted(themes))}")
        label = CLASSIFICATION_ATTR.search(tag)
        if label and label.group(1) not in m["classifications"]:
            raise DeckError(f"{name}: data-classification=\"{label.group(1)}\" is not a label of "
                            f"Brand pack '{pack.slug}'. Labels: {', '.join(m['classifications'])}")


def _inline(path):
    return XML_PROLOG.sub("", path.read_text(encoding="utf-8"))


def assemble(pack, template_text):
    """(finished HTML, number of inlined files)."""
    replacements = {marker: _inline(RUNTIME / name) for marker, name in RUNTIME_MARKERS.items()}
    replacements["/*__TOKENS__*/"] = _inline(pack.path("tokens.css"))
    replacements["<!--__LOGO__-->"] = _inline(pack.path(pack.manifest["logo"]))
    inlined = len(replacements)
    for marker, parts in (("/*__FONTS__*/", ("fonts.css",)),
                          ("/*__GRADIENTS__*/", ("assets", "gradients.css")),
                          ("/*__ICONS_JS__*/", ("icon-library.js",))):
        optional = pack.optional(*parts)
        replacements[marker] = _inline(optional) if optional else ""
        inlined += 1 if optional else 0
    replacements["/*__BRAND_CONFIG__*/"] = brand_config_js(pack, template_text)

    missing = [marker for marker in replacements if marker not in template_text]
    if missing:
        raise DeckError("template is missing markers: " + ", ".join(sorted(missing)))
    # One pass, so a marker-like string inside an inlined file is left alone.
    pattern = re.compile("|".join(re.escape(marker) for marker in replacements))
    return pattern.sub(lambda hit: replacements[hit.group(0)], template_text), inlined


def run(brand, template, out, open_after=False):
    ensure_outside_skill(out, "the built deck")
    pack = packs.load(brand)
    if not template.is_file():
        raise DeckError(f"template not found: {template}")
    template_text = template.read_text(encoding="utf-8")
    _check_template(template_text, template, pack)
    html, inlined = assemble(pack, template_text)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} ({len(html):,} bytes), Brand pack '{brand}', {inlined} files inlined.",
          flush=True)
    for warning in packs.warnings(pack):
        print(f"warning: {warning}", file=sys.stderr)
    for kind, warning in textchecks.text_warnings(template_text, pack.manifest):
        print(f"{kind}: {warning}", file=sys.stderr)
    if open_after:
        from . import open_deck
        print(open_deck.open_deck(out))
