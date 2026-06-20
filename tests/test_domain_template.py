"""Tests for DomainTemplate and DomainTemplateRegistry — Phase 6 Step 2."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import tests._paths  # noqa: F401

from nexus_graph_builder import (
    DEFAULT_ENTITY_TYPES,
    DEFAULT_RELATIONSHIP_TYPES,
    DomainTemplate,
    DomainTemplateRegistry,
    LLMEntityExtractor,
    InMemoryGraphRepository,
    GraphBuilder,
)
from nexus_llm_gateway import LLMGateway, LLMRequest, ModelRoute
from nexus_shared.contracts import GraphChunkInput


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_yaml(directory: Path, filename: str, content: str) -> Path:
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


def _chunk(content: str = "FastAPI uses Pydantic.", domain: str | None = None) -> GraphChunkInput:
    meta: dict = {}
    if domain:
        meta["domain"] = domain
    return GraphChunkInput(chunk_id=uuid4(), document_id=uuid4(), content=content, metadata=meta)


# ── DomainTemplate unit tests ──────────────────────────────────────────────────

class DomainTemplateTest(unittest.TestCase):

    def test_from_dict_populates_all_fields(self) -> None:
        data = {
            "domain": "software-engineering",
            "description": "Tech domain",
            "entity_types": ["TECHNOLOGY", "CONCEPT"],
            "relationship_types": ["USES", "EXTENDS"],
        }
        t = DomainTemplate.from_dict(data)
        self.assertEqual(t.domain, "software-engineering")
        self.assertEqual(t.description, "Tech domain")
        self.assertEqual(t.entity_types, ["TECHNOLOGY", "CONCEPT"])
        self.assertEqual(t.relationship_types, ["USES", "EXTENDS"])

    def test_from_dict_defaults_empty_lists(self) -> None:
        t = DomainTemplate.from_dict({"domain": "general"})
        self.assertEqual(t.entity_types, [])
        self.assertEqual(t.relationship_types, [])
        self.assertEqual(t.description, "")

    def test_from_yaml_loads_file_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            yaml_text = (
                "domain: test-domain\n"
                "description: Test\n"
                "entity_types:\n  - TERM\n  - PERSON\n"
                "relationship_types:\n  - RELATED_TO\n"
            )
            path = _write_yaml(Path(tmp), "test-domain.yaml", yaml_text)
            t = DomainTemplate.from_yaml(path)
        self.assertEqual(t.domain, "test-domain")
        self.assertIn("TERM", t.entity_types)
        self.assertIn("PERSON", t.entity_types)
        self.assertEqual(t.relationship_types, ["RELATED_TO"])

    def test_from_yaml_raises_when_domain_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_yaml(Path(tmp), "bad.yaml", "entity_types:\n  - TERM\n")
            with self.assertRaises(ValueError):
                DomainTemplate.from_yaml(path)


# ── DomainTemplateRegistry unit tests ─────────────────────────────────────────

class DomainTemplateRegistryTest(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_registry(self, templates: dict[str, str]) -> DomainTemplateRegistry:
        for filename, content in templates.items():
            _write_yaml(self.tmp_dir, filename, content)
        return DomainTemplateRegistry(self.tmp_dir)

    def test_loads_all_yaml_files_from_directory(self) -> None:
        registry = self._make_registry({
            "a.yaml": "domain: alpha\nentity_types:\n  - TERM\nrelationship_types:\n  - RELATED_TO\n",
            "b.yaml": "domain: beta\nentity_types:\n  - CONCEPT\nrelationship_types:\n  - USES\n",
        })
        self.assertEqual(len(registry), 2)
        self.assertIn("alpha", registry.domains())
        self.assertIn("beta", registry.domains())

    def test_entity_types_for_returns_template_types(self) -> None:
        registry = self._make_registry({
            "sw.yaml": "domain: software\nentity_types:\n  - TECHNOLOGY\n  - FRAMEWORK\nrelationship_types:\n  - USES\n",
        })
        types = registry.entity_types_for("software")
        self.assertEqual(types, ["TECHNOLOGY", "FRAMEWORK"])

    def test_entity_types_for_falls_back_to_defaults_on_unknown_domain(self) -> None:
        registry = self._make_registry({})
        types = registry.entity_types_for("nonexistent")
        self.assertEqual(types, DEFAULT_ENTITY_TYPES)

    def test_relationship_types_for_returns_template_types(self) -> None:
        registry = self._make_registry({
            "sw.yaml": "domain: software\nentity_types:\n  - TERM\nrelationship_types:\n  - USES\n  - EXTENDS\n",
        })
        types = registry.relationship_types_for("software")
        self.assertEqual(types, ["USES", "EXTENDS"])

    def test_relationship_types_for_falls_back_to_defaults(self) -> None:
        registry = self._make_registry({})
        types = registry.relationship_types_for("unknown")
        self.assertEqual(types, DEFAULT_RELATIONSHIP_TYPES)

    def test_skips_malformed_yaml_files_without_crashing(self) -> None:
        registry = self._make_registry({
            "good.yaml": "domain: good\nentity_types:\n  - TERM\nrelationship_types:\n  - RELATED_TO\n",
            "bad.yaml": "entity_types:\n  - TERM\n",  # missing domain
        })
        self.assertEqual(len(registry), 1)
        self.assertIn("good", registry.domains())

    def test_nonexistent_directory_creates_empty_registry(self) -> None:
        registry = DomainTemplateRegistry("/nonexistent/path/to/templates")
        self.assertEqual(len(registry), 0)
        self.assertEqual(registry.domains(), [])

    def test_get_returns_none_for_unknown_domain(self) -> None:
        registry = self._make_registry({})
        self.assertIsNone(registry.get("mystery"))

    def test_get_returns_template_for_known_domain(self) -> None:
        registry = self._make_registry({
            "sw.yaml": "domain: software\nentity_types:\n  - TERM\nrelationship_types:\n  - USES\n",
        })
        template = registry.get("software")
        self.assertIsNotNone(template)
        assert template is not None
        self.assertEqual(template.domain, "software")

    def test_loads_real_software_engineering_template(self) -> None:
        # Test against the actual template shipped with nexus-kb
        templates_dir = Path(__file__).resolve().parents[1] / "data" / "domain-templates"
        if not templates_dir.is_dir():
            self.skipTest("data/domain-templates not found")
        registry = DomainTemplateRegistry(templates_dir)
        self.assertIn("software-engineering", registry.domains())
        types = registry.entity_types_for("software-engineering")
        self.assertIn("TECHNOLOGY", types)
        self.assertIn("FRAMEWORK", types)

    def test_loads_all_five_shipped_templates(self) -> None:
        templates_dir = Path(__file__).resolve().parents[1] / "data" / "domain-templates"
        if not templates_dir.is_dir():
            self.skipTest("data/domain-templates not found")
        registry = DomainTemplateRegistry(templates_dir)
        expected = {"software-engineering", "knowledge-management", "research-science", "business-process", "general"}
        self.assertEqual(expected, set(registry.domains()))


# ── LLMEntityExtractor + DomainTemplateRegistry integration ───────────────────

class _PromptCaptureProvider:
    """Records the prompt text so tests can inspect it."""
    provider_name = "capture"

    def __init__(self, payload: dict) -> None:
        self._text = json.dumps(payload)
        self.captured_prompts: list[str] = []

    def complete(self, request: LLMRequest, model: str) -> str:
        self.captured_prompts.append(request.prompt)
        return self._text


def _make_gateway(provider) -> LLMGateway:
    return LLMGateway(
        providers={provider.provider_name: provider},
        routes=[ModelRoute(task_type="entity_extraction", provider=provider.provider_name, model="test-model")],
        default_route=ModelRoute(task_type="default", provider=provider.provider_name, model="test-model"),
    )


class LLMEntityExtractorDomainTest(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_registry(self, entity_types: list[str], rel_types: list[str], domain: str = "test-domain") -> DomainTemplateRegistry:
        yaml_content = (
            f"domain: {domain}\n"
            "entity_types:\n" + "".join(f"  - {t}\n" for t in entity_types) +
            "relationship_types:\n" + "".join(f"  - {t}\n" for t in rel_types)
        )
        _write_yaml(self.tmp_dir, f"{domain}.yaml", yaml_content)
        return DomainTemplateRegistry(self.tmp_dir)

    def test_prompt_includes_domain_entity_types_from_registry(self) -> None:
        registry = self._make_registry(["DATASET", "RESEARCHER"], ["CITES"], "research-science")
        payload = {"entities": [], "relationships": []}
        provider = _PromptCaptureProvider(payload)
        extractor = LLMEntityExtractor(
            gateway=_make_gateway(provider),
            template_registry=registry,
            domain="research-science",
        )
        extractor.extract_entities(_chunk())
        prompt = provider.captured_prompts[0]
        self.assertIn("DATASET", prompt)
        self.assertIn("RESEARCHER", prompt)

    def test_prompt_includes_domain_relationship_types_from_registry(self) -> None:
        registry = self._make_registry(["TERM"], ["CONTRADICTS", "SUPPORTS"], "research")
        payload = {"entities": [], "relationships": []}
        provider = _PromptCaptureProvider(payload)
        extractor = LLMEntityExtractor(
            gateway=_make_gateway(provider),
            template_registry=registry,
            domain="research",
        )
        extractor.extract_entities(_chunk())
        prompt = provider.captured_prompts[0]
        self.assertIn("CONTRADICTS", prompt)
        self.assertIn("SUPPORTS", prompt)

    def test_prompt_includes_domain_name_when_set(self) -> None:
        registry = self._make_registry(["TERM"], ["RELATED_TO"])
        payload = {"entities": [], "relationships": []}
        provider = _PromptCaptureProvider(payload)
        extractor = LLMEntityExtractor(
            gateway=_make_gateway(provider),
            template_registry=registry,
            domain="test-domain",
        )
        extractor.extract_entities(_chunk())
        self.assertIn("test-domain", provider.captured_prompts[0])

    def test_explicit_entity_types_override_registry(self) -> None:
        registry = self._make_registry(["DATASET"], ["CITES"])
        payload = {"entities": [], "relationships": []}
        provider = _PromptCaptureProvider(payload)
        extractor = LLMEntityExtractor(
            gateway=_make_gateway(provider),
            entity_types=["OVERRIDE_TYPE"],  # explicit override
            template_registry=registry,
            domain="test-domain",
        )
        extractor.extract_entities(_chunk())
        prompt = provider.captured_prompts[0]
        self.assertIn("OVERRIDE_TYPE", prompt)
        self.assertNotIn("DATASET", prompt)

    def test_falls_back_to_defaults_when_no_registry(self) -> None:
        payload = {"entities": [], "relationships": []}
        provider = _PromptCaptureProvider(payload)
        extractor = LLMEntityExtractor(gateway=_make_gateway(provider))
        extractor.extract_entities(_chunk())
        prompt = provider.captured_prompts[0]
        for entity_type in DEFAULT_ENTITY_TYPES:
            self.assertIn(entity_type, prompt)


if __name__ == "__main__":
    unittest.main()
