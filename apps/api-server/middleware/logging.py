"""Structured JSON request logging middleware."""
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Emits a single structured JSON log line per request containing:
    request_id, method, path, status_code, duration_ms, org_id (if available).
    """

    # Paths that should not be logged (health checks spam logs)
    _SKIP_PATHS = {"/v1/health", "/metrics", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if request.url.path in self._SKIP_PATHS:
            return await call_next(request)  # type: ignore[operator]

        start = time.perf_counter()
        request_id = getattr(request.state, "request_id", "unknown")

        try:
            response: Response = await call_next(request)  # type: ignore[operator]
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
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
