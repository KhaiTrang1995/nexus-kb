from __future__ import annotations

from fastapi import APIRouter, Depends

from nexus_api import tsx_bridge
from nexus_api.auth.dependencies import get_current_user, require_privileged
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.dependencies import build_embedding_provider, build_repository, build_vector_client
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_shared.contracts import IngestionRequest, IngestionResponse

router = APIRouter(tags=["ingestion"])


@router.post("/api/v1/ingest", response_model=IngestionResponse)
def ingest(
    request: IngestionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> IngestionResponse:
    require_privileged(user)
    tsx_bridge.intercept(
        action=f"Ingest document from {request.source_path}",
        context=f"source_type={request.source_type}",
    )

    pipeline = IngestionPipeline(
        repository=build_repository(),
        vector_client=build_vector_client(),
        embedding_provider=build_embedding_provider(),
    )
    result = pipeline.ingest(request.source_path, request.source_type)

    tsx_bridge.save_experience(
        title=f"Ingested: {request.source_path}",
        description=(
            f"Source: {request.source_path} | Type: {request.source_type}\n"
            f"Chunks: {getattr(result, 'chunk_count', '?')} | "
            f"Status: {getattr(result, 'status', 'ok')}"
        ),
        tags=["nexus-kb", "ingest", request.source_type],
    )
    return result
