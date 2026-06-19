"""HyperedgeExtractor — LLM-powered n-ary relationship extraction.

A hyperedge is a single fact that connects 3 or more entities at once, e.g.
"FastAPI relies on Pydantic and Starlette for validation and routing" captures
one fact involving three entities instead of two binary edges.

Usage::
    from nexus_graph_builder.hyperedge_extractor import HyperedgeExtractor
    extractor = HyperedgeExtractor(gateway=llm_gateway, min_members=3)
    candidates = extractor.extract(chunk)
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from nexus_shared.contracts import GraphChunkInput, HyperedgeCandidate

if TYPE_CHECKING:
    from nexus_llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
Identify n-ary facts in the text — relationships that link 3 or more distinct entities in a single statement.
Return ONLY valid JSON, no markdown fences:
{{"hyperedges":[{{"entities":["A","B","C"],"type":"...","label":"...","confidence":0.0}}]}}

Rules:
- "entities" must contain 3 or more distinct names
- "type": INVOLVES, COLLABORATES_ON, CO_USES, CO_PRODUCES, GOVERNS, COMPETES_WITH, or RELATED_TO
- "label": one short sentence describing the shared fact
- "confidence": 0.0–1.0; omit hyperedges with confidence < 0.3
- Extract only facts where the n-ary nature is semantically meaningful (not just co-occurrence)
- Return {{"hyperedges":[]}} when no n-ary facts exist

TEXT:
{content}"""


class HyperedgeExtractor:
    """Extracts n-ary (3+) entity relationships from text using an LLM.

    Falls back to an empty list when the gateway is unavailable or the LLM
    response cannot be parsed — hyperedges are a best-effort enrichment.
    """

    def __init__(
        self,
        gateway: "LLMGateway",
        min_members: int = 3,
        min_confidence: float = 0.3,
        max_content_chars: int = 2000,
    ) -> None:
        if min_members < 2:
            raise ValueError("min_members must be >= 2")
        self._gateway = gateway
        self._min_members = min_members
        self._min_confidence = min_confidence
        self._max_content_chars = max_content_chars
        self._cache: dict[str, list[HyperedgeCandidate]] = {}

    def extract(self, chunk: GraphChunkInput) -> list[HyperedgeCandidate]:
        """Return hyperedge candidates for the chunk, using a per-chunk cache."""
        cache_key = str(chunk.chunk_id)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._llm_extract(chunk)
        return self._cache[cache_key]

    # ── Internal ────────────────────────────────────────────────────────────

    def _llm_extract(self, chunk: GraphChunkInput) -> list[HyperedgeCandidate]:
        try:
            from nexus_llm_gateway import LLMRequest

            content = chunk.content[: self._max_content_chars]
            request = LLMRequest(
                prompt=_PROMPT_TEMPLATE.format(content=content),
                prompt_category="hyperedge_extraction",
                task_type="hyperedge_extraction",
                actor_id="graph-builder",
            )
            response = self._gateway.complete(request)
            return self._parse(response.text, chunk)
        except Exception as exc:
            logger.warning("HyperedgeExtractor failed for chunk %s: %s", chunk.chunk_id, exc)
            return []

    def _parse(self, text: str, chunk: GraphChunkInput) -> list[HyperedgeCandidate]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[1:end])

        data: dict = json.loads(text)
        prov = {"chunk_id": str(chunk.chunk_id), "document_id": str(chunk.document_id)}
        candidates: list[HyperedgeCandidate] = []

        for h in data.get("hyperedges", []):
            names: list[str] = [str(n).strip() for n in h.get("entities", []) if str(n).strip()]
            conf = float(h.get("confidence", chunk.confidence))
            if len(set(names)) < self._min_members or conf < self._min_confidence:
                continue
            candidates.append(
                HyperedgeCandidate(
                    entity_names=names,
                    relationship_type=h.get("type", "INVOLVES"),
                    label=str(h.get("label", "")),
                    confidence=conf,
                    provenance=prov,
                )
            )
        return candidates
