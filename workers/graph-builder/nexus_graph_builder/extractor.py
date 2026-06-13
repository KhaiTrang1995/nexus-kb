from __future__ import annotations

import re

from nexus_shared.contracts import GraphChunkInput, GraphEntityCandidate, GraphRelationshipCandidate


class MetadataEntityExtractor:
    def extract_entities(self, chunk: GraphChunkInput) -> list[GraphEntityCandidate]:
        raw_entities = chunk.metadata.get("entities") or []
        candidates: list[GraphEntityCandidate] = []
        for raw in raw_entities:
            if isinstance(raw, str):
                candidates.append(_entity_from_values(raw, "TERM", chunk.confidence, chunk))
            elif isinstance(raw, dict) and raw.get("name"):
                candidates.append(
                    _entity_from_values(
                        raw["name"],
                        raw.get("type", "TERM"),
                        float(raw.get("confidence", chunk.confidence)),
                        chunk,
                    )
                )
        if candidates:
            return candidates

        names = sorted(set(re.findall(r"\b[A-Z][A-Za-z0-9]+(?:[- ][A-Z][A-Za-z0-9]+)*\b", chunk.content)))
        return [_entity_from_values(name, "TERM", chunk.confidence, chunk) for name in names[:25]]

    def extract_relationships(self, chunk: GraphChunkInput) -> list[GraphRelationshipCandidate]:
        raw_relationships = chunk.metadata.get("relationships") or []
        candidates: list[GraphRelationshipCandidate] = []
        for raw in raw_relationships:
            if not isinstance(raw, dict) or not raw.get("source") or not raw.get("target"):
                continue
            candidates.append(
                GraphRelationshipCandidate(
                    source_name=raw["source"],
                    target_name=raw["target"],
                    relationship_type=raw.get("type", "RELATED_TO"),
                    confidence=float(raw.get("confidence", chunk.confidence)),
                    provenance=_provenance(chunk),
                )
            )
        return candidates


def _entity_from_values(name: str, entity_type: str, confidence: float, chunk: GraphChunkInput) -> GraphEntityCandidate:
    return GraphEntityCandidate(
        name=name,
        entity_type=entity_type,
        confidence=confidence,
        provenance=_provenance(chunk),
    )


def _provenance(chunk: GraphChunkInput) -> dict[str, str]:
    return {"chunk_id": str(chunk.chunk_id), "document_id": str(chunk.document_id)}


def normalize_entity_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


class WikilinkDocumentLinkExtractor:
    """Extracts document-to-document LINKS_TO relationships from Obsidian wikilinks."""

    def extract_wikilink_links(self, chunk: GraphChunkInput) -> list[GraphRelationshipCandidate]:
        # Prefer explicit top-level wikilinks (from updated GraphChunkInput), fallback to metadata
        wikilinks = getattr(chunk, "wikilinks", None) or chunk.metadata.get("wikilinks") or []
        if not wikilinks:
            return []

        source_title = chunk.metadata.get("title") or str(chunk.document_id)
        source_name = f"DOC:{source_title}"

        candidates: list[GraphRelationshipCandidate] = []
        for wl in wikilinks:
            if not isinstance(wl, str) or not wl.strip():
                continue
            target_name = f"DOC:{wl.strip()}"
            candidates.append(
                GraphRelationshipCandidate(
                    source_name=source_name,
                    target_name=target_name,
                    relationship_type="LINKS_TO",
                    confidence=chunk.confidence,
                    provenance=_provenance(chunk),
                )
            )
        return candidates
