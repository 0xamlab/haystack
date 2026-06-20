"""Shared FastAPI app-construction helpers + the role-aware app factory (P4).

These helpers are engine-free so BOTH the full app (``main.py``) and the control-plane app
(``control_plane.py``) can use them WITHOUT importing each other — importing ``main`` pulls in
every engine router, which the control plane must never load. The full app keeps its own
lifespan/routers in ``main.py``; this module only holds the cross-cutting pieces + the factory
that selects which app to build from ``ALGENTA_SERVICE_ROLE``.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog
from fastapi.middleware.cors import CORSMiddleware

from apps.api_server.config import Settings, get_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

CORS_EXPOSE_HEADERS = [
    "X-Request-Id",
    "X-Decision-Hash",
    "X-Execution-Ms",
    "X-Mojo-Ms",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
]


def cors_middleware_kwargs(config: Settings) -> dict[str, Any]:
    return {
        "allow_origins": config.cors_origins_list,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": list(CORS_EXPOSE_HEADERS),
    }


def sync_cors_middleware(app: FastAPI, config: Settings) -> None:
    desired_kwargs = cors_middleware_kwargs(config)
    for middleware in app.user_middleware:
        if middleware.cls is not CORSMiddleware:
            continue
        if middleware.kwargs != desired_kwargs:
            middleware.kwargs = desired_kwargs
            app.middleware_stack = None
        return
    raise RuntimeError("CORSMiddleware not registered on FastAPI application.")


def redact_log_secrets(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """B10: scrub credential-shaped keys from every structured log event before it is rendered, so
    an auth header / API key / token can never reach stdout or the log pipeline."""
    from apps.api_server.services.secret_redaction import redact_secret_fields

    return redact_secret_fields(event_dict)


def configure_logging(config: Settings) -> None:
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        redact_log_secrets,
    ]
    renderer = (
        structlog.dev.ConsoleRenderer()
        if config.is_development
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, config.log_level.upper(), logging.INFO),
    )


def _response_headers_with_request_state(
    request: Any, existing: dict[str, str] | None = None
) -> dict[str, str]:
    headers = dict(existing or {})
    extra_headers = getattr(request.state, "extra_response_headers", {})
    if isinstance(extra_headers, dict):
        for key, value in extra_headers.items():
            if isinstance(key, str) and isinstance(value, str) and value:
                headers.setdefault(key, value)
    return headers


def register_exception_handlers(app: FastAPI) -> None:
    """Register the standard {"error": {...}} normalizers (request_id injection).

    The control-plane app uses this so its auth/billing errors carry the same contract as the
    full app's. (The full app registers equivalent inline handlers in main.py.)
    """
    from fastapi import HTTPException, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    @app.exception_handler(HTTPException)
    async def _http_exc(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        detail: Any = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            error_body = detail["error"]
            if isinstance(error_body, dict):
                if request_id and not error_body.get("request_id"):
                    error_body["request_id"] = request_id
                return JSONResponse(
                    status_code=exc.status_code,
                    content=detail,
                    headers=_response_headers_with_request_state(request, exc.headers),
                )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": str(detail),
                    "request_id": request_id,
                    "docs_url": "https://docs.algenta.ai/errors/http_error",
                }
            },
            headers=_response_headers_with_request_state(request, exc.headers),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        details = [
            {
                "field": ".".join(str(loc) for loc in e.get("loc", [])),
                "issue": e.get("msg", "Invalid value"),
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": details,
                    "request_id": request_id,
                    "docs_url": "https://docs.algenta.ai/errors/validation_error",
                }
            },
            headers=_response_headers_with_request_state(request),
        )

    @app.exception_handler(Exception)
    async def _generic_exc(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        structlog.get_logger(__name__).error(
            "unhandled_exception", error=str(exc), exc_info=True, request_id=request_id
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "request_id": request_id,
                    "docs_url": "https://docs.algenta.ai/errors/internal_error",
                }
            },
        )


def create_app(role: str | None = None) -> FastAPI:
    """Build the FastAPI app for the given service role (default from ALGENTA_SERVICE_ROLE).

    ``control_plane`` → the engine-free control-plane app (no engine routers / Mojo / /mcp).
    ``full`` (default) → the complete app in ``main.py`` (today's behavior, byte-identical).

    The ``full`` branch imports ``main`` LAZILY so building the control-plane app never loads the
    engine. ``main.py`` imports helpers from this module (not vice-versa at module scope), so
    there is no import cycle.
    """
    resolved = (role or get_settings().algenta_service_role or "full").strip().lower()
    if resolved == "control_plane":
        from apps.api_server.control_plane import build_control_plane_app

        return build_control_plane_app()
    from apps.api_server.main import app as full_app

    return full_app
