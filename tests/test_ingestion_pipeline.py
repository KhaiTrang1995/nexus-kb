import unittest
from pathlib import Path
from uuid import UUID, uuid4

from tests import _paths  # noqa: F401

from nexus_document_parser.chunker import TextChunker
from nexus_document_parser.embedding import DeterministicEmbeddingProvider
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_shared.contracts import DocumentRecord, IngestionRunRecord, IngestionStatus, SourceType


class FakeRepository:
    def __init__(self) -> None:
        self.run_id = uuid4()
        self.documents_by_path: dict[str, DocumentRecord] = {}
        self.chunks_replaced = 0

    def create_ingestion_run(self, source_path: str) -> IngestionRunRecord:
        return IngestionRunRecord(id=self.run_id, source_path=source_path, status=IngestionStatus.RUNNING)

    def finish_ingestion_run(
        self,
        run_id: UUID,
        status: IngestionStatus,
        documents_seen: int,
        documents_indexed: int,
        chunks_indexed: int,
        error_message: str | None = None,
    ) -> IngestionRunRecord:
        return IngestionRunRecord(
            id=run_id,
            source_path="source",
            status=status,
            documents_seen=documents_seen,
            documents_indexed=documents_indexed,
            chunks_indexed=chunks_indexed,
            error_message=error_message,
        )

    def upsert_document(self, document):
        existing = self.documents_by_path.get(document.source_path)
        if existing and existing.content_hash == document.content_hash:
            return existing, False

        record = DocumentRecord(
            id=existing.id if existing else uuid4(),
            source_type=document.source_type,
            source_path=document.source_path,
            file_extension=document.file_extension,
            mime_type=document.mime_type,
            title=document.title,
            content_hash=document.content_hash,
            frontmatter=document.frontmatter,
            tags=document.tags,
            wikilinks=document.wikilinks,
        )
        self.documents_by_path[document.source_path] = record
        return record, True

    def replace_chunks(self, document_id, chunks, embedding_model):
        self.chunks_replaced += len(chunks)
        return [(uuid4(), chunk) for chunk in chunks]


class FakeVectorClient:
    def __init__(self) -> None:
        self.points = []

    def upsert_chunks(self, points):
        self.points.extend(points)


class IngestionPipelineTest(unittest.TestCase):
    def test_ingests_changed_documents_and_skips_unchanged(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "pipeline"
        repository = FakeRepository()
        vector_client = FakeVectorClient()
        pipeline = IngestionPipeline(
            repository=repository,
            vector_client=vector_client,
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            chunker=TextChunker(max_chars=200, overlap_chars=20),
        )

        first = pipeline.ingest(str(fixture), SourceType.OBSIDIAN)
        second = pipeline.ingest(str(fixture), SourceType.OBSIDIAN)

        self.assertEqual(first.status, IngestionStatus.COMPLETED)
        self.assertEqual(first.documents_seen, 1)
        self.assertEqual(first.documents_indexed, 1)
        self.assertEqual(first.chunks_indexed, 1)
        self.assertEqual(second.documents_seen, 1)
        self.assertEqual(second.documents_indexed, 0)
        self.assertEqual(second.chunks_indexed, 0)
        self.assertEqual(len(vector_client.points), 1)
        point_id, vector, payload = vector_client.points[0]
        self.assertEqual(str(point_id), payload.chunk_id)
        self.assertEqual(len(vector), 8)
        self.assertEqual(payload.tags, ["rag"])
        self.assertEqual(payload.wikilinks, ["Graph"])
        self.assertEqual(payload.heading_path, ["RAG", "Retrieval"])
        self.assertEqual(payload.section_title, "Retrieval")


if __name__ == "__main__":
    unittest.main()
