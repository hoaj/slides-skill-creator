"""Find and load Brand packs, and stop on anything the build needs and cannot find.

The full validator (contrast against WCAG AA, guard data against tokens.css) is a later
ticket. This module checks what `deck.py build` itself depends on, and names the file and
field in every error.
"""
import json
import pathlib
import re

from .common import BRANDS, FIXTURES, RUNTIME, DeckError, display

FORMAT_VERSION = 1
HIDDEN_PACK = "plain"
UPGRADE_COMMAND = "python3 <skill>/engine/deck.py upgrade"
RETIRED_FIELDS = ("files", "logoWidthPx", "fontFamily", "storePrefix")
GUARD_LISTS = ("neutrals", "vivids")
GUARD_NAMES = ("lightNeutral", "darkNeutral")
GUARD_MAPS = ("themeBg", "themeText")

CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
CSS_VAR_USE = re.compile(r"var\(\s*(--[\w-]+)\s*\)")
CSS_VAR_DECLARED = re.compile(r"(?:^|[;{\s])(--[\w-]+)\s*:")


class Pack:
    """One loaded Brand pack: its folder and its parsed brand.json."""

    def __init__(self, slug, root, manifest):
        self.slug = slug
        self.root = root
        self.manifest = manifest

    def path(self, *parts):
        return self.root.joinpath(*parts)

    def optional(self, *parts):
        """The file's path when the pack has it, else None."""
        p = self.path(*parts)
        return p if p.is_file() else None


def pack_dir(slug):
    """`plain` always means the Engine's hidden test pack."""
    return FIXTURES / HIDDEN_PACK if slug == HIDDEN_PACK else BRANDS / slug


