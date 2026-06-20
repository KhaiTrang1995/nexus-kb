"""Tests for LLMEntityExtractor — Phase 6 LLM-powered graph extraction."""
from __future__ import annotations

import json
import unittest
from uuid import uuid4

import tests._paths  # noqa: F401

from nexus_graph_builder import GraphBuildService, GraphBuilder, InMemoryGraphRepository, LLMEntityExtractor
from nexus_llm_gateway import LLMGateway, LLMRequest, ModelRoute
from nexus_llm_gateway.providers import LLMProvider
from nexus_shared.contracts import GraphChunkInput


# ── Fake providers ─────────────────────────────────────────────────────────────

class _JsonProvider:
    """Returns a fixed JSON payload regardless of prompt."""

    provider_name = "json-test"

    def __init__(self, payload: dict) -> None:
        self._text = json.dumps(payload)
        self.calls: list[str] = []

    def complete(self, request: LLMRequest, model: str) -> str:
        self.calls.append(request.prompt)
        return self._text


class _MarkdownFenceProvider:
    """Simulates an LLM that wraps JSON in a markdown code block."""

    provider_name = "fence-test"

    def __init__(self, payload: dict) -> None:
        self._text = "```json\n" + json.dumps(payload) + "\n```"

    def complete(self, request: LLMRequest, model: str) -> str:
        return self._text


class _FailingProvider:
    """Always raises."""

    provider_name = "fail-test"

    def complete(self, request: LLMRequest, model: str) -> str:
        raise RuntimeError("provider unavailable")


def _make_gateway(provider) -> LLMGateway:
    return LLMGateway(
        providers={provider.provider_name: provider},
        routes=[ModelRoute(task_type="entity_extraction", provider=provider.provider_name, model="test-model")],
        default_route=ModelRoute(task_type="default", provider=provider.provider_name, model="test-model"),
    )


