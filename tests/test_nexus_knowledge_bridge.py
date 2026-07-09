from __future__ import annotations

import json
import unittest
from uuid import uuid4

from tests import _paths  # noqa: F401

from nexus_knowledge_mcp.auth import ActorResolutionError
from nexus_knowledge_mcp.bridge import NexusKnowledgeBridge
from nexus_knowledge_mcp.schemas import McpActorContext, ToolCallEnvelope
from nexus_knowledge_mcp.server import handle_json_request
from nexus_shared.contracts import ChatResponse, DocumentRecord, SearchResponse, SearchResult, SourceType


class FakeTokenVerifier:
    def __init__(self, actor: McpActorContext | None = None, error: Exception | None = None) -> None:
        self.actor = actor
        self.error = error
        self.seen_tokens: list[str] = []

    def verify(self, token: str) -> McpActorContext:
        self.seen_tokens.append(token)
        if self.error is not None:
            raise self.error
        return self.actor


class FakeSearchService:
    def __init__(self, response: SearchResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def search(self, request, actor_id, workspace_ids):
        self.calls.append({"request": request, "actor_id": actor_id, "workspace_ids": workspace_ids})
        return self.response


class FakeRagService:
    def __init__(self, response: ChatResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def ask(self, request, actor_id, workspace_ids):
        self.calls.append({"request": request, "actor_id": actor_id, "workspace_ids": workspace_ids})
        return self.response


class FakeRepository:
    def __init__(self, documents: list[DocumentRecord]) -> None:
        self.documents = documents
        self.audit_events: list[dict] = []
        self.received_workspace_ids = None

    def list_documents_in_workspaces(self, workspace_ids, limit):
        self.received_workspace_ids = workspace_ids
        return self.documents[:limit]

    def record_audit_log(self, actor_id, action, status, resource_id=None, details=None):
        self.audit_events.append({"actor_id": actor_id, "action": action, "details": details})


def make_search_result() -> SearchResult:
    return SearchResult(
        score=0.9,
        vector_score=0.9,
        rank_score=0.9,
        chunk_id=uuid4(),
        document_id=uuid4(),
        title="Doc",
        source_path="/data/uploads/a.txt",
        file_extension=".txt",
        mime_type="text/plain",
        source_type=SourceType.LOCAL_FILE,
        chunk_index=0,
        content="content",
        snippet="content",
    )


class NexusKnowledgeBridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace_id = uuid4()
        self.actor = McpActorContext(user_id="alice", is_admin=False, workspace_ids=[str(self.workspace_id)])
        self.token_verifier = FakeTokenVerifier(actor=self.actor)
        self.search_service = FakeSearchService(SearchResponse(query="q", results=[make_search_result()]))
        self.rag_service = FakeRagService(ChatResponse(answer="42", citations=[]))
        self.repository = FakeRepository(documents=[])
        self.bridge = NexusKnowledgeBridge(
            self.token_verifier, self.search_service, self.rag_service, self.repository
        )

    def test_tool_definitions_are_read_only(self) -> None:
        names = {tool.name for tool in self.bridge.tool_definitions()}
        self.assertEqual(names, {"search_knowledge", "ask_knowledge", "list_documents"})

    def test_search_knowledge_scopes_to_actor_workspaces_and_logs_usage(self) -> None:
        result = self.bridge.call_tool("search_knowledge", "tok", {"query": "hello", "limit": 3})

        self.assertEqual(result, self.search_service.response)
        self.assertEqual(self.search_service.calls[0]["workspace_ids"], [str(self.workspace_id)])
        self.assertEqual(self.search_service.calls[0]["actor_id"], "alice")
        self.assertEqual(self.repository.audit_events[0]["action"], "MCP_TOOL_CALL")
        self.assertEqual(self.repository.audit_events[0]["actor_id"], "mcp:alice")

    def test_admin_actor_has_no_workspace_filter(self) -> None:
        self.token_verifier.actor = McpActorContext(user_id="root", is_admin=True, workspace_ids=[])

        self.bridge.call_tool("search_knowledge", "tok", {"query": "hello"})

        self.assertIsNone(self.search_service.calls[0]["workspace_ids"])

    def test_ask_knowledge_delegates_to_rag_service(self) -> None:
        result = self.bridge.call_tool("ask_knowledge", "tok", {"query": "what is nexus-kb?"})

        self.assertEqual(result, self.rag_service.response)
        self.assertEqual(self.rag_service.calls[0]["workspace_ids"], [str(self.workspace_id)])

    def test_list_documents_scopes_to_actor_workspaces(self) -> None:
        self.bridge.call_tool("list_documents", "tok", {"limit": 10})

        self.assertEqual(self.repository.received_workspace_ids, [self.workspace_id])

    def test_unsupported_tool_raises_connector_error(self) -> None:
        with self.assertRaises(Exception):
            self.bridge.call_tool("upload_knowledge", "tok", {})

    def test_invalid_token_maps_to_authorization_denied(self) -> None:
        self.token_verifier.error = ActorResolutionError("bad token")
        envelope = ToolCallEnvelope(tool="search_knowledge", token="bad", arguments={"query": "x"})

        result = self.bridge.call_tool_result(envelope)

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "AUTHORIZATION_DENIED")

    def test_json_runner_end_to_end(self) -> None:
        raw = json.dumps(
            {"tool": "search_knowledge", "token": "tok", "arguments": {"query": "hello"}, "correlation_id": "c1"}
        )

        payload = json.loads(handle_json_request(raw, self.bridge))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["correlation_id"], "c1")
        self.assertEqual(payload["result"]["query"], "q")


if __name__ == "__main__":
    unittest.main()
