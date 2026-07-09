from __future__ import annotations

import logging
from uuid import UUID

from nexus_shared.contracts import AuditStatus, IngestionResponse, IngestionStatus, QdrantChunkPayload, SourceType
from nexus_document_parser.chunker import TextChunker
from nexus_document_parser.embedding import EmbeddingProvider
from nexus_document_parser.loader import load_documents
from nexus_document_parser.ports import DocumentConverter, DocumentLoader, MetadataRepository, VectorIndex

logger = logging.getLogger(__name__)


class LocalDocumentLoader:
    def __init__(self, converter: DocumentConverter | None = None) -> None:
        self._converter = converter

    def load(self, source_path: str, source_type: SourceType):
        return load_documents(source_path, source_type, converter=self._converter)


class IngestionPipeline:
    def __init__(
        self,
        repository: MetadataRepository,
        vector_client: VectorIndex,
        embedding_provider: EmbeddingProvider,
        chunker: TextChunker | None = None,
        document_loader: DocumentLoader | None = None,
        confidence_threshold: float = 0.70,
        actor_id: str = "system:ingestion",
    ) -> None:
        self.repository = repository
        self.vector_client = vector_client
        self.embedding_provider = embedding_provider
        self.chunker = chunker or TextChunker()
        self.document_loader = document_loader or LocalDocumentLoader()
        self.confidence_threshold = confidence_threshold
        self.actor_id = actor_id

    def ingest(
        self,
        source_path: str,
        source_type: SourceType,
        target_document_id: UUID | None = None,
        workspace_id: UUID | None = None,
        uploaded_by: str | None = None,
    ) -> IngestionResponse:
        run = self.repository.create_ingestion_run(source_path)
        self._record_audit("INGEST_START", AuditStatus.SUCCESS, run.id, {"source_type": source_type.value})
        documents_seen = 0
        documents_indexed = 0
        chunks_indexed = 0
        try:
            documents = self.document_loader.load(source_path, source_type)
            documents_seen = len(documents)
            for document in documents:
                self._record_audit(
                    "DOCUMENT_READ",
                    AuditStatus.SUCCESS,
                    run.id,
                    {
                        "source_path": document.source_path,
                        "source_type": document.source_type.value,
                        "title": document.title,
                        "content_hash": document.content_hash,
                    },
                )
                if target_document_id is not None:
                    document_record, changed = self.repository.upsert_document_version(
                        target_document_id, document, uploaded_by=uploaded_by
                    )
                else:
                    document_record, changed = self.repository.upsert_document(
                        document, workspace_id=workspace_id, uploaded_by=uploaded_by
                    )
                if not changed:
                    continue

                chunks = self.chunker.chunk_document(document)
                persisted_chunks = self.repository.replace_chunks(
                    document_id=document_record.id,
                    chunks=chunks,
                    embedding_model=self.embedding_provider.model_name,
                )
                vectors = self.embedding_provider.embed([chunk.content for _, chunk in persisted_chunks])
                points = []
                for (chunk_id, chunk), vector in zip(persisted_chunks, vectors, strict=True):
                    confidence = float(chunk.metadata.get("confidence", 1.0))
                    self._record_audit(
                        "CHUNK_GENERATED",
                        AuditStatus.SUCCESS,
                        chunk_id,
                        {
                            "run_id": str(run.id),
                            "document_id": str(document_record.id),
                            "chunk_index": chunk.chunk_index,
                            "token_count": chunk.token_count,
                            "content_hash": chunk.content_hash,
                            "confidence": confidence,
                        },
                    )
                    payload = QdrantChunkPayload(
                        document_id=str(document_record.id),
                        chunk_id=str(chunk_id),
                        source_type=document.source_type.value,
                        source_path=document.source_path,
                        file_extension=document.file_extension,
                        mime_type=document.mime_type,
                        title=document.title,
                        tags=document.tags,
                        wikilinks=document.wikilinks,
                        frontmatter=document.frontmatter,
                        chunk_index=chunk.chunk_index,
                        heading_path=list(chunk.metadata.get("heading_path") or []),
                        section_title=chunk.metadata.get("section_title"),
                        workspace_id=str(document_record.workspace_id) if document_record.workspace_id else None,
                    )
                    if confidence < self.confidence_threshold:
                        self.repository.create_review_item(
                            run_id=run.id,
                            source_path=document.source_path,
                            content=chunk.content,
                            confidence=confidence,
                            payload={
                                "chunk_id": str(chunk_id),
                                "document_id": str(document_record.id),
                                "embedding_model": self.embedding_provider.model_name,
                                "chunk_metadata": chunk.metadata,
                                "qdrant_payload": payload.model_dump(),
                            },
                        )
                        continue
                    points.append((chunk_id, vector, payload))
                self.vector_client.upsert_chunks(points)
                documents_indexed += 1
                chunks_indexed += len(points)

            finished = self.repository.finish_ingestion_run(
                run.id,
                IngestionStatus.COMPLETED,
                documents_seen,
                documents_indexed,
                chunks_indexed,
            )
            response = IngestionResponse(
                run_id=finished.id,
                status=finished.status,
                documents_seen=finished.documents_seen,
                documents_indexed=finished.documents_indexed,
                chunks_indexed=finished.chunks_indexed,
                error_message=finished.error_message,
            )
            self._record_audit(
                "INGEST_FINISH",
                AuditStatus.SUCCESS,
                finished.id,
                {"documents_seen": documents_seen, "documents_indexed": documents_indexed, "chunks_indexed": chunks_indexed},
            )
            return response
        except Exception as exc:
            logger.exception("ingestion pipeline failed for source_path=%s", source_path)
            finished = self.repository.finish_ingestion_run(
                run.id,
                IngestionStatus.FAILED,
                documents_seen,
                documents_indexed,
                chunks_indexed,
                str(exc),
            )
            self._record_audit("INGEST_FINISH", AuditStatus.FAILURE, finished.id, {"error": str(exc)})
            return IngestionResponse(
                run_id=finished.id,
                status=finished.status,
                documents_seen=finished.documents_seen,
                documents_indexed=finished.documents_indexed,
                chunks_indexed=finished.chunks_indexed,
                error_message=finished.error_message,
            )

    def _record_audit(self, action: str, status: AuditStatus, resource_id: UUID, details: dict) -> None:
        self.repository.record_audit_log(
            actor_id=self.actor_id,
            action=action,
            status=status,
            resource_id=resource_id,
            details=details,
        )


def chunk_uuid_from_payload(payload: dict) -> UUID:
    return UUID(str(payload["chunk_id"]))
