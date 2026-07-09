from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from nexus_api.audit import list_audit_records
from nexus_api.auth.dependencies import get_current_user
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.dependencies import build_repository
from nexus_shared.contracts import AuditRecord

router = APIRouter(tags=["audit"])


@router.get("/api/v1/audit", response_model=list[AuditRecord])
def audit(
    limit: int = 50,
    offset: int = 0,
    action_filter: str | None = None,
    actor_filter: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[AuditRecord]:
    if actor_filter and user.role != "Auditor":
        raise HTTPException(status_code=403, detail="Auditor role required for actor filtering")
    return list_audit_records(build_repository(), limit, offset, action_filter, actor_filter)
