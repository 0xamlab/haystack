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
from apps.api_server.schemas.response import (
    DecisionEnvelope,
    MetricsSummary,
    PercentileSummary,
    RunMetadata,
)
from apps.api_server.schemas.simulate import (
    SimulateRequest,
    SimulateRequestAuto,
    SimulateRequestExpert,
)
from apps.api_server.services import unit_service as _unit_svc
from apps.api_server.services.chart_service import build_charts_from_envelope, build_histogram
from apps.api_server.services.decision_integrity import hash_decision_envelope

logger = structlog.get_logger(__name__)

_PROCEED_THRESHOLD = 0.65
_CAUTION_THRESHOLD = 0.40


# ─── Payload builders ─────────────────────────────────────────────────────────

def _build_auto_mojo_payload(req: SimulateRequestAuto) -> dict[str, Any]:
    sim_model = req.simulation_model.value if hasattr(req, "simulation_model") else "monte_carlo"

    variables = []
    for name, var in req.scenario.variables.items():
        midpoint = (var.low + var.high) / 2
        variables.append({
            "name": name,
            "distribution": "triangular",
            "params": {"low": var.low, "mode": midpoint, "high": var.high},
        })

    var_names = list(req.scenario.variables.keys())
    positive, negative = [], []
    for name in var_names:
        lower = name.lower()
        if any(kw in lower for kw in ["cost", "expense", "loss", "risk", "churn"]):
            negative.append(name)
        else:
            positive.append(name)
    if not positive:
        positive = [var_names[0]] if var_names else []
        negative = var_names[1:] if var_names else []

    pos_expr = " + ".join(positive)
    objective_fn = f"{pos_expr} - {' - '.join(negative)}" if negative else pos_expr

    payload: dict[str, Any] = {
        "engine_type": sim_model,
        "runs": req.runs,
        "seed": req.seed,
        "variables": variables,
        "objective_function": objective_fn,
        "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
    }
    if req.bootstrap_config is not None:
        payload["bootstrap_config"] = req.bootstrap_config.model_dump()
    if req.scenario_config is not None:
        payload["scenario_config"] = req.scenario_config.model_dump()
    if req.sensitivity_config is not None:
        payload["sensitivity_config"] = req.sensitivity_config.model_dump()
    return payload


def _extract_unit_context(req: SimulateRequestExpert) -> tuple[list[Any], list[Any]]:
    """Return (unit_specs_raw, output_unit_specs_raw) for the unit service."""
    unit_specs_raw: list[Any] = []
    for v in req.simulation.variables:
        spec_raw = v.unit_spec.model_dump() if v.unit_spec is not None else v.unit
        unit_specs_raw.append(spec_raw)
    output_unit_specs_raw: list[Any] = []
    if req.simulation.output_unit_specs:
        output_unit_specs_raw = [s.model_dump() for s in req.simulation.output_unit_specs]
    elif req.simulation.output_units:
        output_unit_specs_raw = list(req.simulation.output_units)
    return unit_specs_raw, output_unit_specs_raw


def _raise_decision_tree_validation_error(
    *,
    code: str,
    message: str,
    details: dict[str, Any],
) -> None:
    raise HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        },
    )


def _copy_engine_variable(variable: dict[str, Any]) -> dict[str, Any]:
    copied = dict(variable)
    params = copied.get("params")
    if isinstance(params, dict):
        copied["params"] = dict(params)
    return copied


def _normalize_decision_tree_override_variable(
    *,
    name: str,
    raw_override: Any,
    unit_spec_raw: Any,
    node_id: str,
) -> dict[str, Any]:
    if isinstance(raw_override, bool):
        _raise_decision_tree_validation_error(
            code="invalid_decision_tree_override",
            message="Decision-tree variable overrides must be numeric or {distribution, params}.",
            details={"node_id": node_id, "variable": name, "override_type": "bool"},
        )

    if isinstance(raw_override, int | float):
        variable = {
            "name": name,
            "distribution": "fixed",
            "params": {"value": float(raw_override)},
        }
    elif isinstance(raw_override, dict):
        distribution = raw_override.get("distribution")
        params = raw_override.get("params")
        if not isinstance(distribution, str) or not isinstance(params, dict):
            _raise_decision_tree_validation_error(
                code="invalid_decision_tree_override",
                message=(
                    "Decision-tree variable override dicts must include string "
                    "'distribution' and object 'params'."
                ),
                details={"node_id": node_id, "variable": name},
            )
        variable = dict(raw_override)
        variable["name"] = name
        variable["params"] = dict(params)
    else:
        _raise_decision_tree_validation_error(
            code="invalid_decision_tree_override",
            message="Decision-tree variable overrides must be numeric or {distribution, params}.",
            details={
                "node_id": node_id,
                "variable": name,
                "override_type": type(raw_override).__name__,
            },
        )

    unit_spec = _unit_svc.UnitSpec.from_raw(unit_spec_raw)
    return _unit_svc.preprocess_variable(variable, unit_spec)


def _merge_decision_tree_variables(
    *,
    base_variables: list[dict[str, Any]],
    raw_overrides: dict[str, Any],
    unit_specs_by_name: dict[str, Any],
    node_id: str,
) -> list[dict[str, Any]]:
    merged = [_copy_engine_variable(variable) for variable in base_variables]
    positions = {
        str(variable.get("name")): idx
        for idx, variable in enumerate(merged)
        if isinstance(variable.get("name"), str)
    }

    for override_name, raw_override in raw_overrides.items():
        normalized = _normalize_decision_tree_override_variable(
            name=override_name,
            raw_override=raw_override,
            unit_spec_raw=unit_specs_by_name.get(override_name),
            node_id=node_id,
        )
        position = positions.get(override_name)
        if position is None:
            positions[override_name] = len(merged)
            merged.append(normalized)
        else:
            merged[position] = normalized

    return merged


def _flatten_decision_tree_paths(
    *,
    nodes: list[dict[str, Any]],
    base_variables: list[dict[str, Any]],
    default_objective: str,
    unit_specs_by_name: dict[str, Any],
    max_depth: int,
) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []

    for node in reversed(nodes):
        node_id = str(node.get("id") or "root")
        label = str(node.get("name") or node_id)
        probability = float(node.get("probability", 1.0))
        merged_variables = _merge_decision_tree_variables(
            base_variables=base_variables,
            raw_overrides=node.get("variables") or {},
            unit_specs_by_name=unit_specs_by_name,
            node_id=node_id,
        )
        stack.append(
            {
                "node": node,
                "label": label,
                "probability": probability,
                "variables": merged_variables,
                "objective_function": str(node.get("objective_function") or default_objective),
                "depth": 1,
            }
        )

    while stack:
        frame = stack.pop()
        branches = list(frame["node"].get("branches") or [])
        if not branches:
            paths.append(
                {
                    "label": frame["label"],
                    "probability": frame["probability"],
                    "variables": frame["variables"],
                    "objective_function": frame["objective_function"],
                }
            )
            continue

        next_depth = int(frame["depth"]) + 1
        if next_depth > max_depth:
            _raise_decision_tree_validation_error(
                code="decision_tree_depth_exceeded",
                message="Decision tree exceeds configured max_depth.",
                details={
                    "node_id": str(frame["node"].get("id") or "unknown"),
                    "max_depth": max_depth,
                },
            )

        for branch in reversed(branches):
            node_id = str(branch.get("id") or "branch")
            label = str(branch.get("name") or node_id)
            merged_variables = _merge_decision_tree_variables(
                base_variables=frame["variables"],
                raw_overrides=branch.get("variables") or {},
                unit_specs_by_name=unit_specs_by_name,
                node_id=node_id,
            )
            objective_function = str(
                branch.get("objective_function") or frame["objective_function"]
            )
            stack.append(
                {
                    "node": branch,
                    "label": f"{frame['label']} > {label}",
                    "probability": (
                        float(frame["probability"])
                        * float(branch.get("probability", 1.0))
                    ),
                    "variables": merged_variables,
                    "objective_function": objective_function,
                    "depth": next_depth,
                }
            )

    total_probability = sum(float(path["probability"]) for path in paths)
    if total_probability > 0.0 and total_probability != 1.0:
        for path in paths:
            path["probability"] = float(path["probability"]) / total_probability

    return paths


