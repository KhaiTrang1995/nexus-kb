from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.auth.dependencies import require_admin, require_workspace_access
from nexus_api.auth.jwt import create_token, decode_token
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.main import app


class JwtTokenTest(unittest.TestCase):
    def test_create_and_decode_roundtrip(self) -> None:
        token = create_token("u1", "Alice", "Reviewer")
        user = decode_token(token)
        self.assertEqual(user.id, "u1")
        self.assertEqual(user.name, "Alice")
        self.assertEqual(user.role, "Reviewer")

    def test_decode_invalid_token_raises(self) -> None:
        with self.assertRaises(Exception):
            decode_token("invalid.token.here")

    def test_decode_empty_role(self) -> None:
        token = create_token("u1", "Alice", "")
        user = decode_token(token)
        self.assertEqual(user.role, "")

    def test_token_defaults_are_fail_closed_no_admin_no_workspaces(self) -> None:
        token = create_token("u1", "Alice", "")
        user = decode_token(token)
        self.assertFalse(user.is_admin)
        self.assertEqual(user.workspace_ids, [])

    def test_workspace_and_admin_claims_roundtrip(self) -> None:
        from uuid import uuid4

        workspace_id = str(uuid4())
        token = create_token("u1", "Alice", "", is_admin=True, workspace_ids=[workspace_id])
        user = decode_token(token)
        self.assertTrue(user.is_admin)
        self.assertEqual(user.workspace_ids, [workspace_id])


class WorkspaceAccessDependencyTest(unittest.TestCase):
    def test_admin_bypasses_workspace_check(self) -> None:
        from uuid import uuid4

        user = AuthenticatedUser(id="root", name="Root", role="", is_admin=True, workspace_ids=[])
        require_workspace_access(user, uuid4())  # should not raise

    def test_member_of_workspace_is_allowed(self) -> None:
        from uuid import uuid4

        workspace_id = uuid4()
        user = AuthenticatedUser(id="u1", name="Alice", role="", workspace_ids=[str(workspace_id)])
        require_workspace_access(user, workspace_id)  # should not raise

    def test_non_member_denied_fail_closed(self) -> None:
        from uuid import uuid4

        from fastapi import HTTPException

        user = AuthenticatedUser(id="u1", name="Alice", role="", workspace_ids=[])
        with self.assertRaises(HTTPException) as ctx:
            require_workspace_access(user, uuid4())
        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_admin_denies_non_admin(self) -> None:
        from fastapi import HTTPException

        user = AuthenticatedUser(id="u1", name="Alice", role="", is_admin=False)
        with self.assertRaises(HTTPException) as ctx:
            require_admin(user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_admin_allows_admin(self) -> None:
        user = AuthenticatedUser(id="root", name="Root", role="", is_admin=True)
        self.assertIs(require_admin(user), user)


class DevTokenEndpointTest(unittest.TestCase):
    def test_dev_token_returns_jwt(self) -> None:
        response = TestClient(app).post(
            "/api/v1/auth/dev-token",
            json={"user_id": "u1", "name": "Alice", "role": "Reviewer"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("access_token", payload)
        self.assertEqual(payload["token_type"], "bearer")
        self.assertEqual(payload["user"]["id"], "u1")
        self.assertEqual(payload["user"]["name"], "Alice")
        self.assertEqual(payload["user"]["role"], "Reviewer")

        user = decode_token(payload["access_token"])
        self.assertEqual(user.id, "u1")

    def test_dev_token_disabled_in_jwt_mode(self) -> None:
        with patch.dict("os.environ", {"AUTH_MODE": "jwt"}):
            response = TestClient(app).post(
                "/api/v1/auth/dev-token",
                json={"user_id": "u1", "name": "Alice", "role": ""},
            )
        self.assertEqual(response.status_code, 404)

    def test_list_dev_users(self) -> None:
        response = TestClient(app).get("/api/v1/auth/users")
        self.assertEqual(response.status_code, 200)
        users = response.json()
        self.assertEqual(len(users), 3)
        self.assertEqual(users[0]["name"], "Alice")


class AuthHeaderIntegrationTest(unittest.TestCase):
    def test_bearer_token_accepted_on_review_queue(self) -> None:
        token = create_token("u2", "Bob", "Reviewer")
        from unittest.mock import MagicMock
        repo = MagicMock()
        repo.list_review_items.return_value = []
        with (
            patch("nexus_api.routers.review.build_repository", return_value=repo),
            patch("nexus_api.routers.review.build_vector_client"),
            patch("nexus_api.routers.review.build_embedding_provider"),
        ):
            response = TestClient(app).get(
                "/api/v1/review/queue?limit=1",
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
