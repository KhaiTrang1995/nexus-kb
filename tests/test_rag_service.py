from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from tests import _paths  # noqa: F401

from nexus_api.rag import RagService, RagUnavailable
from nexus_shared.contracts import ChatRequest, SearchResponse, SearchResult, SourceType


def make_result(**overrides) -> SearchResult:
    defaults = dict(
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
        content="Nexus KB is a knowledge hub.",
        snippet="Nexus KB is a knowledge hub.",
        document_version=1,
    )
    defaults.update(overrides)
    return SearchResult(**defaults)


class FakeSearchService:
    def __init__(self, response: SearchResponse) -> None:
        self.response = response
        self.repository = MagicMock()
        self.received_workspace_ids = None
        self.received_actor_id = None

    def search(self, request, actor_id=None, workspace_ids=None):
        self.received_workspace_ids = workspace_ids
        self.received_actor_id = actor_id
        return self.response


class RagServiceTest(unittest.TestCase):
    def test_no_search_results_returns_canned_answer_without_calling_llm(self) -> None:
        search_service = FakeSearchService(SearchResponse(query="q", results=[]))
        llm_gateway = MagicMock()
        service = RagService(search_service, llm_gateway)

        response = service.ask(ChatRequest(query="hello"), actor_id="u1", workspace_ids=["ws-a"])

        self.assertEqual(response.citations, [])
        llm_gateway.complete.assert_not_called()
        search_service.repository.record_audit_log.assert_called_once()

    def test_successful_answer_includes_citations_from_search_results(self) -> None:
        result = make_result()
        search_service = FakeSearchService(SearchResponse(query="q", results=[result]))
        llm_gateway = MagicMock()
        llm_gateway.complete.return_value = MagicMock(text="Nexus KB la trung tam tri thuc.")
        service = RagService(search_service, llm_gateway)

        response = service.ask(ChatRequest(query="Nexus KB la gi?"), actor_id="u1", workspace_ids=["ws-a"])

        self.assertEqual(response.answer, "Nexus KB la trung tam tri thuc.")
        self.assertEqual(len(response.citations), 1)
        self.assertEqual(response.citations[0].chunk_id, result.chunk_id)
        self.assertEqual(response.citations[0].document_version, 1)
        self.assertEqual(search_service.received_workspace_ids, ["ws-a"])

        prompt = llm_gateway.complete.call_args[0][0].prompt
        self.assertIn(result.snippet, prompt)
        self.assertIn("Nexus KB la gi?", prompt)

    def test_missing_llm_gateway_raises_rag_unavailable(self) -> None:
        search_service = FakeSearchService(SearchResponse(query="q", results=[make_result()]))
        service = RagService(search_service, llm_gateway=None)

        with self.assertRaises(RagUnavailable):
            service.ask(ChatRequest(query="hello"), actor_id="u1", workspace_ids=None)

    def test_llm_failure_is_wrapped_as_rag_unavailable_search_still_worked(self) -> None:
        search_service = FakeSearchService(SearchResponse(query="q", results=[make_result()]))
        llm_gateway = MagicMock()
        llm_gateway.complete.side_effect = RuntimeError("llm provider failed after retries")
        service = RagService(search_service, llm_gateway)

        with self.assertRaises(RagUnavailable):
            service.ask(ChatRequest(query="hello"), actor_id="u1", workspace_ids=None)


if __name__ == "__main__":
    unittest.main()
