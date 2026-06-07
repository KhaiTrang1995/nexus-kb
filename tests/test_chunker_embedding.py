from __future__ import annotations

import unittest

from tests import _paths  # noqa: F401

from nexus_document_parser.chunker import TextChunker
from nexus_document_parser.embedding import DeterministicEmbeddingProvider
from nexus_shared.contracts import ParsedDocument, SourceType


class ChunkerEmbeddingTest(unittest.TestCase):
    def test_chunks_document_with_metadata(self) -> None:
        document = ParsedDocument(
            source_type=SourceType.LOCAL_FILE,
            source_path="/tmp/doc.md",
            file_extension=".md",
            mime_type="text/markdown",
            title="Doc",
            content="First paragraph.\n\nSecond paragraph with more words.\n\nThird paragraph.",
            content_hash="hash",
            tags=["rag"],
            wikilinks=["Vector Store"],
        )

        chunks = TextChunker(max_chars=45, overlap_chars=5).chunk_document(document)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].chunk_index, 0)
        self.assertEqual(chunks[0].metadata["tags"], ["rag"])
        self.assertEqual(chunks[0].metadata["wikilinks"], ["Vector Store"])
        self.assertGreater(chunks[0].token_count, 0)

    def test_markdown_headings_are_carried_into_chunk_metadata(self) -> None:
        document = ParsedDocument(
            source_type=SourceType.OBSIDIAN,
            source_path="/vault/nexus.md",
            file_extension=".md",
            mime_type="text/markdown",
            title="Nexus",
            content="# Platform\n\nIntro text.\n\n## Retrieval\n\nRAG search details.\n\n## Graph\n\nGraph details.",
            content_hash="hash",
            tags=["rag"],
            wikilinks=["Graph"],
        )

        chunks = TextChunker(max_chars=80, overlap_chars=10).chunk_document(document)

        heading_paths = [chunk.metadata["heading_path"] for chunk in chunks]
        self.assertIn(["Platform", "Retrieval"], heading_paths)
        self.assertTrue(all("char_start" in chunk.metadata for chunk in chunks))
        self.assertTrue(all("char_end" in chunk.metadata for chunk in chunks))

    def test_deterministic_embedding_is_stable_and_normalized(self) -> None:
        provider = DeterministicEmbeddingProvider(dimension=8)

        first = provider.embed(["same text"])[0]
        second = provider.embed(["same text"])[0]

        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        norm = sum(value * value for value in first) ** 0.5
        self.assertAlmostEqual(norm, 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
