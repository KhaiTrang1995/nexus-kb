from __future__ import annotations

import unittest

from tests import _paths  # noqa: F401

from nexus_api.auth.jwt import create_token
from nexus_knowledge_mcp.auth import ActorResolutionError, InternalJwtVerifier


class InternalJwtVerifierTest(unittest.TestCase):
    def test_verifies_token_minted_by_nexus_api(self) -> None:
        token = create_token("alice", "Alice", "", is_admin=False, workspace_ids=["ws-a"])
        verifier = InternalJwtVerifier()

        actor = verifier.verify(token)

        self.assertEqual(actor.user_id, "alice")
        self.assertFalse(actor.is_admin)
        self.assertEqual(actor.workspace_ids, ["ws-a"])

    def test_admin_claim_roundtrips(self) -> None:
        token = create_token("root", "Root", "", is_admin=True, workspace_ids=[])
        verifier = InternalJwtVerifier()

        actor = verifier.verify(token)

        self.assertTrue(actor.is_admin)

    def test_invalid_token_fails_closed(self) -> None:
        verifier = InternalJwtVerifier()
        with self.assertRaises(ActorResolutionError):
            verifier.verify("not-a-real-token")

    def test_token_signed_with_different_secret_is_rejected(self) -> None:
        token = create_token("alice", "Alice", "", workspace_ids=["ws-a"])
        verifier = InternalJwtVerifier(secret="a-different-secret")

        with self.assertRaises(ActorResolutionError):
            verifier.verify(token)

    def test_missing_claims_default_to_no_access(self) -> None:
        from jose import jwt as jose_jwt

        # A token with no is_admin/workspace_ids claims at all (e.g. minted by
        # a different, older issuer) must resolve to zero access, not crash.
        verifier = InternalJwtVerifier()
        token = jose_jwt.encode({"sub": "legacy-user"}, verifier._secret, algorithm="HS256")
        actor = verifier.verify(token)

        self.assertFalse(actor.is_admin)
        self.assertEqual(actor.workspace_ids, [])


if __name__ == "__main__":
    unittest.main()
