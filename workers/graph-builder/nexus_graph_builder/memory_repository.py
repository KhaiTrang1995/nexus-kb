from __future__ import annotations

from uuid import UUID, uuid4

from nexus_graph_builder.extractor import normalize_entity_name
from nexus_shared.contracts import (
    GraphBuildResult,
    GraphEntityCandidate,
    GraphEntityRecord,
    GraphRelationshipCandidate,
    GraphRelationshipRecord,
    HyperedgeCandidate,
    HyperedgeRecord,
)


class InMemoryGraphRepository:
    def __init__(self) -> None:
        self.entities: dict[tuple[str, str], GraphEntityRecord] = {}
        self.relationships: dict[tuple[UUID, UUID, str], GraphRelationshipRecord] = {}
        self.hyperedges: list[HyperedgeRecord] = []

    def upsert_entity(self, candidate: GraphEntityCandidate) -> GraphEntityRecord:
        normalized_name = normalize_entity_name(candidate.name)
        key = (normalized_name, candidate.entity_type)
        existing = self.entities.get(key)
        if existing is None:
            record = GraphEntityRecord(
                id=uuid4(),
                name=candidate.name,
                normalized_name=normalized_name,
                entity_type=candidate.entity_type,
                confidence=candidate.confidence,
                provenance=candidate.provenance,
            )
            self.entities[key] = record
            return record

        merged = existing.model_copy(
            update={
                "confidence": max(existing.confidence, candidate.confidence),
                "provenance": merge_provenance(existing.provenance, candidate.provenance),
            }
        )
        self.entities[key] = merged
        return merged

    def upsert_relationship(
        self,
        source: GraphEntityRecord,
        target: GraphEntityRecord,
        candidate: GraphRelationshipCandidate,
    ) -> GraphRelationshipRecord:
        key = (source.id, target.id, candidate.relationship_type)
        existing = self.relationships.get(key)
        if existing is None:
            record = GraphRelationshipRecord(
                id=uuid4(),
                source_entity_id=source.id,
                target_entity_id=target.id,
                relationship_type=candidate.relationship_type,
                confidence=candidate.confidence,
                provenance=candidate.provenance,
            )
            self.relationships[key] = record
            return record

        merged = existing.model_copy(
            update={
                "confidence": max(existing.confidence, candidate.confidence),
                "provenance": merge_provenance(existing.provenance, candidate.provenance),
            }
        )
        self.relationships[key] = merged
        return merged

    def upsert_hyperedge(
        self,
        entity_records: list[GraphEntityRecord],
        candidate: HyperedgeCandidate,
    ) -> HyperedgeRecord:
        entity_ids = [e.id for e in entity_records]
        # Deduplicate by sorted entity_ids + type
        key = (tuple(sorted(str(eid) for eid in entity_ids)), candidate.relationship_type)
        for existing in self.hyperedges:
            existing_key = (tuple(sorted(str(eid) for eid in existing.entity_ids)), existing.relationship_type)
            if existing_key == key:
                return existing
        record = HyperedgeRecord(
            id=uuid4(),
            entity_ids=entity_ids,
            relationship_type=candidate.relationship_type,
            label=candidate.label,
            confidence=candidate.confidence,
            provenance=candidate.provenance,
        )
        self.hyperedges.append(record)
        return record

    def related_to_entity(self, entity_id: UUID) -> list[GraphRelationshipRecord]:
        return [
            relationship
            for relationship in self.relationships.values()
            if relationship.source_entity_id == entity_id or relationship.target_entity_id == entity_id
        ]

    def graph_for_chunk(self, chunk_id: UUID) -> GraphBuildResult:
        chunk_key = str(chunk_id)
        entities = [
            entity
            for entity in self.entities.values()
            if provenance_contains(entity.provenance, "chunk_id", chunk_key)
        ]
        relationships = [
            relationship
            for relationship in self.relationships.values()
            if provenance_contains(relationship.provenance, "chunk_id", chunk_key)
        ]
        return GraphBuildResult(entities=entities, relationships=relationships)


def merge_provenance(left: dict, right: dict) -> dict:
    merged = dict(left)
    for key, value in right.items():
        if key not in merged:
            merged[key] = value
            continue
        current = merged[key]
        if current == value:
            continue
        values = current if isinstance(current, list) else [current]
        if value not in values:
            values.append(value)
        merged[key] = values
    return merged


def provenance_contains(provenance: dict, key: str, value: str) -> bool:
    current = provenance.get(key)
    if isinstance(current, list):
        return value in {str(item) for item in current}
    return str(current) == value
