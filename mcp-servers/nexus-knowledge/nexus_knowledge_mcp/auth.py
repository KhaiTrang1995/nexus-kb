from __future__ import annotations

import os
from typing import Protocol

from jose import JWTError, jwt

from nexus_knowledge_mcp.schemas import McpActorContext


class ActorResolutionError(PermissionError):
    pass


class TokenVerifier(Protocol):
    def verify(self, token: str) -> McpActorContext:
        raise NotImplementedError


class InternalJwtVerifier:
    """Verifies the same internal HS256 JWTs `nexus-api` issues
    (services/nexus-api/nexus_api/auth/jwt.py) -- reads the shared
    `JWT_SECRET` env var so a token minted via /api/v1/auth/dev-token works
    here unchanged.

    This is an interim TokenVerifier. The target design (per brainstorm) is
    for the MCP Gateway to issue Keycloak-signed (RS256) tokens verified via
    that realm's JWKS endpoint -- swap this class for a
    `KeycloakJwksVerifier(TokenVerifier)` once the gateway's issuer/audience/
    claim-mapping details are available. `NexusKnowledgeBridge` depends only
    on the `TokenVerifier` protocol, so that swap needs no changes here.
    """

    ALGORITHM = "HS256"

    def __init__(self, secret: str | None = None) -> None:
        self._secret = secret or os.getenv("JWT_SECRET", "nexus-kb-dev-secret-change-in-production")

    def verify(self, token: str) -> McpActorContext:
        try:
            claims = jwt.decode(token, self._secret, algorithms=[self.ALGORITHM])
        except JWTError as exc:
            raise ActorResolutionError("invalid or expired token") from exc

        user_id = claims.get("sub")
        if not user_id:
            raise ActorResolutionError("token missing subject claim")

        return McpActorContext(
            user_id=user_id,
            is_admin=bool(claims.get("is_admin", False)),
            workspace_ids=list(claims.get("workspace_ids") or []),
        )