def _build_expert_mojo_payload(req: SimulateRequestExpert) -> dict[str, Any]:
    """Build Mojo engine payload from expert request. Unit preprocessing applied here."""
    sim_model = req.simulation_model.value if hasattr(req, "simulation_model") else "monte_carlo"
    scoring   = req.simulation.scoring

    unit_specs_raw, _ = _extract_unit_context(req)

    variables_raw = [
        {
            "name": v.name,
            "distribution": v.distribution.value,
            "params": v.params.model_dump(exclude_none=True),
        }
        for v in req.simulation.variables
    ]

    payload: dict[str, Any] = {
        "engine_type": sim_model,
        "runs": req.runs,
        "seed": req.seed,
        "variables": variables_raw,
        "correlations": [
            {"variables": c.variables, "coefficient": c.coefficient}
            for c in req.simulation.correlations
        ],
        # Use empty string when objective_function is None — Mojo py_str(None)
        # returns the string "None" which parses as a literal-zero expr node,
        # making every run return 0.0.
        "objective_function": req.simulation.objective_function or "",
        "scoring": {
            "expected_value": scoring.expected_value,
            "downside_risk": scoring.downside_risk,
        },
    }

    # Apply unit preprocessing (date→epoch, crypto scaling, range validation)
    payload, unit_warnings = _unit_svc.preprocess_payload(payload, unit_specs_raw)

    if req.bootstrap_config is not None:
        payload["bootstrap_config"] = req.bootstrap_config.model_dump()
    if req.scenario_config is not None:
        payload["scenario_config"] = req.scenario_config.model_dump()
    if hasattr(req, "mcmc_config") and req.mcmc_config is not None:
        payload["mcmc_config"] = req.mcmc_config.model_dump()
    if req.sensitivity_config is not None:
        payload["sensitivity_config"] = req.sensitivity_config.model_dump()
    if hasattr(req, "importance_sampling_config") and req.importance_sampling_config is not None:
        payload["importance_sampling_config"] = req.importance_sampling_config.model_dump()
    if hasattr(req, "decision_tree_config") and req.decision_tree_config is not None:
        unit_specs_by_name = {
            variable.name: unit_specs_raw[idx] if idx < len(unit_specs_raw) else None
            for idx, variable in enumerate(req.simulation.variables)
        }
        payload["decision_tree_config"] = {
            "paths": _flatten_decision_tree_paths(
                nodes=req.decision_tree_config.model_dump()["nodes"],
                base_variables=payload["variables"],
                default_objective=req.simulation.objective_function or "",
                unit_specs_by_name=unit_specs_by_name,
                max_depth=req.decision_tree_config.max_depth,
            )
        }

    # ── Time series: flatten StochasticParam drift/vol to Mojo-consumable scalars
    if hasattr(req, "time_series_config") and req.time_series_config is not None:
        ts = req.time_series_config
        # Resolve drift and volatility to scalar or stochastic param dict
        def _ts_param(p: Any) -> Any:
            if isinstance(p, int | float):
                return {"type": "fixed", "value": float(p)}
            return p.model_dump() if hasattr(p, "model_dump") else dict(p)
        gran = ts.granularity.lower()
        # dt = years per step (inline constant — no python_engine dependency)
        granularity_to_years = {
            "day": 1.0 / 365.0,
            "week": 1.0 / 52.0,
            "month": 1.0 / 12.0,
            "quarter": 0.25,
            "year": 1.0,
        }
        dt = granularity_to_years.get(gran, 1.0 / 12.0)
        payload["time_series_config"] = {
            "model":               ts.model,
            "initial_value":       ts.initial_value,
            "horizons":            ts.horizons,
            "granularity":         gran,
            "dt":                  dt,
            "drift":               _ts_param(ts.drift),
            "volatility":          _ts_param(ts.volatility),
            "autocorrelation":     ts.autocorrelation,
            "ou_theta":            ts.mean_reversion_speed,
            "ou_mu": (
                ts.long_run_mean
                if ts.long_run_mean is not None
                else ts.initial_value
            ),
            "path_expression":     ts.path_expression or "",
            "pct_levels":          ts.fan_chart_percentiles,
            "output_paths":        ts.output_paths,
            "n_sample_paths":      ts.n_sample_paths,
        }
        # For Mojo: resolve stochastic params to single float (mean/value)
        # Python engine handles the full stochastic version
        def _to_float(p: Any) -> float:
            if isinstance(p, int | float):
                return float(p)
            d = p if isinstance(p, dict) else {}
            return float(d.get("value", d.get("mean", 0.0)))
        payload["time_series_config"]["drift"]      = _to_float(ts.drift)
        payload["time_series_config"]["volatility"] = _to_float(ts.volatility)
    return payload


