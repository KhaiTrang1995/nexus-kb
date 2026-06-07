from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    prompt: str
    prompt_category: str
    task_type: str = "default"
    actor_id: str = "system"
    parameters: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    text: str
    model: str
    provider: str
    cached: bool = False
    attempts: int = 1


class ModelRoute(BaseModel):
    task_type: str
    provider: str
    model: str


class TelemetryRecord(BaseModel):
    actor_id: str
    prompt_category: str
    task_type: str
    provider: str
    model: str
    cached: bool
    attempts: int
    status: str
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
