"""Integration tests for Phase 6-7 web console API contracts.

Verifies endpoints consumed by AuditView, SearchView, GraphView, and IngestionView.
Documents RBAC and response-shape mismatches between frontend expectations and backend.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.main import app
from nexus_shared.contracts import (
    AuditRecord,
    AuditStatus,
    GraphBuildResult,
    GraphEntityRecord,
    GraphRelationshipRecord,
    IngestionResponse,
    IngestionStatus,
    SourceType,
)


class AuditApiContractTest(unittest.TestCase):
    """GET /api/v1/audit — consumed by AuditView on mount."""

    def _mock_repo(self, records: list[AuditRecord]):
        repo = MagicMock()
        repo.list_audit_logs.return_value = records
        return repo

    def test_audit_returns_list_with_action_pill_fields(self) -> None:
        """Happy path: audit records include id, actor_id, action, status, details, created_at."""
        record_id = uuid4()
        records = [
            AuditRecord(
                id=record_id,
                actor_id="u2",
                action="SEARCH_QUERY",
                status=AuditStatus.SUCCESS,
                details={"query": "governed retrieval"},
                created_at=datetime.now(timezone.utc),
            ),
            AuditRecord(
                id=uuid4(),
                actor_id="pipeline",
                action="INGEST_START",
                status=AuditStatus.SUCCESS,
                details={"source_path": "/docs"},
                created_at=datetime.now(timezone.utc),
            ),
        ]
        with patch("nexus_api.routers.audit.build_repository", return_value=self._mock_repo(records)):
            response = TestClient(app).get("/api/v1/audit?limit=20&offset=0")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload, list)
        self.assertEqual(len(payload), 2)
        first = payload[0]
        self.assertIn("id", first)
        self.assertIn("actor_id", first)
        self.assertIn("action", first)
        self.assertIn("status", first)
        self.assertIn("details", first)
        self.assertEqual(first["action"], "SEARCH_QUERY")
        self.assertEqual(first["status"], "SUCCESS")

    def test_audit_supports_action_and_actor_filters(self) -> None:
        """Edge case: query params action_filter and actor_filter are forwarded to repository."""
        repo = self._mock_repo([])
        with patch("nexus_api.routers.audit.build_repository", return_value=repo):
            TestClient(app).get(
                "/api/v1/audit?limit=5&offset=10&action_filter=GRAPH_WRITE&actor_filter=u3",
                headers={"X-User-Role": "Auditor", "X-User-Id": "u3"},
            )

        repo.list_audit_logs.assert_called_once_with(
            limit=5,
            offset=10,
            action_filter="GRAPH_WRITE",
            actor_filter="u3",
        )

    def test_audit_actor_filter_requires_auditor_role(self) -> None:
        """Server-side RBAC: actor_filter restricted to Auditor role."""
        repo = self._mock_repo([])
        with patch("nexus_api.routers.audit.build_repository", return_value=repo):
            response = TestClient(app).get(
                "/api/v1/audit?actor_filter=secret-actor",
                headers={"X-User-Role": "Searcher"},
            )
        self.assertEqual(response.status_code, 403)

    def test_audit_actor_filter_allowed_for_auditor(self) -> None:
        repo = self._mock_repo([])
        with patch("nexus_api.routers.audit.build_repository", return_value=repo):
            response = TestClient(app).get(
                "/api/v1/audit?actor_filter=secret-actor",
                headers={"X-User-Role": "Auditor"},
            )
        self.assertEqual(response.status_code, 200)
        repo.list_audit_logs.assert_called_once()
        self.assertEqual(repo.list_audit_logs.call_args.kwargs["actor_filter"], "secret-actor")


class GraphBuildApiContractTest(unittest.TestCase):
    """POST /api/v1/graph/build — consumed by GraphView Build Graph button."""

    def test_graph_build_post_returns_entities_and_relationships(self) -> None:
        """Happy path: POST with limit query param returns GraphBuildResult shape."""
        entity_id = uuid4()
        target_id = uuid4()
        result = GraphBuildResult(
            entities=[
                GraphEntityRecord(
                    id=entity_id,
                    name="Nexus-KB",
                    normalized_name="nexus-kb",
                    entity_type="TERM",
                    confidence=0.9,
                    provenance={},
                ),
                GraphEntityRecord(
                    id=target_id,
                    name="Qdrant",
                    normalized_name="qdrant",
                    entity_type="TECHNOLOGY",
                    confidence=0.85,
                    provenance={},
                ),
            ],
            relationships=[
                GraphRelationshipRecord(
                    id=uuid4(),
                    source_entity_id=entity_id,
                    target_entity_id=target_id,
                    relationship_type="USES",
                    confidence=0.88,
                    provenance={},
                )
            ],
        )

        class MetadataRepository:
            def list_approved_graph_chunks(self, limit=100):
                return []

        mock_service = MagicMock()
        mock_service.build_from_approved_chunks.return_value = result

        with (
            patch("nexus_api.routers.graph.build_repository", return_value=MetadataRepository()),
            patch("nexus_api.routers.graph.build_graph_repository"),
            patch("nexus_api.routers.graph.GraphBuildService", return_value=mock_service),
        ):
            response = TestClient(app).post(
                "/api/v1/graph/build?limit=25",
                headers={"X-User-Role": "Reviewer", "X-User-Id": "u2"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["entities"]), 2)
        self.assertEqual(payload["entities"][0]["entity_type"], "TERM")
        self.assertEqual(payload["relationships"][0]["relationship_type"], "USES")
        self.assertEqual(payload.get("hyperedges", []), [])

    def test_graph_build_requires_reviewer_or_auditor_role(self) -> None:
        """Error condition: graph build rejects requests without Reviewer/Auditor role header."""
        response = TestClient(app).post("/api/v1/graph/build?limit=1")
        self.assertEqual(response.status_code, 403)

    def test_graph_build_allows_auditor_role(self) -> None:
        """Happy path: Auditor role passes RBAC for graph build."""
        mock_service = MagicMock()
        mock_service.build_from_approved_chunks.return_value = GraphBuildResult(
            entities=[], relationships=[]
        )

        class MetadataRepository:
            def list_approved_graph_chunks(self, limit=100):
                return []

        with (
            patch("nexus_api.routers.graph.build_repository", return_value=MetadataRepository()),
            patch("nexus_api.routers.graph.build_graph_repository"),
            patch("nexus_api.routers.graph.GraphBuildService", return_value=mock_service),
        ):
            response = TestClient(app).post(
                "/api/v1/graph/build?limit=1",
                headers={"X-User-Role": "Auditor", "X-User-Id": "u3"},
            )

        self.assertEqual(response.status_code, 200)

    def test_graph_build_get_not_allowed(self) -> None:
        """Error condition: GraphView uses POST; GET must fail."""
        response = TestClient(app).get("/api/v1/graph/build?limit=1")
        self.assertEqual(response.status_code, 405)


class IngestApiContractTest(unittest.TestCase):
    """POST /api/v1/ingest — consumed by IngestionView form submit."""

    def test_ingest_returns_ingestion_response_shape(self) -> None:
        """Happy path: response matches IngestionResponse contract expected by IngestionView."""
        run_id = uuid4()
        mock_result = IngestionResponse(
            run_id=run_id,
            status=IngestionStatus.COMPLETED,
            documents_seen=2,
            documents_indexed=2,
            chunks_indexed=5,
            error_message=None,
        )

        with patch("nexus_api.routers.ingest.IngestionPipeline") as mock_pipeline_cls:
            mock_pipeline_cls.return_value.ingest.return_value = mock_result
            response = TestClient(app).post(
                "/api/v1/ingest",
                json={"source_path": "/tmp/docs", "source_type": "local_file"},
                headers={"X-User-Role": "Reviewer", "X-User-Id": "u2"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["run_id"], str(run_id))
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["documents_seen"], 2)
        self.assertEqual(payload["documents_indexed"], 2)
        self.assertEqual(payload["chunks_indexed"], 5)

    def test_ingest_validates_source_type_enum(self) -> None:
        """Error condition: invalid source_type returns 422."""
        response = TestClient(app).post(
            "/api/v1/ingest",
            json={"source_path": "/tmp/docs", "source_type": "invalid"},
            headers={"X-User-Role": "Reviewer", "X-User-Id": "u2"},
        )
        self.assertEqual(response.status_code, 422)

    def test_ingest_requires_reviewer_or_auditor_role(self) -> None:
        """Error condition: ingest rejects requests without Reviewer/Auditor role header."""
        response = TestClient(app).post(
            "/api/v1/ingest",
            json={"source_path": "/tmp/docs", "source_type": "local_file"},
        )
        self.assertEqual(response.status_code, 403)


class SearchStatsContractTest(unittest.TestCase):
    """GET /api/v1/graph/stats — consumed by SearchView stats bar."""

    def test_graph_stats_returns_node_count(self) -> None:
        """Happy path: SearchView reads node_count from graph/stats."""
        mock_vector_client = MagicMock()
        mock_vector_client.collection_name = "nexus_graph"
        mock_collection_info = MagicMock()
        mock_collection_info.points_count = 128
        mock_vector_client.client.get_collection.return_value = mock_collection_info

        with patch("nexus_api.routers.graph.build_graph_vector_client", return_value=mock_vector_client):
            response = TestClient(app).get("/api/v1/graph/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["node_count"], 128)

    def test_graph_stats_semantic_is_qdrant_points_not_postgres_entities(self) -> None:
        """Contract mismatch: node_count is Qdrant nexus_graph points, not Postgres graph_entities rows."""
        mock_vector_client = MagicMock()
        mock_vector_client.collection_name = "nexus_graph"
        mock_collection_info = MagicMock()
        mock_collection_info.points_count = 7
        mock_vector_client.client.get_collection.return_value = mock_collection_info

        with patch("nexus_api.routers.graph.build_graph_vector_client", return_value=mock_vector_client):
            response = TestClient(app).get("/api/v1/graph/stats")

        self.assertEqual(mock_vector_client.collection_name, "nexus_graph")
        self.assertNotIn("entity_count", response.json())


class RbacMismatchTest(unittest.TestCase):
    """Documents frontend/backend RBAC divergence for Phase 6-7 console."""

    def test_auditor_allowed_on_review_queue(self) -> None:
        """Happy path: Auditor role passes RBAC (same privileges as Reviewer for queue)."""
        repo = MagicMock()
        repo.list_review_items.return_value = []
        with (
            patch("nexus_api.routers.review.build_repository", return_value=repo),
            patch("nexus_api.routers.review.build_vector_client"),
            patch("nexus_api.routers.review.build_embedding_provider"),
        ):
            response = TestClient(app).get(
                "/api/v1/review/queue?limit=1",
                headers={"X-User-Role": "Auditor", "X-User-Id": "u3"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_reviewer_allowed_on_review_queue_with_mock_repo(self) -> None:
        """Happy path: Reviewer role passes RBAC (queue may be empty)."""
        repo = MagicMock()
        repo.list_review_items.return_value = []
        with (
            patch("nexus_api.routers.review.build_repository", return_value=repo),
            patch("nexus_api.routers.review.build_vector_client"),
            patch("nexus_api.routers.review.build_embedding_provider"),
        ):
            response = TestClient(app).get(
                "/api/v1/review/queue?limit=1",
                headers={"X-User-Role": "Reviewer", "X-User-Id": "u2"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


if __name__ == "__main__":
    unittest.main()
