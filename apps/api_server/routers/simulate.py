"""
POST /v1/simulate — sub-50ms decision endpoint.

Hot path:
  1. Rate limit (Redis, ~1ms)
  2. Quota check (Redis counter, ~1ms)
  3. Compute via Mojo worker pool (~10ms)
  4. Return HTTP 200 to client  ← client receives here, ~13ms total
  5. Celery task persists run/audit/usage asynchronously
"""

import time
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.background import BackgroundTasks
from fastapi.responses import JSONResponse

from apps.api_server.config import SettingsProxy
from apps.api_server.middleware.auth import get_current_org, get_redis, require_verified_email
from apps.api_server.middleware.metrics import record_simulation_error, record_simulation_latency
from apps.api_server.schemas.response import DecisionEnvelope, build_decision_plan
from apps.api_server.schemas.simulate import SimulateRequest
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.decision_integrity import format_result_hash_header
from apps.api_server.services.quota_service import check_quota_redis, check_rate_limit
from apps.api_server.services.simulation_service import run_simulation_fast

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Simulation"], dependencies=[Depends(require_verified_email)])
settings = SettingsProxy()


@router.post(
    "/v1/simulate",
    response_model=DecisionEnvelope,
    status_code=200,
    summary="Run a simulation",
    description=(
        "Execute a Monte Carlo simulation and receive a structured decision envelope. "
        "Use `mode: 'auto'` for minimal setup or `mode: 'expert'` for full control.\n\n"
        "**Performance**: p50 < 15ms server-side (Mojo worker pool, async persistence).\n\n"
        "**Quota**: Each successful call consumes 1 simulation from your monthly quota. "
        "Returns HTTP 429 when quota or rate limit is exceeded."
    ),
)
async def simulate(
    request: Request,
    payload: SimulateRequest,
    background_tasks: BackgroundTasks,
    auth: Annotated[AuthContext, Depends(get_current_org)],
    redis_client: object = Depends(get_redis),
) -> JSONResponse:
    t_start = time.perf_counter()

    # ── 1. Rate limit (Redis sliding window, ~1ms) ────────────────────────
    await check_rate_limit(
        auth["org_id"],
        auth["plan"],
        redis_client,
        request_state=request.state,
    )

    # ── 2. Quota check (Redis counter, ~1ms — no DB query) ───────────────
    await check_quota_redis(auth["org_id"], auth["plan"], redis_client)

    # ── 3. Compute via Mojo worker pool (~10ms — no DB) ───────────────────
    try:
        envelope, persist_meta = await run_simulation_fast(
            request=payload,
            org_id=auth["org_id"],
            api_key_id=auth["key_id"],
        )
    except Exception:
        record_simulation_error("engine_error")
        raise

    envelope.request_id = getattr(request.state, "request_id", None)

    # Inject DecisionPlan — structured headline output for LLMs and dashboards
    envelope.decision_plan = build_decision_plan(envelope)

    # Apply historical calibration to confidence (raw stays in envelope.confidence)
    try:
        from apps.api_server.services.calibration_service import calibrate_confidence

        cal_conf, cal_stats = calibrate_confidence(
            envelope.confidence,
            str(auth["org_id"]),
            workspace_id=str(auth["workspace_id"]) if auth.get("workspace_id") else None,
        )
        envelope.decision_plan.confidence = cal_conf
        if cal_stats.is_reliable:
            envelope.decision_plan.calibration = cal_stats.summary()
    except Exception as exc:
        logger.warning(
            "simulate_calibration_skipped",
            error=str(exc),
            request_id=envelope.request_id,
            org_id=str(auth["org_id"]),
        )

    t_total_ms = int((time.perf_counter() - t_start) * 1000)

    # ── 4. Record Prometheus metrics (non-blocking) ───────────────────────
    try:
        record_simulation_latency(
            total_ms=t_total_ms,
            mojo_ms=persist_meta.get("execution_ms", 0),
            mode=persist_meta.get("mode", "auto"),
            plan=auth.get("plan", "free"),
            engine_type=persist_meta.get("simulation_model", "monte_carlo"),
        )
    except Exception as exc:
        logger.warning(
            "simulate_metrics_recording_failed",
            error=str(exc),
            request_id=envelope.request_id,
        )

    # ── 5. Dispatch async persistence (Celery — runs after response sent) ─
    _dispatch_persist(
        persist_meta=persist_meta,
        auth=auth,
        client_ip=_get_client_ip(request),
        background_tasks=background_tasks,
        redis_client=redis_client,
        request_id=envelope.request_id,
    )

    # ── 6. Return response immediately ────────────────────────────────────
    headers: dict[str, str] = {
        "X-Execution-Ms": str(t_total_ms),
        "X-Mojo-Ms": str(persist_meta.get("execution_ms", 0)),
    }
    request.state.mojo_ms = int(persist_meta.get("execution_ms", 0) or 0)
    if envelope.result_hash:
        request.state.decision_hash_header = format_result_hash_header(envelope.result_hash)
        headers["X-Decision-Hash"] = request.state.decision_hash_header

    logger.info(
        "simulate_responded",
        run_id=str(envelope.run_id),
        request_id=envelope.request_id,
        execution_ms=t_total_ms,
        mojo_ms=persist_meta.get("execution_ms", 0),
        recommended_action=envelope.recommended_action,
        org_id=str(auth["org_id"]),
    )

    return JSONResponse(
        content=envelope.model_dump(mode="json"),
        status_code=200,
        headers=headers,
        background=background_tasks,
    )