def _chunk(content: str = "FastAPI uses Pydantic for validation.", metadata: dict | None = None) -> GraphChunkInput:
    return GraphChunkInput(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content=content,
        metadata=metadata or {},
        confidence=0.9,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

class LLMEntityExtractorTest(unittest.TestCase):

    # ── Basic extraction ──────────────────────────────────────────────────────

    def test_extracts_entities_from_valid_json_response(self) -> None:
        payload = {
            "entities": [
                {"name": "FastAPI", "type": "TECHNOLOGY", "confidence": 0.95},
                {"name": "Pydantic", "type": "TECHNOLOGY", "confidence": 0.90},
            ],
            "relationships": [],
        }
        extractor = LLMEntityExtractor(gateway=_make_gateway(_JsonProvider(payload)))
        entities = extractor.extract_entities(_chunk())

        self.assertEqual(len(entities), 2)
        names = {e.name for e in entities}
        self.assertIn("FastAPI", names)
        self.assertIn("Pydantic", names)
        self.assertEqual(entities[0].entity_type, "TECHNOLOGY")

    def test_extracts_relationships_when_both_ends_are_entities(self) -> None:
        payload = {
            "entities": [
                {"name": "FastAPI", "type": "TECHNOLOGY", "confidence": 0.9},
                {"name": "Pydantic", "type": "TECHNOLOGY", "confidence": 0.9},
            ],
            "relationships": [
                {"source": "FastAPI", "target": "Pydantic", "type": "USES", "confidence": 0.85},
            ],
        }
        extractor = LLMEntityExtractor(gateway=_make_gateway(_JsonProvider(payload)))
        chunk = _chunk()
        entities = extractor.extract_entities(chunk)
        relationships = extractor.extract_relationships(chunk)

        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0].source_name, "FastAPI")
        self.assertEqual(relationships[0].target_name, "Pydantic")
        self.assertEqual(relationships[0].relationship_type, "USES")
        self.assertAlmostEqual(relationships[0].confidence, 0.85)

    def test_drops_relationship_when_source_not_in_entity_list(self) -> None:
        payload = {
            "entities": [
                {"name": "FastAPI", "type": "TECHNOLOGY", "confidence": 0.9},
            ],
            "relationships": [
                {"source": "FastAPI", "target": "UnknownLib", "type": "USES", "confidence": 0.8},
            ],
        }
        extractor = LLMEntityExtractor(gateway=_make_gateway(_JsonProvider(payload)))
        chunk = _chunk()
        extractor.extract_entities(chunk)
        relationships = extractor.extract_relationships(chunk)

        self.assertEqual(len(relationships), 0)

    # ── Confidence filtering ──────────────────────────────────────────────────

    def test_filters_entities_below_min_confidence(self) -> None:
        payload = {
            "entities": [
                {"name": "FastAPI", "type": "TECHNOLOGY", "confidence": 0.9},
                {"name": "MaybeLib", "type": "TERM", "confidence": 0.1},
            ],
            "relationships": [],
        }
        extractor = LLMEntityExtractor(gateway=_make_gateway(_JsonProvider(payload)), min_confidence=0.3)
        entities = extractor.extract_entities(_chunk())

        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].name, "FastAPI")

    def test_filters_relationships_below_min_confidence(self) -> None:
        payload = {
            "entities": [
                {"name": "A", "type": "TERM", "confidence": 0.9},
                {"name": "B", "type": "TERM", "confidence": 0.9},
            ],
            "relationships": [
                {"source": "A", "target": "B", "type": "RELATED_TO", "confidence": 0.1},
            ],
        }
        extractor = LLMEntityExtractor(gateway=_make_gateway(_JsonProvider(payload)), min_confidence=0.3)
        chunk = _chunk()
        extractor.extract_entities(chunk)
        relationships = extractor.extract_relationships(chunk)

        self.assertEqual(len(relationships), 0)

    # ── Markdown fence handling ───────────────────────────────────────────────

    def test_strips_markdown_code_fence_before_parsing(self) -> None:
        payload = {"entities": [{"name": "Qdrant", "type": "TECHNOLOGY", "confidence": 0.88}], "relationships": []}
        extractor = LLMEntityExtractor(gateway=_make_gateway(_MarkdownFenceProvider(payload)))
        entities = extractor.extract_entities(_chunk())

        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].name, "Qdrant")

    # ── Fallback ─────────────────────────────────────────────────────────────

    def test_falls_back_to_metadata_when_llm_fails(self) -> None:
        gateway = LLMGateway(
            providers={"fail-test": _FailingProvider()},
            routes=[],
            default_route=ModelRoute(task_type="default", provider="fail-test", model="m"),
            retry_policy=__import__("nexus_llm_gateway").RetryPolicy(max_attempts=1),
        )
        extractor = LLMEntityExtractor(gateway=gateway)
        chunk = _chunk(metadata={"entities": [{"name": "PostgreSQL", "type": "DATABASE", "confidence": 0.7}]})
        entities = extractor.extract_entities(chunk)

        # Should fall back to MetadataEntityExtractor → reads from metadata
        self.assertTrue(any(e.name == "PostgreSQL" for e in entities))

    def test_falls_back_to_regex_when_llm_fails_and_no_metadata(self) -> None:
        gateway = LLMGateway(
            providers={"fail-test": _FailingProvider()},
            routes=[],
            default_route=ModelRoute(task_type="default", provider="fail-test", model="m"),
            retry_policy=__import__("nexus_llm_gateway").RetryPolicy(max_attempts=1),
        )
        extractor = LLMEntityExtractor(gateway=gateway)
        # No metadata — fallback regex catches capitalized words
        entities = extractor.extract_entities(_chunk(content="FastAPI and Pydantic are great."))

        names = {e.name for e in entities}
        self.assertIn("FastAPI", names)

    # ── Per-chunk caching ─────────────────────────────────────────────────────

    def test_makes_only_one_llm_call_per_chunk(self) -> None:
        payload = {
            "entities": [{"name": "FastAPI", "type": "TECHNOLOGY", "confidence": 0.9}],
            "relationships": [],
        }
        provider = _JsonProvider(payload)
        extractor = LLMEntityExtractor(gateway=_make_gateway(provider))
        chunk = _chunk()

        extractor.extract_entities(chunk)
        extractor.extract_relationships(chunk)  # second call, same chunk

        # extract_entities + extract_relationships both call _get_or_extract;
        # only one LLM call should have been made (cache hit on second call)
        self.assertEqual(len(provider.calls), 1)

    def test_makes_separate_calls_for_different_chunks(self) -> None:
        payload = {"entities": [], "relationships": []}
        provider = _JsonProvider(payload)
        extractor = LLMEntityExtractor(gateway=_make_gateway(provider))

        # Different content → different prompts → gateway cache misses → two provider calls
        extractor.extract_entities(_chunk(content="FastAPI is fast."))
        extractor.extract_entities(_chunk(content="Qdrant stores vectors."))

        self.assertEqual(len(provider.calls), 2)

    # ── Provenance ────────────────────────────────────────────────────────────

    def test_provenance_contains_chunk_and_document_ids(self) -> None:
        chunk = _chunk()
        payload = {
            "entities": [{"name": "FastAPI", "type": "TECHNOLOGY", "confidence": 0.9}],
            "relationships": [],
        }
        extractor = LLMEntityExtractor(gateway=_make_gateway(_JsonProvider(payload)))
        entities = extractor.extract_entities(chunk)

        self.assertEqual(entities[0].provenance.get("chunk_id"), str(chunk.chunk_id))
        self.assertEqual(entities[0].provenance.get("document_id"), str(chunk.document_id))

    # ── Empty response ────────────────────────────────────────────────────────

    def test_empty_llm_response_returns_no_entities(self) -> None:
        payload = {"entities": [], "relationships": []}
        extractor = LLMEntityExtractor(gateway=_make_gateway(_JsonProvider(payload)))
        entities = extractor.extract_entities(_chunk())
        self.assertEqual(entities, [])


