"""The Sample deck: one neutral deck, built for any Brand pack.

It shows the pack's themes, the Engine's base layouts, the pack's own layouts, the widgets, the
icons when the pack has them, and the classification and footer. The same deck serves brand
approval, CI and Upgrade, so its text is neutral and its date and revision are fixed.
"""
import html as htmllib
import itertools
import pathlib
import re

from . import build, layouts, packs
from .common import ENGINE, DeckError, ensure_outside_skill

SAMPLE = ENGINE / "sample"
SECTION = re.compile(r"<section\b.*?</section>", re.S)
LAYOUT_ID = re.compile(r'\bdata-layout="([^"]+)"')
ROADMAP_CSS = re.compile(r"## Roadmap toolkit CSS\s+```css\n(.*?)```", re.S)
SAMPLE_DATE = "2026-01-15"
EMBED = ("data:text/html,%3Cbody style='margin:0;display:grid;place-items:center;height:100vh;"
         "font:600 28px sans-serif;background:%23F2F2F2;color:%23333'%3EAn embedded page%3C/body%3E")

SKELETON = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sample deck: {name}</title>
<style>
/*__FONTS__*/
/*__TOKENS__*/
/*__GRADIENTS__*/
/*__VIEWPORT__*/
/*__WIDGETS_CSS__*/
/*__CHROME__*/
{css}
</style>
</head>
<body>
<!-- key-terms
- Sample deck: the Engine's neutral deck, built for any Brand pack.
-->
  <div class="deck-viewport">
    <main class="deck-stage" id="deckStage" data-deck-id="sample-{slug}" data-deck-rev="sample-1"
          data-date="{date}" data-theme="{theme}" data-classification="{classification}"
          data-header="Sample deck" lang="en">
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
{script}
</script>
</body>
</html>
"""

# Fills the icon slide from the pack's own library, whatever way the library was generated.
ICON_SCRIPT = """(function () {
  var grid = document.querySelector('[data-sample-icons]');
  if (!grid || grid.children.length || !window.DeckIcons) return;
  var names = Object.keys(window.DeckIcons).slice(0, 24);
  grid.innerHTML = names.map(function (name) {
    var icon = window.DeckIcons[name];
    return '<svg class="deck-icon" viewBox="' + icon.vb + '" fill="currentColor" aria-hidden="true">' +
      icon.inner + '</svg>';
  }).join('');
})();"""


def _esc(text):
    return htmllib.escape(str(text), quote=True)


def _base_sections():
    """{layout id: section markup} from the Engine's sample slides."""
    text = (SAMPLE / "slides.html").read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    found = {}
    for section in SECTION.findall(text):
        hit = LAYOUT_ID.search(section)
        if hit:
            found[hit.group(1)] = section
    missing = [i for i in layouts.base_ids() if i not in found]
    if missing:
        raise DeckError(f"engine/sample/slides.html has no slide for: {', '.join(missing)}")
    return found


def _theme_slide(theme):
    label = _esc(theme["label"])
    return f"""<section class="slide" data-theme="{_esc(theme['value'])}" data-sample="theme" data-title="Theme: {label}">
  <div class="slide-content center">
    <div class="stack-tight"><span class="sample-kicker">Colour theme</span><h2 class="sample-title">{label}</h2></div>
    <p class="sample-body">Body text stays readable on this background.</p>
    <p class="sample-muted">Muted text is for captions and supporting lines.</p>
    <div class="sample-swatches">
      <span class="sample-swatch sample-swatch--surface">Surface</span>
      <span class="sample-swatch sample-swatch--accent">Accent</span>
      <span class="sample-swatch sample-swatch--text">Text</span>
    </div>
  </div>
</section>"""


def _widget_slides(theme_a, theme_b):
    charts = f"""<section class="slide" data-theme="{theme_a}" data-sample="widgets" data-title="Widgets: charts">
  <div class="slide-content center">
    <h2 class="sample-title">Charts and counters</h2>
    <div class="sample-widgets">
      <div class="chart-bars" style="height:520px">
        <div class="bar" data-value="35" data-max="100" style="--bar-color:var(--series-1)"><span class="value">35</span><div class="fill"></div><span class="label">North</span></div>
        <div class="bar" data-value="60" data-max="100" style="--bar-color:var(--series-2)"><span class="value">60</span><div class="fill"></div><span class="label">South</span></div>
        <div class="bar" data-value="80" data-max="100" style="--bar-color:var(--series-3)"><span class="value">80</span><div class="fill"></div><span class="label">East</span></div>
        <div class="bar" data-value="50" data-max="100" style="--bar-color:var(--series-4)"><span class="value">50</span><div class="fill"></div><span class="label">West</span></div>
      </div>
      <div class="sample-stack">
        <div class="chart-donut" data-percent="68" style="width:300px;height:300px"><span class="pct" style="font-size:var(--fs-h2)">68%</span></div>
        <span class="counter-stat" data-to="1234" data-suffix=" items" style="font-size:var(--fs-h1)">0</span>
      </div>
    </div>
  </div>
</section>"""
    interactive = f"""<section class="slide" data-theme="{theme_b}" data-sample="widgets" data-title="Widgets: interactive">
  <div class="slide-content center">
    <h2 class="sample-title">Toggles, steps and embeds</h2>
    <div class="sample-widgets" style="align-items:start">
      <div class="sample-stack">
        <div class="toggle-group" role="tablist">
          <button role="tab" aria-selected="true" aria-controls="sample-plan-a">Plan A</button>
          <button role="tab" aria-selected="false" aria-controls="sample-plan-b">Plan B</button>
        </div>
        <div style="font-size:var(--fs-body);color:var(--text)">
          <div class="toggle-panel active" id="sample-plan-a">Plan A keeps the current process.</div>
          <div class="toggle-panel" id="sample-plan-b">Plan B moves it to one team.</div>
        </div>
        <ul class="sample-steps">
          <li data-step>A point that appears first</li>
          <li data-step>A point that appears next</li>
        </ul>
      </div>
      <iframe class="embed-frame sample-embed" title="An embedded page" data-src="{EMBED}"></iframe>
    </div>
  </div>
</section>"""
    return [charts, interactive]


