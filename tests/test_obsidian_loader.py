import unittest
from pathlib import Path

from tests import _paths  # noqa: F401

from nexus_document_parser.loader import extract_wikilinks, load_documents, parse_frontmatter
from nexus_shared.contracts import SourceType


class ObsidianLoaderTest(unittest.TestCase):
    def test_parses_frontmatter_tags_and_wikilinks(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "obsidian"

        documents = load_documents(str(fixture), SourceType.OBSIDIAN)

        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertEqual(document.title, "Platform Overview")
        self.assertEqual(document.source_type, SourceType.OBSIDIAN)
        self.assertEqual(document.file_extension, ".md")
        self.assertEqual(document.mime_type, "text/markdown")
        self.assertEqual(document.frontmatter["owner"], "platform")
        self.assertEqual(document.tags, ["architecture", "obsidian", "phase/one", "rag"])
        self.assertEqual(document.wikilinks, ["Graph Layer", "Vector Store"])

    def test_loads_plain_text_without_wikilinks_or_frontmatter(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "plain"

        documents = load_documents(str(fixture), SourceType.LOCAL_FILE)

        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertEqual(document.file_extension, ".txt")
        self.assertEqual(document.mime_type, "text/plain")
        self.assertEqual(document.title, "plain")
        self.assertEqual(document.frontmatter, {})
        self.assertEqual(document.wikilinks, [])

    def test_ignores_unsupported_files(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "unsupported"

        documents = load_documents(str(fixture), SourceType.LOCAL_FILE)

        self.assertEqual(documents, [])

    def test_parse_frontmatter_returns_body_when_missing(self) -> None:
        frontmatter, body = parse_frontmatter("# Plain\n\nNo metadata")

        self.assertEqual(frontmatter, {})
        self.assertEqual(body, "# Plain\n\nNo metadata")

    def test_extract_wikilinks_ignores_alias_and_heading(self) -> None:
        links = extract_wikilinks("[[Page#Section|Alias]] and [[Other Page]]")

        self.assertEqual(links, {"Other Page", "Page"})


if __name__ == "__main__":
    unittest.main()
