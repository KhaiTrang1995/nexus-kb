from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.main import app
from nexus_shared.contracts import SearchResponse


class SearchRouterWorkspaceScopingTest(unittest.TestCase):
    def _patched(self, service_mock):
        return (
            patch("nexus_api.routers.search.build_repository"),
            patch("nexus_api.routers.search.build_vector_client"),
            patch("nexus_api.routers.search.build_embedding_provider"),
            patch("nexus_api.routers.search.build_graph_repository"),
            patch("nexus_api.routers.search.SearchService", return_value=service_mock),
        )

    def test_member_search_is_scoped_to_their_workspaces(self) -> None:
        service = MagicMock()
        service.search.return_value = SearchResponse(query="q", results=[])
        patches = self._patched(service)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            response = TestClient(app).post(
                "/api/v1/search",
                json={"query": "hello"},
                headers={"X-User-Id": "u1", "X-Workspace-Ids": "ws-a,ws-b"},
            )

        self.assertEqual(response.status_code, 200)
        _, kwargs = service.search.call_args
        self.assertEqual(kwargs["workspace_ids"], ["ws-a", "ws-b"])
        self.assertEqual(kwargs["actor_id"], "u1")

    def test_admin_search_has_no_workspace_filter(self) -> None:
        service = MagicMock()
        service.search.return_value = SearchResponse(query="q", results=[])
        patches = self._patched(service)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            response = TestClient(app).post(
                "/api/v1/search",
                json={"query": "hello"},
                headers={"X-User-Id": "root", "X-Is-Admin": "true"},
            )

        self.assertEqual(response.status_code, 200)
        _, kwargs = service.search.call_args
        self.assertIsNone(kwargs["workspace_ids"])

    def test_no_membership_yields_empty_fail_closed_filter(self) -> None:
        service = MagicMock()
        service.search.return_value = SearchResponse(query="q", results=[])
        patches = self._patched(service)
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            response = TestClient(app).post(
                "/api/v1/search",
                json={"query": "hello"},
                headers={"X-User-Id": "u1"},
            )

        self.assertEqual(response.status_code, 200)
        _, kwargs = service.search.call_args
        self.assertEqual(kwargs["workspace_ids"], [])


if __name__ == "__main__":
    unittest.main()
