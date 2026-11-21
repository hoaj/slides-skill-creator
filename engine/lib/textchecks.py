"""Slide-text checks. They warn, one line per finding, and never stop a build.

    key terms:      a slide uses a name the template's `<!-- key-terms -->` block lists
                    under "Avoid:" (visible text, data-title and alt text)
    headline count: a headline counts the items below it ("Five requirements ...")
    kicker:         the label above a headline repeats the headline
    number format:  a number is not in the Brand pack's numberFormat
"""
import html as htmllib
import re

KEY_TERMS = re.compile(r"<!--\s*key-terms\s*\n(.*?)-->", re.S)
SLIDE = re.compile(r'<section\b[^>]*class="[^"]*\bslide\b[^"]*"[^>]*>', re.S)
ALSO_CALLED = re.compile(r"also called(\s+\S+){0,2}\s*$", re.I)  # "X (also called the Y)"
NOT_TEXT = re.compile(r"<(style|script)\b.*?</\1>|<!--.*?-->", re.S | re.I)
TEXT_ATTRS = re.compile(r'\b(?:alt|title|aria-label)="([^"]*)"')
NUMBER_WORDS = {
    "en": "two three four five six seven eight nine ten eleven twelve".split(),
    "da": "to tre fire fem seks syv otte ni ti elleve tolv".split(),
}
HEADING = re.compile(r"<h([1-3])\b[^>]*>(.*?)</h\1>", re.S)
KICKER = re.compile(r"<(span|p|div)\b[^>]*>((?:(?!</?(?:div|section|h\d|p|span)\b).){1,160}?)</\1>"
                    r"\s*<h([12])\b[^>]*>(.*?)</h\3>", re.S)
STOP = set("the and for with that this what from into your our their about over will "
           "der det den med som til fra for og af på er en et vi".split())


def parse_key_terms(html):
    """The template's key-terms block -> [(term, [avoided names])].

    One term per line: `Term: what it is. Avoid: other name, another name`.
    """
    m = KEY_TERMS.search(html)
    if not m:
        return []
    terms = []
    for line in m.group(1).splitlines():
        line = line.strip().lstrip("-").strip()
        if ":" not in line:
            continue
        term = line.split(":", 1)[0].strip()
        parts = re.split(r"\bavoid:", line, maxsplit=1, flags=re.I)
        avoid = [a.strip().rstrip(".") for a in parts[1].split(",")] if len(parts) > 1 else []
        terms.append((term, [a for a in avoid if a]))
    return terms


def _plain(fragment):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def slides(html):
    """[(slide number, data-title, inner HTML)] for each <section class="slide">."""
    out = []
    for n, m in enumerate(SLIDE.finditer(html), 1):
        end = html.find("</section>", m.end())
        title = re.search(r'data-title="([^"]*)"', m.group(0))
        out.append((n, htmllib.unescape(title.group(1)) if title else "",
                    NOT_TEXT.sub(" ", html[m.end():end if end != -1 else None])))
    return out


def slide_texts(html):
    """[(slide number, data-title, text)]: the visible text plus the words a viewer meets
    elsewhere: the data-title (overview, edit panel) and alt / title / aria-label text."""
    out = []
    for n, title, body in slides(html):
        hidden = " ".join([title] + [htmllib.unescape(a) for a in TEXT_ATTRS.findall(body)])
        out.append((n, title, _plain(body) + " " + hidden))
    return out


def key_term_warnings(html):
    """One line per avoided name a slide uses. "Term (also called X)" introduces X: allowed."""
    warnings = []
    terms = parse_key_terms(html)
    if not terms:
        return warnings
    for n, title, text in slide_texts(html):
        seen = []                        # spans already reported on this slide
        for term, avoid in terms:
            # an avoided name inside the key term itself ("in-house" in "Build in-house")
            # is the term, not the name to avoid
            own = [t.span() for t in re.finditer(re.escape(term), text, re.I)]
            for name in avoid:
                for hit in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, re.I):
                    if any(a <= hit.start() and hit.end() <= b for a, b in own):
                        continue
                    if ALSO_CALLED.search(text[max(0, hit.start() - 60):hit.start()]):
                        continue
                    if any(a < hit.end() and hit.start() < b for a, b in seen):
                        continue             # overlapping avoided names: one report
                    seen.append(hit.span())
                    warnings.append(f'slide {n} "{title}" says "{hit.group(0)}"; '
                                    f'the key term is "{term}"')
                    break
    return warnings


