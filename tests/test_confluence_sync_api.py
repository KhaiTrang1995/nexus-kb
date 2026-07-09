from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.main import app
from nexus_shared.contracts import SyncRunRecord, SyncRunStatus, WorkspaceRecord

ADMIN_HEADERS = {"X-User-Id": "root", "X-Is-Admin": "true"}
MEMBER_HEADERS = {"X-User-Id": "u1"}


class ConfluenceSyncApiTest(unittest.TestCase):
    def test_trigger_sync_requires_admin(self) -> None:
        response = TestClient(app).post(
            "/api/v1/confluence/sync",
            json={"space_key": "KB", "workspace_id": str(uuid4())},
            headers=MEMBER_HEADERS,
        )
        self.assertEqual(response.status_code, 403)

    def test_trigger_sync_400_when_not_configured(self) -> None:
        with patch("nexus_api.routers.confluence_sync.build_confluence_client", return_value=None):
            response = TestClient(app).post(
                "/api/v1/confluence/sync",
                json={"space_key": "KB", "workspace_id": str(uuid4())},
                headers=ADMIN_HEADERS,
            )
        self.assertEqual(response.status_code, 400)

    def test_trigger_sync_404_when_workspace_missing(self) -> None:
        repo = MagicMock()
        repo.get_workspace.return_value = None
        with (
            patch("nexus_api.routers.confluence_sync.build_confluence_client", return_value=MagicMock()),
            patch("nexus_api.routers.confluence_sync.build_repository", return_value=repo),
        ):
            response = TestClient(app).post(
                "/api/v1/confluence/sync",
                json={"space_key": "KB", "workspace_id": str(uuid4())},
                headers=ADMIN_HEADERS,
            )
        self.assertEqual(response.status_code, 404)

    def test_admin_triggers_sync_successfully(self) -> None:
        workspace_id = uuid4()
        run_id = uuid4()
        repo = MagicMock()
        repo.get_workspace.return_value = WorkspaceRecord(id=workspace_id, name="A", slug="a")

        sync_result = SyncRunRecord(
            id=run_id,
            space_key="KB",
            workspace_id=workspace_id,
            status=SyncRunStatus.COMPLETED,
            actor_id="root",
            pages_seen=3,
            pages_indexed=3,
        )
        with (
            patch("nexus_api.routers.confluence_sync.build_confluence_client", return_value=MagicMock()),
            patch("nexus_api.routers.confluence_sync.build_repository", return_value=repo),
            patch("nexus_api.routers.confluence_sync.ConfluenceSyncService") as mock_service_cls,
        ):
            mock_service_cls.return_value.sync.return_value = sync_result
            response = TestClient(app).post(
                "/api/v1/confluence/sync",
                json={"space_key": "KB", "workspace_id": str(workspace_id)},
                headers=ADMIN_HEADERS,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["pages_indexed"], 3)

    def test_list_sync_runs_requires_admin(self) -> None:
        response = TestClient(app).get("/api/v1/confluence/sync-runs", headers=MEMBER_HEADERS)
        self.assertEqual(response.status_code, 403)

    def test_admin_lists_sync_runs(self) -> None:
        repo = MagicMock()
        repo.list_sync_runs.return_value = []
        with patch("nexus_api.routers.confluence_sync.build_repository", return_value=repo):
            response = TestClient(app).get("/api/v1/confluence/sync-runs", headers=ADMIN_HEADERS)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sync_runs"], [])


if __name__ == "__main__":
    unittest.main()
