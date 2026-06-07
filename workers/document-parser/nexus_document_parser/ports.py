from __future__ import annotations

from typing import Protocol
from uuid import UUID

from nexus_shared.contracts import ChunkCandidate, DocumentRecord, IngestionRunRecord, IngestionStatus, ParsedDocument, QdrantChunkPayload, SourceType


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


class VectorIndex(Protocol):
    def upsert_chunks(self, points: list[tuple[UUID, list[float], QdrantChunkPayload]]) -> None:
        raise NotImplementedError


class DocumentLoader(Protocol):
    def load(self, source_path: str, source_type: SourceType) -> list[ParsedDocument]:
        raise NotImplementedError
