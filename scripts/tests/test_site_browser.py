"""Exercise the built static page locally with an installed browser."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright, expect


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "site" / "dist" / "index.html"
CHANNEL = "msedge"
SCREENSHOTS = None


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class SiteBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not INDEX.is_file():
            raise RuntimeError("Build site/dist/index.html before running browser tests.")
        cls.temporary = tempfile.TemporaryDirectory(prefix="halostrix-browser-")
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name) / "halostrixlab"
        directory.mkdir()
        shutil.copy2(INDEX, directory / "index.html")
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(QuietHandler, directory=cls.temporary.name),
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()
        cls.addClassCleanup(cls.close_server)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/halostrixlab/"
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(channel=CHANNEL, headless=True)
        cls.addClassCleanup(cls.browser.close)

    @classmethod
    def close_server(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def setUp(self):
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 1000},
            color_scheme="light", reduced_motion="reduce",
        )
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.errors = []
        self.external_requests = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

        def guard(route):
            url = route.request.url
            if url.startswith(self.url) or url.startswith(("file:", "blob:", "data:")):
                route.continue_()
            else:
                self.external_requests.append(url)
                route.abort()

        self.context.route("**/*", guard)

    def tearDown(self):
        self.assertEqual(self.errors, [], "Browser JavaScript errors")
        self.assertEqual(self.external_requests, [], "Unexpected network request")

    def visit(self, suffix=""):
        response = self.page.goto(self.url + suffix, wait_until="networkidle")
        self.assertEqual(response.status, 200)
        expect(self.page.locator("body")).to_have_class(re.compile(r"\bready\b"))

    def data(self):
        return self.page.locator("#site-data").evaluate("node => JSON.parse(node.textContent)")

    def assert_no_overflow(self):
        self.assertFalse(self.page.evaluate(
            "document.documentElement.scrollWidth > window.innerWidth"
        ))

    def test_overview_contains_every_public_markdown_guide(self):
        self.visit()
        data = self.data()
        expected = {"README.md", "README.en.md", "site/README.md", "scripts/README.md"}
        expected.update(path.relative_to(ROOT).as_posix() for path in (ROOT / "docs").rglob("*.md"))
        expected.update(path.relative_to(ROOT).as_posix() for path in (ROOT / "workspaces").glob("*/README*.md"))
        actual = {item["path"] for item in data["documents"] if item["kind"] == "document"}
        self.assertEqual(actual, expected)
        expect(self.page.locator("#document-list > a")).to_have_count(len(expected))
        expect(self.page.locator("html")).to_have_attribute("lang", "es")
        self.assert_no_overflow()

    def test_language_theme_and_model_keyboard_controls(self):
        self.visit()
        self.page.locator("#language-toggle").click()
        expect(self.page.locator("html")).to_have_attribute("lang", "en")
        self.assertIn("lang=en", self.page.url)
        self.page.locator("#theme-toggle").click()
        expect(self.page.locator("html")).to_have_attribute("data-theme", "dark")
        self.assertIn("scoutTheme=dark", self.page.url)
        self.page.locator("#tab-coder").focus()
        self.page.keyboard.press("ArrowRight")
        expect(self.page.locator("#tab-thinking")).to_have_attribute("aria-selected", "true")
        expect(self.page.locator("#model-context")).to_have_text("98304")
        expect(self.page.locator("#model-slots")).to_have_text("1")
        model = next(item for item in self.data()["profile"]["lemonade"]["models"] if item["role"] == "thinking")
        expect(self.page.locator("#model-args")).to_have_text(model["load_request_reference"]["llamacpp_args"])
        self.page.keyboard.press("Home")
        expect(self.page.locator("#model-context")).to_have_text("196608")
        expect(self.page.locator("#model-slots")).to_have_text("3")

    def test_library_filters_search_and_no_results_reset(self):
        self.visit("?lang=en")
        data = self.data()
        references = [
            item for item in data["documents"]
            if item["kind"] == "document"
            and item["lang"] == "en"
            and item["category"] == "reference"
        ]
        self.page.locator("#doc-language").select_option("en")
        self.page.locator("#doc-category").select_option("reference")
        self.assertEqual(
            set(self.page.locator("#document-list .doc-path").all_inner_texts()),
            {item["path"] for item in references},
        )
        self.page.locator("#doc-search").fill("Vulkan")
        self.assertEqual(
            set(self.page.locator("#document-list .doc-path").all_inner_texts()),
            {
                item["path"] for item in references
                if "vulkan" in "\n".join(
                    (item["title"], item["path"], item["markdown"])
                ).casefold()
            },
        )
        self.page.locator("#doc-search").fill("<img src=x onerror=alert(1)>")
        expect(self.page.locator("#library-empty")).to_be_visible()
        self.assertEqual(self.page.locator("#document-list img").count(), 0)
        self.page.locator("#reset-filters").click()
        expect(self.page.locator("#document-list > a")).to_have_count(data["metadata"]["documentCount"])
        self.page.locator("#include-sources").check()
        expect(self.page.locator("#document-list > a")).to_have_count(len(data["documents"]))

    def test_full_reader_and_browser_back_forward(self):
        self.visit("?lang=en")
        opener = self.page.locator('a[data-doc-link="reference"]').first
        opener.click()
        expect(self.page.locator("#document-reader")).to_be_visible()
        expect(self.page.locator("#reader-path")).to_have_text("docs/en/configuration-reference.md")
        self.assertGreater(self.page.locator("#reader-content table").count(), 2)
        self.assertIn("196608", self.page.locator("#reader-content").inner_text())
        self.page.locator("#close-reader").click()
        expect(self.page.locator("#document-reader")).not_to_be_visible()
        expect(opener).to_be_focused()
        self.page.go_back()
        expect(self.page.locator("#document-reader")).to_be_visible()
        self.page.go_forward()
        expect(self.page.locator("#document-reader")).not_to_be_visible()

    def test_direct_anchor_links_and_escape(self):
        self.visit("?lang=en#doc=docs-en-configuration-reference-md&anchor=exact-resident-model-profile")
        target = self.page.locator("#reader-content #exact-resident-model-profile")
        expect(target).to_be_focused()
        expect(target).to_be_in_viewport()
        self.page.locator('#reader-content a[href="#doc=docs-en-model-guide-md"]').first.click()
        expect(self.page.locator("#reader-path")).to_have_text("docs/en/model-guide.md")
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#document-reader")).not_to_be_visible()
        expect(self.page.locator("#doc-search")).to_be_focused()

    def test_every_document_and_linked_source_can_be_opened(self):
        self.visit("?lang=en")
        for document in self.data()["documents"]:
            self.page.evaluate("id => { location.hash = 'doc=' + encodeURIComponent(id); }", document["id"])
            expect(self.page.locator("#reader-path")).to_have_text(document["path"])
            expect(self.page.locator("#download-document")).to_be_enabled()
            self.assertTrue(self.page.locator("#reader-content").inner_text().strip())
        self.page.evaluate("location.hash='doc=does-not-exist'")
        expect(self.page.locator("#download-document")).to_be_disabled()
        expect(self.page.locator("#reader-title")).not_to_be_empty()

    def test_profile_and_original_source_downloads(self):
        self.visit("?lang=en")
        data = self.data()
        with self.page.expect_download() as captured:
            self.page.locator("#download-profile").click()
        download = captured.value
        self.assertEqual(download.suggested_filename, "halo-strix.reference.json")
        self.assertEqual(json.loads(Path(download.path()).read_text(encoding="utf-8")), data["profile"])
        self.page.locator('a[data-doc-link="reference"]').first.click()
        with self.page.expect_download() as captured:
            self.page.locator("#download-document").click()
        download = captured.value
        self.assertEqual(download.suggested_filename, "configuration-reference.md")
        expected = next(item["markdown"] for item in data["documents"] if item["path"] == "docs/en/configuration-reference.md")
        self.assertEqual(Path(download.path()).read_text(encoding="utf-8"), expected)

    def test_clipboard_success_and_denied_fallback_are_honest(self):
        self.context.add_init_script("""
          Object.defineProperty(navigator, 'clipboard', {value: {
            writeText: async text => {
              if (window.rejectClipboard) throw new DOMException('Denied', 'NotAllowedError');
              window.testCopiedText = text;
            }
          }});
        """)
        self.visit("?lang=en")
        self.page.locator('[data-copy="model-args"]').click()
        expect(self.page.locator("#copy-status")).to_contain_text("Copied")
        self.assertEqual(
            self.page.evaluate("window.testCopiedText"),
            self.page.locator("#model-args").inner_text(),
        )
        self.page.evaluate("window.rejectClipboard = true")
        self.page.locator('[data-copy="endpoint-url"]').click()
        expect(self.page.locator("#copy-status")).not_to_contain_text("Copied")
        expect(self.page.locator("#copy-status")).not_to_be_empty()
        self.assertEqual(
            self.page.evaluate("getSelection().toString()"),
            self.page.locator("#endpoint-url").inner_text(),
        )

    def test_responsive_layout_reader_and_visual_snapshots(self):
        for width in (360, 390, 768, 1440):
            self.page.set_viewport_size({"width": width, "height": 900})
            self.visit("?lang=en&scoutTheme=dark")
            self.assert_no_overflow()
            expect(self.page.locator("#language-toggle")).to_be_visible()
            self.page.locator('a[data-doc-link="reference"]').first.click()
            expect(self.page.locator("#document-reader")).to_be_visible()
            self.assert_no_overflow()
            self.assertLessEqual(self.page.locator("#document-reader").bounding_box()["width"], width)
            self.page.keyboard.press("Escape")
        if SCREENSHOTS:
            directory = Path(SCREENSHOTS)
            directory.mkdir(parents=True, exist_ok=True)
            for width, theme in ((1440, "light"), (1440, "dark"), (390, "light")):
                self.page.set_viewport_size({"width": width, "height": 1000})
                self.visit(f"?lang=en&scoutTheme={theme}")
                self.page.screenshot(path=str(directory / f"halo-{width}-{theme}.png"), full_page=True)

    def test_secondary_text_contrast_in_both_themes(self):
        def luminance(rgb):
            channels = [value / 255 for value in rgb]
            channels = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
            return sum(value * weight for value, weight in zip(channels, (0.2126, 0.7152, 0.0722)))

        selectors = [
            ".hero-description", ".nav a", ".brand-name span", ".spec span",
            ".section-head > p", ".inventory dt", ".lesson p",
            ".status-description", ".control > label", ".workspace > p",
            ".footer p:last-child",
        ]
        for theme in ("light", "dark"):
            self.visit(f"?lang=en&scoutTheme={theme}")
            for selector in selectors:
                with self.subTest(theme=theme, selector=selector):
                    colors = self.page.locator(selector).first.evaluate("""node => {
                      const rgb = value => value.match(/[\\d.]+/g).map(Number);
                      const chain = [];
                      for (let current = node; current; current = current.parentElement) chain.unshift(current);
                      let background = [255, 255, 255];
                      for (const current of chain) {
                        const color = rgb(getComputedStyle(current).backgroundColor);
                        const alpha = color.length > 3 ? color[3] : 1;
                        background = background.map((old, index) => color[index] * alpha + old * (1-alpha));
                      }
                      return {foreground: rgb(getComputedStyle(node).color).slice(0,3), background};
                    }""")
                    values = sorted((luminance(colors["foreground"]), luminance(colors["background"])))
                    ratio = (values[1] + 0.05) / (values[0] + 0.05)
                    self.assertGreaterEqual(ratio, 4.5)

    def test_direct_file_opening_and_no_javascript_overview(self):
        self.page.goto(INDEX.as_uri() + "?lang=en&scoutTheme=dark#doc=docs-en-model-guide-md")
        expect(self.page.locator("#reader-path")).to_have_text("docs/en/model-guide.md")
        self.page.keyboard.press("Escape")
        self.page.locator("#language-toggle").click()
        expect(self.page.locator("html")).to_have_attribute("lang", "es")
        no_js = self.browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        self.addCleanup(no_js.close)
        page = no_js.new_page()
        page.goto(self.url)
        expect(page.locator("h1").first).to_be_visible()
        expect(page.locator("noscript").first).to_be_visible()
        expect(page.locator("#language-toggle")).not_to_be_visible()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser-channel", default="msedge", help="An already installed browser channel")
    parser.add_argument("--screenshots", help="Optional output directory outside site/dist")
    options, remaining = parser.parse_known_args()
    CHANNEL = options.browser_channel
    SCREENSHOTS = options.screenshots
    unittest.main(argv=[__file__] + remaining)
