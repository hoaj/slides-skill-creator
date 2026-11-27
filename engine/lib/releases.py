"""Find, fetch and verify the Engine's public releases with `gh`.

A release holds slides-skill-X.Y.Z.tar.gz, release-manifest.json and SHA256SUMS. `fetch` trusts
it only after GitHub confirms the release is immutable, each asset belongs to it, and this repo's
release workflow built it. It then checks every hash and unpacks plain files only.
Uses only the standard library, so Upgrade and the release tools can share it.
"""
import hashlib
import json
import pathlib
import re
import subprocess
import tarfile

REPO = "hoaj/slides-skill-creator"
SIGNER = f"{REPO}/.github/workflows/release.yml"
GH_MINIMUM = (2, 81, 0)
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-(dev|rc\.(\d+)))?")
ARCHIVE_FOLDERS = ("engine", "starter", "upgrade", "migrations")
MANIFEST = "release-manifest.json"
SUMS = "SHA256SUMS"


class ReleaseError(Exception):
    pass


def parse(version):
    """A sort key: X.Y.Z-dev < X.Y.Z-rc.1 < X.Y.Z-rc.2 < X.Y.Z."""
    m = VERSION.fullmatch(version or "")
    if not m:
        raise ReleaseError(f"{version!r} is not X.Y.Z, X.Y.Z-rc.N or X.Y.Z-dev")
    major, minor, patch, pre, rc = m.groups()
    stage = (2, 0) if pre is None else (0, 0) if pre == "dev" else (1, int(rc))
    return (int(major), int(minor), int(patch)) + stage


def archive_name(version):
    return f"slides-skill-{version}.tar.gz"


def gh(*args, check=True):
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise ReleaseError("`gh` is not installed. Install the GitHub CLI 2.81 or later.")
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise ReleaseError(f"`gh {' '.join(args[:2])}` failed: {detail[-1] if detail else 'no output'}")
    return result


def check_gh():
    """Stop unless `gh` 2.81 or later is installed: older versions cannot verify releases."""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", gh("--version").stdout)
    if not m or tuple(int(n) for n in m.groups()) < GH_MINIMUM:
        raise ReleaseError("Upgrade needs `gh` 2.81 or later to verify releases. Run `gh --version`.")


def list_versions():
    """[(version, prerelease)] of every release, lowest first. Tags that are not vX.Y.Z are skipped."""
    out = gh("release", "list", "-R", REPO, "--json", "tagName,isPrerelease", "--limit", "200").stdout
    found = []
    for item in json.loads(out or "[]"):
        tag = item.get("tagName", "")
        if tag.startswith("v") and VERSION.fullmatch(tag[1:]):
            found.append((tag[1:], bool(item.get("isPrerelease"))))
    return sorted(found, key=lambda pair: parse(pair[0]))


def notes(version):
    return gh("release", "view", f"v{version}", "-R", REPO, "--json", "body", "-q", ".body").stdout.strip()


def _sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _extract(archive, dest, expected):
    """Unpack only the regular files the manifest lists, each inside one of the four folders."""
    with tarfile.open(str(archive), "r:gz") as tar:
        members = tar.getmembers()
        names = set()
        for m in members:
            path = pathlib.PurePosixPath(m.name)
            if (not m.isfile() or path.is_absolute() or ".." in path.parts
                    or path.parts[0] not in ARCHIVE_FOLDERS):
                raise ReleaseError(f"the archive holds an unexpected entry: {m.name}")
            names.add(m.name)
        if names != set(expected):
            raise ReleaseError("the archive's files differ from release-manifest.json")
        for m in members:
            data = tar.extractfile(m).read()
            if hashlib.sha256(data).hexdigest() != expected[m.name]:
                raise ReleaseError(f"{m.name} does not match its hash in release-manifest.json")
            target = dest / m.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def fetch(version, dest):
    """Download and verify release vX.Y.Z into dest. Returns (manifest, archive sha256).

    dest/assets holds the three assets and dest/release the unpacked archive.
    """
    tag = f"v{version}"
    dest = pathlib.Path(dest)
    assets, unpacked = dest / "assets", dest / "release"
    assets.mkdir(parents=True)
    gh("release", "download", tag, "-R", REPO, "-D", str(assets))
    archive = assets / archive_name(version)
    for path in (archive, assets / MANIFEST, assets / SUMS):
        if not path.is_file():
            raise ReleaseError(f"release {tag} has no {path.name}")
    gh("release", "verify", tag, "-R", REPO)
    for path in (archive, assets / MANIFEST, assets / SUMS):
        gh("release", "verify-asset", tag, str(path), "-R", REPO)
        gh("attestation", "verify", str(path), "--repo", REPO, "--signer-workflow", SIGNER)

    sums = {}
    for line in (assets / SUMS).read_text(encoding="utf-8").splitlines():
        sha, _, name = line.partition("  ")
        sums[name] = sha
    for path in (archive, assets / MANIFEST):
        if sums.get(path.name) != _sha256(path):
            raise ReleaseError(f"{path.name} does not match SHA256SUMS")
    manifest = json.loads((assets / MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("version") != version:
        raise ReleaseError(f"release {tag} has a manifest for version {manifest.get('version')}")
    unpacked.mkdir()
    _extract(archive, unpacked, manifest.get("files") or {})
    return manifest, _sha256(archive)
