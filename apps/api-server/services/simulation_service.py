"""
Simulation service — orchestrates the full simulation flow:
1. Build Mojo engine payload from request
2. Invoke Mojo via subprocess adapter
3. Map engine output to DecisionEnvelope
4. Persist SimulationRun record to DB
"""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.compute.mojo_adapter import MojoEngineError, invoke_engine
from apps.api_server.models.simulation_run import ExecutionType, RunStatus, SimulationMode, SimulationRun
from apps.api_server.schemas.response import DecisionEnvelope, MetricsSummary, PercentileSummary, RunMetadata
from apps.api_server.schemas.simulate import (
    DistributionType,
    ObjectiveType,
    SimulateRequest,
    SimulateRequestAuto,
    SimulateRequestExpert,
)

logger = structlog.get_logger(__name__)

# Decision thresholds
_PROCEED_THRESHOLD = 0.65   # probability of positive outcome → "proceed"
_CAUTION_THRESHOLD = 0.40   # below this → "reject"


def _build_auto_mojo_payload(req: SimulateRequestAuto) -> dict[str, Any]:
    """Convert auto-mode request to Mojo engine JSON payload."""
    variables = []
    for name, var in req.scenario.variables.items():
        midpoint = (var.low + var.high) / 2
        variables.append({
            "name": name,
            "distribution": "triangular",
            "params": {"low": var.low, "mode": midpoint, "high": var.high},
        })

    # Build objective expression from first variable if not mapped
    objective_map = {
        ObjectiveType.MAXIMIZE_NET_VALUE: _build_net_value_expression(list(req.scenario.variables.keys())),
        ObjectiveType.MAXIMIZE_REVENUE: list(req.scenario.variables.keys())[0],
        ObjectiveType.MINIMIZE_COST: f"-{list(req.scenario.variables.keys())[0]}",
        ObjectiveType.MINIMIZE_RISK: f"-{list(req.scenario.variables.keys())[0]}",
        ObjectiveType.MAXIMIZE_SCORE: list(req.scenario.variables.keys())[0],
    }
    objective_fn = objective_map.get(req.scenario.objective, list(req.scenario.variables.keys())[0])

    return {
        "runs": req.runs,
        "seed": req.seed,
        "variables": variables,
        "objective_function": objective_fn,
        "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
    }


def _build_net_value_expression(variable_names: list[str]) -> str:
    """Auto-derive net value expression: first variable minus all others."""
    if len(variable_names) == 1:
        return variable_names[0]
    # Heuristic: revenue-like names positive, cost-like names negative
    positive = []
    negative = []
    for name in variable_names:
        lower = name.lower()
        if any(kw in lower for kw in ["cost", "expense", "loss", "risk", "churn"]):
            negative.append(name)
        else:
            positive.append(name)
    if not positive:
        positive = [variable_names[0]]
        negative = variable_names[1:]
    pos_expr = " + ".join(positive)
    if negative:
        neg_expr = " - ".join(negative)
        return f"{pos_expr} - {neg_expr}"
    return pos_expr


def _build_expert_mojo_payload(req: SimulateRequestExpert) -> dict[str, Any]:
    """Convert expert-mode request to Mojo engine JSON payload."""
    variables = []
    for var in req.simulation.variables:
        v: dict[str, Any] = {
            "name": var.name,
            "distribution": var.distribution.value,
            "params": var.params.model_dump(exclude_none=True),
        }
        variables.append(v)

    return {
        "runs": req.runs,
        "seed": req.seed,
        "variables": variables,
        "correlations": [
            {"variables": c.variables, "coefficient": c.coefficient}
            for c in req.simulation.correlations
        ],
        "objective_function": req.simulation.objective_function,
        "scoring": {
            "expected_value": req.simulation.scoring.expected_value,
            "downside_risk": req.simulation.scoring.downside_risk,
        },
    }


def _derive_recommendation(metrics: MetricsSummary) -> tuple[str, float, str]:
    """Derive recommended_action, confidence, and rationale from metrics."""
    prob_positive = 1.0 - metrics.probability_of_loss

    if prob_positive >= _PROCEED_THRESHOLD:
        action = "proceed"
        confidence = prob_positive
        rationale = (
            f"Expected value is positive in {prob_positive:.0%} of simulated scenarios. "
            f"Mean outcome: {metrics.expected_value:,.0f}. Risk is manageable."
        )
    elif prob_positive >= _CAUTION_THRESHOLD:
        action = "caution"
        confidence = prob_positive
        rationale = (
            f"Mixed outcomes: positive in {prob_positive:.0%} of scenarios. "
            f"Consider risk mitigation before proceeding. Mean: {metrics.expected_value:,.0f}."
        )
    else:
        action = "reject"
        confidence = metrics.probability_of_loss
        rationale = (
            f"High probability of loss ({metrics.probability_of_loss:.0%}). "
            f"Expected value {metrics.expected_value:,.0f} does not justify the risk."
        )

    return action, round(confidence, 4), rationale


