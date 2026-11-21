"""The real thing: a built deck in Chrome. Skipped when Playwright or a browser is missing."""
import json
import unittest
import zipfile

from tests.helpers import Workspace

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
try:
    from pptx import Presentation
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False


@unittest.skipUnless(HAS_PLAYWRIGHT, "playwright is not installed")
class BrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        result = cls.ws.build("plain")
        assert result.returncode == 0, result.stderr
        cls.deck = cls.ws.project / "deck.html"
        cls.manifest = json.loads((cls.ws.engine / "fixtures/plain/brand.json").read_text(encoding="utf-8"))
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

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1920, "height": 1080},
                                                accept_downloads=True)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.goto(self.deck.as_uri())
        self.page.wait_for_function("() => window.deck && window.DeckContrast")

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def current(self):
        return self.page.evaluate("() => deck.current")

    def test_navigation_steps_and_hash(self):
        self.assertEqual(self.current(), 0)
        self.page.keyboard.press("ArrowRight")
        self.assertEqual(self.current(), 1)
        self.page.keyboard.press("ArrowRight")
        self.assertEqual(self.current(), 1)     # first build step, same slide
        self.assertTrue(self.page.evaluate("() => document.getElementById('step-one').classList.contains('step-shown')"))
        self.page.keyboard.press("ArrowRight")
        self.page.keyboard.press("ArrowRight")
        self.assertEqual(self.current(), 2)
        self.assertTrue(self.page.url.endswith("#/3"))
        self.page.keyboard.press("Home")
        self.assertEqual(self.current(), 0)
        self.page.keyboard.press("End")
        self.assertEqual(self.current(), 2)

    def test_frame_shows_pack_values(self):
        frame = self.page.evaluate("""() => ({
            classification: document.querySelector('.deck-classification').textContent,
            page: document.querySelector('.deck-pagenum').textContent,
            date: document.querySelector('.deck-date').textContent,
            header: document.querySelector('.deck-header').textContent,
            logo: !!document.querySelector('.deck-logo svg')})""")
        self.assertEqual(frame, {"classification": self.manifest["defaultClassification"], "page": "1",
                                 "date": "15 January 2026", "header": "Neutral header", "logo": True})

    def test_panel_classification_from_pack_updates_frame_and_saved_state(self):
        self.page.keyboard.press("e")
        options = self.page.evaluate("""() => Array.from(
            deck.panel.querySelector('[data-ctl="classification"]').options).map(o => o.value)""")
        self.assertEqual(options, self.manifest["classifications"])
        self.page.select_option('[data-ctl="classification"]', "OPEN")
        self.assertEqual(self.page.inner_text(".deck-classification"), "OPEN")
        saved = self.page.evaluate("() => JSON.parse(localStorage.getItem(deck.STORE_KEY))")
        self.assertEqual(saved["classification"], "OPEN")
        self.assertTrue(self.page.evaluate("() => deck.STORE_KEY").startswith("plain-deck:"))
        self.page.reload()
        self.page.wait_for_function("() => window.deck && window.DeckContrast")
        self.assertEqual(self.page.inner_text(".deck-classification"), "OPEN")
        self.page.keyboard.press("e")
        self.page.select_option('[data-ctl="classification"]', "none")
        self.assertEqual(self.page.evaluate("() => document.querySelector('.deck-classification').textContent"), "")
        self.page.evaluate("() => localStorage.clear()")

    def test_unknown_saved_classification_falls_back_to_the_pack_default(self):
        self.page.evaluate("""() => { const d = JSON.parse(JSON.stringify({rev:'r1', classification:'NOT-A-LABEL',
            header:'', date:null, themes:{}, bloom:{}, html:{}})); localStorage.setItem(deck.STORE_KEY, JSON.stringify(d)); }""")
        self.page.reload()
        self.page.wait_for_function("() => window.deck && window.DeckContrast")
        self.assertEqual(self.page.inner_text(".deck-classification"), self.manifest["defaultClassification"])
        self.page.evaluate("() => localStorage.clear()")

    def test_edit_mode_persists_text(self):
        self.page.keyboard.press("e")
        self.assertEqual(self.page.get_attribute("#headline", "contenteditable"), "true")
        self.page.click("#headline")
        self.page.keyboard.press("End")
        self.page.keyboard.type(" edited")
        self.assertIn("edited", self.page.inner_text("#headline"))
        self.page.keyboard.press("Escape")
        self.page.reload()
        self.page.wait_for_function("() => window.deck && window.DeckContrast")
        self.assertIn("edited", self.page.inner_text("#headline"))
        self.page.evaluate("() => localStorage.clear()")

    def test_theme_picker_lists_pack_themes_and_guard_runs(self):
        self.page.keyboard.press("e")
        options = self.page.evaluate("() => Array.from(deck.themeSelect.options).map(o => o.value)")
        self.assertEqual(options, [t["value"] for t in self.manifest["themes"]])
        self.page.select_option('[data-ctl="theme"]', "graphite")
        self.assertEqual(self.page.evaluate("() => deck.slides[0].dataset.theme"), "graphite")
        ratio = self.page.evaluate("""() => {
            const el = document.getElementById('headline'), slide = deck.slides[0];
            const rgb = s => s.match(/[\\d.]+/g).slice(0, 3).map(Number);
            return DeckContrast.contrast(rgb(getComputedStyle(el).color), rgb(getComputedStyle(slide).backgroundColor)); }""")
        self.assertGreaterEqual(ratio, 4.5)
        self.page.evaluate("() => localStorage.clear()")

    def test_bloom_control_stays_hidden_without_bloom_themes(self):
        self.page.keyboard.press("e")
        self.assertFalse(self.page.is_visible("[data-bloom-row]"))

    def test_icon_picker_is_hidden_without_an_icon_library(self):
        self.page.keyboard.press("End")
        self.page.keyboard.press("e")
        self.assertTrue(self.page.evaluate("() => document.body.classList.contains('deck-no-icons')"))
        self.page.click("#icon")
        self.assertEqual(self.page.locator(".deck-icon-picker").count(), 0)
        self.assertTrue(self.page.evaluate("() => deck.editing"))

    def test_overview_and_save_serialisation(self):
        self.page.keyboard.press("o")
        self.assertEqual(self.page.locator(".deck-overview.open .ov-thumb").count(), 3)
        self.page.keyboard.press("Escape")
        saved = self.page.evaluate("() => deck._serialize()")
        self.assertIn('class="deck-frame"', saved)
        self.assertNotIn("deck-toolbar", saved.split("<script>")[0].split("</style>")[-1])

    def test_pdf_has_one_page_per_slide(self):
        self.page.evaluate("() => deck._pdfPrep()")
        self.page.emulate_media(media="print")
        self.page.wait_for_timeout(200)
        pdf = self.page.pdf(prefer_css_page_size=True, print_background=True)
        path = self.ws.project / "print.pdf"
        path.write_bytes(pdf)
        try:
            import fitz
        except ImportError:
            import re
            self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", pdf)), 3)
            return
        document = fitz.open(str(path))
        self.assertEqual(len(document), 3)
        self.assertAlmostEqual(document[0].rect.width / document[0].rect.height, 16 / 9, places=2)
        self.assertIn("Neutral opening", document[0].get_text())

    def test_toolbar_pptx_export_downloads_a_deck(self):
        self.page.mouse.move(600, 600)
        with self.page.expect_download(timeout=60000) as info:
            self.page.click('[data-act="pptx"]')
        path = self.ws.project / "toolbar.pptx"
        info.value.save_as(str(path))
        with zipfile.ZipFile(str(path)) as z:
            slides = [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
        self.assertEqual(len(slides), 3)
        self.page.wait_for_function("() => document.querySelector('.deck-hint').textContent.includes('no line-spacing')")


@unittest.skipUnless(HAS_PLAYWRIGHT and HAS_PPTX, "playwright and python-pptx are needed")
class ExportCommandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = Workspace()
        assert cls.ws.build("plain").returncode == 0
        cls.out = cls.ws.project / "out" / "deck.pptx"
        cls.result = cls.ws.deck("export-pptx", str(cls.ws.project / "deck.html"), str(cls.out))

    @classmethod
    def tearDownClass(cls):
        cls.ws.close()

    def test_export_has_right_slide_count_and_live_text(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        prs = Presentation(str(self.out))
        self.assertEqual(len(prs.slides), 3)
        texts = [" ".join(s.text_frame.text for s in slide.shapes if s.has_text_frame) for slide in prs.slides]
        self.assertIn("Neutral opening", texts[0])
        self.assertIn("Second point", texts[1])
        for slide in prs.slides:
            self.assertTrue(any(s.shape_type == 13 for s in slide.shapes))   # background picture

    def test_export_warns_without_calibration(self):
        self.assertIn("no vertical correction", self.result.stderr)

    def test_extract_reads_the_export_back(self):
        out_dir = self.ws.project / "extracted"
        result = self.ws.deck("extract-pptx", str(self.out), str(out_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((out_dir / "extracted-slides.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data), 3)
        self.assertIn("Neutral opening", " ".join(data[0]["content"]))


if __name__ == "__main__":
    unittest.main()
