from __future__ import annotations

import hashlib
from typing import Protocol

from nexus_llm_gateway.schemas import LLMRequest


class LLMProvider(Protocol):
    provider_name: str

    def complete(self, request: LLMRequest, model: str) -> str:
        raise NotImplementedError


class DeterministicLLMProvider:
    provider_name = "deterministic"

    def complete(self, request: LLMRequest, model: str) -> str:
        digest = hashlib.sha256(f"{model}:{request.prompt}".encode("utf-8")).hexdigest()[:16]
        return f"{model}:{digest}"


class FailingThenSuccessProvider:
    provider_name = "retry-test"

    def __init__(self, failures: int = 1) -> None:
        self.failures = failures
        self.calls = 0

    def complete(self, request: LLMRequest, model: str) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("temporary provider failure")
        return f"{model}:ok"