def _map_engine_output_to_envelope(
    engine_result: dict[str, Any],
    run_id: uuid.UUID,
    mode: str,
    seed: int | None,
    execution_ms: int,
) -> DecisionEnvelope:
    """Map raw Mojo engine output to the DecisionEnvelope response schema."""
    summary = engine_result.get("summary", {})
    risk = engine_result.get("risk", {})
    percentiles_raw = engine_result.get("percentiles", {})

    metrics = MetricsSummary(
        expected_value=float(summary.get("mean", 0.0)),
        median=float(summary.get("median", 0.0)),
        std_deviation=float(summary.get("std", 0.0)),
        variance=float(summary.get("variance", 0.0)),
        probability_of_loss=float(risk.get("probability_of_loss", 0.0)),
        var_95=float(risk["var_95"]) if "var_95" in risk else None,
        cvar_95=float(risk["cvar_95"]) if "cvar_95" in risk else None,
    )

    percentiles = PercentileSummary(
        p5=float(percentiles_raw.get("p5", 0.0)),
        p25=float(percentiles_raw.get("p25", 0.0)),
        p50=float(percentiles_raw.get("p50", 0.0)),
        p75=float(percentiles_raw.get("p75", 0.0)),
        p95=float(percentiles_raw.get("p95", 0.0)),
    )

    action, confidence, rationale = _derive_recommendation(metrics)
    engine_version = engine_result.get("engine_version", "0.1.0")

    return DecisionEnvelope(
        run_id=run_id,
        status="completed",
        engine_version=engine_version,
        recommended_action=action,
        confidence=confidence,
        rationale=rationale,
        metrics=metrics,
        percentiles=percentiles,
        scenarios_run=int(engine_result.get("scenarios_run", 0)),
        execution_ms=execution_ms,
        metadata=RunMetadata(
            mode=mode,
            seed=seed,
            billing_units=1,
            engine_version=engine_version,
        ),
        created_at=datetime.now(timezone.utc),
    )


async def run_simulation(
    request: SimulateRequest,
    org_id: uuid.UUID,
    api_key_id: uuid.UUID | None,
    db: AsyncSession,
) -> DecisionEnvelope:
    """
    Full simulation flow:
    1. Build engine payload
    2. Invoke Mojo
    3. Map to DecisionEnvelope
    4. Persist SimulationRun record
    """
    # ── Determine mode and build payload ──────────────────────────────────────
    if isinstance(request, SimulateRequestAuto):
        payload = _build_auto_mojo_payload(request)
        mode = SimulationMode.AUTO
        seed = request.seed
    else:
        payload = _build_expert_mojo_payload(request)
        mode = SimulationMode.EXPERT
        seed = request.seed

    # ── Hash the request for deduplication ───────────────────────────────────
    request_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()

    # ── Create DB run record (status=RUNNING) ─────────────────────────────────
    run = SimulationRun(
        org_id=org_id,
        api_key_id=api_key_id,
        mode=mode,
        request_hash=request_hash,
        status=RunStatus.RUNNING,
        execution_type=ExecutionType.SYNC,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()  # Get run.id without committing
    run_id = run.id

    logger.info("simulation_started", run_id=str(run_id), mode=mode.value, org_id=str(org_id))

    # ── Invoke Mojo engine ────────────────────────────────────────────────────
    start = time.perf_counter()
    try:
        engine_result = await invoke_engine(payload)
    except MojoEngineError as exc:
        # Update run record to failed
        run.status = RunStatus.FAILED
        run.error_message = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.perf_counter() - start) * 1000)
        await db.flush()
        logger.error("simulation_failed", run_id=str(run_id), error=str(exc))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "engine_error",
                    "message": "The simulation engine encountered an error.",
                    "docs_url": "https://docs.algenta.ai/errors/engine_error",
                }
            },
        ) from exc

    execution_ms = int((time.perf_counter() - start) * 1000)

    # ── Map to DecisionEnvelope ───────────────────────────────────────────────
    envelope = _map_engine_output_to_envelope(
        engine_result=engine_result,
        run_id=run_id,
        mode=mode.value,
        seed=seed,
        execution_ms=execution_ms,
    )

    # ── Update run record to completed ────────────────────────────────────────
    run.status = RunStatus.COMPLETED
    run.engine_version = envelope.engine_version
    run.scenarios_run = envelope.scenarios_run
    run.billing_units = 1
    run.completed_at = datetime.now(timezone.utc)
    run.duration_ms = execution_ms
    await db.flush()

    logger.info(
        "simulation_completed",
        run_id=str(run_id),
        execution_ms=execution_ms,
        scenarios_run=envelope.scenarios_run,
        recommended_action=envelope.recommended_action,
    )

    return envelope
