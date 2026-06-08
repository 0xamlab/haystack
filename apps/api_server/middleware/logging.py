"""Structured JSON request logging middleware."""

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

_SKIP_PATHS = {"/health", "/metrics", "/favicon.ico"}


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            # Read request_id after inner middleware has set it
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise

        # Read after call_next so RequestIDMiddleware has already set it
        duration_ms = int((time.perf_counter() - start) * 1000)
        request_id = getattr(request.state, "request_id", "unknown")
        org_id = getattr(request.state, "org_id", None)
        run_id = getattr(request.state, "run_id", None)

        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            org_id=str(org_id) if org_id else None,
            run_id=str(run_id) if run_id else None,
        )
        return response
