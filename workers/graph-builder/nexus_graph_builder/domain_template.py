"""DomainTemplate — YAML-driven entity/relationship type config for LLMEntityExtractor.

Usage::
    registry = DomainTemplateRegistry("data/domain-templates")
    types = registry.entity_types_for("software-engineering")
    # → ["TECHNOLOGY", "FRAMEWORK", "LIBRARY", "API", "CONCEPT", "PROCESS", "TERM"]

Templates live in *.yaml files under the configured directory.
Falls back to DEFAULT_ENTITY_TYPES / DEFAULT_RELATIONSHIP_TYPES when no template matches.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_ENTITY_TYPES: list[str] = [
    "CONCEPT",
    "PERSON",
    "ORGANIZATION",
    "TECHNOLOGY",
    "PROCESS",
    "PRODUCT",
    "TERM",
]

DEFAULT_RELATIONSHIP_TYPES: list[str] = [
    "USES",
    "EXTENDS",
    "DEPENDS_ON",
    "PART_OF",
    "DESCRIBES",
    "RELATED_TO",
]


@dataclass
class DomainTemplate:
    domain: str
    entity_types: list[str] = field(default_factory=list)
    relationship_types: list[str] = field(default_factory=list)
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DomainTemplate":
        return cls(
            domain=str(data["domain"]),
            entity_types=[str(t) for t in data.get("entity_types", [])],
            relationship_types=[str(t) for t in data.get("relationship_types", [])],
            description=str(data.get("description", "")),
        )

    @classmethod
    def from_yaml(cls, path: Path) -> "DomainTemplate":
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict) or "domain" not in data:
            raise ValueError(f"Missing required 'domain' key in {path}")
        return cls.from_dict(data)


class DomainTemplateRegistry:
    """Loads and indexes DomainTemplate instances from a directory of YAML files."""

    def __init__(self, templates_dir: Path | str) -> None:
        self._templates: dict[str, DomainTemplate] = {}
        self._load(Path(templates_dir))

    def _load(self, templates_dir: Path) -> None:
        if not templates_dir.is_dir():
            logger.warning("DomainTemplateRegistry: directory not found: %s", templates_dir)
            return
        for yaml_file in sorted(templates_dir.glob("*.yaml")):
            try:
                template = DomainTemplate.from_yaml(yaml_file)
                self._templates[template.domain] = template
                logger.debug("Loaded domain template: %s", template.domain)
            except Exception as exc:
                logger.warning("Skipping malformed template %s: %s", yaml_file.name, exc)

    def get(self, domain: str) -> DomainTemplate | None:
        return self._templates.get(domain)

    def entity_types_for(self, domain: str) -> list[str]:
        template = self._templates.get(domain)
        return template.entity_types if template and template.entity_types else DEFAULT_ENTITY_TYPES

    def relationship_types_for(self, domain: str) -> list[str]:
        template = self._templates.get(domain)
        return template.relationship_types if template and template.relationship_types else DEFAULT_RELATIONSHIP_TYPES

    def domains(self) -> list[str]:
        return list(self._templates.keys())

    def __len__(self) -> int:
        return len(self._templates)
