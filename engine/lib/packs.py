"""Find and load Brand packs. `load` stops on anything the validator (validate.py) stops on."""
import json

from . import validate
from .common import BRANDS, FIXTURES, DeckError, display

HIDDEN_PACK = "plain"


class Pack:
    """One loaded Brand pack: its folder and its parsed brand.json."""

    def __init__(self, slug, root, manifest):
        self.slug = slug
        self.root = root
        self.manifest = manifest
        self.report = None

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


def read(slug):
    """The pack's folder and parsed manifest, without validating it."""
    root = pack_dir(slug)
    manifest_path = root / "brand.json"
    if not manifest_path.is_file():
        available = ", ".join(s for s, _, _ in list_packs()[0]) or "(none)"
        raise DeckError(f"unknown Brand pack '{slug}': {display(manifest_path)} does not "
                        f"exist. Available: {available}")
    return Pack(slug, root, _read_manifest(manifest_path))


def check(slug):
    """(pack, report) for `deck.py check`: every problem, without stopping at the first."""
    pack = read(slug)
    return pack, validate.validate(pack)


def load(slug):
    """Load one Brand pack and stop with a precise error if it is not valid."""
    pack, report = check(slug)
    if report.errors:
        raise DeckError("Brand pack is not valid:\n  " + "\n  ".join(str(e) for e in report.errors))
    pack.report = report
    return pack


def all_slugs():
    """Every pack in <skill>/brands, then the hidden test pack."""
    slugs = []
    if BRANDS.is_dir():
        slugs = sorted(p.name for p in BRANDS.iterdir()
                       if (p / "brand.json").is_file() and p.name != HIDDEN_PACK)
    return slugs + [HIDDEN_PACK]


def warnings(pack):
    """What still works but is worth saying."""
    return [str(w) for w in pack.report.warnings]


def required_tokens():
    return validate.required_tokens()
