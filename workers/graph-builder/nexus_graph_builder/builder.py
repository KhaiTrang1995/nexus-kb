from __future__ import annotations

from nexus_graph_builder.extractor import MetadataEntityExtractor, normalize_entity_name
from nexus_shared.contracts import GraphBuildResult, GraphChunkInput


class GraphBuilder:
    def __init__(
        self,
        repository,
        extractor: MetadataEntityExtractor | None = None,
    ) -> None:
        self.repository = repository
        self.extractor = extractor or MetadataEntityExtractor()

    def build_from_chunks(self, chunks: list[GraphChunkInput]) -> GraphBuildResult:
        entities_by_name = {}
        entities_by_id = {}
        relationships_by_id = {}
        for chunk in chunks:
            for candidate in self.extractor.extract_entities(chunk):
                entity = self.repository.upsert_entity(candidate)
                entities_by_name[(normalize_entity_name(candidate.name), candidate.entity_type)] = entity
                entities_by_id[entity.id] = entity

            for candidate in self.extractor.extract_relationships(chunk):
                source = entities_by_name.get((normalize_entity_name(candidate.source_name), "TERM"))
                target = entities_by_name.get((normalize_entity_name(candidate.target_name), "TERM"))
                if source is None or target is None:
                    continue
                relationship = self.repository.upsert_relationship(source, target, candidate)
                relationships_by_id[relationship.id] = relationship

        return GraphBuildResult(
            entities=list(entities_by_id.values()),
            relationships=list(relationships_by_id.values()),
        )
