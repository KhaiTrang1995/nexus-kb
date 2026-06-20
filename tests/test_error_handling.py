from __future__ import annotations

import unittest
from pathlib import Path
from uuid import UUID, uuid4

from tests import _paths  # noqa: F401

from nexus_document_parser.embedding import DeterministicEmbeddingProvider
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_shared.contracts import IngestionRunRecord, IngestionStatus, SourceType


class FailingPathRepository:
    def __init__(self) -> None:
        self.run_id = uuid4()

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
            source_path="missing",
            status=status,
            documents_seen=documents_seen,
            documents_indexed=documents_indexed,
            chunks_indexed=chunks_indexed,
            error_message=error_message,
        )

    def record_audit_log(self, actor_id, action, status, resource_id=None, details=None):
        # Stub for error path test (INGEST_START is recorded before load failure surfaces).
        pass


class NoopVectorClient:
    def upsert_chunks(self, points):
        return None


class ErrorHandlingTest(unittest.TestCase):
    def test_missing_source_path_returns_failed_ingestion_run(self) -> None:
        pipeline = IngestionPipeline(
            repository=FailingPathRepository(),
            vector_client=NoopVectorClient(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        )
        missing = Path("tests") / "fixtures" / "missing"

        with self.assertLogs("nexus_document_parser.pipeline", level="ERROR") as logs:
            result = pipeline.ingest(str(missing), SourceType.LOCAL_FILE)

        self.assertEqual(result.status, IngestionStatus.FAILED)
        self.assertIn("source path does not exist", result.error_message or "")
        self.assertTrue(any("ingestion pipeline failed" in message for message in logs.output))
        self.assertEqual(result.documents_seen, 0)
        self.assertEqual(result.documents_indexed, 0)
        self.assertEqual(result.chunks_indexed, 0)


if __name__ == "__main__":
    unittest.main()
