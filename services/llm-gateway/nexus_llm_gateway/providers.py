from __future__ import annotations

import hashlib
import json
import urllib.request
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


class OllamaProvider:
    """Calls a local Ollama server via its /api/generate REST endpoint."""

    provider_name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self._base_url = base_url.rstrip("/")

    def complete(self, request: LLMRequest, model: str) -> str:
        payload = json.dumps(
            {"model": model, "prompt": request.prompt, "stream": False}
        ).encode()
        req = urllib.request.Request(
            f"{self._base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            data = json.loads(resp.read())
            return data.get("response", "")


class OpenAIProvider:
    """Calls the OpenAI chat completions API (or any OpenAI-compatible endpoint)."""

    provider_name = "openai"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def complete(self, request: LLMRequest, model: str) -> str:
        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": request.prompt}],
                "temperature": 0,
            }
        ).encode()
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
