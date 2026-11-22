"""The Starter files: rendering, the assembled Slides skill and engine.lock."""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import ACME, REPO

sys.path.insert(0, str(REPO / "starter"))

import render  # noqa: E402
from lib import lock  # noqa: E402

VALUES = {
    "skill": "acme-slides",
    "description": 'Builds decks for Acme ("acme corp"): on brand. Not for other brands.',
    "repo": "acme-example/acme-slides",
    "author": "Acme Maintainers",
}
MANIFESTS = (".claude-plugin/plugin.json", ".cursor-plugin/plugin.json", ".github/plugin/plugin.json")
MARKETPLACES = (".claude-plugin/marketplace.json", ".cursor-plugin/marketplace.json",
                ".github/plugin/marketplace.json")


def frontmatter(text):
    """{key: raw value} from a SKILL.md's frontmatter."""
    block = text.split("---\n")[1]
    return dict(line.split(": ", 1) for line in block.strip().splitlines())


class RenderTests(unittest.TestCase):
    def test_standalone_is_its_own_marketplace(self):
        files = render.render_files(VALUES)
        for path in MANIFESTS + MARKETPLACES:
            data = json.loads(files[path])
            self.assertEqual(data["name"], "acme-slides")
        for path in ("skills/acme-slides/SKILL.md", "skills/acme-slides-feedback/SKILL.md",
                     ".github/workflows/acme-slides-ci.yml",
                     ".github/workflows/acme-slides-release.yml", ".gitignore"):
            self.assertIn(path, files)

    def test_shared_places_the_plugin_in_its_folder(self):
        files = render.render_files({**VALUES, "layout": "shared"})
        for path in MANIFESTS:
            self.assertIn(f"plugins/acme-slides/{path}", files)
        self.assertFalse([p for p in files if p.endswith("marketplace.json")])
        ci = files[".github/workflows/acme-slides-ci.yml"]
        self.assertIn("- plugins/acme-slides/**", ci)
        self.assertIn("working-directory: plugins/acme-slides", ci)
        release = files[".github/workflows/acme-slides-release.yml"]
        self.assertIn('tag="acme-slides-v$version"', release)
        self.assertIn("--latest=false", release)

    def test_nothing_is_left_unrendered(self):
        for layout in ("standalone", "shared"):
            for path, text in render.render_files({**VALUES, "layout": layout}).items():
                self.assertIsNone(re.search(r"__[A-Z][A-Z_]*__|#@(standalone|shared)", path + text),
                                  path)

    def test_description_survives_quotes_and_colons(self):
        files = render.render_files(VALUES)
        for path in MANIFESTS:
            self.assertEqual(json.loads(files[path])["description"], VALUES["description"])
        raw = frontmatter(files["skills/acme-slides/SKILL.md"])["description"]
        self.assertEqual(json.loads(raw), VALUES["description"])

    def test_a_token_inside_a_value_is_not_expanded(self):
        files = render.render_files({**VALUES, "description": "Keeps __SKILL__ as written."})
        self.assertEqual(json.loads(files[MANIFESTS[0]])["description"],
                         "Keeps __SKILL__ as written.")

    def test_skill_md_is_thin_and_hands_off_to_the_workflow(self):
        text = render.render_files(VALUES)["skills/acme-slides/SKILL.md"]
        self.assertLessEqual(len(text.splitlines()), 50)
        self.assertIn("engine/workflow.md", text)
        self.assertRegex(text, r"(?m)^## Local rules$")
        self.assertTrue(text.rstrip().endswith("-->"), "Local rules must be the last section")

    def test_feedback_skill_holds_the_forwarding_step(self):
        text = render.render_files(VALUES)["skills/acme-slides-feedback/SKILL.md"]
        for expected in ("doctor --report", "--brand plain", "hoaj/slides-skill-creator",
                         "never links back", "--repo acme-example/acme-slides"):
            self.assertIn(expected, text)

    def test_skill_descriptions_fit_the_limit(self):
        files = render.render_files(VALUES)
        feedback = frontmatter(files["skills/acme-slides-feedback/SKILL.md"])["description"]
        self.assertLessEqual(len(feedback), render.MAX_DESCRIPTION)
        generator = (REPO / "skills/slides-skill-creator-feedback/SKILL.md").read_text("utf-8")
        self.assertLessEqual(len(frontmatter(generator)["description"]), render.MAX_DESCRIPTION)

    def test_bad_values_are_refused(self):
        bad = ({"skill": "acme"}, {"skill": "Acme-slides"}, {"skill": "a" * 60 + "-slides"},
               {"repo": "acme"}, {"version": "1.0"}, {"layout": "nested"},
               {"description": "two\nlines"}, {"description": "x" * 1025}, {"author": ""},
               {"surprise": "value"}, {"author": 3})
        for change in bad:
            with self.subTest(change), self.assertRaises(render.StarterError):
                render.render_files({**VALUES, **change})


class CreateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)
        self.out = self.root / "repo"
        self.skill = self.out / "skills" / "acme-slides"

    def deck(self, *args):
        return subprocess.run([sys.executable, "-I", "-S", str(self.skill / "engine/deck.py"), *args],
                              cwd=str(self.root), capture_output=True, text=True)

    def test_the_skill_passes_check_and_builds_its_sample_deck(self):
        render.create(VALUES, self.out, [ACME])
        check = self.deck("check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("acme: valid", check.stdout)
        sample = self.root / "acme-sample.html"
        built = self.deck("sample", "--brand", "acme", str(sample))
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertGreater(sample.stat().st_size, 10000)

    def test_lock_records_the_engine_and_the_values(self):
        render.create(VALUES, self.out, [ACME])
        data = lock.read(self.skill / "engine.lock")
        self.assertEqual(set(data), {"version", "commit", "archiveSha256", "engineTreeHash",
                                     "starterTreeHash", "formatVersion", "starterValues",
                                     "engineFiles"})
        self.assertEqual(data["engineTreeHash"], lock.tree_hash(self.skill / "engine"))
        self.assertEqual(data["engineFiles"], lock.file_hashes(self.skill / "engine"))
        self.assertEqual(data["starterValues"],
                         {**VALUES, "version": "0.1.0", "layout": "standalone"})
        self.assertEqual(render.render_files(data["starterValues"]), render.render_files(VALUES))

    def test_nothing_is_written_over_an_existing_file(self):
        target = self.out / ".claude-plugin" / "plugin.json"
        target.parent.mkdir(parents=True)
        target.write_text("mine", encoding="utf-8")
        with self.assertRaises(render.StarterError):
            render.create(VALUES, self.out, [ACME])
        self.assertEqual(target.read_text(encoding="utf-8"), "mine")
        self.assertFalse((self.out / "skills").exists())

    def test_the_hidden_pack_cannot_be_added(self):
        plain = self.root / "plain"
        shutil.copytree(ACME, plain)
        with self.assertRaises(render.StarterError):
            render.create(VALUES, self.out, [plain])

    def test_cli_prints_json_and_reports_errors(self):
        values = self.root / "values.json"
        values.write_text(json.dumps(VALUES), encoding="utf-8")
        cmd = [sys.executable, str(REPO / "starter/render.py"), "--values", str(values),
               "--brand", str(ACME), "--out", str(self.out)]
        first = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["brands"], ["acme"])
        second = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(second.returncode, 1)
        self.assertIn("already exists", second.stderr)

    @unittest.skipUnless(shutil.which("actionlint"), "actionlint is not installed")
    def test_workflows_pass_actionlint(self):
        for layout in ("standalone", "shared"):
            out = self.root / layout
            render.create({**VALUES, "layout": layout}, out, [ACME])
            subprocess.run(["git", "init", "-q"], cwd=str(out), check=True)
            result = subprocess.run(["actionlint"], cwd=str(out), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def report_line(self):
        result = self.deck("doctor", "--report")
        self.assertEqual(result.returncode, 0, result.stderr)
        return re.search(r"Engine files edited locally: (.*)", result.stdout).group(1)

    def test_report_names_edited_and_removed_engine_files(self):
        render.create(VALUES, self.out, [ACME])
        self.assertEqual(self.report_line(), "none")
        with (self.skill / "engine/runtime/widgets.css").open("a", encoding="utf-8") as f:
            f.write("/* local */\n")
        (self.skill / "engine/docs/roadmaps.md").unlink()
        line = self.report_line()
        self.assertIn("runtime/widgets.css", line)
        self.assertIn("docs/roadmaps.md (removed)", line)

    def test_report_counts_added_files_without_naming_them(self):
        render.create(VALUES, self.out, [ACME])
        (self.skill / "engine/private-brand-patch.py").write_text("x = 1\n", encoding="utf-8")
        line = self.report_line()
        self.assertIn("1 added file(s)", line)
        self.assertNotIn("private-brand-patch", line)

    def test_report_survives_a_broken_lock(self):
        render.create(VALUES, self.out, [ACME])
        (self.skill / "engine.lock").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.report_line(), "unknown (engine.lock cannot be read)")


class TreeHashTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.root / "a").mkdir()
        (self.root / "a/file.txt").write_text("one", encoding="utf-8")

    def test_ignores_caches_and_sees_content_and_names(self):
        before = lock.tree_hash(self.root)
        (self.root / "a/__pycache__").mkdir()
        (self.root / "a/__pycache__/x.cpython-39.pyc").write_bytes(b"\0")
        (self.root / ".DS_Store").write_bytes(b"\0")
        self.assertEqual(lock.tree_hash(self.root), before)
        (self.root / "a/file.txt").write_text("two", encoding="utf-8")
        changed = lock.tree_hash(self.root)
        self.assertNotEqual(changed, before)
        os.rename(self.root / "a/file.txt", self.root / "a/renamed.txt")
        self.assertNotEqual(lock.tree_hash(self.root), changed)


if __name__ == "__main__":
    unittest.main()
