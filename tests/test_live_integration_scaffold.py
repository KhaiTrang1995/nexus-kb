from __future__ import annotations

import os
import unittest
from pathlib import Path

from tests import _paths  # noqa: F401


@unittest.skipUnless(os.getenv("NEXUS_KB_RUN_LIVE_TESTS") == "1", "live service tests require Docker services")
class LiveIntegrationScaffoldTest(unittest.TestCase):
    def test_postgres_and_qdrant_are_reachable(self) -> None:
        import psycopg
        from qdrant_client import QdrantClient

        postgres_dsn = os.getenv("POSTGRES_DSN", "postgresql://nexus:change-me@localhost:5432/nexus_kb")
        psycopg_dsn = postgres_dsn.replace("+psycopg", "")
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_HTTP_PORT", "6333"))

        with psycopg.connect(psycopg_dsn) as connection:
            value = connection.execute("SELECT 1").fetchone()[0]
        collections = QdrantClient(host=qdrant_host, port=qdrant_port).get_collections()

        self.assertEqual(value, 1)
        self.assertIsNotNone(collections.collections)

    def test_live_ingestion_and_search_path(self) -> None:
        import psycopg
        from qdrant_client import QdrantClient

        from nexus_api.search import SearchService
        from nexus_document_parser.chunker import TextChunker
        from nexus_document_parser.embedding import DeterministicEmbeddingProvider
        from nexus_document_parser.pipeline import IngestionPipeline
        from nexus_document_parser.sqlalchemy_repository import SQLAlchemyMetadataRepository
        from nexus_shared.contracts import IngestionStatus, SearchRequest, SourceType
        from nexus_vector.client import NexusVectorClient

        postgres_dsn = os.getenv("POSTGRES_DSN", "postgresql://nexus:change-me@localhost:5432/nexus_kb")
        psycopg_dsn = postgres_dsn.replace("+psycopg", "")
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_HTTP_PORT", "6333"))
        collection_name = "nexus_chunks_live_test"
        fixture = (Path(__file__).parent / "fixtures" / "pipeline").resolve()
        source_path = str((fixture / "Note.md").resolve())

        with psycopg.connect(psycopg_dsn) as connection:
            connection.execute("DELETE FROM documents WHERE source_path = %s", (source_path,))
            connection.commit()

        raw_qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)
        existing = {collection.name for collection in raw_qdrant.get_collections().collections}
        if collection_name in existing:
            raw_qdrant.delete_collection(collection_name)

        embedding_provider = DeterministicEmbeddingProvider(dimension=8)
        repository = SQLAlchemyMetadataRepository(postgres_dsn)
        vector_client = NexusVectorClient(
            host=qdrant_host,
            port=qdrant_port,
            collection_name=collection_name,
            vector_size=8,
        )
        pipeline = IngestionPipeline(
            repository=repository,
            vector_client=vector_client,
            embedding_provider=embedding_provider,
            chunker=TextChunker(max_chars=200, overlap_chars=20),
        )

        ingestion = pipeline.ingest(str(fixture), SourceType.OBSIDIAN)
        search = SearchService(repository, vector_client, embedding_provider).search(
            SearchRequest(query="rag graph", tags=["rag"], source_type=SourceType.OBSIDIAN)
        )

        self.assertEqual(ingestion.status, IngestionStatus.COMPLETED)
        self.assertEqual(ingestion.documents_indexed, 1)
        self.assertEqual(ingestion.chunks_indexed, 1)
        self.assertEqual(len(search.results), 1)
        self.assertEqual(search.results[0].tags, ["rag"])
        self.assertEqual(search.results[0].wikilinks, ["Graph"])
        self.assertEqual(search.results[0].heading_path, ["RAG", "Retrieval"])
        self.assertEqual(search.results[0].section_title, "Retrieval")


if __name__ == "__main__":
    unittest.main()
