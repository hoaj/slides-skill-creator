"""The one Brand pack validator, used by `deck.py check` and by every command that uses a pack.

It stops on a missing required file or field, a `formatVersion` other than the Engine's,
contrast data that does not match `tokens.css`, a theme below WCAG AA (4.5:1) without a named
exception, and a broken layout or Playbook. It warns on what still works: a missing PowerPoint
calibration, a missing icon library, and rules that name an unknown question id or layout.

Every problem names its file, its field and how to fix it.
"""
import pathlib
import re

from . import csstokens, layouts, playbook
from .common import RUNTIME, display

FORMAT_VERSION = 1
UPGRADE_COMMAND = "python3 <skill>/engine/deck.py upgrade"
RETIRED_FIELDS = ("files", "logoWidthPx", "fontFamily", "storePrefix")
GUARD_LISTS = ("neutrals", "vivids")
GUARD_NAMES = ("lightNeutral", "darkNeutral")
GUARD_MAPS = ("themeBg", "themeText")
CONTRAST_PAIRS = ("body", "muted", "on-accent")
CONTRAST_MINIMUM = 4.5
CSS_VAR_USE = re.compile(r"var\(\s*(--[\w-]+)\s*\)")
CSS_VAR_DECLARED = re.compile(r"(?:^|[;{\s])(--[\w-]+)\s*:")
GUIDE = "See the Brand pack format in engine/docs/brand-pack.md."


class Problem:
    """One thing wrong with a pack, with where it is and how to fix it."""

    def __init__(self, file, where, problem, fix):
        self.file, self.where, self.problem, self.fix = file, where, problem, fix

    def __str__(self):
        where = f" {self.where}" if self.where else ""
        return f"{self.file}:{where} {self.problem} Fix: {self.fix}"


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, file, where, problem, fix):
        self.errors.append(Problem(file, where, problem, fix))

    def warn(self, file, where, problem, fix):
        self.warnings.append(Problem(file, where, problem, fix))

    def has_error_on(self, *prefixes):
        return any(p.where.startswith(prefix) for p in self.errors for prefix in prefixes)


def required_tokens():
    """Custom properties the runtime CSS reads with no fallback and does not set itself."""
    used, declared = set(), set()
    for css in sorted(RUNTIME.glob("*.css")):
        text = csstokens.strip_comments(css.read_text(encoding="utf-8"))
        used |= set(CSS_VAR_USE.findall(text))
        declared |= set(CSS_VAR_DECLARED.findall(text))
    return sorted(used - declared)


def validate(pack):
    """The pack's Report. A wrong formatVersion ends it: other rules assume the format."""
    report = Report()
    _check_format(pack, report)
    if report.errors:
        return report
    _check_manifest(pack, report)
    _check_files(pack, report)
    themes = _theme_values(pack)
    if pack.path("tokens.css").is_file() and not report.has_error_on("field 'themes"):
        _check_tokens(pack, report)
        if not report.has_error_on("field 'guard", "field 'themes", "token", "theme"):
            _check_contrast(pack, report)
    for file, where, problem, fix in layouts.problems(pack, themes):
        report.error(file, where, problem, fix)
    found = playbook.check(pack)
    for file, where, problem, fix in found.errors:
        report.error(file, where, problem, fix)
    for file, where, problem, fix in found.warnings:
        report.warn(file, where, problem, fix)
    _add_warnings(pack, report)
    return report


def _theme_values(pack):
    themes = pack.manifest.get("themes")
    if not isinstance(themes, list):
        return []
    return [t["value"] for t in themes if isinstance(t, dict) and isinstance(t.get("value"), str)]


def _add_warnings(pack, report):
    name = display(pack.path("brand.json"))
    if not pack.manifest.get("pptxLead"):
        report.warn(name, "field 'pptxLead'",
                    "is missing: no pptxLead, so PowerPoint export applies no vertical correction.",
                    "Calibrate it with the Generator's brand tools.")
    if not pack.optional("icon-library.js"):
        report.warn(display(pack.root), "",
                    "has no icon-library.js, so the icon picker is hidden.",
                    "Add icon-library.js and icons.md, or leave them out on purpose.")
    elif not pack.optional("icons.md"):
        report.warn(display(pack.path("icons.md")), "", "is missing, so an agent has no guide to the icons.",
                    "Add icons.md next to icon-library.js.")


def _check_format(pack, report):
    version = pack.manifest.get("formatVersion")
    if version == FORMAT_VERSION and type(version) is int:
        return
    state = "is missing" if version is None else f"is {version!r}"
    report.error(display(pack.path("brand.json")), "field 'formatVersion'",
                 f"{state}, and this Engine supports exactly {FORMAT_VERSION}.",
                 f"Migrate the pack with: {UPGRADE_COMMAND}")


