from __future__ import annotations

import unittest

from tests import _paths  # noqa: F401

from nexus_llm_gateway import (
    DeterministicLLMProvider,
    FailingThenSuccessProvider,
    LLMGateway,
    LLMRequest,
    ModelRoute,
    RetryPolicy,
)


class LLMGatewayTest(unittest.TestCase):
    def test_routes_requests_and_caches_by_prompt_category(self) -> None:
        gateway = LLMGateway(
            providers={"deterministic": DeterministicLLMProvider()},
            routes=[ModelRoute(task_type="extract", provider="deterministic", model="local-extractor")],
            default_route=ModelRoute(task_type="default", provider="deterministic", model="local-default"),
        )
        request = LLMRequest(
            prompt="Extract entities from synthetic text.",
            prompt_category="entity_extraction",
            task_type="extract",
            actor_id="worker",
        )

        first = gateway.complete(request)
        second = gateway.complete(request)

        self.assertEqual(first.model, "local-extractor")
        self.assertFalse(first.cached)
        self.assertTrue(second.cached)
        self.assertEqual(second.attempts, 0)
        self.assertEqual(gateway.telemetry[0].prompt_category, "entity_extraction")
        self.assertEqual(gateway.telemetry[1].cached, True)

    def test_retries_transient_provider_failures(self) -> None:
        provider = FailingThenSuccessProvider(failures=1)
        gateway = LLMGateway(
            providers={"retry-test": provider},
            routes=[],
            default_route=ModelRoute(task_type="default", provider="retry-test", model="retry-model"),
            retry_policy=RetryPolicy(max_attempts=2),
        )

        response = gateway.complete(LLMRequest(prompt="hello", prompt_category="test"))

        self.assertEqual(response.text, "retry-model:ok")
        self.assertEqual(response.attempts, 2)
        self.assertEqual(provider.calls, 2)

    def test_records_failure_telemetry_without_prompt_content(self) -> None:
        gateway = LLMGateway(
            providers={"retry-test": FailingThenSuccessProvider(failures=3)},
            routes=[],
            default_route=ModelRoute(task_type="default", provider="retry-test", model="retry-model"),
            retry_policy=RetryPolicy(max_attempts=2),
        )

        with self.assertRaises(RuntimeError):
            gateway.complete(LLMRequest(prompt="sensitive prompt content", prompt_category="test"))

        self.assertEqual(gateway.telemetry[-1].status, "FAILURE")
        self.assertNotIn("sensitive prompt content", gateway.telemetry[-1].model_dump_json())


if __name__ == "__main__":
    unittest.main()
