"""Read a Brand pack's CSS: its rules, its custom properties and their colours.

A small reader, not a CSS engine. It understands what a pack's `tokens.css` and
`assets/gradients.css` hold: `:root`, `[data-theme="x"]` rules, `var()` with a fallback, and
hex, rgb() and rgba() colours. Anything else (a gradient, color-mix) is "not a plain colour".
"""
import re

COMMENT = re.compile(r"/\*.*?\*/", re.S)
CUSTOM_PROPERTY = re.compile(r"^(--[\w-]+)\s*:\s*(.*)$", re.S)
VAR = re.compile(r"^var\(\s*(--[\w-]+)\s*(?:,(.*))?\)$", re.S)
HEX = re.compile(r"^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$")
RGB = re.compile(r"^rgba?\((.*)\)$", re.S)
ANY_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)")
NOT = re.compile(r":not\([^)]*\)")
NAMED = {"white": (255, 255, 255, 1.0), "black": (0, 0, 0, 1.0), "transparent": (0, 0, 0, 0.0)}


def strip_comments(text):
    return COMMENT.sub("", text)


def _closing_brace(text, opening, end):
    depth, quote, i = 0, None, opening
    while i < end:
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return end


def rules(text):
    """[(selector or at-rule, body, enclosing @media or None)], in source order."""
    text = strip_comments(text)
    out = []

    def walk(start, end, media):
        i = start
        while i < end:
            brace = text.find("{", i, end)
            if brace == -1:
                return
            head = text[i:brace].rsplit(";", 1)[-1].strip()
            close = _closing_brace(text, brace, end)
            if head.startswith("@media"):
                walk(brace + 1, close, head)
            else:
                out.append((head, text[brace + 1:close], media))
            i = close + 1

    walk(0, len(text), None)
    return out


def declarations(body):
    """{custom property: value} from a rule body. A ';' inside url() or a string is kept."""
    parts, buf, depth, quote = [], [], 0, None
    for c in body:
        if quote:
            quote = None if c == quote else quote
        elif c in "\"'":
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth = max(0, depth - 1)
        elif c == ";" and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(c)
    parts.append("".join(buf))
    out = {}
    for part in parts:
        hit = CUSTOM_PROPERTY.match(part.strip())
        if hit:
            out[hit.group(1)] = hit.group(2).strip()
    return out


def _selects_theme(selector, theme):
    """True for `[data-theme="x"]`, optionally on one compound such as `.slide[...]`."""
    selector = NOT.sub("", selector).strip()
    return bool(re.fullmatch(r"[\w.-]*\[data-theme=[\"']?" + re.escape(theme) + r"[\"']?\][\w.:-]*",
                             selector))


def theme_tokens(css, theme):
    """The custom properties a theme sees: `:root`, then the rules that select the theme."""
    tokens = {}
    parsed = [r for r in rules(css) if r[2] is None]
    for head, body, _ in parsed:
        if ":root" in [s.strip() for s in head.split(",")]:
            tokens.update(declarations(body))
    for head, body, _ in parsed:
        if any(_selects_theme(s, theme) for s in head.split(",")):
            tokens.update(declarations(body))
    return tokens


def resolve(tokens, name, depth=0):
    """A property's value with var() followed, or None when it cannot be resolved."""
    if depth > 16 or name not in tokens:
        return None
    return _follow(tokens, tokens[name], depth)


def _follow(tokens, value, depth):
    hit = VAR.match(value.strip())
    if not hit:
        return value.strip()
    found = resolve(tokens, hit.group(1), depth + 1)
    if found is not None:
        return found
    return _follow(tokens, hit.group(2), depth + 1) if hit.group(2) else None


def _channel(text):
    text = text.strip()
    if text.endswith("%"):
        return round(float(text[:-1]) * 255 / 100)
    return round(float(text))


def _alpha(text):
    text = text.strip()
    return float(text[:-1]) / 100 if text.endswith("%") else float(text)


def parse_colour(value):
    """(r, g, b, alpha) for a plain colour, or None for anything else."""
    if value is None:
        return None
    v = value.strip().lower()
    if v in NAMED:
        return NAMED[v]
    hit = HEX.match(v)
    if hit:
        h = hit.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        alpha = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)
    hit = RGB.match(v)
    if not hit:
        return None
    parts = [p for p in re.split(r"[\s,/]+", hit.group(1).strip()) if p]
    try:
        if len(parts) == 3:
            return (_channel(parts[0]), _channel(parts[1]), _channel(parts[2]), 1.0)
        if len(parts) == 4:
            return (_channel(parts[0]), _channel(parts[1]), _channel(parts[2]), _alpha(parts[3]))
    except ValueError:
        return None
    return None


def colours_in(css):
    """Every opaque (r, g, b) written as a hex or rgb() value in this CSS."""
    found = set()
    for text in ANY_COLOUR.findall(strip_comments(css)):
        colour = parse_colour(text)
        if colour and colour[3] == 1.0:
            found.add(colour[:3])
    return found


def over(top, bottom):
    """A colour with alpha, composited over an opaque (r, g, b)."""
    a = top[3] if len(top) > 3 else 1.0
    return tuple(top[k] * a + bottom[k] * (1 - a) for k in range(3))


def _linear(channel):
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    return 0.2126 * _linear(rgb[0]) + 0.7152 * _linear(rgb[1]) + 0.0722 * _linear(rgb[2])


def contrast(a, b):
    """The WCAG contrast ratio of two opaque colours."""
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def to_hex(rgb):
    return "#" + "".join(f"{int(round(c)):02X}" for c in rgb[:3])
