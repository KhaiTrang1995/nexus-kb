from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID, uuid4

from nexus_shared.contracts import ChunkCandidate, DocumentRecord, IngestionRunRecord, IngestionStatus, ParsedDocument


class SQLAlchemyMetadataRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = normalize_sqlalchemy_dsn(dsn)

    @contextmanager
    def session_scope(self) -> Iterator[Any]:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(self.dsn)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            engine.dispose()

    def create_ingestion_run(self, source_path: str) -> IngestionRunRecord:
        from nexus_document_parser.db_models import IngestionRunModel

        with self.session_scope() as session:
            model = IngestionRunModel(source_path=source_path, status=IngestionStatus.RUNNING.value)
            session.add(model)
            session.flush()
            return ingestion_run_record(model)

    def finish_ingestion_run(
        self,
        run_id: UUID,
        status: IngestionStatus,
        documents_seen: int,
        documents_indexed: int,
        chunks_indexed: int,
        error_message: str | None = None,
    ) -> IngestionRunRecord:
        from datetime import datetime, timezone

        from nexus_document_parser.db_models import IngestionRunModel

        with self.session_scope() as session:
            model = session.get(IngestionRunModel, run_id)
            if model is None:
                raise ValueError(f"ingestion run not found: {run_id}")
            model.status = status.value
            model.documents_seen = documents_seen
            model.documents_indexed = documents_indexed
            model.chunks_indexed = chunks_indexed
            model.error_message = error_message
            model.finished_at = datetime.now(timezone.utc)
            session.flush()
            return ingestion_run_record(model)

    def upsert_document(self, document: ParsedDocument) -> tuple[DocumentRecord, bool]:
        from sqlalchemy import select

        from nexus_document_parser.db_models import DocumentModel

        with self.session_scope() as session:
            model = session.execute(
                select(DocumentModel).where(DocumentModel.source_path == document.source_path)
            ).scalar_one_or_none()
            if model is not None and model.content_hash == document.content_hash:
                return document_record(model), False

            if model is None:
                model = DocumentModel(source_path=document.source_path)
                session.add(model)

            model.source_type = document.source_type.value
            model.file_extension = document.file_extension
            model.mime_type = document.mime_type
            model.title = document.title
            model.content_hash = document.content_hash
            model.frontmatter = document.frontmatter
            model.tags = document.tags
            model.wikilinks = document.wikilinks
            session.flush()
            return document_record(model), True

    def replace_chunks(
        self,
        document_id: UUID,
        chunks: list[ChunkCandidate],
        embedding_model: str,
    ) -> list[tuple[UUID, ChunkCandidate]]:
        from sqlalchemy import delete

        from nexus_document_parser.db_models import ChunkModel

        with self.session_scope() as session:
            session.execute(delete(ChunkModel).where(ChunkModel.document_id == document_id))
            persisted: list[tuple[UUID, ChunkCandidate]] = []
            for chunk in chunks:
                chunk_id = uuid4()
                model = ChunkModel(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
                    token_count=chunk.token_count,
                    metadata_=chunk.metadata,
                    qdrant_point_id=chunk_id,
                    embedding_model=embedding_model,
                )
                session.add(model)
                persisted.append((chunk_id, chunk))
            session.flush()
            return persisted

    def get_chunk_with_document(self, chunk_id: UUID) -> dict | None:
        from sqlalchemy import select

        from nexus_document_parser.db_models import ChunkModel, DocumentModel

        with self.session_scope() as session:
            row = session.execute(
                select(ChunkModel, DocumentModel)
                .join(DocumentModel, DocumentModel.id == ChunkModel.document_id)
                .where(ChunkModel.id == chunk_id)
            ).one_or_none()
            if row is None:
                return None
            chunk, document = row
            return {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "chunk_metadata": chunk.metadata_ or {},
                "title": document.title,
                "source_path": document.source_path,
                "file_extension": document.file_extension,
                "mime_type": document.mime_type,
                "source_type": document.source_type,
                "tags": document.tags,
                "wikilinks": document.wikilinks,
                "frontmatter": document.frontmatter,
            }


def document_record(model: Any) -> DocumentRecord:
    return DocumentRecord(
        id=model.id,
        source_type=model.source_type,
        source_path=model.source_path,
        file_extension=model.file_extension,
        mime_type=model.mime_type,
        title=model.title,
        content_hash=model.content_hash,
        frontmatter=model.frontmatter or {},
        tags=list(model.tags or []),
        wikilinks=list(model.wikilinks or []),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def ingestion_run_record(model: Any) -> IngestionRunRecord:
    return IngestionRunRecord(
        id=model.id,
        source_path=model.source_path,
        status=model.status,
        documents_seen=model.documents_seen,
        documents_indexed=model.documents_indexed,
        chunks_indexed=model.chunks_indexed,
        error_message=model.error_message,
        started_at=model.started_at,
        finished_at=model.finished_at,
    )


def normalize_sqlalchemy_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    return dsn
