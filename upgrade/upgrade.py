#!/usr/bin/env python3
"""Upgrade a Slides skill to this release's Engine and Starter files, in a PR.

`deck.py upgrade` verifies this release, unpacks it in <git dir>/slides-upgrade/new and starts
this script, so the new release's own code does the upgrade:

    python3 <state>/new/release/upgrade/upgrade.py start --skill <dir> --to X.Y.Z --archive-sha256 <sha>
    python3 <state>/new/release/upgrade/upgrade.py continue [--draft]
    python3 <state>/new/release/upgrade/upgrade.py abort

`start` merges three ways on a new branch, with the release named in engine.lock as the base,
then runs the Brand pack format migrations. When a file or a migration needs the coding agent,
it stops and lists them in <state>/decisions.md. `continue` checks that each one is resolved,
runs the gate and opens the PR. A failed check stops again; `continue --draft` then opens a
draft PR with the failure report. Exit 0 when done, 1 on an error, 3 when stopped for the agent.
"""
import argparse
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
RELEASE = HERE.parent
STATE = RELEASE.parent.parent
sys.path.insert(0, str(RELEASE / "engine"))
sys.path.insert(0, str(HERE))

from lib import lock, releases  # noqa: E402
import gate  # noqa: E402
import merge  # noqa: E402

STOPPED = 3
MANIFESTS = (".claude-plugin/plugin.json", ".cursor-plugin/plugin.json", ".github/plugin/plugin.json")
TODO = "Decision: TODO"


class UpgradeError(Exception):
    pass


