"""Create a Slides skill, add a Brand pack to one, and change its trigger description.

`new --dir` makes a repo that is its own marketplace. `new --into` adds the skill to
`plugins/<skill>` of a repo that already has a marketplace, and lists it there.
"""
import json
import pathlib
import shutil

from . import pack as packs
from .common import HIDDEN_PACK, GenError, read_json, write_json, write_text

MARKETPLACES = (".claude-plugin/marketplace.json", ".cursor-plugin/marketplace.json",
                ".github/plugin/marketplace.json")
MANIFESTS = (".claude-plugin/plugin.json", ".cursor-plugin/plugin.json", ".github/plugin/plugin.json")


def _render():
    import render
    return render


def _values(skill, description, repo, author, layout):
    render = _render()
    try:
        return render.normalise({"skill": skill, "description": description, "repo": repo,
                                 "author": author, "layout": layout})
    except render.StarterError as e:
        raise GenError(str(e))


def _create(values, out, brand):
    render = _render()
    try:
        return render.create(values, out, [brand])
    except render.StarterError as e:
        raise GenError(str(e))


def _next(skill_dir, slug):
    engine = pathlib.Path(skill_dir) / "engine" / "deck.py"
    return [f"python3 {engine} check",
            f"python3 {engine} sample --brand {slug} <folder outside the skill>/{slug}-sample.html --open"]


def new_dir(folder, skill, description, repo, author, brand):
    """A standalone Slides skill repo in `folder`, which is missing, empty or holds only .git."""
    values = _values(skill, description, repo, author, "standalone")
    brand = pathlib.Path(brand).resolve()
    packs.require_valid(brand)
    folder = pathlib.Path(folder).resolve()
    if folder.exists():
        extra = sorted(p.name for p in folder.iterdir() if p.name != ".git")
        if extra:
            raise GenError(f"{folder} must be empty or hold only .git, nothing was written; it holds: "
                           + ", ".join(extra))
    result = _create(values, folder, brand)
    result.update({"root": str(folder), "next": _next(result["skillDir"], brand.name)})
    return result


def _shared_marketplaces(root, skill):
    """{path: parsed marketplace} for every marketplace file at the root, checked before writing."""
    found = {}
    for rel in MARKETPLACES:
        path = root / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise GenError(f"{rel} is not valid JSON ({e}), nothing was written")
        if not (isinstance(data, dict) and isinstance(data.get("name"), str)
                and isinstance(data.get("plugins"), list)):
            raise GenError(f"{rel} has no `name` or no `plugins` list, nothing was written")
        if any(isinstance(p, dict) and p.get("name") == skill for p in data["plugins"]):
            raise GenError(f"{rel} already lists {skill}, nothing was written")
        found[rel] = data
    if not found:
        raise GenError(f"{root} has no marketplace file ({', '.join(MARKETPLACES)}), so it is not a "
                       "shared marketplace repo. Use --dir for a repo of its own.")
    return found


def new_into(root, skill, description, repo, author, brand):
    """The Slides skill in plugins/<skill> of a shared marketplace repo, listed in its marketplaces."""
    values = _values(skill, description, repo, author, "shared")
    brand = pathlib.Path(brand).resolve()
    packs.require_valid(brand)
    root = pathlib.Path(root).resolve()
    marketplaces = _shared_marketplaces(root, values["skill"])
    result = _create(values, root, brand)
    entry = {"name": values["skill"], "source": f"./plugins/{values['skill']}",
             "description": values["description"]}
    for rel, data in marketplaces.items():
        data["plugins"].append(dict(entry))
        write_json(root / rel, data)
    result.update({"root": str(root), "marketplaces": sorted(marketplaces),
                   "next": _next(result["skillDir"], brand.name)})
    return result


class Skill:
    """A Slides skill folder: <plugin>/skills/<skill>, with its Engine copy and engine.lock."""

    def __init__(self, folder):
        self.dir = pathlib.Path(folder).resolve()
        for needed in ("SKILL.md", "engine.lock", "engine/deck.py"):
            if not (self.dir / needed).is_file():
                raise GenError(f"not a Slides skill (no {needed}): {self.dir}. Give the folder that "
                               "holds the skill's SKILL.md, <plugin>/skills/<skill>.")
        self.lock = read_json(self.dir / "engine.lock")
        self.values = self.lock.get("starterValues") or {}
        if self.values.get("skill") != self.dir.name:
            raise GenError(f"engine.lock names skill {self.values.get('skill')!r}, but the folder is "
                           f"{self.dir.name!r}")
        self.plugin = self.dir.parent.parent
        self.root = self.plugin if self.values.get("layout") == "standalone" else self.plugin.parent.parent

    def brands(self):
        folder = self.dir / "brands"
        return sorted(p.name for p in folder.iterdir()
                      if (p / "brand.json").is_file()) if folder.is_dir() else []


def add_brand(skill_dir, brand):
    """Copy a valid Brand pack into the skill's brands/."""
    from lib.validate import FORMAT_VERSION
    skill = Skill(skill_dir)
    brand = pathlib.Path(brand).resolve()
    if brand.name == HIDDEN_PACK:
        raise GenError("`plain` is the Engine's hidden test pack and cannot be added")
    if skill.lock.get("formatVersion") != FORMAT_VERSION:
        raise GenError(f"the skill's Engine supports Brand pack format {skill.lock.get('formatVersion')}, "
                       f"and this Generator writes format {FORMAT_VERSION}. Upgrade the skill first: "
                       f"python3 {skill.dir / 'engine' / 'deck.py'} upgrade")
    packs.require_valid(brand)
    target = skill.dir / "brands" / brand.name
    if target.exists():
        raise GenError(f"the skill already has a Brand pack named {brand.name!r}; use edit-brand, "
                       "or choose another slug")
    shutil.copytree(brand, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    return {"skillDir": str(skill.dir), "added": brand.name, "brands": skill.brands(),
            "description": skill.values.get("description"),
            "next": [f"propose a new description naming every brand, then: python3 <gen>/tools/gen.py "
                     f"describe --skill-dir {skill.dir} --description \"<text>\""]
            + _next(skill.dir, brand.name)}


def bump(skill_dir, part):
    """Raise the version in the three plugin manifests and in engine.lock's Starter values."""
    import re
    skill = Skill(skill_dir)
    manifests = [skill.plugin / m for m in MANIFESTS]
    versions = {str(m): read_json(m).get("version") for m in manifests if m.is_file()}
    if len(set(versions.values())) != 1:
        raise GenError("the manifests disagree on the version; make them equal first", versions=versions)
    old = next(iter(versions.values()))
    if not (isinstance(old, str) and re.fullmatch(r"\d+\.\d+\.\d+", old)):
        raise GenError(f"the manifests' version is not X.Y.Z: {old!r}")
    major, minor, patch = (int(n) for n in old.split("."))
    new = {"major": f"{major + 1}.0.0", "minor": f"{major}.{minor + 1}.0",
           "patch": f"{major}.{minor}.{patch + 1}"}[part]
    for path in manifests:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            write_text(path, text.replace(f'"version": "{old}"', f'"version": "{new}"', 1))
    skill.lock["starterValues"]["version"] = new
    write_text(skill.dir / "engine.lock", json.dumps(skill.lock, indent=2) + "\n")
    return {"skillDir": str(skill.dir), "from": old, "to": new,
            "changed": [str(p) for p in manifests if p.is_file()] + [str(skill.dir / "engine.lock")]}


def describe(skill_dir, description):
    """Change the trigger description everywhere the Starter files hold it, and in engine.lock.

    engine.lock keeps the Starter values Upgrade renders from, so they must follow the change.
    """
    skill = Skill(skill_dir)
    old = skill.values.get("description")
    values = _values(skill.values["skill"], description, skill.values["repo"],
                     skill.values["author"], skill.values["layout"])
    if values["description"] == old:
        return {"skillDir": str(skill.dir), "changed": [], "unchanged": []}
    old_json = json.dumps(old, ensure_ascii=False)
    new_json = json.dumps(values["description"], ensure_ascii=False)

    files = [skill.dir / "SKILL.md"] + [skill.plugin / m for m in MANIFESTS]
    if values["layout"] == "standalone":
        files += [skill.plugin / m for m in MARKETPLACES]
    changed, unchanged = [], []
    edits = {}
    for path in files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if old_json in text:
            edits[path] = text.replace(old_json, new_json)
        else:
            unchanged.append(str(path))
    shared = {}
    if values["layout"] == "shared":
        for rel in MARKETPLACES:
            path = skill.root / rel
            if not path.is_file():
                continue
            data = read_json(path)
            entries = [p for p in data.get("plugins", [])
                       if isinstance(p, dict) and p.get("name") == values["skill"]]
            if entries:
                for e in entries:
                    e["description"] = values["description"]
                shared[path] = data
            else:
                unchanged.append(str(path))

    for path, text in edits.items():
        write_text(path, text)
        changed.append(str(path))
    for path, data in shared.items():
        write_json(path, data)
        changed.append(str(path))
    skill.lock["starterValues"]["description"] = values["description"]
    # The same form starter/render.py writes, so the file differs only in the description.
    write_text(skill.dir / "engine.lock", json.dumps(skill.lock, indent=2) + "\n")
    changed.append(str(skill.dir / "engine.lock"))
    result = {"skillDir": str(skill.dir), "changed": changed, "unchanged": unchanged}
    if unchanged:
        result["warning"] = ("the old description was not found in these files, so they were left as "
                             "they are; update them by hand")
    return result
