from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from nexus_api.auth.dependencies import get_current_user, require_admin
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.dependencies import build_repository
from nexus_shared.contracts import (
    AuditStatus,
    WorkspaceCreateRequest,
    WorkspaceListResponse,
    WorkspaceMemberAddRequest,
    WorkspaceMemberListResponse,
    WorkspaceMemberRecord,
    WorkspaceRecord,
)

router = APIRouter(tags=["workspaces"])


@router.get("/api/v1/workspaces", response_model=WorkspaceListResponse)
def list_workspaces(user: AuthenticatedUser = Depends(get_current_user)) -> WorkspaceListResponse:
    workspaces = build_repository().list_workspaces()
    if not user.is_admin:
        workspaces = [w for w in workspaces if str(w.id) in user.workspace_ids]
    return WorkspaceListResponse(workspaces=workspaces)


@router.post("/api/v1/workspaces", response_model=WorkspaceRecord)
def create_workspace(
    request: WorkspaceCreateRequest, user: AuthenticatedUser = Depends(get_current_user)
) -> WorkspaceRecord:
    require_admin(user)
    repository = build_repository()
    workspace = repository.create_workspace(request.name, request.slug)
    repository.record_audit_log(
        actor_id=user.id,
        action="WORKSPACE_CREATED",
        status=AuditStatus.SUCCESS,
        resource_id=workspace.id,
        details={"name": workspace.name, "slug": workspace.slug},
    )
    return workspace


@router.get("/api/v1/workspaces/{workspace_id}/members", response_model=WorkspaceMemberListResponse)
def list_workspace_members(
    workspace_id: UUID, user: AuthenticatedUser = Depends(get_current_user)
) -> WorkspaceMemberListResponse:
    if not user.is_admin and str(workspace_id) not in user.workspace_ids:
        raise HTTPException(status_code=403, detail="No access to this workspace")
    members = build_repository().list_workspace_members(workspace_id)
    return WorkspaceMemberListResponse(workspace_id=workspace_id, members=members)


@router.post("/api/v1/workspaces/{workspace_id}/members", response_model=WorkspaceMemberRecord)
def add_workspace_member(
    workspace_id: UUID, request: WorkspaceMemberAddRequest, user: AuthenticatedUser = Depends(get_current_user)
) -> WorkspaceMemberRecord:
    require_admin(user)
    repository = build_repository()
    if repository.get_workspace(workspace_id) is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    member = repository.add_workspace_member(workspace_id, request.user_id)
    repository.record_audit_log(
        actor_id=user.id,
        action="WORKSPACE_MEMBER_ADDED",
        status=AuditStatus.SUCCESS,
        resource_id=workspace_id,
        details={"user_id": request.user_id},
    )
    return member


@router.delete(
    "/api/v1/workspaces/{workspace_id}/members/{member_user_id}",
    status_code=204,
    response_model=None,
)
def remove_workspace_member(
    workspace_id: UUID, member_user_id: str, user: AuthenticatedUser = Depends(get_current_user)
) -> None:
    require_admin(user)
    repository = build_repository()
    repository.remove_workspace_member(workspace_id, member_user_id)
    repository.record_audit_log(
        actor_id=user.id,
        action="WORKSPACE_MEMBER_REMOVED",
        status=AuditStatus.SUCCESS,
        resource_id=workspace_id,
        details={"user_id": member_user_id},
    )
