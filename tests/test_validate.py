import json
import shutil
import unittest

from tests.helpers import TEMPLATE, Workspace


class ValidatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def tearDown(self):
        for pack in (self.ws.skill / "brands").iterdir():
            shutil.rmtree(str(pack))

    def assert_stops(self, slug, *expected):
        result = self.ws.check(slug)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("error:", result.stdout)
        self.assertIn("Fix:", result.stdout)
        for text in expected:
            self.assertIn(text, result.stdout)
        return result

    def assert_passes(self, slug):
        result = self.ws.check(slug)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    # --- the two shipped packs ---

    def test_plain_passes_with_its_two_warnings(self):
        result = self.assert_passes("plain")
        self.assertIn("plain: valid, 0 error(s), 2 warning(s)", result.stdout)

    def test_acme_passes(self):
        self.ws.add_acme()
        result = self.assert_passes("acme")
        self.assertIn("acme: valid, 0 error(s), 0 warning(s)", result.stdout)

    def test_check_without_a_brand_covers_every_pack(self):
        self.ws.add_acme()
        result = self.ws.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("acme: valid", result.stdout)
        self.assertIn("plain: valid", result.stdout)
        self.assertIn("Checked 2 Brand pack(s)", result.stdout)

    def test_check_without_a_brand_fails_on_any_broken_pack(self):
        self.ws.add_pack("broken", lambda m: m.pop("name"))
        result = self.ws.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("broken: not valid", result.stdout)
        self.assertIn("plain: valid", result.stdout)

    def test_unknown_brand_is_an_error(self):
        result = self.ws.check("nosuch")
        self.assertEqual(result.returncode, 1)
        self.assertIn("nosuch", result.stderr)

    # --- stops: required files and fields ---

    def test_missing_required_field_names_file_field_and_fix(self):
        for field in ("name", "aliases", "logo", "defaultTheme", "themes", "classifications",
                      "defaultClassification", "fonts", "guard"):
            with self.subTest(field=field):
                slug = f"nofield{field.lower()}"
                self.ws.add_pack(slug, lambda m: m.pop(field))
                self.assert_stops(slug, f"brands/{slug}/brand.json", f"field '{field}'")

    def test_missing_required_file_stops(self):
        for name in ("tokens.css", "brand.md", "assets/logo.svg"):
            with self.subTest(file=name):
                slug = "nofile" + name.split(".")[0].replace("/", "")
                pack = self.ws.add_pack(slug)
                (pack / name).unlink()
                self.assert_stops(slug, f"brands/{slug}/{name}")

    def test_theme_flags_must_be_booleans(self):
        for flag in ("hero", "bloom"):
            with self.subTest(flag=flag):
                self.ws.add_pack(f"flag{flag}", lambda m: m["themes"][0].update({flag: "yes"}))
                self.assert_stops(f"flag{flag}", f"field 'themes[0].{flag}'")

    def test_every_problem_is_printed_at_once(self):
        def edit(m):
            m.pop("name")
            m["pptxLead"] = "wrong"
            m["numberFormat"] = {"thousands": ".", "decimal": "."}
        self.ws.add_pack("many", edit)
        self.assert_stops("many", "field 'name'", "field 'pptxLead'", "field 'numberFormat'")

    def test_wrongly_typed_values_stop_without_a_crash(self):
        def set_field(path, value):
            def edit(m):
                target = m
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
            return edit
        cases = ((("classifications",), 5, "classifications"), (("themes",), "x", "themes"),
                 (("themes", 0, "label"), 7, "themes[0].label"), (("fonts",), 3, "fonts"),
                 (("aliases",), "x", "aliases"), (("guard", "lightNeutral"), [], "guard.lightNeutral"),
                 (("guard", "neutrals"), [[]], "guard.neutrals"), (("guard", "themeBg", "white"), {}, "guard.themeBg.white"),
                 (("contrastExceptions",), ["x"], "contrastExceptions[0]"), (("contrastExceptions",), [{}], "contrastExceptions[0].theme"),
                 (("contrastExceptions",), [{"theme": [], "pair": {}, "reason": "x"}], "contrastExceptions[0].theme"),
                 (("contrastExceptions",), "x", "contrastExceptions"), (("pptxLead",), [1, 2], "pptxLead"))
        for i, (path, value, field) in enumerate(cases):
            with self.subTest(path=path, value=value):
                self.ws.add_pack(f"typed{i}", set_field(path, value))
                self.assert_stops(f"typed{i}", f"field '{field}'")

    def test_format_version_older_and_newer_stop_with_the_command(self):
        for version in (0, 2):
            with self.subTest(version=version):
                slug = f"version{version}"
                self.ws.add_pack(slug, lambda m: m.update(formatVersion=version))
                self.assert_stops(slug, "field 'formatVersion'", "deck.py upgrade")

    def test_listed_font_file_must_exist(self):
        def edit(m):
            m["fonts"] = [{"file": "fonts/missing.woff2", "family": "X", "weight": 400}]
        pack = self.ws.add_pack("nofont", edit)
        (pack / "fonts.css").write_text("/* none */", encoding="utf-8")
        self.assert_stops("nofont", "field 'fonts[0]'", "missing.woff2")

    def test_font_list_needs_fonts_css(self):
        def edit(m):
            m["fonts"] = ["fonts/a.woff2"]
        pack = self.ws.add_pack("nofontcss", edit)
        (pack / "fonts").mkdir()
        (pack / "fonts" / "a.woff2").write_bytes(b"x")
        self.assert_stops("nofontcss", "fonts.css")

    # --- numberFormat ---

    def test_number_format_accepts_valid_values(self):
        for i, nf in enumerate(({"thousands": ".", "decimal": ","}, {"thousands": ",", "decimal": "."},
                                {"thousands": " ", "decimal": ","}, {"decimal": ","}, {"thousands": ""})):
            with self.subTest(nf=nf):
                self.ws.add_pack(f"nfok{i}", lambda m: m.update(numberFormat=nf))
                self.assert_passes(f"nfok{i}")

    def test_number_format_stops_on_invalid_values(self):
        cases = (("text", "numberFormat"), ({}, "numberFormat"),
                 ({"thousands": ".", "decimal": "."}, "numberFormat"),
                 ({"decimal": ",,"}, "numberFormat.decimal"), ({"decimal": 1}, "numberFormat.decimal"),
                 ({"thousands": 1}, "numberFormat.thousands"), ({"group": "."}, "numberFormat.group"))
        for i, (nf, field) in enumerate(cases):
            with self.subTest(nf=nf):
                self.ws.add_pack(f"nfbad{i}", lambda m: m.update(numberFormat=nf))
                self.assert_stops(f"nfbad{i}", f"field '{field}'")

    # --- stops: contrast data against tokens.css ---

    def test_palette_colour_not_in_tokens_stops(self):
        self.ws.add_pack("palette", lambda m: m["guard"]["palette"].update(steel=[1, 2, 3]))
        self.assert_stops("palette", "field 'guard.palette.steel'", "#010203")

    def test_theme_background_that_differs_from_tokens_stops(self):
        self.ws.add_pack("bgdata", lambda m: m["guard"]["themeBg"].update(white="silver"))
        self.assert_stops("bgdata", "field 'guard.themeBg.white'", "--bg")

    def test_theme_text_that_differs_from_tokens_stops(self):
        self.ws.add_pack("textdata", lambda m: m["guard"]["themeText"].update(white="steel"))
        self.assert_stops("textdata", "field 'guard.themeText.white'", "--text")

    def test_token_with_no_plain_colour_stops(self):
        pack = self.ws.add_pack("nocolour")
        self.ws.replace_in(pack / "tokens.css", "--muted: #595959;", "--muted: color-mix(in srgb, red, blue);")
        self.assert_stops("nocolour", "theme 'white'", "--muted")

    # --- stops: WCAG AA ---

    def low(self, slug, old, new):
        pack = self.ws.add_pack(slug)
        self.ws.replace_in(pack / "tokens.css", old, new)
        return pack

    def test_low_contrast_body_stops(self):
        pack = self.ws.add_pack("lowbody", lambda m: (
            m["guard"]["palette"].update(faint=[170, 170, 170]),
            m["guard"]["themeText"].update(white="faint")))
        self.ws.replace_in(pack / "tokens.css", "--plain-pale: #F2F2F2;", "--plain-pale: #F2F2F2; --faint: #AAAAAA;")
        self.ws.replace_in(pack / "tokens.css", "--surface: var(--plain-pale); --text: var(--plain-coal);",
                           "--surface: var(--plain-pale); --text: var(--faint);")
        self.assert_stops("lowbody", "theme 'white' pair 'body'", "below WCAG AA")

    def test_low_contrast_muted_stops(self):
        self.low("lowmuted", "--muted: #595959;", "--muted: #AAAAAA;")
        self.assert_stops("lowmuted", "theme 'white' pair 'muted'", "below WCAG AA")

    def test_low_contrast_on_accent_stops(self):
        self.low("lowaccent", "--on-accent: var(--plain-coal);", "--on-accent: #B0B0B0;")
        self.assert_stops("lowaccent", "theme 'graphite' pair 'on-accent'", "below WCAG AA")

    def test_named_exception_with_reason_passes(self):
        pack = self.low("excepted", "--muted: #595959;", "--muted: #AAAAAA;")
        self.ws.edit_manifest(pack, lambda m: m.update(contrastExceptions=[
            {"theme": "white", "pair": "muted", "reason": "Used only at display size."}]))
        self.assert_passes("excepted")

    def test_exception_for_another_pair_does_not_pass(self):
        pack = self.low("wrongpair", "--muted: #595959;", "--muted: #AAAAAA;")
        self.ws.edit_manifest(pack, lambda m: m.update(contrastExceptions=[
            {"theme": "white", "pair": "body", "reason": "Not this pair."}]))
        self.assert_stops("wrongpair", "pair 'muted'")

    def test_exception_needs_a_known_theme_pair_and_reason(self):
        cases = (({"theme": "nope", "pair": "muted", "reason": "x"}, ".theme"),
                 ({"theme": "white", "pair": "title", "reason": "x"}, ".pair"),
                 ({"theme": "white", "pair": "muted", "reason": " "}, ".reason"),
                 ({"theme": "white", "pair": "muted"}, ".reason"))
        for i, (item, field) in enumerate(cases):
            with self.subTest(item=item):
                self.ws.add_pack(f"badexc{i}", lambda m: m.update(contrastExceptions=[item]))
                self.assert_stops(f"badexc{i}", f"contrastExceptions[0]{field}")

    def test_unneeded_exception_warns(self):
        self.ws.add_pack("unneeded", lambda m: m.update(contrastExceptions=[
            {"theme": "white", "pair": "muted", "reason": "Not needed."}]))
        result = self.assert_passes("unneeded")
        self.assertIn("already meets", result.stdout)

    def test_transparent_theme_is_measured_on_its_base_colour(self):
        pack = self.ws.add_pack("seethrough", lambda m: m["guard"]["themeBg"].update(white="graphite"))
        self.ws.replace_in(pack / "tokens.css", "--bg: var(--plain-paper);", "--bg: transparent;")
        # Dark text on the dark base colour fails, although the transparent --bg has no colour.
        self.assert_stops("seethrough", "theme 'white' pair 'body'")

    def test_gradient_theme_is_measured_on_its_base_colour(self):
        pack = self.ws.add_pack("gradient", lambda m: m["guard"]["themeBg"].update(white="silver"))
        self.ws.replace_in(pack / "tokens.css", "--bg: var(--plain-paper);", "--bg: linear-gradient(red, blue);")
        self.assert_passes("gradient")

    def test_build_uses_the_same_validator(self):
        self.low("buildlow", "--muted: #595959;", "--muted: #AAAAAA;")
        result = self.ws.build("buildlow", out="buildlow.html")
        self.assertEqual(result.returncode, 1)
        self.assertIn("theme 'white' pair 'muted'", result.stderr)
        self.assertFalse((self.ws.project / "buildlow.html").exists())

    # --- warnings ---

    def test_missing_calibration_warns(self):
        self.assertIn("no pptxLead", self.assert_passes("plain").stdout)

    def test_missing_icon_library_warns(self):
        self.assertIn("icon picker is hidden", self.assert_passes("plain").stdout)

    def test_icon_library_without_guide_warns(self):
        pack = self.ws.add_pack("icons")
        (pack / "icon-library.js").write_text('window.DeckIcons = {};', encoding="utf-8")
        result = self.assert_passes("icons")
        self.assertIn("icons.md", result.stdout)
        self.assertNotIn("icon picker is hidden", result.stdout)

    # --- own layouts ---

    SECTION = '<section class="slide layout-band" data-title="Band"><div class="slide-content">x</div></section>'

    def layout_pack(self, slug, html=None, css=None, name="band"):
        pack = self.ws.add_pack(slug)
        self.ws.write(pack / "layouts" / f"{name}.html", self.SECTION if html is None else html)
        if css is not None:
            self.ws.write(pack / "layouts" / f"{name}.css", css)
        return pack

    def test_own_layout_passes_and_its_css_reaches_the_deck(self):
        self.layout_pack("layoutok", css=".layout-band { color: red; }\n.layout-band__part { margin: 0 }")
        self.assert_passes("layoutok")
        self.assertEqual(self.ws.build("layoutok", out="layoutok.html").returncode, 0)
        self.assertIn(".layout-band__part", self.ws.built("layoutok.html"))

    def test_own_layout_cannot_override_a_base_id(self):
        html = self.SECTION.replace("layout-band", "layout-kpi")
        self.layout_pack("override", html=html, name="kpi")
        self.assert_stops("override", "layouts/kpi.html", "cannot override")

    def test_own_layout_css_must_stay_scoped(self):
        for i, css in enumerate((".slide { color: red; }", ".layout-bandit { color: red; }",
                                 ".layout-band, .card { color: red; }",
                                 "@media print { .card { color: red; } }")):
            with self.subTest(css=css):
                self.layout_pack(f"scope{i}", css=css)
                self.assert_stops(f"scope{i}", "layouts/band.css", "selector")

    def test_own_layout_css_may_use_media(self):
        self.layout_pack("media", css="@media print { .layout-band { color: red; } }")
        self.assert_passes("media")

    def test_own_layout_css_cannot_load_or_declare_at_rules(self):
        for i, css in enumerate(('@import url("https://example.com/a.css");\n.layout-band { color: red }',
                                 ".layout-band { background: url(https://example.com/a.png) }",
                                 "@font-face { font-family: X }")):
            with self.subTest(css=css):
                self.layout_pack(f"remote{i}", css=css)
                self.assert_stops(f"remote{i}", "layouts/band.css")

    def test_own_layout_holds_no_code(self):
        cases = (self.SECTION.replace("x</div>", "<script>1</script></div>"),
                 self.SECTION.replace("<div class", '<div onclick="1" class'),
                 self.SECTION.replace("x</div>", '<a href="javascript:1">x</a></div>'))
        for i, html in enumerate(cases):
            with self.subTest(html=html):
                self.layout_pack(f"code{i}", html=html)
                self.assert_stops(f"code{i}", "no hand-written code")

    def test_own_layout_must_be_self_contained(self):
        html = self.SECTION.replace("x</div>", '<img src="https://example.com/a.png" alt=""></div>')
        self.layout_pack("remoteimg", html=html)
        self.assert_stops("remoteimg", "self-contained")

    def test_own_layout_needs_one_scoped_section_with_a_title(self):
        cases = (("<div>no section</div>", "exactly one"),
                 (self.SECTION + self.SECTION, "exactly one"),
                 (self.SECTION.replace('class="slide layout-band"', 'class="slide"'), "layout-band"),
                 (self.SECTION.replace(' data-title="Band"', ""), "data-title"),
                 (self.SECTION.replace('data-title="Band"', 'data-title="Band" data-theme="nope"'), "nope"))
        for i, (html, expected) in enumerate(cases):
            with self.subTest(html=html):
                self.layout_pack(f"form{i}", html=html)
                self.assert_stops(f"form{i}", expected)

    def test_stylesheet_without_a_layout_stops(self):
        pack = self.ws.add_pack("orphan")
        self.ws.write(pack / "layouts" / "band.css", ".layout-band { color: red }")
        self.assert_stops("orphan", "no matching .html")

    def test_other_files_in_layouts_stop(self):
        pack = self.layout_pack("strayfile")
        self.ws.write(pack / "layouts" / "notes.txt", "x")
        self.assert_stops("strayfile", "notes.txt")

    def test_layout_id_format(self):
        html = self.SECTION.replace("layout-band", "layout-Bad_Id")
        self.layout_pack("badid", html=html, name="Bad_Id")
        self.assert_stops("badid", "valid id")

    # --- font inlining ---

    def test_relative_font_urls_are_inlined(self):
        def edit(m):
            m["fonts"] = [{"file": "fonts/a.woff2", "family": "X", "weight": 400}]
        pack = self.ws.add_pack("fonturl", edit)
        (pack / "fonts").mkdir()
        (pack / "fonts" / "a.woff2").write_bytes(b"not a real font")
        (pack / "fonts.css").write_text('@font-face{font-family:X;src:url("fonts/a.woff2") format("woff2")}',
                                        encoding="utf-8")
        result = self.ws.build("fonturl", out="fonturl.html")
        self.assertEqual(result.returncode, 0, result.stderr)
        html = self.ws.built("fonturl.html")
        self.assertIn("url(data:font/woff2;base64,", html)
        self.assertNotIn('url("fonts/a.woff2")', html)

    def test_font_url_to_a_missing_file_stops(self):
        pack = self.ws.add_pack("fontgone")
        (pack / "fonts.css").write_text('@font-face{font-family:X;src:url(fonts/gone.woff2)}', encoding="utf-8")
        result = self.ws.build("fontgone", out="fontgone.html")
        self.assertEqual(result.returncode, 1)
        self.assertIn("fonts/gone.woff2", result.stderr)


