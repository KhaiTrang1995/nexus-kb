from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID, uuid4

from nexus_shared.contracts import (
    AuditRecord,
    AuditStatus,
    ChunkCandidate,
    DocumentRecord,
    DocumentVersionRecord,
    IngestionJobRecord,
    IngestionRunRecord,
    IngestionStatus,
    JobStatus,
    ParsedDocument,
    ReviewItemRecord,
    ReviewStatus,
    GraphChunkInput,
    SyncRunRecord,
    SyncRunStatus,
    WorkspaceMemberRecord,
    WorkspaceRecord,
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

    def upsert_document(
        self,
        document: ParsedDocument,
        workspace_id: UUID | None = None,
        uploaded_by: str | None = None,
    ) -> tuple[DocumentRecord, bool]:
        from sqlalchemy import select

        from nexus_document_parser.db_models import DocumentModel

        with self.session_scope() as session:
            model = session.execute(
                select(DocumentModel).where(DocumentModel.source_path == document.source_path)
            ).scalar_one_or_none()
            if model is not None and model.content_hash == document.content_hash:
                return document_record(model), False

            if model is None:
                model = DocumentModel(source_path=document.source_path, workspace_id=workspace_id)
                session.add(model)

            model.source_type = document.source_type.value
            model.file_extension = document.file_extension
            model.mime_type = document.mime_type
            model.title = document.title
            model.content_hash = document.content_hash
            model.frontmatter = document.frontmatter
            model.tags = document.tags
            model.wikilinks = document.wikilinks
            # New or changed content always needs a fresh read-ack, even on
            # re-scan of an already-published document.
            model.uploaded_by = uploaded_by
            model.acked_by = None
            model.acked_at = None
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
                "document_version": document.current_version,
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
                        c.metadata AS chunk_metadata,
                        d.wikilinks AS document_wikilinks,
                        d.title AS document_title
                    FROM chunks c
                    JOIN documents d ON d.id = c.document_id
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
                # Ensure title in metadata for downstream (graph linking source name)
                if "title" not in metadata and row.get("document_title"):
                    metadata["title"] = row["document_title"]
                wikilinks = list(row.get("document_wikilinks") or [])
                chunks.append(
                    GraphChunkInput(
                        chunk_id=row["chunk_id"],
                        document_id=row["document_id"],
                        content=row["content"],
                        metadata=metadata,
                        confidence=float(metadata.get("confidence", 1.0)),
                        wikilinks=wikilinks,
                    )
                )
            return chunks

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
        from nexus_document_parser.db_models import IngestionJobModel

        with self.session_scope() as session:
            model = IngestionJobModel(
                source_path=source_path,
                original_filename=original_filename,
                file_extension=file_extension,
                uploaded_by=uploaded_by,
                workspace_id=workspace_id,
                status=JobStatus.QUEUED.value,
                max_attempts=max_attempts,
                raw_content_hash=raw_content_hash,
                target_document_id=target_document_id,
                sync_run_id=sync_run_id,
            )
            session.add(model)
            session.flush()
            return ingestion_job_record(model)

    def find_indexed_job_by_raw_hash(self, raw_content_hash: str) -> IngestionJobRecord | None:
        from sqlalchemy import desc, select

        from nexus_document_parser.db_models import IngestionJobModel

        with self.session_scope() as session:
            model = session.execute(
                select(IngestionJobModel)
                .where(
                    IngestionJobModel.raw_content_hash == raw_content_hash,
                    IngestionJobModel.status == JobStatus.INDEXED.value,
                )
                .order_by(desc(IngestionJobModel.finished_at))
                .limit(1)
            ).scalar_one_or_none()
            return None if model is None else ingestion_job_record(model)

    def get_ingestion_job(self, job_id: UUID) -> IngestionJobRecord | None:
        from nexus_document_parser.db_models import IngestionJobModel

        with self.session_scope() as session:
            model = session.get(IngestionJobModel, job_id)
            return None if model is None else ingestion_job_record(model)

    def queue_position(self, job_id: UUID) -> int | None:
        from sqlalchemy import func, select

        from nexus_document_parser.db_models import IngestionJobModel

        with self.session_scope() as session:
            job = session.get(IngestionJobModel, job_id)
            if job is None or job.status != JobStatus.QUEUED.value:
                return None
            ahead = session.execute(
                select(func.count())
                .select_from(IngestionJobModel)
                .where(
                    IngestionJobModel.status == JobStatus.QUEUED.value,
                    IngestionJobModel.queued_at <= job.queued_at,
                    IngestionJobModel.id != job.id,
                )
            ).scalar_one()
            return int(ahead) + 1

    def claim_next_job(self) -> IngestionJobRecord | None:
        from datetime import datetime, timezone

        from sqlalchemy import select

        from nexus_document_parser.db_models import IngestionJobModel

        with self.session_scope() as session:
            model = session.execute(
                select(IngestionJobModel)
                .where(IngestionJobModel.status == JobStatus.QUEUED.value)
                .order_by(IngestionJobModel.queued_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).scalar_one_or_none()
            if model is None:
                return None
            model.status = JobStatus.EXTRACTING.value
            model.attempt += 1
            model.started_at = datetime.now(timezone.utc)
            session.flush()
            return ingestion_job_record(model)

    def complete_job(self, job_id: UUID, document_id: UUID, run_id: UUID) -> IngestionJobRecord:
        from datetime import datetime, timezone

        from nexus_document_parser.db_models import IngestionJobModel

        with self.session_scope() as session:
            model = session.get(IngestionJobModel, job_id)
            if model is None:
                raise ValueError(f"ingestion job not found: {job_id}")
            model.status = JobStatus.INDEXED.value
            model.document_id = document_id
            model.run_id = run_id
            model.error_message = None
            model.finished_at = datetime.now(timezone.utc)
            session.flush()
            return ingestion_job_record(model)

    def fail_job(self, job_id: UUID, error_message: str) -> IngestionJobRecord:
        from datetime import datetime, timezone

        from nexus_document_parser.db_models import IngestionJobModel

        with self.session_scope() as session:
            model = session.get(IngestionJobModel, job_id)
            if model is None:
                raise ValueError(f"ingestion job not found: {job_id}")
            model.error_message = error_message
            if model.attempt < model.max_attempts:
                model.status = JobStatus.QUEUED.value
                model.started_at = None
            else:
                model.status = JobStatus.FAILED.value
                model.finished_at = datetime.now(timezone.utc)
            session.flush()
            return ingestion_job_record(model)

    def retry_job(self, job_id: UUID) -> IngestionJobRecord:
        from datetime import datetime, timezone

        from nexus_document_parser.db_models import IngestionJobModel

        with self.session_scope() as session:
            model = session.get(IngestionJobModel, job_id)
            if model is None:
                raise ValueError(f"ingestion job not found: {job_id}")
            if model.status != JobStatus.FAILED.value:
                raise ValueError(f"only failed jobs can be retried: {job_id}")
            model.status = JobStatus.QUEUED.value
            model.attempt = 0
            model.error_message = None
            model.started_at = None
            model.finished_at = None
            model.queued_at = datetime.now(timezone.utc)
            session.flush()
            return ingestion_job_record(model)

    def delete_document_by_source_path(self, source_path: str) -> None:
        from sqlalchemy import delete

        from nexus_document_parser.db_models import DocumentModel

        with self.session_scope() as session:
            session.execute(delete(DocumentModel).where(DocumentModel.source_path == source_path))

    def get_document_by_source_path(self, source_path: str) -> DocumentRecord | None:
        from sqlalchemy import select

        from nexus_document_parser.db_models import DocumentModel

        with self.session_scope() as session:
            model = session.execute(
                select(DocumentModel).where(DocumentModel.source_path == source_path)
            ).scalar_one_or_none()
            return None if model is None else document_record(model)

    def get_document(self, document_id: UUID) -> DocumentRecord | None:
        from nexus_document_parser.db_models import DocumentModel

        with self.session_scope() as session:
            model = session.get(DocumentModel, document_id)
            return None if model is None else document_record(model)

    def upsert_document_version(
        self,
        target_document_id: UUID,
        document: ParsedDocument,
        uploaded_by: str | None = None,
    ) -> tuple[DocumentRecord, bool]:
        from nexus_document_parser.db_models import DocumentModel, DocumentVersionModel

        with self.session_scope() as session:
            model = session.get(DocumentModel, target_document_id)
            if model is None:
                raise ValueError(f"document not found: {target_document_id}")

            snapshot = DocumentVersionModel(
                document_id=model.id,
                version_number=model.current_version,
                title=model.title,
                content_hash=model.content_hash,
                file_extension=model.file_extension,
                mime_type=model.mime_type,
                source_path=model.source_path,
                uploaded_by=model.uploaded_by,
                acked_by=model.acked_by,
                acked_at=model.acked_at,
            )
            session.add(snapshot)

            model.source_type = document.source_type.value
            model.source_path = document.source_path
            model.file_extension = document.file_extension
            model.mime_type = document.mime_type
            model.title = document.title
            model.content_hash = document.content_hash
            model.frontmatter = document.frontmatter
            model.tags = document.tags
            model.wikilinks = document.wikilinks
            model.current_version += 1
            # A new version is unread until someone acks it again, regardless
            # of whether the previous version was already published.
            model.uploaded_by = uploaded_by
            model.acked_by = None
            model.acked_at = None
            session.flush()
            return document_record(model), True

    def rollback_failed_version(self, document_id: UUID) -> None:
        from sqlalchemy import delete, select

        from nexus_document_parser.db_models import DocumentModel, DocumentVersionModel

        with self.session_scope() as session:
            model = session.get(DocumentModel, document_id)
            if model is None or model.current_version <= 1:
                return
            snapshot = session.execute(
                select(DocumentVersionModel).where(
                    DocumentVersionModel.document_id == document_id,
                    DocumentVersionModel.version_number == model.current_version - 1,
                )
            ).scalar_one_or_none()
            if snapshot is None:
                return

            model.title = snapshot.title
            model.content_hash = snapshot.content_hash
            model.file_extension = snapshot.file_extension
            model.mime_type = snapshot.mime_type
            model.source_path = snapshot.source_path
            model.current_version = snapshot.version_number
            model.uploaded_by = snapshot.uploaded_by
            model.acked_by = snapshot.acked_by
            model.acked_at = snapshot.acked_at
            session.execute(delete(DocumentVersionModel).where(DocumentVersionModel.id == snapshot.id))

    def list_document_versions(self, document_id: UUID) -> list[DocumentVersionRecord]:
        from sqlalchemy import select

        from nexus_document_parser.db_models import DocumentModel, DocumentVersionModel

        with self.session_scope() as session:
            document = session.get(DocumentModel, document_id)
            if document is None:
                return []

            records = [
                DocumentVersionRecord(
                    document_id=document.id,
                    workspace_id=document.workspace_id,
                    version_number=document.current_version,
                    title=document.title,
                    content_hash=document.content_hash,
                    file_extension=document.file_extension,
                    mime_type=document.mime_type,
                    source_path=document.source_path,
                    uploaded_by=document.uploaded_by,
                    acked_by=document.acked_by,
                    acked_at=document.acked_at,
                    is_current=True,
                    created_at=document.updated_at,
                )
            ]
            snapshots = session.execute(
                select(DocumentVersionModel)
                .where(DocumentVersionModel.document_id == document_id)
                .order_by(DocumentVersionModel.version_number.desc())
            ).scalars()
            for snapshot in snapshots:
                records.append(
                    DocumentVersionRecord(
                        document_id=snapshot.document_id,
                        workspace_id=document.workspace_id,
                        version_number=snapshot.version_number,
                        title=snapshot.title,
                        content_hash=snapshot.content_hash,
                        file_extension=snapshot.file_extension,
                        mime_type=snapshot.mime_type,
                        source_path=snapshot.source_path,
                        uploaded_by=snapshot.uploaded_by,
                        acked_by=snapshot.acked_by,
                        acked_at=snapshot.acked_at,
                        is_current=False,
                        created_at=snapshot.created_at,
                    )
                )
            return records

    def ack_document(self, document_id: UUID, actor_id: str) -> tuple[DocumentRecord, list[UUID]]:
        from datetime import datetime, timezone

        from sqlalchemy import select

        from nexus_document_parser.db_models import ChunkModel, DocumentModel

        with self.session_scope() as session:
            model = session.get(DocumentModel, document_id)
            if model is None:
                raise ValueError(f"document not found: {document_id}")
            if model.acked_at is not None:
                raise ValueError(f"document already acknowledged: {document_id}")
            model.acked_by = actor_id
            model.acked_at = datetime.now(timezone.utc)
            session.flush()
            chunk_ids = list(
                session.execute(
                    select(ChunkModel.qdrant_point_id).where(ChunkModel.document_id == document_id)
                ).scalars()
            )
            return document_record(model), chunk_ids

    def list_documents_awaiting_ack(
        self,
        uploaded_by: str | None = None,
        workspace_ids: list[UUID] | None = None,
    ) -> list[DocumentRecord]:
        from sqlalchemy import select

        from nexus_document_parser.db_models import DocumentModel

        with self.session_scope() as session:
            statement = select(DocumentModel).where(DocumentModel.acked_at.is_(None))
            if uploaded_by is not None:
                statement = statement.where(DocumentModel.uploaded_by == uploaded_by)
            if workspace_ids is not None:
                statement = statement.where(DocumentModel.workspace_id.in_(workspace_ids))
            statement = statement.order_by(DocumentModel.updated_at)
            return [document_record(model) for model in session.execute(statement).scalars()]

    def list_documents_in_workspaces(
        self, workspace_ids: list[UUID] | None, limit: int = 50
    ) -> list[DocumentRecord]:
        from sqlalchemy import desc, select

        from nexus_document_parser.db_models import DocumentModel

        with self.session_scope() as session:
            statement = select(DocumentModel).where(DocumentModel.acked_at.isnot(None))
            if workspace_ids is not None:
                statement = statement.where(DocumentModel.workspace_id.in_(workspace_ids))
            statement = statement.order_by(desc(DocumentModel.updated_at)).limit(max(1, min(limit, 200)))
            return [document_record(model) for model in session.execute(statement).scalars()]

    def create_workspace(self, name: str, slug: str) -> WorkspaceRecord:
        from nexus_document_parser.db_models import WorkspaceModel

        with self.session_scope() as session:
            model = WorkspaceModel(name=name, slug=slug)
            session.add(model)
            session.flush()
            return workspace_record(model)

    def list_workspaces(self) -> list[WorkspaceRecord]:
        from sqlalchemy import select

        from nexus_document_parser.db_models import WorkspaceModel

        with self.session_scope() as session:
            models = session.execute(select(WorkspaceModel).order_by(WorkspaceModel.name)).scalars()
            return [workspace_record(model) for model in models]

    def get_workspace(self, workspace_id: UUID) -> WorkspaceRecord | None:
        from nexus_document_parser.db_models import WorkspaceModel

        with self.session_scope() as session:
            model = session.get(WorkspaceModel, workspace_id)
            return None if model is None else workspace_record(model)

    def add_workspace_member(self, workspace_id: UUID, user_id: str) -> WorkspaceMemberRecord:
        from nexus_document_parser.db_models import WorkspaceMemberModel

        with self.session_scope() as session:
            model = session.get(WorkspaceMemberModel, (workspace_id, user_id))
            if model is None:
                model = WorkspaceMemberModel(workspace_id=workspace_id, user_id=user_id)
                session.add(model)
                session.flush()
            return workspace_member_record(model)

    def remove_workspace_member(self, workspace_id: UUID, user_id: str) -> None:
        from nexus_document_parser.db_models import WorkspaceMemberModel

        with self.session_scope() as session:
            model = session.get(WorkspaceMemberModel, (workspace_id, user_id))
            if model is not None:
                session.delete(model)

    def list_workspace_members(self, workspace_id: UUID) -> list[WorkspaceMemberRecord]:
        from sqlalchemy import select

        from nexus_document_parser.db_models import WorkspaceMemberModel

        with self.session_scope() as session:
            models = session.execute(
                select(WorkspaceMemberModel).where(WorkspaceMemberModel.workspace_id == workspace_id)
            ).scalars()
            return [workspace_member_record(model) for model in models]

    def list_workspace_ids_for_user(self, user_id: str) -> list[UUID]:
        from sqlalchemy import select

        from nexus_document_parser.db_models import WorkspaceMemberModel

        with self.session_scope() as session:
            rows = session.execute(
                select(WorkspaceMemberModel.workspace_id).where(WorkspaceMemberModel.user_id == user_id)
            ).scalars()
            return list(rows)

    def create_sync_run(self, space_key: str, workspace_id: UUID, actor_id: str) -> SyncRunRecord:
        from nexus_document_parser.db_models import SyncRunModel

        with self.session_scope() as session:
            model = SyncRunModel(
                space_key=space_key,
                workspace_id=workspace_id,
                status=SyncRunStatus.RUNNING.value,
                actor_id=actor_id,
            )
            session.add(model)
            session.flush()
            return sync_run_record(model)

    def finish_sync_run(
        self,
        sync_run_id: UUID,
        status: SyncRunStatus,
        pages_seen: int,
        pages_indexed: int,
        error_message: str | None = None,
    ) -> SyncRunRecord:
        from datetime import datetime, timezone

        from nexus_document_parser.db_models import SyncRunModel

        with self.session_scope() as session:
            model = session.get(SyncRunModel, sync_run_id)
            if model is None:
                raise ValueError(f"sync run not found: {sync_run_id}")
            model.status = status.value
            model.pages_seen = pages_seen
            model.pages_indexed = pages_indexed
            model.error_message = error_message
            model.finished_at = datetime.now(timezone.utc)
            session.flush()
            return sync_run_record(model)

    def get_sync_run(self, sync_run_id: UUID) -> SyncRunRecord | None:
        from nexus_document_parser.db_models import SyncRunModel

        with self.session_scope() as session:
            model = session.get(SyncRunModel, sync_run_id)
            return None if model is None else sync_run_record(model)

    def list_sync_runs(self, workspace_id: UUID | None = None) -> list[SyncRunRecord]:
        from sqlalchemy import desc, select

        from nexus_document_parser.db_models import SyncRunModel

        with self.session_scope() as session:
            statement = select(SyncRunModel)
            if workspace_id is not None:
                statement = statement.where(SyncRunModel.workspace_id == workspace_id)
            statement = statement.order_by(desc(SyncRunModel.started_at))
            return [sync_run_record(model) for model in session.execute(statement).scalars()]

    def cleanup_sync_run(self, sync_run_id: UUID) -> int:
        from sqlalchemy import delete, select

        from nexus_document_parser.db_models import DocumentModel, IngestionJobModel

        with self.session_scope() as session:
            jobs = session.execute(
                select(IngestionJobModel).where(IngestionJobModel.sync_run_id == sync_run_id)
            ).scalars().all()
            document_ids = [job.document_id for job in jobs if job.document_id is not None]
            for job in jobs:
                if job.status in (JobStatus.QUEUED.value, JobStatus.EXTRACTING.value):
                    job.status = JobStatus.FAILED.value
                    job.error_message = "sync run aborted: all pages from this run are being discarded"
            if document_ids:
                session.execute(delete(DocumentModel).where(DocumentModel.id.in_(document_ids)))
            session.flush()
            return len(document_ids)

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
        current_version=model.current_version,
        workspace_id=model.workspace_id,
        uploaded_by=model.uploaded_by,
        acked_by=model.acked_by,
        acked_at=model.acked_at,
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


def ingestion_job_record(model: Any) -> IngestionJobRecord:
    return IngestionJobRecord(
        id=model.id,
        source_path=model.source_path,
        original_filename=model.original_filename,
        file_extension=model.file_extension,
        uploaded_by=model.uploaded_by,
        workspace_id=model.workspace_id,
        status=model.status,
        attempt=model.attempt,
        max_attempts=model.max_attempts,
        error_message=model.error_message,
        document_id=model.document_id,
        run_id=model.run_id,
        raw_content_hash=model.raw_content_hash,
        target_document_id=model.target_document_id,
        sync_run_id=model.sync_run_id,
        queued_at=model.queued_at,
        started_at=model.started_at,
        finished_at=model.finished_at,
    )


def workspace_record(model: Any) -> WorkspaceRecord:
    return WorkspaceRecord(id=model.id, name=model.name, slug=model.slug, created_at=model.created_at)


def workspace_member_record(model: Any) -> WorkspaceMemberRecord:
    return WorkspaceMemberRecord(
        workspace_id=model.workspace_id,
        user_id=model.user_id,
        created_at=model.created_at,
    )


def sync_run_record(model: Any) -> SyncRunRecord:
    return SyncRunRecord(
        id=model.id,
        space_key=model.space_key,
        workspace_id=model.workspace_id,
        status=model.status,
        actor_id=model.actor_id,
        pages_seen=model.pages_seen,
        pages_indexed=model.pages_indexed,
        error_message=model.error_message,
        started_at=model.started_at,
        finished_at=model.finished_at,
    )


def normalize_sqlalchemy_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    return dsn
