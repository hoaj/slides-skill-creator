"""The checks an upgraded Slides skill must pass before its PR.

| Check | Fails the gate | Makes the PR a draft |
|---|---|---|
| `deck.py check` for every brand | Errors | |
| A Sample deck for every brand | Build fails | |
| `deck.py compare` old and new Engine, every brand: HTML, PDF and PowerPoint | | A difference, or it could not run |
| The skill's own tests in `<plugin>/tests` | A failure | |

A difference needs the maintainer's approval, and a comparison that could not run (missing
tools, or a Brand pack the old Engine cannot read after a format migration) needs the same.
"""
import pathlib
import subprocess
import sys


def _run(cmd, cwd):
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd), capture_output=True, text=True)


def _last(result):
    lines = (result.stderr or result.stdout).strip().splitlines()
    return lines[-1] if lines else "no output"


def brands(skill):
    folder = pathlib.Path(skill) / "brands"
    return sorted(p.name for p in folder.iterdir() if (p / "brand.json").is_file()) if folder.is_dir() else []


def ignored_rules(deck_py, cwd):
    """The Playbook and Deck type rules that `deck.py check` reports as ignored."""
    output = _run([sys.executable, deck_py, "check"], cwd).stdout
    return sorted({line.strip()[len("warning: "):] for line in output.splitlines()
                   if line.strip().startswith("warning: ") and "ignored" in line})


def run(skill, plugin, before_engine, out):
    """{"checks": [{name, status, detail}], "ignored": [...]}. Status is pass, fail, difference or not run."""
    skill, out = pathlib.Path(skill), pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    deck_py = skill / "engine" / "deck.py"
    checks = []

    # Upgrade never changes SKILL.md's description, so its trigger is the maintainer's to check.
    result = _run([sys.executable, deck_py, "check", "--packs"], out)
    errors = [l.strip() for l in result.stdout.splitlines() if l.strip().startswith("error: ")]
    checks.append({"name": "deck.py check", "status": "pass" if result.returncode == 0 else "fail",
                   "detail": "; ".join(errors) or _last(result)})
    for slug in brands(skill):
        result = _run([sys.executable, deck_py, "sample", "--brand", slug, out / f"{slug}-sample.html"], out)
        checks.append({"name": f"Sample deck for {slug}", "status": "pass" if result.returncode == 0 else "fail",
                       "detail": "" if result.returncode == 0 else _last(result)})
    for slug in brands(skill):
        result = _run([sys.executable, deck_py, "compare", before_engine, skill / "engine", "--brand", slug], out)
        status = {0: "pass", 1: "difference"}.get(result.returncode, "not run")
        detail = result.stdout.strip() if result.returncode in (0, 1) else _last(result)
        checks.append({"name": f"Compare HTML, PDF and PowerPoint for {slug}", "status": status, "detail": detail})
    tests = pathlib.Path(plugin) / "tests"
    if tests.is_dir():
        result = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], plugin)
        checks.append({"name": "The skill's tests", "status": "pass" if result.returncode == 0 else "fail",
                       "detail": _last(result)})
    return {"checks": checks, "ignored": ignored_rules(deck_py, out)}
