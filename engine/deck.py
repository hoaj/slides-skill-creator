#!/usr/bin/env python3
"""The Engine's one entry point.

    python3 <skill>/engine/deck.py brands
    python3 <skill>/engine/deck.py deck-types --brand <slug> [--json]
    python3 <skill>/engine/deck.py interview --brand <slug> [--deck-type <id>] [--json]
    python3 <skill>/engine/deck.py build --brand <slug> [--deck-type <id>] template.html deck.html [--open]
    python3 <skill>/engine/deck.py inspect deck.html [--json]
    python3 <skill>/engine/deck.py export-pptx deck.html deck.pptx
    python3 <skill>/engine/deck.py extract-pptx in.pptx [out_dir]
    python3 <skill>/engine/deck.py check [--brand <slug>]
    python3 <skill>/engine/deck.py sample --brand <slug> [out.html] [--open]
    python3 <skill>/engine/deck.py compare <old-engine> <new-engine> --brand <slug> [--out <dir>] [--json]
    python3 <skill>/engine/deck.py doctor [--report]
    python3 <skill>/engine/deck.py upgrade [--to X.Y.Z] [--check]
    python3 <skill>/engine/deck.py eval [--runs 3] [--model <model>] [--out <dir>]

Everything but the PowerPoint commands and `compare` needs only Python 3.8+. Those import
their optional dependencies when they run, and say how to install what is missing. `upgrade`
also needs git and `gh` 2.81 or later. `eval` needs Claude Code's `claude` command, runs a live
agent on the user's account and never publishes its report.
Generated output never goes into the skill folder.
"""
import argparse
import json
import pathlib
import sys

if sys.version_info < (3, 8):
    sys.exit("error: the Engine needs Python 3.8 or newer.")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from lib.common import SKILL, DeckError, ensure_outside_skill  # noqa: E402


def cmd_brands(args):
    from lib import packs
    found, problems = packs.list_packs()
    for slug, name, aliases in found:
        also = f" (also: {', '.join(aliases)})" if aliases else ""
        print(f"{slug}: {name}{also}")
    if not found:
        print(f"No Brand packs in {packs.BRANDS}")
    for problem in problems:
        print(f"warning: {problem}", file=sys.stderr)
    return 0


def cmd_build(args):
    from lib import build
    build.run(args.brand, pathlib.Path(args.template), pathlib.Path(args.out), args.open,
              args.deck_type)
    return 0


def cmd_check(args):
    from lib import packs
    slugs = [args.brand] if args.brand else packs.all_slugs()
    errors = warnings = 0
    for slug in slugs:
        _, report = packs.check(slug)
        errors += len(report.errors)
        warnings += len(report.warnings)
        state = "not valid" if report.errors else "valid"
        print(f"{slug}: {state}, {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        for problem in report.errors:
            print(f"  error: {problem}")
        for problem in report.warnings:
            print(f"  warning: {problem}")
    checked = f"{len(slugs)} Brand pack(s)"
    skill_md = SKILL / "SKILL.md"
    if not args.brand and skill_md.is_file():
        from lib import triggers
        problems = triggers.check_skill(skill_md, [(n, a) for _, n, a in packs.list_packs()[0]])
        errors += len(problems)
        print(f"SKILL.md: {'not valid' if problems else 'valid'}, {len(problems)} error(s)")
        for problem in problems:
            print(f"  error: {problem}")
        checked += " and SKILL.md"
    print(f"Checked {checked}: {errors} error(s), {warnings} warning(s).")
    return 1 if errors else 0


def cmd_deck_types(args):
    from lib import packs, playbook
    found = playbook.list_deck_types(packs.load(args.brand))
    if args.json:
        print(json.dumps(found, indent=2, ensure_ascii=False))
    else:
        for item in found:
            print(f"{item['id']}: {item['name']}. Use for: {item['when']}")
        if not found:
            print(f"Brand pack '{args.brand}' has no Deck types.")
    return 0


def cmd_interview(args):
    from lib import packs, playbook
    result, _ = playbook.merge(packs.load(args.brand), args.deck_type)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else playbook.render(result))
    return 0


def cmd_inspect(args):
    from lib import inspect_deck
    return inspect_deck.run(pathlib.Path(args.deck), args.json)


def cmd_sample(args):
    from lib import sample
    sample.run(args.brand, args.out, args.open, args.template_only)
    return 0


def cmd_compare(args):
    """Exit 0 for no difference, 1 for a difference, 2 when the comparison could not run."""
    try:
        from lib import compare
        return compare.run(args)
    except DeckError as e:
        print(f"error: {e}", file=sys.stderr)
    except Exception as e:  # a crash in a tool must not look like "a difference"
        print(f"error: the comparison could not run: {type(e).__name__}: {e}", file=sys.stderr)
    return 2


def cmd_export_pptx(args):
    from lib import pptx_export
    pptx_export.run(args)
    return 0


