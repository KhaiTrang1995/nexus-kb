from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.main import app
from nexus_graph_builder import InMemoryGraphRepository
from nexus_shared.contracts import GraphBuildResult, GraphChunkInput
from nexus_document_parser.embedding import DeterministicEmbeddingProvider


class GraphApiTest(unittest.TestCase):
    def test_build_graph_endpoint_uses_approved_chunks(self) -> None:
        chunk_id = uuid4()
        document_id = uuid4()

        class MetadataRepository:
            def list_approved_graph_chunks(self, limit=100):
                return [
                    GraphChunkInput(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        content="Nexus-KB uses Qdrant.",
                        metadata={
                            "entities": ["Nexus-KB", "Qdrant"],
                            "relationships": [{"source": "Nexus-KB", "target": "Qdrant", "type": "USES"}],
                        },
                    )
                ]

        graph_repository = InMemoryGraphRepository()
        with (
            patch("nexus_api.main.build_repository", return_value=MetadataRepository()),
            patch("nexus_api.main.build_graph_repository", return_value=graph_repository),
        ):
            response = TestClient(app).post("/api/v1/graph/build?limit=5")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["entities"]), 2)
        self.assertEqual(payload["relationships"][0]["relationship_type"], "USES")

    def test_graph_for_chunk_endpoint_returns_context(self) -> None:
        chunk_id = uuid4()
        graph_repository = InMemoryGraphRepository()
        graph_repository.graph_for_chunk = lambda requested: GraphBuildResult(entities=[], relationships=[])  # type: ignore[method-assign]

        with patch("nexus_api.main.build_graph_repository", return_value=graph_repository):
            response = TestClient(app).get(f"/api/v1/graph/chunks/{chunk_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"entities": [], "relationships": []})

    def test_graph_ingest_success(self) -> None:
        mock_vector_client = MagicMock()
        mock_vector_client.collection_name = "nexus_graph"
        # Deterministic embedding provider to avoid calling external APIs
        embedding_provider = DeterministicEmbeddingProvider(dimension=16)

        with (
            patch("nexus_api.main.build_graph_vector_client", return_value=mock_vector_client),
            patch("nexus_api.main.build_embedding_provider", return_value=embedding_provider),
            patch("nexus_api.main.build_repository") as mock_repo_func,
        ):
            mock_repo = MagicMock()
            mock_repo_func.return_value = mock_repo
            
            payload = {
                "text": "This is test paragraph. And this is another paragraph.",
                "source": "test_doc.txt",
                "actor_id": "service_user"
            }
            response = TestClient(app).post("/api/v1/graph/ingest", json=payload)

        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["status"], "ok")
        self.assertGreater(json_data["chunks_count"], 0)
        self.assertTrue(mock_vector_client.client.upsert.called)
        self.assertTrue(mock_repo.record_audit_log.called)

    def test_graph_ingest_unauthorized(self) -> None:
        payload = {
            "text": "Unauthorized write test.",
            "source": "test_doc.txt",
            "actor_id": "unauthorized"
        }
        response = TestClient(app).post("/api/v1/graph/ingest", json=payload)
        self.assertEqual(response.status_code, 403)

        payload_empty = {
            "text": "Unauthorized write test.",
            "source": "test_doc.txt",
            "actor_id": ""
        }
        response_empty = TestClient(app).post("/api/v1/graph/ingest", json=payload_empty)
        self.assertEqual(response_empty.status_code, 403)

    def test_graph_search_success(self) -> None:
        mock_vector_client = MagicMock()
        mock_vector_client.search.return_value = [
            {
                "id": str(uuid4()),
                "score": 0.85,
                "payload": {"text": "Found snippet content.", "source": "test_doc.txt"}
            }
        ]
        embedding_provider = DeterministicEmbeddingProvider(dimension=16)

        with (
            patch("nexus_api.main.build_graph_vector_client", return_value=mock_vector_client),
            patch("nexus_api.main.build_embedding_provider", return_value=embedding_provider),
        ):
            response = TestClient(app).get(
                "/api/v1/graph/search?q=query&limit=5",
                headers={"X-Actor-Id": "service_user"}
            )

        self.assertEqual(response.status_code, 200)
        results = response.json().get("results", [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["snippet"], "Found snippet content.")
        self.assertEqual(results[0]["source"], "test_doc.txt")
        self.assertEqual(results[0]["score"], 0.85)

    def test_graph_search_forbidden(self) -> None:
        response = TestClient(app).get("/api/v1/graph/search?q=query")
        self.assertEqual(response.status_code, 403)

        response_bad = TestClient(app).get(
            "/api/v1/graph/search?q=query",
            headers={"X-Actor-Id": "anonymous"}
        )
        self.assertEqual(response_bad.status_code, 403)

    def test_graph_stats(self) -> None:
        mock_vector_client = MagicMock()
        mock_vector_client.collection_name = "nexus_graph"
        mock_collection_info = MagicMock()
        mock_collection_info.points_count = 42
        mock_vector_client.client.get_collection.return_value = mock_collection_info

        with patch("nexus_api.main.build_graph_vector_client", return_value=mock_vector_client):
            response = TestClient(app).get("/api/v1/graph/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"node_count": 42})


if __name__ == "__main__":
    unittest.main()
