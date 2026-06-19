"""EntityMerger — cross-type entity deduplication for incremental ingestion.

When ingesting multiple documents, the same real-world entity may appear with
different types in different chunks (e.g. "Qdrant" as TECHNOLOGY in one doc
and as TERM in another).  The repositories already merge entities with the same
(normalized_name, entity_type), but cross-type duplicates are stored separately.

EntityMerger resolves this before persistence:
  - Groups candidates by normalized name
  - Picks the dominant entity_type (highest confidence)
  - Merges provenance from all candidates with the same name
  - Returns a deduplicated list ready for upsert

Usage::
    from nexus_graph_builder.merger import EntityMerger
    merger = EntityMerger()
    merged = merger.merge(candidates)
"""
from __future__ import annotations

from nexus_graph_builder.extractor import normalize_entity_name
from nexus_shared.contracts import GraphEntityCandidate


class EntityMerger:
    """Merges entity candidates that share the same normalized name.

    Strategy options
    ----------------
    ``"dominant"`` (default)
        Keep the entity_type with the highest confidence. Merge provenance and
        take max confidence across all candidates with the same name.

    ``"strict"``
        No cross-type merging.  Candidates are returned unchanged (identical to
        not using the merger at all).  Useful for debugging or when entity_types
        are known to be high quality.
    """

    STRATEGIES = ("dominant", "strict")

    def __init__(self, strategy: str = "dominant") -> None:
        if strategy not in self.STRATEGIES:
            raise ValueError(f"strategy must be one of {self.STRATEGIES}, got {strategy!r}")
        self._strategy = strategy

    def merge(self, candidates: list[GraphEntityCandidate]) -> list[GraphEntityCandidate]:
        if self._strategy == "strict" or not candidates:
            return list(candidates)
        return self._dominant_merge(candidates)

    def _dominant_merge(self, candidates: list[GraphEntityCandidate]) -> list[GraphEntityCandidate]:
        # Group by normalized name
        groups: dict[str, list[GraphEntityCandidate]] = {}
        for cand in candidates:
            key = normalize_entity_name(cand.name)
            groups.setdefault(key, []).append(cand)

        merged: list[GraphEntityCandidate] = []
        for norm_name, group in groups.items():
            if len(group) == 1:
                merged.append(group[0])
                continue

            # Pick dominant: highest confidence → most representative name/type
            dominant = max(group, key=lambda c: c.confidence)
            # Merge provenance across all candidates in group
            merged_provenance = dominant.provenance.copy()
            for other in group:
                if other is dominant:
                    continue
                merged_provenance = _merge_provenance(merged_provenance, other.provenance)
            # Max confidence across all
            best_confidence = max(c.confidence for c in group)

            merged.append(
                GraphEntityCandidate(
                    name=dominant.name,
                    entity_type=dominant.entity_type,
                    confidence=best_confidence,
                    provenance=merged_provenance,
                )
            )
        return merged


def _merge_provenance(left: dict, right: dict) -> dict:
    """Merge two provenance dicts, accumulating list values for duplicate keys."""
    result = dict(left)
    for key, value in right.items():
        if key not in result:
            result[key] = value
            continue
        current = result[key]
        if current == value:
            continue
        values = current if isinstance(current, list) else [current]
        if isinstance(value, list):
            for v in value:
                if v not in values:
                    values.append(v)
        elif value not in values:
            values.append(value)
        result[key] = values
    return result
