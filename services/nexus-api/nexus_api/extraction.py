"""3-stage entity extraction pipeline for technical documentation."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Entity:
    text: str
    entity_type: str  # API | ENDPOINT | VERSION | CONCEPT | UNKNOWN
    start: int
    end: int


@dataclass
class Relationship:
    source: str
    target: str
    relationship_type: str  # CO_OCCURS | REFERENCES | DEPENDS_ON


@dataclass
class ExtractionResult:
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    text: str = ""


class EntityExtractor:
    """3-stage hybrid entity extraction pipeline.

    Stage 1 — Regex NER: detects known technical entity types
        (ENDPOINT, VERSION, API) via compiled regex patterns.
    Stage 2 — Noun-phrase heuristic: captures capitalized multi-word
        phrases as CONCEPT entities without requiring spaCy.
    Stage 3 — Relationship inference: emits CO_OCCURS / REFERENCES
        relationships for entity pairs whose start positions are within
        100 characters of each other.
    """

    # Stage 1: regex patterns for known technical entity types.
    # Ordered so that more-specific patterns are applied first.
    _PATTERNS: dict[str, re.Pattern[str]] = {
        "ENDPOINT": re.compile(
            r"(?:GET|POST|PUT|PATCH|DELETE)\s+/[\w/{}?=&.-]+",
            re.IGNORECASE,
        ),
        "VERSION": re.compile(r"\bv\d+(?:\.\d+){0,2}\b", re.IGNORECASE),
        "API": re.compile(r"\b[A-Z][a-zA-Z]+(?:API|Service|Client|SDK)\b"),
    }

    # Stage 2: capitalized multi-word noun phrase (title-case words).
    _NOUN_PHRASE: re.Pattern[str] = re.compile(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
    )

    # Stage 3: proximity window in characters.
    _PROXIMITY_WINDOW: int = 100

    def extract(self, text: str) -> ExtractionResult:
        """Run the full 3-stage pipeline on *text* and return an ExtractionResult."""
        result = ExtractionResult(text=text)

        if not text:
            return result

        # ── Stage 1: regex NER ───────────────────────────────────────────────
        seen_spans: list[tuple[int, int]] = []

        for etype, pattern in self._PATTERNS.items():
            for m in pattern.finditer(text):
                if not self._overlaps(m.start(), m.end(), seen_spans):
                    result.entities.append(
                        Entity(
                            text=m.group(),
                            entity_type=etype,
                            start=m.start(),
                            end=m.end(),
                        )
                    )
                    seen_spans.append((m.start(), m.end()))

        # ── Stage 2: noun-phrase heuristic ──────────────────────────────────
        for m in self._NOUN_PHRASE.finditer(text):
            if not self._overlaps(m.start(), m.end(), seen_spans):
                result.entities.append(
                    Entity(
                        text=m.group(),
                        entity_type="CONCEPT",
                        start=m.start(),
                        end=m.end(),
                    )
                )
                seen_spans.append((m.start(), m.end()))

        # ── Stage 3: relationship inference by proximity ─────────────────────
        entities = result.entities
        for i, a in enumerate(entities):
            for b in entities[i + 1 :]:
                if abs(a.start - b.start) < self._PROXIMITY_WINDOW:
                    rtype = (
                        "REFERENCES"
                        if a.entity_type == "ENDPOINT" or b.entity_type == "ENDPOINT"
                        else "CO_OCCURS"
                    )
                    result.relationships.append(
                        Relationship(
                            source=a.text,
                            target=b.text,
                            relationship_type=rtype,
                        )
                    )

        return result

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
        """Return True if [start, end) overlaps any span in *spans*."""
        return any(not (end <= s or start >= e) for s, e in spans)
