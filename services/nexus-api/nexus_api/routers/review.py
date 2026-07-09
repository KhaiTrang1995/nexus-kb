from __future__ import annotations

from fastapi import APIRouter, Depends

from nexus_api.auth.dependencies import get_current_user, require_privileged
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.dependencies import build_embedding_provider, build_repository, build_vector_client
from nexus_api.review import ReviewService
from nexus_shared.contracts import (
    ReviewActionRequest,
    ReviewActionResponse,
    ReviewItemRecord,
)

router = APIRouter(tags=["review"])


@router.get("/api/v1/review/queue", response_model=list[ReviewItemRecord])
def review_queue(
    limit: int = 50,
    offset: int = 0,
    min_confidence: float | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[ReviewItemRecord]:
    require_privileged(user)
    service = ReviewService(build_repository(), build_vector_client(), build_embedding_provider())
    return service.list_queue(limit=limit, offset=offset, min_confidence=min_confidence)


@router.post("/api/v1/review/action", response_model=ReviewActionResponse)
def review_action(
    request: ReviewActionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> ReviewActionResponse:
    require_privileged(user)
    service = ReviewService(build_repository(), build_vector_client(), build_embedding_provider())
    return service.apply_action(request, reviewer_id=user.id)
