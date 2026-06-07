from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.main import app


class ReviewRbacTest(unittest.TestCase):
    def test_non_reviewer_cannot_read_review_queue(self) -> None:
        client = TestClient(app)

        response = client.get("/api/v1/review/queue", headers={"X-User-Role": "Analyst"})

        self.assertEqual(response.status_code, 403)

    def test_non_reviewer_cannot_action_review_item(self) -> None:
        client = TestClient(app)

        response = client.post(
            "/api/v1/review/action",
            headers={"X-User-Role": "Analyst"},
            json={"item_id": "00000000-0000-0000-0000-000000000000", "action": "APPROVE"},
        )

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
