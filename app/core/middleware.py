from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        route_path = request.url.path
        route = request.scope.get("route")
        if route is not None and getattr(route, "path", None):
            route_path = str(route.path)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "http_request",
            extra={
                "event": "http_request",
                "method": request.method,
                "route": route_path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
