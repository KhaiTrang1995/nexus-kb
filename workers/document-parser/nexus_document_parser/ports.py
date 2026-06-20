from __future__ import annotations

from typing import Protocol
from uuid import UUID

from nexus_shared.contracts import (
    AuditRecord,
    AuditStatus,
    ChunkCandidate,
    DocumentRecord,
    GraphChunkInput,
    IngestionRunRecord,
    IngestionStatus,
    ParsedDocument,
    QdrantChunkPayload,
    ReviewItemRecord,
    ReviewStatus,
    SourceType,
)


class MetadataRepository(Protocol):
    def create_ingestion_run(self, source_path: str) -> IngestionRunRecord:
        raise NotImplementedError

    def finish_ingestion_run(
        self,
        run_id: UUID,
        status: IngestionStatus,
        documents_seen: int,
        documents_indexed: int,
        chunks_indexed: int,
        error_message: str | None = None,
    ) -> IngestionRunRecord:
        raise NotImplementedError

    def upsert_document(self, document: ParsedDocument) -> tuple[DocumentRecord, bool]:
        raise NotImplementedError

    def replace_chunks(
        self,
        document_id: UUID,
        chunks: list[ChunkCandidate],
        embedding_model: str,
    ) -> list[tuple[UUID, ChunkCandidate]]:
        raise NotImplementedError

    def get_chunk_with_document(self, chunk_id: UUID) -> dict | None:
        raise NotImplementedError

    def record_audit_log(
        self,
        actor_id: str,
        action: str,
        status: AuditStatus,
        resource_id: UUID | None = None,
        details: dict | None = None,
    ) -> AuditRecord:
        raise NotImplementedError

    def list_audit_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        action_filter: str | None = None,
        actor_filter: str | None = None,
    ) -> list[AuditRecord]:
        raise NotImplementedError

    def create_review_item(
        self,
        run_id: UUID,
        source_path: str,
        content: str,
        confidence: float,
        payload: dict | None = None,
    ) -> ReviewItemRecord:
        raise NotImplementedError

    def list_review_items(
        self,
        limit: int = 50,
        offset: int = 0,
        min_confidence: float | None = None,
        status: ReviewStatus | None = ReviewStatus.PENDING,
    ) -> list[ReviewItemRecord]:
        raise NotImplementedError

    def get_review_item(self, item_id: UUID) -> ReviewItemRecord | None:
        raise NotImplementedError

    def mark_review_item(
        self,
        item_id: UUID,
        status: ReviewStatus,
        reviewer_id: str,
        content: str | None = None,
        payload: dict | None = None,
    ) -> ReviewItemRecord:
        raise NotImplementedError

    def update_chunk_content(self, chunk_id: UUID, content: str, metadata: dict | None = None) -> None:
        raise NotImplementedError

    def list_approved_graph_chunks(self, limit: int = 100) -> list[GraphChunkInput]:
        raise NotImplementedError


class VectorIndex(Protocol):
    def upsert_chunks(self, points: list[tuple[UUID, list[float], QdrantChunkPayload]]) -> None:
        raise NotImplementedError


class DocumentLoader(Protocol):
    def load(self, source_path: str, source_type: SourceType) -> list[ParsedDocument]:
        raise NotImplementedError
