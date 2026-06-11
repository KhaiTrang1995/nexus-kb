from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.main import app
from nexus_graph_builder import InMemoryGraphRepository
from nexus_shared.contracts import GraphBuildResult, GraphChunkInput


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
        # 2 from metadata (Nexus-KB, Qdrant) + 1 DOCUMENT for the source doc (new document linking feature)
        self.assertEqual(len(payload["entities"]), 3)
        self.assertEqual(payload["relationships"][0]["relationship_type"], "USES")

    def test_graph_for_chunk_endpoint_returns_context(self) -> None:
        chunk_id = uuid4()
        graph_repository = InMemoryGraphRepository()
        graph_repository.graph_for_chunk = lambda requested: GraphBuildResult(entities=[], relationships=[])  # type: ignore[method-assign]

        with patch("nexus_api.main.build_graph_repository", return_value=graph_repository):
            response = TestClient(app).get(f"/api/v1/graph/chunks/{chunk_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"entities": [], "relationships": []})


if __name__ == "__main__":
    unittest.main()
