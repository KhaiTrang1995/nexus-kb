from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.main import app
from nexus_graph_builder import InMemoryGraphRepository
from nexus_shared.contracts import GraphBuildResult, GraphChunkInput, GraphEntityRecord, GraphRelationshipRecord
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
            patch("nexus_api.routers.graph.build_repository", return_value=MetadataRepository()),
            patch("nexus_api.routers.graph.build_graph_repository", return_value=graph_repository),
        ):
            response = TestClient(app).post(
                "/api/v1/graph/build?limit=5",
                headers={"X-User-Role": "Reviewer", "X-User-Id": "u2"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["entities"]), 2)
        self.assertEqual(payload["relationships"][0]["relationship_type"], "USES")

    def test_graph_for_chunk_endpoint_returns_context(self) -> None:
        chunk_id = uuid4()
        graph_repository = InMemoryGraphRepository()
        graph_repository.graph_for_chunk = lambda requested: GraphBuildResult(entities=[], relationships=[])  # type: ignore[method-assign]

        with patch("nexus_api.routers.graph.build_graph_repository", return_value=graph_repository):
            response = TestClient(app).get(f"/api/v1/graph/chunks/{chunk_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"entities": [], "relationships": [], "hyperedges": []})

    def test_graph_ingest_success(self) -> None:
        mock_vector_client = MagicMock()
        mock_vector_client.collection_name = "nexus_graph"
        # Deterministic embedding provider to avoid calling external APIs
        embedding_provider = DeterministicEmbeddingProvider(dimension=16)

        with (
            patch("nexus_api.routers.graph.build_graph_vector_client", return_value=mock_vector_client),
            patch("nexus_api.routers.graph.build_embedding_provider", return_value=embedding_provider),
            patch("nexus_api.routers.graph.build_repository") as mock_repo_func,
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
            patch("nexus_api.routers.graph.build_graph_vector_client", return_value=mock_vector_client),
            patch("nexus_api.routers.graph.build_embedding_provider", return_value=embedding_provider),
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

    def test_graph_view_reads_without_rebuilding(self) -> None:
        entity = GraphEntityRecord(
            id=uuid4(), name="Nexus-KB", normalized_name="nexus-kb", entity_type="TERM", confidence=0.9
        )
        relationship = GraphRelationshipRecord(
            id=uuid4(), source_entity_id=entity.id, target_entity_id=entity.id,
            relationship_type="USES", confidence=0.8,
        )
        graph_repository = MagicMock()
        graph_repository.list_entities.return_value = [entity]
        graph_repository.list_relationships_among.return_value = [relationship]

        with patch("nexus_api.routers.graph.build_graph_repository", return_value=graph_repository):
            response = TestClient(app).get("/api/v1/graph/view?limit=50&entity_type=TERM")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["entities"]), 1)
        self.assertEqual(payload["entities"][0]["name"], "Nexus-KB")
        graph_repository.list_entities.assert_called_once_with(limit=50, entity_type="TERM")

    def test_graph_entities_search(self) -> None:
        entity = GraphEntityRecord(
            id=uuid4(), name="Qdrant", normalized_name="qdrant", entity_type="TECHNOLOGY", confidence=0.95
        )
        graph_repository = MagicMock()
        graph_repository.search_entities.return_value = [entity]

        with patch("nexus_api.routers.graph.build_graph_repository", return_value=graph_repository):
            response = TestClient(app).get("/api/v1/graph/entities/search?q=qdr")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "Qdrant")

    def test_graph_entities_search_blank_query_returns_empty_without_hitting_repository(self) -> None:
        graph_repository = MagicMock()
        with patch("nexus_api.routers.graph.build_graph_repository", return_value=graph_repository):
            response = TestClient(app).get("/api/v1/graph/entities/search?q=")

        self.assertEqual(response.json(), [])
        graph_repository.search_entities.assert_not_called()

    def test_graph_entity_neighbors(self) -> None:
        entity_id = uuid4()
        entity = GraphEntityRecord(
            id=entity_id, name="Nexus-KB", normalized_name="nexus-kb", entity_type="TERM", confidence=0.9
        )
        graph_repository = MagicMock()
        graph_repository.get_entity_neighbors.return_value = ([entity], [])

        with patch("nexus_api.routers.graph.build_graph_repository", return_value=graph_repository):
            response = TestClient(app).get(f"/api/v1/graph/entities/{entity_id}/neighbors")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["entities"]), 1)

    def test_graph_entity_context_returns_source_chunks(self) -> None:
        entity_id = uuid4()
        chunk_id = uuid4()
        document_id = uuid4()
        entity = GraphEntityRecord(
            id=entity_id, name="Nexus-KB", normalized_name="nexus-kb", entity_type="TERM", confidence=0.9,
            provenance={"chunk_id": str(chunk_id)},
        )
        graph_repository = MagicMock()
        graph_repository.get_entity.return_value = entity

        repository = MagicMock()
        repository.get_chunk_with_document.return_value = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "title": "Nexus Overview",
            "source_path": "/vault/Nexus.md",
            "content": "Nexus-KB is a governed retrieval platform.",
        }

        with (
            patch("nexus_api.routers.graph.build_graph_repository", return_value=graph_repository),
            patch("nexus_api.routers.graph.build_repository", return_value=repository),
        ):
            response = TestClient(app).get(f"/api/v1/graph/entities/{entity_id}/context")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["chunks"]), 1)
        self.assertEqual(payload["chunks"][0]["document_title"], "Nexus Overview")

    def test_graph_entity_context_404_when_entity_missing(self) -> None:
        graph_repository = MagicMock()
        graph_repository.get_entity.return_value = None

        with patch("nexus_api.routers.graph.build_graph_repository", return_value=graph_repository):
            response = TestClient(app).get(f"/api/v1/graph/entities/{uuid4()}/context")

        self.assertEqual(response.status_code, 404)

    def test_graph_stats(self) -> None:
        mock_vector_client = MagicMock()
        mock_vector_client.collection_name = "nexus_graph"
        mock_collection_info = MagicMock()
        mock_collection_info.points_count = 42
        mock_vector_client.client.get_collection.return_value = mock_collection_info

        with patch("nexus_api.routers.graph.build_graph_vector_client", return_value=mock_vector_client):
            response = TestClient(app).get("/api/v1/graph/stats")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["node_count"], 42)
        self.assertIsNone(data.get("error"))


if __name__ == "__main__":
    unittest.main()
