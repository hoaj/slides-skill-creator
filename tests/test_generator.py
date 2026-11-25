"""The Generator's tools: packs, extraction, fonts, icons, guard data, skills and calibration."""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import ACME, ENGINE, REPO

TOOLS = REPO / "skills" / "slides-skill-creator" / "tools"
MATERIAL = REPO / "examples" / "brand-material"
sys.path.insert(0, str(TOOLS))

from genlib import calibrate, extract, fonts, guard, icons, pack, skill  # noqa: E402
from genlib.common import GenError  # noqa: E402

import render  # noqa: E402  (on the path through genlib.common)

DESCRIPTION = 'Builds on-brand slide decks for Acme ("Acme Corp"). Not for other brands.'


def has(module):
    try:
        __import__(module)
        return True
    except ImportError:
        return False


class Temp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def copy(self, src, name=None):
        target = self.tmp / (name or src.name)
        shutil.copytree(src, target)
        return target

    def manifest(self, folder):
        return json.loads((folder / "brand.json").read_text(encoding="utf-8"))

    def edit(self, folder, change):
        data = self.manifest(folder)
        change(data)
        (folder / "brand.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    def gen(self, *args):
        done = subprocess.run([sys.executable, str(TOOLS / "gen.py"), *map(str, args)],
                              capture_output=True, text=True)
        return done.returncode, json.loads(done.stdout)


class PackTests(Temp):
    def test_init_renames_the_plain_pack(self):
        out = self.tmp / "packs" / "orbit"
        result = pack.init(out, "orbit", "Orbit", ["orbit labs"])
        tokens = (out / "tokens.css").read_text(encoding="utf-8")
        self.assertIn("--orbit-paper", tokens)
        self.assertNotIn("--plain-", tokens)
        m = self.manifest(out)
        self.assertEqual((m["slug"], m["name"], m["aliases"]), ("orbit", "Orbit", ["orbit labs"]))
        self.assertIn("brand.md", " ".join(result["todo"]))
        # brand.md is the agent's to write, so the skeleton is not yet valid.
        check = pack.check(out)
        self.assertFalse(check["valid"])
        self.assertTrue(any("brand.md" in e for e in check["errors"]))

    def test_init_refuses(self):
        with self.assertRaisesRegex(GenError, "hidden test pack"):
            pack.init(self.tmp / "plain", "plain", "Plain", [])
        with self.assertRaisesRegex(GenError, "named after its slug"):
            pack.init(self.tmp / "other", "orbit", "Orbit", [])
        (self.tmp / "orbit").mkdir()
        (self.tmp / "orbit" / "x.txt").write_text("x")
        with self.assertRaisesRegex(GenError, "not empty"):
            pack.init(self.tmp / "orbit", "orbit", "Orbit", [])

    def test_check_the_example_pack(self):
        code, result = self.gen("pack-check", "--pack", ACME)
        self.assertEqual(code, 0)
        self.assertTrue(result["valid"])


class ExtractTests(Temp):
    def test_the_acme_template(self):
        facts = extract.facts(MATERIAL / "acme" / "acme-template.pptx", self.tmp / "out")
        theme = facts["masters"][0]["theme"]
        self.assertEqual(theme["colours"]["accent1"]["value"], "#2447D8")
        self.assertEqual(theme["colours"]["dk1"]["source"], "ppt/theme/theme1.xml clrScheme dk1")
        self.assertEqual(theme["fonts"]["headings"]["value"], "Public Sans")
        self.assertEqual(facts["slideSize"]["aspect"], "1.778")
        self.assertTrue(facts["masters"][0]["layouts"])
        image = facts["images"][0]
        self.assertFalse(image["svg"])
        self.assertTrue((self.tmp / "out" / image["file"]).is_file())
        self.assertTrue((self.tmp / "out" / "pptx-facts.json").is_file())

    def test_refuses_other_files(self):
        other = self.tmp / "notes.pptx"
        other.write_text("not a zip")
        with self.assertRaisesRegex(GenError, "not a valid PowerPoint"):
            extract.facts(other, self.tmp / "out")


class GuardTests(Temp):
    def strip(self, folder):
        self.edit(folder, lambda m: m.pop("guard"))

    def test_regenerates_the_acme_guard(self):
        expected = self.manifest(ACME)["guard"]
        folder = self.copy(ACME)
        self.strip(folder)
        # Dawn's --bg is its solid base, so nothing needs to be asked.
        result = guard.build(folder)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["guard"], expected)
        self.assertEqual(result["contrast"]["cobalt"]["muted"], 4.07)

    def test_a_gradient_background_needs_its_base(self):
        folder = self.copy(ACME)
        self.strip(folder)
        tokens = folder / "tokens.css"
        tokens.write_text(tokens.read_text(encoding="utf-8").replace(
            "--bg: var(--acme-dusk);", "--bg: linear-gradient(#2A1458, #2447D8);"), encoding="utf-8")
        with self.assertRaises(GenError) as caught:
            guard.build(folder)
        self.assertEqual([n["theme"] for n in caught.exception.details["needs"]], ["dawn"])
        result = guard.build(folder, bases=["dawn=dusk"])
        self.assertEqual(result["guard"]["themeBg"]["dawn"], "dusk")
        # A later run keeps the base it was given.
        self.assertEqual(guard.build(folder)["guard"]["themeBg"]["dawn"], "dusk")

    def test_overrides_and_kept_choices(self):
        folder = self.copy(ACME)
        result = guard.build(folder, neutral=["teal"])
        self.assertIn("teal", result["guard"]["neutrals"])
        self.assertIn("teal", guard.build(folder)["guard"]["neutrals"])
        with self.assertRaisesRegex(GenError, "not palette colours"):
            guard.build(folder, vivid=["mauve"])


