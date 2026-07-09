from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class McpActorContext(BaseModel):
    """Resolved from a verified token -- never trust a client-supplied actor
    object directly (unlike the Confluence bridge, which is called by an
    already-authenticated internal caller)."""

    user_id: str
    is_admin: bool = False
    workspace_ids: list[str] = Field(default_factory=list)


class ToolCallEnvelope(BaseModel):
    tool: str
    token: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class AskKnowledgeArgs(BaseModel):
    query: str = Field(max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class ListDocumentsArgs(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)


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
