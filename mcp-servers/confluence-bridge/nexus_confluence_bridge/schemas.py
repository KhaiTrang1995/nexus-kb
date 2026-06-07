from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ActorContext(BaseModel):
    user_id: str
    roles: list[str] = Field(default_factory=list)
    allowed_spaces: list[str] = Field(default_factory=list)
    source_principal: str | None = None
    correlation_id: str | None = None


class SourceDiscoveryRequest(BaseModel):
    actor: ActorContext
    space_key: str
    limit: int = Field(default=25, ge=1, le=100)


class SourceReadRequest(BaseModel):
    actor: ActorContext
    page_id: str


class SourceDocumentSummary(BaseModel):
    source_id: str
    title: str
    space_key: str
    source_type: str = "confluence"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceDocument(SourceDocumentSummary):
    content: str
    content_hash: str


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCallResult(BaseModel):
    tool: str
    ok: bool
    result: Any | None = None
    error_code: str | None = None
    error_message: str | None = None
    correlation_id: str | None = None