class DeckTypeRecordTest(unittest.TestCase):
    TYPE = "---\nname: Review\nwhen: A review\n---\n"

    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def setUp(self):
        self.pack = self.ws.add_pack("typed")
        self.ws.write(self.pack / "playbook" / "deck-types" / "review.md", self.TYPE)
        for old in self.ws.project.glob("*.html"):
            old.unlink()

    def tearDown(self):
        shutil.rmtree(str(self.pack))

    def build(self, *flags, template=TEMPLATE, out="deck.html"):
        return self.ws.stdlib("build", "--brand", "typed", *flags, str(template), str(self.ws.project / out))

    def stage_attr(self, out="deck.html"):
        html = self.ws.built(out)
        tag = html[html.index('<main class="deck-stage"'):]
        return tag[:tag.index(">")]

    def inspect(self, out="deck.html"):
        result = self.ws.stdlib("inspect", str(self.ws.project / out), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_build_records_the_deck_type(self):
        self.assertEqual(self.build("--deck-type", "review").returncode, 0)
        self.assertIn('data-deck-type="review"', self.stage_attr())
        self.assertEqual(self.inspect()["deckType"], "review")

    def test_no_deck_type_records_nothing(self):
        self.assertEqual(self.build().returncode, 0)
        self.assertNotIn("data-deck-type", self.stage_attr())
        self.assertIsNone(self.inspect()["deckType"])

    def test_a_later_build_keeps_the_recorded_type(self):
        self.assertEqual(self.build("--deck-type", "review").returncode, 0)
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('data-deck-type="review"', self.stage_attr())

    def test_the_template_attribute_is_kept(self):
        text = TEMPLATE.read_text(encoding="utf-8").replace('id="deckStage"', 'id="deckStage" data-deck-type="review"')
        path = self.ws.project / "typed.template.html"
        path.write_text(text, encoding="utf-8")
        self.assertEqual(self.build(template=path).returncode, 0)
        self.assertEqual(self.stage_attr().count("data-deck-type"), 1)

    def test_none_clears_it(self):
        self.build("--deck-type", "review")
        self.assertEqual(self.build("--deck-type", "none").returncode, 0)
        self.assertNotIn("data-deck-type", self.stage_attr())

    def test_flag_replaces_an_earlier_type(self):
        self.ws.write(self.pack / "playbook" / "deck-types" / "other.md", self.TYPE)
        self.build("--deck-type", "review")
        self.build("--deck-type", "other")
        attr = self.stage_attr()
        self.assertIn('data-deck-type="other"', attr)
        self.assertEqual(attr.count("data-deck-type"), 1)

    def test_an_unknown_flag_stops(self):
        result = self.build("--deck-type", "nosuch")
        self.assertEqual(result.returncode, 1)
        self.assertIn("nosuch", result.stderr)
        self.assertIn("review", result.stderr)

    def test_a_removed_type_warns_on_a_later_build_and_stays(self):
        self.build("--deck-type", "review")
        (self.pack / "playbook" / "deck-types" / "review.md").unlink()
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning:", result.stderr)
        self.assertIn("'review'", result.stderr)
        self.assertIn('data-deck-type="review"', self.stage_attr())
        self.assertTrue(any("review" in w for w in self.inspect()["warnings"]))

    def test_inspect_reads_key_terms(self):
        text = TEMPLATE.read_text(encoding="utf-8").replace(
            "<body>", "<body>\n<!-- key-terms\n- Opening: the start. Avoid: Beginning\n-->", 1)
        path = self.ws.project / "terms.template.html"
        path.write_text(text, encoding="utf-8")
        self.build(template=path)
        info = self.inspect()
        self.assertEqual(info["brand"], "typed")
        self.assertEqual(info["keyTerms"], [{"term": "Opening", "avoid": ["Beginning"]}])

    def test_inspect_refuses_a_file_that_is_not_a_deck(self):
        path = self.ws.project / "other.html"
        path.write_text("<html></html>", encoding="utf-8")
        result = self.ws.stdlib("inspect", str(path))
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a deck", result.stderr)

    def test_unknown_data_layout_warns(self):
        text = TEMPLATE.read_text(encoding="utf-8").replace('data-title="Steps"', 'data-title="Steps" data-layout="nosuch"')
        path = self.ws.project / "layout.template.html"
        path.write_text(text, encoding="utf-8")
        result = self.build(template=path)
        self.assertEqual(result.returncode, 0)
        self.assertIn('data-layout="nosuch"', result.stderr)

    def test_unbalanced_div_warns(self):
        text = TEMPLATE.read_text(encoding="utf-8").replace('<p id="step-one"', '<div><p id="step-one"', 1)
        path = self.ws.project / "markup.template.html"
        path.write_text(text, encoding="utf-8")
        result = self.build(template=path)
        self.assertEqual(result.returncode, 0)
        self.assertIn("markup:", result.stderr)


if __name__ == "__main__":
    unittest.main()