def _check_manifest(pack, report):
    m = pack.manifest
    name = display(pack.path("brand.json"))

    def err(field, problem, fix):
        report.error(name, f"field '{field}'", problem, fix)

    for field in RETIRED_FIELDS:
        if field in m:
            err(field, "is no longer part of the format.", "Remove it.")
    for field in ("slug", "name", "logo", "defaultTheme", "defaultClassification"):
        if not (isinstance(m.get(field), str) and m[field].strip()):
            err(field, "is missing or not a text value.", f"Set '{field}' to a text value.")
    if isinstance(m.get("slug"), str) and m["slug"] != pack.root.name:
        err("slug", f"is '{m['slug']}' but the pack's folder is '{pack.root.name}'.",
            "Make the slug and the folder name the same.")
    if not (isinstance(m.get("aliases"), list)
            and all(isinstance(a, str) and a.strip() for a in m["aliases"])):
        err("aliases", "is missing or not a list of text values.",
            "Use a list such as [\"other name\"], or [] for none.")

    values = _check_themes(m, err)
    if values and m.get("defaultTheme") not in values:
        err("defaultTheme", f"is '{m.get('defaultTheme')}', which is not one of the themes.",
            f"Use one of: {', '.join(values)}.")

    labels = m.get("classifications")
    if not (isinstance(labels, list) and labels
            and all(isinstance(c, str) and c.strip() for c in labels)):
        err("classifications", "is missing or not a list of labels.",
            "Set a list of labels, for example [\"INTERNAL\", \"PUBLIC\", \"none\"].")
    elif "defaultClassification" in m and m["defaultClassification"] not in labels:
        err("defaultClassification",
            f"is '{m['defaultClassification']}', which is not one of the classifications.",
            f"Use one of: {', '.join(labels)}.")

    _check_fonts(pack, err)
    lead = m.get("pptxLead")
    if lead is not None and not (isinstance(lead, list) and len(lead) == 3 and all(
            isinstance(n, (int, float)) and not isinstance(n, bool) for n in lead)):
        err("pptxLead", "must be a list of three numbers.", "Use [fs, lh, c], or remove the field.")
    _check_number_format(m, err)
    _check_guard(m.get("guard"), values, err)
    _check_exceptions(m, values, err)


def _check_fonts(pack, err):
    fonts = pack.manifest.get("fonts")
    if not isinstance(fonts, list):
        err("fonts", "is missing or not a list (use [] for system fonts).",
            "Set 'fonts' to a list of font files, or [].")
        return
    for i, entry in enumerate(fonts):
        file = entry.get("file") if isinstance(entry, dict) else entry
        if not (isinstance(file, str) and file.strip()):
            err(f"fonts[{i}]", "must be a path, or an object with a 'file' path.",
                "Use an entry such as {\"file\": \"fonts/name.woff2\"}.")
        elif not _safe_relative(file):
            err(f"fonts[{i}]", "must be a path inside the pack.", "Use a path such as fonts/name.woff2.")
        elif not pack.path(file).is_file():
            err(f"fonts[{i}]", f"names '{file}', which does not exist.",
                "Add the font file or remove the entry.")


def _check_number_format(m, err):
    nf = m.get("numberFormat")
    if nf is None:
        return
    fix = "Use an object such as {\"thousands\": \".\", \"decimal\": \",\"}, or remove the field."
    if not (isinstance(nf, dict) and nf):
        err("numberFormat", "must be an object with 'thousands' and 'decimal'.", fix)
        return
    for key in nf:
        if key not in ("thousands", "decimal"):
            err(f"numberFormat.{key}", "is not a known field.", fix)
    thousands, decimal = nf.get("thousands"), nf.get("decimal")
    if "thousands" in nf and not (isinstance(thousands, str) and len(thousands) <= 1):
        err("numberFormat.thousands", "must be one character, or empty for no grouping.", fix)
    if "decimal" in nf and not (isinstance(decimal, str) and len(decimal) == 1):
        err("numberFormat.decimal", "must be one character.", fix)
    if isinstance(thousands, str) and thousands and thousands == decimal:
        err("numberFormat", f"uses '{thousands}' for both thousands and decimal.", fix)


def _check_themes(m, err):
    themes = m.get("themes")
    if not (isinstance(themes, list) and themes):
        err("themes", "is missing or empty.", "List at least one theme with 'value' and 'label'.")
        return []
    values = []
    for i, theme in enumerate(themes):
        if not isinstance(theme, dict):
            err(f"themes[{i}]", "must be an object.", "Use {\"value\": \"...\", \"label\": \"...\"}.")
            continue
        for key in ("value", "label"):
            if not (isinstance(theme.get(key), str) and theme[key].strip()):
                err(f"themes[{i}].{key}", "is missing or not a text value.", f"Set '{key}'.")
        for key in ("hero", "bloom"):
            if key in theme and not isinstance(theme[key], bool):
                err(f"themes[{i}].{key}", "must be true or false.", f"Set '{key}' to true or false.")
        value = theme.get("value")
        if isinstance(value, str) and value:
            if value in values:
                err(f"themes[{i}].value", f"repeats '{value}'.", "Give each theme its own value.")
            values.append(value)
    return values