def _dispatch_persist(
    persist_meta: dict[str, Any],
    auth: AuthContext,
    client_ip: str,
    background_tasks: BackgroundTasks,
    redis_client: object,
    request_id: str | None,
) -> None:
    """
    Dispatch all DB writes + usage tracking to Celery.
    In development, Celery unavailability falls back to FastAPI BackgroundTasks.
    In strict runtime mode, persistence fail-closes instead of silently degrading.
    """
    persist_transport = settings.normalized_simulation_persist_transport
    if persist_transport == "in_process":
        logger.info(
            "simulation_persist_transport_override",
            run_id=persist_meta.get("run_id"),
            request_id=request_id,
            transport="in_process",
        )
        background_tasks.add_task(
            _persist_in_process,
            persist_meta=persist_meta,
            auth=auth,
            client_ip=client_ip,
            redis_client=redis_client,
        )
        return

    try:
        from apps.worker.tasks.simulation_task import persist_simulation

        persist_task = persist_simulation
        if persist_task is None:
            raise RuntimeError("celery_persist_task_unavailable")
        persist_task.delay(
            persist_meta=persist_meta,
            plan=auth["plan"],
            actor_email=auth.get("email", "api_key"),
            client_ip=client_ip,
        )
    except Exception as exc:
        fallback_allowed = (
            settings.allow_runtime_fallbacks and persist_transport == "auto"
        )
        if persist_transport == "celery" or not fallback_allowed:
            logger.error(
                "persistence_backend_unavailable",
                error=str(exc),
                org_id=str(auth["org_id"]),
                request_id=request_id,
                backend="celery",
                fallback_allowed=False,
                persist_transport=persist_transport,
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": {
                        "code": "persistence_backend_unavailable",
                        "message": "Simulation persistence backend unavailable.",
                        "details": {
                            "backend": "celery",
                            "policy": "strict_runtime",
                            "persist_transport": persist_transport,
                        },
                    }
                },
            ) from exc

        logger.warning(
            "celery_unavailable_using_background_task",
            error=str(exc),
            org_id=str(auth["org_id"]),
            request_id=request_id,
            backend="celery",
            fallback_allowed=True,
            persist_transport=persist_transport,
        )
        background_tasks.add_task(
            _persist_in_process,
            persist_meta=persist_meta,
            auth=auth,
            client_ip=client_ip,
            redis_client=redis_client,
        )


async def _persist_in_process(
    persist_meta: dict[str, Any],
    auth: AuthContext,
    client_ip: str,
    redis_client: object,
) -> None:
    """Fallback: persist synchronously in the same process (no Celery)."""
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.services._persist_helpers import persist_simulation_run

    async with AsyncSessionLocal() as db:
        await persist_simulation_run(
            db=db,
            persist_meta=persist_meta,
            plan=auth["plan"],
            actor_email=auth.get("email", "api_key"),
            client_ip=client_ip,
            redis_client=redis_client,
        )
        await db.commit()


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
