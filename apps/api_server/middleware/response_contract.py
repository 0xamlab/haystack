"""Shared response header enforcement for public v1 API routes."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from apps.api_server.middleware.deprecation import is_alias_successor_path


def _apply_request_state_headers(request: Request, response: Response) -> None:
    extra_headers = getattr(request.state, "extra_response_headers", {})
    if not isinstance(extra_headers, dict):
        return
    for key, value in extra_headers.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value:
            continue
        response.headers.setdefault(key, value)


class ResponseContractMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        started = time.perf_counter()
        response: Response = await call_next(request)  # type: ignore[operator]
        _apply_request_state_headers(request, response)

        if not request.url.path.startswith("/v1/"):
            return response

        # A generated /v1 alias must behave EXACTLY like the unversioned path it stands in for
        # (see middleware/deprecation.py), so it does not pick up contract headers its legacy
        # twin has never emitted. Migrating a caller from /auth/login to /v1/auth/login is then a
        # pure path change with no observable difference.
        if is_alias_successor_path(request):
            return response

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return response

        if "X-Execution-Ms" not in response.headers:
            elapsed_ms = max(int((time.perf_counter() - started) * 1000), 0)
            response.headers["X-Execution-Ms"] = str(elapsed_ms)

        if "X-Mojo-Ms" not in response.headers:
            mojo_ms = getattr(request.state, "mojo_ms", None)
            response.headers["X-Mojo-Ms"] = str(int(mojo_ms or 0))

        decision_hash = getattr(request.state, "decision_hash_header", None)
        if decision_hash and "X-Decision-Hash" not in response.headers:
            response.headers["X-Decision-Hash"] = str(decision_hash)

        rate_limit_limit = getattr(request.state, "rate_limit_limit", None)
        if rate_limit_limit is not None and "X-RateLimit-Limit" not in response.headers:
            response.headers["X-RateLimit-Limit"] = str(rate_limit_limit)

        rate_limit_remaining = getattr(request.state, "rate_limit_remaining", None)
        if rate_limit_remaining is not None and "X-RateLimit-Remaining" not in response.headers:
            response.headers["X-RateLimit-Remaining"] = str(rate_limit_remaining)

        return response
