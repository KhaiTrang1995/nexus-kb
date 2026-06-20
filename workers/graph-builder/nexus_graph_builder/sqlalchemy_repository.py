from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID

from nexus_graph_builder.extractor import normalize_entity_name
from nexus_graph_builder.memory_repository import merge_provenance
from nexus_shared.contracts import (
    GraphBuildResult,
    GraphEntityCandidate,
    GraphEntityRecord,
    GraphRelationshipCandidate,
    GraphRelationshipRecord,
    HyperedgeCandidate,
    HyperedgeRecord,
)


class SQLAlchemyGraphRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = normalize_sqlalchemy_dsn(dsn)

    @contextmanager
    def session_scope(self) -> Iterator[Any]:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(self.dsn)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            engine.dispose()

    def upsert_entity(self, candidate: GraphEntityCandidate) -> GraphEntityRecord:
        from sqlalchemy import select

        from nexus_document_parser.db_models import GraphEntityModel

        normalized_name = normalize_entity_name(candidate.name)
        with self.session_scope() as session:
            model = session.execute(
                select(GraphEntityModel).where(
                    GraphEntityModel.normalized_name == normalized_name,
                    GraphEntityModel.entity_type == candidate.entity_type,
                )
            ).scalar_one_or_none()
            if model is None:
                model = GraphEntityModel(
                    name=candidate.name,
                    normalized_name=normalized_name,
                    entity_type=candidate.entity_type,
                    confidence=candidate.confidence,
                    provenance=candidate.provenance,
                )
                session.add(model)
            else:
                model.confidence = max(model.confidence, candidate.confidence)
                model.provenance = merge_provenance(model.provenance or {}, candidate.provenance)
            session.flush()
            return graph_entity_record(model)

    def upsert_relationship(
        self,
        source: GraphEntityRecord,
        target: GraphEntityRecord,
        candidate: GraphRelationshipCandidate,
    ) -> GraphRelationshipRecord:
        from sqlalchemy import select

        from nexus_document_parser.db_models import GraphRelationshipModel

        with self.session_scope() as session:
            model = session.execute(
                select(GraphRelationshipModel).where(
                    GraphRelationshipModel.source_entity_id == source.id,
                    GraphRelationshipModel.target_entity_id == target.id,
                    GraphRelationshipModel.relationship_type == candidate.relationship_type,
                )
            ).scalar_one_or_none()
            if model is None:
                model = GraphRelationshipModel(
                    source_entity_id=source.id,
                    target_entity_id=target.id,
                    relationship_type=candidate.relationship_type,
                    confidence=candidate.confidence,
                    provenance=candidate.provenance,
                )
                session.add(model)
            else:
                model.confidence = max(model.confidence, candidate.confidence)
                model.provenance = merge_provenance(model.provenance or {}, candidate.provenance)
            session.flush()
            return graph_relationship_record(model)

    def upsert_hyperedge(
        self,
        entity_records: list[GraphEntityRecord],
        candidate: HyperedgeCandidate,
    ) -> HyperedgeRecord:
        from sqlalchemy import select, text

        from nexus_document_parser.db_models import GraphHyperedgeMemberModel, GraphHyperedgeModel

        entity_ids = sorted({str(r.id) for r in entity_records})
        with self.session_scope() as session:
            # Look for existing hyperedge with same entity set + relationship_type
            existing_id: UUID | None = None
            rows = session.execute(
                text(
                    """
                    SELECT h.id
                    FROM graph_hyperedges h
                    WHERE h.relationship_type = :rel_type
                      AND (
                        SELECT array_agg(m.entity_id::text ORDER BY m.entity_id::text)
                        FROM graph_hyperedge_members m
                        WHERE m.hyperedge_id = h.id
                      ) = :entity_ids
                    LIMIT 1
                    """
                ),
                {"rel_type": candidate.relationship_type, "entity_ids": entity_ids},
            ).fetchall()
            if rows:
                existing_id = rows[0][0]

            if existing_id is not None:
                model = session.get(GraphHyperedgeModel, existing_id)
                model.confidence = max(model.confidence, candidate.confidence)
                model.provenance = merge_provenance(model.provenance or {}, candidate.provenance)
            else:
                model = GraphHyperedgeModel(
                    relationship_type=candidate.relationship_type,
                    label=candidate.label,
                    confidence=candidate.confidence,
                    provenance=candidate.provenance,
                )
                session.add(model)
                session.flush()
                for r in entity_records:
                    member = GraphHyperedgeMemberModel(
                        hyperedge_id=model.id,
                        entity_id=r.id,
                    )
                    session.add(member)

            session.flush()
            return HyperedgeRecord(
                id=model.id,
                entity_ids=[r.id for r in entity_records],
                relationship_type=model.relationship_type,
                label=model.label,
                confidence=model.confidence,
                provenance=model.provenance or {},
                created_at=model.created_at,
            )

    def related_to_entity(self, entity_id: UUID) -> list[GraphRelationshipRecord]:
        from sqlalchemy import or_, select

        from nexus_document_parser.db_models import GraphRelationshipModel

        with self.session_scope() as session:
            statement = select(GraphRelationshipModel).where(
                or_(
                    GraphRelationshipModel.source_entity_id == entity_id,
                    GraphRelationshipModel.target_entity_id == entity_id,
                )
            )
            return [graph_relationship_record(model) for model in session.execute(statement).scalars()]

    def graph_for_chunk(self, chunk_id: UUID) -> GraphBuildResult:
        from sqlalchemy import text

        chunk_key = str(chunk_id)
        with self.session_scope() as session:
            entity_rows = session.execute(
                text(
                    """
                    SELECT *
                    FROM graph_entities
                    WHERE provenance ->> 'chunk_id' = :chunk_id
                       OR provenance -> 'chunk_id' ? :chunk_id
                    """
                ),
                {"chunk_id": chunk_key},
            ).mappings().all()
            relationship_rows = session.execute(
                text(
                    """
                    SELECT *
                    FROM graph_relationships
                    WHERE provenance ->> 'chunk_id' = :chunk_id
                       OR provenance -> 'chunk_id' ? :chunk_id
                    """
                ),
                {"chunk_id": chunk_key},
            ).mappings().all()
            hyperedge_rows = session.execute(
                text(
                    """
                    SELECT h.id, h.relationship_type, h.label, h.confidence,
                           h.provenance, h.created_at,
                           array_agg(m.entity_id) AS entity_ids
                    FROM graph_hyperedges h
                    JOIN graph_hyperedge_members m ON m.hyperedge_id = h.id
                    WHERE h.provenance ->> 'chunk_id' = :chunk_id
                       OR h.provenance -> 'chunk_id' ? :chunk_id
                    GROUP BY h.id
                    """
                ),
                {"chunk_id": chunk_key},
            ).mappings().all()
            entities = [graph_entity_record(row) for row in entity_rows]
            relationships = [graph_relationship_record(row) for row in relationship_rows]
            hyperedges = [graph_hyperedge_record(row) for row in hyperedge_rows]
        return GraphBuildResult(entities=entities, relationships=relationships, hyperedges=hyperedges)


def graph_entity_record(model: Any) -> GraphEntityRecord:
    return GraphEntityRecord(
        id=model.id,
        name=model.name,
        normalized_name=model.normalized_name,
        entity_type=model.entity_type,
        confidence=model.confidence,
        provenance=model.provenance or {},
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def graph_relationship_record(model: Any) -> GraphRelationshipRecord:
    return GraphRelationshipRecord(
        id=model.id,
        source_entity_id=model.source_entity_id,
        target_entity_id=model.target_entity_id,
        relationship_type=model.relationship_type,
        confidence=model.confidence,
        provenance=model.provenance or {},
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def graph_hyperedge_record(row: Any) -> HyperedgeRecord:
    entity_ids = row["entity_ids"] or []
    return HyperedgeRecord(
        id=row["id"],
        entity_ids=list(entity_ids),
        relationship_type=row["relationship_type"],
        label=row["label"] or "",
        confidence=row["confidence"],
        provenance=row["provenance"] or {},
        created_at=row["created_at"],
    )


def normalize_sqlalchemy_dsn(dsn: str) -> str:
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    return dsn
