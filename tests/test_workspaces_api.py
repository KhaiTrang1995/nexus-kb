from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.main import app
from nexus_shared.contracts import WorkspaceMemberRecord, WorkspaceRecord

ADMIN_HEADERS = {"X-User-Id": "root", "X-Is-Admin": "true"}
MEMBER_HEADERS = {"X-User-Id": "u1"}


class WorkspaceAdminApiTest(unittest.TestCase):
    def test_create_workspace_requires_admin(self) -> None:
        repo = MagicMock()
        with patch("nexus_api.routers.workspaces.build_repository", return_value=repo):
            response = TestClient(app).post(
                "/api/v1/workspaces",
                json={"name": "Engineering", "slug": "engineering"},
                headers=MEMBER_HEADERS,
            )

        self.assertEqual(response.status_code, 403)
        repo.create_workspace.assert_not_called()

    def test_admin_can_create_workspace_and_it_is_audited(self) -> None:
        workspace_id = uuid4()
        repo = MagicMock()
        repo.create_workspace.return_value = WorkspaceRecord(id=workspace_id, name="Engineering", slug="engineering")

        with patch("nexus_api.routers.workspaces.build_repository", return_value=repo):
            response = TestClient(app).post(
                "/api/v1/workspaces",
                json={"name": "Engineering", "slug": "engineering"},
                headers=ADMIN_HEADERS,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slug"], "engineering")
        repo.record_audit_log.assert_called_once()
        _, kwargs = repo.record_audit_log.call_args
        self.assertEqual(kwargs["action"], "WORKSPACE_CREATED")

    def test_list_workspaces_filters_to_membership_for_non_admin(self) -> None:
        workspace_a = uuid4()
        workspace_b = uuid4()
        repo = MagicMock()
        repo.list_workspaces.return_value = [
            WorkspaceRecord(id=workspace_a, name="A", slug="a"),
            WorkspaceRecord(id=workspace_b, name="B", slug="b"),
        ]

        with patch("nexus_api.routers.workspaces.build_repository", return_value=repo):
            response = TestClient(app).get(
                "/api/v1/workspaces", headers={"X-User-Id": "u1", "X-Workspace-Ids": str(workspace_a)}
            )

        payload = response.json()
        self.assertEqual(len(payload["workspaces"]), 1)
        self.assertEqual(payload["workspaces"][0]["id"], str(workspace_a))

    def test_list_workspaces_returns_all_for_admin(self) -> None:
        repo = MagicMock()
        repo.list_workspaces.return_value = [
            WorkspaceRecord(id=uuid4(), name="A", slug="a"),
            WorkspaceRecord(id=uuid4(), name="B", slug="b"),
        ]

        with patch("nexus_api.routers.workspaces.build_repository", return_value=repo):
            response = TestClient(app).get("/api/v1/workspaces", headers=ADMIN_HEADERS)

        self.assertEqual(len(response.json()["workspaces"]), 2)

    def test_add_member_requires_admin(self) -> None:
        repo = MagicMock()
        with patch("nexus_api.routers.workspaces.build_repository", return_value=repo):
            response = TestClient(app).post(
                f"/api/v1/workspaces/{uuid4()}/members",
                json={"user_id": "u2"},
                headers=MEMBER_HEADERS,
            )

        self.assertEqual(response.status_code, 403)
        repo.add_workspace_member.assert_not_called()

    def test_add_member_404_when_workspace_missing(self) -> None:
        repo = MagicMock()
        repo.get_workspace.return_value = None
        with patch("nexus_api.routers.workspaces.build_repository", return_value=repo):
            response = TestClient(app).post(
                f"/api/v1/workspaces/{uuid4()}/members",
                json={"user_id": "u2"},
                headers=ADMIN_HEADERS,
            )

        self.assertEqual(response.status_code, 404)

    def test_admin_adds_member_and_it_is_audited(self) -> None:
        workspace_id = uuid4()
        repo = MagicMock()
        repo.get_workspace.return_value = WorkspaceRecord(id=workspace_id, name="A", slug="a")
        repo.add_workspace_member.return_value = WorkspaceMemberRecord(workspace_id=workspace_id, user_id="u2")

        with patch("nexus_api.routers.workspaces.build_repository", return_value=repo):
            response = TestClient(app).post(
                f"/api/v1/workspaces/{workspace_id}/members",
                json={"user_id": "u2"},
                headers=ADMIN_HEADERS,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], "u2")
        repo.record_audit_log.assert_called_once()

    def test_remove_member_requires_admin(self) -> None:
        repo = MagicMock()
        with patch("nexus_api.routers.workspaces.build_repository", return_value=repo):
            response = TestClient(app).delete(
                f"/api/v1/workspaces/{uuid4()}/members/u2", headers=MEMBER_HEADERS
            )

        self.assertEqual(response.status_code, 403)
        repo.remove_workspace_member.assert_not_called()

    def test_member_cannot_list_members_of_another_workspace(self) -> None:
        workspace_id = uuid4()
        repo = MagicMock()
        with patch("nexus_api.routers.workspaces.build_repository", return_value=repo):
            response = TestClient(app).get(
                f"/api/v1/workspaces/{workspace_id}/members",
                headers={"X-User-Id": "u1", "X-Workspace-Ids": str(uuid4())},
            )

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
