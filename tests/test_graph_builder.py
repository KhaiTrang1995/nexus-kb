from __future__ import annotations

import unittest
from uuid import uuid4

from tests import _paths  # noqa: F401

from nexus_graph_builder import GraphBuildService, GraphBuilder, InMemoryGraphRepository
from nexus_shared.contracts import GraphChunkInput


class GraphBuilderTest(unittest.TestCase):
    def test_merges_duplicate_entities_and_preserves_provenance(self) -> None:
        first_chunk = uuid4()
        second_chunk = uuid4()
        document_id = uuid4()
        builder = GraphBuilder(InMemoryGraphRepository())

        result = builder.build_from_chunks(
            [
                GraphChunkInput(
                    chunk_id=first_chunk,
                    document_id=document_id,
                    content="Nexus KB uses Qdrant.",
                    metadata={"entities": [{"name": "Qdrant", "type": "TERM", "confidence": 0.72}]},
                ),
                GraphChunkInput(
                    chunk_id=second_chunk,
                    document_id=document_id,
                    content="qdrant stores vectors.",
                    metadata={"entities": [{"name": "qdrant", "type": "TERM", "confidence": 0.91}]},
                ),
            ]
        )

        self.assertEqual(len(result.entities), 1)
        entity = result.entities[0]
        self.assertEqual(entity.normalized_name, "qdrant")
        self.assertEqual(entity.confidence, 0.91)
        self.assertEqual(set(entity.provenance["chunk_id"]), {str(first_chunk), str(second_chunk)})

    def test_builds_relationships_with_confidence_and_graph_lookup(self) -> None:
        repository = InMemoryGraphRepository()
        builder = GraphBuilder(repository)
        chunk_id = uuid4()
        document_id = uuid4()

        result = builder.build_from_chunks(
            [
                GraphChunkInput(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    content="Nexus-KB uses Qdrant.",
                    metadata={
                        "entities": ["Nexus-KB", "Qdrant"],
                        "relationships": [
                            {"source": "Nexus-KB", "target": "Qdrant", "type": "USES", "confidence": 0.88}
                        ],
                    },
                )
            ]
        )

        self.assertEqual(len(result.relationships), 1)
        relationship = result.relationships[0]
        self.assertEqual(relationship.relationship_type, "USES")
        self.assertEqual(relationship.confidence, 0.88)
        self.assertEqual(relationship.provenance["chunk_id"], str(chunk_id))
        self.assertEqual(len(repository.related_to_entity(relationship.source_entity_id)), 1)

    def test_build_service_uses_only_metadata_repository_approved_chunks(self) -> None:
        approved_chunk = GraphChunkInput(
            chunk_id=uuid4(),
            document_id=uuid4(),
            content="Nexus-KB uses Qdrant.",
            metadata={
                "entities": ["Nexus-KB", "Qdrant"],
                "relationships": [{"source": "Nexus-KB", "target": "Qdrant", "type": "USES"}],
            },
        )

        class MetadataRepository:
            def __init__(self) -> None:
                self.limit = None

            def list_approved_graph_chunks(self, limit=100):
                self.limit = limit
                return [approved_chunk]

        metadata_repository = MetadataRepository()
        result = GraphBuildService(metadata_repository, InMemoryGraphRepository()).build_from_approved_chunks(limit=10)

        self.assertEqual(metadata_repository.limit, 10)
        self.assertEqual(len(result.entities), 2)
        self.assertEqual(len(result.relationships), 1)

    def test_extracts_document_links_from_wikilinks_and_creates_LINKS_TO(self) -> None:
        repository = InMemoryGraphRepository()
        builder = GraphBuilder(repository)
        chunk_id = uuid4()
        document_id = uuid4()

        result = builder.build_from_chunks(
            [
                GraphChunkInput(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    content="See also [[Related Note]] and [[Another Doc]].",
                    metadata={"title": "Platform.md"},
                    wikilinks=["Related Note", "Another Doc"],
                )
            ]
        )

        # Should create DOCUMENT entities for source docs + targets, and LINKS_TO relationships
        doc_entities = [e for e in result.entities if e.entity_type == "DOCUMENT"]
        self.assertTrue(len(doc_entities) >= 2)  # at least source + target

        links_to = [r for r in result.relationships if r.relationship_type == "LINKS_TO"]
        self.assertTrue(len(links_to) >= 1)
        link = links_to[0]
        self.assertEqual(link.provenance.get("document_id"), str(document_id))
        self.assertEqual(link.provenance.get("chunk_id"), str(chunk_id))


if __name__ == "__main__":
    unittest.main()
