from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from nexus_api.auth.dependencies import get_current_user, require_admin
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.confluence_sync import ConfluenceSyncService
from nexus_api.config import get_settings
from nexus_api.dependencies import build_confluence_client, build_repository
from nexus_shared.contracts import SyncRunListResponse, SyncRunRecord, SyncRunTriggerRequest

router = APIRouter(tags=["confluence-sync"])


@router.post("/api/v1/confluence/sync", response_model=SyncRunRecord)
def trigger_sync(
    request: SyncRunTriggerRequest, user: AuthenticatedUser = Depends(get_current_user)
) -> SyncRunRecord:
    require_admin(user)
    client = build_confluence_client()
    if client is None:
        raise HTTPException(
            status_code=400,
            detail="Confluence chua duoc cau hinh (CONFLUENCE_BASE_URL / CONFLUENCE_API_TOKEN)",
        )
    repository = build_repository()
    if repository.get_workspace(request.workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    settings = get_settings()
    service = ConfluenceSyncService(
        repository=repository,
        confluence_client=client,
        staging_dir=settings.upload_staging_dir,
        max_attempts=settings.ingestion_job_max_attempts,
        page_limit=settings.confluence_sync_page_limit,
    )
    return service.sync(request.space_key, request.workspace_id, actor_id=user.id)


@router.get("/api/v1/confluence/sync-runs", response_model=SyncRunListResponse)
def list_sync_runs(
    workspace_id: UUID | None = None, user: AuthenticatedUser = Depends(get_current_user)
) -> SyncRunListResponse:
    require_admin(user)
    sync_runs = build_repository().list_sync_runs(workspace_id=workspace_id)
    return SyncRunListResponse(sync_runs=sync_runs)
