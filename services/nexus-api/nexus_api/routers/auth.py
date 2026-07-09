from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from nexus_api.auth.jwt import create_token
from nexus_api.auth.models import AuthenticatedUser, TokenRequest, TokenResponse

router = APIRouter(tags=["auth"])

DEV_USERS = [
    {"id": "u1", "name": "Alice", "role": ""},
    {"id": "u2", "name": "Bob", "role": "Reviewer"},
    {"id": "u3", "name": "Carol", "role": "Auditor"},
]


@router.post("/api/v1/auth/dev-token", response_model=TokenResponse)
def dev_token(request: TokenRequest) -> TokenResponse:
    if os.getenv("AUTH_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not available in production")
    # is_admin/workspace_ids are trusted from the request like `role` already
    # is -- acceptable only because this endpoint is disabled outside
    # AUTH_MODE=dev. There is no real login/SSO flow yet (Keycloak OIDC is a
    # later milestone); until then, callers look up current membership via
    # GET /api/v1/workspaces (admin) and pass it back in here explicitly.
    token = create_token(
        request.user_id,
        request.name,
        request.role,
        is_admin=request.is_admin,
        workspace_ids=request.workspace_ids,
    )
    return TokenResponse(
        access_token=token,
        user=AuthenticatedUser(
            id=request.user_id,
            name=request.name,
            role=request.role,
            is_admin=request.is_admin,
            workspace_ids=request.workspace_ids,
        ),
    )


@router.get("/api/v1/auth/users")
def list_dev_users() -> list[dict]:
    if os.getenv("AUTH_MODE", "dev") != "dev":
        raise HTTPException(status_code=404, detail="Not available in production")
    return DEV_USERS