def git(cwd, *args, check=True):
    result = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if check and result.returncode:
        raise UpgradeError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def save(state):
    (STATE / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def load():
    path = STATE / "state.json"
    if not path.is_file():
        raise UpgradeError("no upgrade is in progress")
    return json.loads(path.read_text(encoding="utf-8"))


def read_tree(root):
    root = pathlib.Path(root)
    return {path: (root / path).read_bytes() for path in lock.file_hashes(root)} if root.is_dir() else {}


def render_starter(release_root, values):
    """The Starter files a release renders from `values`, using that release's own renderer."""
    code = ("import json, sys; sys.path.insert(0, sys.argv[1]); import render; "
            "print(json.dumps(render.render_files(json.loads(sys.argv[2]))))")
    result = subprocess.run([sys.executable, "-c", code, str(pathlib.Path(release_root) / "starter"),
                             json.dumps(values)], capture_output=True, text=True)
    if result.returncode:
        raise UpgradeError(f"cannot render the Starter files of {release_root}: {result.stderr.strip()}")
    return {path: text.encode("utf-8") for path, text in json.loads(result.stdout).items()}


def migrate(brands_dir, old, new):
    """Run migrations/format_N.py for N in old+1..new on every Brand pack. Returns (steps, flags)."""
    if new < old:
        raise UpgradeError(f"this release reads Brand pack format {new}, older than the skill's {old}")
    steps, flags = [], []
    packs = sorted(p for p in pathlib.Path(brands_dir).iterdir() if (p / "brand.json").is_file())
    for number in range(old + 1, new + 1):
        script = RELEASE / "migrations" / f"format_{number}.py"
        if not script.is_file():
            raise UpgradeError(f"this release has no migration to Brand pack format {number}")
        spec = importlib.util.spec_from_file_location(f"format_{number}", str(script))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for pack in packs:
            flags += [f"{pack.name}: {flag}" for flag in module.migrate(pack) or []]
            found = json.loads((pack / "brand.json").read_text(encoding="utf-8")).get("formatVersion")
            if found != number:
                raise UpgradeError(f"the migration to format {number} left {pack.name} at format {found}")
        steps.append(number)
    return steps, flags


def write_decisions(state):
    lines = ["# Upgrade decisions", "",
             f"The upgrade to Engine {state['to']} needs a decision on each item below. Resolve each file",
             "in place, then replace `TODO` with what you decided and why. These lines go into the PR.",
             f"When all are done, run `python3 {HERE / 'upgrade.py'} continue`.", ""]
    for n, item in enumerate(state["decisions"], 1):
        lines += [f"## {n}. {item['title']}", "", item["reason"]]
        if item.get("upstream"):
            lines.append(f"Upstream version: {item['upstream']}")
        lines += ["", TODO, ""]
    (STATE / "decisions.md").write_text("\n".join(lines), encoding="utf-8")


def read_decisions():
    """[(title, decision)] from decisions.md, or an error naming the items still open."""
    text = (STATE / "decisions.md").read_text(encoding="utf-8")
    found = re.findall(r"^## \d+\. ([^\n]+)\n.*?^Decision:[ \t]*([^\n]*)", text, re.M | re.S)
    open_items = [title for title, decision in found if not decision.strip() or decision.strip() == "TODO"]
    if open_items:
        raise UpgradeError("these items still need a decision in decisions.md: " + ", ".join(open_items))
    return found


def _skill_md(state):
    return pathlib.Path(state["skill"]) / "SKILL.md"


def start(args):
    """Until the upgrade branch exists, a failure removes the state, so nothing is in progress."""
    try:
        return _start(args)
    except Exception:
        if STATE.exists() and not (STATE / "state.json").exists():
            shutil.rmtree(str(STATE))
        raise


def _start(args):
    skill = pathlib.Path(args.skill).resolve()
    repo = pathlib.Path(git(skill, "rev-parse", "--show-toplevel")).resolve()
    if "origin" not in git(repo, "remote").split():
        raise UpgradeError("the repo has no `origin` remote to push the upgrade branch to")
    recorded = lock.read(skill / "engine.lock")
    old, new = recorded["version"], args.to
    new_manifest = json.loads((STATE / "new" / "assets" / releases.MANIFEST).read_text(encoding="utf-8"))

    base_manifest, _ = releases.fetch(old, STATE / "base")
    for key in ("engineTreeHash", "starterTreeHash"):
        if base_manifest[key] != recorded.get(key):
            raise UpgradeError(f"engine.lock's {key} does not match release {old}, so the merge has no base")

    plugin = skill.parent.parent
    edited, removed, added = lock.local_edits(skill / "engine", recorded)
    shutil.copytree(str(skill / "engine"), str(STATE / "before" / "engine"))
    ignored_before = gate.ignored_rules(skill / "engine" / "deck.py", STATE)
    kept = merge.protected(_skill_md({"skill": str(skill)}).read_text(encoding="utf-8"))
    base_branch = git(repo, "symbolic-ref", "--short", "HEAD")
    branch = f"slides-upgrade/v{new}"
    git(repo, "checkout", "-q", "-b", branch)
    save({"repo": str(repo), "baseBranch": base_branch, "branch": branch, "to": new, "stage": "merging"})

    engine = merge.three_way(read_tree(STATE / "base" / "release" / "engine"), read_tree(skill / "engine"),
                             read_tree(RELEASE / "engine"), skill / "engine", "engine", RELEASE / "engine")
    values = recorded.get("starterValues") or {}
    starter_base = render_starter(STATE / "base" / "release", values)
    starter_new = render_starter(RELEASE, values)
    for path, data in starter_new.items():
        (STATE / "starter-new" / path).parent.mkdir(parents=True, exist_ok=True)
        (STATE / "starter-new" / path).write_bytes(data)
    ours = {p: (repo / p).read_bytes() for p in set(starter_base) | set(starter_new) if (repo / p).is_file()}
    starter = merge.three_way(starter_base, ours, starter_new, repo, "starter", STATE / "starter-new")

    skill_md = _skill_md({"skill": str(skill)})
    if not merge.has_markers(skill_md):
        skill_md.write_text(merge.restore(skill_md.read_text(encoding="utf-8"), kept), encoding="utf-8")
    steps, flags = migrate(skill / "brands", recorded.get("formatVersion") or 1, new_manifest["formatVersion"])

    new_lock = dict(recorded, version=new, commit=new_manifest["commit"], archiveSha256=args.archive_sha256,
                    engineTreeHash=new_manifest["engineTreeHash"], starterTreeHash=new_manifest["starterTreeHash"],
                    formatVersion=new_manifest["formatVersion"], engineFiles=lock.file_hashes(RELEASE / "engine"))
    (skill / "engine.lock").write_text(json.dumps(new_lock, indent=2) + "\n", encoding="utf-8")

    decisions = []
    for item in engine["conflicts"] + starter["conflicts"]:
        prefix = f"{skill.relative_to(repo).as_posix()}/engine/" if item["kind"] == "engine" else ""
        decisions.append({"title": prefix + item["path"], "reason": item["reason"],
                          "upstream": item["upstream"], "file": str((skill / "engine" if item["kind"] == "engine"
                                                                    else repo) / item["path"])})
    decisions += [{"title": f"Migration flag: {flag}", "reason": "The format migration could not decide this."}
                  for flag in flags]
    state = {"skill": str(skill), "repo": str(repo), "plugin": str(plugin), "baseBranch": base_branch,
             "branch": branch, "from": old, "to": new, "protected": kept, "ignoredBefore": ignored_before,
             "localEdits": {"edited": edited, "removed": removed, "added": added},
             "engine": engine, "starter": starter, "migrations": steps, "decisions": decisions,
             "stage": "decisions" if decisions else "gate"}
    save(state)
    if decisions:
        write_decisions(state)
        print(f"Upgrade to {new} needs {len(decisions)} decision(s) from the coding agent. "
              f"They are listed in {STATE / 'decisions.md'}.")
        for item in decisions:
            print(f"  {item['title']}: {item['reason']}")
        print(f"Resolve each one, fill in its decision, then run `python3 {HERE / 'upgrade.py'} continue`.")
        return STOPPED
    return finish(state, draft=False)


def resume(args):
    state = load()
    if state["stage"] == "merging":
        raise UpgradeError("the merge did not finish. Undo it with `abort` and start again.")
    if state["stage"] == "decisions":
        resolved = read_decisions()
        marked = [item["title"] for item in state["decisions"] if item.get("file") and merge.has_markers(item["file"])]
        if marked:
            raise UpgradeError("these files still hold conflict markers: " + ", ".join(marked))
        state["resolved"] = resolved
        state["stage"] = "gate"
        save(state)
    if merge.protected(_skill_md(state).read_text(encoding="utf-8")) != state["protected"]:
        raise UpgradeError("SKILL.md's name, description or `## Local rules` changed. Upgrade never "
                           "changes them: put them back as they were.")
    return finish(state, draft=args.draft)


def bump(version, old_engine, new_engine):
    """The Slides skill's version, raised at the level of the Engine change."""
    old, new = releases.parse(old_engine)[:3], releases.parse(new_engine)[:3]
    major, minor, patch = (int(n) for n in version.split("."))
    if new[0] != old[0]:
        return f"{major + 1}.0.0"
    if new[1] != old[1]:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _bump_skill(state):
    plugin, skill = pathlib.Path(state["plugin"]), pathlib.Path(state["skill"])
    current = json.loads((plugin / MANIFESTS[0]).read_text(encoding="utf-8"))["version"]
    raised = bump(current, state["from"], state["to"])
    for manifest in MANIFESTS:
        path = plugin / manifest
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace(f'"version": "{current}"', f'"version": "{raised}"', 1), encoding="utf-8")
    recorded = json.loads((skill / "engine.lock").read_text(encoding="utf-8"))
    recorded.setdefault("starterValues", {})["version"] = raised
    (skill / "engine.lock").write_text(json.dumps(recorded, indent=2) + "\n", encoding="utf-8")
    return current, raised