# ─── Recommendation logic ─────────────────────────────────────────────────────

def _derive_recommendation(metrics: MetricsSummary) -> tuple[str, float, str]:
    """Derive action, confidence, and rationale from simulation metrics.

    Rationale uses {:.6g} (generic float) instead of {:,.0f} so it works for
    all unit types: currencies (large integers), probabilities (0–1),
    percentages, crypto (8 decimal places), etc.
    Callers with unit context can substitute their own formatted string.
    """
    prob_positive = 1.0 - metrics.probability_of_loss
    ev_fmt = f"{metrics.expected_value:.6g}"
    if prob_positive >= _PROCEED_THRESHOLD:
        return (
            "proceed",
            round(prob_positive, 4),
            f"Expected value is positive in {prob_positive:.0%} of scenarios. Mean: {ev_fmt}.",
        )
    elif prob_positive >= _CAUTION_THRESHOLD:
        return (
            "caution",
            round(prob_positive, 4),
            f"Mixed outcomes: positive in {prob_positive:.0%} of scenarios. Mean: {ev_fmt}.",
        )
    else:
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


# ─── Engine output mapping ────────────────────────────────────────────────────

def _map_engine_output(
    engine_result: dict[str, Any],
    run_id: uuid.UUID,
    mode: str,
    seed: int | None,
    execution_ms: int,
    request_hash: str | None = None,
    validated_inputs: dict[str, Any] | None = None,
) -> DecisionEnvelope:
    summary          = engine_result.get("summary", {})
    risk             = engine_result.get("risk", {})
    percentiles_raw  = engine_result.get("percentiles", {})

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
    sim_model      = engine_result.get("simulation_model", "monte_carlo")
    engine_type    = engine_result.get("engine_type", "monte_carlo")

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


