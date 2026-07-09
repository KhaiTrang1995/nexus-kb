from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from nexus_api.auth.models import AuthenticatedUser

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def _secret() -> str:
    return os.getenv("JWT_SECRET", "nexus-kb-dev-secret-change-in-production")


def create_token(
    user_id: str,
    name: str,
    role: str,
    is_admin: bool = False,
    workspace_ids: list[str] | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "name": name,
        "role": role,
        "is_admin": is_admin,
        "workspace_ids": workspace_ids or [],
        "exp": expire,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> AuthenticatedUser:
    claims = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    return AuthenticatedUser(
        id=claims["sub"],
        name=claims["name"],
        role=claims.get("role", ""),
        # Missing claims fail closed: no admin rights, no workspace access.
        is_admin=bool(claims.get("is_admin", False)),
        workspace_ids=list(claims.get("workspace_ids") or []),
    )
