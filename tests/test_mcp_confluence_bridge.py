from __future__ import annotations

import unittest
import json

from tests import _paths  # noqa: F401

from nexus_confluence_bridge.bridge import (
    AuthorizationError,
    ConfluenceBridge,
    ConnectorError,
    InMemoryConfluenceClient,
    InMemoryConfluencePage,
)
from nexus_confluence_bridge.server import handle_json_request


class ConfluenceBridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = InMemoryConfluenceClient(
            [
                InMemoryConfluencePage(
                    id="page-1",
                    space_key="KB",
                    title="Runbook",
                    content="Synthetic runbook content.",
                )
            ]
        )
        self.bridge = ConfluenceBridge(self.client)
        self.actor = {"user_id": "alice", "roles": ["SourceReader"], "allowed_spaces": ["KB"]}

    def test_tool_schema_exposes_read_only_tools(self) -> None:
        tools = self.bridge.tool_definitions()
        names = {tool.name for tool in tools}

        self.assertEqual(names, {"confluence.discover_sources", "confluence.read_document"})
        self.assertTrue(all("input_schema" in tool.model_dump() for tool in tools))
        discover_schema = next(tool.input_schema for tool in tools if tool.name == "confluence.discover_sources")
        self.assertIn("actor", discover_schema["properties"])

    def test_discover_sources_requires_authorized_actor_context(self) -> None:
        result = self.bridge.call_tool(
            "confluence.discover_sources",
            {"actor": self.actor, "space_key": "KB", "limit": 10},
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source_id, "page-1")
        self.assertEqual(result[0].metadata["authorized_actor"], "alice")

        with self.assertRaises(AuthorizationError):
            self.bridge.call_tool(
                "confluence.discover_sources",
                {"actor": {"user_id": "bob", "roles": [], "allowed_spaces": []}, "space_key": "KB"},
            )

    def test_read_document_requires_space_access_and_returns_hash(self) -> None:
        actor = self.actor | {"source_principal": "alice@example.test", "correlation_id": "corr-1"}
        document = self.bridge.call_tool("confluence.read_document", {"actor": actor, "page_id": "page-1"})

        self.assertEqual(document.content, "Synthetic runbook content.")
        self.assertEqual(len(document.content_hash), 64)
        self.assertEqual(document.metadata["source_principal"], "alice@example.test")
        self.assertEqual(document.metadata["correlation_id"], "corr-1")

        with self.assertRaises(AuthorizationError):
            self.bridge.call_tool(
                "confluence.read_document",
                {"actor": {"user_id": "mallory", "roles": ["SourceReader"], "allowed_spaces": ["HR"]}, "page_id": "page-1"},
            )

    def test_mutating_tools_are_disabled_by_default(self) -> None:
        with self.assertRaises(AuthorizationError):
            self.bridge.call_tool("confluence.update_page", {"actor": self.actor, "page_id": "page-1"})

    def test_connector_errors_are_redacted(self) -> None:
        class FailingClient(InMemoryConfluenceClient):
            def list_pages(self, space_key: str, limit: int):
                raise RuntimeError("GET https://internal.example.test/wiki token=abc123 owner=admin@example.test")

        bridge = ConfluenceBridge(FailingClient())

        with self.assertRaises(ConnectorError) as context:
            bridge.call_tool("confluence.discover_sources", {"actor": self.actor, "space_key": "KB"})

        message = str(context.exception)
        self.assertIn("[redacted-url]", message)
        self.assertIn("token=[redacted]", message)
        self.assertIn("[redacted-email]", message)
        self.assertNotIn("internal.example.test", message)
        self.assertNotIn("abc123", message)
        self.assertNotIn("admin@example.test", message)

    def test_structured_tool_result_preserves_correlation_and_redacts_errors(self) -> None:
        result = self.bridge.call_tool_result(
            "confluence.read_document",
            {
                "actor": {
                    "user_id": "mallory",
                    "roles": ["SourceReader"],
                    "allowed_spaces": ["HR"],
                    "correlation_id": "corr-denied",
                },
                "page_id": "page-1",
            },
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "AUTHORIZATION_DENIED")
        self.assertEqual(result.correlation_id, "corr-denied")
        self.assertIsNone(result.result)

    def test_json_runner_returns_mcp_style_result(self) -> None:
        raw = json.dumps(
            {
                "tool": "confluence.discover_sources",
                "arguments": {
                    "actor": {
                        "user_id": "alice",
                        "roles": ["SourceReader"],
                        "allowed_spaces": ["KB"],
                        "correlation_id": "corr-json",
                    },
                    "space_key": "KB",
                },
            }
        )

        payload = json.loads(handle_json_request(raw, self.bridge))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["correlation_id"], "corr-json")
        self.assertEqual(payload["result"][0]["source_id"], "page-1")


if __name__ == "__main__":
    unittest.main()
