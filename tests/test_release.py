"""scripts/release.py: the version rules, the release plan and the reproducible assets."""
import hashlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

from tests.helpers import REPO

sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "starter"))

import release  # noqa: E402
import render  # noqa: E402

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


class Repo:
    """A throwaway git repo with the version files and a copy of the archive's folders."""

    def __init__(self, version="0.1.0-dev"):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name).resolve()
        for folder in release.ARCHIVE_FOLDERS:
            shutil.copytree(REPO / folder, self.root / folder, ignore=IGNORE)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "test")
        self.set_version(version)
        self.commit("start")

    def close(self):
        self._tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def set_version(self, version, only=None):
        self.write("engine/VERSION", version + "\n")
        for manifest in release.MANIFESTS:
            self.write(manifest, json.dumps({"name": "x", "version": only or version}))

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


class VersionTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)

    def test_order_of_dev_candidates_and_release(self):
        ordered = ["0.1.0-dev", "0.1.0-rc.1", "0.1.0-rc.2", "0.1.0-rc.10", "0.1.0", "0.1.1-dev", "0.2.0"]
        self.assertEqual(sorted(reversed(ordered), key=release.parse), ordered)

    def test_other_version_forms_are_refused(self):
        for bad in ("0.1", "v0.1.0", "0.1.0-beta.1", "0.1.0-rc", "0.1.0+build"):
            with self.assertRaises(release.ReleaseError, msg=bad):
                release.parse(bad)

    def test_versions_must_agree(self):
        self.assertEqual(release.version(self.repo.root), "0.1.0-dev")
        self.repo.set_version("0.1.0-rc.1", only="0.1.0-rc.2")
        with self.assertRaisesRegex(release.ReleaseError, "versions differ"):
            release.version(self.repo.root)

    def test_dev_is_allowed_only_before_the_first_release(self):
        self.assertEqual(release.check_version(self.repo.root), "0.1.0-dev")
        self.repo.git("tag", "v0.1.0-rc.1")
        with self.assertRaisesRegex(release.ReleaseError, "only allowed before the first release"):
            release.check_version(self.repo.root)

    def _branch(self, path="engine/deck.py"):
        self.repo.git("checkout", "-q", "-b", "change")
        self.repo.write(path, "changed\n")

    def test_a_shipped_change_must_raise_the_version(self):
        self.repo.set_version("0.1.0-rc.1")
        self.repo.commit("rc.1")
        self._branch()
        self.repo.commit("change")
        with self.assertRaisesRegex(release.ReleaseError, "must rise above 0.1.0-rc.1"):
            release.check_version(self.repo.root, "main")
        self.repo.set_version("0.1.0-rc.2")
        self.repo.commit("bump")
        self.assertEqual(release.check_version(self.repo.root, "main"), "0.1.0-rc.2")

    def test_the_version_must_also_rise_above_the_latest_tag(self):
        self.repo.set_version("0.1.0")
        self.repo.commit("0.1.0")
        self.repo.git("tag", "v0.2.0")
        self._branch()
        self.repo.set_version("0.1.1")
        self.repo.commit("change")
        with self.assertRaisesRegex(release.ReleaseError, "must rise above 0.2.0"):
            release.check_version(self.repo.root, "main")

    def test_changes_outside_shipped_files_need_no_bump(self):
        self.repo.set_version("0.1.0")
        self.repo.commit("0.1.0")
        self._branch("tests/test_new.py")
        self.repo.commit("tests only")
        self.assertEqual(release.check_version(self.repo.root, "main"), "0.1.0")

    def test_a_dev_version_needs_no_bump(self):
        self._branch()
        self.repo.commit("change")
        self.assertEqual(release.check_version(self.repo.root, "main"), "0.1.0-dev")


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)

    def test_dev_is_never_released(self):
        self.assertFalse(release.plan(self.repo.root)["release"])

    def test_a_candidate_is_a_prerelease_with_the_previous_tag(self):
        for tag in ("v0.1.0-rc.1", "v0.0.9", "not-a-version"):
            self.repo.git("tag", tag)
        self.repo.set_version("0.1.0-rc.2")
        self.assertEqual(release.plan(self.repo.root), {
            "version": "0.1.0-rc.2", "tag": "v0.1.0-rc.2", "release": True,
            "prerelease": True, "previous": "v0.1.0-rc.1"})

    def test_a_tagged_version_is_not_released_again(self):
        self.repo.set_version("0.1.0")
        self.repo.git("tag", "v0.1.0")
        result = release.plan(self.repo.root)
        self.assertFalse(result["release"])
        self.assertFalse(result["prerelease"])
        self.assertEqual(result["previous"], "")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo("0.1.0-rc.1")
        self.addCleanup(self.repo.close)
        self.out = self.repo.root.parent / (self.repo.root.name + "-out")
        self.addCleanup(shutil.rmtree, str(self.out), True)

    def build(self, name="a"):
        names = release.build(self.repo.root, self.out / name)
        return {n: (self.out / name / n).read_bytes() for n in names}

    def test_the_same_commit_gives_the_same_bytes(self):
        first = self.build("a")
        (self.repo.root / "engine" / "lib" / "__pycache__").mkdir(exist_ok=True)
        (self.repo.root / "engine" / "lib" / "__pycache__" / "x.pyc").write_bytes(b"junk")
        self.assertEqual(sorted(first), ["SHA256SUMS", "release-manifest.json",
                                         "slides-skill-0.1.0-rc.1.tar.gz"])
        self.assertEqual(first, self.build("b"))

    def test_the_archive_holds_only_plain_files_in_its_four_folders(self):
        assets = self.build()
        with tarfile.open(fileobj=io.BytesIO(assets["slides-skill-0.1.0-rc.1.tar.gz"])) as tar:
            members = tar.getmembers()
        self.assertTrue(members)
        for m in members:
            self.assertTrue(m.isfile(), m.name)
            self.assertIn(m.name.split("/")[0], ("engine", "starter", "upgrade", "migrations"))
            self.assertEqual((m.mode, m.mtime, m.uid, m.gid, m.uname, m.gname),
                             (0o644, 0, 0, 0, "", ""))
        names = [m.name for m in members]
        for name in ("engine/deck.py", "starter/render.py", "upgrade/upgrade.py", "migrations/README.md"):
            self.assertIn(name, names)
        self.assertNotIn("engine/lib/__pycache__", "".join(m.name for m in members))

    def test_the_manifest_matches_engine_lock_and_the_files(self):
        current = release.version(REPO)
        self.repo.set_version(current)
        self.repo.commit("same Engine as this repo")
        assets = self.build()
        manifest = json.loads(assets["release-manifest.json"])
        lock = render.lock_data({"skill": "acme-slides", "description": "d",
                                 "repo": "example/acme-slides", "author": "a"})
        self.assertEqual(manifest["version"], current)
        self.assertEqual(manifest["commit"], self.repo.git("rev-parse", "HEAD").strip())
        for key in ("engineTreeHash", "starterTreeHash", "formatVersion"):
            self.assertEqual(manifest[key], lock[key], key)
        with tarfile.open(fileobj=io.BytesIO(assets[f"slides-skill-{current}.tar.gz"])) as tar:
            unpacked = {m.name: hashlib.sha256(tar.extractfile(m).read()).hexdigest()
                        for m in tar.getmembers()}
        self.assertEqual(manifest["files"], unpacked)

    def test_sha256sums_lists_the_other_two_assets(self):
        assets = self.build()
        lines = assets["SHA256SUMS"].decode("utf-8").splitlines()
        expected = [f"{hashlib.sha256(assets[n]).hexdigest()}  {n}"
                    for n in ("release-manifest.json", "slides-skill-0.1.0-rc.1.tar.gz")]
        self.assertEqual(lines, expected)

    def test_uncommitted_changes_are_refused(self):
        self.repo.write("engine/deck.py", "edited\n")
        with self.assertRaisesRegex(release.ReleaseError, "uncommitted changes"):
            self.build()

    def test_a_missing_folder_is_refused(self):
        shutil.rmtree(str(self.repo.root / "upgrade"))
        self.repo.commit("no upgrade code")
        with self.assertRaisesRegex(release.ReleaseError, "upgrade/ is missing"):
            self.build()


class RepoTest(unittest.TestCase):
    def test_this_repo_meets_the_version_rules(self):
        self.assertEqual(release.check_version(REPO), (REPO / "engine" / "VERSION").read_text().strip())


if __name__ == "__main__":
    unittest.main()
