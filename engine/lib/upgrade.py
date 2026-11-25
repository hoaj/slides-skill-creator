"""`deck.py upgrade`: fetch a newer Engine release and hand over to that release's upgrade code.

This copy of the Engine only checks the repo, finds the target and verifies it. The merge, the
migrations, the checks and the PR run from the new release, so a fix to Upgrade works on its
first use. Nothing here runs unless asked, so deck builds stay offline.
"""
import pathlib
import shutil
import subprocess
import sys

from . import lock, releases
from .common import SKILL, DeckError

# Folders where coding agents keep installed plugins. Upgrade works on the source repo only.
PLUGIN_CACHES = ((".claude", "plugins"), (".copilot", "installed-plugins"), (".cursor", "plugins"))


def _git(*args):
    return subprocess.run(["git", "-C", str(SKILL), *args], capture_output=True, text=True)


def _in_cache(path):
    parts = path.parts
    return any(parts[i:i + len(c)] == c for c in PLUGIN_CACHES for i in range(len(parts)))


def state_dir():
    result = _git("rev-parse", "--absolute-git-dir")
    if result.returncode:
        raise DeckError("Upgrade runs in the Slides skill's own git repo, and this skill is not in one.")
    return pathlib.Path(result.stdout.strip()) / "slides-upgrade"


def target_version(current, to):
    found = releases.list_versions()
    if to:
        releases.parse(to)
        if to not in [v for v, _ in found]:
            raise DeckError(f"there is no release v{to}")
        return to
    stable = [v for v, prerelease in found if not prerelease]
    if not stable:
        raise DeckError("there is no stable release yet. Name a release candidate with --to.")
    return stable[-1]


def run(to=None, check_only=False):
    if _in_cache(SKILL):
        raise DeckError("this is an installed copy of the skill. Run Upgrade in the skill's own repo.")
    try:
        recorded = lock.read(SKILL / "engine.lock")
    except ValueError as e:
        raise DeckError(str(e))
    current = recorded.get("version") or ""
    state = state_dir()
    releases.check_gh()
    target = target_version(current, to)
    newer = releases.parse(target) > releases.parse(current)

    if check_only:
        print(f"This skill's Engine is {current}. The newest release is {target}.")
        print("Run `deck.py upgrade` to move to it." if newer else "Nothing to upgrade.")
        return 0
    if not newer:
        if target == current:
            print(f"This skill's Engine is already {current}. Nothing to upgrade.")
            return 0
        raise DeckError(f"{target} is older than this skill's Engine {current}. "
                        "Upgrade never downgrades: revert the upgrade's PR instead.")
    if state.exists():
        script = state / "new" / "release" / "upgrade" / "upgrade.py"
        raise DeckError(f"an upgrade is already in progress. Finish it with `python3 {script} continue` "
                        f"or undo it with `python3 {script} abort`.")
    if _git("symbolic-ref", "-q", "HEAD").returncode:
        raise DeckError("Upgrade needs a branch, and HEAD is detached.")
    if _git("status", "--porcelain").stdout.strip():
        raise DeckError("the working tree has uncommitted changes. Commit or stash them first.")

    state.mkdir(parents=True)
    try:
        _, archive_sha = releases.fetch(target, state / "new")
    except Exception:
        shutil.rmtree(str(state), ignore_errors=True)
        raise
    script = state / "new" / "release" / "upgrade" / "upgrade.py"
    return subprocess.call([sys.executable, str(script), "start", "--skill", str(SKILL),
                            "--to", target, "--archive-sha256", archive_sha])
