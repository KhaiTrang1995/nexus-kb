from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from nexus_shared.contracts import GraphChunkInput, GraphEntityCandidate, GraphRelationshipCandidate

if TYPE_CHECKING:
    from nexus_llm_gateway import LLMGateway, LLMRequest
    from nexus_graph_builder.domain_template import DomainTemplateRegistry

logger = logging.getLogger(__name__)

_DEFAULT_ENTITY_TYPES = [
    "CONCEPT",
    "PERSON",
    "ORGANIZATION",
    "TECHNOLOGY",
    "PROCESS",
    "PRODUCT",
    "TERM",
]


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


class LLMEntityExtractor(MetadataEntityExtractor):
    """LLM-powered entity and relationship extractor.

    Replaces the regex fallback in MetadataEntityExtractor with a structured
    LLM prompt that returns typed entities and relationships as JSON. Falls back
    to the parent (metadata + regex) if the LLM call fails or gateway is None.

    Usage::
        from nexus_llm_gateway import LLMGateway, ModelRoute
        from nexus_graph_builder.domain_template import DomainTemplateRegistry
        gateway = LLMGateway(providers={...}, routes=[...], default_route=...)
        registry = DomainTemplateRegistry("data/domain-templates")
        extractor = LLMEntityExtractor(gateway=gateway, template_registry=registry, domain="software-engineering")
    """

    def __init__(
        self,
        gateway: "LLMGateway",
        entity_types: list[str] | None = None,
        min_confidence: float = 0.3,
        max_content_chars: int = 2000,
        template_registry: "DomainTemplateRegistry | None" = None,
        domain: str | None = None,
    ) -> None:
        self._gateway = gateway
        self._template_registry = template_registry
        self._domain = domain
        self._entity_types = entity_types  # explicit override takes priority over registry
        self._min_confidence = min_confidence
        self._max_content_chars = max_content_chars
        # per-chunk result cache keyed by chunk_id string — avoids two LLM calls per chunk
        self._cache: dict[str, tuple[list[GraphEntityCandidate], list[GraphRelationshipCandidate]]] = {}

    # ── Public interface ────────────────────────────────────────────────────

    def extract_entities(self, chunk: GraphChunkInput) -> list[GraphEntityCandidate]:
        entities, _ = self._get_or_extract(chunk)
        return entities

    def extract_relationships(self, chunk: GraphChunkInput) -> list[GraphRelationshipCandidate]:
        _, relationships = self._get_or_extract(chunk)
        return relationships

    # ── Internal ────────────────────────────────────────────────────────────

    def _get_or_extract(
        self, chunk: GraphChunkInput
    ) -> tuple[list[GraphEntityCandidate], list[GraphRelationshipCandidate]]:
        cache_key = str(chunk.chunk_id)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._llm_extract(chunk)
        return self._cache[cache_key]

    def _llm_extract(
        self, chunk: GraphChunkInput
    ) -> tuple[list[GraphEntityCandidate], list[GraphRelationshipCandidate]]:
        try:
            from nexus_llm_gateway import LLMRequest  # local import to keep optional dependency lazy

            request = LLMRequest(
                prompt=self._build_prompt(chunk),
                prompt_category="entity_extraction",
                task_type="entity_extraction",
                actor_id="graph-builder",
            )
            response = self._gateway.complete(request)
            return self._parse_response(response.text, chunk)
        except Exception as exc:
            logger.warning("LLMEntityExtractor fell back to metadata/regex for chunk %s: %s", chunk.chunk_id, exc)
            return (super().extract_entities(chunk), super().extract_relationships(chunk))

    def _resolved_entity_types(self) -> list[str]:
        if self._entity_types:
            return self._entity_types
        if self._template_registry and self._domain:
            return self._template_registry.entity_types_for(self._domain)
        return _DEFAULT_ENTITY_TYPES

    def _resolved_relationship_types(self) -> list[str]:
        if self._template_registry and self._domain:
            return self._template_registry.relationship_types_for(self._domain)
        return ["USES", "EXTENDS", "DEPENDS_ON", "PART_OF", "DESCRIBES", "RELATED_TO"]

    def _build_prompt(self, chunk: GraphChunkInput) -> str:
        entity_types_str = ", ".join(self._resolved_entity_types())
        rel_types_str = ", ".join(self._resolved_relationship_types())
        title = chunk.metadata.get("title", "")
        title_line = f"Document title: {title}\n" if title else ""
        domain_line = f"Domain: {self._domain}\n" if self._domain else ""
        content = chunk.content[: self._max_content_chars]
        return (
            "Extract named entities and semantic relationships from the text below.\n"
            f"{title_line}"
            f"{domain_line}"
            f"Entity types to detect: {entity_types_str}\n\n"
            "Return ONLY valid JSON — no markdown fences, no extra keys:\n"
            '{"entities":[{"name":"...","type":"...","confidence":0.0}],'
            '"relationships":[{"source":"...","target":"...","type":"...","confidence":0.0}]}\n\n'
            "Rules:\n"
            "- confidence range 0.0–1.0; omit entities with confidence < 0.3\n"
            f"- relationship type must be one of: {rel_types_str}\n"
            "- both 'source' and 'target' must be entity names from the entities list\n\n"
            f"TEXT:\n{content}"
        )

    def _parse_response(
        self, text: str, chunk: GraphChunkInput
    ) -> tuple[list[GraphEntityCandidate], list[GraphRelationshipCandidate]]:
        text = text.strip()
        # Strip markdown code block if LLM disobeys the prompt
        if text.startswith("```"):
            lines = text.splitlines()
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[1:end])

        data: dict = json.loads(text)
        prov = _provenance(chunk)

        entities: list[GraphEntityCandidate] = []
        for e in data.get("entities", []):
            name = (e.get("name") or "").strip()
            conf = float(e.get("confidence", chunk.confidence))
            if not name or conf < self._min_confidence:
                continue
            entities.append(
                GraphEntityCandidate(
                    name=name,
                    entity_type=e.get("type", "TERM"),
                    confidence=conf,
                    provenance=prov,
                )
            )

        entity_names = {e.name.lower() for e in entities}
        relationships: list[GraphRelationshipCandidate] = []
        for r in data.get("relationships", []):
            src = (r.get("source") or "").strip()
            tgt = (r.get("target") or "").strip()
            conf = float(r.get("confidence", chunk.confidence))
            if not src or not tgt or conf < self._min_confidence:
                continue
            # Only keep relationships where both sides were extracted as entities
            if src.lower() not in entity_names or tgt.lower() not in entity_names:
                continue
            relationships.append(
                GraphRelationshipCandidate(
                    source_name=src,
                    target_name=tgt,
                    relationship_type=r.get("type", "RELATED_TO"),
                    confidence=conf,
                    provenance=prov,
                )
            )

        return entities, relationships


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
