from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from nexus_confluence_bridge.bridge import sanitize_error
from nexus_knowledge_mcp.auth import ActorResolutionError, TokenVerifier
from nexus_knowledge_mcp.schemas import (
    AskKnowledgeArgs,
    ListDocumentsArgs,
    McpActorContext,
    SearchKnowledgeArgs,
    ToolCallResult,
    ToolDefinition,
)


class KnowledgeSearchService(Protocol):
    def search(self, request, actor_id: str, workspace_ids: list[str] | None):
        raise NotImplementedError


class KnowledgeRagService(Protocol):
    def ask(self, request, actor_id: str, workspace_ids: list[str] | None):
        raise NotImplementedError


class KnowledgeRepository(Protocol):
    def list_documents_in_workspaces(self, workspace_ids: list[UUID] | None, limit: int):
        raise NotImplementedError

    def record_audit_log(self, actor_id: str, action: str, status, resource_id=None, details=None) -> None:
        raise NotImplementedError


class ConnectorError(RuntimeError):
    pass


class NexusKnowledgeBridge:
    """Read-only MCP surface for AI agents connecting via the MCP Gateway.

    Deliberately thin: every tool delegates to the *same* SearchService /
    RagService the web console's REST API uses, so an agent can never see
    more (or less) than a logged-in user would -- no separate retrieval
    path, no bypass of workspace/publish filtering.
    """

    def __init__(
        self,
        token_verifier: TokenVerifier,
        search_service: KnowledgeSearchService,
        rag_service: KnowledgeRagService,
        repository: KnowledgeRepository,
    ) -> None:
        self.token_verifier = token_verifier
        self.search_service = search_service
        self.rag_service = rag_service
        self.repository = repository

    def tool_definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="search_knowledge",
                description="Search the indexed, published knowledge base (workspace-scoped).",
                input_schema=SearchKnowledgeArgs.model_json_schema(),
            ),
            ToolDefinition(
                name="ask_knowledge",
                description="Ask a question answered from the indexed knowledge base, with citations.",
                input_schema=AskKnowledgeArgs.model_json_schema(),
            ),
            ToolDefinition(
                name="list_documents",
                description="List published documents visible to the caller's workspaces.",
                input_schema=ListDocumentsArgs.model_json_schema(),
            ),
        ]

    def call_tool(self, name: str, token: str, arguments: dict[str, Any]):
        actor = self.token_verifier.verify(token)
        if name == "search_knowledge":
            return self._search_knowledge(actor, SearchKnowledgeArgs.model_validate(arguments))
        if name == "ask_knowledge":
            return self._ask_knowledge(actor, AskKnowledgeArgs.model_validate(arguments))
        if name == "list_documents":
            return self._list_documents(actor, ListDocumentsArgs.model_validate(arguments))
        raise ConnectorError(f"unsupported tool: {name}")

    def call_tool_result(self, envelope) -> ToolCallResult:
        try:
            result = self.call_tool(envelope.tool, envelope.token, envelope.arguments)
            return ToolCallResult(
                tool=envelope.tool,
                ok=True,
                result=serialize_tool_result(result),
                correlation_id=envelope.correlation_id,
            )
        except ActorResolutionError as exc:
            return ToolCallResult(
                tool=envelope.tool,
                ok=False,
                error_code="AUTHORIZATION_DENIED",
                error_message=sanitize_error(str(exc)),
                correlation_id=envelope.correlation_id,
            )
        except Exception as exc:
            return ToolCallResult(
                tool=envelope.tool,
                ok=False,
                error_code="CONNECTOR_ERROR",
                error_message=sanitize_error(str(exc)),
                correlation_id=envelope.correlation_id,
            )

    def _workspace_scope(self, actor: McpActorContext) -> list[str] | None:
        return None if actor.is_admin else actor.workspace_ids

    def _search_knowledge(self, actor: McpActorContext, args: SearchKnowledgeArgs):
        from nexus_shared.contracts import SearchRequest

        response = self.search_service.search(
            SearchRequest(query=args.query, limit=args.limit),
            actor_id=actor.user_id,
            workspace_ids=self._workspace_scope(actor),
        )
        self._log_usage(actor, "search_knowledge", {"query_length": len(args.query)})
        return response

    def _ask_knowledge(self, actor: McpActorContext, args: AskKnowledgeArgs):
        from nexus_shared.contracts import ChatRequest

        response = self.rag_service.ask(
            ChatRequest(query=args.query, limit=args.limit),
            actor_id=actor.user_id,
            workspace_ids=self._workspace_scope(actor),
        )
        self._log_usage(actor, "ask_knowledge", {"query_length": len(args.query)})
        return response

    def _list_documents(self, actor: McpActorContext, args: ListDocumentsArgs):
        workspace_ids = (
            None if actor.is_admin else [UUID(workspace_id) for workspace_id in actor.workspace_ids]
        )
        documents = self.repository.list_documents_in_workspaces(workspace_ids, limit=args.limit)
        self._log_usage(actor, "list_documents", {"result_count": len(documents)})
        return documents

    def _log_usage(self, actor: McpActorContext, tool: str, details: dict) -> None:
        from nexus_shared.contracts import AuditStatus

        self.repository.record_audit_log(
            actor_id=f"mcp:{actor.user_id}",
            action="MCP_TOOL_CALL",
            status=AuditStatus.SUCCESS,
            details={"tool": tool, **details},
        )


def serialize_tool_result(result: Any) -> Any:
    if isinstance(result, list):
        return [serialize_tool_result(item) for item in result]
    if hasattr(result, "model_dump"):
        # mode="json" so UUID/datetime fields (SearchResponse, ChatResponse,
        # DocumentRecord all carry them) come out as JSON-safe strings.
        return result.model_dump(mode="json")
    return result
