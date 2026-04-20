"""
Universal Decision Engine — FastAPI Application Entry Point.
"""
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from apps.api_server.config import get_settings
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.middleware.idempotency import IdempotencyMiddleware
from apps.api_server.middleware.logging import StructuredLoggingMiddleware
from apps.api_server.middleware.request_id import RequestIDMiddleware
from apps.api_server.middleware.response_contract import ResponseContractMiddleware
from apps.api_server.pagination import paginate_sequence
from apps.api_server.routers import (
    account,
    auth,
    billing,
    connectors,
    deployments,
    infrastructure,
    jobs,
    logs,  # noqa: E402  (imported again below for explicitness)
    meta,
    recommend,
    runs,
    simulate,
    team,
)
from apps.api_server.routers import engines as engines_router
from apps.platform_contract_constants import API_BASE_URL, MCP_ENDPOINT

settings = get_settings()


def _configure_logging() -> None:
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.is_development
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
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    _configure_logging()
    logger = structlog.get_logger(__name__)
    logger.info("starting_up", env=settings.api_env)

    # ── Redis ────────────────────────────────────────────────────────────────
    import redis.asyncio as aioredis
    redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    try:
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
            if not settings.allow_runtime_fallbacks:
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
        if not settings.allow_runtime_fallbacks:
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
    if mojo_pool is not None:
        await mojo_pool.stop()
    await redis_client.aclose()
    logger.info("shutdown_complete")


app = FastAPI(
    title="Universal Decision Engine",
    description=(
        "API infrastructure for probabilistic decision-making. "
        "Run Monte Carlo simulations and get structured decision recommendations "
        "with a single API call."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-Id",
        "X-Decision-Hash",
        "X-Execution-Ms",
        "X-Mojo-Ms",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
    ],
)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(ResponseContractMiddleware)
app.add_middleware(StructuredLoggingMiddleware)

# Deployment routing middleware — proxies requests to per-org data planes
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
app.include_router(connectors.router)
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

# ── MCP Server — Mount at /mcp/* for AI-agent connectivity ───────────────────
try:
    from apps.mcp_server.server import create_fastapi_router as _mcp_router
    _mcp = _mcp_router()
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
    schema["servers"] = [{"url": API_BASE_URL}]
    schema["x-canonical-mcp-endpoint"] = MCP_ENDPOINT
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
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if isinstance(operation, dict) and operation.get("security"):
                operation["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


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
):
    from apps.api_server.simulation_templates import get_all_domains, get_all_tags, list_templates

    templates = list_templates(domain=domain, industry=industry)
    if tag:
        templates = [t for t in templates if tag.lower() in [x.lower() for x in t.get("tags", [])]]
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
):
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
    auth=Depends(get_current_org),
):
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
            "expected_value":      envelope.metrics.expected_value,
            "std_deviation":       envelope.metrics.std_deviation,
            "probability_of_loss": envelope.metrics.probability_of_loss,
            "recommended_action":  envelope.recommended_action,
            "confidence":          envelope.confidence,
            "execution_ms":        envelope.execution_ms,
            "scenarios_run":       envelope.scenarios_run,
            "percentiles": {
                "p5":  envelope.percentiles.p5,
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
        "template_id":   template_id,
        "template_name": template.name,
        "domain":        template.domain,
        "result":        result,
    }


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
            return JSONResponse(status_code=exc.status_code, content=detail)
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
    )
