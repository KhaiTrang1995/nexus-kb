from __future__ import annotations

import logging
from uuid import UUID

from nexus_shared.contracts import IngestionResponse, IngestionStatus, QdrantChunkPayload, SourceType
from nexus_document_parser.chunker import TextChunker
from nexus_document_parser.embedding import EmbeddingProvider
from nexus_document_parser.loader import load_documents
from nexus_document_parser.ports import DocumentLoader, MetadataRepository, VectorIndex

logger = logging.getLogger(__name__)


class LocalDocumentLoader:
    def load(self, source_path: str, source_type: SourceType):
        return load_documents(source_path, source_type)


class IngestionPipeline:
    def __init__(
        self,
        repository: MetadataRepository,
        vector_client: VectorIndex,
        embedding_provider: EmbeddingProvider,
        chunker: TextChunker | None = None,
        document_loader: DocumentLoader | None = None,
    ) -> None:
        self.repository = repository
        self.vector_client = vector_client
        self.embedding_provider = embedding_provider
        self.chunker = chunker or TextChunker()
        self.document_loader = document_loader or LocalDocumentLoader()

    def ingest(self, source_path: str, source_type: SourceType) -> IngestionResponse:
        run = self.repository.create_ingestion_run(source_path)
        documents_seen = 0
        documents_indexed = 0
        chunks_indexed = 0
        try:
            documents = self.document_loader.load(source_path, source_type)
            documents_seen = len(documents)
            for document in documents:
                document_record, changed = self.repository.upsert_document(document)
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
                    )
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
            return IngestionResponse(
                run_id=finished.id,
                status=finished.status,
                documents_seen=finished.documents_seen,
                documents_indexed=finished.documents_indexed,
                chunks_indexed=finished.chunks_indexed,
                error_message=finished.error_message,
            )
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
            return IngestionResponse(
                run_id=finished.id,
                status=finished.status,
                documents_seen=finished.documents_seen,
                documents_indexed=finished.documents_indexed,
                chunks_indexed=finished.chunks_indexed,
                error_message=finished.error_message,
            )


def chunk_uuid_from_payload(payload: dict) -> UUID:
    return UUID(str(payload["chunk_id"]))
