"""A stand-in for `claude plugin eval` that writes a report, so the eval tests run offline.

    FAKE_CLAUDE_WRONG  a case whose quiet graders fail in one run (a wrong skill started)
    FAKE_CLAUDE_MISS   a case whose start graders fail in this many runs
    FAKE_CLAUDE_EXIT   the exit code, without a report when it is not 0 or 1
    FAKE_CLAUDE_LOG    the arguments, as one JSON list
"""
import json
import os
import pathlib
import sys


def main(args):
    if os.environ.get("FAKE_CLAUDE_LOG"):
        pathlib.Path(os.environ["FAKE_CLAUDE_LOG"]).write_text(json.dumps(args), encoding="utf-8")
    code = int(os.environ.get("FAKE_CLAUDE_EXIT", "0"))
    if code not in (0, 1):
        return code
    plugin = pathlib.Path(args[2])
    runs = int(args[args.index("--runs") + 1])
    wrong = os.environ.get("FAKE_CLAUDE_WRONG")
    miss_case, _, misses = os.environ.get("FAKE_CLAUDE_MISS", "").partition(":")
    cases = []
    for folder in sorted((plugin / "evals").iterdir()):
        graders = sorted(p.stem for p in (folder / "graders").iterdir())
        arm = []
        for i in range(runs):
            results = []
            for name in graders:
                quiet = name.startswith("quiet-")
                failed = ((quiet and folder.name == wrong and i == 0)
                          or (not quiet and folder.name == miss_case and i < int(misses or 0)))
                results.append({"name": name, "passed": not failed, "scored": True})
            arm.append({"passed": all(r["passed"] for r in results), "error": None,
                        "graders": results})
        cases.append({"name": folder.name, "arms": {"with": arm}})
    report = {"schemaVersion": 1, "partial": False, "cases": cases}
    pathlib.Path(args[args.index("--json") + 1]).write_text(json.dumps(report), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
