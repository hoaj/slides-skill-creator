#!/usr/bin/env python3
"""Check the version and build the release assets.

    python3 scripts/release.py check-version [--base <git ref>]
    python3 scripts/release.py plan
    python3 scripts/release.py build --out <folder>

One version covers the Engine and the Generator. It lives in engine/VERSION and the three
plugin manifests, which must agree. It is X.Y.Z, X.Y.Z-rc.N, or X.Y.Z-dev before the first
release; a -dev version is never released.

`build` writes slides-skill-X.Y.Z.tar.gz, release-manifest.json and SHA256SUMS. The archive is
reproducible: the same commit gives the same bytes. Uses only the standard library.
"""
import argparse
import gzip
import hashlib
import io
import json
import pathlib
import re
import subprocess
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from lib import lock, releases  # noqa: E402

MANIFESTS = (".claude-plugin/plugin.json", ".cursor-plugin/plugin.json", ".github/plugin/plugin.json")
# What a user installs or Upgrade receives. A pull request that changes one must raise the version.
SHIPPED = ("engine", "starter", "upgrade", "migrations", "skills", "brands", "examples",
           ".claude-plugin", ".cursor-plugin", ".github/plugin", "LICENSE")
# The archive's top-level folders, the ones Upgrade unpacks.
ARCHIVE_FOLDERS = releases.ARCHIVE_FOLDERS
VERSION = releases.VERSION


class ReleaseError(Exception):
    pass


def parse(version):
    """A sort key: X.Y.Z-dev < X.Y.Z-rc.1 < X.Y.Z-rc.2 < X.Y.Z."""
    try:
        return releases.parse(version)
    except releases.ReleaseError as e:
        raise ReleaseError(str(e))


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if result.returncode:
        raise ReleaseError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def released(root):
    """Released versions from the vX.Y.Z tags, lowest first."""
    versions = []
    for tag in _git(root, "tag", "--list", "v*").split():
        if VERSION.fullmatch(tag[1:]):
            versions.append(tag[1:])
    return sorted(versions, key=parse)


def version(root):
    """The one version, after checking that engine/VERSION and every manifest agree."""
    root = pathlib.Path(root)
    found = {"engine/VERSION": (root / "engine/VERSION").read_text(encoding="utf-8").strip()}
    for manifest in MANIFESTS:
        found[manifest] = json.loads((root / manifest).read_text(encoding="utf-8")).get("version")
    if len(set(found.values())) != 1:
        raise ReleaseError("the versions differ: " + ", ".join(f"{k} has {v}" for k, v in found.items()))
    value = found["engine/VERSION"]
    parse(value)
    return value


def check_version(root, base=None):
    """The version, after the rules a pull request or a push to main must meet."""
    current = version(root)
    tags = released(root)
    if current.endswith("-dev") and tags:
        raise ReleaseError(f"{current} is a -dev version, which is only allowed before the first release")
    if base is None:
        return current
    changed = _git(root, "diff", "--name-only", f"{base}...HEAD", "--", *SHIPPED).split()
    if not changed or current.endswith("-dev"):
        return current
    floors = list(tags)
    try:
        floors.append(_git(root, "show", f"{base}:engine/VERSION").strip())
    except ReleaseError:
        pass
    floor = max(floors, key=parse, default=None)
    if floor is not None and parse(current) <= parse(floor):
        raise ReleaseError(f"shipped files changed ({changed[0]} and {len(changed) - 1} more), "
                           f"so the version must rise above {floor} (now {current})")
    return current


def plan(root):
    """What the release workflow does for this commit."""
    current = version(root)
    tags = released(root)
    lower = [v for v in tags if parse(v) < parse(current)]
    return {
        "version": current,
        "tag": f"v{current}",
        "release": not current.endswith("-dev") and current not in tags,
        "prerelease": "-" in current,
        "previous": f"v{lower[-1]}" if lower else "",
    }


def format_version(root):
    """The Brand pack format of the Engine in `root`, read from its source rather than imported."""
    text = (root / "engine" / "lib" / "validate.py").read_text(encoding="utf-8")
    m = re.search(r"^FORMAT_VERSION = (\d+)$", text, re.M)
    if not m:
        raise ReleaseError("engine/lib/validate.py has no FORMAT_VERSION")
    return int(m.group(1))


def _archive_files(root):
    """{archive path: bytes} for every file the archive holds, with lock's ignore rules."""
    files = {}
    for folder in ARCHIVE_FOLDERS:
        path = root / folder
        if not path.is_dir():
            raise ReleaseError(f"{folder}/ is missing")
        for relative in lock.file_hashes(path):
            files[f"{folder}/{relative}"] = (path / relative).read_bytes()
    return dict(sorted(files.items()))


def _tarball(files):
    """A gzipped tar that depends only on the files: sorted, no timestamps, owners or modes."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    packed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=packed, compresslevel=9, mtime=0) as gz:
        gz.write(raw.getvalue())
    return packed.getvalue()


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def build(root, out):
    """Write the three release assets to `out` and return their names."""
    root = pathlib.Path(root)
    current = version(root)
    dirty = [line for line in _git(root, "status", "--porcelain", "--", *ARCHIVE_FOLDERS).splitlines()
             if not lock._ignored(pathlib.PurePosixPath(line[3:].strip('"')))]
    if dirty:
        raise ReleaseError("uncommitted changes would not match the commit: " + "; ".join(dirty))

    files = _archive_files(root)
    archive = releases.archive_name(current)
    manifest = {
        "version": current,
        "commit": _git(root, "rev-parse", "HEAD").strip(),
        "engineTreeHash": lock.tree_hash(root / "engine"),
        "starterTreeHash": lock.tree_hash(root / "starter"),
        "formatVersion": format_version(root),
        "files": {name: _sha256(data) for name, data in files.items()},
    }
    assets = {
        archive: _tarball(files),
        "release-manifest.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
    }
    assets["SHA256SUMS"] = "".join(f"{_sha256(data)}  {name}\n"
                                   for name, data in sorted(assets.items())).encode("utf-8")
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in assets.items():
        (out / name).write_bytes(data)
    return sorted(assets)


def main(argv=None):
    p = argparse.ArgumentParser(description="Check the version and build the release assets.")
    sub = p.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-version", help="the version rules for a pull request or push")
    check.add_argument("--base", help="the pull request's base, such as origin/main")
    sub.add_parser("plan", help="print what the release workflow does, as key=value lines")
    make = sub.add_parser("build", help="write the release assets")
    make.add_argument("--out", required=True, help="folder for the assets")
    args = p.parse_args(argv)
    try:
        if args.command == "check-version":
            print(check_version(ROOT, args.base))
        elif args.command == "plan":
            for key, value in plan(ROOT).items():
                print(f"{key}={str(value).lower() if isinstance(value, bool) else value}")
        else:
            for name in build(ROOT, args.out):
                print(name)
    except (ReleaseError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
