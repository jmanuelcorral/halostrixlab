"""Build a self-contained static site from the reviewed public documentation."""

from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, quote, unquote, urlsplit

import markdown
from markdown.treeprocessors import Treeprocessor


ROOT = Path(__file__).resolve().parents[1]
MARKER = "__SITE_DATA__"
PRIVATE_PARTS = {
    ".git", ".squad", ".copilot", ".vscode", ".venv-site", "__pycache__",
    "data", "sandbox", ".sandbox", "build-start", "ownership", "dist",
    "node_modules", "test-results", "playwright-report",
}
SOURCE_EXTENSIONS = {".md", ".json", ".sh", ".yaml", ".yml", ".ps1", ".py"}
SOURCE_NAMES = {"Dockerfile", ".env.example", ".gitattributes", ".gitignore"}
SITE_SOURCES = {
    "README.md", "README.en.md", "site/README.md", "site/requirements.txt",
    "site/requirements-browser.txt", "site/index.template.html", ".github/workflows/pages.yml",
}


class BuildError(Exception):
    """The source tree cannot safely produce a complete standalone site."""


class ReaderLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag == "a" and attributes.get("href", "").startswith("#doc="):
            self.links.append(attributes["href"])


def heading_slug(value: str, separator: str) -> str:
    value = html.unescape(value).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    return re.sub(r"\s", separator, value)


class SourceLinks(Treeprocessor):
    def __init__(self, md, builder: "SiteBuilder", source: Path):
        super().__init__(md)
        self.builder = builder
        self.source = source

    def run(self, root):
        for element in root.iter("a"):
            href = element.get("href")
            if href is not None:
                rewritten = self.builder.rewrite_link(self.source, href)
                if rewritten is None:
                    element.tag = "span"
                    element.attrib.pop("href", None)
                else:
                    element.set("href", rewritten)
        if any(True for _ in root.iter("img")):
            raise BuildError(f"Image resources require explicit embedding: {self.source}")