def cmd_extract_pptx(args):
    from lib import pptx_extract
    pptx_extract.run(pathlib.Path(args.input), pathlib.Path(args.out_dir))
    return 0


def cmd_doctor(args):
    from lib import doctor
    return doctor.run(report_only=args.report)


def cmd_eval(args):
    """Exit 0 when every case passes, 1 when one fails, 2 when the evals could not run."""
    from lib import packs, triggers
    try:
        brands = [(name, aliases) for _, name, aliases in packs.list_packs()[0]]
        if not brands:
            raise DeckError(f"no Brand packs in {packs.BRANDS}")
        if args.out:
            ensure_outside_skill(args.out, "the eval folder")
        cases = triggers.slides_cases(SKILL.name, brands)
        passed, results, report = triggers.run(triggers.plugin_skills(SKILL), cases, args.runs,
                                               args.model, args.out)
    except DeckError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    triggers.print_results(results)
    if report:
        print(f"Report: {report}")
    return 0 if passed else 1


def cmd_upgrade(args):
    from lib import releases, upgrade
    try:
        return upgrade.run(args.to, args.check)
    except releases.ReleaseError as e:
        raise DeckError(str(e))


def parser():
    ap = argparse.ArgumentParser(prog="deck.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("brands", help="list this Slides skill's Brand packs")
    p.set_defaults(func=cmd_brands)

    p = sub.add_parser("build", help="build one self-contained deck from a template")
    p.add_argument("--brand", required=True, help="Brand pack slug")
    p.add_argument("template")
    p.add_argument("out")
    p.add_argument("--open", action="store_true",
                   help="show the deck: reload the tab that shows it, or open one")
    p.add_argument("--deck-type", help="record this Deck type in the deck ('none' clears it)")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("check", help="validate Brand packs and print every problem")
    p.add_argument("--brand", help="check only this Brand pack")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("deck-types", help="list a Brand pack's Deck types")
    p.add_argument("--brand", required=True, help="Brand pack slug")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_deck_types)

    p = sub.add_parser("interview", help="print the merged Interview for a brand and Deck type")
    p.add_argument("--brand", required=True, help="Brand pack slug")
    p.add_argument("--deck-type", help="Deck type id")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_interview)

    p = sub.add_parser("inspect", help="read a built deck's brand, Deck type and key terms")
    p.add_argument("deck")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("sample", help="build the neutral Sample deck for a Brand pack")
    p.add_argument("--brand", required=True, help="Brand pack slug")
    p.add_argument("out", nargs="?", help="output file (default: <slug>-sample.html here)")
    p.add_argument("--open", action="store_true", help="show the deck in the browser")
    p.add_argument("--template-only", action="store_true",
                   help="write the Sample deck's template and do not build it")
    p.set_defaults(func=cmd_sample)

    p = sub.add_parser("compare", help="compare a Brand pack's Sample deck on two Engines")
    p.add_argument("old_engine", help="the old Engine folder, or a Slides skill that holds one")
    p.add_argument("new_engine", help="the new Engine folder, or a Slides skill that holds one")
    p.add_argument("--brand", required=True, help="Brand pack slug")
    p.add_argument("--out", help="folder for the report and images (default: none are kept)")
    p.add_argument("--json", action="store_true", help="print the summary as JSON")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("export-pptx", help="export a built deck to PowerPoint with live text")
    p.add_argument("deck")
    p.add_argument("out")
    p.add_argument("--brand", help="Brand pack slug, needed only with --fonts")
    p.add_argument("--image-only", action="store_true",
                   help="background images only, no live text layer")
    p.add_argument("--scale", type=int, default=2, help="render scale (default 2)")
    p.add_argument("--fonts", help="also write the pack's fonts as installable TTFs here")
    p.add_argument("--json", help="also write the raw layout plan here (debugging)")
    p.set_defaults(func=cmd_export_pptx)

    p = sub.add_parser("extract-pptx", help="extract text, images and notes from a .pptx")
    p.add_argument("input")
    p.add_argument("out_dir", nargs="?", default=".")
    p.set_defaults(func=cmd_extract_pptx)

    p = sub.add_parser("doctor", help="check this machine and the Brand packs")
    p.add_argument("--report", action="store_true",
                   help="print a redacted environment report for a bug report")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("eval", help="test with Claude Code that requests start this skill "
                                    "(costs tokens)")
    p.add_argument("--runs", type=int, default=3, help="runs per case (default 3)")
    p.add_argument("--model", help="the model under test (default: Claude Code's)")
    p.add_argument("--out", help="keep the eval plugin and report.json in this empty folder")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("upgrade", help="move this Slides skill to a newer Engine release in a PR")
    p.add_argument("--to", help="the release to move to (default: the newest stable release)")
    p.add_argument("--check", action="store_true", help="only report whether a newer release exists")
    p.set_defaults(func=cmd_upgrade)
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except DeckError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
