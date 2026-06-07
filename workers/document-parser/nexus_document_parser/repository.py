from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID, uuid4

from nexus_shared.contracts import ChunkCandidate, DocumentRecord, IngestionRunRecord, IngestionStatus, ParsedDocument


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


def jsonb(value: dict) -> Any:
    from psycopg.types.json import Jsonb

    return Jsonb(value)
