"""Tests for the 3-stage entity extraction pipeline (nexus_api.extraction)."""
from __future__ import annotations

import unittest

# Ensure service package paths are on sys.path before any project imports.
import tests._paths  # noqa: F401  — side-effect: mutates sys.path

from nexus_api.extraction import Entity, EntityExtractor, ExtractionResult, Relationship


class TestStage1EndpointDetection(unittest.TestCase):
    """Stage 1 — regex NER: ENDPOINT entities."""

    def setUp(self) -> None:
        self.extractor = EntityExtractor()

    def test_post_endpoint_detected(self) -> None:
        text = "Call POST /api/v1/graph/ingest to add data."
        result = self.extractor.extract(text)
        endpoints = [e for e in result.entities if e.entity_type == "ENDPOINT"]
        self.assertEqual(len(endpoints), 1)
        self.assertIn("/api/v1/graph/ingest", endpoints[0].text)

    def test_get_endpoint_detected(self) -> None:
        text = "Use GET /api/v1/graph/stats for statistics."
        result = self.extractor.extract(text)
        endpoints = [e for e in result.entities if e.entity_type == "ENDPOINT"]
        self.assertEqual(len(endpoints), 1)
        self.assertIn("/api/v1/graph/stats", endpoints[0].text)

    def test_endpoint_type_is_endpoint(self) -> None:
        text = "DELETE /api/v1/items/{id} removes a record."
        result = self.extractor.extract(text)
        endpoints = [e for e in result.entities if e.entity_type == "ENDPOINT"]
        self.assertTrue(len(endpoints) >= 1)
        self.assertEqual(endpoints[0].entity_type, "ENDPOINT")

    def test_multiple_endpoints_detected(self) -> None:
        text = "POST /api/v1/ingest uploads a doc. GET /api/v1/audit returns logs."
        result = self.extractor.extract(text)
        endpoints = [e for e in result.entities if e.entity_type == "ENDPOINT"]
        self.assertEqual(len(endpoints), 2)

    def test_endpoint_span_positions_are_valid(self) -> None:
        text = "Send PUT /api/v1/users/{id} with body."
        result = self.extractor.extract(text)
        for e in result.entities:
            self.assertGreaterEqual(e.start, 0)
            self.assertLess(e.start, e.end)
            self.assertEqual(text[e.start : e.end], e.text)


class TestStage1VersionDetection(unittest.TestCase):
    """Stage 1 — regex NER: VERSION entities."""

    def setUp(self) -> None:
        self.extractor = EntityExtractor()

    def test_full_semver_detected(self) -> None:
        text = "Upgrade to v1.2.3 immediately."
        result = self.extractor.extract(text)
        versions = [e for e in result.entities if e.entity_type == "VERSION"]
        self.assertTrue(any("v1.2.3" in v.text for v in versions))

    def test_major_minor_version_detected(self) -> None:
        text = "Compatible with v2.0 and above."
        result = self.extractor.extract(text)
        versions = [e for e in result.entities if e.entity_type == "VERSION"]
        self.assertTrue(any("v2.0" in v.text for v in versions))

    def test_major_only_version_detected(self) -> None:
        text = "API v3 is now stable."
        result = self.extractor.extract(text)
        versions = [e for e in result.entities if e.entity_type == "VERSION"]
        self.assertTrue(any("v3" in v.text for v in versions))

    def test_version_type_is_version(self) -> None:
        text = "Released as v1.0.0."
        result = self.extractor.extract(text)
        versions = [e for e in result.entities if e.entity_type == "VERSION"]
        self.assertGreater(len(versions), 0)
        self.assertEqual(versions[0].entity_type, "VERSION")


class TestStage1APIClassDetection(unittest.TestCase):
    """Stage 1 — regex NER: API entities."""

    def setUp(self) -> None:
        self.extractor = EntityExtractor()

    def test_service_suffix_detected(self) -> None:
        text = "The GraphService handles all graph operations."
        result = self.extractor.extract(text)
        apis = [e for e in result.entities if e.entity_type == "API"]
        self.assertTrue(any("GraphService" in a.text for a in apis))

    def test_api_suffix_detected(self) -> None:
        text = "Integrate via the NexusAPI for all requests."
        result = self.extractor.extract(text)
        apis = [e for e in result.entities if e.entity_type == "API"]
        self.assertTrue(any("NexusAPI" in a.text for a in apis))

    def test_client_suffix_detected(self) -> None:
        text = "Instantiate a QdrantClient before querying."
        result = self.extractor.extract(text)
        apis = [e for e in result.entities if e.entity_type == "API"]
        self.assertTrue(any("QdrantClient" in a.text for a in apis))

    def test_sdk_suffix_detected(self) -> None:
        text = "Download the PythonSDK from the release page."
        result = self.extractor.extract(text)
        apis = [e for e in result.entities if e.entity_type == "API"]
        self.assertTrue(any("PythonSDK" in a.text for a in apis))

    def test_api_type_field(self) -> None:
        text = "Use SearchService to find relevant chunks."
        result = self.extractor.extract(text)
        apis = [e for e in result.entities if e.entity_type == "API"]
        self.assertGreater(len(apis), 0)
        for a in apis:
            self.assertEqual(a.entity_type, "API")


