from __future__ import annotations

from fastapi import APIRouter, Depends

from nexus_api.auth.dependencies import get_current_user
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.dependencies import (
    build_embedding_provider,
    build_graph_repository,
    build_repository,
    build_vector_client,
)
from nexus_api.search import SearchService
from nexus_shared.contracts import SearchRequest, SearchResponse

router = APIRouter(tags=["search"])


@router.post("/api/v1/search", response_model=SearchResponse)
def search(
    request: SearchRequest, user: AuthenticatedUser = Depends(get_current_user)
) -> SearchResponse:
    service = SearchService(
        repository=build_repository(),
        vector_client=build_vector_client(),
        embedding_provider=build_embedding_provider(),
        graph_repository=build_graph_repository(),
    )
    workspace_ids = None if user.is_admin else user.workspace_ids
    return service.search(request, actor_id=user.id, workspace_ids=workspace_ids)
