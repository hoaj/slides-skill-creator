"""`deck.py upgrade` between two local fixture releases, served by a fake `gh`."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import ACME, REPO
from tests.test_release import Repo

sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "upgrade"))

import merge  # noqa: E402
import release  # noqa: E402

OLD, NEW = "0.1.0-rc.1", "0.1.0-rc.2"
VALUES = {"skill": "acme-slides", "description": "Builds decks for Acme (Acme Corp, Acme Inc). Not for other brands.",
          "repo": "example/acme-slides", "author": "Example"}
MIGRATION = '''import json


def migrate(pack):
    path = pack / "brand.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["formatVersion"] = 2
    path.write_text(json.dumps(data, indent=2) + "\\n", encoding="utf-8")
    return ["playbook/interview.md: check each rule's wording"] if (pack / "playbook" / "interview.md").is_file() else []
'''


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def first_line(path, text):
    lines = path.read_text(encoding="utf-8").splitlines(True)
    path.write_text(text + "\n" + "".join(lines[1:]), encoding="utf-8")


class Releases:
    """v0.1.0-rc.1 from this repo, and v0.1.0-rc.2 with one change for each merge rule."""

    def __init__(self, root):
        self.dir = root / "releases"
        self.source = Repo(OLD)
        self.publish(OLD, "First candidate.")
        src = self.source.root
        docs = src / "engine" / "docs"
        (docs / "widgets.md").write_text((docs / "widgets.md").read_text() + "\nUpstream only.\n")
        first_line(docs / "html-template.md", "# Upstream title")
        (docs / "brand-pack.md").write_text((docs / "brand-pack.md").read_text() + "\nUpstream end.\n")
        (docs / "new-topic.md").write_text("# New upstream topic\n")
        (docs / "pptx-export.md").unlink()
        (docs / "slide-templates.md").unlink()
        edit(src / "engine" / "lib" / "validate.py", "FORMAT_VERSION = 1", "FORMAT_VERSION = 2")
        edit(src / "engine" / "fixtures" / "plain" / "brand.json", '"formatVersion": 1', '"formatVersion": 2')
        (src / "migrations" / "format_2.py").write_text(MIGRATION)
        template = src / "starter" / "files" / "plugin" / "skills" / "__SKILL__" / "SKILL.md"
        edit(template, "Builds on-brand HTML slide decks", "Builds on-brand HTML slide decks, upgraded,")
        (src / "starter" / "files" / "plugin" / ".gitignore").unlink()
        (template.parent / "reference.md").write_text("# __SKILL__ reference\n")
        self.source.set_version(NEW)
        self.source.commit("rc.2")
        self.publish(NEW, "Second candidate.")

    def publish(self, version, notes):
        folder = self.dir / f"v{version}"
        release.build(self.source.root, folder / "assets")
        (folder / "notes.md").write_text(notes)
        (folder / "prerelease").touch()

    def close(self):
        self.source.close()


class UpgradeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls._tmp.name).resolve()
        cls.releases = Releases(cls.root)
        cls.bin = cls.root / "bin"
        cls.bin.mkdir()
        gh = cls.bin / "gh"
        gh.write_text(f"#!{sys.executable}\nimport runpy, sys\nsys.argv[0] = {str(REPO / 'tests' / 'fake_gh.py')!r}\n"
                      f"runpy.run_path(sys.argv[0], run_name='__main__')\n")
        gh.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls.releases.close()
        cls._tmp.cleanup()

    def setUp(self):
        self.work = pathlib.Path(tempfile.mkdtemp(dir=str(self.root)))
        self.repo = self.work / "acme-slides"
        self.skill = self.repo / "skills" / "acme-slides"
        self.log = self.work / "gh.log"
        (self.work / "values.json").write_text(json.dumps(VALUES))
        old_render = self.root / "rc1-source"
        if not old_render.exists():
            with tempfile.TemporaryDirectory() as unpack:
                subprocess.run(["tar", "-xzf", str(self.releases.dir / f"v{OLD}" / "assets" /
                                                   f"slides-skill-{OLD}.tar.gz"), "-C", unpack], check=True)
                shutil.copytree(unpack, str(old_render))
        subprocess.run([sys.executable, str(old_render / "starter" / "render.py"), "--values",
                        str(self.work / "values.json"), "--brand", str(ACME), "--out", str(self.repo)],
                       check=True, capture_output=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "test")
        self.commit("acme-slides")
        subprocess.run(["git", "init", "-q", "--bare", str(self.work / "remote.git")], check=True)
        self.git("remote", "add", "origin", str(self.work / "remote.git"))
        self.git("push", "-q", "origin", "main")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True).stdout

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def env(self, **extra):
        env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                   FAKE_GH_RELEASES=str(self.releases.dir), FAKE_GH_LOG=str(self.log))
        env.update(extra)
        return env

    def deck(self, *args, **env):
        return subprocess.run([sys.executable, str(self.skill / "engine" / "deck.py"), *args],
                              cwd=str(self.work), capture_output=True, text=True, env=self.env(**env))

    @property
    def state(self):
        return pathlib.Path(self.git("rev-parse", "--absolute-git-dir").strip()) / "slides-upgrade"

    def upgrade_script(self, *args, **env):
        script = self.state / "new" / "release" / "upgrade" / "upgrade.py"
        return subprocess.run([sys.executable, str(script), *args], cwd=str(self.work),
                              capture_output=True, text=True, env=self.env(**env))

    def gh_calls(self, command):
        if not self.log.exists():
            return []
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        return [c for c in calls if " ".join(c[:2]) == command]

    def local_edits(self):
        docs = self.skill / "engine" / "docs"
        first_line(docs / "roadmaps.md", "# Local roadmaps")
        first_line(docs / "html-template.md", "# Local title")
        first_line(docs / "brand-pack.md", "# Local brand pack")
        (docs / "slide-templates.md").write_text((docs / "slide-templates.md").read_text() + "\nLocal note.\n")
        edit(self.skill / "SKILL.md", "Upgrade never changes this section. -->",
             "Upgrade never changes this section. -->\n\n- Always cite the source on chart slides.")
        self.commit("local edits")

    def resolve(self):
        """Do what the coding agent does: resolve each file and state each decision."""
        html = self.skill / "engine" / "docs" / "html-template.md"
        if merge.has_markers(html):
            text = html.read_text().split("\n")
            start = next(i for i, l in enumerate(text) if l.startswith("<<<<<<< "))
            end = next(i for i, l in enumerate(text) if l.startswith(">>>>>>> "))
            html.write_text("\n".join(text[:start] + ["# Local title"] + text[end + 1:]))
        decisions = self.state / "decisions.md"
        decisions.write_text(decisions.read_text().replace("Decision: TODO", "Decision: kept the local wording."))

    # --- the full upgrade -----------------------------------------------------------------

    def test_check_reports_a_newer_release_and_changes_nothing(self):
        result = self.deck("upgrade", "--check")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no stable release yet", result.stderr)
        result = self.deck("upgrade", "--check", "--to", NEW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"The newest release is {NEW}", result.stdout)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_upgrade_applies_every_merge_rule_and_a_format_migration(self):
        self.local_edits()
        result = self.deck("upgrade", "--to", NEW)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        engine, docs = self.skill / "engine", self.skill / "engine" / "docs"

        # Changed only upstream, only locally, new upstream and removed upstream unedited.
        self.assertIn("Upstream only.", (docs / "widgets.md").read_text())
        self.assertTrue((docs / "roadmaps.md").read_text().startswith("# Local roadmaps"))
        self.assertEqual((docs / "new-topic.md").read_text(), "# New upstream topic\n")
        self.assertFalse((docs / "pptx-export.md").exists())
        # Changed on both sides: markers when they disagree, a clean merge when they do not.
        self.assertTrue(merge.has_markers(docs / "html-template.md"))
        brand_pack = (docs / "brand-pack.md").read_text()
        self.assertTrue(brand_pack.startswith("# Local brand pack") and "Upstream end." in brand_pack)
        # Removed upstream but edited: kept for the coding agent.
        self.assertIn("Local note.", (docs / "slide-templates.md").read_text())
        # Starter files: removed upstream is reported and kept, new upstream is added.
        self.assertTrue((self.repo / ".gitignore").exists())
        self.assertEqual((self.skill / "reference.md").read_text(), "# acme-slides reference\n")
        skill_md = (self.skill / "SKILL.md").read_text()
        self.assertIn("decks, upgraded,", skill_md)
        self.assertIn("- Always cite the source on chart slides.", skill_md)
        # The format migration ran.
        self.assertEqual(json.loads((self.skill / "brands" / "acme" / "brand.json").read_text())["formatVersion"], 2)

        decisions = (self.state / "decisions.md").read_text()
        for title in ("engine/docs/html-template.md", "engine/docs/brand-pack.md",
                      "engine/docs/slide-templates.md", "skills/acme-slides/SKILL.md",
                      "Migration flag: acme: playbook/interview.md"):
            self.assertIn(title, decisions)
        self.assertNotIn("widgets.md", decisions)

        refused = self.upgrade_script("continue")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("still need a decision", refused.stderr)
        self.resolve()
        result = self.upgrade_script("continue")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Opened a draft PR that moves the skill from 0.1.0 to 0.1.1", result.stdout)

        self.assertFalse(self.state.exists())
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), f"slides-upgrade/v{NEW}")
        self.assertEqual(self.git("status", "--porcelain"), "")
        pushed = subprocess.run(["git", "-C", str(self.work / "remote.git"), "branch", "--list"],
                                capture_output=True, text=True).stdout
        self.assertIn(f"slides-upgrade/v{NEW}", pushed)
        recorded = json.loads((self.skill / "engine.lock").read_text())
        manifest = json.loads((self.releases.dir / f"v{NEW}" / "assets" / "release-manifest.json").read_text())
        self.assertEqual((recorded["version"], recorded["formatVersion"], recorded["engineTreeHash"]),
                         (NEW, 2, manifest["engineTreeHash"]))
        self.assertEqual(recorded["starterValues"]["version"], "0.1.1")
        for manifest_path in (".claude-plugin/plugin.json", ".cursor-plugin/plugin.json", ".github/plugin/plugin.json"):
            self.assertEqual(json.loads((self.repo / manifest_path).read_text())["version"], "0.1.1")

        doctor = self.deck("doctor", "--report")
        self.assertIn("edited locally: docs/brand-pack.md, docs/html-template.md, docs/roadmaps.md, 1 added", doctor.stdout)

        self.assertIn("--draft", self.gh_calls("pr create")[-1])

    def test_the_pr_reports_notes_edits_decisions_migrations_and_checks(self):
        self.local_edits()
        self.deck("upgrade", "--to", NEW)
        self.resolve()
        result = self.upgrade_script("continue")
        self.assertEqual(result.returncode, 0, result.stderr)
        pr = self.gh_calls("pr create")[-1]
        self.assertEqual(pr[pr.index("--base") + 1], "main")
        self.assertEqual(pr[pr.index("--title") + 1], f"Upgrade the Engine to {NEW}")
        body = pathlib.Path(str(self.log) + ".body").read_text()
        for expected in ("**Draft:** A comparison could not run",
                         "| deck.py check | pass |", "| Sample deck for acme | pass |",
                         "| Compare HTML, PDF and PowerPoint for acme | not run |",
                         f"#### v{NEW}", "Second candidate.",
                         "- Edited: `docs/roadmaps.md`", "- Edited: `docs/slide-templates.md`",
                         "- **skills/acme-slides/engine/docs/html-template.md:** kept the local wording.",
                         "- Engine, Added: `docs/new-topic.md`", "- Engine, Removed: `docs/pptx-export.md`",
                         "- Starter, Removed upstream, kept here: `.gitignore`", "- To format 2"):
            self.assertIn(expected, body)
        self.assertNotIn(f"#### v{OLD}", body)
        self.assertIn(f"Upgrade the Engine to {NEW}", self.git("log", "-1", "--format=%s"))

    def test_a_failed_check_stops_then_opens_a_draft_with_the_report(self):
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_fails.py").write_text(
            "import unittest\n\nclass T(unittest.TestCase):\n    def test_fails(self):\n        self.fail('no')\n")
        self.commit("a failing test")
        self.assertEqual(self.deck("upgrade", "--to", NEW).returncode, 3)
        self.resolve()
        stopped = self.upgrade_script("continue")
        self.assertEqual(stopped.returncode, 3, stopped.stdout + stopped.stderr)
        self.assertIn("The skill's tests", stopped.stdout)
        self.assertEqual(self.gh_calls("pr create"), [])
        result = self.upgrade_script("continue", "--draft")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--draft", self.gh_calls("pr create")[-1])

    def test_continue_refuses_markers_and_changed_local_rules(self):
        self.local_edits()
        self.deck("upgrade", "--to", NEW)
        decisions = self.state / "decisions.md"
        decisions.write_text(decisions.read_text().replace("Decision: TODO", "Decision: done."))
        result = self.upgrade_script("continue")
        self.assertEqual(result.returncode, 1)
        self.assertIn("conflict markers", result.stderr)
        self.resolve()
        edit(self.skill / "SKILL.md", "- Always cite", "- Never cite")
        result = self.upgrade_script("continue")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Local rules", result.stderr)

    def test_abort_puts_the_repo_back(self):
        self.local_edits()
        before = self.git("rev-parse", "HEAD")
        self.assertEqual(self.deck("upgrade", "--to", NEW).returncode, 3)
        result = self.upgrade_script("abort")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), before)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), "main")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertFalse(self.state.exists())
        self.assertNotIn("slides-upgrade", self.git("branch", "--list"))

    # --- refusals -----------------------------------------------------------------------------

    def assertRefused(self, result, text):
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(text, result.stderr)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").strip(), "main")

    def test_a_dirty_tree_is_refused(self):
        (self.skill / "SKILL.md").write_text("edited")
        self.assertRefused(self.deck("upgrade", "--to", NEW), "uncommitted changes")

    def test_an_old_gh_is_refused(self):
        self.assertRefused(self.deck("upgrade", "--to", NEW, FAKE_GH_VERSION="2.80.0"), "2.81 or later")

    def test_an_unverified_release_is_refused(self):
        for failing in ("release verify", "release verify-asset", "attestation verify"):
            self.assertRefused(self.deck("upgrade", "--to", NEW, FAKE_GH_FAIL=failing), failing)

    def test_a_tampered_archive_is_refused(self):
        tampered = self.work / "releases"
        shutil.copytree(str(self.releases.dir), str(tampered))
        sums = tampered / f"v{NEW}" / "assets" / "SHA256SUMS"
        sums.write_text("0" * 64 + sums.read_text()[64:])
        self.assertRefused(self.deck("upgrade", "--to", NEW, FAKE_GH_RELEASES=str(tampered)),
                           "does not match SHA256SUMS")

    def test_a_downgrade_and_an_unknown_release_are_refused(self):
        lock = self.skill / "engine.lock"
        lock.write_text(lock.read_text().replace(f'"version": "{OLD}"', f'"version": "{NEW}"'))
        self.commit("pretend rc.2")
        self.assertRefused(self.deck("upgrade", "--to", OLD), "never downgrades")
        self.assertIn("already", self.deck("upgrade", "--to", NEW).stdout)
        self.assertRefused(self.deck("upgrade", "--to", "9.9.9"), "no release v9.9.9")

    def test_an_installed_copy_is_refused(self):
        cache = self.work / ".claude" / "plugins" / "cache" / "m" / "acme-slides"
        shutil.copytree(str(self.skill), str(cache))
        result = subprocess.run([sys.executable, str(cache / "engine" / "deck.py"), "upgrade"],
                                capture_output=True, text=True, env=self.env())
        self.assertEqual(result.returncode, 1)
        self.assertIn("installed copy", result.stderr)


class MergeTest(unittest.TestCase):
    """The merge rules on small maps, including the cases the fixture releases do not reach."""

    def merge(self, base, ours, theirs, kind="engine"):
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp)
            for path, data in ours.items():
                (target / path).write_bytes(data)
            summary = merge.three_way(base, ours, theirs, target, kind, target / "upstream")
            return summary, {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}

    def test_each_rule(self):
        base = {"up": b"1\n", "local": b"1\n", "gone": b"1\n", "gone-edited": b"1\n", "same": b"1\n"}
        ours = {"up": b"1\n", "local": b"2\n", "gone": b"1\n", "gone-edited": b"2\n", "same": b"2\n",
                "mine": b"m\n"}
        theirs = {"up": b"2\n", "local": b"1\n", "same": b"2\n", "new": b"n\n"}
        summary, files = self.merge(base, ours, theirs)
        self.assertEqual(summary["taken"], ["up"])
        self.assertEqual(summary["kept"], ["local", "mine"])
        self.assertEqual(summary["added"], ["new"])
        self.assertEqual(summary["removed"], ["gone"])
        self.assertEqual([c["path"] for c in summary["conflicts"]], ["gone-edited"])
        self.assertEqual(files["up"], b"2\n")
        self.assertNotIn("gone", files)

    def test_a_starter_file_removed_upstream_is_reported_and_never_deleted(self):
        summary, files = self.merge({"a": b"1\n", "b": b"1\n"}, {"a": b"1\n", "b": b"2\n"}, {}, "starter")
        self.assertEqual(summary["reported"], ["a", "b"])
        self.assertEqual(files, {"a": b"1\n", "b": b"2\n"})

    def test_binary_and_both_added_files_keep_the_local_copy(self):
        summary, files = self.merge({"bin": b"\xff1"}, {"bin": b"\xff2", "both": b"a\n"},
                                    {"bin": b"\xff3", "both": b"b\n"})
        self.assertEqual(len(summary["conflicts"]), 2)
        self.assertEqual(files, {"bin": b"\xff2", "both": b"a\n"})

    def test_protected_parts_of_skill_md_are_restored(self):
        before = "---\nname: a-slides\ndescription: Old.\n---\n\n# A\n\n## Local rules\n\n- Mine.\n"
        merged = "---\nname: b-slides\ndescription: New.\n---\n\n# A, new\n\n## Local rules\n\n- Theirs.\n"
        restored = merge.restore(merged, merge.protected(before))
        self.assertEqual(restored, "---\nname: a-slides\ndescription: Old.\n---\n\n# A, new\n\n## Local rules\n\n- Mine.\n")


if __name__ == "__main__":
    unittest.main()