class LLMEntityExtractorIntegrationTest(unittest.TestCase):
    """Integration: LLMEntityExtractor wired into GraphBuilder + GraphBuildService."""

    def test_graph_builder_uses_llm_extractor_when_provided(self) -> None:
        payload = {
            "entities": [
                {"name": "Qdrant", "type": "TECHNOLOGY", "confidence": 0.9},
                {"name": "PostgreSQL", "type": "TECHNOLOGY", "confidence": 0.85},
            ],
            "relationships": [
                {"source": "Qdrant", "target": "PostgreSQL", "type": "RELATED_TO", "confidence": 0.7},
            ],
        }
        repository = InMemoryGraphRepository()
        extractor = LLMEntityExtractor(gateway=_make_gateway(_JsonProvider(payload)))
        builder = GraphBuilder(repository, extractor=extractor)

        result = builder.build_from_chunks([_chunk()])

        self.assertEqual(len(result.entities), 2)
        self.assertEqual(len(result.relationships), 1)

    def test_graph_build_service_uses_llm_extractor_when_gateway_provided(self) -> None:
        approved_chunk = _chunk(metadata={})
        payload = {
            "entities": [{"name": "Qdrant", "type": "TECHNOLOGY", "confidence": 0.9}],
            "relationships": [],
        }

        class _MetaRepo:
            def list_approved_graph_chunks(self, limit=100):
                return [approved_chunk]

        service = GraphBuildService(
            metadata_repository=_MetaRepo(),
            graph_repository=InMemoryGraphRepository(),
            llm_gateway=_make_gateway(_JsonProvider(payload)),
        )
        result = service.build_from_approved_chunks()

        self.assertEqual(len(result.entities), 1)
        self.assertEqual(result.entities[0].name, "Qdrant")

    def test_graph_build_service_falls_back_to_metadata_when_no_gateway(self) -> None:
        approved_chunk = _chunk(metadata={"entities": ["Kafka"]})

        class _MetaRepo:
            def list_approved_graph_chunks(self, limit=100):
                return [approved_chunk]

        service = GraphBuildService(
            metadata_repository=_MetaRepo(),
            graph_repository=InMemoryGraphRepository(),
            llm_gateway=None,
        )
        result = service.build_from_approved_chunks()

        self.assertTrue(any(e.name == "Kafka" for e in result.entities))


if __name__ == "__main__":
    unittest.main()
