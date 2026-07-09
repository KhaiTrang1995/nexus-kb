from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from nexus_api import tsx_bridge

router = APIRouter(tags=["deliberation"])


class DeliberateRequest(BaseModel):
    topic: str
    context: str = ""
    from_cli: str = "nexus-kb"
    preferred_consultants: Optional[list[str]] = None


class DeliberateResponse(BaseModel):
    deliberation_id: Optional[str]
    status: str


@router.post("/api/v1/deliberate", response_model=DeliberateResponse, status_code=202)
def deliberate(request: DeliberateRequest) -> DeliberateResponse:
    d_id = tsx_bridge.deliberate(
        topic=request.topic,
        context=request.context,
        from_cli=request.from_cli,
        preferred_consultants=request.preferred_consultants,
    )
    return DeliberateResponse(
        deliberation_id=d_id,
        status="accepted" if d_id else "engine_unavailable",
    )