def _icon_slide(theme):
    return f"""<section class="slide" data-theme="{theme}" data-sample="icons" data-title="Icons">
  <div class="slide-content center">
    <h2 class="sample-title">Icon library</h2>
    <div class="sample-icons" data-sample-icons></div>
  </div>
</section>"""


def _frame_slide(theme, manifest):
    pills = "".join(
        f'<span class="sample-pill{" sample-pill--default" if c == manifest["defaultClassification"] else ""}">{_esc(c)}</span>'
        for c in manifest["classifications"])
    return f"""<section class="slide" data-theme="{theme}" data-sample="frame" data-title="Classification and footer">
  <div class="slide-content center">
    <h2 class="sample-title">Classification and footer</h2>
    <p class="sample-body">The label at the top right is the pack's default. The logo, date and page number sit in the footer of every slide.</p>
    <div class="sample-pills">{pills}</div>
  </div>
</section>"""


def _fill_themes(section, hero, light):
    if "{{hero}}" in section:
        section = section.replace("{{hero}}", _esc(next(hero)))
    if "{{light}}" in section:
        section = section.replace("{{light}}", _esc(next(light)))
    return section


def template(pack):
    """The Sample deck's template for this pack, before the build fills its markers."""
    manifest = pack.manifest
    themes = manifest["themes"]
    values = [t["value"] for t in themes]
    heroes = [t["value"] for t in themes if t.get("hero")] or values
    lights = [t["value"] for t in themes if not t.get("hero")] or values
    hero, light = itertools.cycle(heroes), itertools.cycle(lights)

    base = _base_sections()
    slides = [_fill_themes(base["cover"], hero, light)]
    slides += [_theme_slide(t) for t in themes]
    for layout_id in layouts.base_ids():
        if layout_id not in ("cover", "closing"):
            slides.append(_fill_themes(base[layout_id], hero, light))
    for layout_id in layouts.own_ids(pack):
        section = layouts.html(pack, layout_id)
        if "data-layout=" not in section.split(">", 1)[0]:
            section = section.replace("<section", f'<section data-layout="{layout_id}"', 1)
        if "data-theme=" not in section.split(">", 1)[0]:
            section = section.replace("<section", f'<section data-theme="{_esc(next(light))}"', 1)
        slides.append(section)
    slides += _widget_slides(_esc(next(light)), _esc(next(light)))
    has_icons = bool(pack.optional("icon-library.js"))
    if has_icons:
        slides.append(_icon_slide(_esc(next(light))))
    slides.append(_frame_slide(_esc(next(light)), manifest))
    slides.append(_fill_themes(base["closing"], hero, light))

    roadmap = ROADMAP_CSS.search((ENGINE / "docs" / "roadmaps.md").read_text(encoding="utf-8"))
    if not roadmap:
        raise DeckError("engine/docs/roadmaps.md has no Roadmap toolkit CSS block")
    css = roadmap.group(1) + (SAMPLE / "sample.css").read_text(encoding="utf-8")
    return SKELETON.format(name=_esc(manifest["name"]), css=css, slug=_esc(pack.slug), date=SAMPLE_DATE,
                           theme=_esc(manifest["defaultTheme"]),
                           classification=_esc(manifest["defaultClassification"]),
                           slides="\n".join(slides), script=ICON_SCRIPT if has_icons else "")


def run(brand, out=None, open_after=False, template_only=False):
    pack = packs.load(brand)
    suffix = ".template.html" if template_only else ".html"
    target = pathlib.Path(out) if out else pathlib.Path.cwd() / f"{brand}-sample{suffix}"
    ensure_outside_skill(target, "the Sample deck")
    text = template(pack)
    if template_only:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"Wrote {target}: the Sample deck's template for Brand pack '{brand}'.")
        return
    build.build_text(pack, text, target.name, target, open_after, deck_type="none")