def _names_colour(palette, name):
    return isinstance(name, str) and name in palette


def _check_guard(guard, themes, err):
    regen = "Regenerate the guard data from tokens.css with the Generator's brand tools."
    if not isinstance(guard, dict):
        err("guard", "is missing or not an object.", regen)
        return
    palette = guard.get("palette")
    if not (isinstance(palette, dict) and palette):
        err("guard.palette", "is missing or empty.", regen)
        palette = {}
    for colour, rgb in palette.items():
        if not (isinstance(rgb, list) and len(rgb) == 3 and all(
                isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in rgb)):
            err(f"guard.palette.{colour}", "must be three integers from 0 to 255.", regen)
    for key in GUARD_LISTS:
        names = guard.get(key)
        if not isinstance(names, list):
            err(f"guard.{key}", "is missing or not a list.", regen)
            continue
        for n in names:
            if palette and not _names_colour(palette, n):
                err(f"guard.{key}", f"names '{n}', which is not in guard.palette.", regen)
    for key in GUARD_NAMES:
        if key not in guard:
            err(f"guard.{key}", "is missing.", regen)
        elif palette and not _names_colour(palette, guard[key]):
            err(f"guard.{key}", f"names '{guard[key]}', which is not in guard.palette.", regen)
    for key in GUARD_MAPS:
        mapping = guard.get(key)
        if not isinstance(mapping, dict):
            err(f"guard.{key}", "is missing or not an object.", regen)
            continue
        for theme in themes:
            if theme not in mapping:
                err(f"guard.{key}.{theme}", "is missing.", regen)
            elif palette and not _names_colour(palette, mapping[theme]):
                err(f"guard.{key}.{theme}", f"names '{mapping[theme]}', which is not in guard.palette.", regen)


def _check_exceptions(m, themes, err):
    exceptions = m.get("contrastExceptions")
    if exceptions is None:
        return
    if not isinstance(exceptions, list):
        err("contrastExceptions", "must be a list.", "Use a list of {theme, pair, reason}, or remove it.")
        return
    for i, item in enumerate(exceptions):
        field = f"contrastExceptions[{i}]"
        if not isinstance(item, dict):
            err(field, "must be an object.", "Use {\"theme\": ..., \"pair\": ..., \"reason\": ...}.")
            continue
        if item.get("theme") not in themes:
            err(f"{field}.theme", f"is {item.get('theme')!r}, which is not a theme.",
                f"Use one of: {', '.join(themes)}.")
        if item.get("pair") not in CONTRAST_PAIRS:
            err(f"{field}.pair", f"is {item.get('pair')!r}.", f"Use one of: {', '.join(CONTRAST_PAIRS)}.")
        if not (isinstance(item.get("reason"), str) and item["reason"].strip()):
            err(f"{field}.reason", "is missing.", "Say why this theme may go below 4.5:1.")


def _safe_relative(value):
    p = pathlib.PurePosixPath(value)
    return not p.is_absolute() and ".." not in p.parts


def _check_files(pack, report):
    m = pack.manifest
    for required in ("tokens.css", "brand.md"):
        if not pack.path(required).is_file():
            report.error(display(pack.path(required)), "", "required file is missing.",
                         f"Add {required} to the pack. {GUIDE}")
    logo = m.get("logo")
    if isinstance(logo, str) and logo.strip():
        name = display(pack.path("brand.json"))
        if not _safe_relative(logo):
            report.error(name, "field 'logo'", "must be a path inside the pack.",
                         "Use a path such as assets/logo.svg.")
        elif not logo.lower().endswith(".svg"):
            report.error(name, "field 'logo'", "must name an SVG file.", "Use an .svg logo.")
        elif not pack.path(logo).is_file():
            report.error(display(pack.path(logo)), "", "logo file named by field 'logo' is missing.",
                         "Add the file or correct field 'logo'.")
    if m.get("fonts") and not pack.path("fonts.css").is_file():
        report.error(display(pack.path("fonts.css")), "",
                     "is required because field 'fonts' lists fonts.",
                     "Add fonts.css with the @font-face rules.")
    themes = m.get("themes") if isinstance(m.get("themes"), list) else []
    blooms = [t["value"] for t in themes if isinstance(t, dict) and t.get("bloom") and "value" in t]
    if blooms and not pack.path("assets", "gradients.css").is_file():
        report.error(display(pack.path("assets", "gradients.css")), "",
                     f"is required because theme '{blooms[0]}' has bloom set.",
                     "Add the gradient, or set bloom to false.")


