from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID, uuid4

from nexus_shared.contracts import (
    AuditRecord,
    AuditStatus,
    ChunkCandidate,
    DocumentRecord,
    GraphChunkInput,
    IngestionRunRecord,
    IngestionStatus,
    ParsedDocument,
    ReviewItemRecord,
    ReviewStatus,
)


class PostgresMetadataRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            yield connection

    def create_ingestion_run(self, source_path: str) -> IngestionRunRecord:
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO ingestion_runs (source_path, status)
                VALUES (%s, %s)
                RETURNING *
                """,
                (source_path, IngestionStatus.RUNNING.value),
            ).fetchone()
            connection.commit()
        return IngestionRunRecord.model_validate(row)

    def finish_ingestion_run(
        self,
        run_id: UUID,
        status: IngestionStatus,
        documents_seen: int,
        documents_indexed: int,
        chunks_indexed: int,
        error_message: str | None = None,
    ) -> IngestionRunRecord:
        with self.connection() as connection:
            row = connection.execute(
                """
                UPDATE ingestion_runs
                SET status = %s,
                    documents_seen = %s,
                    documents_indexed = %s,
                    chunks_indexed = %s,
                    error_message = %s,
                    finished_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (status.value, documents_seen, documents_indexed, chunks_indexed, error_message, run_id),
            ).fetchone()
            connection.commit()
        return IngestionRunRecord.model_validate(row)

    def upsert_document(self, document: ParsedDocument) -> tuple[DocumentRecord, bool]:
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM documents WHERE source_path = %s",
                (document.source_path,),
            ).fetchone()
            if existing and existing["content_hash"] == document.content_hash:
                return DocumentRecord.model_validate(existing), False

            row = connection.execute(
                """
                INSERT INTO documents (
                    source_type, source_path, file_extension, mime_type, title, content_hash,
                    frontmatter, tags, wikilinks
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_path)
                DO UPDATE SET
                    source_type = EXCLUDED.source_type,
                    file_extension = EXCLUDED.file_extension,
                    mime_type = EXCLUDED.mime_type,
                    title = EXCLUDED.title,
                    content_hash = EXCLUDED.content_hash,
                    frontmatter = EXCLUDED.frontmatter,
                    tags = EXCLUDED.tags,
                    wikilinks = EXCLUDED.wikilinks,
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    document.source_type.value,
                    document.source_path,
                    document.file_extension,
                    document.mime_type,
                    document.title,
                    document.content_hash,
                    jsonb(document.frontmatter),
                    document.tags,
                    document.wikilinks,
                ),
            ).fetchone()
            connection.commit()
        return DocumentRecord.model_validate(row), True

    def replace_chunks(
        self,
        document_id: UUID,
        chunks: list[ChunkCandidate],
        embedding_model: str,
    ) -> list[tuple[UUID, ChunkCandidate]]:
        with self.connection() as connection:
            connection.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
            persisted: list[tuple[UUID, ChunkCandidate]] = []
            for chunk in chunks:
                chunk_id = uuid4()
                connection.execute(
                    """
                    INSERT INTO chunks (
                        id, document_id, chunk_index, content, content_hash, token_count,
                        metadata, qdrant_point_id, embedding_model
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        chunk_id,
                        document_id,
                        chunk.chunk_index,
                        chunk.content,
                        chunk.content_hash,
                        chunk.token_count,
                        jsonb(chunk.metadata),
                        chunk_id,
                        embedding_model,
                    ),
                )
                persisted.append((chunk_id, chunk))
            connection.commit()
        return persisted

    def get_chunk_with_document(self, chunk_id: UUID) -> dict | None:
        with self.connection() as connection:
            return connection.execute(
                """
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.chunk_index,
                    c.content,
                    c.metadata AS chunk_metadata,
                    d.title,
                    d.source_path,
                    d.file_extension,
                    d.mime_type,
                    d.source_type,
                    d.tags,
                    d.wikilinks,
                    d.frontmatter
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.id = %s
                """,
                (chunk_id,),
            ).fetchone()

    def record_audit_log(
        self,
        actor_id: str,
        action: str,
        status: AuditStatus,
        resource_id: UUID | None = None,
        details: dict | None = None,
    ) -> AuditRecord:
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO audit_logs (actor_id, action, status, resource_id, details)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (actor_id, action, status.value, resource_id, jsonb(details or {})),
            ).fetchone()
            connection.commit()
        return AuditRecord.model_validate(row)

    def list_audit_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        action_filter: str | None = None,
        actor_filter: str | None = None,
    ) -> list[AuditRecord]:
        with self.connection() as connection:
            where_clauses = []
            params: list[Any] = []
            if action_filter:
                where_clauses.append("action = %s")
                params.append(action_filter)
            if actor_filter:
                where_clauses.append("actor_id = %s")
                params.append(actor_filter)
            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            params.extend([limit, offset])
            rows = connection.execute(
                f"""
                SELECT * FROM audit_logs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(params),
            ).fetchall()
        return [AuditRecord.model_validate(row) for row in rows]

    def create_review_item(
        self,
        run_id: UUID,
        source_path: str,
        content: str,
        confidence: float,
        payload: dict | None = None,
    ) -> ReviewItemRecord:
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO review_items (run_id, source_path, content, confidence, status, payload)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (run_id, source_path, content, confidence, ReviewStatus.PENDING.value, jsonb(payload or {})),
            ).fetchone()
            connection.commit()
        return ReviewItemRecord.model_validate(row)

    def list_review_items(
        self,
        limit: int = 50,
        offset: int = 0,
        min_confidence: float | None = None,
        status: ReviewStatus | None = ReviewStatus.PENDING,
    ) -> list[ReviewItemRecord]:
        with self.connection() as connection:
            where_clauses = []
            params: list[Any] = []
            if status is not None:
                where_clauses.append("status = %s")
                params.append(status.value)
            if min_confidence is not None:
                where_clauses.append("confidence >= %s")
                params.append(min_confidence)
            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            params.extend([limit, offset])
            rows = connection.execute(
                f"""
                SELECT * FROM review_items
                {where_sql}
                ORDER BY created_at
                LIMIT %s OFFSET %s
                """,
                tuple(params),
            ).fetchall()
        return [ReviewItemRecord.model_validate(row) for row in rows]

    def get_review_item(self, item_id: UUID) -> ReviewItemRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM review_items WHERE id = %s",
                (item_id,),
            ).fetchone()
        return ReviewItemRecord.model_validate(row) if row else None

    def mark_review_item(
        self,
        item_id: UUID,
        status: ReviewStatus,
        reviewer_id: str,
        content: str | None = None,
        payload: dict | None = None,
    ) -> ReviewItemRecord:
        with self.connection() as connection:
            # Guard: only pending can be marked (fetch current)
            current = connection.execute(
                "SELECT status FROM review_items WHERE id = %s",
                (item_id,),
            ).fetchone()
            if current is None:
                raise ValueError(f"review item not found: {item_id}")
            if current["status"] != ReviewStatus.PENDING.value:
                raise ValueError(f"review item is already finalized: {item_id}")
            # Build update
            sets = ["status = %s", "reviewer_id = %s", "reviewed_at = NOW()"]
            params: list[Any] = [status.value, reviewer_id]
            if content is not None:
                sets.append("content = %s")
                params.append(content)
            if payload is not None:
                sets.append("payload = %s")
                params.append(jsonb(payload))
            params.append(item_id)
            row = connection.execute(
                f"""
                UPDATE review_items
                SET {", ".join(sets)}
                WHERE id = %s
                RETURNING *
                """,
                tuple(params),
            ).fetchone()
            connection.commit()
        return ReviewItemRecord.model_validate(row)

    def update_chunk_content(self, chunk_id: UUID, content: str, metadata: dict | None = None) -> None:
        with self.connection() as connection:
            if metadata is not None:
                connection.execute(
                    "UPDATE chunks SET content = %s, metadata = %s WHERE id = %s",
                    (content, jsonb(metadata), chunk_id),
                )
            else:
                connection.execute(
                    "UPDATE chunks SET content = %s WHERE id = %s",
                    (content, chunk_id),
                )
            connection.commit()

    def list_approved_graph_chunks(self, limit: int = 100) -> list[GraphChunkInput]:
        with self.connection() as connection:
            rows = connection.execute(
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
                LIMIT %s
                """,
                (max(1, min(limit, 1000)),),
            ).fetchall()
            chunks: list[GraphChunkInput] = []
            for row in rows:
                metadata = dict(row.get("chunk_metadata") or {})
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


def jsonb(value: dict) -> Any:
    from psycopg.types.json import Jsonb

    return Jsonb(value)
