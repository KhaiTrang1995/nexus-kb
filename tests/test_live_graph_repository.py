from __future__ import annotations

import os
import unittest
from uuid import uuid4

from tests import _paths  # noqa: F401


@unittest.skipUnless(os.getenv("NEXUS_KB_RUN_LIVE_TESTS") == "1", "live graph tests require PostgreSQL")
class LiveGraphRepositoryTest(unittest.TestCase):
    def test_graph_builder_persists_entities_relationships_and_lookup(self) -> None:
        import psycopg

        from nexus_graph_builder import GraphBuilder, SQLAlchemyGraphRepository
        from nexus_shared.contracts import GraphChunkInput

        postgres_dsn = os.getenv("POSTGRES_DSN", "postgresql://nexus:change-me@localhost:5432/nexus_kb")
        psycopg_dsn = postgres_dsn.replace("+psycopg", "")
        with psycopg.connect(psycopg_dsn) as connection:
            connection.execute("DELETE FROM graph_relationships")
            connection.execute("DELETE FROM graph_entities")
            connection.commit()

        repository = SQLAlchemyGraphRepository(postgres_dsn)
        chunk_id = uuid4()
        document_id = uuid4()
        result = GraphBuilder(repository).build_from_chunks(
            [
                GraphChunkInput(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    content="Nexus-KB uses Qdrant.",
                    metadata={
                        "entities": ["Nexus-KB", "Qdrant"],
                        "relationships": [
                            {"source": "Nexus-KB", "target": "Qdrant", "type": "USES", "confidence": 0.9}
                        ],
                    },
                )
            ]
        )

        self.assertEqual(len(result.entities), 2)
        self.assertEqual(len(result.relationships), 1)
        relationship = result.relationships[0]
        self.assertEqual(relationship.confidence, 0.9)
        self.assertEqual(relationship.provenance["chunk_id"], str(chunk_id))
        self.assertEqual(len(repository.related_to_entity(relationship.source_entity_id)), 1)
        graph = repository.graph_for_chunk(chunk_id)
        self.assertEqual(len(graph.entities), 2)
        self.assertEqual(len(graph.relationships), 1)

    def test_metadata_repository_lists_only_approved_graph_chunks(self) -> None:
        import psycopg

        from nexus_document_parser.sqlalchemy_repository import SQLAlchemyMetadataRepository

        postgres_dsn = os.getenv("POSTGRES_DSN", "postgresql://nexus:change-me@localhost:5432/nexus_kb")
        psycopg_dsn = postgres_dsn.replace("+psycopg", "")
        direct_document = uuid4()
        direct_chunk = uuid4()
        pending_document = uuid4()
        pending_chunk = uuid4()
        run_id = uuid4()
        with psycopg.connect(psycopg_dsn) as connection:
            connection.execute("DELETE FROM review_items")
            connection.execute("DELETE FROM chunks")
            connection.execute("DELETE FROM documents")
            connection.execute("DELETE FROM ingestion_runs")
            connection.execute(
                """
                INSERT INTO ingestion_runs (id, source_path, status)
                VALUES (%s, %s, %s)
                """,
                (run_id, "synthetic", "completed"),
            )
            for document_id, source_path in [
                (direct_document, "synthetic/direct.md"),
                (pending_document, "synthetic/pending.md"),
            ]:
                connection.execute(
                    """
                    INSERT INTO documents (
                        id, source_type, source_path, file_extension, mime_type, title, content_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (document_id, "local_file", source_path, ".md", "text/markdown", "Synthetic", str(document_id).replace("-", "")),
                )
            for chunk_id, document_id, content in [
                (direct_chunk, direct_document, "Direct chunk for graph."),
                (pending_chunk, pending_document, "Pending chunk for graph."),
            ]:
                connection.execute(
                    """
                    INSERT INTO chunks (
                        id, document_id, chunk_index, content, content_hash, token_count,
                        metadata, qdrant_point_id, embedding_model
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    """,
                    (
                        chunk_id,
                        document_id,
                        0,
                        content,
                        str(chunk_id).replace("-", ""),
                        4,
                        '{"entities":["Qdrant"]}',
                        chunk_id,
                        "test",
                    ),
                )
            connection.execute(
                """
                INSERT INTO review_items (run_id, source_path, content, confidence, status, payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    run_id,
                    "synthetic/pending.md",
                    "Pending chunk for graph.",
                    0.2,
                    "PENDING",
                    f'{{"chunk_id":"{pending_chunk}"}}',
                ),
            )
            connection.commit()

        chunks = SQLAlchemyMetadataRepository(postgres_dsn).list_approved_graph_chunks(limit=10)

        self.assertEqual([chunk.chunk_id for chunk in chunks], [direct_chunk])


if __name__ == "__main__":
    unittest.main()
