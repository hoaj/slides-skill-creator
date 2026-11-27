import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import ACME, ENGINE, REPO, Workspace

sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(REPO / "scripts"))

from lib import triggers  # noqa: E402
from lib.common import DeckError  # noqa: E402

import trigger_evals  # noqa: E402

ACME_BRANDS = [("Acme", ["acme corp", "acme inc"])]
GOOD = ('---\nname: acme-slides\ndescription: "Builds decks for Acme (\\"Acme Corp\\", '
        '\\"Acme Inc\\"). Not for other brands."\n---\n\n# acme-slides\n')
FAKE = REPO / "tests" / "fake_claude.py"


def skill_md(description, name="acme-slides"):
    return f"---\nname: {name}\ndescription: {description}\n---\n\nBody.\n"


class CheckTest(unittest.TestCase):
    def test_a_good_description_passes(self):
        self.assertEqual(triggers.check_text(GOOD, "acme-slides", ACME_BRANDS), [])

    def test_quoted_and_plain_values_are_read(self):
        self.assertEqual(triggers.frontmatter(GOOD)["description"],
                         'Builds decks for Acme ("Acme Corp", "Acme Inc"). Not for other brands.')
        self.assertEqual(triggers.frontmatter(skill_md("It's plain. Not for x."))["description"],
                         "It's plain. Not for x.")

    def test_each_problem_is_reported(self):
        cases = {
            "differs from its folder": (skill_md("Acme. Not for x.", "other-slides"), []),
            "a-z, 0-9": (skill_md("Acme. Not for x.", "Acme_Slides"), []),
            "not for": (skill_md("Builds decks for Acme."), []),
            "over 1024": (skill_md("Not for x. " + "y" * 1020), []),
            "'acme inc'": (skill_md("Acme (acme corp). Not for x."), ACME_BRANDS),
            "one line each": ("---\nname: acme-slides\ndescription: >\n  Acme. Not for x.\n---\n", []),
            "no description": ("---\nname: acme-slides\n---\n", []),
            "no frontmatter": ("# acme-slides\n", []),
        }
        for expected, (text, brands) in cases.items():
            with self.subTest(expected):
                problems = triggers.check_text(text, "acme-slides", brands)
                self.assertTrue(any(expected in p for p in problems), problems)

    def test_brand_names_match_without_case(self):
        text = skill_md("For ACME, Acme Corp and ACME INC. Not for others.")
        self.assertEqual(triggers.check_text(text, "acme-slides", ACME_BRANDS), [])


class GeneratorSuiteTest(unittest.TestCase):
    def test_the_static_check_passes_on_this_repo(self):
        self.assertEqual(trigger_evals.check(), [])

    def test_the_cases_are_the_decided_ones(self):
        expects = {c["name"]: c["expect"] for c in trigger_evals.CASES}
        self.assertEqual(expects["deck-acme"], "acme-slides")
        self.assertEqual(expects["deck-plain"], "plain-slides")
        for name in ("new-skill", "add-brand", "edit-font", "upgrade"):
            self.assertEqual(expects[name], "slides-skill-creator")
        self.assertIsNone(expects["no-skill-brand"])
        self.assertIsNone(expects["fix-pptx"])

    def test_build_writes_the_competing_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "plugin"
            self.assertEqual(trigger_evals.main(["build", "--out", str(out)]), 0)
            manifest = json.loads((out / ".claude-plugin" / "plugin.json").read_text())
            self.assertEqual(manifest["skills"], ["./skills/slides-skill-creator",
                                                  "./skills/acme-slides", "./skills/plain-slides"])
            graders = sorted(p.name for p in (out / "evals" / "upgrade" / "graders").iterdir())
            self.assertEqual(graders, ["quiet-acme-slides.md", "quiet-plain-slides.md", "says.md",
                                       "starts-slides-skill-creator.md"])
            self.assertIn("max_turns: 8", (out / "evals" / "upgrade" / "prompt.md").read_text())


