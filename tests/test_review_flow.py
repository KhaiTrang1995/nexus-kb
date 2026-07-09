from __future__ import annotations

import unittest
from uuid import UUID, uuid4

from tests import _paths  # noqa: F401

from nexus_api.review import ReviewService
from nexus_document_parser.embedding import DeterministicEmbeddingProvider
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_shared.contracts import (
    AuditRecord,
    ChunkCandidate,
    DocumentRecord,
    IngestionRunRecord,
    IngestionStatus,
    ParsedDocument,
    ReviewAction,
    ReviewActionRequest,
    ReviewItemRecord,
    ReviewStatus,
    SourceType,
)


class ReviewRepository:
    def __init__(self) -> None:
        self.run_id = uuid4()
        self.document_id = uuid4()
        self.chunk_id = uuid4()
        self.review_items: dict[UUID, ReviewItemRecord] = {}
        self.updated_chunks: list[tuple[UUID, str, dict]] = []
        self.audit_logs: list[AuditRecord] = []

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

    def upsert_document(self, document: ParsedDocument, workspace_id=None, uploaded_by=None):
        return (
            DocumentRecord(
                id=self.document_id,
                source_type=document.source_type,
                source_path=document.source_path,
                file_extension=document.file_extension,
                mime_type=document.mime_type,
                title=document.title,
                content_hash=document.content_hash,
            ),
            True,
        )

    def replace_chunks(self, document_id, chunks, embedding_model):
        return [(self.chunk_id, chunk) for chunk in chunks]

    def create_review_item(self, run_id, source_path, content, confidence, payload=None):
        item = ReviewItemRecord(
            id=uuid4(),
            run_id=run_id,
            source_path=source_path,
            content=content,
            confidence=confidence,
            status=ReviewStatus.PENDING,
            payload=payload or {},
        )
        self.review_items[item.id] = item
        return item

    def list_review_items(self, limit=50, offset=0, min_confidence=None, status=ReviewStatus.PENDING):
        items = [item for item in self.review_items.values() if status is None or item.status == status]
        if min_confidence is not None:
            items = [item for item in items if item.confidence >= min_confidence]
        return items[offset : offset + limit]

    def get_review_item(self, item_id):
        return self.review_items.get(item_id)

    def mark_review_item(self, item_id, status, reviewer_id, content=None, payload=None):
        item = self.review_items[item_id]
        updated = item.model_copy(
            update={
                "status": status,
                "reviewer_id": reviewer_id,
                "content": content if content is not None else item.content,
                "payload": payload if payload is not None else item.payload,
            }
        )
        self.review_items[item_id] = updated
        return updated

    def update_chunk_content(self, chunk_id, content, metadata=None):
        self.updated_chunks.append((chunk_id, content, metadata or {}))

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
        return list(self.audit_logs)

    def get_chunk_with_document(self, chunk_id):
        return None

    def list_approved_graph_chunks(self, limit=100):
        return []


class LowConfidenceChunker:
    def chunk_document(self, document):
        return [
            ChunkCandidate(
                chunk_index=0,
                content=document.content,
                content_hash=document.content_hash,
                token_count=3,
                metadata={"confidence": 0.42, "heading_path": ["Review"]},
            )
        ]


class SingleDocumentLoader:
    def load(self, source_path: str, source_type: SourceType):
        return [
            ParsedDocument(
                source_type=source_type,
                source_path=f"{source_path}/review.md",
                file_extension=".md",
                mime_type="text/markdown",
                title="Review",
                content="low confidence entity",
                content_hash="hash",
            )
        ]


class FakeVectorClient:
    def __init__(self) -> None:
        self.points = []

    def upsert_chunks(self, points):
        self.points.extend(points)


class ReviewFlowTest(unittest.TestCase):
    def test_low_confidence_chunks_route_to_review_queue(self) -> None:
        repository = ReviewRepository()
        vector_client = FakeVectorClient()
        pipeline = IngestionPipeline(
            repository=repository,
            vector_client=vector_client,
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            chunker=LowConfidenceChunker(),
            document_loader=SingleDocumentLoader(),
            confidence_threshold=0.70,
        )

        result = pipeline.ingest("source", SourceType.LOCAL_FILE)

        self.assertEqual(result.status, IngestionStatus.COMPLETED)
        self.assertEqual(result.chunks_indexed, 0)
        self.assertEqual(len(vector_client.points), 0)
        self.assertEqual(len(repository.list_review_items()), 1)
        item = repository.list_review_items()[0]
        self.assertEqual(item.confidence, 0.42)
        self.assertEqual(item.payload["qdrant_payload"]["chunk_id"], str(repository.chunk_id))

    def test_approve_review_item_pushes_to_qdrant(self) -> None:
        repository = ReviewRepository()
        vector_client = FakeVectorClient()
        pipeline = IngestionPipeline(
            repository=repository,
            vector_client=vector_client,
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            chunker=LowConfidenceChunker(),
            document_loader=SingleDocumentLoader(),
        )
        pipeline.ingest("source", SourceType.LOCAL_FILE)
        item = repository.list_review_items()[0]
        service = ReviewService(repository, vector_client, DeterministicEmbeddingProvider(dimension=8))

        response = service.apply_action(
            ReviewActionRequest(item_id=item.id, action=ReviewAction.APPROVE),
            reviewer_id="reviewer@example.test",
        )

        self.assertEqual(response.status, ReviewStatus.APPROVED)
        self.assertEqual(len(vector_client.points), 1)
        self.assertEqual(vector_client.points[0][0], repository.chunk_id)
        self.assertEqual(repository.review_items[item.id].status, ReviewStatus.APPROVED)

    def test_modify_review_item_updates_payload_and_chunk_content(self) -> None:
        repository = ReviewRepository()
        vector_client = FakeVectorClient()
        pipeline = IngestionPipeline(
            repository=repository,
            vector_client=vector_client,
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            chunker=LowConfidenceChunker(),
            document_loader=SingleDocumentLoader(),
        )
        pipeline.ingest("source", SourceType.LOCAL_FILE)
        item = repository.list_review_items()[0]
        service = ReviewService(repository, vector_client, DeterministicEmbeddingProvider(dimension=8))

        response = service.apply_action(
            ReviewActionRequest(
                item_id=item.id,
                action=ReviewAction.MODIFY,
                modified_content="edited entity",
                modified_payload={"tags": ["edited"]},
            ),
            reviewer_id="reviewer@example.test",
        )

        self.assertEqual(response.status, ReviewStatus.MODIFIED)
        self.assertEqual(repository.updated_chunks[0][1], "edited entity")
        self.assertEqual(repository.review_items[item.id].payload["qdrant_payload"]["tags"], ["edited"])


if __name__ == "__main__":
    unittest.main()
