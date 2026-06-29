from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from cue.config import settings

logger = logging.getLogger(__name__)


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

        if method == "GET" and path in public_get_paths:
            return await call_next(request)

        return JSONResponse(status_code=404, content={"detail": "Not Found"})


def _is_public_request(request: Request) -> bool:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return True

    client_host = request.client.host if request.client else ""
    return client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}