class TestStage2NounPhraseDetection(unittest.TestCase):
    """Stage 2 — noun-phrase heuristic: CONCEPT entities."""

    def setUp(self) -> None:
        self.extractor = EntityExtractor()

    def test_two_word_concept_detected(self) -> None:
        text = "The Knowledge Graph stores relationships between concepts."
        result = self.extractor.extract(text)
        concepts = [e for e in result.entities if e.entity_type == "CONCEPT"]
        self.assertTrue(any("Knowledge Graph" in c.text for c in concepts))

    def test_three_word_concept_detected(self) -> None:
        text = "The Natural Language Processing pipeline runs nightly."
        result = self.extractor.extract(text)
        concepts = [e for e in result.entities if e.entity_type == "CONCEPT"]
        texts = [c.text for c in concepts]
        # Should capture at least a 2-word subset within the 3-word phrase
        self.assertTrue(
            any("Natural Language" in t or "Language Processing" in t or "Natural Language Processing" in t for t in texts)
        )

    def test_concept_not_duplicated_with_api(self) -> None:
        # "Graph Service" as two-word phrase should not also be API
        # GraphService (no space) is API; "Graph Service" (spaced) is CONCEPT
        text = "The Graph Service is separate from GraphService."
        result = self.extractor.extract(text)
        entity_texts = [e.text for e in result.entities]
        # Ensure no entity appears twice
        self.assertEqual(len(entity_texts), len(set(entity_texts)))

    def test_concept_type_is_concept(self) -> None:
        text = "Vector Database supports fast retrieval."
        result = self.extractor.extract(text)
        concepts = [e for e in result.entities if e.entity_type == "CONCEPT"]
        for c in concepts:
            self.assertEqual(c.entity_type, "CONCEPT")


class TestStage3RelationshipInference(unittest.TestCase):
    """Stage 3 — relationship inference by co-occurrence proximity."""

    def setUp(self) -> None:
        self.extractor = EntityExtractor()

    def test_close_entities_produce_relationship(self) -> None:
        # Two entities within 100 chars of each other
        text = "POST /api/v1/graph/ingest requires v1.2.3 or later."
        result = self.extractor.extract(text)
        self.assertGreater(len(result.relationships), 0)

    def test_relationship_source_target_are_entity_texts(self) -> None:
        text = "The GraphService calls POST /api/v1/search internally."
        result = self.extractor.extract(text)
        entity_texts = {e.text for e in result.entities}
        for rel in result.relationships:
            self.assertIn(rel.source, entity_texts)
            self.assertIn(rel.target, entity_texts)

    def test_endpoint_entity_produces_references_relationship(self) -> None:
        text = "Use GraphService via POST /api/v1/graph/build for all builds."
        result = self.extractor.extract(text)
        ref_rels = [r for r in result.relationships if r.relationship_type == "REFERENCES"]
        self.assertGreater(len(ref_rels), 0)

    def test_two_concepts_produce_co_occurs_relationship(self) -> None:
        # No endpoint — two concepts close together → CO_OCCURS
        text = "Knowledge Graph and Vector Database are both used here."
        result = self.extractor.extract(text)
        co_rels = [r for r in result.relationships if r.relationship_type == "CO_OCCURS"]
        self.assertGreater(len(co_rels), 0)

    def test_distant_entities_do_not_relate(self) -> None:
        # Pad 200 chars between two entities
        padding = " " * 200
        text = f"GraphService{padding}SearchService"
        result = self.extractor.extract(text)
        self.assertEqual(len(result.relationships), 0)

    def test_relationship_type_field_is_valid(self) -> None:
        valid_types = {"CO_OCCURS", "REFERENCES", "DEPENDS_ON"}
        text = "NexusAPI calls POST /api/v1/ingest to persist data."
        result = self.extractor.extract(text)
        for rel in result.relationships:
            self.assertIn(rel.relationship_type, valid_types)


class TestEdgeCases(unittest.TestCase):
    """Edge cases: empty input, no overlapping spans, single entity."""

    def setUp(self) -> None:
        self.extractor = EntityExtractor()

    def test_empty_text_returns_empty_result(self) -> None:
        result = self.extractor.extract("")
        self.assertIsInstance(result, ExtractionResult)
        self.assertEqual(result.entities, [])
        self.assertEqual(result.relationships, [])
        self.assertEqual(result.text, "")

    def test_whitespace_only_text(self) -> None:
        result = self.extractor.extract("   ")
        self.assertIsInstance(result, ExtractionResult)
        self.assertEqual(result.entities, [])

    def test_no_overlapping_spans(self) -> None:
        text = (
            "GraphService uses POST /api/v1/search and v2.0 for Knowledge Graph queries."
        )
        result = self.extractor.extract(text)
        spans = [(e.start, e.end) for e in result.entities]
        for i, (s1, e1) in enumerate(spans):
            for j, (s2, e2) in enumerate(spans):
                if i == j:
                    continue
                overlap = not (e1 <= s2 or s1 >= e2)
                self.assertFalse(overlap, f"Overlapping spans at indices {i} and {j}: {spans[i]} vs {spans[j]}")

    def test_single_entity_no_relationships(self) -> None:
        text = "Use v1.0 only."
        result = self.extractor.extract(text)
        self.assertEqual(len(result.relationships), 0)

    def test_result_text_preserved(self) -> None:
        text = "POST /api/v1/audit returns logs."
        result = self.extractor.extract(text)
        self.assertEqual(result.text, text)

    def test_entity_span_integrity(self) -> None:
        """For every entity, text[start:end] must equal entity.text."""
        text = (
            "NexusAPI wraps GET /api/v1/search using v2.1 — part of the Knowledge Base."
        )
        result = self.extractor.extract(text)
        for e in result.entities:
            self.assertEqual(
                text[e.start : e.end],
                e.text,
                f"Span mismatch for entity {e!r}",
            )

    def test_plain_text_no_entities(self) -> None:
        text = "this is plain lowercase text with no technical entities."
        result = self.extractor.extract(text)
        self.assertEqual(result.entities, [])
        self.assertEqual(result.relationships, [])


if __name__ == "__main__":
    unittest.main()
