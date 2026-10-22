from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        limit = get_settings().rate_limit_per_minute
        if limit > 0 and request.url.path.startswith("/api/v1"):
            key = request.client.host if request.client else "unknown"
            now = monotonic()
            window = self._requests[key]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": {"code": "rate_limited", "message": "Too many requests"}},
                )
            window.append(now)
        return await call_next(request)
