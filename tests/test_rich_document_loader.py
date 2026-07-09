import unittest
from pathlib import Path

from tests import _paths  # noqa: F401

from nexus_document_parser.converters import MarkItDownConverter
from nexus_document_parser.loader import RICH_EXTENSIONS, SUPPORTED_EXTENSIONS, load_documents
from nexus_shared.contracts import SourceType

FIXTURES = Path(__file__).parent / "fixtures" / "rich"
EMPTY_FIXTURE = Path(__file__).parent / "fixtures" / "rich-empty"


class RichDocumentLoaderTest(unittest.TestCase):
    def test_supported_extensions_include_rich_formats(self) -> None:
        self.assertEqual(RICH_EXTENSIONS, {".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".html"})
        self.assertTrue(RICH_EXTENSIONS.issubset(SUPPORTED_EXTENSIONS))

    def test_loads_pdf_via_markitdown(self) -> None:
        documents = load_documents(str(FIXTURES / "sample.pdf"), SourceType.LOCAL_FILE)

        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertEqual(document.file_extension, ".pdf")
        self.assertEqual(document.mime_type, "application/pdf")
        self.assertIn("Nexus KB Sample PDF", document.content)
        self.assertEqual(document.frontmatter, {})
        self.assertEqual(document.wikilinks, [])

    def test_loads_docx_via_markitdown(self) -> None:
        documents = load_documents(str(FIXTURES / "sample.docx"), SourceType.LOCAL_FILE)

        document = documents[0]
        self.assertEqual(document.file_extension, ".docx")
        self.assertEqual(document.title, "Nexus KB Sample Doc")
        self.assertIn("synthetic DOCX fixture", document.content)

    def test_loads_xlsx_via_markitdown(self) -> None:
        documents = load_documents(str(FIXTURES / "sample.xlsx"), SourceType.LOCAL_FILE)

        document = documents[0]
        self.assertEqual(document.file_extension, ".xlsx")
        self.assertIn("| alpha | 1 |", document.content)

    def test_loads_pptx_via_markitdown(self) -> None:
        documents = load_documents(str(FIXTURES / "sample.pptx"), SourceType.LOCAL_FILE)

        document = documents[0]
        self.assertEqual(document.file_extension, ".pptx")
        self.assertEqual(document.title, "Nexus KB Sample Slide")

    def test_loads_csv_via_markitdown(self) -> None:
        documents = load_documents(str(FIXTURES / "sample.csv"), SourceType.LOCAL_FILE)

        document = documents[0]
        self.assertEqual(document.file_extension, ".csv")
        self.assertEqual(document.mime_type, "text/csv")
        self.assertIn("| beta | 2 |", document.content)

    def test_loads_html_via_markitdown(self) -> None:
        documents = load_documents(str(FIXTURES / "sample.html"), SourceType.LOCAL_FILE)

        document = documents[0]
        self.assertEqual(document.file_extension, ".html")
        self.assertEqual(document.mime_type, "text/html")
        self.assertEqual(document.title, "Nexus KB Sample HTML")
        self.assertIn("Synthetic HTML fixture", document.content)

    def test_rejects_empty_rich_file(self) -> None:
        with self.assertRaises(ValueError):
            load_documents(str(EMPTY_FIXTURE / "empty.pdf"), SourceType.LOCAL_FILE)

    def test_directory_scan_picks_up_mixed_formats(self) -> None:
        documents = load_documents(str(FIXTURES), SourceType.LOCAL_FILE)

        extensions = {document.file_extension for document in documents}
        self.assertEqual(extensions, {".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".html"})

    def test_injected_converter_is_used_instead_of_default(self) -> None:
        calls: list[Path] = []

        class RecordingConverter:
            def convert(self, path: Path) -> str:
                calls.append(path)
                return "# Recorded\n\nStub content."

        documents = load_documents(
            str(FIXTURES / "sample.pdf"),
            SourceType.LOCAL_FILE,
            converter=RecordingConverter(),
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(documents[0].content, "# Recorded\n\nStub content.")

    def test_markitdown_converter_is_callable_directly(self) -> None:
        converter = MarkItDownConverter()
        text = converter.convert(FIXTURES / "sample.csv")

        self.assertIn("alpha", text)


if __name__ == "__main__":
    unittest.main()
