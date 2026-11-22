#!/usr/bin/env python3
"""Render the Starter files and assemble a Slides skill.

    python3 starter/render.py --values values.json --brand brands/acme --out <folder>

values.json holds `skill`, `description`, `repo` and `author`, and optionally `version`
(default 0.1.0) and `layout`: `standalone` makes the output a repo that is its own marketplace,
and `shared` places the plugin in `plugins/<skill>` of a repo that already has a marketplace.

`render_files` is pure, so Upgrade can render a release's Starter files with the values
recorded in `engine.lock` and compare them. Uses only the standard library.
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
ENGINE = ROOT / "engine"
TEMPLATES = HERE / "files"

sys.path.insert(0, str(ENGINE))

from lib import lock  # noqa: E402
from lib.validate import FORMAT_VERSION  # noqa: E402

SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*-slides")
REPO_NAME = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
VERSION = re.compile(r"\d+\.\d+\.\d+")
TOKEN = re.compile(r"__[A-Z][A-Z_]*__")
MARKER = re.compile(r"^(\s*)#@(standalone|shared) ?(.*)$")
# Agent skill names stop at 64 characters, and the feedback skill adds "-feedback".
MAX_SKILL_NAME = 64 - len("-feedback")
MAX_DESCRIPTION = 1024


class StarterError(Exception):
    """A problem with the values or the output folder that the caller can fix."""


def normalise(values):
    """The complete, validated Starter values."""
    known = {"skill", "description", "repo", "author", "version", "layout"}
    unknown = sorted(set(values) - known)
    if unknown:
        raise StarterError(f"unknown value(s): {', '.join(unknown)}")
    missing = [k for k in ("skill", "description", "repo", "author") if not values.get(k)]
    if missing:
        raise StarterError(f"missing value(s): {', '.join(missing)}")
    out = {"version": "0.1.0", "layout": "standalone", **values}
    if any(not isinstance(v, str) for v in out.values()):
        raise StarterError("every value must be a string")
    if not SKILL_NAME.fullmatch(out["skill"]) or len(out["skill"]) > MAX_SKILL_NAME:
        raise StarterError(f"skill must look like <name>-slides, at most {MAX_SKILL_NAME} "
                           f"characters of a-z, 0-9 and hyphens: {out['skill']!r}")
    if not REPO_NAME.fullmatch(out["repo"]):
        raise StarterError(f"repo must be owner/name: {out['repo']!r}")
    if not VERSION.fullmatch(out["version"]):
        raise StarterError(f"version must be X.Y.Z: {out['version']!r}")
    if out["layout"] not in ("standalone", "shared"):
        raise StarterError(f"layout must be standalone or shared: {out['layout']!r}")
    for key in ("description", "author"):
        if any(ord(c) < 32 for c in out[key]):
            raise StarterError(f"{key} must be a single line")
    if len(out["description"]) > MAX_DESCRIPTION:
        raise StarterError(f"description is over {MAX_DESCRIPTION} characters")
    return out


def plugin_dir(values):
    return "." if values["layout"] == "standalone" else f"plugins/{values['skill']}"


def _tokens(values):
    # JSON strings are also valid YAML double-quoted strings, so one form serves the manifests
    # and the SKILL.md frontmatter.
    return {
        "__SKILL__": values["skill"],
        "__REPO__": values["repo"],
        "__VERSION__": values["version"],
        "__PLUGIN_DIR__": plugin_dir(values),
        "__TAG_PREFIX__": "v" if values["layout"] == "standalone" else f"{values['skill']}-v",
        "__DESCRIPTION_JSON__": json.dumps(values["description"], ensure_ascii=False),
        "__AUTHOR_JSON__": json.dumps(values["author"], ensure_ascii=False),
    }


def _substitute(text, tokens, where):
    def replace(match):
        if match.group(0) not in tokens:
            raise StarterError(f"{where}: unknown token {match.group(0)}")
        return tokens[match.group(0)]
    # One pass, so a value that happens to contain a token is left alone.
    return TOKEN.sub(replace, text)


def _apply_markers(text, layout):
    lines = []
    for line in text.splitlines(keepends=True):
        match = MARKER.match(line)
        if not match:
            lines.append(line)
        elif match.group(2) == layout:
            ending = "\n" if line.endswith("\n") else ""
            lines.append(f"{match.group(1)}{match.group(3)}{ending}")
    return "".join(lines)


def render_files(values):
    """{path relative to the repo root: text} for every Starter file."""
    values = normalise(values)
    tokens = _tokens(values)
    prefixes = {"plugin": pathlib.PurePosixPath(plugin_dir(values)),
                "repo": pathlib.PurePosixPath(".")}
    if values["layout"] == "standalone":
        prefixes["marketplace"] = pathlib.PurePosixPath(".")
    rendered = {}
    for group, prefix in prefixes.items():
        base = TEMPLATES / group
        for path in sorted(p for p in base.rglob("*") if p.is_file() and p.name != ".DS_Store"):
            relative = path.relative_to(base).as_posix()
            text = _apply_markers(path.read_text(encoding="utf-8"), values["layout"])
            target = prefix / _substitute(relative, tokens, relative)
            rendered[target.as_posix()] = _substitute(text, tokens, relative)
    return rendered


def _source_commit():
    """This checkout's commit, or None when the Generator is not its own git checkout."""
    def git(*args):
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    try:
        top = git("rev-parse", "--show-toplevel")
        if top.returncode or pathlib.Path(top.stdout.strip()).resolve() != ROOT:
            return None
        head = git("rev-parse", "HEAD")
    except OSError:
        return None
    return head.stdout.strip() if head.returncode == 0 else None


