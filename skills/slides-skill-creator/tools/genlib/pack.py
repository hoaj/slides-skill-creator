"""Start a Brand pack and validate one that is not yet in a Slides skill.

A draft pack is validated with this Generator's Engine, the same validator `deck.py check` runs.
"""
import pathlib
import re
import shutil

from .common import ENGINE, HIDDEN_PACK, SLUG, GenError, read_json, write_json, write_text

PLAIN = ENGINE / "fixtures" / HIDDEN_PACK


def load(folder):
    """The Engine's Pack object for any folder that holds a brand.json."""
    from lib import packs
    root = pathlib.Path(folder).resolve()
    if not (root / "brand.json").is_file():
        raise GenError(f"not a Brand pack (no brand.json): {root}")
    manifest = read_json(root / "brand.json")
    if not isinstance(manifest, dict):
        raise GenError(f"{root / 'brand.json'}: must be a JSON object")
    return packs.Pack(root.name, root, manifest)


def check(folder):
    """{valid, errors, warnings} from the Engine's validator."""
    from lib import validate
    pack = load(folder)
    report = validate.validate(pack)
    return {"pack": str(pack.root), "valid": not report.errors,
            "errors": [str(p) for p in report.errors],
            "warnings": [str(p) for p in report.warnings]}


def require_valid(folder):
    result = check(folder)
    if not result["valid"]:
        raise GenError("the Brand pack is not valid; fix every error, then run the command again",
                       errors=result["errors"])
    return result


def init(out, slug, name, aliases):
    """A pack skeleton copied from the Engine's plain pack, renamed to `slug`."""
    out = pathlib.Path(out).resolve()
    if not re.fullmatch(SLUG, slug):
        raise GenError(f"slug must be lowercase a-z, 0-9 and hyphens: {slug!r}")
    if slug == HIDDEN_PACK:
        raise GenError("`plain` is the Engine's hidden test pack; choose another slug")
    if out.name != slug:
        raise GenError(f"the pack's folder must be named after its slug: {out.name!r} is not {slug!r}")
    if out.exists() and any(out.iterdir()):
        raise GenError(f"already exists and is not empty, nothing was written: {out}")
    if not name.strip():
        raise GenError("name must not be empty")

    tokens = (PLAIN / "tokens.css").read_text(encoding="utf-8")
    tokens = tokens.replace(f"--{HIDDEN_PACK}-", f"--{slug}-")
    tokens = re.sub(r"\A/\*.*?\*/", f"/* === {name}: Brand pack tokens ===\n"
                    "   Semantic tokens remap per theme through [data-theme] on .deck-stage\n"
                    "   (deck-wide) or a .slide (per slide). */", tokens, count=1, flags=re.S)
    manifest = read_json(PLAIN / "brand.json")
    manifest.update({"slug": slug, "name": name, "aliases": list(aliases),
                     "classifications": ["INTERNAL", "PUBLIC", "none"],
                     "defaultClassification": "INTERNAL"})

    (out / "assets").mkdir(parents=True, exist_ok=True)
    write_text(out / "tokens.css", tokens)
    write_json(out / "brand.json", manifest)
    shutil.copyfile(PLAIN / "assets" / "logo.svg", out / "assets" / "logo.svg")
    return {
        "pack": str(out),
        "written": ["brand.json", "tokens.css", "assets/logo.svg"],
        "todo": [
            "Replace assets/logo.svg with the brand's single-colour SVG logo (fill=\"currentColor\").",
            "Set the palette and one [data-theme] rule per theme in tokens.css, and the same themes in brand.json.",
            "Write brand.md with the brand's design rules.",
            "Run `fonts` for font files and `icons` for an icon set, when the brand has them.",
            "Run `guard` to write the contrast data, then `pack-check`.",
        ],
    }
