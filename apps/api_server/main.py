"""
Algenta API — FastAPI application entry point.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from apps.api_server.app_support import configure_logging as _configure_logging
from apps.api_server.app_support import cors_middleware_kwargs as _cors_middleware_kwargs
from apps.api_server.app_support import (
    redact_log_secrets as _redact_log_secrets,  # noqa: F401 — back-compat re-export
)
from apps.api_server.app_support import sync_cors_middleware as _sync_cors_middleware
from apps.api_server.config import SettingsProxy, get_settings
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.middleware.idempotency import IdempotencyMiddleware
from apps.api_server.middleware.logging import StructuredLoggingMiddleware
from apps.api_server.middleware.request_id import RequestIDMiddleware
from apps.api_server.middleware.response_contract import ResponseContractMiddleware
from apps.api_server.openapi_surface import apply_openapi_surface, validate_openapi_surface_configuration
from apps.api_server.pagination import paginate_sequence
from apps.api_server.routers import (
    account,
    agent_runs,
    auth,
    billing,
    capabilities,
    connectors,
    deployments,
    infrastructure,
    jobs,
    llm,
    logs,  # noqa: E402  (imported again below for explicitness)
    meta,
    recommend,
    repositories,
    runs,
    runtime_libraries,
    simulate,
    team,
)
from apps.api_server.routers import engines as engines_router
from apps.api_server.services.public_url_policy import validate_public_url_configuration
from apps.platform_contract_constants import (
    CAPABILITY_PLANE_CONTRACT,
    PRIMARY_DATA_QUERY_CONTRACT,
)

settings = SettingsProxy()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = get_settings()
    _sync_cors_middleware(app, config)
    _configure_logging(config)
    logger = structlog.get_logger(__name__)
    privacy_policy = config.privacy_policy
    validate_openapi_surface_configuration()
    validate_public_url_configuration(config)
    # Fail closed if Stripe billing is half-configured (real secret, placeholder webhook/prices).
    from apps.api_server.services.stripe_service import validate_billing_configuration

    validate_billing_configuration(config)
    # Fail closed on dangerous cross-environment config (live Stripe key off-prod; managed-LLM mode
    # contradicting strict per-tenant keys).
    from apps.api_server.services.env_separation import validate_environment_separation

    validate_environment_separation(config)
    logger.info(
        "starting_up",
        env=config.api_env,
        deployment_mode=privacy_policy.deployment_mode,
        algenta_cloud_enabled=privacy_policy.algenta_cloud_enabled,
        telemetry_mode=privacy_policy.telemetry_mode,
        metering_mode=privacy_policy.metering_mode,
    )

    # ── Redis ────────────────────────────────────────────────────────────────
    import redis.asyncio as aioredis

    aioredis_module: Any = aioredis
    # Wave-C: a bad/empty REDIS_URL must DEGRADE (app.state.redis=None), never crash startup —
    # from_url("") raises, and the idempotency middleware / coordination accessor already treat a
    # None client as "no Redis" (fall back to the local store / host-local flock).
    redis_client = None
    try:
        redis_client = aioredis_module.from_url(
            config.redis_url,
            encoding="utf-8",
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await redis_client.ping()
        logger.info("redis_connected")
    except Exception as exc:
        logger.warning("redis_connection_failed", error=str(exc))
    app.state.redis = redis_client

    # ── Mojo Worker Pool ─────────────────────────────────────────────────────
    mojo_pool = None
    try:
        from apps.api_server.compute.mojo_pool import MojoWorkerPool, set_pool

        mojo_pool = MojoWorkerPool()
        await mojo_pool.start()
        if not mojo_pool.running:
            if not config.allow_runtime_fallbacks:
                raise RuntimeError(
                    "Mojo worker pool did not enter running state and runtime fallbacks are denied."
                )
            app.state.mojo_pool = None
            logger.warning(
                "mojo_pool_not_running_runtime_fallback",
                fallback_allowed=True,
            )
        else:
            app.state.mojo_pool = mojo_pool
            set_pool(mojo_pool)
            logger.info("mojo_pool_started", size=mojo_pool.size)
    except Exception as exc:
        if not config.allow_runtime_fallbacks:
            logger.error(
                "mojo_pool_required_unavailable",
                error=str(exc),
                fallback_allowed=False,
            )
            raise
        logger.warning(
            "mojo_pool_unavailable",
            error=str(exc),
            hint=(
                "Simulations will use subprocess fallback. "
                "Run `make build-mojo` to enable the pool."
            ),
        )
        app.state.mojo_pool = None

    # ── Preload registered sources into memory cache ─────────────────────────
    try:
        from apps.api_server.routers.query import _CACHE_LOCK, _SOURCE_CACHE, _CachedSource
        from apps.api_server.services import source_registry as _reg

        sources_base = _reg._SOURCES_DIR
        if sources_base.exists():
            total_loaded = 0
            for org_dir in sources_base.iterdir():
                if org_dir.is_dir():
                    n = _reg.load_all_into_cache(
                        org_dir.name, _SOURCE_CACHE, _CACHE_LOCK, _CachedSource
                    )
                    total_loaded += n
            if total_loaded:
                logger.info("sources_preloaded", total=total_loaded)
    except Exception as _src_exc:
        logger.warning("sources_preload_failed", error=str(_src_exc))

    logger.info("startup_complete")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("shutting_down")
    from apps.api_server.compute.mojo_pool import set_pool

    if mojo_pool is not None:
        await mojo_pool.stop()
    set_pool(None)
    try:
        await redis_client.aclose()
    finally:
        app.state.mojo_pool = None
        app.state.redis = None
    logger.info("shutdown_complete")


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
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    **_cors_middleware_kwargs(get_settings()),
)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(ResponseContractMiddleware)
app.add_middleware(StructuredLoggingMiddleware)

# Deployment routing middleware — proxies requests to per-org data planes when
# the active deployment profile is SaaS or managed VPC.
try:
    from apps.api_server.middleware.deployment_router import DeploymentRoutingMiddleware

    app.add_middleware(DeploymentRoutingMiddleware)
except Exception as exc:
    structlog.get_logger(__name__).warning(
        "deployment_router_unavailable",
        error=str(exc),
    )

app.include_router(meta.router)
app.include_router(simulate.router)
app.include_router(recommend.router)
app.include_router(llm.router)
app.include_router(agent_runs.router)

# What-if parametric sweep
from apps.api_server.routers import whatif as _whatif_router  # noqa: E402

app.include_router(_whatif_router.router)
app.include_router(auth.router)
app.include_router(account.router)
app.include_router(jobs.router)
app.include_router(billing.router)
app.include_router(runs.router)
app.include_router(infrastructure.router)
app.include_router(team.router)
app.include_router(capabilities.router)
app.include_router(connectors.router)
app.include_router(repositories.router)
app.include_router(deployments.router)

# Export API — /v1/runs/{run_id}/export.{csv,xlsx,pdf,json}
from apps.api_server.routers import export as _export_router  # noqa: E402

app.include_router(_export_router.router)

# SSE Streaming — /v1/simulate/stream
from apps.api_server.routers import stream as _stream_router  # noqa: E402

app.include_router(_stream_router.router)

# Import and register logs SSE router
app.include_router(logs.router)
app.include_router(engines_router.router)

# Simple product APIs — jargon-free entry points
from apps.api_server.routers import products as _products_router  # noqa: E402

app.include_router(_products_router.router)

# Instant data ingestion — POST /v1/ingest
from apps.api_server.routers import ingest as _ingest_router  # noqa: E402

app.include_router(_ingest_router.router)

# Instant semantic data layer — POST /v1/map, GET /v1/map/{id}
from apps.api_server.routers import data_map as _data_map_router  # noqa: E402

app.include_router(_data_map_router.router)

# High-level connection + dataset flow — /v1/data/*
from apps.api_server.routers import data as _data_router  # noqa: E402

app.include_router(_data_router.router)

# Semantic query engine — POST /v1/query
from apps.api_server.routers import query as _query_router  # noqa: E402

app.include_router(_query_router.router)

# Playground — no auth, rate-limited, instant demo
from apps.api_server.routers import playground as _playground_router  # noqa: E402

app.include_router(_playground_router.router)

# Source registry — POST/GET/DELETE /v1/sources/*
from apps.api_server.routers import sources as _sources_router  # noqa: E402

app.include_router(_sources_router.router)

# Device licensing — POST /v1/device/register, heartbeat, list, revoke
from apps.api_server.routers import devices as _devices_router  # noqa: E402

app.include_router(_devices_router.router)

# License control-plane surfaces — GET /.well-known/jwks.json (+ renewal/CRL in P3b)
from apps.api_server.routers import license as _license_router  # noqa: E402

app.include_router(_license_router.router)

# Credit bucket — POST /v1/credits/refresh
from apps.api_server.routers import credits as _credits_router  # noqa: E402

app.include_router(_credits_router.router)

# Local runtime metering flush — POST /v1/metering
from apps.api_server.routers import metering as _metering_router  # noqa: E402

app.include_router(_metering_router.router)

# Dataset onboarding — POST /v1/datasets/onboard, GET /v1/datasets, etc.
from apps.api_server.routers import datasets as _datasets_router  # noqa: E402

app.include_router(_datasets_router.router)

# Decision Memory — POST /v1/decisions, GET /v1/decisions, PATCH /v1/decisions/{id}/outcome
from apps.api_server.routers import decisions as _decisions_router  # noqa: E402

app.include_router(_decisions_router.router)

# Real-time triggers — POST /v1/triggers, GET /v1/triggers, POST /v1/triggers/{id}/fire
from apps.api_server.routers import triggers as _triggers_router  # noqa: E402

app.include_router(_triggers_router.router)

# Confidence calibration — GET /v1/calibration
from apps.api_server.routers import calibration as _calibration_router  # noqa: E402

app.include_router(_calibration_router.router)

# Execution policy — GET/PATCH /v1/execution/policy
from apps.api_server.routers import execution_policy as _exec_policy_router  # noqa: E402

app.include_router(_exec_policy_router.router)

# GitHub App — POST /webhooks/github (unauthenticated, HMAC-verified) + install callback.
# Inert until GITHUB_APP_* is configured.
from apps.api_server.routers import github_webhooks as _github_webhooks_router  # noqa: E402

app.include_router(_github_webhooks_router.router)

# codna website BYOK — top-level POST/DELETE /byok, authenticated by a Supabase JWT (not a codna
# API key) and mapped to the caller's engine org. Inert until SUPABASE_URL + GITHUB_APP_* are set.
from apps.api_server.routers import byok as _byok_router  # noqa: E402

app.include_router(_byok_router.router)

# Website subscription dashboard — self-service device/seat mgmt (GET/DELETE /account/devices),
# Supabase-authenticated (the user's OAuth session), org-scoped. Inert until SUPABASE_URL is set.
from apps.api_server.routers import website_devices as _website_devices_router  # noqa: E402

app.include_router(_website_devices_router.router)

if settings.runtime_library_http_api_enabled:
    app.include_router(runtime_libraries.router)

# ── MCP Server — Mount at /mcp/* for AI-agent connectivity ───────────────────
try:
    from apps.mcp_server.server import create_fastapi_router as _mcp_router

    create_mcp_router = cast(Callable[[], APIRouter | None], _mcp_router)
    _mcp = create_mcp_router()
    if _mcp is not None:
        app.include_router(_mcp)
        import structlog as _sl

        _sl.get_logger(__name__).info(
            "mcp_server_mounted",
            endpoints=["/mcp/sse", "/mcp/messages", "/mcp/tools"],
        )
except Exception as _mcp_exc:  # pragma: no cover
    import structlog as _sl

    _sl.get_logger(__name__).warning(
        "mcp_server_not_loaded",
        reason=str(_mcp_exc),
        hint="pip install mcp to enable MCP AI-agent connectivity",
    )


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    apply_openapi_surface(schema)
    schema["x-primary-data-query-contract"] = PRIMARY_DATA_QUERY_CONTRACT
    schema["x-capability-plane-contract"] = CAPABILITY_PLANE_CONTRACT
    components = schema.setdefault("components", {})
    components["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "APIKey",
            "description": "Canonical v1 authentication. Use Authorization: Bearer <api_key>.",
        },
        "LegacyApiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Legacy compatibility header for existing v1 clients.",
        },
    }
    protected_operation_security = [
        {"BearerAuth": []},
        {"LegacyApiKey": []},
    ]
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if isinstance(operation, dict) and operation.get("security"):
                operation["security"] = list(protected_operation_security)
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]


@app.get(
    "/v1/simulate/templates",
    summary="List simulation templates for all industries",
    description=(
        "Returns all available domain-specific simulation templates. "
        "Requires API key authentication. "
        "Use the template's `id` with "
        "`GET /v1/simulate/templates/{id}` to get a ready-to-run payload."
    ),
    tags=["Simulation"],
    dependencies=[Depends(get_current_org)],
)
async def list_simulation_templates(
    domain: str | None = None,
    industry: str | None = None,
    tag: str | None = None,
    page: int = 1,
    limit: int = 25,
) -> dict[str, Any]:
    from apps.api_server.simulation_templates import get_all_domains, get_all_tags, list_templates

    templates = list_templates(domain=domain, industry=industry)
    if tag:
        lowered_tag = tag.lower()
        filtered_templates: list[dict[str, object]] = []
        for template in templates:
            raw_tags = template.get("tags")
            if not isinstance(raw_tags, list):
                continue
            normalized_tags = [item.lower() for item in raw_tags if isinstance(item, str)]
            if lowered_tag in normalized_tags:
                filtered_templates.append(template)
        templates = filtered_templates
    envelope = paginate_sequence(templates, page=page, limit=limit)
    return {
        "templates": envelope.items,
        "count": len(envelope.items),
        "total": envelope.total,
        "page": envelope.page,
        "limit": envelope.limit,
        "pages": envelope.pages,
        "domains": get_all_domains(),
        "tags": get_all_tags(),
    }


@app.get(
    "/v1/simulate/templates/{template_id}",
    summary="Get a simulation template with ready-to-run payload",
    tags=["Simulation"],
    dependencies=[Depends(get_current_org)],
)
async def get_simulation_template(
    template_id: str,
    runs: int = 50000,
    seed: int | None = None,
) -> dict[str, Any]:
    from apps.api_server.simulation_templates import get_template

    template = get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "template_not_found",
                    "message": f"Template '{template_id}' not found",
                }
            },
        )
    return {
        "template": template.to_dict(),
        "payload": template.to_simulate_payload(runs=runs, seed=seed),
    }


@app.post(
    "/v1/templates/{template_id}/run",
    summary="Run a simulation template directly",
    description=(
        "Run a simulation template by ID without constructing the full payload. "
        "Optionally override `runs` and `seed`. Returns simulation results immediately.\n\n"
        "Use `GET /v1/simulate/templates` to list all available templates."
    ),
    tags=["Simulation"],
    dependencies=[Depends(get_current_org)],
)
async def run_simulation_template(
    template_id: str,
    runs: int = 10000,
    seed: int | None = None,
    engine: str = "monte_carlo",
    auth: Any = Depends(get_current_org),
) -> dict[str, Any]:
    """
    engine options: monte_carlo, lhs, qmc_sobol, bootstrap, scenario,
                    sensitivity, mcmc, decision_tree, time_series, importance_sampling
    """
    from apps.api_server.schemas.simulate import SimulateRequestExpert
    from apps.api_server.services.simulation_service import run_simulation_fast
    from apps.api_server.simulation_templates import get_template

    template = get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "template_not_found",
                    "message": f"Template '{template_id}' not found",
                }
            },
        )
    payload_dict = template.to_simulate_payload(runs=runs, seed=seed)
    payload_dict["simulation_model"] = engine
    try:
        sim_request = SimulateRequestExpert.model_validate(payload_dict)
        envelope, _ = await run_simulation_fast(
            request=sim_request,
            org_id=auth["org_id"],
            api_key_id=auth.get("key_id"),
        )
        result = {
            "expected_value": envelope.metrics.expected_value,
            "std_deviation": envelope.metrics.std_deviation,
            "probability_of_loss": envelope.metrics.probability_of_loss,
            "recommended_action": envelope.recommended_action,
            "confidence": envelope.confidence,
            "execution_ms": envelope.execution_ms,
            "scenarios_run": envelope.scenarios_run,
            "percentiles": {
                "p5": envelope.percentiles.p5,
                "p95": envelope.percentiles.p95,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        import structlog as _sl

        _sl.get_logger(__name__).error("template_run_error", template=template_id, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "template_run_error", "message": str(exc)}},
        ) from exc
    return {
        "template_id": template_id,
        "template_name": template.name,
        "domain": template.domain,
        "result": result,
    }


@app.get(
    "/v1/health/ready",
    include_in_schema=False,
    summary="Readiness check (DB + Redis)",
)
async def health_ready(request: Request) -> JSONResponse:
    """Deep readiness check: pings the DB (critical) and Redis (optional, if present).

    Distinct from the liveness ``/v1/health`` route (which the Fly healthcheck contract
    depends on and which must stay fast + non-throwing). DB is the only critical dep:
    its failure yields 503. A missing/failing Redis is reported but never fails readiness.
    """
    db_status = "down"
    try:
        from sqlalchemy import text

        from apps.api_server.db.session import AsyncReadSessionLocal

        async with AsyncReadSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001 - readiness must report, never raise
        db_status = "down"

    redis_status: str | None = None
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        try:
            await redis_client.ping()
            redis_status = "ok"
        except Exception:  # noqa: BLE001 - optional dep; degrade, do not fail readiness
            redis_status = "down"

    ready = db_status == "ok"
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ok" if ready else "unavailable",
            "db": db_status,
            "redis": redis_status,
        },
    )


@app.get(
    "/metrics",
    include_in_schema=False,
    summary="Prometheus metrics",
)
async def metrics(request: Request) -> PlainTextResponse:
    """
    Prometheus metrics endpoint — protected.
    Requires either:
    - Local request (127.0.0.1 / ::1)
    - X-Metrics-Secret header matching METRICS_SECRET env var
    """
    # Allow loopback always (internal scraping from same host)
    client_ip = request.client.host if request.client else "unknown"
    is_loopback = client_ip in ("127.0.0.1", "::1", "localhost")

    if not is_loopback:
        metrics_secret = settings.metrics_secret if hasattr(settings, "metrics_secret") else None
        provided = request.headers.get("X-Metrics-Secret", "")
        if not metrics_secret or not provided or provided != metrics_secret:
            return PlainTextResponse("Forbidden", status_code=403)

    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


def _response_headers_with_request_state(
    request: Request,
    existing: dict[str, str] | None = None,
) -> dict[str, str]:
    headers = dict(existing or {})
    extra_headers = getattr(request.state, "extra_response_headers", {})
    if isinstance(extra_headers, dict):
        for key, value in extra_headers.items():
            if isinstance(key, str) and isinstance(value, str) and value:
                headers.setdefault(key, value)
    return headers


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalize HTTPException to standard {"error": {...}} schema."""
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
                    "code": str(error_body),
                    "message": str(detail.get("message", error_body)),
                    "request_id": request_id,
                    "docs_url": "https://docs.algenta.ai/errors/http_error",
                    **{k: v for k, v in detail.items() if k not in {"error", "message"}},
                }
            },
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
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
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
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger = structlog.get_logger(__name__)
    request_id = getattr(request.state, "request_id", None)
    logger.error("unhandled_exception", error=str(exc), exc_info=True, request_id=request_id)
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
        headers=_response_headers_with_request_state(request),
    )
