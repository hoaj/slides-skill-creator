"""Hash a folder of files and read `engine.lock`.

The hashes must stay stable: `engine.lock`, the release manifest and Upgrade all compare them.
This module takes every path as an argument and imports only the standard library, so the
Starter renderer and the release tools can use it too.
"""
import hashlib
import json
import pathlib

IGNORED_DIRS = {"__pycache__"}
IGNORED_NAMES = {".DS_Store"}
IGNORED_SUFFIXES = (".pyc",)


def _ignored(relative):
    return (any(part in IGNORED_DIRS for part in relative.parts)
            or relative.name in IGNORED_NAMES
            or relative.name.endswith(IGNORED_SUFFIXES))


def file_hashes(root):
    """{posix path relative to root: sha256 of the file's bytes}, sorted by path."""
    root = pathlib.Path(root)
    found = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_file() and not _ignored(relative):
            found[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(found.items()))


def tree_hash(root):
    """One sha256 for a folder's file paths and contents."""
    digest = hashlib.sha256()
    for path, sha in file_hashes(root).items():
        digest.update(f"{path}\0{sha}\n".encode("utf-8"))
    return digest.hexdigest()


def read(path):
    """The parsed lock. Raises ValueError when it is not a usable engine.lock."""
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"cannot read {path}: {e}")
    files = data.get("engineFiles") if isinstance(data, dict) else None
    if not isinstance(files, dict) or not all(isinstance(v, str) for v in files.values()):
        raise ValueError(f"{path}: engineFiles is missing or not a map of hashes")
    return data


def local_edits(engine, recorded):
    """(edited, removed, added count) of the Engine copy against a parsed lock.

    Added files are only counted: their names are the maintainer's own and may identify a
    brand, while edited and removed names come from the public Engine.
    """
    current = file_hashes(engine)
    expected = recorded["engineFiles"]
    edited = sorted(p for p, sha in expected.items() if p in current and current[p] != sha)
    removed = sorted(p for p in expected if p not in current)
    added = sum(1 for p in current if p not in expected)
    return edited, removed, added