def lock_data(values):
    """engine.lock for this Engine. `archiveSha256` stays null until it comes from a release."""
    return {
        "version": (ENGINE / "VERSION").read_text(encoding="utf-8").strip(),
        "commit": _source_commit(),
        "archiveSha256": None,
        "engineTreeHash": lock.tree_hash(ENGINE),
        "starterTreeHash": lock.tree_hash(HERE),
        "formatVersion": FORMAT_VERSION,
        "starterValues": normalise(values),
        "engineFiles": lock.file_hashes(ENGINE),
    }


def create(values, out, brands):
    """Write a whole Slides skill to `out`. Nothing is written when any target already exists."""
    values = normalise(values)
    out = pathlib.Path(out).resolve()
    if not brands:
        raise StarterError("at least one Brand pack is needed")
    brand_dirs = [pathlib.Path(b).resolve() for b in brands]
    for brand in brand_dirs:
        if not (brand / "brand.json").is_file():
            raise StarterError(f"not a Brand pack (no brand.json): {brand}")
        if brand.name == "plain":
            raise StarterError("`plain` is the Engine's hidden test pack and cannot be added")
    if len({b.name for b in brand_dirs}) != len(brand_dirs):
        raise StarterError("two Brand packs have the same folder name")

    files = render_files(values)
    skill_dir = out / plugin_dir(values) / "skills" / values["skill"]
    targets = [out / path for path in files] + [skill_dir / "engine", skill_dir / "engine.lock"]
    targets += [skill_dir / "brands" / b.name for b in brand_dirs]
    taken = [str(t) for t in targets if t.exists()]
    if taken:
        raise StarterError("already exists, nothing was written: " + ", ".join(taken))

    for path, text in files.items():
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    shutil.copytree(ENGINE, skill_dir / "engine", ignore=ignore)
    for brand in brand_dirs:
        shutil.copytree(brand, skill_dir / "brands" / brand.name, ignore=ignore)
    (skill_dir / "engine.lock").write_bytes(
        (json.dumps(lock_data(values), indent=2) + "\n").encode("utf-8"))
    return {"skill": values["skill"], "layout": values["layout"], "skillDir": str(skill_dir),
            "starterFiles": sorted(files), "brands": sorted(b.name for b in brand_dirs)}


def main(argv=None):
    p = argparse.ArgumentParser(description="Render the Starter files into a new Slides skill.")
    p.add_argument("--values", required=True, help="JSON file with the Starter values")
    p.add_argument("--brand", action="append", required=True, help="Brand pack folder (repeatable)")
    p.add_argument("--out", required=True, help="the repo folder to write into")
    args = p.parse_args(argv)
    try:
        values = json.loads(pathlib.Path(args.values).read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise StarterError("the values file must hold a JSON object")
        print(json.dumps(create(values, args.out, args.brand), indent=2))
    except (StarterError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
