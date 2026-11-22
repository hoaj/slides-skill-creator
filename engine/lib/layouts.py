"""The Engine's base layout ids, and a Brand pack's own layouts.

A pack's own layout is one file, with an optional stylesheet:

    layouts/<id>.html   exactly one <section class="slide layout-<id>" data-title="...">
    layouts/<id>.css    optional; every selector starts with .layout-<id> or .layout-<id>__part

The build inlines the CSS into every deck of the pack, and the HTML is markup an agent copies
into a deck's template. The scoping is what keeps the decision that a pack can add layouts but
cannot change the base layouts. A pack holds no hand-written code, so a layout has no script.
"""
import json
import re

from . import csstokens
from .common import ENGINE, display

ID = re.compile(r"^[a-z][a-z0-9-]*$")
SECTION = re.compile(r"<section\b[^>]*>", re.I)
CODE = re.compile(r"<script\b|\son[a-z]+\s*=|javascript:", re.I)
REMOTE_ATTR = re.compile(r"\b(?:src|href)\s*=\s*[\"']?\s*(?:https?:)?//", re.I)
REMOTE_URL = re.compile(r"url\(\s*[\"']?\s*(?:https?:)?//", re.I)
THEME_ATTR = re.compile(r'\bdata-theme="([^"]*)"')
CLASS_ATTR = re.compile(r'\bclass="([^"]*)"')
TITLE_ATTR = re.compile(r'\bdata-title="([^"]*)"')


def base():
    """The base layouts, in their documented order."""
    return json.loads((ENGINE / "layouts.json").read_text(encoding="utf-8"))["layouts"]


def base_ids():
    return [layout["id"] for layout in base()]


def own(pack):
    """{id: {"html": path, "css": path or None}} for the pack's `layouts/<id>.html` files."""
    folder = pack.path("layouts")
    if not folder.is_dir():
        return {}
    found = {}
    for html in sorted(folder.glob("*.html")):
        css = html.with_suffix(".css")
        found[html.stem] = {"html": html, "css": css if css.is_file() else None}
    return found


def own_ids(pack):
    return sorted(own(pack))


def known_ids(pack):
    return base_ids() + [i for i in own_ids(pack) if i not in base_ids()]


def own_css(pack):
    """The pack's layout stylesheets, joined for inlining into a deck."""
    parts = []
    for layout_id, files in own(pack).items():
        if files["css"]:
            parts.append(f"/* layout: {layout_id} */\n" + files["css"].read_text(encoding="utf-8"))
    return "\n".join(parts)


def html(pack, layout_id):
    return own(pack)[layout_id]["html"].read_text(encoding="utf-8").strip()


def problems(pack, themes):
    """Format errors in `layouts/`, as (file, where, problem, fix)."""
    folder = pack.path("layouts")
    if not folder.exists():
        return []
    if not folder.is_dir():
        return [(display(folder), "", "must be a folder.", "Make layouts/ a folder or remove it.")]
    out = []
    stems = {p.stem for p in folder.glob("*.html")}
    for item in sorted(folder.iterdir()):
        if item.name.startswith("."):
            continue
        if not item.is_file() or item.suffix not in (".html", ".css"):
            out.append((display(item), "", "is not a layout file.",
                        "Keep only <id>.html and <id>.css in layouts/."))
        elif item.suffix == ".css" and item.stem not in stems:
            out.append((display(item), "", "has no matching .html file.",
                        f"Add layouts/{item.stem}.html or remove this stylesheet."))
    reserved = set(base_ids())
    for layout_id, files in own(pack).items():
        out += _check_id(files["html"], layout_id, reserved)
        out += _check_html(files["html"], layout_id, themes)
        if files["css"]:
            out += _check_css(files["css"], layout_id)
    return out


def _check_id(path, layout_id, reserved):
    if not ID.match(layout_id):
        return [(display(path), "layout id", f"'{layout_id}' is not a valid id.",
                 "Name the file with lowercase letters, digits and hyphens.")]
    if layout_id in reserved:
        return [(display(path), "layout id", f"'{layout_id}' is one of the Engine's base layouts, "
                 "and a Brand pack cannot override a base layout.",
                 "Rename the file to an id of its own.")]
    return []


def _check_html(path, layout_id, themes):
    name, out = display(path), []
    text = path.read_text(encoding="utf-8")
    sections = SECTION.findall(text)
    if len(sections) != 1:
        return [(name, "", f"must hold exactly one <section>, and holds {len(sections)}.",
                 f'Keep one <section class="slide layout-{layout_id}" data-title="...">.')]
    classes = CLASS_ATTR.search(sections[0])
    classes = classes.group(1).split() if classes else []
    for needed in ("slide", f"layout-{layout_id}"):
        if needed not in classes:
            out.append((name, "<section> class", f"does not include '{needed}'.",
                        f'Use class="slide layout-{layout_id}".'))
    title = TITLE_ATTR.search(sections[0])
    if not (title and title.group(1).strip()):
        out.append((name, "<section> data-title", "is missing.", 'Add data-title="...".'))
    if CODE.search(text):
        out.append((name, "", "holds script code, and a Brand pack holds no hand-written code.",
                    "Remove the <script>, on* attribute or javascript: link."))
    if REMOTE_ATTR.search(text) or REMOTE_URL.search(text):
        out.append((name, "", "loads a remote file, and a deck must be self-contained.",
                    "Use a file inlined as a data: URI, or CSS."))
    for theme in THEME_ATTR.findall(text):
        if themes and theme not in themes:
            out.append((name, "data-theme", f"'{theme}' is not a theme of this pack.",
                        f"Use one of: {', '.join(themes)}."))
    return out


def _check_css(path, layout_id):
    name, out = display(path), []
    text = path.read_text(encoding="utf-8")
    scope = re.compile(r"^\.layout-" + re.escape(layout_id) + r"(?:__[\w-]+)?(?![\w-])")
    if re.search(r"@import\b", text) or REMOTE_URL.search(text):
        out.append((name, "", "loads a remote file, and a deck must be self-contained.",
                    "Remove the @import or remote url()."))
    for head, _body, _media in csstokens.rules(text):
        if head.startswith("@"):
            out.append((name, f"rule '{head}'", "is not allowed in a layout stylesheet.",
                        "Use plain rules, optionally inside @media."))
            continue
        for selector in head.split(","):
            if not scope.match(selector.strip()):
                out.append((name, f"selector '{selector.strip()}'",
                            f"does not start with .layout-{layout_id} or .layout-{layout_id}__part, "
                            "so it could change a base layout.",
                            f"Start the selector with .layout-{layout_id}."))
    return out
