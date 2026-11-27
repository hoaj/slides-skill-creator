"""A stand-in for `gh` that serves releases from a folder, so Upgrade's tests run offline.

    FAKE_GH_RELEASES  <dir>/<tag>/assets/*, <dir>/<tag>/notes.md, <dir>/<tag>/prerelease
    FAKE_GH_LOG       every call, one JSON list per line, and the PR body in <log>.body
    FAKE_GH_FAIL      a command such as "release verify-asset" that fails
    FAKE_GH_VERSION   the version `gh --version` prints (default 2.90.0)

An asset passes `verify-asset` and `attestation verify` only when its bytes are the published ones.
"""
import json
import os
import pathlib
import shutil
import sys

SIGNER = "hoaj/slides-skill-creator/.github/workflows/release.yml"


def option(args, name):
    return args[args.index(name) + 1] if name in args else None


def main(args):
    releases = pathlib.Path(os.environ["FAKE_GH_RELEASES"])
    if os.environ.get("FAKE_GH_LOG"):
        with open(os.environ["FAKE_GH_LOG"], "a", encoding="utf-8") as log:
            log.write(json.dumps(args) + "\n")
    if args == ["--version"]:
        print(f"gh version {os.environ.get('FAKE_GH_VERSION', '2.90.0')} (2026-01-01)")
        return 0
    command = " ".join(args[:2])
    if command == os.environ.get("FAKE_GH_FAIL"):
        print(f"fake failure of gh {command}", file=sys.stderr)
        return 1
    published = [p.read_bytes() for tag in releases.iterdir() for p in (tag / "assets").iterdir()]
    if command == "release list":
        print(json.dumps([{"tagName": t.name, "isPrerelease": (t / "prerelease").exists()}
                          for t in sorted(releases.iterdir())]))
    elif command == "release download":
        dest = pathlib.Path(option(args, "-D"))
        dest.mkdir(parents=True, exist_ok=True)
        for asset in (releases / args[2] / "assets").iterdir():
            shutil.copy(str(asset), str(dest / asset.name))
    elif command == "release verify":
        return 0 if (releases / args[2]).is_dir() else 1
    elif command == "release verify-asset":
        asset = releases / args[2] / "assets" / pathlib.Path(args[3]).name
        return 0 if asset.is_file() and asset.read_bytes() == pathlib.Path(args[3]).read_bytes() else 1
    elif command == "attestation verify":
        data = pathlib.Path(args[2]).read_bytes()
        return 0 if option(args, "--signer-workflow") == SIGNER and data in published else 1
    elif command == "release view":
        print((releases / args[2] / "notes.md").read_text(encoding="utf-8"))
    elif command == "pr create":
        if os.environ.get("FAKE_GH_LOG"):
            body = pathlib.Path(option(args, "--body-file")).read_text(encoding="utf-8")
            pathlib.Path(os.environ["FAKE_GH_LOG"] + ".body").write_text(body, encoding="utf-8")
        print("https://github.com/example/acme-slides/pull/1")
    else:
        print(f"fake gh does not know: {command}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
