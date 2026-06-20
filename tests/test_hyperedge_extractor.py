"""Tests for HyperedgeExtractor — Phase 6 Step 3."""
from __future__ import annotations

import json
import unittest
from uuid import uuid4

import tests._paths  # noqa: F401

from nexus_graph_builder import GraphBuilder, HyperedgeExtractor, InMemoryGraphRepository, LLMEntityExtractor
from nexus_llm_gateway import LLMGateway, LLMRequest, ModelRoute
from nexus_shared.contracts import GraphChunkInput, HyperedgeCandidate


# ── Fake providers ─────────────────────────────────────────────────────────────

class _JsonProvider:
    provider_name = "json-test"

    def __init__(self, payload: dict) -> None:
        self._text = json.dumps(payload)
        self.calls: list[str] = []

    def complete(self, request: LLMRequest, model: str) -> str:
        self.calls.append(request.prompt)
        return self._text


class _FailingProvider:
    provider_name = "fail-test"

    def complete(self, request: LLMRequest, model: str) -> str:
        raise RuntimeError("unavailable")


def _make_gateway(provider) -> LLMGateway:
    return LLMGateway(
        providers={provider.provider_name: provider},
        routes=[ModelRoute(task_type="hyperedge_extraction", provider=provider.provider_name, model="m")],
        default_route=ModelRoute(task_type="default", provider=provider.provider_name, model="m"),
    )


def _chunk(content: str = "FastAPI uses Pydantic and SQLAlchemy for data validation and ORM.") -> GraphChunkInput:
    return GraphChunkInput(chunk_id=uuid4(), document_id=uuid4(), content=content)


# ── Unit tests ─────────────────────────────────────────────────────────────────

class HyperedgeExtractorTest(unittest.TestCase):

    def test_extracts_hyperedge_with_3_entities(self) -> None:
        payload = {
            "hyperedges": [{
                "entities": ["FastAPI", "Pydantic", "SQLAlchemy"],
                "type": "CO_USES",
                "label": "FastAPI uses Pydantic and SQLAlchemy together",
                "confidence": 0.85,
            }]
        }
        extractor = HyperedgeExtractor(gateway=_make_gateway(_JsonProvider(payload)))
        candidates = extractor.extract(_chunk())

        self.assertEqual(len(candidates), 1)
        self.assertEqual(set(candidates[0].entity_names), {"FastAPI", "Pydantic", "SQLAlchemy"})
        self.assertEqual(candidates[0].relationship_type, "CO_USES")
        self.assertAlmostEqual(candidates[0].confidence, 0.85)

    def test_drops_hyperedge_with_fewer_than_min_members(self) -> None:
        payload = {
            "hyperedges": [
                {"entities": ["A", "B"], "type": "CO_USES", "label": "pair", "confidence": 0.9},
                {"entities": ["A", "B", "C"], "type": "CO_USES", "label": "triple", "confidence": 0.9},
            ]
        }
        extractor = HyperedgeExtractor(gateway=_make_gateway(_JsonProvider(payload)), min_members=3)
        candidates = extractor.extract(_chunk())

        self.assertEqual(len(candidates), 1)  # pair dropped, triple kept
        self.assertIn("C", candidates[0].entity_names)

    def test_drops_hyperedge_below_min_confidence(self) -> None:
        payload = {
            "hyperedges": [
                {"entities": ["A", "B", "C"], "type": "INVOLVES", "label": "weak", "confidence": 0.1},
                {"entities": ["D", "E", "F"], "type": "INVOLVES", "label": "strong", "confidence": 0.9},
            ]
        }
        extractor = HyperedgeExtractor(gateway=_make_gateway(_JsonProvider(payload)), min_confidence=0.3)
        candidates = extractor.extract(_chunk())

        self.assertEqual(len(candidates), 1)
        self.assertIn("D", candidates[0].entity_names)

    def test_strips_markdown_fence_before_parsing(self) -> None:
        payload = {"hyperedges": [{"entities": ["X", "Y", "Z"], "type": "INVOLVES", "label": "l", "confidence": 0.9}]}
        text = "```json\n" + json.dumps(payload) + "\n```"

        class _FenceProvider:
            provider_name = "fence"
            def complete(self, r, m): return text

        extractor = HyperedgeExtractor(gateway=_make_gateway(_FenceProvider()))
        candidates = extractor.extract(_chunk())
        self.assertEqual(len(candidates), 1)

    def test_returns_empty_list_on_llm_failure(self) -> None:
        gateway = LLMGateway(
            providers={"fail-test": _FailingProvider()},
            routes=[],
            default_route=ModelRoute(task_type="default", provider="fail-test", model="m"),
            retry_policy=__import__("nexus_llm_gateway").RetryPolicy(max_attempts=1),
        )
        extractor = HyperedgeExtractor(gateway=gateway)
        result = extractor.extract(_chunk())
        self.assertEqual(result, [])

    def test_returns_empty_list_when_no_hyperedges_in_text(self) -> None:
        payload = {"hyperedges": []}
        extractor = HyperedgeExtractor(gateway=_make_gateway(_JsonProvider(payload)))
        self.assertEqual(extractor.extract(_chunk()), [])

    def test_per_chunk_caching(self) -> None:
        payload = {"hyperedges": []}
        provider = _JsonProvider(payload)
        extractor = HyperedgeExtractor(gateway=_make_gateway(provider))
        chunk = _chunk()
        extractor.extract(chunk)
        extractor.extract(chunk)
        self.assertEqual(len(provider.calls), 1)  # second call is a cache hit

    def test_provenance_contains_chunk_and_document_ids(self) -> None:
        chunk = _chunk()
        payload = {
            "hyperedges": [{"entities": ["A", "B", "C"], "type": "INVOLVES", "label": "l", "confidence": 0.8}]
        }
        extractor = HyperedgeExtractor(gateway=_make_gateway(_JsonProvider(payload)))
        candidates = extractor.extract(chunk)
        prov = candidates[0].provenance
        self.assertEqual(prov.get("chunk_id"), str(chunk.chunk_id))
        self.assertEqual(prov.get("document_id"), str(chunk.document_id))

    def test_raises_on_min_members_less_than_2(self) -> None:
        with self.assertRaises(ValueError):
            HyperedgeExtractor(gateway=_make_gateway(_JsonProvider({})), min_members=1)

    def test_deduplicates_entity_names_in_candidate(self) -> None:
        # LLM returns duplicates — enforce unique by set
        payload = {
            "hyperedges": [{"entities": ["A", "A", "B", "C"], "type": "INVOLVES", "label": "l", "confidence": 0.9}]
        }
        extractor = HyperedgeExtractor(gateway=_make_gateway(_JsonProvider(payload)), min_members=3)
        candidates = extractor.extract(_chunk())
        # With duplicates collapsed, we have {A, B, C} = 3 unique — should pass min_members=3
        self.assertEqual(len(candidates), 1)


