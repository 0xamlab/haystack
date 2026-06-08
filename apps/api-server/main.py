"""
Algenta API — FastAPI application entry point.

Startup sequence:
1. Configure structured logging
2. Connect to Redis
3. Register middleware (CORS, request ID, structured logging)
4. Register routers
5. Register global exception handlers
"""
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api_server.config import get_settings
from apps.api_server.middleware.logging import StructuredLoggingMiddleware
from apps.api_server.middleware.request_id import RequestIDMiddleware
from apps.api_server.routers import meta, simulate
from apps.api_server.routers.connector_data import router as connector_data_router

settings = get_settings()


# ─── Structured Logging Setup ─────────────────────────────────────────────────

def _configure_logging() -> None:
    """Configure structlog for JSON (prod) or pretty (dev) output."""
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_development:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

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
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )


# ─── Application Lifespan ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Startup and shutdown lifecycle management."""
    _configure_logging()
    logger = structlog.get_logger(__name__)

    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("starting_up", env=settings.api_env, version="1.0.0")

    # Connect to Redis
    redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    try:
        await redis_client.ping()
        logger.info("redis_connected", url=settings.redis_url.split("@")[-1])
    except Exception as exc:
        logger.warning("redis_connection_failed", error=str(exc))

    app.state.redis = redis_client

    logger.info("startup_complete")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("shutting_down")
    await redis_client.aclose()
    logger.info("shutdown_complete")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Algenta API",
    description=(
        "Hosted and self-hosted Algenta API for governed data discovery, exact queries, "
        "read-only SQL reports, and simulation workflows."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "Simulation", "description": "Core simulation and decision endpoints"},
        {"name": "System", "description": "Health, version, and metadata endpoints"},
    ],
    lifespan=lifespan,
)

# ─── Middleware (order matters: outermost first) ───────────────────────────────

# 1. CORS (must be before request ID so preflight responses have CORS headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)

# 2. Request ID (adds X-Request-Id to every request/response)
app.add_middleware(RequestIDMiddleware)

# 3. Structured logging (logs after request ID is set)
app.add_middleware(StructuredLoggingMiddleware)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(meta.router)
app.include_router(simulate.router)
app.include_router(connector_data_router)

# ─── Exception Handlers ───────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert Pydantic validation errors to our standard error schema."""
    request_id = getattr(request.state, "request_id", None)
    details = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []))
        details.append({"field": field, "issue": error.get("msg", "Invalid value")})

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed. Check the 'details' field for specifics.",
                "details": details,
                "request_id": request_id,
                "docs_url": "https://docs.decisionengine.io/errors/validation_error",
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler — ensures no raw tracebacks leak to clients."""
    logger = structlog.get_logger(__name__)
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "unhandled_exception",
        error=str(exc),
        exc_info=True,
        request_id=request_id,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred. Our team has been notified.",
                "request_id": request_id,
                "docs_url": "https://docs.decisionengine.io/errors/internal_error",
            }
        },
    )
