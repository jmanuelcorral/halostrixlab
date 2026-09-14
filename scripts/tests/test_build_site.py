"""Offline CLI regression tests for the static-site generator."""

import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


BUILDER = Path(__file__).resolve().parents[1] / "build_site.py"


class EmbeddedData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "site-data":
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


class SiteBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="halostrix-site-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.output = Path(self.temporary.name) / "output"
        self.write("README.md", "# Inicio\n\n[English](README.en.md)\n")
        self.write("README.en.md", "# Home\n\n[Spanish](README.md)\n")
        self.write("site/README.md", "# Deployment\n")
        self.write("scripts/README.md", "# Client guide\n")
        self.write(
            "site/index.template.html",
            '<!doctype html><html><script id="site-data" type="application/json">'
            '__SITE_DATA__</script><body>Static overview</body></html>',
        )
        self.profile = {
            "positive_baseline_evidence_through": "2026-09-04",
            "consolidated_on": "2026-09-07",
            "native_lemonade_importable": False,
            "test_literal": "</script><script>UNSAFE</script>",
        }
        self.write("config/halo-strix.reference.json", json.dumps(self.profile))
        (self.root / "docs").mkdir()
        (self.root / "workspaces").mkdir()

    def write(self, path, text):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")

    def invoke(self):
        return subprocess.run(
            [sys.executable, str(BUILDER), "--source-root", str(self.root),
             "--output", str(self.output)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
            check=False,
        )

    def build(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        page = (self.output / "index.html").read_text(encoding="utf-8")
        parser = EmbeddedData()
        parser.feed(page)
        return page, json.loads("".join(parser.parts))

    def test_cli_embeds_every_guide_and_preserves_profile(self):
        self.write("docs/en/example.md", "# Example\n\nComplete instructions.\n")
        _, data = self.build()
        self.assertEqual(data["profile"], self.profile)
        self.assertEqual(data["metadata"]["documentCount"], 5)
        self.assertEqual(data["metadata"]["sourceCount"], 0)
        guide = next(item for item in data["documents"] if item["path"] == "docs/en/example.md")
        self.assertEqual(guide["lang"], "en")
        self.assertIn("Complete instructions.", guide["html"])
        self.assertTrue((self.output / ".nojekyll").is_file())

    def test_script_closing_tags_are_safely_embedded(self):
        page, data = self.build()
        self.assertNotIn("</script><script>UNSAFE", page)
        self.assertEqual(data["profile"]["test_literal"], self.profile["test_literal"])

    def test_internal_and_cross_document_anchors_are_reader_routes(self):
        self.write("docs/example.md", "# Configuraci\u00f3n\n\n[Here](#configuraci%C3%B3n)\n")
        self.write("README.md", "# Inicio\n\n[Guide](docs/example.md#configuraci%C3%B3n)\n")
        _, data = self.build()
        guide = next(item for item in data["documents"] if item["path"] == "docs/example.md")
        home = next(item for item in data["documents"] if item["path"] == "README.md")
        self.assertIn('id="configuraci\u00f3n"', guide["html"])
        self.assertIn("#doc=docs-example-md&amp;anchor=configuraci%C3%B3n", guide["html"])
        self.assertIn("#doc=docs-example-md&amp;anchor=configuraci%C3%B3n", home["html"])

    def test_linked_source_and_reviewed_env_template_are_embedded(self):
        self.write("workspaces/example/.env.example", "DEVICE_GID=\n")
        self.write("scripts/example.sh", "#!/usr/bin/env bash\nprintf 'example\\n'\n")
        self.write("README.md", "# Home\n\n[Script](scripts/example.sh)\n\n"
                   "[Template](workspaces/example/.env.example)\n")
        _, data = self.build()
        sources = [item for item in data["documents"] if item["kind"] == "file"]
        self.assertEqual(len(sources), 2)
        self.assertIn("DEVICE_GID=", sources[1]["markdown"])
        self.assertEqual(data["metadata"]["sourceCount"], 2)

    def test_private_environment_link_fails_without_copying_values(self):
        self.write("workspaces/example/.env", "SYNTHETIC_PRIVATE_VALUE\n")
        self.write("README.md", "# Home\n\n[Private](workspaces/example/.env)\n")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-public source", result.stderr)
        self.assertNotIn("SYNTHETIC_PRIVATE_VALUE", result.stderr)
        self.assertFalse((self.output / "index.html").exists())

    def test_runtime_data_and_agent_state_are_not_collected(self):
        self.write("workspaces/example/data/notes.md", "# SYNTHETIC_PRIVATE_DATA")
        self.write(".squad/team.md", "# SYNTHETIC_PRIVATE_TEAM")
        page, _ = self.build()
        self.assertNotIn("SYNTHETIC_PRIVATE_DATA", page)
        self.assertNotIn("SYNTHETIC_PRIVATE_TEAM", page)

    def test_broken_and_outside_links_fail(self):
        for target in ("docs/missing.md", "../outside.md", ".squad/team.md"):
            with self.subTest(target=target):
                self.write("README.md", f"# Home\n\n[Link]({target})\n")
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.output / "index.html").exists())

    def test_executable_urls_are_rejected(self):
        self.write("README.md", "# Home\n\n[Bad](javascript:alert)\n")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsupported external link", result.stderr)

    def test_missing_heading_fails_instead_of_publishing_a_broken_route(self):
        self.write("README.md", "# Home\n\n[Missing](README.en.md#not-a-heading)\n")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing reader anchor", result.stderr)

    def test_raw_html_is_displayed_not_executed(self):
        self.write("README.md", '# Home\n\n<script>alert("fixture")</script>\n\n'
                   '<iframe src="https://example.invalid"></iframe>\n')
        _, data = self.build()
        home = next(item for item in data["documents"] if item["path"] == "README.md")
        self.assertNotIn("<script>", home["html"])
        self.assertNotIn("<iframe", home["html"])
        self.assertIn("&lt;script&gt;", home["html"])

    def test_unexpected_output_files_block_publication(self):
        self.output.mkdir()
        (self.output / "private.txt").write_text("fixture", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected files", result.stderr)
        self.assertEqual((self.output / "private.txt").read_text(), "fixture")

    def test_template_requires_one_marker(self):
        for value in ("none", "__SITE_DATA____SITE_DATA__"):
            with self.subTest(value=value):
                self.write("site/index.template.html", value)
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("exactly one data marker", result.stderr)

    def test_build_is_deterministic(self):
        first, _ = self.build()
        second, _ = self.build()
        self.assertEqual(first, second)

    def test_source_symlinks_are_rejected_when_supported(self):
        source = self.root / "docs" / "linked.md"
        try:
            source.symlink_to(self.root / "README.md")
        except OSError as error:
            self.skipTest(f"Native symlink creation unavailable: {error}")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not followed", result.stderr)


if __name__ == "__main__":
    unittest.main()
