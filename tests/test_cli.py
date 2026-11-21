import json
import os
import re
import sys
import unittest

from tests.helpers import ENGINE, TEMPLATE, Workspace

sys.path.insert(0, str(ENGINE))


class CliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def tearDown(self):
        for pack in (self.ws.skill / "brands").iterdir():
            import shutil
            shutil.rmtree(str(pack))

    def test_brands_lists_packs_and_hides_plain(self):
        self.ws.add_pack("northwind", lambda m: m.update(aliases=["north wind"]))
        result = self.ws.stdlib("brands")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("northwind: Northwind (also: north wind)", result.stdout)
        self.assertNotIn("plain", result.stdout.lower())

    def test_brands_never_lists_plain_even_from_the_brands_folder(self):
        self.ws.add_pack("plain")
        self.assertNotIn("plain:", self.ws.stdlib("brands").stdout)

    def test_brands_with_no_packs_says_so(self):
        result = self.ws.stdlib("brands")
        self.assertEqual(result.returncode, 0)
        self.assertIn("No Brand packs", result.stdout)

    def test_plain_still_builds_though_hidden(self):
        result = self.ws.build("plain")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_works_from_any_working_directory(self):
        other = self.ws.root / "elsewhere" / "deep"
        other.mkdir(parents=True)
        out = self.ws.project / "from-elsewhere.html"
        result = self.ws.stdlib("build", "--brand", "plain", str(TEMPLATE), str(out), cwd=other)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(out.is_file())

    def test_relative_paths_resolve_against_the_working_directory(self):
        (self.ws.project / "t.html").write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
        result = self.ws.stdlib("build", "--brand", "plain", "t.html", "relative.html")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.ws.project / "relative.html").is_file())

    def test_output_never_goes_into_the_skill_folder(self):
        for target in (self.ws.skill / "deck.html", self.ws.engine / "docs" / "deck.html"):
            result = self.ws.stdlib("build", "--brand", "plain", str(TEMPLATE), str(target))
            self.assertEqual(result.returncode, 1)
            self.assertIn("skill folder", result.stderr)
            self.assertFalse(target.exists())

    def test_relative_output_from_inside_the_skill_is_refused(self):
        result = self.ws.stdlib("build", "--brand", "plain", str(TEMPLATE), "deck.html", cwd=self.ws.skill)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.ws.skill / "deck.html").exists())

    def test_extract_output_never_goes_into_the_skill_folder(self):
        source = self.ws.project / "in.pptx"
        source.write_bytes(b"not read")
        code = ("import sys, types; sys.modules['pptx'] = types.ModuleType('pptx'); "
                f"sys.path.insert(0, {str(self.ws.engine)!r}); "
                "from deck import main; "
                f"sys.exit(main(['extract-pptx', {str(source)!r}, {str(self.ws.skill / 'x')!r}]))")
        import subprocess
        result = subprocess.run([sys.executable, "-I", "-S", "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("skill folder", result.stderr)

    def test_powerpoint_commands_name_the_missing_dependency(self):
        deck = self.ws.project / "x.html"
        deck.write_text("<html></html>", encoding="utf-8")
        for args, needed in ((("export-pptx", str(deck), str(self.ws.project / "x.pptx")), "playwright"),
                             (("extract-pptx", str(self.ws.project / "x.pptx")), "python-pptx")):
            result = self.ws.stdlib(*args)
            self.assertEqual(result.returncode, 1)
            self.assertIn(needed, result.stderr)
            self.assertIn("pip install", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_unknown_brand_lists_what_is_available(self):
        self.ws.add_pack("northwind")
        result = self.ws.build("nosuch")
        self.assertEqual(result.returncode, 1)
        self.assertIn("nosuch", result.stderr)
        self.assertIn("northwind", result.stderr)
        self.assertNotIn("plain", result.stderr.split("Available:")[1])

    def test_doctor_passes_with_the_standard_library(self):
        self.ws.add_pack("northwind")
        result = self.ws.stdlib("doctor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("northwind", result.stdout)
        self.assertIn("plain (hidden test pack)", result.stdout)

    def test_doctor_fails_on_a_broken_pack(self):
        self.ws.add_pack("broken", lambda m: m.pop("themes"))
        result = self.ws.stdlib("doctor")
        self.assertEqual(result.returncode, 1)
        self.assertIn("themes", result.stdout)

    def test_doctor_report_is_redacted(self):
        self.ws.add_pack("northwind")
        result = self.ws.stdlib("doctor", "--report")
        self.assertEqual(result.returncode, 0, result.stderr)
        for expected in ("Engine:", "Python:", "OS:", "Browsers:", "python-pptx", "playwright"):
            self.assertIn(expected, result.stdout)
        self.assertNotIn(os.path.expanduser("~"), result.stdout)
        self.assertNotIn(str(self.ws.root), result.stdout)
        self.assertNotIn("northwind", result.stdout)
        self.assertRegex(result.stdout, r"Brand packs: 1 plus the hidden test pack")

    def test_redact_home_replaces_the_home_directory(self):
        from lib.doctor import redact_home
        home = os.path.expanduser("~")
        self.assertEqual(redact_home(f"at {home}/project"), "at ~/project")


class StandardLibraryTest(unittest.TestCase):
    def test_engine_python_parses_as_3_8(self):
        import ast
        for path in sorted(ENGINE.rglob("*.py")):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 8))

    def test_engine_python_avoids_newer_standard_library_calls(self):
        newer = re.compile(r"\.(removeprefix|removesuffix|is_relative_to|with_stem|readlink)\(|"
                           r"BooleanOptionalAction|functools\.cache\b|zip\([^)]*strict=")
        for path in sorted(ENGINE.rglob("*.py")):
            self.assertIsNone(newer.search(path.read_text(encoding="utf-8")), path.name)

    def test_only_optional_imports_are_third_party_and_they_are_lazy(self):
        import ast
        third_party = {"pptx", "playwright", "fontTools", "brotli"}
        for path in sorted(ENGINE.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:           # module level only
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    names = [node.module]
                for name in names:
                    self.assertNotIn(name.split(".")[0], third_party, f"{path.name} imports {name}")


if __name__ == "__main__":
    unittest.main()
