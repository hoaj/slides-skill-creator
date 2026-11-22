"""Read what a built deck records about itself: its Brand pack, Deck type and key terms."""
import json
import re

from . import build, packs, playbook, textchecks
from .common import DeckError

BRAND_SLUG = re.compile(r'window\.DeckBrand = \{"slug":"([^"]+)"')


def run(path, as_json=False):
    if not path.is_file():
        raise DeckError(f"deck not found: {path}")
    html = path.read_text(encoding="utf-8", errors="replace")
    slug = BRAND_SLUG.search(html)
    if not slug:
        raise DeckError(f"{path} is not a deck built by deck.py: it has no window.DeckBrand.")
    slug = slug.group(1)
    type_id = build.recorded_deck_type(html)
    warnings = []
    known = None
    try:
        known = {t["id"] for t in playbook.list_deck_types(packs.load(slug))}
    except DeckError as e:
        warnings.append(f"Brand pack '{slug}' cannot be used here: {e}")
    if type_id and known is not None and type_id not in known:
        warnings.append(f"the deck records the Deck type '{type_id}', which Brand pack "
                        f"'{slug}' no longer has.")
    terms = textchecks.parse_key_terms(html)
    info = {"brand": slug, "deckType": type_id, "slides": len(textchecks.slides(html)),
            "keyTerms": [{"term": t, "avoid": a} for t, a in terms], "warnings": warnings}
    if as_json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        return 0
    print(f"Brand pack: {slug}")
    print(f"Deck type: {type_id or 'none'}")
    print(f"Slides: {info['slides']}")
    print("Key terms: " + (", ".join(t for t, _ in terms) if terms else "(none)"))
    for warning in warnings:
        print(f"warning: {warning}")
    return 0
