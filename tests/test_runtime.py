"""Static checks that the runtime stays free of brand values."""
import json
import re
import sys
import unittest

from tests.helpers import ENGINE

sys.path.insert(0, str(ENGINE))

RUNTIME = ENGINE / "runtime"
OWN_FILES = [p for p in sorted(RUNTIME.iterdir()) if p.name != "pptxgen.bundle.js"]
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
# Per-element layout settings, each with a neutral default.
ALLOWED_FALLBACKS = {"--cols", "--card-parts", "--h", "--bar-color", "--logo-color"}


class NoBrandValuesTest(unittest.TestCase):
    def test_css_var_fallbacks_are_only_neutral_layout_settings(self):
        for css in RUNTIME.glob("*.css"):
            text = CSS_COMMENT.sub("", css.read_text(encoding="utf-8"))
            for name in re.findall(r"var\(\s*(--[\w-]+)\s*,", text):
                self.assertIn(name, ALLOWED_FALLBACKS, f"{css.name}: fallback on {name}")

    def test_every_runtime_token_is_set_by_the_plain_pack(self):
        from lib.validate import CSS_VAR_DECLARED, required_tokens
        tokens = (ENGINE / "fixtures/plain/tokens.css").read_text(encoding="utf-8")
        declared = set(CSS_VAR_DECLARED.findall(CSS_COMMENT.sub("", tokens)))
        needed = required_tokens()
        self.assertGreater(len(needed), 20)
        self.assertEqual([t for t in needed if t not in declared], [])

    def test_controller_has_no_theme_or_classification_values(self):
        source = (RUNTIME / "deck-controller.js").read_text(encoding="utf-8")
        self.assertNotIn("<option value=", source)
        self.assertNotRegex(source, r"\|\|\s*'white'")
        self.assertNotIn("DECK_BRAND.themes ||", source)
        self.assertNotRegex(source, r"'(CONFIDENTIAL|RESTRICTED|INTERNAL|PUBLIC)'")

    def test_guard_has_no_palette_of_its_own(self):
        source = (RUNTIME / "contrast-guard.js").read_text(encoding="utf-8")
        triples = re.findall(r"\[\s*(\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})\s*\]", source)
        self.assertEqual([t for t in triples if t != ("0", "1", "2")], [])   # [0, 1, 2] is an index list
        self.assertNotRegex(source, r"B\.\w+\s*\|\|")

    def test_export_has_no_default_calibration(self):
        source = (RUNTIME / "pptx-export.js").read_text(encoding="utf-8")
        self.assertNotIn("LEAD_FS", source)
        self.assertNotRegex(source, r"pptxNaturalLineHeight\s*\|\|")

    def test_runtime_uses_neutral_names(self):
        for path in OWN_FILES:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("--mesh-amount", text, path.name)
            self.assertNotRegex(text, r"[.\"' ]y" + r"s-[a-z]", path.name)

    def test_slide_frame_and_browser_chrome_are_distinct(self):
        css = (RUNTIME / "chrome.css").read_text(encoding="utf-8")
        self.assertIn(".deck-frame {", css)
        self.assertNotIn(".deck-chrome", CSS_COMMENT.sub("", css))


class PlainPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = ENGINE / "fixtures" / "plain"
        cls.manifest = json.loads((cls.pack / "brand.json").read_text(encoding="utf-8"))
        cls.tokens = CSS_COMMENT.sub("", (cls.pack / "tokens.css").read_text(encoding="utf-8"))

    @staticmethod
    def luminance(rgb):
        def channel(c):
            c /= 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2])

    def contrast(self, a, b):
        hi, lo = sorted((self.luminance(a), self.luminance(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    def resolve(self, value):
        value = value.strip()
        ref = re.fullmatch(r"var\((--[\w-]+)\)", value)
        if ref:
            return self.resolve(re.search(re.escape(ref.group(1)) + r"\s*:\s*([^;]+);", self.tokens).group(1))
        hex_value = value.lstrip("#")
        return [int(hex_value[i:i + 2], 16) for i in (0, 2, 4)]

    def theme_value(self, theme, token):
        block = re.search(r'\[data-theme="%s"\][^{]*\{(.*?)\}' % theme, self.tokens, re.S).group(1)
        return self.resolve(re.search(re.escape(token) + r"\s*:\s*([^;]+);", block).group(1))

    def test_only_required_files(self):
        files = sorted(p.relative_to(self.pack).as_posix() for p in self.pack.rglob("*") if p.is_file())
        self.assertEqual(files, ["assets/logo.svg", "brand.json", "brand.md", "tokens.css"])

    def test_format(self):
        self.assertEqual(self.manifest["formatVersion"], 1)
        self.assertEqual(self.manifest["fonts"], [])
        self.assertFalse(any(t.get("bloom") for t in self.manifest["themes"]))
        self.assertIn(len(self.manifest["themes"]), (2, 3))

    def test_greys_only(self):
        for colour in re.findall(r"#([0-9a-fA-F]{6})\b", self.tokens):
            self.assertEqual(colour[:2], colour[2:4], colour)
            self.assertEqual(colour[2:4], colour[4:], colour)

    def test_themes_meet_wcag_aa(self):
        for theme in self.manifest["themes"]:
            value = theme["value"]
            bg = self.theme_value(value, "--bg")
            for token in ("--text", "--muted"):
                self.assertGreaterEqual(self.contrast(self.theme_value(value, token), bg), 4.5, (value, token))
            self.assertGreaterEqual(self.contrast(self.theme_value(value, "--on-accent"),
                                                  self.theme_value(value, "--accent")), 4.5, value)

    def test_guard_matches_tokens(self):
        guard = self.manifest["guard"]
        for theme in self.manifest["themes"]:
            value = theme["value"]
            self.assertEqual(guard["palette"][guard["themeBg"][value]], self.theme_value(value, "--bg"))
            self.assertEqual(guard["palette"][guard["themeText"][value]], self.theme_value(value, "--text"))


class LicenceTest(unittest.TestCase):
    def test_bundled_libraries_have_their_licences(self):
        licences = ENGINE / "licenses"
        readme = (licences / "README.md").read_text(encoding="utf-8")
        for name in ("PptxGenJS.txt", "JSZip.markdown", "pako.txt", "pako-zlib.txt", "lie.md",
                     "immediate.txt", "set-immediate-shim.txt", "babel-polyfill.txt", "core-js.txt",
                     "regenerator-runtime.txt", "tslib.txt"):
            self.assertTrue((licences / name).is_file(), name)
            self.assertIn(f"({name})", readme)

    def test_jszip_is_used_under_mit(self):
        readme = (ENGINE / "licenses" / "README.md").read_text(encoding="utf-8")
        self.assertRegex(readme, r"JSZip \| 3\.5\.0 \| \*\*MIT\*\*")


if __name__ == "__main__":
    unittest.main()