def _section(title, items):
    return [f"### {title}", ""] + (items or ["None."]) + [""]


def pr_body(state, result, draft_reasons, versions):
    lines = [f"Moves this Slides skill from Engine {state['from']} to {state['to']}, made by `deck.py upgrade`.", ""]
    if draft_reasons:
        lines += ["**Draft:** " + " ".join(draft_reasons), ""]
    lines += ["### Checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {c['name']} | {c['status']} | {c['detail'].replace('|', '/').replace(chr(10), '; ')} |"
              for c in result["checks"]]
    lines.append("")
    notes = []
    for version in versions:
        notes += [f"#### v{version}", "", releases.notes(version) or "No notes.", ""]
    lines += _section("Release notes", notes)
    edits = state["localEdits"]
    lines += _section("Local Engine edits", [f"- Edited: `{p}`" for p in edits["edited"]]
                      + [f"- Removed: `{p}`" for p in edits["removed"]]
                      + ([f"- {edits['added']} file(s) added locally"] if edits["added"] else []))
    lines += _section("The coding agent's decisions", [f"- **{t}:** {d.strip()}" for t, d in state.get("resolved", [])])
    merged = []
    for kind in ("engine", "starter"):
        for key, label in (("taken", "Updated"), ("added", "Added"), ("removed", "Removed"),
                           ("kept", "Kept local version"), ("reported", "Removed upstream, kept here")):
            merged += [f"- {kind.title()}, {label}: `{p}`" for p in state[kind][key]]
    lines += _section("Merge", merged)
    lines += _section("Brand pack migrations", [f"- To format {n}" for n in state["migrations"]])
    became = [rule for rule in result["ignored"] if rule not in state["ignoredBefore"]]
    lines += _section("Playbook rules that became ignored", [f"- {rule}" for rule in became])
    return "\n".join(lines)