def _read_manifest(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise DeckError(f"{display(path)}: not valid JSON ({e})")
    if not isinstance(data, dict):
        raise DeckError(f"{display(path)}: must be a JSON object")
    return data


def list_packs():
    """([(slug, name, aliases)], [problem]) for <skill>/brands, without the hidden pack."""
    found, problems = [], []
    if not BRANDS.is_dir():
        return found, problems
    for folder in sorted(p for p in BRANDS.iterdir() if p.is_dir()):
        manifest = folder / "brand.json"
        if folder.name == HIDDEN_PACK or not manifest.is_file():
            continue
        try:
            data = _read_manifest(manifest)
        except DeckError as e:
            problems.append(str(e))
            continue
        aliases = data.get("aliases")
        found.append((folder.name, str(data.get("name", folder.name)),
                      [str(a) for a in aliases] if isinstance(aliases, list) else []))
    return found, problems


def load(slug):
    """Load and check one Brand pack. Stops with a precise error."""
    root = pack_dir(slug)
    manifest_path = root / "brand.json"
    if not manifest_path.is_file():
        available = ", ".join(s for s, _, _ in list_packs()[0]) or "(none)"
        raise DeckError(f"unknown Brand pack '{slug}': {display(manifest_path)} does not "
                        f"exist. Available: {available}")
    manifest = _read_manifest(manifest_path)
    pack = Pack(slug, root, manifest)
    _check_format(pack, manifest_path)
    errors = _check_manifest(pack) + _check_files(pack)
    if not errors:
        errors = _check_tokens(pack)
    if errors:
        raise DeckError("Brand pack is not valid:\n  " + "\n  ".join(errors))
    return pack


def warnings(pack):
    """What still works but is worth saying."""
    out = []
    name = display(pack.path("brand.json"))
    if not pack.manifest.get("pptxLead"):
        out.append(f"{name}: no pptxLead, so PowerPoint export applies no vertical correction")
    if not pack.optional("icon-library.js"):
        out.append(f"{display(pack.root)}: no icon-library.js, so the icon picker is hidden")
    return out


def required_tokens():
    """Custom properties the runtime CSS reads with no fallback and does not set itself."""
    used, declared = set(), set()
    for css in sorted(RUNTIME.glob("*.css")):
        text = CSS_COMMENT.sub("", css.read_text(encoding="utf-8"))
        used |= set(CSS_VAR_USE.findall(text))
        declared |= set(CSS_VAR_DECLARED.findall(text))
    return sorted(used - declared)


def _check_format(pack, manifest_path):
    version = pack.manifest.get("formatVersion")
    if version == FORMAT_VERSION and type(version) is int:
        return
    state = "is missing" if version is None else f"is {version!r}"
    raise DeckError(f"{display(manifest_path)}: field 'formatVersion' {state}, and this Engine "
                    f"supports exactly {FORMAT_VERSION}. Migrate the pack with: {UPGRADE_COMMAND}")


def _check_manifest(pack):
    m, errors = pack.manifest, []
    name = display(pack.path("brand.json"))

    def err(field, problem):
        errors.append(f"{name}: field '{field}' {problem}")

    for field in RETIRED_FIELDS:
        if field in m:
            err(field, "is no longer part of the format; remove it")
    for field in ("slug", "name", "logo", "defaultTheme", "defaultClassification"):
        if not (isinstance(m.get(field), str) and m[field].strip()):
            err(field, "is missing or not a text value")
    if isinstance(m.get("slug"), str) and m["slug"] != pack.root.name:
        err("slug", f"is '{m['slug']}' but the pack's folder is '{pack.root.name}'")
    if not isinstance(m.get("fonts"), list):
        err("fonts", "is missing or not a list (use [] for system fonts)")

    values = _check_themes(m, err)
    if values and m.get("defaultTheme") not in values:
        err("defaultTheme", f"is '{m.get('defaultTheme')}', which is not one of the themes")

    labels = m.get("classifications")
    if not (isinstance(labels, list) and labels
            and all(isinstance(c, str) and c.strip() for c in labels)):
        err("classifications", "is missing or not a list of labels")
    elif "defaultClassification" in m and m["defaultClassification"] not in labels:
        err("defaultClassification",
            f"is '{m['defaultClassification']}', which is not one of the classifications")

    lead = m.get("pptxLead")
    if lead is not None and not (isinstance(lead, list) and len(lead) == 3 and all(
            isinstance(n, (int, float)) and not isinstance(n, bool) for n in lead)):
        err("pptxLead", "must be a list of three numbers")
    _check_guard(m.get("guard"), values, err)
    return errors


def _check_themes(m, err):
    themes = m.get("themes")
    if not (isinstance(themes, list) and themes):
        err("themes", "is missing or empty")
        return []
    values = []
    for i, theme in enumerate(themes):
        if not isinstance(theme, dict):
            err(f"themes[{i}]", "must be an object")
            continue
        for key in ("value", "label"):
            if not (isinstance(theme.get(key), str) and theme[key].strip()):
                err(f"themes[{i}].{key}", "is missing or not a text value")
        value = theme.get("value")
        if isinstance(value, str) and value:
            if value in values:
                err(f"themes[{i}].value", f"repeats '{value}'")
            values.append(value)
    return values


def _check_guard(guard, themes, err):
    if not isinstance(guard, dict):
        err("guard", "is missing or not an object")
        return
    palette = guard.get("palette")
    if not (isinstance(palette, dict) and palette):
        err("guard.palette", "is missing or empty")
        palette = {}
    for colour, rgb in palette.items():
        if not (isinstance(rgb, list) and len(rgb) == 3 and all(
                isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in rgb)):
            err(f"guard.palette.{colour}", "must be three integers from 0 to 255")
    for key in GUARD_LISTS:
        names = guard.get(key)
        if not isinstance(names, list):
            err(f"guard.{key}", "is missing or not a list")
            continue
        for n in names:
            if palette and n not in palette:
                err(f"guard.{key}", f"names '{n}', which is not in guard.palette")
    for key in GUARD_NAMES:
        if key not in guard:
            err(f"guard.{key}", "is missing")
        elif palette and guard[key] not in palette:
            err(f"guard.{key}", f"names '{guard[key]}', which is not in guard.palette")
    for key in GUARD_MAPS:
        mapping = guard.get(key)
        if not isinstance(mapping, dict):
            err(f"guard.{key}", "is missing or not an object")
            continue
        for theme in themes:
            if theme not in mapping:
                err(f"guard.{key}.{theme}", "is missing")
            elif palette and mapping[theme] not in palette:
                err(f"guard.{key}.{theme}",
                    f"names '{mapping[theme]}', which is not in guard.palette")


def _safe_relative(value):
    p = pathlib.PurePosixPath(value)
    return not p.is_absolute() and ".." not in p.parts


def _check_files(pack):
    m, errors = pack.manifest, []
    for required in ("tokens.css", "brand.md"):
        if not pack.path(required).is_file():
            errors.append(f"{display(pack.path(required))}: required file is missing")
    logo = m.get("logo")
    if isinstance(logo, str) and logo.strip():
        name = display(pack.path("brand.json"))
        if not _safe_relative(logo):
            errors.append(f"{name}: field 'logo' must be a path inside the pack")
        elif not logo.lower().endswith(".svg"):
            errors.append(f"{name}: field 'logo' must name an SVG file")
        elif not pack.path(logo).is_file():
            errors.append(f"{display(pack.path(logo))}: logo file named by field 'logo' is missing")
    if m.get("fonts") and not pack.path("fonts.css").is_file():
        errors.append(f"{display(pack.path('fonts.css'))}: required because field 'fonts' lists fonts")
    themes = m.get("themes") if isinstance(m.get("themes"), list) else []
    blooms = [t["value"] for t in themes if isinstance(t, dict) and t.get("bloom") and "value" in t]
    if blooms and not pack.path("assets", "gradients.css").is_file():
        errors.append(f"{display(pack.path('assets', 'gradients.css'))}: required because theme "
                      f"'{blooms[0]}' has bloom set")
    return errors


def _check_tokens(pack):
    tokens_path = pack.path("tokens.css")
    tokens = CSS_COMMENT.sub("", tokens_path.read_text(encoding="utf-8"))
    declared = set(CSS_VAR_DECLARED.findall(tokens))
    errors = [f"{display(tokens_path)}: token '{t}' is missing"
              for t in required_tokens() if t not in declared]
    gradients = pack.optional("assets", "gradients.css")
    theme_css = tokens + (CSS_COMMENT.sub("", gradients.read_text(encoding="utf-8")) if gradients else "")
    for theme in pack.manifest["themes"]:
        if f'[data-theme="{theme["value"]}"]' not in theme_css:
            errors.append(f"{display(tokens_path)}: theme '{theme['value']}' has no "
                          f'[data-theme="{theme["value"]}"] rule')
    return errors
