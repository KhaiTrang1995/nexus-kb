from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from nexus_llm_gateway.providers import LLMProvider
from nexus_llm_gateway.schemas import LLMRequest, LLMResponse, ModelRoute, TelemetryRecord


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2


class LLMGateway:
    def __init__(
        self,
        providers: dict[str, LLMProvider],
        routes: list[ModelRoute],
        default_route: ModelRoute,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.providers = providers
        self.routes = {route.task_type: route for route in routes}
        self.default_route = default_route
        self.retry_policy = retry_policy or RetryPolicy()
        self.cache: dict[str, LLMResponse] = {}
        self.telemetry: list[TelemetryRecord] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        route = self.routes.get(request.task_type, self.default_route)
        cache_key = build_cache_key(request, route)
        cached = self.cache.get(cache_key)
        if cached is not None:
            response = cached.model_copy(update={"cached": True, "attempts": 0})
            self._record(request, route, response, status="SUCCESS")
            return response

        provider = self.providers[route.provider]
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                text = provider.complete(request, route.model)
                response = LLMResponse(
                    text=text,
                    model=route.model,
                    provider=route.provider,
                    cached=False,
                    attempts=attempt,
                )
                self.cache[cache_key] = response
                self._record(request, route, response, status="SUCCESS")
                return response
            except Exception as exc:
                last_error = exc

        response = LLMResponse(text="", model=route.model, provider=route.provider, cached=False, attempts=self.retry_policy.max_attempts)
        self._record(request, route, response, status="FAILURE", error=str(last_error))
        raise RuntimeError("llm provider failed after retries") from last_error

    def _record(
        self,
        request: LLMRequest,
        route: ModelRoute,
        response: LLMResponse,
        status: str,
        error: str | None = None,
    ) -> None:
        self.telemetry.append(
            TelemetryRecord(
                actor_id=request.actor_id,
                prompt_category=request.prompt_category,
                task_type=request.task_type,
                provider=route.provider,
                model=route.model,
                cached=response.cached,
                attempts=response.attempts,
                status=status,
                error=error,
            )
        )


def build_cache_key(request: LLMRequest, route: ModelRoute) -> str:
    payload = {
        "model": route.model,
        "provider": route.provider,
        "prompt": request.prompt,
        "prompt_category": request.prompt_category,
        "task_type": request.task_type,
        "parameters": request.parameters,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
