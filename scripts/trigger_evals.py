#!/usr/bin/env python3
"""Test that the Generator and the Slides skills it makes start on the right requests.

    python3 scripts/trigger_evals.py check
    python3 scripts/trigger_evals.py build --out <empty folder>
    python3 scripts/trigger_evals.py run [--runs 3] [--model <model>] [--out <empty folder>]

`check` is free and runs in CI: every skill in skills/ and the Starter files rendered for `acme`
and `plain` have a valid name, a one-line description within the limit that says what the skill
is not for, and, for a Slides skill, names each brand and alias.

`build` writes the competing test plugin: the Generator, `acme-slides` and `plain-slides` in one
plugin, so their descriptions compete as when a maintainer has all three installed, with the
eval cases. `run` runs them with Claude Code on your account and applies the pass rule: no wrong
skill starts in any run, and the expected one starts in at least two of three. Run it when a
description or the workflow changes and before every release. It never publishes the report.
"""
import argparse
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "starter"))

import render  # noqa: E402
from lib import triggers  # noqa: E402
from lib.common import DeckError  # noqa: E402

GENERATOR = "slides-skill-creator"
# The test Slides skills, described as reference/new.md tells a maintainer to.
SLIDES = {
    "acme-slides": (ROOT / "brands" / "acme",
                    'Builds on-brand slide decks, presentations and PowerPoint exports for Acme '
                    '("Acme Corp", "Acme Inc"). Use for any deck, talk or report for Acme, or to '
                    'turn an Acme .pptx into a web deck. Not for other brands.'),
    "plain-slides": (ROOT / "engine" / "fixtures" / "plain",
                     "Builds on-brand slide decks, presentations and PowerPoint exports for Plain. "
                     "Use for any deck, talk or report for Plain, or to turn a Plain .pptx into a "
                     "web deck. Not for other brands."),
}

case = triggers.case
CASES = [
    case("deck-acme", "Make a deck for Acme about our third-quarter results.", "acme-slides"),
    case("deck-plain", "Make a deck for Plain about our third-quarter results.", "plain-slides"),
    case("new-skill", "Make a slides skill for our brand. I have our guidelines as a PDF, the "
                      "logo and our font files.", GENERATOR),
    case("add-brand", "Add a brand to acme-slides: our sister company Tidewell needs decks too.",
         GENERATOR),
    case("edit-font", "Change the font in the Acme Brand pack to Inter.", GENERATOR),
    case("upgrade", "Upgrade acme-slides to the newest Engine.", GENERATOR,
         says=r"deck\.py upgrade", max_turns=8),
    case("no-skill-brand", "Make a deck for Brightfield about our third-quarter results.", None),
    case("fix-pptx", "Fix this .pptx: the title on slide 3 of quarterly-review.pptx overlaps the "
                     "logo.", None),
]


def _brand(folder):
    data = json.loads((folder / "brand.json").read_text(encoding="utf-8"))
    return data["name"], data.get("aliases", [])


def _rendered(skill):
    """The Starter files rendered for one test Slides skill."""
    _, description = SLIDES[skill]
    return render.render_files({"skill": skill, "description": description,
                                "repo": "example/" + skill, "author": "Example"})


def check():
    """[(file, problem)] across the Generator's skills and the rendered Starter skills."""
    problems = []
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        problems += [(skill_md.relative_to(ROOT).as_posix(), p) for p in triggers.check_skill(skill_md)]
    for skill, (pack, _) in SLIDES.items():
        files = _rendered(skill)
        for name, brands in ((skill, [_brand(pack)]), (f"{skill}-feedback", [])):
            path = f"skills/{name}/SKILL.md"
            problems += [(f"starter: {path}", p)
                         for p in triggers.check_text(files[path], name, brands)]
    return problems


def competing_skills(folder):
    """The Generator's folder, and acme-slides and plain-slides written into `folder`."""
    folders = [ROOT / "skills" / GENERATOR]
    for skill in SLIDES:
        target = pathlib.Path(folder) / skill
        target.mkdir(parents=True)
        text = _rendered(skill)[f"skills/{skill}/SKILL.md"]
        (target / "SKILL.md").write_text(text, encoding="utf-8")
        folders.append(target)
    return folders


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="the free static check of every description")
    p = sub.add_parser("build", help="write the competing test plugin and its cases")
    p.add_argument("--out", required=True, help="an empty or missing folder")
    p = sub.add_parser("run", help="run the evals with Claude Code (costs tokens)")
    p.add_argument("--runs", type=int, default=triggers.RUNS, help="runs per case (default 3)")
    p.add_argument("--model", help="the model under test (default: Claude Code's)")
    p.add_argument("--out", help="keep the plugin and report.json in this empty folder")
    args = ap.parse_args(argv)

    if args.command == "check":
        problems = check()
        for where, problem in problems:
            print(f"error: {where}: {problem}")
        print(f"{len(problems)} problem(s)." if problems else "Every skill description passes.")
        return 1 if problems else 0
    try:
        with tempfile.TemporaryDirectory() as tmp:
            skills = competing_skills(tmp)
            if args.command == "build":
                out = pathlib.Path(args.out).resolve()
                if out.exists() and (not out.is_dir() or any(out.iterdir())):
                    raise DeckError(f"{out} is not an empty folder")
                triggers.build_plugin(out, skills, CASES)
                print(f"Wrote the test plugin to {out}")
                return 0
            passed, results, report = triggers.run(skills, CASES, args.runs, args.model, args.out)
    except DeckError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    triggers.print_results(results)
    if report:
        print(f"Report: {report}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
