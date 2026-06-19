from __future__ import annotations

from nexus_graph_builder.extractor import (
    MetadataEntityExtractor,
    WikilinkDocumentLinkExtractor,
    normalize_entity_name,
)
from nexus_shared.contracts import (
    GraphBuildResult,
    GraphChunkInput,
    GraphEntityCandidate,
    GraphRelationshipCandidate,
)


class GraphBuilder:
    def __init__(
        self,
        repository,
        extractor: MetadataEntityExtractor | None = None,
        wikilink_extractor: WikilinkDocumentLinkExtractor | None = None,
    ) -> None:
        self.repository = repository
        self.extractor = extractor or MetadataEntityExtractor()
        self.wikilink_extractor = wikilink_extractor or WikilinkDocumentLinkExtractor()

    def build_from_chunks(self, chunks: list[GraphChunkInput]) -> GraphBuildResult:
        entities_by_name: dict[tuple[str, str], object] = {}
        entities_by_id: dict[object, object] = {}
        relationships_by_id: dict[object, object] = {}

        # Regular entities + relationships (TERM by default)
        for chunk in chunks:
            for candidate in self.extractor.extract_entities(chunk):
                entity = self.repository.upsert_entity(candidate)
                key = (normalize_entity_name(candidate.name), candidate.entity_type)
                entities_by_name[key] = entity
                entities_by_id[entity.id] = entity

            for candidate in self.extractor.extract_relationships(chunk):
                src_type = "TERM"
                tgt_type = "TERM"
                source = entities_by_name.get((normalize_entity_name(candidate.source_name), src_type))
                target = entities_by_name.get((normalize_entity_name(candidate.target_name), tgt_type))
                if source is None or target is None:
                    continue
                relationship = self.repository.upsert_relationship(source, target, candidate)
                relationships_by_id[relationship.id] = relationship

        # Wikilink document links (DOCUMENT type for source/target, LINKS_TO)
        for chunk in chunks:
            for candidate in self.wikilink_extractor.extract_wikilink_links(chunk):
                src_type = "DOCUMENT"
                tgt_type = "DOCUMENT"
                source = entities_by_name.get((normalize_entity_name(candidate.source_name), src_type))
                if source is None:
                    # Create a DOCUMENT entity for source on the fly
                    src_candidate = type("tmp", (), {
                        "name": candidate.source_name,
                        "entity_type": src_type,
                        "confidence": candidate.confidence,
                        "provenance": candidate.provenance,
                    })()
                    source = self.repository.upsert_entity(src_candidate)
                    entities_by_name[(normalize_entity_name(candidate.source_name), src_type)] = source
                    entities_by_id[source.id] = source

                target = entities_by_name.get((normalize_entity_name(candidate.target_name), tgt_type))
                if target is None:
                    tgt_candidate = type("tmp", (), {
                        "name": candidate.target_name,
                        "entity_type": tgt_type,
                        "confidence": candidate.confidence,
                        "provenance": candidate.provenance,
                    })()
                    target = self.repository.upsert_entity(tgt_candidate)
                    entities_by_name[(normalize_entity_name(candidate.target_name), tgt_type)] = target
                    entities_by_id[target.id] = target

                if source is None or target is None:
                    continue
                relationship = self.repository.upsert_relationship(source, target, candidate)
                relationships_by_id[relationship.id] = relationship

        # Post-processing step: aggregate unique wikilinks per document for additional cross-doc edges
        # (ensures links even if some chunks didn't carry full list)
        doc_wikilinks: dict[object, set[str]] = {}
        for chunk in chunks:
            doc_id = chunk.document_id
            if doc_id not in doc_wikilinks:
                doc_wikilinks[doc_id] = set()
            doc_wikilinks[doc_id].update(getattr(chunk, "wikilinks", []) or chunk.metadata.get("wikilinks", []))

        for doc_id, wls in doc_wikilinks.items():
            rep_chunk = next((c for c in chunks if c.document_id == doc_id), None)
            if not rep_chunk or not wls:
                continue
            src_title = rep_chunk.metadata.get("title", str(doc_id))
            src_name = f"DOC:{src_title}"
            for wl in wls:
                if not wl:
                    continue
                tgt_name = f"DOC:{wl.strip()}"
                # Create DOCUMENT entities properly
                for name, etype in [(src_name, "DOCUMENT"), (tgt_name, "DOCUMENT")]:
                    key = (normalize_entity_name(name), etype)
                    if key not in entities_by_name:
                        cand = GraphEntityCandidate(
                            name=name,
                            entity_type=etype,
                            confidence=1.0,
                            provenance={"document_id": str(doc_id), "chunk_id": str(rep_chunk.chunk_id)},
                        )
                        ent = self.repository.upsert_entity(cand)
                        entities_by_name[key] = ent
                        entities_by_id[ent.id] = ent

                source = entities_by_name.get((normalize_entity_name(src_name), "DOCUMENT"))
                target = entities_by_name.get((normalize_entity_name(tgt_name), "DOCUMENT"))
                if source and target:
                    rel_cand = GraphRelationshipCandidate(
                        source_name=src_name,
                        target_name=tgt_name,
                        relationship_type="LINKS_TO",
                        confidence=1.0,
                        provenance={"document_id": str(doc_id), "chunk_id": str(rep_chunk.chunk_id)},
                    )
                    rel = self.repository.upsert_relationship(source, target, rel_cand)
                    relationships_by_id[rel.id] = rel

        return GraphBuildResult(
            entities=list(entities_by_id.values()),
            relationships=list(relationships_by_id.values()),
        )
