from __future__ import annotations

from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    id: str
    name: str
    role: str
    is_admin: bool = False
    workspace_ids: list[str] = Field(default_factory=list)


class TokenRequest(BaseModel):
    user_id: str
    name: str
    role: str
    is_admin: bool = False
    workspace_ids: list[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthenticatedUser
