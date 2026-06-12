from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from cue.config import settings

logger = logging.getLogger(__name__)

PUBLIC_POST_PATHS = {"/v1/linq/webhook"}


class PublicRouteGuardMiddleware(BaseHTTPMiddleware):
    """Block public internet access to local-only API routes."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.public_strict_routes:
            return await call_next(request)

        if not _is_public_request(request):
            return await call_next(request)

        path = request.url.path
        method = request.method.upper()
        public_get_paths = {"/health"} if settings.public_expose_health else set()

        if method == "POST" and path in PUBLIC_POST_PATHS:
            return await call_next(request)
        if method == "GET" and path in public_get_paths:
            return await call_next(request)

        return JSONResponse(status_code=404, content={"detail": "Not Found"})


class WebhookRateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limit for the Linq webhook endpoint."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._events: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path != "/v1/linq/webhook" or request.method.upper() != "POST":
            return await call_next(request)

        client_key = _client_key(request)
        if self._is_rate_limited(client_key):
            logger.warning("Rate limited Linq webhook request from %s", client_key)
            return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})

        return await call_next(request)

    def _is_rate_limited(self, client_key: str) -> bool:
        limit = settings.webhook_rate_limit_per_minute
        now = time.monotonic()
        window_start = now - 60.0
        events = self._events[client_key]

        while events and events[0] < window_start:
            events.popleft()

        if len(events) >= limit:
            return True

        events.append(now)
        return False


def _is_public_request(request: Request) -> bool:
    return bool(request.headers.get("x-forwarded-for", "").strip())


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
