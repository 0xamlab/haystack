"""The Algenta CONTROL-PLANE FastAPI app (P4) — ALGENTA_SERVICE_ROLE=control_plane.

Mounts ONLY the hosted control-plane surfaces — auth, account, team, billing, credits, metering,
devices, license (JWKS / CRL / renewal), meta, + a control-plane marker — plus readiness/metrics.
There is NO engine: no simulate/recommend/query/repositories/agent-run routers, no Mojo worker
pool, no source preload, no /mcp mount. Because it never imports those modules, the control plane
can run as a small Fly app behind Cloudflare with its OWN Postgres (it runs the same alembic
migrations against its own DATABASE_URL). The full app is unchanged (apps/api_server/main.py).
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from apps.api_server.app_support import (
    configure_logging,
    cors_middleware_kwargs,
    register_exception_handlers,
    sync_cors_middleware,
)
from apps.api_server.config import get_settings
from apps.api_server.middleware.idempotency import IdempotencyMiddleware
from apps.api_server.middleware.logging import StructuredLoggingMiddleware
from apps.api_server.middleware.origin_guard import OriginGuardMiddleware
from apps.api_server.middleware.request_id import RequestIDMiddleware
from apps.api_server.middleware.response_contract import ResponseContractMiddleware
from apps.api_server.openapi_surface import validate_openapi_surface_configuration
from apps.api_server.routers import (
    account,
    auth,
    billing,
    control_plane,
    credits,
    devices,
    metering,
    oauth_device,
    team,
    website_billing,
    website_devices,
    website_team,
    website_usage,
)
from apps.api_server.routers import license as license_router
from apps.api_server.routers import meta as meta_router
from apps.api_server.routers import registry_credentials as registry_credentials_router
from apps.api_server.services.public_url_policy import validate_public_url_configuration

logger = structlog.get_logger(__name__)

# The ONLY routers the control plane mounts. Engine routers are deliberately ABSENT — adding one
# here (or importing an engine module above) would defeat the isolation guarantee (asserted by
# tests/test_control_plane_role.py's subprocess sys.modules check).
_CONTROL_PLANE_ROUTERS = (
    auth.router,
    account.router,
    team.router,
    billing.router,
    credits.router,
    metering.router,
    devices.router,
    oauth_device.router,
    registry_credentials_router.router,
    license_router.router,
    meta_router.router,
    control_plane.router,
    # The accounts-portal surface (/account/orgs|devices|billing|team|usage — Supabase-authed,
    # engine-free). Absent, every portal call against a control-plane host (api.telys.ai) 404'd:
    # the CLI registered devices HERE while the portal read nothing — "No devices registered yet"
    # right after a successful `telys login`.
    website_billing.router,
    website_devices.router,
    website_team.router,
    website_usage.router,
)


@contextlib.asynccontextmanager
async def _control_plane_lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = get_settings()
    sync_cors_middleware(app, config)
    configure_logging(config)
    log = structlog.get_logger(__name__)
    # Same fail-closed startup validations as the full app (auth/billing/url/env) — but NONE of
    # the engine startup (Mojo pool, source preload).
    validate_openapi_surface_configuration()
    validate_public_url_configuration(config)
    from apps.api_server.services.stripe_service import validate_billing_configuration

    validate_billing_configuration(config)
    from apps.api_server.services.env_separation import validate_environment_separation

    validate_environment_separation(config)

    import redis.asyncio as aioredis

    redis_client = None
    try:
        redis_client = aioredis.from_url(
            config.redis_url,
            encoding="utf-8",
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await redis_client.ping()
        log.info("redis_connected")
    except Exception as exc:  # noqa: BLE001 — Redis degrades to None (local fallback), never crash
        log.warning("redis_connection_failed", error=str(exc))
    app.state.redis = redis_client
    app.state.mojo_pool = None  # the control plane never runs the engine
    log.info("control_plane_startup_complete", role="control_plane")
    yield
    log.info("control_plane_shutting_down")
    if redis_client is not None:
        with contextlib.suppress(Exception):
            await redis_client.aclose()
    app.state.redis = None
    log.info("control_plane_shutdown_complete")


def build_control_plane_app() -> FastAPI:
    """Construct the control-plane-only FastAPI app (mounts the allowlist; no engine)."""
    config = get_settings()
    app = FastAPI(
        title="Algenta Control Plane",
        description=(
            "Hosted Algenta control plane — accounts, billing, device licensing, and license "
            "verification (JWKS / revocations). No engine; deploy with ALGENTA_SERVICE_ROLE=control_plane."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=_control_plane_lifespan,
    )
    app.state.service_role = "control_plane"

    # Same middleware stack + order as the full app.
    app.add_middleware(CORSMiddleware, **cors_middleware_kwargs(config))
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(ResponseContractMiddleware)
    app.add_middleware(StructuredLoggingMiddleware)
    with contextlib.suppress(Exception):
        from apps.api_server.middleware.deployment_router import DeploymentRoutingMiddleware

        app.add_middleware(DeploymentRoutingMiddleware)

    # Added LAST so it is the OUTERMOST middleware: a request that did not come through Cloudflare
    # is rejected before it touches auth, idempotency, or the DB. Inert unless ORIGIN_GUARD_MODE is
    # set to log/enforce AND ORIGIN_SHARED_SECRET is present, so this is a no-op by default.
    app.add_middleware(
        OriginGuardMiddleware,
        secret=config.origin_shared_secret,
        mode=config.origin_guard_mode,
    )

    for router in _CONTROL_PLANE_ROUTERS:
        app.include_router(router)

    # Same {"error": {...}} + request_id contract as the full app.
    register_exception_handlers(app)

    @app.get("/v1/health/ready", include_in_schema=False)
    async def _ready() -> dict[str, str]:
        return {"status": "ready", "role": "control_plane"}

    @app.get("/metrics", include_in_schema=False)
    async def _metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
