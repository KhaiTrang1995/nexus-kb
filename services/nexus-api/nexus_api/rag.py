from __future__ import annotations

from nexus_api.search import SearchService
from nexus_shared.contracts import AuditStatus, ChatCitation, ChatRequest, ChatResponse, SearchRequest

NO_CONTEXT_ANSWER = "Khong tim thay tai lieu lien quan de tra loi cau hoi nay."
LLM_UNAVAILABLE_MESSAGE = "Tro ly AI tam thoi gian doan. Ban van co the tim kiem theo tai lieu."


class RagUnavailable(Exception):
    def __init__(self, message: str = LLM_UNAVAILABLE_MESSAGE) -> None:
        super().__init__(message)
        self.message = message


class RagService:
    """Retrieval-augmented chat: reuses SearchService's already-workspace-filtered
    results as context, then calls the LLM gateway. Plain search keeps working
    even when this fails -- callers hit /api/v1/search directly for that."""

    def __init__(self, search_service: SearchService, llm_gateway) -> None:
        self.search_service = search_service
        self.llm_gateway = llm_gateway

    def ask(
        self,
        request: ChatRequest,
        actor_id: str,
        workspace_ids: list[str] | None,
    ) -> ChatResponse:
        search_response = self.search_service.search(
            SearchRequest(query=request.query, limit=request.limit),
            actor_id=actor_id,
            workspace_ids=workspace_ids,
        )

        if not search_response.results:
            self._audit(actor_id, request, citation_count=0, answered=False)
            return ChatResponse(answer=NO_CONTEXT_ANSWER, citations=[])

        if self.llm_gateway is None:
            raise RagUnavailable()

        context_block = "\n\n".join(
            f"[{index + 1}] {result.title}: {result.snippet}"
            for index, result in enumerate(search_response.results)
        )
        prompt = (
            "Tra loi cau hoi sau bang tieng Viet, chi dua tren ngu canh duoi day. "
            "Neu ngu canh khong du thong tin, noi ro la khong biet.\n\n"
            f"Ngu canh:\n{context_block}\n\nCau hoi: {request.query}"
        )

        from nexus_llm_gateway.schemas import LLMRequest

        try:
            llm_response = self.llm_gateway.complete(
                LLMRequest(prompt=prompt, prompt_category="rag_answer", task_type="chat", actor_id=actor_id)
            )
        except Exception as exc:
            raise RagUnavailable() from exc

        citations = [
            ChatCitation(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                title=result.title,
                document_version=result.document_version,
                snippet=result.snippet,
            )
            for result in search_response.results
        ]
        self._audit(actor_id, request, citation_count=len(citations), answered=True)
        return ChatResponse(answer=llm_response.text, citations=citations)

    def _audit(self, actor_id: str, request: ChatRequest, citation_count: int, answered: bool) -> None:
        # Never log the raw query/answer text -- only shape/size, matching the
        # existing audit convention (no raw document content in details).
        self.search_service.repository.record_audit_log(
            actor_id=actor_id,
            action="CHAT_QUERY",
            status=AuditStatus.SUCCESS,
            details={
                "query_length": len(request.query),
                "citation_count": citation_count,
                "answered": answered,
            },
        )
