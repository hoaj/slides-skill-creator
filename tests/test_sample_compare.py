"""The Sample deck and `deck.py compare`, in real Chrome. Skipped without the optional tools."""
import json
import re
import shutil
import sys
import tempfile
import unittest
import pathlib

from tests.helpers import ENGINE, Workspace

sys.path.insert(0, str(ENGINE))

try:
    from playwright.sync_api import sync_playwright
    HAS_BROWSER_TOOLS = True
except ImportError:
    HAS_BROWSER_TOOLS = False
try:
    import fitz
    import numpy as np
    from pptx import Presentation
    HAS_COMPARE_TOOLS = HAS_BROWSER_TOOLS
except ImportError:
    HAS_COMPARE_TOOLS = False

BASE_IDS = [item["id"] for item in json.loads((ENGINE / "layouts.json").read_text(encoding="utf-8"))["layouts"]]
OVERFLOW = """() => {
  deck._pdfPrep();
  const bad = [];
  deck.slides.forEach((s, i) => {
    const c = s.querySelector('.slide-content');
    if (c && (c.scrollHeight > c.clientHeight + 1 || c.scrollWidth > c.clientWidth + 1)) bad.push(i + 1);
    if (s.scrollHeight > s.clientHeight + 1) bad.push(i + 1);
  });
  deck._teardownPDF();
  return bad;
}"""


class SampleTemplateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        cls.ws.add_acme()
        for slug in ("acme", "plain"):
            result = cls.ws.stdlib("sample", "--brand", slug, str(cls.ws.project / f"{slug}.html"))
            assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def slides(self, slug):
        return re.findall(r'<section\b[^>]*\bclass="slide[^>]*>', self.ws.built(f"{slug}.html"))

    def test_every_base_layout_appears_once(self):
        for slug in ("acme", "plain"):
            found = [re.search(r'data-layout="([^"]+)"', tag).group(1)
                     for tag in self.slides(slug) if "data-layout" in tag]
            for layout in BASE_IDS:
                self.assertEqual(found.count(layout), 1, f"{slug}: {layout}")

    def test_every_theme_has_its_slide(self):
        for slug in ("acme", "plain"):
            manifest = json.loads((self.ws.skill / "brands/acme/brand.json" if slug == "acme"
                                   else self.ws.engine / "fixtures/plain/brand.json").read_text(encoding="utf-8"))
            shown = {re.search(r'data-theme="([^"]+)"', t).group(1) for t in self.slides(slug) if 'data-sample="theme"' in t}
            self.assertEqual(shown, {t["value"] for t in manifest["themes"]})

    def test_own_layouts_and_their_css(self):
        self.assertTrue(any('data-layout="scorecard"' in t for t in self.slides("acme")))
        self.assertIn(".layout-scorecard__value", self.ws.built("acme.html"))
        self.assertFalse(any('data-layout="scorecard"' in t for t in self.slides("plain")))

    def test_widgets_are_there(self):
        html = self.ws.built("plain.html")
        for marker in ('class="chart-bars', 'class="chart-donut"', 'class="counter-stat"', 'class="toggle-group',
                       "data-step", 'class="embed-frame'):
            self.assertIn(marker, html)

    def test_icon_slide_only_with_an_icon_library(self):
        self.assertTrue(any('data-sample="icons"' in t for t in self.slides("acme")))
        self.assertFalse(any('data-sample="icons"' in t for t in self.slides("plain")))

    def test_classification_labels_are_listed(self):
        for label in ("INTERNAL", "PUBLIC"):
            self.assertIn(f">{label}</span>", self.ws.built("acme.html"))
        for label in ("SECRET", "PRIVATE", "OPEN"):
            self.assertIn(f">{label}</span>", self.ws.built("plain.html"))

    def test_the_date_and_revision_are_fixed(self):
        self.assertIn('data-date="2026-01-15"', self.ws.built("plain.html"))
        self.assertIn('data-deck-rev="sample-1"', self.ws.built("plain.html"))

    def test_no_text_warnings(self):
        for slug in ("acme", "plain"):
            result = self.ws.stdlib("sample", "--brand", slug, str(self.ws.project / f"{slug}2.html"))
            self.assertEqual(result.returncode, 0)
            for kind in ("key terms:", "headline count:", "kicker:", "number format:", "markup:"):
                self.assertNotIn(kind, result.stderr)

    def test_default_output_is_in_the_working_folder(self):
        result = self.ws.stdlib("sample", "--brand", "plain")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.ws.project / "plain-sample.html").is_file())

    def test_output_never_goes_into_the_skill_folder(self):
        result = self.ws.stdlib("sample", "--brand", "plain", str(self.ws.skill / "x.html"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("skill folder", result.stderr)

    def test_template_only_writes_the_template(self):
        out = self.ws.project / "only.template.html"
        result = self.ws.stdlib("sample", "--brand", "plain", str(out), "--template-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/*__BRAND_CONFIG__*/", out.read_text(encoding="utf-8"))

    def test_unknown_brand_stops(self):
        self.assertEqual(self.ws.stdlib("sample", "--brand", "nosuch").returncode, 1)


@unittest.skipUnless(HAS_COMPARE_TOOLS, "playwright, python-pptx, pymupdf and numpy are needed")
class SampleInChromeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        cls.ws.add_acme()
        for slug in ("acme", "plain"):
            result = cls.ws.deck("sample", "--brand", slug, str(cls.ws.project / f"{slug}.html"))
            assert result.returncode == 0, result.stderr
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(channel="chrome")
        except Exception:
            try:
                cls.browser = cls.pw.chromium.launch()
            except Exception as e:
                cls.pw.stop()
                cls.ws.close()
                raise unittest.SkipTest(f"no browser: {e}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.ws.close()

    def open(self, slug):
        context = self.browser.new_context(viewport={"width": 1920, "height": 1080})
        self.addCleanup(context.close)
        page = context.new_page()
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto((self.ws.project / f"{slug}.html").as_uri())
        page.wait_for_function("() => window.deck && window.DeckContrast")
        page.evaluate("() => document.fonts.ready")
        return page, errors

    def test_renders_without_console_errors_or_overflow(self):
        for slug in ("acme", "plain"):
            with self.subTest(brand=slug):
                page, errors = self.open(slug)
                self.assertEqual(page.evaluate(OVERFLOW), [])
                for i in range(page.evaluate("() => deck.slides.length")):
                    page.evaluate("i => deck.go(i)", i)
                page.wait_for_timeout(300)
                self.assertEqual(errors, [])

    def test_acme_uses_its_own_font_and_icons(self):
        page, _ = self.open("acme")
        loaded = page.evaluate("() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.weight)")
        self.assertEqual(sorted(loaded), ["400", "700"])
        self.assertEqual(page.evaluate("() => document.querySelectorAll('[data-sample-icons] .deck-icon').length"), 24)

    def test_plain_has_no_icon_picker(self):
        page, _ = self.open("plain")
        self.assertTrue(page.evaluate("() => document.body.classList.contains('deck-no-icons')"))

    def test_pdf_has_one_page_per_slide(self):
        for slug in ("acme", "plain"):
            with self.subTest(brand=slug):
                page, _ = self.open(slug)
                count = page.evaluate("() => deck.slides.length")
                page.evaluate("() => deck._pdfPrep()")
                page.emulate_media(media="print")
                page.wait_for_timeout(200)
                pdf = page.pdf(prefer_css_page_size=True, print_background=True)
                with fitz.open(stream=pdf, filetype="pdf") as document:
                    self.assertEqual(len(document), count)

    def test_pptx_has_one_slide_per_deck_slide(self):
        for slug in ("acme", "plain"):
            with self.subTest(brand=slug):
                out = self.ws.project / f"{slug}.pptx"
                result = self.ws.deck("export-pptx", str(self.ws.project / f"{slug}.html"), str(out))
                self.assertEqual(result.returncode, 0, result.stderr)
                page, _ = self.open(slug)
                self.assertEqual(len(Presentation(str(out)).slides), page.evaluate("() => deck.slides.length"))


@unittest.skipUnless(HAS_COMPARE_TOOLS, "numpy is needed")
class ToleranceTest(unittest.TestCase):
    """The exact limits of the comparison, without a browser."""

    def setUp(self):
        from lib import compare
        self.compare = compare

    def image(self, value=100):
        return np.full((1080, 1920, 3), value, dtype=np.uint8)

    def changed(self, pixels, by):
        img = self.image()
        img[:1, :pixels, 0] = 100 + by
        return img

    def over(self, img):
        share, _ = self.compare.pixel_difference(self.image(), img)
        return self.compare.pixels_over_limit(share)

    def test_identical_images_pass(self):
        self.assertFalse(self.over(self.image()))

    def test_a_channel_difference_of_two_is_within_tolerance(self):
        self.assertFalse(self.over(self.changed(1920, 2)))

    def test_a_channel_difference_of_three_counts(self):
        self.assertTrue(self.over(self.changed(1920, 3)))

    def test_exactly_at_the_pixel_limit_passes(self):
        self.assertFalse(self.over(self.changed(207, 50)))     # 207 of 2,073,600 is under 0.01%

    def test_one_pixel_over_the_limit_fails(self):
        self.assertTrue(self.over(self.changed(208, 50)))

    def test_different_sizes_are_a_difference(self):
        share, _ = self.compare.pixel_difference(self.image(), np.zeros((10, 10, 3), dtype=np.uint8))
        self.assertTrue(self.compare.pixels_over_limit(share))

    def box(self, **change):
        box = {"text": "A", "x": 10.0, "y": 20.0, "w": 100.0, "h": 40.0}
        box.update(change)
        return box

    def test_text_box_tolerance_is_half_a_pixel(self):
        check = self.compare.text_box_differences
        for key, base in (("x", 10.0), ("y", 20.0), ("w", 100.0), ("h", 40.0)):
            self.assertEqual(check(1, [self.box()], [self.box(**{key: base + 0.5})]), [])
            self.assertEqual(len(check(1, [self.box()], [self.box(**{key: base + 0.51})])), 1)

    def test_text_box_count_and_text_are_compared(self):
        check = self.compare.text_box_differences
        self.assertEqual(check(1, [self.box()], [])[0].kind, "HTML text boxes")
        self.assertEqual(check(1, [self.box()], [self.box(text="B")])[0].kind, "HTML text")

    def pptx_box(self, text="A", size=20.0, colour=(10, 20, 30), **place):
        box = {"text": text, "left": 10.0, "top": 20.0, "width": 100.0, "height": 40.0,
               "runs": [{"text": text, "size": size, "colour": colour, "font": "X", "bold": False, "italic": False}]}
        box.update(place)
        return box

    def pptx_kinds(self, old, new):
        return [d.kind for d in self.compare.pptx_differences(1, [old], [new])]

    def test_pptx_text_is_exact(self):
        self.assertEqual(self.pptx_kinds(self.pptx_box(), self.pptx_box(text="B")), ["PowerPoint text"])

    def test_pptx_position_tolerance_is_one_point(self):
        for key, base in (("left", 10.0), ("top", 20.0), ("width", 100.0), ("height", 40.0)):
            self.assertEqual(self.pptx_kinds(self.pptx_box(), self.pptx_box(**{key: base + 1.0})), [])
            self.assertEqual(self.pptx_kinds(self.pptx_box(), self.pptx_box(**{key: base + 1.01})),
                             ["PowerPoint position"])

    def test_pptx_font_size_tolerance_is_point_six(self):
        self.assertEqual(self.pptx_kinds(self.pptx_box(), self.pptx_box(size=20.6)), [])
        self.assertEqual(self.pptx_kinds(self.pptx_box(), self.pptx_box(size=20.61)), ["PowerPoint size"])

    def test_pptx_colour_tolerance_is_eight(self):
        self.assertEqual(self.pptx_kinds(self.pptx_box(), self.pptx_box(colour=(18, 20, 30))), [])
        self.assertEqual(self.pptx_kinds(self.pptx_box(), self.pptx_box(colour=(19, 20, 30))), ["PowerPoint colour"])

    def test_pptx_font_is_exact(self):
        other = self.pptx_box()
        other["runs"][0]["font"] = "Y"
        self.assertEqual(self.pptx_kinds(self.pptx_box(), other), ["PowerPoint text style"])

    def test_a_difference_says_nothing_about_the_text(self):
        found = self.compare.pptx_differences(4, [self.pptx_box(text="Private words")],
                                              [self.pptx_box(text="Other words")])
        self.assertNotIn("words", str(found[0]))
        self.assertIn("slide 4", str(found[0]))


@unittest.skipUnless(HAS_COMPARE_TOOLS, "playwright, python-pptx, pymupdf and numpy are needed")
class CompareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        cls.ws.add_acme()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls.tmp.name).resolve()
        cls.old = cls.engine("old")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.ws.close()

    @classmethod
    def engine(cls, name, edit=None):
        target = cls.root / name / "engine"
        shutil.copytree(ENGINE, target, ignore=shutil.ignore_patterns("__pycache__"))
        if edit:
            edit(target)
        return target

    def compare(self, new, brand="plain", *flags):
        return self.ws.deck("compare", str(self.old), str(new), "--brand", brand, *flags)

    def test_identical_engines_report_no_difference(self):
        for brand in ("acme", "plain"):
            with self.subTest(brand=brand):
                result = self.compare(self.old, brand)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f"{brand}: no difference", result.stdout)

    def test_a_visual_change_is_a_difference(self):
        new = self.engine("visual", lambda e: self.ws.replace_in(
            e / "runtime" / "widgets.css", "gap:24px; height:520px", "gap:90px; height:520px"))
        out = self.root / "visual-report"
        result = self.compare(new, "plain", "--out", str(out), "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertFalse(summary["same"])
        kinds = {d["check"] for d in summary["differences"]}
        self.assertIn("HTML pixels", kinds)
        self.assertIn("PDF pixels", kinds)
        self.assertIn("PowerPoint background", kinds)
        self.assertTrue((out / "report.html").is_file())
        self.assertTrue((out / "report.json").is_file())
        names = [p.name for p in (out / "images").iterdir()]
        self.assertTrue(any(n.endswith("-before.png") for n in names))
        self.assertTrue(any(n.endswith("-after.png") for n in names))
        self.assertTrue(any(n.endswith("-diff.png") for n in names))

    def test_a_pptx_text_change_is_a_difference(self):
        new = self.engine("text", lambda e: self.ws.replace_in(
            e / "lib" / "pptx_export.py", 'r.text = rn["text"]', 'r.text = rn["text"] + "!"'))
        result = self.compare(new, "plain", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        kinds = {d["check"] for d in json.loads(result.stdout)["differences"]}
        self.assertEqual(kinds, {"PowerPoint text"})

    def test_a_new_sample_slide_is_not_a_regression(self):
        def add_slide(engine):
            self.ws.replace_in(engine / "lib" / "sample.py", 'slides.append(_fill_themes(base["closing"], hero, light))',
                               'slides.append(_theme_slide(themes[0]))\n    slides.append(_fill_themes(base["closing"], hero, light))')
        new = self.engine("newslide", add_slide)
        result = self.compare(new, "plain")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_summary_names_no_text_or_path(self):
        new = self.engine("private", lambda e: self.ws.replace_in(
            e / "lib" / "pptx_export.py", 'r.text = rn["text"]', 'r.text = "Sensitive words"'))
        out = self.root / "private-report"
        result = self.compare(new, "plain", "--out", str(out))
        self.assertEqual(result.returncode, 1)
        for leaked in ("Sensitive", str(self.root), str(out)):
            self.assertNotIn(leaked, result.stdout)
        self.assertRegex(result.stdout, r"plain: \d+ difference\(s\) across \d+ slides")
        self.assertRegex(result.stdout, r"slide \d+: PowerPoint text:")

    def test_a_missing_engine_is_a_tool_error(self):
        result = self.ws.deck("compare", str(self.root / "nowhere"), str(self.old), "--brand", "plain")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no Engine", result.stderr)

    def test_an_unknown_brand_is_a_tool_error(self):
        result = self.compare(self.old, "nosuch")
        self.assertEqual(result.returncode, 2)
        self.assertIn("nosuch", result.stderr)

    def test_an_engine_that_cannot_build_is_a_tool_error(self):
        new = self.engine("broken", lambda e: (e / "runtime" / "widgets.css").unlink())
        result = self.compare(new)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_the_report_cannot_go_into_the_skill_folder(self):
        result = self.compare(self.old, "plain", "--out", str(self.ws.skill / "report"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("skill folder", result.stderr)


if __name__ == "__main__":
    unittest.main()
