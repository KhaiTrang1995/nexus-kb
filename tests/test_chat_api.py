from __future__ import annotations

import contextlib
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.main import app
from nexus_shared.contracts import ChatResponse


class ChatApiTest(unittest.TestCase):
    @contextlib.contextmanager
    def _patched_dependencies(self):
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("nexus_api.routers.chat.build_repository"))
            stack.enter_context(patch("nexus_api.routers.chat.build_vector_client"))
            stack.enter_context(patch("nexus_api.routers.chat.build_embedding_provider"))
            stack.enter_context(patch("nexus_api.routers.chat.build_graph_repository"))
            stack.enter_context(patch("nexus_api.routers.chat.build_llm_gateway"))
            stack.enter_context(patch("nexus_api.routers.chat.SearchService"))
            mock_rag_cls = stack.enter_context(patch("nexus_api.routers.chat.RagService"))
            yield mock_rag_cls

    def test_chat_returns_answer_and_citations(self) -> None:
        with self._patched_dependencies() as mock_rag_cls:
            mock_rag_cls.return_value.ask.return_value = ChatResponse(answer="42", citations=[])
            response = TestClient(app).post(
                "/api/v1/chat", json={"query": "hello"}, headers={"X-User-Id": "u1"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "42")

    def test_chat_passes_workspace_scope_from_token(self) -> None:
        with self._patched_dependencies() as mock_rag_cls:
            mock_rag_cls.return_value.ask.return_value = ChatResponse(answer="ok", citations=[])
            TestClient(app).post(
                "/api/v1/chat",
                json={"query": "hello"},
                headers={"X-User-Id": "u1", "X-Workspace-Ids": "ws-a,ws-b"},
            )
            _, kwargs = mock_rag_cls.return_value.ask.call_args
            self.assertEqual(kwargs["workspace_ids"], ["ws-a", "ws-b"])
            self.assertEqual(kwargs["actor_id"], "u1")

    def test_chat_admin_has_no_workspace_filter(self) -> None:
        with self._patched_dependencies() as mock_rag_cls:
            mock_rag_cls.return_value.ask.return_value = ChatResponse(answer="ok", citations=[])
            TestClient(app).post(
                "/api/v1/chat", json={"query": "hello"}, headers={"X-User-Id": "root", "X-Is-Admin": "true"}
            )
            _, kwargs = mock_rag_cls.return_value.ask.call_args
            self.assertIsNone(kwargs["workspace_ids"])

    def test_chat_returns_503_when_llm_unavailable(self) -> None:
        from nexus_api.rag import RagUnavailable

        with self._patched_dependencies() as mock_rag_cls:
            mock_rag_cls.return_value.ask.side_effect = RagUnavailable()
            response = TestClient(app).post(
                "/api/v1/chat", json={"query": "hello"}, headers={"X-User-Id": "u1"}
            )

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