def headline_count_warnings(html, lang="en"):
    """A headline that counts the items below it ("Five requirements ...") goes stale on the
    next edit. Warn when a number in a heading equals the item count of a list, a card row
    or the build steps on the same slide."""
    words = NUMBER_WORDS.get(lang, []) + NUMBER_WORDS["en"]
    value = {w: i + 2 for ws in NUMBER_WORDS.values() for i, w in enumerate(ws)}
    num = re.compile(r"(?<![\w.,])(" + "|".join(words) + r"|[2-9]|1[0-2])(?![\w.,%])", re.I)
    warnings = []
    for n, title, body in slides(html):
        counts = {len(re.findall(r"<li\b", lst))
                  for lst in re.findall(r"<(?:ul|ol)\b.*?</(?:ul|ol)>", body, re.S)}
        counts.add(len(re.findall(r'class="(?:[^"]*\s)?card(?:\s[^"]*)?"', body)))  # .card, not .card-row
        counts.add(len(re.findall(r"\sdata-step\b", body)))
        for _, heading in HEADING.findall(body):
            text = _plain(heading)
            for m in num.finditer(text):
                k = int(m.group(1)) if m.group(1).isdigit() else value.get(m.group(1).lower())
                if k in counts:
                    warnings.append(f'slide {n} "{title}": "{text}" counts the {k} items below it')
                    break
    return warnings


def _content_words(text):
    return {w[:6] for w in re.findall(r"\w{4,}", text.lower()) if w not in STOP}


def kicker_warnings(html):
    """A kicker (the small label right above a headline) that shares a content word with the
    headline usually says it twice ("What the server needs" over "Requirements for the server")."""
    warnings = []
    for n, title, body in slides(html):
        for m in KICKER.finditer(body):
            kicker, heading = _plain(m.group(2)), _plain(m.group(4))
            if kicker and _content_words(kicker) & _content_words(heading):
                warnings.append(f'slide {n} "{title}": the kicker "{kicker}" repeats the headline "{heading}"')
    return warnings


def number_format_warnings(html, nf):
    """Numbers written in the other convention than the pack's numberFormat. Only clear
    cases: 159,365 (thousands comma) and 3.5% / 1.5x (decimal point before a unit) when the
    pack uses "." for thousands. Versions such as "OAuth 2.1" are left alone."""
    if not nf or nf.get("thousands") != ".":
        return []
    us = re.compile(r"(?<![\w.,])[1-9]\d{0,2}(?:,\d{3})+(?:\.\d+)?(?![\d,])"
                    r"|(?<![\w.,])\d+\.\d+(?=\s?(?:%|x\b|pct\b|percent|procent|kr\b|DKK|EUR|mio\b|mia\b|bn\b|[kKmM]\b))")
    warnings = []
    for n, title, text in slide_texts(html):
        found = sorted(set(us.findall(text)))
        if found:
            warnings.append(f'slide {n} "{title}": {", ".join(found)} - write numbers as '
                            f'159{nf["thousands"]}365 and 3{nf.get("decimal", ",")}5')
    return warnings


def text_warnings(html, manifest):
    """Every slide-text check, as (kind, message) pairs."""
    stage = re.search(r'<[^>]*\bid="deckStage"[^>]*>', html)
    lang = re.search(r'\blang="([a-z]{2})', stage.group(0)) if stage else None
    lang = lang.group(1) if lang else "en"
    out = [("key terms", w) for w in key_term_warnings(html)]
    out += [("headline count", w) for w in headline_count_warnings(html, lang)]
    out += [("kicker", w) for w in kicker_warnings(html)]
    out += [("number format", w) for w in number_format_warnings(html, manifest.get("numberFormat"))]
    return out
