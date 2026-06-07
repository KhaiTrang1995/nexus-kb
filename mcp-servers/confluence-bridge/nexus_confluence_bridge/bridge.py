from __future__ import annotations

import hashlib
import re
from typing import Protocol

from nexus_confluence_bridge.schemas import (
    ActorContext,
    SourceDiscoveryRequest,
    SourceDocument,
    SourceDocumentSummary,
    SourceReadRequest,
    ToolCallResult,
    ToolDefinition,
)


READER_ROLE = "SourceReader"


class AuthorizationError(PermissionError):
    pass


class ConnectorError(RuntimeError):
    pass


class ConfluencePage(Protocol):
    id: str
    space_key: str
    title: str
    content: str


class ConfluenceClient(Protocol):
    def list_pages(self, space_key: str, limit: int) -> list[ConfluencePage]:
        raise NotImplementedError

    def get_page(self, page_id: str) -> ConfluencePage | None:
        raise NotImplementedError


class InMemoryConfluencePage:
    def __init__(self, id: str, space_key: str, title: str, content: str) -> None:
        self.id = id
        self.space_key = space_key
        self.title = title
        self.content = content


class InMemoryConfluenceClient:
    def __init__(self, pages: list[InMemoryConfluencePage] | None = None) -> None:
        self.pages = {page.id: page for page in pages or []}

    def list_pages(self, space_key: str, limit: int) -> list[InMemoryConfluencePage]:
        return [page for page in self.pages.values() if page.space_key == space_key][:limit]

    def get_page(self, page_id: str) -> InMemoryConfluencePage | None:
        return self.pages.get(page_id)


class ConfluenceBridge:
    def __init__(self, client: ConfluenceClient, mutating_tools_enabled: bool = False) -> None:
        self.client = client
        self.mutating_tools_enabled = mutating_tools_enabled

    def tool_definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="confluence.discover_sources",
                description="List readable Confluence pages in an authorized space.",
                input_schema=SourceDiscoveryRequest.model_json_schema(),
            ),
            ToolDefinition(
                name="confluence.read_document",
                description="Read one authorized Confluence page for ingestion.",
                input_schema=SourceReadRequest.model_json_schema(),
            ),
        ]

    def call_tool(self, name: str, payload: dict):
        try:
            if name == "confluence.discover_sources":
                return self.discover_sources(SourceDiscoveryRequest.model_validate(payload))
            if name == "confluence.read_document":
                return self.read_document(SourceReadRequest.model_validate(payload))
            if name.startswith("confluence.") and not self.mutating_tools_enabled:
                raise AuthorizationError("mutating confluence tools are disabled")
            raise ConnectorError(f"unsupported tool: {name}")
        except AuthorizationError:
            raise
        except Exception as exc:
            raise ConnectorError(sanitize_error(str(exc))) from exc

    def call_tool_result(self, name: str, payload: dict) -> ToolCallResult:
        correlation_id = extract_correlation_id(payload)
        try:
            result = self.call_tool(name, payload)
            return ToolCallResult(
                tool=name,
                ok=True,
                result=serialize_tool_result(result),
                correlation_id=correlation_id,
            )
        except AuthorizationError as exc:
            return ToolCallResult(
                tool=name,
                ok=False,
                error_code="AUTHORIZATION_DENIED",
                error_message=sanitize_error(str(exc)),
                correlation_id=correlation_id,
            )
        except ConnectorError as exc:
            return ToolCallResult(
                tool=name,
                ok=False,
                error_code="CONNECTOR_ERROR",
                error_message=sanitize_error(str(exc)),
                correlation_id=correlation_id,
            )

    def discover_sources(self, request: SourceDiscoveryRequest) -> list[SourceDocumentSummary]:
        authorize_space(request.actor, request.space_key)
        pages = self.client.list_pages(request.space_key, request.limit)
        return [
            SourceDocumentSummary(
                source_id=page.id,
                title=page.title,
                space_key=page.space_key,
                metadata={
                    "connector": "confluence",
                    "authorized_actor": request.actor.user_id,
                    "correlation_id": request.actor.correlation_id,
                },
            )
            for page in pages
        ]

    def read_document(self, request: SourceReadRequest) -> SourceDocument:
        page = self.client.get_page(request.page_id)
        if page is None:
            raise ConnectorError("source document not found")
        authorize_space(request.actor, page.space_key)
        return SourceDocument(
            source_id=page.id,
            title=page.title,
            space_key=page.space_key,
            content=page.content,
            content_hash=hashlib.sha256(page.content.encode("utf-8")).hexdigest(),
            metadata={
                "connector": "confluence",
                "authorized_actor": request.actor.user_id,
                "source_principal": request.actor.source_principal,
                "correlation_id": request.actor.correlation_id,
            },
        )


def authorize_space(actor: ActorContext, space_key: str) -> None:
    if READER_ROLE not in actor.roles or space_key not in actor.allowed_spaces:
        raise AuthorizationError("access denied for source space")


def sanitize_error(message: str) -> str:
    sanitized = re.sub(r"https?://[^\s]+", "[redacted-url]", message)
    sanitized = re.sub(r"(?i)(token|password|secret|apikey|api_key)=\S+", r"\1=[redacted]", sanitized)
    sanitized = re.sub(r"[\w.\-]+@[\w.\-]+", "[redacted-email]", sanitized)
    return sanitized


def extract_correlation_id(payload: dict) -> str | None:
    actor = payload.get("actor") if isinstance(payload, dict) else None
    if not isinstance(actor, dict):
        return None
    value = actor.get("correlation_id")
    return str(value) if value else None


def serialize_tool_result(result):
    if isinstance(result, list):
        return [serialize_tool_result(item) for item in result]
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result
