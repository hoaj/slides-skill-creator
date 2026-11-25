"""Write a Brand pack's `guard` contrast data from its tokens.css, and report each theme's contrast.

Derived: the palette (every literal colour in `:root` except the series and UI tokens, named
without the `--<slug>-` prefix), each theme's background and text colour, and the light and dark
neutral. Asked for, because tokens.css cannot say it: the solid base colour under a gradient or
transparent background (`--base theme=colour`). Whether a colour is a neutral or a vivid accent
is proposed from its chroma and keeps any earlier choice; `--neutral` and `--vivid` override it.
"""
import pathlib

from .common import GenError, read_json, write_json

SKIP_PREFIXES = ("--series-", "--on-series", "--ui-")
NEUTRAL_CHROMA = 80  # max(r, g, b) - min(r, g, b) below this reads as a neutral


def _css(pack):
    text = (pack / "tokens.css").read_text(encoding="utf-8")
    gradients = pack / "assets" / "gradients.css"
    return text + "\n" + (gradients.read_text(encoding="utf-8") if gradients.is_file() else "")


def _palette(css, slug):
    from lib import csstokens
    palette = {}
    for head, body, media in csstokens.rules(css):
        if media is not None or ":root" not in [s.strip() for s in head.split(",")]:
            continue
        for prop, value in csstokens.declarations(body).items():
            if prop.startswith(SKIP_PREFIXES):
                continue
            colour = csstokens.parse_colour(value)
            if not colour or colour[3] != 1.0:
                continue
            name = prop[2:]
            if name.startswith(f"{slug}-"):
                name = name[len(slug) + 1:]
            palette.setdefault(name, list(colour[:3]))
    return palette


def _name_for(palette, rgb, fallback):
    for name, value in palette.items():
        if tuple(value) == tuple(rgb):
            return name
    palette[fallback] = list(rgb)
    return fallback


def _chroma(rgb):
    return max(rgb) - min(rgb)


def build(pack_dir, bases=(), neutral=(), vivid=()):
    from lib import csstokens
    pack = pathlib.Path(pack_dir).resolve()
    manifest = read_json(pack / "brand.json")
    if not (pack / "tokens.css").is_file():
        raise GenError(f"{pack / 'tokens.css'} is missing")
    themes = [t["value"] for t in manifest.get("themes", []) if isinstance(t, dict) and t.get("value")]
    if not themes:
        raise GenError("brand.json lists no themes; add them before writing the guard data")
    css = _css(pack)
    slug = manifest.get("slug", pack.name)
    palette = _palette(css, slug)
    if not palette:
        raise GenError("tokens.css declares no literal colours in :root, so there is no palette")

    given = {}
    for item in bases:
        theme, sep, colour = item.partition("=")
        if not sep or theme not in themes:
            raise GenError(f"--base must be <theme>=<colour> with a theme from brand.json: {item!r}")
        given[theme] = colour.strip()
    old = manifest.get("guard") if isinstance(manifest.get("guard"), dict) else {}
    old_bg = old.get("themeBg") if isinstance(old.get("themeBg"), dict) else {}

    theme_bg, theme_text, needs = {}, {}, []
    for theme in themes:
        tokens = csstokens.theme_tokens(css, theme)
        bg = csstokens.parse_colour(csstokens.resolve(tokens, "--bg"))
        if theme in given:
            value = given[theme]
            if value in palette:
                theme_bg[theme] = value
            else:
                colour = csstokens.parse_colour(value)
                if not colour or colour[3] != 1.0:
                    raise GenError(f"--base {theme}={value}: name a palette colour or give an opaque "
                                   f"hex colour. Palette: {', '.join(palette)}")
                theme_bg[theme] = _name_for(palette, colour[:3], f"{theme}-base")
        elif bg and bg[3] == 1.0:
            theme_bg[theme] = _name_for(palette, bg[:3], f"{theme}-bg")
        elif old_bg.get(theme) in palette:
            theme_bg[theme] = old_bg[theme]          # the base given on an earlier run
        else:
            needs.append({"theme": theme, "why": "its --bg is a gradient, transparent or not a plain "
                          "colour, so the solid colour under it cannot be read from tokens.css",
                          "give": f"--base {theme}=<palette colour or #hex>"})
            continue
        text = csstokens.parse_colour(csstokens.resolve(tokens, "--text"))
        if not text or text[3] != 1.0:
            raise GenError(f"theme {theme!r}: --text must be an opaque hex or rgb() colour in tokens.css")
        theme_text[theme] = _name_for(palette, text[:3], f"{theme}-text")
    if needs:
        raise GenError("the guard data needs the base colour of some themes", needs=needs)

    unknown = [n for n in list(neutral) + list(vivid) if n not in palette]
    if unknown:
        raise GenError(f"not palette colours: {', '.join(unknown)}. Palette: {', '.join(palette)}")
    old_neutrals = set(old.get("neutrals") or [])
    old_vivids = set(old.get("vivids") or [])
    kinds = {}
    for name, rgb in palette.items():
        if name in neutral:
            kinds[name] = "neutral"
        elif name in vivid:
            kinds[name] = "vivid"
        elif name in old_neutrals:
            kinds[name] = "neutral"
        elif name in old_vivids:
            kinds[name] = "vivid"
        else:
            kinds[name] = "neutral" if _chroma(rgb) < NEUTRAL_CHROMA else "vivid"
    neutrals = [n for n in palette if kinds[n] == "neutral"]
    if not neutrals:
        raise GenError("the palette has no neutral colour; mark one with --neutral")
    lum = {n: csstokens.luminance(palette[n]) for n in neutrals}

    manifest["guard"] = {
        "palette": palette,
        "neutrals": neutrals,
        "vivids": [n for n in palette if kinds[n] == "vivid"],
        "lightNeutral": max(neutrals, key=lambda n: lum[n]),
        "darkNeutral": min(neutrals, key=lambda n: lum[n]),
        "themeBg": theme_bg,
        "themeText": theme_text,
    }
    write_json(pack / "brand.json", manifest)

    from . import pack as packs
    result = packs.check(pack)
    result.update({"guard": manifest["guard"], "contrast": contrast_table(css, manifest),
                   "written": ["brand.json"]})
    return result


def contrast_table(css, manifest):
    """{theme: {pair: ratio}} on each theme's base colour, as the validator measures it."""
    from lib import csstokens
    guard = manifest["guard"]
    table = {}
    for theme in guard["themeBg"]:
        tokens = csstokens.theme_tokens(css, theme)
        base = tuple(guard["palette"][guard["themeBg"][theme]])
        colours = {t: csstokens.parse_colour(csstokens.resolve(tokens, t))
                   for t in ("--text", "--muted", "--accent", "--on-accent")}
        if None in colours.values():
            table[theme] = {"error": "a contrast token is not a plain colour"}
            continue
        accent = csstokens.over(colours["--accent"], base)
        pairs = {"body": (csstokens.over(colours["--text"], base), base),
                 "muted": (csstokens.over(colours["--muted"], base), base),
                 "on-accent": (csstokens.over(colours["--on-accent"], accent), accent)}
        table[theme] = {pair: round(csstokens.contrast(fg, bg), 2) for pair, (fg, bg) in pairs.items()}
    return table
