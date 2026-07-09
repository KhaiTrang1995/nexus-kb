from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from nexus_api.logging_config import configure_logging
from nexus_api.routers import (
    audit,
    auth,
    chat,
    confluence_sync,
    deliberate,
    documents,
    graph,
    ingest,
    review,
    search,
    workspaces,
)

configure_logging()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


app = FastAPI(title="Nexus-KB API", version="0.4.0")
app.add_middleware(CorrelationIdMiddleware)

app.include_router(auth.router)
app.include_router(ingest.router)
app.include_router(documents.router)
app.include_router(workspaces.router)
app.include_router(confluence_sync.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(graph.router)
app.include_router(review.router)
app.include_router(audit.router)
app.include_router(deliberate.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "nexus-api", "version": "0.4.0"}
