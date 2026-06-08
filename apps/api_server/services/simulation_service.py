"""
Simulation service — compute-only fast path + deferred persistence.

Public API:
  run_simulation_fast()  — compute only; returns DecisionEnvelope in < 15ms
  build_persist_payload() — extracts serializable data for the Celery persist task
  run_simulation()        — legacy combined path (kept for backward compat; not used on hot path)
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.compute.mojo_adapter import MojoEngineError, invoke_engine
from apps.api_server.models.simulation_run import (
    ExecutionType,
    RunStatus,
    SimulationMode,
    SimulationRun,
)
from apps.api_server.schemas.response import DecisionEnvelope
from apps.api_server.schemas.simulate import (
    SimulateRequest,
    SimulateRequestAuto,
    SimulateRequestExpert,
)
from apps.api_server.services import unit_service as _unit_svc
from apps.api_server.services.chart_service import build_charts_from_envelope, build_histogram
from apps.api_server.services.simulation_output import (
    _derive_recommendation,
    _fallback_decision_tree_result,
    _map_engine_output,
    _simulation_class_for_model,
    _validated_input_summary,
)
from apps.api_server.services.simulation_payloads import (
    _build_auto_mojo_payload,
    _build_expert_mojo_payload,
    _copy_engine_variable,
    _extract_unit_context,
    _flatten_decision_tree_paths,
    _merge_decision_tree_variables,
    _normalize_decision_tree_override_variable,
    _raise_decision_tree_validation_error,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "_build_auto_mojo_payload",
    "_build_expert_mojo_payload",
    "_copy_engine_variable",
    "_derive_recommendation",
    "_extract_unit_context",
    "_fallback_decision_tree_result",
    "_flatten_decision_tree_paths",
    "_map_engine_output",
    "_merge_decision_tree_variables",
    "_normalize_decision_tree_override_variable",
    "_raise_decision_tree_validation_error",
    "_simulation_class_for_model",
    "_validated_input_summary",
    "run_simulation",
    "run_simulation_fast",
]


async def run_simulation_fast(
    request: SimulateRequest,
    org_id: uuid.UUID,
    api_key_id: uuid.UUID | None,
) -> tuple[DecisionEnvelope, dict[str, Any]]:
    """
    Compute a simulation without touching the database.

    Returns (envelope, mojo_payload) so the caller can dispatch
    the persist task with the raw payload for the DB insert.

    This is the production hot path — called by the simulate endpoint
    which returns the HTTP response immediately, then persists asynchronously.
    """
    unit_specs_raw: list[Any] = []
    output_unit_specs_raw: list[Any] = []

    if isinstance(request, SimulateRequestAuto):
        payload = _build_auto_mojo_payload(request)
        mode = SimulationMode.AUTO
        seed = request.seed
    else:
        payload = _build_expert_mojo_payload(request)
        mode = SimulationMode.EXPERT
        seed = request.seed
        unit_specs_raw, output_unit_specs_raw = _extract_unit_context(request)

    request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    run_id = uuid.uuid4()
    validated_inputs = _validated_input_summary(request, payload, mode.value)

    start = time.perf_counter()
    try:
        engine_result = await invoke_engine(payload)
    except MojoEngineError as exc:
        logger.error("simulation_failed", run_id=str(run_id), error=str(exc))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "engine_error",
                    "message": "The simulation engine encountered an error.",
                }
            },
        ) from exc

    execution_ms = int((time.perf_counter() - start) * 1000)
    envelope = _map_engine_output(
        engine_result,
        run_id,
        mode.value,
        seed,
        execution_ms,
        request_hash=request_hash,
        validated_inputs=validated_inputs,
    )
    if envelope.simulation_model == "decision_tree" and envelope.decision_tree_result is None:
        envelope.decision_tree_result = _fallback_decision_tree_result(payload)

    if unit_specs_raw or output_unit_specs_raw:
        raw_stats = {
            "mean": float(engine_result.get("summary", {}).get("mean", 0.0)),
            "std": float(engine_result.get("summary", {}).get("std", 0.0)),
            "p5": float(engine_result.get("percentiles", {}).get("p5", 0.0)),
            "p25": float(engine_result.get("percentiles", {}).get("p25", 0.0)),
            "p50": float(engine_result.get("percentiles", {}).get("p50", 0.0)),
            "p75": float(engine_result.get("percentiles", {}).get("p75", 0.0)),
            "p95": float(engine_result.get("percentiles", {}).get("p95", 0.0)),
            "p99": float(engine_result.get("percentiles", {}).get("p99", 0.0)),
            "var_95": float(engine_result.get("risk", {}).get("var_95", 0.0)),
            "cvar_95": float(engine_result.get("risk", {}).get("cvar_95", 0.0)),
        }
        envelope.formatted_result = _unit_svc.postprocess_results(
            raw_stats, output_unit_specs_raw, output_index=0
        )
        variables_list = payload.get("variables", [])
        envelope.unit_context = _unit_svc.build_unit_context(
            variables_list, unit_specs_raw, output_unit_specs_raw
        )
        all_warns: list[str] = []
        for i, var in enumerate(variables_list):
            spec_raw = unit_specs_raw[i] if i < len(unit_specs_raw) else None
            spec = _unit_svc.UnitSpec.from_raw(spec_raw)
            all_warns.extend(_unit_svc.validate_variable(var, spec))
        if all_warns:
            envelope.unit_warnings = all_warns

    include_charts = False
    include_hist = False
    if isinstance(request, SimulateRequestExpert):
        include_charts = getattr(request.simulation, "include_charts", False) or (
            engine_result.get("engine_type") in ("sensitivity", "time_series")
        )
        include_hist = getattr(request.simulation, "include_histogram", False)

    if include_charts or include_hist:
        sim_block = payload.get("simulation")
        out_unit = ""
        title = "Simulation"
        if isinstance(sim_block, dict):
            out_units = sim_block.get("output_units") or []
            out_unit = out_units[0] if out_units else ""
            title = sim_block.get("domain_template") or sim_block.get("domain") or "Simulation"

        try:
            if include_charts:
                envelope.charts = build_charts_from_envelope(
                    engine_result=engine_result,
                    unit=out_unit,
                    title=title,
                )
            if include_hist and not include_charts:
                mean = float(engine_result.get("summary", {}).get("mean", 0.0))
                std = float(engine_result.get("summary", {}).get("std", 1.0))
                n_pts = 2000
                approx = [mean + std * (-3.0 + 6.0 * i / (n_pts - 1)) for i in range(n_pts)]
                envelope.histogram_data = build_histogram(approx, title=title, n_bins=30)
        except Exception as exc:
            logger.warning("chart_generation_failed", error=str(exc))

    logger.info(
        "simulation_computed",
        run_id=str(run_id),
        execution_ms=execution_ms,
        recommended_action=envelope.recommended_action,
    )

    persist_meta: dict[str, Any] = {
        "run_id": str(run_id),
        "org_id": str(org_id),
        "api_key_id": str(api_key_id) if api_key_id else None,
        "mode": mode.value,
        "request_hash": request_hash,
        "execution_ms": execution_ms,
        "engine_version": envelope.engine_version,
        "scenarios_run": envelope.scenarios_run,
        "result_hash": envelope.result_hash,
        "recommended_action": envelope.recommended_action,
        "confidence": envelope.confidence,
        "expected_value": envelope.metrics.expected_value,
        "probability_of_loss": envelope.metrics.probability_of_loss,
        "std_deviation": envelope.metrics.std_deviation,
        "rationale": envelope.rationale,
        "simulation_model": envelope.simulation_model,
        "envelope_json": envelope.model_dump(mode="json"),
    }
    return envelope, persist_meta


async def run_simulation(
    request: SimulateRequest,
    org_id: uuid.UUID,
    api_key_id: uuid.UUID | None,
    db: AsyncSession,
    workspace_id: uuid.UUID | None = None,
) -> DecisionEnvelope:
    """
    Legacy combined path: compute + DB writes in one call.
    Still used by the async job worker (simulation_task.py) and tests.
    Not used by the production simulate endpoint (which uses run_simulation_fast).
    """
    if isinstance(request, SimulateRequestAuto):
        payload = _build_auto_mojo_payload(request)
        mode = SimulationMode.AUTO
        seed = request.seed
    else:
        payload = _build_expert_mojo_payload(request)
        mode = SimulationMode.EXPERT
        seed = request.seed

    request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    validated_inputs = _validated_input_summary(request, payload, mode.value)

    run = SimulationRun(
        org_id=org_id,
        workspace_id=workspace_id,
        api_key_id=api_key_id,
        mode=mode,
        request_hash=request_hash,
        status=RunStatus.RUNNING,
        execution_type=ExecutionType.SYNC,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.flush()
    run_id = run.id

    logger.info("simulation_started", run_id=str(run_id), mode=mode.value, org_id=str(org_id))

    start = time.perf_counter()
    try:
        engine_result = await invoke_engine(payload)
    except MojoEngineError as exc:
        run.status = RunStatus.FAILED
        run.error_message = str(exc)
        run.completed_at = datetime.now(UTC)
        run.duration_ms = int((time.perf_counter() - start) * 1000)
        await db.flush()
        logger.error("simulation_failed", run_id=str(run_id), error=str(exc))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "engine_error",
                    "message": "The simulation engine encountered an error.",
                }
            },
        ) from exc

    execution_ms = int((time.perf_counter() - start) * 1000)
    envelope = _map_engine_output(
        engine_result,
        run_id,
        mode.value,
        seed,
        execution_ms,
        request_hash=request_hash,
        validated_inputs=validated_inputs,
    )
    if envelope.simulation_model == "decision_tree" and envelope.decision_tree_result is None:
        envelope.decision_tree_result = _fallback_decision_tree_result(payload)

    run.status = RunStatus.COMPLETED
    run.engine_version = envelope.engine_version
    run.scenarios_run = envelope.scenarios_run
    run.billing_units = 1
    run.completed_at = datetime.now(UTC)
    run.duration_ms = execution_ms
    run.result_hash = envelope.result_hash
    run.recommended_action = envelope.recommended_action
    run.confidence = envelope.confidence
    run.expected_value = envelope.metrics.expected_value
    run.probability_of_loss = envelope.metrics.probability_of_loss
    run.std_deviation = envelope.metrics.std_deviation
    run.rationale = envelope.rationale
    try:
        run.simulation_model = envelope.simulation_model
    except Exception as exc:
        logger.debug(
            "simulation_model_persist_failed",
            run_id=str(run_id),
            error=str(exc),
        )

    await db.flush()
    logger.info("simulation_completed", run_id=str(run_id), execution_ms=execution_ms)
    return envelope
