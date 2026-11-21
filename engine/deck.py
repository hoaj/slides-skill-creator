#!/usr/bin/env python3
"""The Engine's one entry point.

    python3 <skill>/engine/deck.py brands
    python3 <skill>/engine/deck.py build --brand <slug> template.html deck.html [--open]
    python3 <skill>/engine/deck.py export-pptx deck.html deck.pptx
    python3 <skill>/engine/deck.py extract-pptx in.pptx [out_dir]
    python3 <skill>/engine/deck.py doctor [--report]

`brands`, `build` and `doctor` need only Python 3.8+. The PowerPoint commands import
their optional dependencies when they run, and say how to install what is missing.
Generated output never goes into the skill folder.
"""
import argparse
import pathlib
import sys

if sys.version_info < (3, 8):
    sys.exit("error: the Engine needs Python 3.8 or newer.")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from lib.common import DeckError  # noqa: E402


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
    build.run(args.brand, pathlib.Path(args.template), pathlib.Path(args.out), args.open)
    return 0


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
    p.set_defaults(func=cmd_build)

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
