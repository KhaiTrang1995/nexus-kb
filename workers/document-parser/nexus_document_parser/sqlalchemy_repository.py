from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID, uuid4

from nexus_shared.contracts import (
    AuditRecord,
    AuditStatus,
    ChunkCandidate,
    DocumentRecord,
    IngestionRunRecord,
    IngestionStatus,
    ParsedDocument,
    ReviewItemRecord,
    ReviewStatus,
    GraphChunkInput,
)


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

    def update_chunk_content(self, chunk_id: UUID, content: str, metadata: dict | None = None) -> None:
        from nexus_document_parser.db_models import ChunkModel

        with self.session_scope() as session:
            model = session.get(ChunkModel, chunk_id)
            if model is None:
                raise ValueError(f"chunk not found: {chunk_id}")
            model.content = content
            if metadata is not None:
                model.metadata_ = metadata

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

    def list_approved_graph_chunks(self, limit: int = 100) -> list[GraphChunkInput]:
        from sqlalchemy import text

        with self.session_scope() as session:
            rows = session.execute(
                text(
                    """
                    SELECT
                        c.id AS chunk_id,
                        c.document_id,
                        c.content,
                        c.metadata AS chunk_metadata
                    FROM chunks c
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM review_items ri
                        WHERE ri.payload ->> 'chunk_id' = c.id::text
                          AND ri.status IN ('PENDING', 'REJECTED')
                    )
                    ORDER BY c.created_at
                    LIMIT :limit
                    """
                ),
                {"limit": max(1, min(limit, 1000))},
            ).mappings()
            chunks: list[GraphChunkInput] = []
            for row in rows:
                metadata = dict(row["chunk_metadata"] or {})
                chunks.append(
                    GraphChunkInput(
                        chunk_id=row["chunk_id"],
                        document_id=row["document_id"],
                        content=row["content"],
                        metadata=metadata,
                        confidence=float(metadata.get("confidence", 1.0)),
                    )
                )
            return chunks

    def record_audit_log(
        self,
        actor_id: str,
        action: str,
        status: AuditStatus,
        resource_id: UUID | None = None,
        details: dict | None = None,
    ) -> AuditRecord:
        from nexus_document_parser.db_models import AuditLogModel

        with self.session_scope() as session:
            model = AuditLogModel(
                actor_id=actor_id,
                action=action,
                status=status.value,
                resource_id=resource_id,
                details=details or {},
            )
            session.add(model)
            session.flush()
            return audit_record(model)

    def list_audit_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        action_filter: str | None = None,
        actor_filter: str | None = None,
    ) -> list[AuditRecord]:
        from sqlalchemy import desc, select

        from nexus_document_parser.db_models import AuditLogModel

        with self.session_scope() as session:
            statement = select(AuditLogModel)
            if action_filter:
                statement = statement.where(AuditLogModel.action == action_filter)
            if actor_filter:
                statement = statement.where(AuditLogModel.actor_id == actor_filter)
            statement = statement.order_by(desc(AuditLogModel.created_at)).limit(limit).offset(offset)
            return [audit_record(model) for model in session.execute(statement).scalars()]

    def create_review_item(
        self,
        run_id: UUID,
        source_path: str,
        content: str,
        confidence: float,
        payload: dict | None = None,
    ) -> ReviewItemRecord:
        from nexus_document_parser.db_models import ReviewItemModel

        with self.session_scope() as session:
            model = ReviewItemModel(
                run_id=run_id,
                source_path=source_path,
                content=content,
                confidence=confidence,
                status=ReviewStatus.PENDING.value,
                payload=payload or {},
            )
            session.add(model)
            session.flush()
            return review_item_record(model)

    def list_review_items(
        self,
        limit: int = 50,
        offset: int = 0,
        min_confidence: float | None = None,
        status: ReviewStatus | None = ReviewStatus.PENDING,
    ) -> list[ReviewItemRecord]:
        from sqlalchemy import select

        from nexus_document_parser.db_models import ReviewItemModel

        with self.session_scope() as session:
            statement = select(ReviewItemModel)
            if status is not None:
                statement = statement.where(ReviewItemModel.status == status.value)
            if min_confidence is not None:
                statement = statement.where(ReviewItemModel.confidence >= min_confidence)
            statement = statement.order_by(ReviewItemModel.created_at).limit(limit).offset(offset)
            return [review_item_record(model) for model in session.execute(statement).scalars()]

    def get_review_item(self, item_id: UUID) -> ReviewItemRecord | None:
        from nexus_document_parser.db_models import ReviewItemModel

        with self.session_scope() as session:
            model = session.get(ReviewItemModel, item_id)
            return None if model is None else review_item_record(model)

    def mark_review_item(
        self,
        item_id: UUID,
        status: ReviewStatus,
        reviewer_id: str,
        content: str | None = None,
        payload: dict | None = None,
    ) -> ReviewItemRecord:
        from datetime import datetime, timezone

        from nexus_document_parser.db_models import ReviewItemModel

        with self.session_scope() as session:
            model = session.get(ReviewItemModel, item_id)
            if model is None:
                raise ValueError(f"review item not found: {item_id}")
            if model.status != ReviewStatus.PENDING.value:
                raise ValueError(f"review item is already finalized: {item_id}")
            model.status = status.value
            model.reviewer_id = reviewer_id
            model.reviewed_at = datetime.now(timezone.utc)
            if content is not None:
                model.content = content
            if payload is not None:
                model.payload = payload
            session.flush()
            return review_item_record(model)


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


def audit_record(model: Any) -> AuditRecord:
    return AuditRecord(
        id=model.id,
        actor_id=model.actor_id,
        action=model.action,
        status=model.status,
        resource_id=model.resource_id,
        details=model.details or {},
        created_at=model.created_at,
    )


def review_item_record(model: Any) -> ReviewItemRecord:
    return ReviewItemRecord(
        id=model.id,
        run_id=model.run_id,
        source_path=model.source_path,
        content=model.content,
        confidence=model.confidence,
        status=model.status,
        payload=model.payload or {},
        reviewer_id=model.reviewer_id,
        reviewed_at=model.reviewed_at,
        created_at=model.created_at,
    )


def normalize_sqlalchemy_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    return dsn