class SiteBuilder:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.records: dict[str, dict] = {}
        self.ids: set[str] = set()

    def checked_path(self, relative: Path) -> Path:
        if relative.is_absolute() or ".." in relative.parts:
            raise BuildError(f"Source path is outside the publication scope: {relative}")
        path = self.root
        for part in relative.parts:
            if part in PRIVATE_PARTS:
                raise BuildError(f"Private source directory is excluded: {relative}")
            path = path / part
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise BuildError(f"Source links/junctions are not followed: {relative}")
        if not path.is_file():
            raise BuildError(f"Source file does not exist: {relative}")
        return path

    def read(self, relative: Path) -> str:
        return self.checked_path(relative).read_text(encoding="utf-8-sig")

    def add_source(self, relative: Path) -> dict:
        key = relative.as_posix()
        if key in self.records:
            return self.records[key]
        parts = relative.parts
        public_root = key in SITE_SOURCES
        public_tree = parts[0] in {"docs", "config", "scripts", "workspaces"}
        safe_type = relative.suffix in SOURCE_EXTENSIONS or relative.name in SOURCE_NAMES
        private_env = relative.name.startswith(".env") and relative.name != ".env.example"
        if not (public_root or (public_tree and safe_type)) or private_env:
            raise BuildError(f"Link points to a non-public source: {key}")
        text = self.read(relative)
        identifier = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
        if identifier in self.ids:
            raise BuildError(f"Document identifier collision: {key}")
        self.ids.add(identifier)
        is_document = relative.suffix == ".md"
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match[1].strip() if title_match else relative.name
        lang = "neutral"
        category = "source"
        if is_document:
            lang = "en" if (
                "en" in parts or relative.name.endswith(".en.md")
                or parts[0] in {"scripts", "site"}
            ) else "es"
            if parts[0] == "workspaces":
                category = "training"
            elif parts[0] == "scripts":
                category = "tools"
            elif "reference" in key or "reutilizable" in key:
                category = "reference"
            elif "model-guide" in key or "comparativa" in key:
                category = "models"
            elif "setup-guide" in key or "setup-completo" in key:
                category = "setup"
            elif parts[0] == "docs" and lang == "es":
                category = "history"
            else:
                category = "project"
        record = {
            "id": identifier, "path": key, "title": title, "lang": lang,
            "category": category, "kind": "document" if is_document else "file",
            "html": "", "markdown": text,
        }
        self.records[key] = record
        return record

    def rewrite_link(self, source: Path, href: str) -> str | None:
        # Placeholders describe private operator input, not a navigable endpoint.
        if "<" in href or ">" in href:
            return None
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
                raise BuildError(f"Unsupported external link in {source}")
            return href
        if parsed.query:
            raise BuildError(f"Unexpected query on local source link in {source}")
        if parsed.path:
            path = Path(unquote(parsed.path).replace("\\", "/"))
            if path.is_absolute():
                raise BuildError(f"Root-relative source link in {source}: {parsed.path}")
            normalized: list[str] = list(source.parent.parts)
            for part in path.parts:
                if part == "..":
                    if not normalized:
                        raise BuildError(f"Source link escapes the repository: {source}")
                    normalized.pop()
                elif part != ".":
                    normalized.append(part)
            target = Path(*normalized)
        else:
            target = source
        record = self.add_source(target)
        rewritten = "#doc=" + quote(record["id"], safe="")
        if parsed.fragment:
            rewritten += "&anchor=" + quote(unquote(parsed.fragment), safe="")
        return rewritten

    def render(self, record: dict) -> str:
        if record["kind"] == "file":
            return "<pre><code>" + html.escape(record["markdown"]) + "</code></pre>"
        md = markdown.Markdown(
            extensions=["fenced_code", "tables", "toc", "sane_lists"],
            extension_configs={"toc": {"slugify": heading_slug}},
            output_format="html",
        )
        # Raw Markdown HTML is displayed as text, never executed in the reader.
        md.preprocessors.deregister("html_block")
        md.inlinePatterns.deregister("html")
        md.treeprocessors.register(SourceLinks(md, self, Path(record["path"])), "source-links", 4)
        return md.convert(record["markdown"])

    def collect(self) -> list[dict]:
        def documents_under(directory: Path):
            for path in sorted(directory.iterdir()):
                if path.name in PRIVATE_PARTS:
                    continue
                if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                    raise BuildError(f"Source links/junctions are not followed: {path.relative_to(self.root)}")
                if path.is_dir():
                    yield from documents_under(path)
                elif path.suffix == ".md":
                    yield path.relative_to(self.root)

        initial = [Path("README.md"), Path("README.en.md"), Path("site/README.md")]
        for folder in ("docs", "workspaces"):
            base = self.root / folder
            if base.is_symlink() or (hasattr(base, "is_junction") and base.is_junction()):
                raise BuildError(f"Documentation root is a link: {folder}")
            initial.extend(documents_under(base))
        initial.append(Path("scripts/README.md"))
        for path in initial:
            self.add_source(path)
        rendered: set[str] = set()
        while len(rendered) < len(self.records):
            for key in list(self.records):
                if key not in rendered:
                    self.records[key]["html"] = self.render(self.records[key])
                    rendered.add(key)
        parsed = {}
        for record in self.records.values():
            document = ReaderLinks()
            document.feed(record["html"])
            parsed[record["id"]] = document
        for record in self.records.values():
            for link in parsed[record["id"]].links:
                route = parse_qs(link[1:])
                target = route["doc"][0]
                if target not in parsed:
                    raise BuildError(f"Unknown reader route in {record['path']}")
                fragment = route.get("anchor", [""])[0]
                if fragment and fragment not in parsed[target].ids:
                    raise BuildError(f"Missing reader anchor in {record['path']}: {fragment}")
        return sorted(self.records.values(), key=lambda item: item["path"])

    def build(self, output: Path) -> dict:
        template = self.read(Path("site/index.template.html"))
        if template.count(MARKER) != 1:
            raise BuildError("The HTML template must contain exactly one data marker.")
        profile = json.loads(self.read(Path("config/halo-strix.reference.json")))
        documents = self.collect()
        data = {
            "metadata": {
                "snapshotDate": profile["positive_baseline_evidence_through"],
                "preparedDate": profile["consolidated_on"],
                "documentCount": sum(item["kind"] == "document" for item in documents),
                "sourceCount": sum(item["kind"] == "file" for item in documents),
            },
            "profile": profile,
            "documents": documents,
        }
        serialized = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
        serialized = serialized.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        page = template.replace(MARKER, serialized)
        output = output.absolute()
        for path in (output, *output.parents):
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise BuildError("The output directory must not traverse a link or junction.")
        if output.exists():
            for path in output.iterdir():
                if path.name not in {"index.html", ".nojekyll"} or not path.is_file() or path.is_symlink():
                    raise BuildError("Output directory contains unexpected files; use an isolated site directory.")
        output.mkdir(parents=True, exist_ok=True)
        (output / "index.html").write_text(page, encoding="utf-8", newline="\n")
        (output / ".nojekyll").write_text("", encoding="utf-8")
        return data["metadata"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, help="Isolated output directory (default: site/dist)")
    args = parser.parse_args()
    output = args.output if args.output is not None else args.source_root / "site" / "dist"
    try:
        metadata = SiteBuilder(args.source_root).build(output)
    except (BuildError, OSError, ValueError, KeyError) as error:
        print(f"Site build failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Built {metadata['documentCount']} documents and {metadata['sourceCount']} linked "
        f"source files into {output / 'index.html'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
