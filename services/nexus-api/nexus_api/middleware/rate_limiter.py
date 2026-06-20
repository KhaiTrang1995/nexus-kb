from __future__ import annotations
import asyncio, os, time
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rpm: int = 60, enabled: bool = True):
        super().__init__(app)
        self.rpm = rpm
        self.enabled = enabled
        self.window = 60.0
        self._clients: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or request.url.path == "/health":
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.monotonic()

        async with self._lock:
            q = self._clients[client]
            # Remove timestamps outside window
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.rpm:
                retry = int(self.window - (now - q[0])) + 1
                return Response(
                    content=f"Rate limit exceeded. Retry after {retry}s.",
                    status_code=429,
                    headers={"Retry-After": str(retry)},
                )
            q.append(now)

        return await call_next(request)


def create_from_env() -> RateLimiterMiddleware:
    from nexus_api.main import app  # import here to avoid circular
    return RateLimiterMiddleware(
        app,
        rpm=int(os.getenv("RATE_LIMIT_RPM", "60")),
        enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
    )
