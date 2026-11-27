"""The three-way merge of the Engine copy and the Starter files.

| Situation | Result |
|---|---|
| Changed only upstream | Take the new version |
| Changed only locally | Keep the local version |
| Changed on both sides | The coding agent merges it and states its decision in the PR |
| New upstream | Add it |
| Removed upstream, Engine file unedited | Remove it |
| Removed upstream, Engine file edited | The coding agent decides |
| Removed upstream, Starter file | Report it, never delete it |

When both sides changed a text file, `git merge-file` writes its best merge, with conflict
markers where the sides disagree. The coding agent still reviews it and states its decision.
"""
import pathlib
import re
import subprocess
import tempfile

MARKERS = ("<<<<<<< local", ">>>>>>> upstream")


def _text(*values):
    try:
        for value in values:
            value.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def merge_file(ours, base, theirs):
    """(merged bytes, clean) from `git merge-file` with diff3 markers."""
    with tempfile.TemporaryDirectory(prefix="slides-merge-") as tmp:
        paths = []
        for name, data in (("local", ours), ("base", base), ("upstream", theirs)):
            path = pathlib.Path(tmp) / name
            path.write_bytes(data)
            paths.append(str(path))
        result = subprocess.run(["git", "merge-file", "-p", "--diff3", "-L", "local", "-L", "base",
                                 "-L", "upstream", *paths], capture_output=True)
    if result.returncode < 0 or result.returncode > 127:
        raise RuntimeError(f"git merge-file failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout, result.returncode == 0


def three_way(base, ours, theirs, target, kind, upstream_dir):
    """Merge {path: bytes} maps into the folder `target` and return what happened to each file.

    `kind` is "engine" or "starter". `upstream_dir` holds the new upstream files, so the coding
    agent can read them when it decides.
    """
    target, upstream_dir = pathlib.Path(target), pathlib.Path(upstream_dir)
    summary = {"taken": [], "kept": [], "added": [], "removed": [], "reported": [], "conflicts": []}
    for path in sorted(set(base) | set(ours) | set(theirs)):
        b, o, t = base.get(path), ours.get(path), theirs.get(path)
        if kind == "starter" and t is None and b is not None:
            if o is not None:
                summary["reported"].append(path)
            continue
        if o == t:
            continue
        if b == o:
            if t is None:
                (target / path).unlink()
                summary["removed"].append(path)
            else:
                (target / path).parent.mkdir(parents=True, exist_ok=True)
                (target / path).write_bytes(t)
                summary["added" if b is None else "taken"].append(path)
            continue
        if b == t:
            summary["kept"].append(path)
            continue
        conflict = {"path": path, "kind": kind, "markers": False,
                    "upstream": str(upstream_dir / path) if t is not None else None}
        if None not in (b, o, t) and _text(b, o, t):
            merged, clean = merge_file(o, b, t)
            (target / path).write_bytes(merged)
            conflict["markers"] = not clean
            conflict["reason"] = ("Both sides changed it. Upgrade merged the changes without "
                                  "conflicts; check that the result is right." if clean else
                                  "Both sides changed it. Conflict markers show where they disagree.")
        elif t is None:
            conflict["reason"] = "It was removed upstream but edited here. Keep, adapt or remove it."
        elif o is None:
            conflict["reason"] = "It was removed here but changed upstream. Restore it or leave it out."
        elif b is None:
            conflict["reason"] = "It was added on both sides with different content. The local file is kept."
        else:
            conflict["reason"] = "Both sides changed this binary file. The local file is kept."
        summary["conflicts"].append(conflict)
    return summary


def has_markers(path):
    path = pathlib.Path(path)
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return any(line.startswith(MARKERS) for line in text.splitlines())


# --- what Upgrade never changes in SKILL.md --------------------------------------------------

FRONT_MATTER = re.compile(r"\A---\n(.*?\n)---\n", re.S)
LOCAL_RULES = re.compile(r"^## Local rules\n.*?(?=^## |\Z)", re.M | re.S)


def _field(front, name):
    m = re.search(rf"^{name}:.*$", front, re.M)
    return m.group(0) if m else None


def protected(text):
    """The `name` and `description` lines and the `## Local rules` section of a SKILL.md."""
    front = FRONT_MATTER.match(text)
    rules = LOCAL_RULES.search(text)
    return {"name": _field(front.group(1), "name") if front else None,
            "description": _field(front.group(1), "description") if front else None,
            "localRules": rules.group(0) if rules else None}


def restore(text, kept):
    """`text` with the protected parts put back as they were before the merge."""
    current = protected(text)
    for key in ("name", "description"):
        if kept[key] and current[key] and current[key] != kept[key]:
            text = text.replace(current[key], kept[key], 1)
    if kept["localRules"] and current["localRules"] and current["localRules"] != kept["localRules"]:
        text = text.replace(current["localRules"], kept["localRules"], 1)
    return text
