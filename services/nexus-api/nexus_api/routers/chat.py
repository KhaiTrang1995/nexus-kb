from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from nexus_api.auth.dependencies import get_current_user
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.dependencies import (
    build_embedding_provider,
    build_graph_repository,
    build_llm_gateway,
    build_repository,
    build_vector_client,
)
from nexus_api.rag import RagService, RagUnavailable
from nexus_api.search import SearchService
from nexus_shared.contracts import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/api/v1/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest, user: AuthenticatedUser = Depends(get_current_user)
) -> ChatResponse:
    search_service = SearchService(
        repository=build_repository(),
        vector_client=build_vector_client(),
        embedding_provider=build_embedding_provider(),
        graph_repository=build_graph_repository(),
    )
    service = RagService(search_service=search_service, llm_gateway=build_llm_gateway())
    workspace_ids = None if user.is_admin else user.workspace_ids
    try:
        return service.ask(request, actor_id=user.id, workspace_ids=workspace_ids)
    except RagUnavailable as exc:
        raise HTTPException(status_code=503, detail=exc.message) from None
