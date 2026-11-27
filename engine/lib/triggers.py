"""Test a skill's trigger: a free static check of its SKILL.md, and live evals with Claude Code.

`check_skill` is what `deck.py check` runs on the Slides skill's own SKILL.md. `run` is
`deck.py eval`: it builds a throwaway plugin with eval cases, runs `claude plugin eval` on it and
applies the pass rule. The Generator's own suite (scripts/trigger_evals.py) uses the same code.

The pass rule: in every case no wrong skill starts in any run, because a wrong start opens a full
Interview, and the expected skill starts in at least two of three runs.
"""
import json
import math
import pathlib
import re
import shutil
import subprocess
import tempfile

from .common import DeckError

NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
NOT_FOR = re.compile(r"\bnot for\b", re.IGNORECASE)
# Brands for the case where no Slides skill may start. The first that the skill does not name is used.
UNKNOWN_BRANDS = ("Brightfield", "Larkspur", "Quillon")
RUNS = 3
MAX_TURNS = 3


def frontmatter(text):
    """{key: value} of a SKILL.md's frontmatter, for one-line values (plain, or quoted as JSON)."""
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        raise DeckError("SKILL.md has no frontmatter (it must start with a --- line)")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise DeckError("SKILL.md's frontmatter has no closing --- line")
    values, last = {}, None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep or line[:1].isspace():
            if last in ("name", "description"):
                values["_continued"] = True
            continue
        last = key.strip()
        value = value.strip()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                raise DeckError(f"SKILL.md: {key.strip()} is not a valid quoted string")
        elif value.startswith("'") and value.endswith("'") and len(value) > 1:
            value = value[1:-1].replace("''", "'")
        values[key.strip()] = value
    return values


def check_text(text, folder, brands=()):
    """Every problem with a SKILL.md's trigger. `brands` is [(name, [alias])] it must name."""
    try:
        meta = frontmatter(text)
    except DeckError as e:
        return [str(e)]
    problems = []
    name = meta.get("name")
    if not name:
        problems.append("SKILL.md has no name")
    else:
        if not NAME.fullmatch(name) or len(name) > MAX_NAME:
            problems.append(f"name {name!r} must be at most {MAX_NAME} characters of a-z, 0-9 "
                            "and single hyphens")
        if name != folder:
            problems.append(f"name {name!r} differs from its folder {folder!r}")
    description = meta.get("description")
    if not description:
        problems.append("SKILL.md has no description")
        return problems
    if meta.get("_continued") or description in (">", "|", ">-", "|-"):
        problems.append("the frontmatter must hold name and description on one line each")
    if len(description) > MAX_DESCRIPTION:
        problems.append(f"the description is {len(description)} characters, over {MAX_DESCRIPTION}")
    if not NOT_FOR.search(description):
        problems.append("the description does not say what the skill is not for (\"Not for ...\")")
    lowered = description.lower()
    for brand, aliases in brands:
        for term in [brand, *aliases]:
            if not re.search(r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)", lowered):
                problems.append(f"the description does not name {term!r}, so a request that says "
                                "it may not start the skill")
    return problems


def check_skill(skill_md, brands=()):
    path = pathlib.Path(skill_md)
    return check_text(path.read_text(encoding="utf-8"), path.parent.name, brands)


# --- cases -----------------------------------------------------------------------------------

def case(name, prompt, expect, says=None, max_turns=MAX_TURNS):
    """One eval case. `expect` is the skill that must start, or None when none may.
    `says` is a regex the final answer must match, checked like a start."""
    return {"name": name, "prompt": prompt, "expect": expect, "says": says, "maxTurns": max_turns}