def _pack_css(pack):
    text = pack.path("tokens.css").read_text(encoding="utf-8")
    gradients = pack.optional("assets", "gradients.css")
    return text + "\n" + (gradients.read_text(encoding="utf-8") if gradients else "")


def _check_tokens(pack, report):
    tokens_path = pack.path("tokens.css")
    name = display(tokens_path)
    declared = set(CSS_VAR_DECLARED.findall(csstokens.strip_comments(tokens_path.read_text(encoding="utf-8"))))
    for token in required_tokens():
        if token not in declared:
            report.error(name, f"token '{token}'", "is missing.", f"Declare {token} in tokens.css.")
    theme_css = csstokens.strip_comments(_pack_css(pack))
    for theme in pack.manifest["themes"]:
        if isinstance(theme, dict) and isinstance(theme.get("value"), str) and \
                f'[data-theme="{theme["value"]}"]' not in theme_css:
            report.error(name, f"theme '{theme['value']}'",
                         f'has no [data-theme="{theme["value"]}"] rule.',
                         "Add the theme's rule to tokens.css or assets/gradients.css.")


def _check_contrast(pack, report):
    m, css = pack.manifest, _pack_css(pack)
    guard = m["guard"]
    palette = {k: tuple(v) for k, v in guard["palette"].items()}
    name, tokens_name = display(pack.path("brand.json")), display(pack.path("tokens.css"))
    regen = "Regenerate the guard data from tokens.css with the Generator's brand tools."

    written = csstokens.colours_in(css)
    for colour, rgb in palette.items():
        if rgb not in written:
            report.error(name, f"field 'guard.palette.{colour}'",
                         f"is {csstokens.to_hex(rgb)}, which tokens.css does not define.", regen)

    exceptions = m.get("contrastExceptions")
    excepted = {(e.get("theme"), e.get("pair")) for e in exceptions
                if isinstance(e, dict) and isinstance(e.get("theme"), str) and isinstance(e.get("pair"), str)
                } if isinstance(exceptions, list) else set()
    used = set()
    for theme in (t["value"] for t in m["themes"]):
        tokens = csstokens.theme_tokens(css, theme)
        base = palette[guard["themeBg"][theme]]
        declared_bg = csstokens.parse_colour(csstokens.resolve(tokens, "--bg"))
        if declared_bg and declared_bg[3] == 1.0 and declared_bg[:3] != base:
            report.error(name, f"field 'guard.themeBg.{theme}'",
                         f"is {csstokens.to_hex(base)}, but --bg in tokens.css is "
                         f"{csstokens.to_hex(declared_bg)}.", regen)
        colours = {}
        for token in ("--text", "--muted", "--accent", "--on-accent"):
            colour = csstokens.parse_colour(csstokens.resolve(tokens, token))
            if colour is None:
                report.error(tokens_name, f"theme '{theme}'",
                             f"has no plain colour for {token}, so its contrast cannot be measured.",
                             f"Set {token} to a hex or rgb() colour for this theme.")
            colours[token] = colour
        if None in colours.values():
            continue
        text = colours["--text"]
        if text[3] == 1.0 and text[:3] != palette[guard["themeText"][theme]]:
            report.error(name, f"field 'guard.themeText.{theme}'",
                         f"is {csstokens.to_hex(palette[guard['themeText'][theme]])}, but --text "
                         f"in tokens.css is {csstokens.to_hex(text)}.", regen)
        accent = csstokens.over(colours["--accent"], base)
        pairs = {"body": (csstokens.over(text, base), base),
                 "muted": (csstokens.over(colours["--muted"], base), base),
                 "on-accent": (csstokens.over(colours["--on-accent"], accent), accent)}
        for pair, (fg, bg) in pairs.items():
            ratio = csstokens.contrast(fg, bg)
            if ratio >= CONTRAST_MINIMUM:
                continue
            if (theme, pair) in excepted:
                used.add((theme, pair))
                continue
            report.error(tokens_name, f"theme '{theme}' pair '{pair}'",
                         f"has contrast {ratio:.2f}:1 ({csstokens.to_hex(fg)} on {csstokens.to_hex(bg)}), "
                         f"below WCAG AA {CONTRAST_MINIMUM}:1.",
                         "Change the colour, or add a contrastExceptions entry with a reason.")
    for theme, pair in sorted(excepted - used):
        report.warn(name, "field 'contrastExceptions'",
                    f"names theme '{theme}' pair '{pair}', which already meets {CONTRAST_MINIMUM}:1.",
                    "Remove the exception.")