# ── Integration: GraphBuilder wires HyperedgeExtractor ────────────────────────

class _EntitiesProvider:
    """Two-call provider: first call → entities JSON, second → hyperedge JSON."""
    provider_name = "dual"

    def __init__(self, entities_payload: dict, hyperedge_payload: dict) -> None:
        self._payloads = [json.dumps(entities_payload), json.dumps(hyperedge_payload)]
        self._call = 0

    def complete(self, request: LLMRequest, model: str) -> str:
        idx = min(self._call, len(self._payloads) - 1)
        self._call += 1
        return self._payloads[idx]


class HyperedgeIntegrationTest(unittest.TestCase):

    def test_graph_builder_wires_hyperedge_extractor(self) -> None:
        chunk = GraphChunkInput(
            chunk_id=uuid4(),
            document_id=uuid4(),
            content="FastAPI, Pydantic, and SQLAlchemy work together in a web stack.",
            metadata={
                "entities": [
                    {"name": "FastAPI", "type": "TECHNOLOGY", "confidence": 0.9},
                    {"name": "Pydantic", "type": "TECHNOLOGY", "confidence": 0.9},
                    {"name": "SQLAlchemy", "type": "TECHNOLOGY", "confidence": 0.9},
                ],
            },
        )
        hyperedge_payload = {
            "hyperedges": [{
                "entities": ["FastAPI", "Pydantic", "SQLAlchemy"],
                "type": "CO_USES",
                "label": "Three libraries in one web stack",
                "confidence": 0.88,
            }]
        }
        provider = _JsonProvider(hyperedge_payload)
        hyperedge_gw = _make_gateway(provider)
        repository = InMemoryGraphRepository()
        builder = GraphBuilder(
            repository,
            hyperedge_extractor=HyperedgeExtractor(gateway=hyperedge_gw),
        )
        result = builder.build_from_chunks([chunk])

        self.assertEqual(len(result.entities), 3)
        self.assertEqual(len(result.hyperedges), 1)
        h = result.hyperedges[0]
        self.assertEqual(h.relationship_type, "CO_USES")
        self.assertEqual(len(h.entity_ids), 3)

    def test_graph_builder_returns_empty_hyperedges_when_no_extractor(self) -> None:
        chunk = GraphChunkInput(
            chunk_id=uuid4(),
            document_id=uuid4(),
            content="A simple test.",
            metadata={"entities": ["Qdrant"]},
        )
        result = GraphBuilder(InMemoryGraphRepository()).build_from_chunks([chunk])
        self.assertEqual(result.hyperedges, [])

    def test_hyperedge_skipped_when_entity_not_in_graph(self) -> None:
        chunk = GraphChunkInput(
            chunk_id=uuid4(),
            document_id=uuid4(),
            content="Only Qdrant is here.",
            metadata={"entities": ["Qdrant"]},
        )
        hyperedge_payload = {
            "hyperedges": [{
                "entities": ["Qdrant", "UnknownLib", "AnotherUnknown"],
                "type": "CO_USES",
                "label": "phantom",
                "confidence": 0.9,
            }]
        }
        provider = _JsonProvider(hyperedge_payload)
        repository = InMemoryGraphRepository()
        builder = GraphBuilder(
            repository,
            hyperedge_extractor=HyperedgeExtractor(gateway=_make_gateway(provider)),
        )
        result = builder.build_from_chunks([chunk])
        # Only Qdrant was extracted → less than 2 unique resolved records → skip hyperedge
        self.assertEqual(result.hyperedges, [])


if __name__ == "__main__":
    unittest.main()
