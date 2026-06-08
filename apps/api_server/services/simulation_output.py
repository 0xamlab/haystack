"""
Simulation engine-output mapping and recommendation helpers.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from apps.api_server.schemas.response import (
    DecisionEnvelope,
    MetricsSummary,
    PercentileSummary,
    RunMetadata,
)
from apps.api_server.schemas.simulate import (
    SimulateRequest,
    SimulateRequestAuto,
)
from apps.api_server.services.decision_integrity import hash_decision_envelope

_PROCEED_THRESHOLD = 0.65
_CAUTION_THRESHOLD = 0.40


def _derive_recommendation(metrics: MetricsSummary) -> tuple[str, float, str]:
    """Derive action, confidence, and rationale from simulation metrics."""
    prob_positive = 1.0 - metrics.probability_of_loss
    ev_fmt = f"{metrics.expected_value:.6g}"
    if prob_positive >= _PROCEED_THRESHOLD:
        return (
            "proceed",
            round(prob_positive, 4),
            f"Expected value is positive in {prob_positive:.0%} of scenarios. Mean: {ev_fmt}.",
        )
    if prob_positive >= _CAUTION_THRESHOLD:
        return (
            "caution",
            round(prob_positive, 4),
            f"Mixed outcomes: positive in {prob_positive:.0%} of scenarios. Mean: {ev_fmt}.",
        )
    return (
        "reject",
        round(metrics.probability_of_loss, 4),
        f"High probability of loss ({metrics.probability_of_loss:.0%}). Mean: {ev_fmt}.",
    )


def _simulation_class_for_model(sim_model: str) -> str:
    model = str(sim_model or "").strip().lower()
    if model == "scenario":
        return "scenario_analysis"
    if model == "sensitivity":
        return "sensitivity_analysis"
    if model == "decision_tree":
        return "decision_tree"
    if model == "compare":
        return "comparative"
    return "predictive"


def _validated_input_summary(
    request: SimulateRequest,
    payload: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "mode": mode,
        "simulation_model": payload.get("engine_type", "monte_carlo"),
        "runs": int(payload.get("runs", 0) or 0),
        "seed": payload.get("seed"),
        "variable_count": len(payload.get("variables", []) or []),
        "correlation_count": len(payload.get("correlations", []) or []),
    }

    if isinstance(request, SimulateRequestAuto):
        summary["input_contract"] = "auto"
        summary["scenario_variable_count"] = len(request.scenario.variables)
        summary["objective"] = request.scenario.objective
    else:
        summary["input_contract"] = "expert"
        summary["distribution_types"] = sorted(
            {variable.distribution.value for variable in request.simulation.variables}
        )
        summary["has_objective_function"] = bool(request.simulation.objective_function)

    return summary


def _map_engine_output(
    engine_result: dict[str, Any],
    run_id: uuid.UUID,
    mode: str,
    seed: int | None,
    execution_ms: int,
    request_hash: str | None = None,
    validated_inputs: dict[str, Any] | None = None,
) -> DecisionEnvelope:
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
        p10=float(percentiles_raw["p10"]) if "p10" in percentiles_raw else None,
        p25=float(percentiles_raw.get("p25", 0.0)),
        p50=float(percentiles_raw.get("p50", 0.0)),
        p75=float(percentiles_raw.get("p75", 0.0)),
        p90=float(percentiles_raw["p90"]) if "p90" in percentiles_raw else None,
        p95=float(percentiles_raw.get("p95", 0.0)),
        p99=float(percentiles_raw["p99"]) if "p99" in percentiles_raw else None,
    )
    action, confidence, rationale = _derive_recommendation(metrics)
    engine_version = engine_result.get("engine_version", "0.1.0")
    sim_model = engine_result.get("simulation_model", "monte_carlo")
    engine_type = engine_result.get("engine_type", "monte_carlo")

    envelope = DecisionEnvelope(
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
        metadata=RunMetadata(mode=mode, seed=seed, billing_units=1, engine_version=engine_version),
        simulation_model=sim_model,
        engine_type=engine_type,
        simulation_class=_simulation_class_for_model(sim_model),
        model_revision=engine_version,
        assumptions_hash=request_hash,
        validated_inputs=validated_inputs,
        confidence_interval={
            "level": 0.90,
            "lower": percentiles.p5,
            "upper": percentiles.p95,
        },
        request_hash=request_hash,
        scenario_analysis=engine_result.get("scenario_analysis"),
        sensitivity_analysis=engine_result.get("sensitivity_analysis"),
        bootstrap_result=engine_result.get("bootstrap_result"),
        mcmc_result=engine_result.get("mcmc_result"),
        decision_tree_result=engine_result.get("decision_tree_result"),
        time_series_result=engine_result.get("time_series_result"),
        importance_sampling_result=engine_result.get("importance_sampling_result"),
        request_id=None,
        score=None,
        formatted_result=None,
        unit_context=None,
        unit_warnings=None,
        charts=None,
        histogram_data=None,
        decision_plan=None,
        result_hash=None,
        created_at=datetime.now(UTC),
    )
    envelope.result_hash = hash_decision_envelope(envelope.model_dump())
    return envelope


def _fallback_decision_tree_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    config = payload.get("decision_tree_config")
    if not isinstance(config, dict):
        return None
    raw_paths = config.get("paths")
    if not isinstance(raw_paths, list):
        return None

    normalized_paths: list[dict[str, Any]] = []
    for path in raw_paths:
        if not isinstance(path, dict):
            continue
        normalized_paths.append(
            {
                "label": path.get("label"),
                "probability": path.get("probability"),
                "objective_function": path.get("objective_function"),
                "variables": path.get("variables"),
            }
        )

    return {
        "n_paths": len(normalized_paths),
        "paths": normalized_paths,
    }