def slides_cases(skill, brands):
    """The suite of one Slides skill: each brand by name and alias, and two it must leave alone.
    `brands` is [(slug, name, [alias])]; the unique slug names the cases."""
    named = " ".join(term for _, brand, aliases in brands for term in [brand, *aliases]).lower()
    unknown = next((b for b in UNKNOWN_BRANDS if b.lower() not in named), None)
    cases = []
    for slug, brand, aliases in brands:
        cases.append(case(f"deck-{slug}", f"Make a five-slide deck for {brand} about next "
                                          "quarter's priorities.", skill))
        for i, alias in enumerate(aliases, 1):
            cases.append(case(f"alias-{slug}-{i}", f"We need a short presentation for {alias} "
                                                   "on this year's results.", skill))
    if unknown:
        cases.append(case("other-brand", f"Make a five-slide deck for {unknown} about next "
                                         "quarter's priorities.", None))
    cases.append(case("fix-pptx", "Fix the overlapping title on slide 3 of quarterly-review.pptx.",
                      None))
    return cases


def plugin_skills(skill_dir):
    """The skill folders the plugin around `skill_dir` lists, so its own skills compete."""
    skill_dir = pathlib.Path(skill_dir)
    manifest = skill_dir.parent.parent / ".claude-plugin" / "plugin.json"
    if skill_dir.parent.name != "skills" or not manifest.is_file():
        raise DeckError(f"{skill_dir} is not in a plugin's skills/ folder next to "
                        ".claude-plugin/plugin.json")
    try:
        listed = json.loads(manifest.read_text(encoding="utf-8")).get("skills") or []
    except (OSError, ValueError, AttributeError) as e:
        raise DeckError(f"{manifest} cannot be read: {e}")
    folders = [(manifest.parent.parent / p).resolve() for p in listed]
    missing = [str(f) for f in folders if not (f / "SKILL.md").is_file()]
    if missing:
        raise DeckError("plugin.json lists skills without a SKILL.md: " + ", ".join(missing))
    if skill_dir.resolve() not in folders:
        folders.append(skill_dir.resolve())
    return folders


def _skill_pattern(skill):
    if not NAME.fullmatch(skill):
        raise DeckError(f"not a valid skill name: {skill!r}")
    # The closing quote keeps acme-slides from matching acme-slides-feedback.
    return r'"skill"\s*:\s*"(?:[\w-]+:)?' + skill + '"'


def _grader(kind, skill=None, pattern=None):
    if kind == "says":
        return ("---\ntype: regex\npattern: '" + pattern.replace("'", "''") + "'\n---\n"
                "The answer says this.\n")
    lines = ["---", "type: tool_used", "tool: Skill",
             "input_match: '" + _skill_pattern(skill) + "'"]
    lines += ["min: 1"] if kind == "starts" else ["min: 0", "max: 0"]
    what = "starts" if kind == "starts" else "does not start"
    return "\n".join(lines + ["---", f"{skill} {what}.", ""])


