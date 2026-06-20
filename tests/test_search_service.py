from __future__ import annotations

import unittest
from uuid import uuid4

from tests import _paths  # noqa: F401

from nexus_api.search import SearchService, build_snippet, rerank_score
from nexus_document_parser.embedding import DeterministicEmbeddingProvider
from nexus_shared.contracts import GraphBuildResult, GraphEntityRecord, GraphRelationshipRecord, SearchRequest, SourceType


class FakeRepository:
    def __init__(self, rows: dict) -> None:
        self.rows = rows

    def get_chunk_with_document(self, chunk_id):
        return self.rows.get(chunk_id)

    def record_audit_log(self, actor_id, action, status, resource_id=None, details=None):
        # Audit side-effect stub for search unit tests; real audit trail tested separately.
        pass


class FakeVectorClient:
    def __init__(self, results) -> None:
        self.results = results
        self.received_tags = None

    def search(self, vector, limit=10, tags=None, source_type=None):
        self.received_tags = tags
        return self.results


class FakeGraphRepository:
    def __init__(self, graph_by_chunk) -> None:
        self.graph_by_chunk = graph_by_chunk

    def graph_for_chunk(self, chunk_id):
        return self.graph_by_chunk.get(chunk_id, GraphBuildResult(entities=[], relationships=[]))


class SearchServiceTest(unittest.TestCase):
    def test_search_joins_vector_payload_with_postgres_metadata(self) -> None:
        chunk_id = uuid4()
        document_id = uuid4()
        row = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "chunk_index": 2,
            "content": "Nexus-KB uses governed retrieval.",
            "chunk_metadata": {"heading_path": ["Platform", "Retrieval"], "section_title": "Retrieval"},
            "title": "Nexus",
            "source_path": "/vault/Nexus.md",
            "file_extension": ".md",
            "mime_type": "text/markdown",
            "source_type": "obsidian",
            "tags": ["rag"],
            "wikilinks": ["Graph"],
            "frontmatter": {"owner": "platform"},
        }
        vector_client = FakeVectorClient(
            [
                {
                    "id": str(chunk_id),
                    "score": 0.91,
                    "payload": {"chunk_id": str(chunk_id)},
                }
            ]
        )
        service = SearchService(
            repository=FakeRepository({chunk_id: row}),
            vector_client=vector_client,
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        )

        response = service.search(SearchRequest(query="retrieval", tags=["rag"], source_type=SourceType.OBSIDIAN))

        self.assertEqual(vector_client.received_tags, ["rag"])
        self.assertEqual(len(response.results), 1)
        result = response.results[0]
        self.assertEqual(result.chunk_id, chunk_id)
        self.assertEqual(result.document_id, document_id)
        self.assertEqual(result.file_extension, ".md")
        self.assertEqual(result.mime_type, "text/markdown")
        self.assertEqual(result.source_type, SourceType.OBSIDIAN)
        self.assertGreater(result.rank_score, result.vector_score)
        self.assertIn("governed retrieval", result.snippet)
        self.assertEqual(result.heading_path, ["Platform", "Retrieval"])
        self.assertEqual(result.section_title, "Retrieval")
        self.assertEqual(result.frontmatter["owner"], "platform")

    def test_search_result_includes_graph_lookup_for_matched_chunk(self) -> None:
        chunk_id = uuid4()
        document_id = uuid4()
        entity_id = uuid4()
        target_id = uuid4()
        row = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "chunk_index": 0,
            "content": "Nexus-KB uses Qdrant.",
            "chunk_metadata": {},
            "title": "Graph",
            "source_path": "/vault/Graph.md",
            "file_extension": ".md",
            "mime_type": "text/markdown",
            "source_type": "obsidian",
            "tags": [],
            "wikilinks": [],
            "frontmatter": {},
        }
        graph = GraphBuildResult(
            entities=[
                GraphEntityRecord(
                    id=entity_id,
                    name="Nexus-KB",
                    normalized_name="nexus-kb",
                    entity_type="TERM",
                    confidence=0.9,
                    provenance={"chunk_id": str(chunk_id)},
                )
            ],
            relationships=[
                GraphRelationshipRecord(
                    id=uuid4(),
                    source_entity_id=entity_id,
                    target_entity_id=target_id,
                    relationship_type="USES",
                    confidence=0.88,
                    provenance={"chunk_id": str(chunk_id)},
                )
            ],
        )
        vector_client = FakeVectorClient([{"id": str(chunk_id), "score": 0.91, "payload": {"chunk_id": str(chunk_id)}}])
        service = SearchService(
            repository=FakeRepository({chunk_id: row}),
            vector_client=vector_client,
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            graph_repository=FakeGraphRepository({chunk_id: graph}),
        )

        response = service.search(SearchRequest(query="qdrant"))

        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].graph_entities[0].normalized_name, "nexus-kb")
        self.assertEqual(response.results[0].graph_relationships[0].relationship_type, "USES")

    def test_search_reranks_lexically_relevant_lower_vector_result(self) -> None:
        first_chunk = uuid4()
        second_chunk = uuid4()
        rows = {
            first_chunk: {
                "chunk_id": first_chunk,
                "document_id": uuid4(),
                "chunk_index": 0,
                "content": "Unrelated content.",
                "chunk_metadata": {"heading_path": ["Misc"], "section_title": "Misc"},
                "title": "Misc",
                "source_path": "/vault/Misc.md",
                "file_extension": ".md",
                "mime_type": "text/markdown",
                "source_type": "obsidian",
                "tags": [],
                "wikilinks": [],
                "frontmatter": {},
            },
            second_chunk: {
                "chunk_id": second_chunk,
                "document_id": uuid4(),
                "chunk_index": 1,
                "content": "Retrieval pipeline uses qdrant search and rag filters.",
                "chunk_metadata": {"heading_path": ["RAG", "Retrieval"], "section_title": "Retrieval"},
                "title": "RAG",
                "source_path": "/vault/RAG.md",
                "file_extension": ".md",
                "mime_type": "text/markdown",
                "source_type": "obsidian",
                "tags": ["rag"],
                "wikilinks": [],
                "frontmatter": {},
            },
        }
        vector_client = FakeVectorClient(
            [
                {"id": str(first_chunk), "score": 0.90, "payload": {"chunk_id": str(first_chunk)}},
                {"id": str(second_chunk), "score": 0.86, "payload": {"chunk_id": str(second_chunk)}},
            ]
        )
        service = SearchService(FakeRepository(rows), vector_client, DeterministicEmbeddingProvider(dimension=8))

        response = service.search(SearchRequest(query="rag retrieval", limit=1))

        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.results[0].chunk_id, second_chunk)

    def test_rerank_and_snippet_helpers_are_stable(self) -> None:
        score = rerank_score(
            query="rag retrieval",
            vector_score=0.8,
            content="RAG retrieval is implemented with filters.",
            title="RAG",
            tags=["retrieval"],
            heading_path=["Platform", "Retrieval"],
        )
        snippet = build_snippet("Intro. RAG retrieval is implemented with filters. Tail.", "retrieval")

        self.assertGreater(score, 0.8)
        self.assertIn("retrieval", snippet)


if __name__ == "__main__":
    unittest.main()