class CasesTest(unittest.TestCase):
    def test_each_brand_and_alias_gets_a_case_and_two_must_stay_quiet(self):
        cases = triggers.slides_cases("acme-slides", ACME_BRANDS)
        self.assertEqual([c["name"] for c in cases],
                         ["deck-acme", "alias-acme-1", "alias-acme-2", "other-brand", "fix-pptx"])
        self.assertIn("acme inc", cases[2]["prompt"])
        self.assertEqual([c["expect"] for c in cases[-2:]], [None, None])

    def test_the_other_brand_is_never_one_the_skill_names(self):
        cases = triggers.slides_cases("x-slides", [("Brightfield", ["larkspur"])])
        other = next(c for c in cases if c["name"] == "other-brand")
        self.assertIn("Quillon", other["prompt"])

    def test_the_start_pattern_matches_only_that_skill(self):
        pattern = re.compile(triggers._skill_pattern("acme-slides"))
        self.assertTrue(pattern.search('{"skill": "acme-slides"}'))
        self.assertTrue(pattern.search('{"skill":"acme:acme-slides"}'))
        self.assertFalse(pattern.search('{"skill": "acme-slides-feedback"}'))
        self.assertFalse(pattern.search('{"skill": "plain-slides"}'))

    def test_a_case_must_expect_a_skill_the_plugin_has(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = pathlib.Path(tmp) / "src" / "acme-slides"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(GOOD)
            with self.assertRaisesRegex(DeckError, "lacks"):
                triggers.build_plugin(pathlib.Path(tmp) / "out", [source],
                                      [triggers.case("x", "p", "other-slides")])


def run(graders):
    return {"error": None, "graders": [{"name": n, "passed": p} for n, p in graders.items()]}


class VerdictTest(unittest.TestCase):
    START = triggers.case("deck-acme", "p", "acme-slides")
    QUIET = triggers.case("fix-pptx", "p", None)

    def verdict(self, case, runs):
        report = {"cases": [{"name": case["name"], "arms": {"with": runs}}]}
        return triggers.verdicts(report, [case])[0]

    def test_a_start_may_be_missed_once_in_three(self):
        ok = run({"starts-acme-slides": True, "quiet-plain-slides": True})
        miss = run({"starts-acme-slides": False, "quiet-plain-slides": True})
        self.assertTrue(self.verdict(self.START, [ok, ok, miss])["passed"])
        self.assertFalse(self.verdict(self.START, [ok, miss, miss])["passed"])

    def test_a_wrong_start_fails_even_once(self):
        ok = run({"starts-acme-slides": True, "quiet-plain-slides": True})
        wrong = run({"starts-acme-slides": True, "quiet-plain-slides": False})
        self.assertFalse(self.verdict(self.START, [ok, ok, wrong])["passed"])
        quiet = run({"quiet-acme-slides": True})
        loud = run({"quiet-acme-slides": False})
        self.assertTrue(self.verdict(self.QUIET, [quiet, quiet, quiet])["passed"])
        self.assertFalse(self.verdict(self.QUIET, [quiet, quiet, loud])["passed"])

    def test_a_run_cut_off_at_the_turn_limit_is_judged_by_its_graders(self):
        cut = {"error": "exit 1: Reached maximum number of turns (3)",
               "graders": [{"name": "quiet-acme-slides", "passed": True}]}
        self.assertTrue(self.verdict(self.QUIET, [cut, cut, cut])["passed"])

    def test_a_run_that_errored_or_a_missing_case_fails(self):
        errored = {"error": "api_error", "graders": []}
        self.assertFalse(self.verdict(self.QUIET, [run({"quiet-acme-slides": True})] * 2 + [errored])["passed"])
        self.assertFalse(triggers.verdicts({"cases": []}, [self.QUIET])[0]["passed"])


class DeckCommandsTest(unittest.TestCase):
    """deck.py check and eval in a plugin: <root>/plugin/skills/acme-slides."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name).resolve()
        self.plugin = self.root / "plugin"
        self.skill = self.plugin / "skills" / "acme-slides"
        shutil.copytree(ENGINE, self.skill / "engine", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ACME, self.skill / "brands" / "acme")
        (self.skill / "SKILL.md").write_text(GOOD)
        (self.plugin / ".claude-plugin").mkdir()
        (self.plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "acme-slides", "skills": ["./skills/acme-slides"]}))
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        claude.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n')
        claude.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    def tearDown(self):
        self.tmp.cleanup()

    def deck(self, *args, **env):
        return subprocess.run([sys.executable, str(self.skill / "engine" / "deck.py"), *args],
                              cwd=str(self.root), capture_output=True, text=True,
                              env={**self.env, **env})

    def test_check_reports_a_description_that_misses_an_alias(self):
        result = self.deck("check")
        self.assertIn("SKILL.md: valid, 0 error(s)", result.stdout)
        (self.skill / "SKILL.md").write_text(skill_md("Builds decks for Acme. Not for others."))
        result = self.deck("check")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("does not name 'acme corp'", result.stdout)
        self.assertIn("Checked 2 Brand pack(s) and SKILL.md: 2 error(s)", result.stdout)

    def test_check_of_one_brand_leaves_skill_md_alone(self):
        (self.skill / "SKILL.md").write_text(skill_md("No brand here. Not for others."))
        self.assertEqual(self.deck("check", "--brand", "acme").returncode, 0)

    @unittest.skipIf(os.name == "nt", "the fake claude is a shell script")
    def test_eval_passes_fails_and_cannot_run(self):
        log = self.root / "args.json"
        result = self.deck("eval", FAKE_CLAUDE_LOG=str(log))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("5 of 5 case(s) passed.", result.stdout)
        args = json.loads(log.read_text())
        for flag in ("--no-publish", "--trust-plugin", "--ablation"):
            self.assertIn(flag, args)

        result = self.deck("eval", FAKE_CLAUDE_WRONG="fix-pptx")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL  fix-pptx", result.stdout)
        self.assertEqual(self.deck("eval", FAKE_CLAUDE_MISS="deck-acme:1").returncode, 0)
        self.assertEqual(self.deck("eval", FAKE_CLAUDE_MISS="deck-acme:2").returncode, 1)
        self.assertEqual(self.deck("eval", FAKE_CLAUDE_EXIT="2").returncode, 2)

    @unittest.skipIf(os.name == "nt", "the fake claude is a shell script")
    def test_eval_keeps_the_plugin_and_report_outside_the_skill(self):
        out = self.root / "kept"
        result = self.deck("eval", "--out", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out / "report.json").is_file())
        self.assertTrue((out / "plugin" / "evals" / "deck-acme" / "prompt.md").is_file())
        self.assertEqual(self.deck("eval", "--out", str(self.skill / "x")).returncode, 2)

    def test_eval_outside_a_plugin_cannot_run(self):
        ws = Workspace()
        try:
            ws.add_acme()
            result = ws.deck("eval")
            self.assertEqual(result.returncode, 2)
            self.assertIn("not in a plugin", result.stderr)
        finally:
            ws.close()


if __name__ == "__main__":
    unittest.main()