def build_plugin(out, skills, cases):
    """A plugin in `out` holding copies of the `skills` folders and the eval cases."""
    out = pathlib.Path(out)
    names = [pathlib.Path(s).name for s in skills]
    if len(set(names)) != len(names):
        raise DeckError("two skills have the same folder name")
    for source in skills:
        shutil.copytree(str(source), str(out / "skills" / pathlib.Path(source).name),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    (out / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    manifest = {"name": "trigger-evals", "version": "0.0.0",
                "skills": [f"./skills/{n}" for n in names]}
    (out / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                                        encoding="utf-8")
    for c in cases:
        if c["expect"] is not None and c["expect"] not in names:
            raise DeckError(f"case {c['name']} expects {c['expect']}, which the plugin lacks")
        folder = out / "evals" / c["name"] / "graders"
        folder.mkdir(parents=True)
        (folder.parent / "prompt.md").write_text(
            f"---\nmax_turns: {c['maxTurns']}\nallowed_tools: [Skill]\n---\n\n{c['prompt']}\n",
            encoding="utf-8")
        for skill in names:
            kind = "starts" if skill == c["expect"] else "quiet"
            (folder / f"{kind}-{skill}.md").write_text(_grader(kind, skill), encoding="utf-8")
        if c["says"]:
            (folder / "says.md").write_text(_grader("says", pattern=c["says"]), encoding="utf-8")
    return out


# --- running and judging ---------------------------------------------------------------------

def verdicts(report, cases, skills):
    """[{case, passed, starts, quiet, runs}] from `claude plugin eval --json` by the pass rule.
    `skills` are the plugin's skill names: each must be graded in every run that counts."""
    by_name = {c.get("name"): c for c in report.get("cases", [])}
    results = []
    for c in cases:
        runs = (by_name.get(c["name"]) or {}).get("arms", {}).get("with", []) or []
        starts = quiet = 0
        quiet_names = {f"quiet-{s}" for s in skills if s != c["expect"]}
        start_names = ({f"starts-{c['expect']}"} if c["expect"] else set()) | ({"says"} if c["says"] else set())
        for run in runs:
            error = run.get("error") or ""
            # A trigger case is meant to stop soon after the first skill call, so reaching the turn
            # limit is no failure: its graders still judge the run. Any other error is one.
            if (error and "maximum number of turns" not in error) or run.get("aborted"):
                continue
            passed = {g.get("name") for g in run.get("graders", []) if g.get("passed")}
            if quiet_names <= passed:
                quiet += 1
            if start_names <= passed:
                starts += 1
        total = len(runs)
        passed = total > 0 and quiet == total
        if c["expect"] is not None or c["says"]:
            passed = passed and starts >= math.ceil(2 * total / 3)
        results.append({"case": c["name"], "expect": c["expect"], "passed": passed,
                        "starts": starts, "quiet": quiet, "runs": total})
    return results


def run_claude(plugin, runs, model, report_path):
    """Run `claude plugin eval` on the plugin; the parsed JSON report."""
    claude = shutil.which("claude")
    if not claude:
        raise DeckError("evals need Claude Code's `claude` command (2.1.269 or later) on PATH")
    cmd = [claude, "plugin", "eval", str(plugin), "--ablation", "none", "--runs", str(runs),
           "--no-publish", "--trust-plugin", "--json", str(report_path)]
    if model:
        cmd += ["--model", model]
    try:
        result = subprocess.run(cmd)
    except OSError as e:
        raise DeckError(f"`claude` could not start: {e}")
    if result.returncode not in (0, 1) or not pathlib.Path(report_path).is_file():
        raise DeckError(f"`claude plugin eval` could not finish (exit {result.returncode})")
    try:
        report = json.loads(pathlib.Path(report_path).read_text(encoding="utf-8"))
    except ValueError as e:
        raise DeckError(f"the eval report is not valid JSON: {e}")
    if report.get("partial"):
        raise DeckError(f"`claude plugin eval` stopped early: {report.get('partialReason')}")
    return report


def run(skills, cases, runs=RUNS, model=None, out=None):
    """Build the plugin, run the evals and judge them. (passed, results, report path or None)."""
    if runs < 1:
        raise DeckError("--runs must be 1 or more")
    if out:
        out = pathlib.Path(out).resolve()
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise DeckError(f"{out} is not an empty folder")
        workdir, tmp = out, None
    else:
        tmp = tempfile.TemporaryDirectory()
        workdir = pathlib.Path(tmp.name)
    try:
        plugin = build_plugin(workdir / "plugin", skills, cases)
        report_path = workdir / "report.json"
        names = [pathlib.Path(s).name for s in skills]
        results = verdicts(run_claude(plugin, runs, model, report_path), cases, names)
    finally:
        if tmp:
            tmp.cleanup()
    return all(r["passed"] for r in results), results, (str(report_path) if out else None)


def print_results(results):
    for r in results:
        expect = r["expect"] or "no skill"
        print(f"{'pass' if r['passed'] else 'FAIL'}  {r['case']}: expects {expect}; "
              f"started {r['starts']}/{r['runs']}, no wrong start {r['quiet']}/{r['runs']}")
    failed = [r["case"] for r in results if not r["passed"]]
    print(f"{len(results) - len(failed)} of {len(results)} case(s) passed"
          + (f"; failed: {', '.join(failed)}" if failed else "."))
