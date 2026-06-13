from __future__ import annotations

import unittest
from uuid import UUID, uuid4

from tests import _paths  # noqa: F401

from nexus_api.search import SearchService
from nexus_document_parser.embedding import DeterministicEmbeddingProvider
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_shared.contracts import (
    AuditRecord,
    AuditStatus,
    DocumentRecord,
    IngestionRunRecord,
    IngestionStatus,
    ParsedDocument,
    SearchRequest,
    SourceType,
)


class AuditRepository:
    def __init__(self) -> None:
        self.run_id = uuid4()
        self.audit_logs: list[AuditRecord] = []
        self.document_id = uuid4()
        self.chunk_id = uuid4()

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

    def upsert_document(self, document: ParsedDocument):
        return (
            DocumentRecord(
                id=self.document_id,
                source_type=document.source_type,
                source_path=document.source_path,
                file_extension=document.file_extension,
                mime_type=document.mime_type,
                title=document.title,
                content_hash=document.content_hash,
                frontmatter={},
                tags=[],
                wikilinks=[],
            ),
            True,
        )

    def replace_chunks(self, document_id, chunks, embedding_model):
        return [(self.chunk_id, chunk) for chunk in chunks]

    def get_chunk_with_document(self, chunk_id):
        return {
            "chunk_id": chunk_id,
            "document_id": self.document_id,
            "chunk_index": 0,
            "content": "governed retrieval audit",
            "chunk_metadata": {},
            "title": "Audit",
            "source_path": "/docs/audit.md",
            "file_extension": ".md",
            "mime_type": "text/markdown",
            "source_type": "local_file",
            "tags": [],
            "wikilinks": [],
            "frontmatter": {},
        }

    def record_audit_log(self, actor_id, action, status, resource_id=None, details=None):
        record = AuditRecord(
            id=uuid4(),
            actor_id=actor_id,
            action=action,
            status=status,
            resource_id=resource_id,
            details=details or {},
        )
        self.audit_logs.append(record)
        return record

    def list_audit_logs(self, limit=50, offset=0, action_filter=None, actor_filter=None):
        # Return captured for audit tests; full filter not exercised here.
        return list(self.audit_logs)

    def create_review_item(self, *a, **k):
        raise NotImplementedError("review not used in audit trail unit test")

    def list_review_items(self, *a, **k):
        return []

    def get_review_item(self, item_id):
        return None

    def mark_review_item(self, *a, **k):
        raise NotImplementedError("review not used in audit trail unit test")

    def update_chunk_content(self, chunk_id, content, metadata=None):
        pass

    def list_approved_graph_chunks(self, limit=100):
        return []


class SingleDocumentLoader:
    def load(self, source_path: str, source_type: SourceType):
        return [
            ParsedDocument(
                source_type=source_type,
                source_path=f"{source_path}/audit.md",
                file_extension=".md",
                mime_type="text/markdown",
                title="Audit",
                content="governed retrieval audit",
                content_hash="hash",
            )
        ]


class FakeVectorClient:
    def __init__(self, chunk_id=None) -> None:
        self.chunk_id = chunk_id

    def upsert_chunks(self, points):
        return None

    def search(self, vector, limit=10, tags=None, source_type=None):
        return [{"id": str(self.chunk_id), "score": 0.9, "payload": {"chunk_id": str(self.chunk_id)}}]


class AuditTrailTest(unittest.TestCase):
    def test_ingestion_writes_start_and_finish_audit_logs(self) -> None:
        repository = AuditRepository()
        pipeline = IngestionPipeline(
            repository=repository,
            vector_client=FakeVectorClient(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            document_loader=SingleDocumentLoader(),
        )

        result = pipeline.ingest("source", SourceType.LOCAL_FILE)

        self.assertEqual(result.status, IngestionStatus.COMPLETED)
        self.assertEqual(
            [log.action for log in repository.audit_logs],
            ["INGEST_START", "DOCUMENT_READ", "CHUNK_GENERATED", "INGEST_FINISH"],
        )
        self.assertTrue(all(log.status == AuditStatus.SUCCESS for log in repository.audit_logs))
        chunk_log = next(log for log in repository.audit_logs if log.action == "CHUNK_GENERATED")
        self.assertIsInstance(chunk_log.details["content_hash"], str)
        self.assertEqual(chunk_log.details["token_count"], 3)
        self.assertNotIn("governed retrieval audit", str(chunk_log.details))

    def test_search_writes_query_audit_log(self) -> None:
        repository = AuditRepository()
        service = SearchService(
            repository=repository,
            vector_client=FakeVectorClient(repository.chunk_id),
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        )

        response = service.search(SearchRequest(query="audit"))

        self.assertEqual(len(response.results), 1)
        self.assertEqual(repository.audit_logs[0].action, "SEARCH_QUERY")
        self.assertEqual(repository.audit_logs[0].details["query"], "audit")


if __name__ == "__main__":
    unittest.main()
