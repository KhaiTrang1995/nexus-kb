from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from nexus_shared.contracts import (
    AuditRecord,
    AuditStatus,
    ChunkCandidate,
    DocumentRecord,
    DocumentVersionRecord,
    GraphChunkInput,
    IngestionJobRecord,
    IngestionRunRecord,
    IngestionStatus,
    ParsedDocument,
    QdrantChunkPayload,
    ReviewItemRecord,
    ReviewStatus,
    SourceType,
    SyncRunRecord,
    SyncRunStatus,
    WorkspaceMemberRecord,
    WorkspaceRecord,
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

    def upsert_document(
        self,
        document: ParsedDocument,
        workspace_id: UUID | None = None,
        uploaded_by: str | None = None,
    ) -> tuple[DocumentRecord, bool]:
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

    def create_ingestion_job(
        self,
        source_path: str,
        original_filename: str,
        file_extension: str,
        uploaded_by: str,
        workspace_id: UUID,
        max_attempts: int,
        raw_content_hash: str | None = None,
        target_document_id: UUID | None = None,
        sync_run_id: UUID | None = None,
    ) -> IngestionJobRecord:
        raise NotImplementedError

    def find_indexed_job_by_raw_hash(self, raw_content_hash: str) -> IngestionJobRecord | None:
        raise NotImplementedError

    def get_ingestion_job(self, job_id: UUID) -> IngestionJobRecord | None:
        raise NotImplementedError

    def queue_position(self, job_id: UUID) -> int | None:
        raise NotImplementedError

    def claim_next_job(self) -> IngestionJobRecord | None:
        raise NotImplementedError

    def complete_job(self, job_id: UUID, document_id: UUID, run_id: UUID) -> IngestionJobRecord:
        raise NotImplementedError

    def fail_job(self, job_id: UUID, error_message: str) -> IngestionJobRecord:
        raise NotImplementedError

    def retry_job(self, job_id: UUID) -> IngestionJobRecord:
        raise NotImplementedError

    def delete_document_by_source_path(self, source_path: str) -> None:
        raise NotImplementedError

    def get_document_by_source_path(self, source_path: str) -> DocumentRecord | None:
        raise NotImplementedError

    def get_document(self, document_id: UUID) -> DocumentRecord | None:
        raise NotImplementedError

    def upsert_document_version(
        self,
        target_document_id: UUID,
        document: ParsedDocument,
        uploaded_by: str | None = None,
    ) -> tuple[DocumentRecord, bool]:
        raise NotImplementedError

    def rollback_failed_version(self, document_id: UUID) -> None:
        raise NotImplementedError

    def list_document_versions(self, document_id: UUID) -> list[DocumentVersionRecord]:
        raise NotImplementedError

    def ack_document(self, document_id: UUID, actor_id: str) -> tuple[DocumentRecord, list[UUID]]:
        raise NotImplementedError

    def list_documents_awaiting_ack(
        self,
        uploaded_by: str | None = None,
        workspace_ids: list[UUID] | None = None,
    ) -> list[DocumentRecord]:
        raise NotImplementedError

    def list_documents_in_workspaces(
        self, workspace_ids: list[UUID] | None, limit: int = 50
    ) -> list[DocumentRecord]:
        raise NotImplementedError

    def create_workspace(self, name: str, slug: str) -> WorkspaceRecord:
        raise NotImplementedError

    def list_workspaces(self) -> list[WorkspaceRecord]:
        raise NotImplementedError

    def get_workspace(self, workspace_id: UUID) -> WorkspaceRecord | None:
        raise NotImplementedError

    def add_workspace_member(self, workspace_id: UUID, user_id: str) -> WorkspaceMemberRecord:
        raise NotImplementedError

    def remove_workspace_member(self, workspace_id: UUID, user_id: str) -> None:
        raise NotImplementedError

    def list_workspace_members(self, workspace_id: UUID) -> list[WorkspaceMemberRecord]:
        raise NotImplementedError

    def list_workspace_ids_for_user(self, user_id: str) -> list[UUID]:
        raise NotImplementedError

    def create_sync_run(self, space_key: str, workspace_id: UUID, actor_id: str) -> SyncRunRecord:
        raise NotImplementedError

    def finish_sync_run(
        self,
        sync_run_id: UUID,
        status: SyncRunStatus,
        pages_seen: int,
        pages_indexed: int,
        error_message: str | None = None,
    ) -> SyncRunRecord:
        raise NotImplementedError

    def get_sync_run(self, sync_run_id: UUID) -> SyncRunRecord | None:
        raise NotImplementedError

    def list_sync_runs(self, workspace_id: UUID | None = None) -> list[SyncRunRecord]:
        raise NotImplementedError

    def cleanup_sync_run(self, sync_run_id: UUID) -> int:
        raise NotImplementedError


class VectorIndex(Protocol):
    def upsert_chunks(self, points: list[tuple[UUID, list[float], QdrantChunkPayload]]) -> None:
        raise NotImplementedError

    def set_payload(self, point_ids: list[UUID], payload: dict) -> None:
        raise NotImplementedError


class DocumentLoader(Protocol):
    def load(self, source_path: str, source_type: SourceType) -> list[ParsedDocument]:
        raise NotImplementedError


class DocumentConverter(Protocol):
    """Converts a rich document (pdf/docx/xlsx/pptx/...) into markdown text."""

    def convert(self, path: Path) -> str:
        raise NotImplementedError