# ─── Fast path — compute only, no DB ─────────────────────────────────────────

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
        mode    = SimulationMode.AUTO
        seed    = request.seed
    else:
        payload = _build_expert_mojo_payload(request)
        mode    = SimulationMode.EXPERT
        seed    = request.seed
        unit_specs_raw, output_unit_specs_raw = _extract_unit_context(request)

    request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    run_id       = uuid.uuid4()
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

    # ── Unit postprocessing ──────────────────────────────────────────────────
    if unit_specs_raw or output_unit_specs_raw:
        raw_stats = {
            "mean":     float(engine_result.get("summary", {}).get("mean", 0.0)),
            "std":      float(engine_result.get("summary", {}).get("std", 0.0)),
            "p5":       float(engine_result.get("percentiles", {}).get("p5", 0.0)),
            "p25":      float(engine_result.get("percentiles", {}).get("p25", 0.0)),
            "p50":      float(engine_result.get("percentiles", {}).get("p50", 0.0)),
            "p75":      float(engine_result.get("percentiles", {}).get("p75", 0.0)),
            "p95":      float(engine_result.get("percentiles", {}).get("p95", 0.0)),
            "p99":      float(engine_result.get("percentiles", {}).get("p99", 0.0)),
            "var_95":   float(engine_result.get("risk", {}).get("var_95", 0.0)),
            "cvar_95":  float(engine_result.get("risk", {}).get("cvar_95", 0.0)),
        }
        envelope.formatted_result = _unit_svc.postprocess_results(
            raw_stats, output_unit_specs_raw, output_index=0
        )
        variables_list = payload.get("variables", [])
        envelope.unit_context = _unit_svc.build_unit_context(
            variables_list, unit_specs_raw, output_unit_specs_raw
        )
        # Re-run validation to capture warnings (preprocessing already ran — this is advisory only)
        all_warns: list[str] = []
        for i, var in enumerate(variables_list):
            spec_raw = unit_specs_raw[i] if i < len(unit_specs_raw) else None
            spec = _unit_svc.UnitSpec.from_raw(spec_raw)
            all_warns.extend(_unit_svc.validate_variable(var, spec))
        if all_warns:
            envelope.unit_warnings = all_warns

    # ── Chart generation (if requested) ─────────────────────────────────────
    _include_charts = False
    _include_hist   = False
    if isinstance(request, SimulateRequestExpert):
        _include_charts = getattr(request.simulation, "include_charts", False) or \
            engine_result.get("engine_type") in ("sensitivity", "time_series")
        _include_hist   = getattr(request.simulation, "include_histogram", False)

    if _include_charts or _include_hist:
        # Safe unit/title extraction — works for both auto and expert mode payloads
        _sim_block = payload.get("simulation")
        _out_unit: str = ""
        _title: str = "Simulation"
        if isinstance(_sim_block, dict):
            _out_units = _sim_block.get("output_units") or []
            _out_unit = _out_units[0] if _out_units else ""
            _title = _sim_block.get("domain_template") or _sim_block.get("domain") or "Simulation"

        try:
            if _include_charts:
                envelope.charts = build_charts_from_envelope(
                    engine_result=engine_result,
                    unit=_out_unit,
                    title=_title,
                )
            if _include_hist and not _include_charts:
                # Approximate outcomes from summary stats using Box-Muller via math module
                # — no stdlib random import, no global state, deterministic on mean/std
                mean = float(engine_result.get("summary", {}).get("mean", 0.0))
                std  = float(engine_result.get("summary", {}).get("std", 1.0))
                n_pts = 2000  # enough for a 30-bin histogram
                # Use deterministic linspace over [-3σ, +3σ] as approximation
                approx = [mean + std * (-3.0 + 6.0 * i / (n_pts - 1)) for i in range(n_pts)]
                envelope.histogram_data = build_histogram(approx, title=_title, n_bins=30)
        except Exception as _ce:
            logger.warning("chart_generation_failed", error=str(_ce))

    logger.info(
        "simulation_computed",
        run_id=str(run_id),
        execution_ms=execution_ms,
        recommended_action=envelope.recommended_action,
    )

    # Return envelope + metadata needed by the persist task
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


# ─── Legacy combined path (backward compat — not on hot path) ─────────────────

async def run_simulation(
    request: SimulateRequest,
    org_id: uuid.UUID,
    api_key_id: uuid.UUID | None,
    db: AsyncSession,
) -> DecisionEnvelope:
    """
    Legacy combined path: compute + DB writes in one call.
    Still used by the async job worker (simulation_task.py) and tests.
    Not used by the production simulate endpoint (which uses run_simulation_fast).
    """
    if isinstance(request, SimulateRequestAuto):
        payload = _build_auto_mojo_payload(request)
        mode    = SimulationMode.AUTO
        seed    = request.seed
    else:
        payload = _build_expert_mojo_payload(request)
        mode    = SimulationMode.EXPERT
        seed    = request.seed

    request_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    validated_inputs = _validated_input_summary(request, payload, mode.value)

    run = SimulationRun(
        org_id=org_id,
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
        run.status        = RunStatus.FAILED
        run.error_message = str(exc)
        run.completed_at  = datetime.now(UTC)
        run.duration_ms   = int((time.perf_counter() - start) * 1000)
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

    run.status            = RunStatus.COMPLETED
    run.engine_version    = envelope.engine_version
    run.scenarios_run     = envelope.scenarios_run
    run.billing_units     = 1
    run.completed_at      = datetime.now(UTC)
    run.duration_ms       = execution_ms
    run.result_hash       = envelope.result_hash
    run.recommended_action = envelope.recommended_action
    run.confidence        = envelope.confidence
    run.expected_value    = envelope.metrics.expected_value
    run.probability_of_loss = envelope.metrics.probability_of_loss
    run.std_deviation     = envelope.metrics.std_deviation
    run.rationale         = envelope.rationale
    try:
        run.simulation_model = envelope.simulation_model  # type: ignore[assignment]
    except Exception as exc:
        logger.debug(
            "simulation_model_persist_failed",
            run_id=str(run_id),
            error=str(exc),
        )

    await db.flush()
    logger.info("simulation_completed", run_id=str(run_id), execution_ms=execution_ms)
    return envelope
