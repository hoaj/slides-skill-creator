#!/usr/bin/env python3
"""The Generator's one entry point. Every command prints JSON; an error is {"error": {...}}, exit 1.

    python3 <gen>/tools/gen.py new --dir <folder> | --into <repo root> --skill <name>-slides
                                   --description "<text>" --repo <owner/name> --author "<name>"
                                   --brand <pack folder>
    python3 <gen>/tools/gen.py add-brand --skill-dir <skill> --brand <pack folder>
    python3 <gen>/tools/gen.py describe --skill-dir <skill> --description "<text>"
    python3 <gen>/tools/gen.py bump --skill-dir <skill> major|minor|patch
    python3 <gen>/tools/gen.py pack-init --out <folder>/<slug> --slug <slug> --name "<Name>" [--alias <a>]...
    python3 <gen>/tools/gen.py pack-check --pack <pack folder>
    python3 <gen>/tools/gen.py extract-pptx <file.pptx> --out <folder>
    python3 <gen>/tools/gen.py fonts --pack <pack folder> --src <font file>... [--display "<family>"] [--body "<family>"]
    python3 <gen>/tools/gen.py icons --pack <pack folder> --src <folder of SVGs>
    python3 <gen>/tools/gen.py guard --pack <pack folder> [--base <theme>=<colour>]... [--neutral <c>]... [--vivid <c>]...
    python3 <gen>/tools/gen.py calibrate prepare --skill-dir <skill> --brand <slug> --out <folder> [--powerpoint]
    python3 <gen>/tools/gen.py calibrate fit --skill-dir <skill> --brand <slug> --out <folder> [--write]

<gen> is the folder of the Generator's SKILL.md, and <skill> the folder of a Slides skill's
SKILL.md. new, add-brand, describe, pack-init, pack-check, extract-pptx, icons and guard need only
Python 3.8+. fonts needs fonttools and brotli; calibrate needs the Engine's export dependencies,
pymupdf and Microsoft PowerPoint.
"""
import argparse
import json
import pathlib
import sys

if sys.version_info < (3, 8):
    sys.exit("error: the Generator needs Python 3.8 or newer.")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from genlib.common import GenError  # noqa: E402


def run(args):
    from genlib import calibrate, extract, fonts, guard, icons, pack, skill
    c = args.command
    if c == "new":
        if bool(args.dir) == bool(args.into):
            raise GenError("give exactly one of --dir (a repo of its own) and --into (a shared repo)")
        make = skill.new_dir if args.dir else skill.new_into
        return make(args.dir or args.into, args.skill, args.description, args.repo, args.author, args.brand)
    if c == "add-brand":
        return skill.add_brand(args.skill_dir, args.brand)
    if c == "describe":
        return skill.describe(args.skill_dir, args.description)
    if c == "bump":
        return skill.bump(args.skill_dir, args.part)
    if c == "pack-init":
        return pack.init(args.out, args.slug, args.name, args.alias or [])
    if c == "pack-check":
        return pack.check(args.pack)
    if c == "extract-pptx":
        return extract.facts(args.input, args.out)
    if c == "fonts":
        return fonts.build(args.pack, args.src, args.display, args.body)
    if c == "icons":
        return icons.build(args.pack, args.src)
    if c == "guard":
        return guard.build(args.pack, args.base or [], args.neutral or [], args.vivid or [])
    if c == "calibrate":
        if args.step == "prepare":
            return calibrate.prepare(args.skill_dir, args.brand, args.out, args.powerpoint)
        return calibrate.fit(args.skill_dir, args.brand, args.out, args.write)
    raise GenError(f"unknown command {c!r}")


def parser():
    ap = argparse.ArgumentParser(prog="gen.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="create a Slides skill with its first Brand pack")
    p.add_argument("--dir", help="a new repo of its own: a folder that is missing, empty or holds only .git")
    p.add_argument("--into", help="the root of a repo that already has a marketplace")
    p.add_argument("--skill", required=True, help="the skill's name, <name>-slides")
    p.add_argument("--description", required=True, help="the approved trigger description")
    p.add_argument("--repo", required=True, help="the GitHub repo, owner/name")
    p.add_argument("--author", required=True, help="the maintainer's name for the manifests")
    p.add_argument("--brand", required=True, help="the approved Brand pack folder")

    p = sub.add_parser("add-brand", help="add a Brand pack to a Slides skill")
    p.add_argument("--skill-dir", required=True, help="the folder of the skill's SKILL.md")
    p.add_argument("--brand", required=True, help="the approved Brand pack folder")

    p = sub.add_parser("describe", help="change a Slides skill's trigger description everywhere")
    p.add_argument("--skill-dir", required=True)
    p.add_argument("--description", required=True)

    p = sub.add_parser("bump", help="raise a Slides skill's version in every manifest")
    p.add_argument("--skill-dir", required=True)
    p.add_argument("part", choices=("major", "minor", "patch"))

    p = sub.add_parser("pack-init", help="start a Brand pack from the Engine's plain pack")
    p.add_argument("--out", required=True, help="the new pack's folder, named after its slug")
    p.add_argument("--slug", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--alias", action="append", help="another name for the brand (repeatable)")

    p = sub.add_parser("pack-check", help="validate a Brand pack folder with this Generator's Engine")
    p.add_argument("--pack", required=True)

    p = sub.add_parser("extract-pptx", help="read theme colours, fonts and logo candidates from a .pptx")
    p.add_argument("input")
    p.add_argument("--out", required=True, help="folder for pptx-facts.json and media/")

    p = sub.add_parser("fonts", help="put font files in a pack: fonts/, fonts.css and brand.json")
    p.add_argument("--pack", required=True)
    p.add_argument("--src", nargs="+", required=True, help="font files: .woff2, .woff, .ttf or .otf")
    p.add_argument("--display", help="put this family first in --font-display")
    p.add_argument("--body", help="put this family first in --font-body")

    p = sub.add_parser("icons", help="build icon-library.js and icons.md from a folder of SVGs")
    p.add_argument("--pack", required=True)
    p.add_argument("--src", required=True)

    p = sub.add_parser("guard", help="write the contrast data from tokens.css and report contrast")
    p.add_argument("--pack", required=True)
    p.add_argument("--base", action="append", help="<theme>=<colour>: the solid colour under a gradient")
    p.add_argument("--neutral", action="append", help="treat this palette colour as a neutral")
    p.add_argument("--vivid", action="append", help="treat this palette colour as a vivid accent")

    p = sub.add_parser("calibrate", help="calibrate a pack's PowerPoint export (pptxLead)")
    p.add_argument("step", choices=("prepare", "fit"))
    p.add_argument("--skill-dir", required=True)
    p.add_argument("--brand", required=True)
    p.add_argument("--out", required=True, help="a folder outside the skill for the probe files")
    p.add_argument("--powerpoint", action="store_true", help="prepare: export the PDF through PowerPoint (macOS)")
    p.add_argument("--write", action="store_true", help="fit: store pptxLead in brand.json")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = run(args)
    except GenError as e:
        print(json.dumps({"error": {"message": str(e), **e.details}}, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if isinstance(result, dict) and result.get("valid") is False else 0


if __name__ == "__main__":
    sys.exit(main())