class IconTests(Temp):
    def test_builds_the_library_and_guide(self):
        folder = self.copy(ENGINE / "fixtures" / "plain", "orbit")
        self.edit(folder, lambda m: m.update(slug="orbit", name="Orbit"))
        src = self.tmp / "svgs"
        src.mkdir()
        (src / "Line_Chart.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            'stroke="#14213D" stroke-width="2"><path d="M3 3v18h18"/></svg>')
        (src / "dot.svg").write_text(
            '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#FF0000"/></svg>')
        result = icons.build(folder, src)
        self.assertEqual(result["names"], ["dot", "line-chart"])
        text = (folder / "icon-library.js").read_text(encoding="utf-8")
        library = json.loads(text[text.index("{"):text.rindex("}") + 1])
        self.assertEqual(library["line-chart"]["inner"],
                         '<g fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/></g>')
        self.assertIn('fill="currentColor"', library["dot"]["inner"])
        self.assertIn("Available: dot, line-chart.", (folder / "icons.md").read_text(encoding="utf-8"))
        self.assertTrue(pack.check(folder)["valid"])

        (src / "extra.svg").write_text('<svg viewBox="0 0 1 1"><rect width="1" height="1"/></svg>')
        icons.build(folder, src)
        self.assertIn("Available: dot, extra, line-chart.", (folder / "icons.md").read_text(encoding="utf-8"))

    def test_refuses_scripts_and_links(self):
        folder = self.copy(ENGINE / "fixtures" / "plain")
        src = self.tmp / "svgs"
        src.mkdir()
        (src / "bad.svg").write_text('<svg viewBox="0 0 1 1"><script>alert(1)</script></svg>')
        with self.assertRaisesRegex(GenError, "plain shapes"):
            icons.build(folder, src)
        (src / "bad.svg").write_text('<svg viewBox="0 0 1 1"><image href="https://x.test/a.png"/></svg>')
        with self.assertRaisesRegex(GenError, "plain shapes"):
            icons.build(folder, src)


@unittest.skipUnless(has("fontTools") and has("brotli"), "needs fonttools and brotli")
class FontTests(Temp):
    def test_sets_and_replaces_the_font_set(self):
        folder = self.copy(ENGINE / "fixtures" / "plain")
        ttfs = sorted((MATERIAL / "acme" / "fonts").glob("*.ttf"))
        result = fonts.build(folder, ttfs, display="Public Sans")
        self.assertEqual([(f["weight"], f["style"]) for f in result["fonts"]], [(400, "normal"), (700, "normal")])
        self.assertTrue((folder / "fonts" / "PublicSans-Bold.woff2").is_file())
        tokens = (folder / "tokens.css").read_text(encoding="utf-8")
        self.assertIn('--font-display: "Public Sans", Arial, Helvetica, sans-serif;', tokens)
        self.assertIn("--font-body: Arial, Helvetica, sans-serif;", tokens)
        self.assertTrue(pack.check(folder)["valid"])

        # Running again with one face replaces the set and deletes only the old listed file.
        result = fonts.build(folder, [ACME / "fonts" / "PublicSans-Regular.woff2"])
        self.assertEqual(result["removed"], ["fonts/PublicSans-Bold.woff2"])
        self.assertEqual(sorted(p.name for p in (folder / "fonts").iterdir()), ["PublicSans-Regular.woff2"])
        self.assertIn('url("fonts/PublicSans-Regular.woff2")', (folder / "fonts.css").read_text(encoding="utf-8"))

    def test_refuses_unknown_family_and_duplicates(self):
        folder = self.copy(ENGINE / "fixtures" / "plain")
        regular = ACME / "fonts" / "PublicSans-Regular.woff2"
        with self.assertRaisesRegex(GenError, "not one of the fonts' families"):
            fonts.build(folder, [regular], body="Other Sans")
        with self.assertRaisesRegex(GenError, "give each face once"):
            fonts.build(folder, [regular, MATERIAL / "acme" / "fonts" / "PublicSans-Regular.ttf"])


class SkillTests(Temp):
    def new(self, folder="acme-slides"):
        return skill.new_dir(self.tmp / folder, "acme-slides", DESCRIPTION, "acme-example/acme-slides",
                             "Acme Maintainers", ACME)

    def assert_starter_matches_lock(self, root, skill_dir):
        values = json.loads((skill_dir / "engine.lock").read_text(encoding="utf-8"))["starterValues"]
        for path, text in render.render_files(values).items():
            self.assertEqual((root / path).read_text(encoding="utf-8"), text, path)

    def test_new_dir(self):
        (self.tmp / "acme-slides" / ".git").mkdir(parents=True)
        result = self.new()
        skill_dir = pathlib.Path(result["skillDir"])
        self.assertEqual(skill_dir, self.tmp / "acme-slides" / "skills" / "acme-slides")
        self.assertTrue((skill_dir / "brands" / "acme" / "brand.json").is_file())
        self.assertTrue((self.tmp / "acme-slides" / ".claude-plugin" / "marketplace.json").is_file())
        self.assertIn("deck.py check", result["next"][0])
        self.assert_starter_matches_lock(self.tmp / "acme-slides", skill_dir)
        done = subprocess.run([sys.executable, str(skill_dir / "engine" / "deck.py"), "check"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_new_dir_refuses_a_folder_with_files(self):
        (self.tmp / "acme-slides").mkdir()
        (self.tmp / "acme-slides" / "README.md").write_text("x")
        with self.assertRaisesRegex(GenError, "must be empty"):
            self.new()

    def test_new_refuses_an_invalid_pack_and_writes_nothing(self):
        broken = self.copy(ACME)
        (broken / "brand.md").unlink()
        with self.assertRaises(GenError) as caught:
            skill.new_dir(self.tmp / "out", "acme-slides", DESCRIPTION, "a/b", "A", broken)
        self.assertTrue(any("brand.md" in e for e in caught.exception.details["errors"]))
        self.assertFalse((self.tmp / "out").exists())

    def test_cli_reports_errors_as_json(self):
        code, result = self.gen("new", "--skill", "acme-slides", "--description", "d", "--repo", "a/b",
                                "--author", "A", "--brand", ACME)
        self.assertEqual(code, 1)
        self.assertIn("exactly one of --dir", result["error"]["message"])

    def test_new_into_a_shared_repo(self):
        root = self.tmp / "plugins"
        (root / ".claude-plugin").mkdir(parents=True)
        other = {"name": "other", "source": "./plugins/other", "description": "x"}
        (root / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps({"name": "shared", "owner": {"name": "o"}, "plugins": [other]}))
        result = skill.new_into(root, "acme-slides", DESCRIPTION, "acme-example/plugins", "Acme", ACME)
        self.assertEqual(result["marketplaces"], [".claude-plugin/marketplace.json"])
        market = json.loads((root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(market["plugins"], [other, {"name": "acme-slides", "source": "./plugins/acme-slides",
                                                    "description": DESCRIPTION}])
        self.assertTrue((root / "plugins" / "acme-slides" / "skills" / "acme-slides" / "engine.lock").is_file())
        self.assertTrue((root / ".github" / "workflows" / "acme-slides-ci.yml").is_file())
        with self.assertRaisesRegex(GenError, "already lists acme-slides"):
            skill.new_into(root, "acme-slides", DESCRIPTION, "acme-example/plugins", "Acme", ACME)

    def test_new_into_needs_a_marketplace(self):
        with self.assertRaisesRegex(GenError, "no marketplace file"):
            skill.new_into(self.tmp, "acme-slides", DESCRIPTION, "a/b", "A", ACME)

    def test_add_brand_describe_and_bump(self):
        root = self.tmp / "acme-slides"
        skill_dir = pathlib.Path(self.new()["skillDir"])
        second = self.copy(ENGINE / "fixtures" / "plain", "orbit")
        self.edit(second, lambda m: m.update(slug="orbit", name="Orbit"))

        result = skill.add_brand(skill_dir, second)
        self.assertEqual(result["brands"], ["acme", "orbit"])
        self.assertEqual(result["description"], DESCRIPTION)
        with self.assertRaisesRegex(GenError, "already has a Brand pack"):
            skill.add_brand(skill_dir, second)
        with self.assertRaisesRegex(GenError, "hidden test pack"):
            skill.add_brand(skill_dir, ENGINE / "fixtures" / "plain")

        new = 'Builds decks for Acme ("Acme Corp") and Orbit. Not for other brands.'
        result = skill.describe(skill_dir, new)
        self.assertEqual(result["unchanged"], [])
        self.assertEqual(len(result["changed"]), 8)
        self.assertIn(json.dumps(new), (skill_dir / "SKILL.md").read_text(encoding="utf-8"))
        market = json.loads((root / ".github" / "plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(market["plugins"][0]["description"], new)

        self.assertEqual(skill.bump(skill_dir, "minor")["to"], "0.2.0")
        for manifest in skill.MANIFESTS:
            self.assertEqual(json.loads((root / manifest).read_text(encoding="utf-8"))["version"], "0.2.0")
        # Upgrade renders the Starter files from engine.lock, so they must still match.
        self.assert_starter_matches_lock(root, skill_dir)

    def test_describe_in_a_shared_repo(self):
        root = self.tmp / "plugins"
        (root / ".cursor-plugin").mkdir(parents=True)
        (root / ".cursor-plugin" / "marketplace.json").write_text(json.dumps({"name": "shared", "plugins": []}))
        skill_dir = pathlib.Path(skill.new_into(root, "acme-slides", DESCRIPTION, "a/plugins", "A", ACME)["skillDir"])
        skill.describe(skill_dir, "A new description.")
        market = json.loads((root / ".cursor-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(market["plugins"][0]["description"], "A new description.")
        self.assert_starter_matches_lock(root, skill_dir)


class CalibrateTests(Temp):
    def test_probe_template(self):
        text = calibrate.template("paper")
        self.assertEqual(text.count('class="probe"'), len(calibrate.probes()))
        self.assertEqual(len(calibrate.probes()), 56)
        self.assertEqual(text.count('class="slide-content"'), 7)
        texts = [p[0] for p in calibrate.probes()]
        self.assertEqual(len(set(texts)), len(texts))

    def test_fit_recovers_known_coefficients(self):
        base, true = [0.4, 0.3, 0.5], [0.45, 0.43, -0.1]
        data = []
        for size in (20, 34, 60, 112):
            for lead in (1.0, 1.3, 1.5):
                nf, lh = 1.2 * size, lead * size
                # The baseline error that remains when the export used `base` instead of the true
                # lead: the shift it applied minus the shift it needed.
                error = (base[0] - true[0]) * nf - (base[1] - true[1]) * lh - (base[2] - true[2])
                data.append((nf, lh, error))
        lead, stats = calibrate.fit_rows(data, base)
        for got, want in zip(lead, true):
            self.assertAlmostEqual(got, want, places=3)
        self.assertLess(stats["maxPx"], 1e-6)

    def test_needs_font_files(self):
        root = self.tmp / "acme-slides"
        skill.new_dir(root, "acme-slides", DESCRIPTION, "a/b", "A", ACME)
        skill_dir = root / "skills" / "acme-slides"
        plain = self.copy(ENGINE / "fixtures" / "plain", "orbit")
        self.edit(plain, lambda m: m.update(slug="orbit", name="Orbit"))
        skill.add_brand(skill_dir, plain)
        with self.assertRaisesRegex(GenError, "nothing to calibrate"):
            calibrate.prepare(skill_dir, "orbit", self.tmp / "cal")
        with self.assertRaisesRegex(GenError, "outside the skill"):
            calibrate.prepare(skill_dir, "acme", skill_dir / "cal")


if __name__ == "__main__":
    unittest.main()