def finish(state, draft):
    repo = pathlib.Path(state["repo"])
    result = gate.run(state["skill"], state["plugin"], STATE / "before" / "engine", STATE / "out")
    failed = [c for c in result["checks"] if c["status"] == "fail"]
    if failed and not draft:
        print("The upgraded skill failed these checks:")
        for c in failed:
            print(f"  {c['name']}: {c['detail']}")
        print(f"Fix them and run `python3 {HERE / 'upgrade.py'} continue` again, or open a draft PR with the "
              "failure report with `continue --draft`.")
        return STOPPED
    reasons = []
    if failed:
        reasons.append("Some checks failed, and the coding agent could not fix them.")
    if any(c["status"] == "difference" for c in result["checks"]):
        reasons.append("The Sample deck looks different. The maintainer must approve the change.")
    if any(c["status"] == "not run" for c in result["checks"]):
        reasons.append("A comparison could not run, so the maintainer must check the Sample decks.")

    old_version, new_version = _bump_skill(state)
    versions = [v for v, _ in releases.list_versions()
                if releases.parse(state["from"]) < releases.parse(v) <= releases.parse(state["to"])]
    body = STATE / "pr.md"
    body.write_text(pr_body(state, result, reasons, versions) + "\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", f"Upgrade the Engine to {state['to']}")
    git(repo, "push", "-q", "-u", "origin", state["branch"])
    args = ["pr", "create", "--base", state["baseBranch"], "--head", state["branch"],
            "--title", f"Upgrade the Engine to {state['to']}", "--body-file", str(body)]
    url = releases.gh(*(args + (["--draft"] if reasons else []))).stdout.strip()
    shutil.rmtree(str(STATE))
    kind = "draft PR" if reasons else "PR"
    print(f"Opened a {kind} that moves the skill from {old_version} to {new_version}: {url}")
    return 0


def abort(_args):
    state = load()
    repo = state["repo"]
    git(repo, "reset", "-q", "--hard")
    git(repo, "clean", "-q", "-fd")
    git(repo, "checkout", "-q", state["baseBranch"])
    git(repo, "branch", "-q", "-D", state["branch"])
    shutil.rmtree(str(STATE))
    print(f"The upgrade to {state['to']} was undone. The repo is back on {state['baseBranch']}.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Upgrade a Slides skill to this release.")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("start")
    s.add_argument("--skill", required=True)
    s.add_argument("--to", required=True)
    s.add_argument("--archive-sha256", required=True)
    s.set_defaults(func=start)
    c = sub.add_parser("continue")
    c.add_argument("--draft", action="store_true", help="open a draft PR even though checks fail")
    c.set_defaults(func=resume)
    sub.add_parser("abort").set_defaults(func=abort)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (UpgradeError, releases.ReleaseError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
