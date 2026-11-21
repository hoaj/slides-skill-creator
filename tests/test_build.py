import json
import re
import unittest

from tests.helpers import TEMPLATE, Workspace


def deep_del(manifest, dotted):
    keys = dotted.split(".")
    for key in keys[:-1]:
        manifest = manifest[key]
    del manifest[keys[-1]]


class BuildPlainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        cls.result = cls.ws.build("plain")

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def test_builds_on_the_standard_library(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)

    def test_output_is_self_contained(self):
        html = self.ws.built()
        self.assertNotRegex(html, r"/\*__[A-Z_]+__\*/")
        self.assertNotIn("<!--__LOGO__-->", html)
        self.assertNotRegex(html, r'<(?:script|link)\b[^>]*\b(?:src|href)=')
        self.assertIn('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 30"', html)

    def test_brand_config_comes_from_the_pack(self):
        cfg = self.ws.deck_brand()
        pack = json.loads((self.ws.engine / "fixtures/plain/brand.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["slug"], "plain")
        self.assertEqual(cfg["defaultTheme"], pack["defaultTheme"])
        self.assertEqual([t["value"] for t in cfg["themes"]], [t["value"] for t in pack["themes"]])
        self.assertEqual(cfg["classifications"], pack["classifications"])
        self.assertEqual(cfg["defaultClassification"], pack["defaultClassification"])
        self.assertEqual(cfg["guard"], pack["guard"])
        self.assertEqual(cfg["bloomThemes"], [])

    def test_no_retired_fields_reach_the_deck(self):
        cfg = self.ws.deck_brand()
        for field in ("storePrefix", "logoWidthPx", "fontFamily", "files"):
            self.assertNotIn(field, cfg)

    def test_storage_prefix_is_derived_from_the_slug(self):
        self.assertIn("DECK_BRAND.slug + '-deck'", self.ws.built())

    def test_no_icons_and_no_calibration_are_reported_not_fatal(self):
        self.assertIn("no pptxLead", self.result.stderr)
        self.assertIn("icon picker is hidden", self.result.stderr)
        cfg = self.ws.deck_brand()
        self.assertNotIn("pptxLead", cfg)
        self.assertNotIn("pptxNaturalLineHeight", cfg)
        self.assertNotIn("window.DeckIcons =", self.ws.built())


class PackErrorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def assert_stops(self, slug, *expected):
        result = self.ws.build(slug, out=f"{slug}.html")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        for text in expected:
            self.assertIn(text, result.stderr)
        self.assertFalse((self.ws.project / f"{slug}.html").exists())

    def test_missing_required_fields_stop_with_file_and_field(self):
        fields = ("slug", "name", "logo", "defaultTheme", "themes", "classifications",
                  "defaultClassification", "fonts", "guard", "guard.palette", "guard.neutrals",
                  "guard.vivids", "guard.lightNeutral", "guard.darkNeutral", "guard.themeBg",
                  "guard.themeText", "guard.themeBg.silver", "guard.themeText.graphite")
        for i, field in enumerate(fields):
            with self.subTest(field=field):
                slug = f"missing{i}"
                self.ws.add_pack(slug, lambda m: deep_del(m, field))
                self.assert_stops(slug, f"brands/{slug}/brand.json", f"'{field}'")

    def test_format_version_must_match_exactly(self):
        for i, value in enumerate((None, 0, 2, "1", True)):
            with self.subTest(value=value):
                slug = f"format{i}"
                self.ws.add_pack(slug, lambda m: m.update(formatVersion=value)
                                 if value is not None else m.pop("formatVersion"))
                self.assert_stops(slug, "brand.json", "'formatVersion'", "deck.py upgrade")

    def test_retired_fields_stop(self):
        for i, field in enumerate(("files", "logoWidthPx", "fontFamily", "storePrefix")):
            with self.subTest(field=field):
                slug = f"retired{i}"
                self.ws.add_pack(slug, lambda m: m.update({field: "x"}))
                self.assert_stops(slug, "brand.json", f"'{field}'")

    def test_missing_required_files_stop(self):
        for i, name in enumerate(("tokens.css", "brand.md", "assets/logo.svg")):
            with self.subTest(file=name):
                slug = f"nofile{i}"
                pack = self.ws.add_pack(slug)
                (pack / name).unlink()
                self.assert_stops(slug, f"brands/{slug}/{name}")

    def test_missing_required_token_stops(self):
        for i, token in enumerate(("--ui-accent", "--logo-w", "--font-body", "--accent")):
            with self.subTest(token=token):
                slug = f"notoken{i}"
                pack = self.ws.add_pack(slug)
                tokens = pack / "tokens.css"
                text = re.sub(re.escape(token) + r"\s*:[^;]*;", "", tokens.read_text(encoding="utf-8"))
                tokens.write_text(text, encoding="utf-8")
                self.assert_stops(slug, f"brands/{slug}/tokens.css", f"'{token}'")

    def test_token_only_in_a_comment_does_not_count(self):
        pack = self.ws.add_pack("commented")
        tokens = pack / "tokens.css"
        text = re.sub(r"--logo-w\s*:[^;]*;", "/* --logo-w: 10px; */", tokens.read_text(encoding="utf-8"))
        tokens.write_text(text, encoding="utf-8")
        self.assert_stops("commented", "'--logo-w'")

    def test_theme_without_css_stops(self):
        self.ws.add_pack("notheme", lambda m: (
            m["themes"].append({"value": "extra", "label": "Extra"}),
            m["guard"]["themeBg"].update(extra="paper"),
            m["guard"]["themeText"].update(extra="coal")))
        self.assert_stops("notheme", "tokens.css", "'extra'")

    def test_default_values_must_exist(self):
        self.ws.add_pack("baddefault", lambda m: m.update(defaultClassification="NOPE", defaultTheme="nope"))
        self.assert_stops("baddefault", "'defaultClassification'", "'defaultTheme'")

    def test_guard_names_must_be_in_the_palette(self):
        self.ws.add_pack("badguard", lambda m: m["guard"]["themeBg"].update(white="nope"))
        self.assert_stops("badguard", "guard.themeBg.white", "nope")

    def test_logo_must_stay_inside_the_pack(self):
        self.ws.add_pack("escape", lambda m: m.update(logo="../outside.svg"))
        self.assert_stops("escape", "'logo'")

    def test_slug_must_match_the_folder(self):
        pack = self.ws.add_pack("folder")
        manifest = json.loads((pack / "brand.json").read_text(encoding="utf-8"))
        manifest["slug"] = "other"
        (pack / "brand.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_stops("folder", "'slug'", "folder")

    def test_bloom_theme_needs_gradients(self):
        def bloom(m):
            m["themes"][2]["bloom"] = True
        self.ws.add_pack("nobloomcss", bloom)
        self.assert_stops("nobloomcss", "assets/gradients.css", "graphite")

    def test_invalid_json_names_the_file(self):
        pack = self.ws.add_pack("badjson")
        (pack / "brand.json").write_text("{", encoding="utf-8")
        self.assert_stops("badjson", "brands/badjson/brand.json", "JSON")


class TemplateErrorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        cls.text = TEMPLATE.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def build_with(self, text, name):
        path = self.ws.project / f"{name}.template.html"
        path.write_text(text, encoding="utf-8")
        return self.ws.build("plain", template=path, out=f"{name}.html")

    def test_missing_marker_stops(self):
        result = self.build_with(self.text.replace("/*__TOKENS__*/", ""), "nomarker")
        self.assertEqual(result.returncode, 1)
        self.assertIn("/*__TOKENS__*/", result.stderr)

    def test_missing_frame_stops(self):
        result = self.build_with(self.text.replace('class="deck-frame"', 'class="other"'), "noframe")
        self.assertEqual(result.returncode, 1)
        self.assertIn("deck-frame", result.stderr)

    def test_unknown_theme_stops(self):
        result = self.build_with(self.text.replace('data-theme="silver"', 'data-theme="nope"'), "theme")
        self.assertEqual(result.returncode, 1)
        self.assertIn('data-theme="nope"', result.stderr)

    def test_unknown_classification_stops(self):
        text = self.text.replace('data-header="Neutral header"',
                                 'data-classification="NOPE" data-header="Neutral header"')
        result = self.build_with(text, "label")
        self.assertEqual(result.returncode, 1)
        self.assertIn('data-classification="NOPE"', result.stderr)
        self.assertIn("SECRET", result.stderr)

    def test_a_marker_inside_an_inlined_file_is_left_alone(self):
        pack = self.ws.add_pack("markerish")
        with (pack / "tokens.css").open("a", encoding="utf-8") as f:
            f.write("\n/* a literal /*__CHROME__ marker name */\n")
        self.assertEqual(self.ws.build("markerish", out="markerish.html").returncode, 0)


class PackFeaturesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def test_classification_labels_and_default_come_from_the_pack(self):
        self.ws.add_pack("labels", lambda m: m.update(classifications=["ALPHA", "BETA", "none"],
                                                      defaultClassification="BETA"))
        self.assertEqual(self.ws.build("labels", out="labels.html").returncode, 0)
        cfg = self.ws.deck_brand("labels.html")
        self.assertEqual(cfg["classifications"], ["ALPHA", "BETA", "none"])
        self.assertEqual(cfg["defaultClassification"], "BETA")

    def test_optional_files_are_inlined_when_present(self):
        def bloom(m):
            m["themes"][2]["bloom"] = True
        pack = self.ws.add_pack("full", bloom)
        (pack / "fonts.css").write_text("/* fonts-css-marker */", encoding="utf-8")
        (pack / "assets" / "gradients.css").write_text("/* gradients-css-marker */", encoding="utf-8")
        (pack / "icon-library.js").write_text(
            'window.DeckIcons = {"dot": {"vb": "0 0 1 1", "inner": ""}};', encoding="utf-8")
        result = self.ws.build("full", out="full.html")
        self.assertEqual(result.returncode, 0, result.stderr)
        html = self.ws.built("full.html")
        for marker in ("fonts-css-marker", "gradients-css-marker", "window.DeckIcons ="):
            self.assertIn(marker, html)
        self.assertEqual(self.ws.deck_brand("full.html")["bloomThemes"], ["graphite"])
        self.assertNotIn("icon picker is hidden", result.stderr)

    def test_calibration_passes_through(self):
        self.ws.add_pack("lead", lambda m: m.update(pptxLead=[0.5, 0.5, 0]))
        result = self.ws.build("lead", out="lead.html")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ws.deck_brand("lead.html")["pptxLead"], [0.5, 0.5, 0])
        self.assertNotIn("no pptxLead", result.stderr)

    def test_number_format_passes_through(self):
        nf = {"thousands": ".", "decimal": ","}
        self.ws.add_pack("numbers", lambda m: m.update(numberFormat=nf))
        self.assertEqual(self.ws.build("numbers", out="numbers.html").returncode, 0)
        self.assertEqual(self.ws.deck_brand("numbers.html")["numberFormat"], nf)

    def test_pack_values_cannot_close_the_script(self):
        self.ws.add_pack("escape2", lambda m: m.update(name="</script><b>x"))
        self.assertEqual(self.ws.build("escape2", out="escape2.html").returncode, 0)
        self.assertNotIn("</script><b>x", self.ws.built("escape2.html"))
        self.assertEqual(self.ws.deck_brand("escape2.html")["name"], "</script><b>x")

    def test_text_checks_warn_without_stopping(self):
        text = TEMPLATE.read_text(encoding="utf-8").replace(
            "<body>", "<body>\n<!-- key-terms\n- Opening: the start. Avoid: Neutral\n-->", 1)
        path = self.ws.project / "terms.template.html"
        path.write_text(text, encoding="utf-8")
        result = self.ws.build("plain", template=path, out="terms.html")
        self.assertEqual(result.returncode, 0)
        self.assertIn("key terms:", result.stderr)


if __name__ == "__main__":
    unittest.main()
