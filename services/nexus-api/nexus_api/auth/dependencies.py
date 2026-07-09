from __future__ import annotations

import os
from uuid import UUID

from fastapi import Header, HTTPException

from nexus_api.auth.jwt import decode_token
from nexus_api.auth.models import AuthenticatedUser

PRIVILEGED_ROLES = frozenset({"Reviewer", "Auditor"})


def _auth_mode() -> str:
    return os.getenv("AUTH_MODE", "dev")


def get_current_user(
    authorization: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_is_admin: str | None = Header(default=None),
    x_workspace_ids: str | None = Header(default=None),
) -> AuthenticatedUser:
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            return decode_token(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    if _auth_mode() == "dev":
        return AuthenticatedUser(
            id=x_user_id or "anonymous",
            name=x_user_id or "anonymous",
            role=x_user_role or "",
            is_admin=(x_is_admin or "").strip().lower() in ("1", "true", "yes"),
            workspace_ids=[w.strip() for w in (x_workspace_ids or "").split(",") if w.strip()],
        )

    raise HTTPException(status_code=401, detail="Authorization header required")


def get_optional_user(
    authorization: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_is_admin: str | None = Header(default=None),
    x_workspace_ids: str | None = Header(default=None),
) -> AuthenticatedUser | None:
    if not authorization and not x_user_role and not x_user_id:
        return None
    return get_current_user(authorization, x_user_role, x_user_id, x_is_admin, x_workspace_ids)


def require_privileged(user: AuthenticatedUser) -> AuthenticatedUser:
    if user.role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Reviewer or Auditor role required")
    return user


def require_admin(user: AuthenticatedUser) -> AuthenticatedUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_workspace_access(user: AuthenticatedUser, workspace_id: UUID) -> None:
    """Fail closed: deny unless the user is a system admin or an explicit member."""
    if user.is_admin:
        return
    if str(workspace_id) in user.workspace_ids:
        return
    raise HTTPException(status_code=403, detail="No access to this workspace")
