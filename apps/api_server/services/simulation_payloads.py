"""
Simulation request payload construction and decision-tree normalization helpers.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import HTTPException

from apps.api_server.schemas.simulate import (
    SimulateRequestAuto,
    SimulateRequestExpert,
)
from apps.api_server.services import unit_service as _unit_svc


def _build_auto_bootstrap_history(
    *,
    positive: list[str],
    negative: list[str],
    variables_by_name: dict[str, Any],
    n_points: int = 30,
) -> list[float]:
    """Derive a deterministic synthetic history from auto-mode scenario bounds."""
    if n_points < 2:
        raise ValueError("Auto bootstrap history requires at least two points.")

    history: list[float] = []
    denominator = n_points - 1
    for index in range(n_points):
        ratio = index / denominator
        sample_value = 0.0

        for name in positive:
            variable = variables_by_name[name]
            sample_value += variable.low + ((variable.high - variable.low) * ratio)

        for name in negative:
            variable = variables_by_name[name]
            sample_value -= variable.low + ((variable.high - variable.low) * ratio)

        history.append(sample_value)

    return history


def _build_auto_mojo_payload(req: SimulateRequestAuto) -> dict[str, Any]:
    sim_model = req.simulation_model.value if hasattr(req, "simulation_model") else "monte_carlo"

    variables = []
    for name, var in req.scenario.variables.items():
        midpoint = (var.low + var.high) / 2
        variables.append(
            {
                "name": name,
                "distribution": "triangular",
                "params": {"low": var.low, "mode": midpoint, "high": var.high},
            }
        )

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
    elif sim_model == "bootstrap":
        payload["bootstrap_config"] = {
            "historical_data": _build_auto_bootstrap_history(
                positive=positive,
                negative=negative,
                variables_by_name=req.scenario.variables,
            ),
            "statistic": "mean",
            "confidence_level": 0.95,
        }
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
        variable["params"] = dict(cast(dict[str, Any], params))
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
                        float(frame["probability"]) * float(branch.get("probability", 1.0))
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
    scoring = req.simulation.scoring

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
        "objective_function": req.simulation.objective_function or "",
        "scoring": {
            "expected_value": scoring.expected_value,
            "downside_risk": scoring.downside_risk,
        },
    }

    payload, _ = _unit_svc.preprocess_payload(payload, unit_specs_raw)

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

    if hasattr(req, "time_series_config") and req.time_series_config is not None:
        ts = req.time_series_config

        def _ts_param(p: Any) -> Any:
            if isinstance(p, int | float):
                return {"type": "fixed", "value": float(p)}
            return p.model_dump() if hasattr(p, "model_dump") else dict(p)

        gran = ts.granularity.lower()
        granularity_to_years = {
            "day": 1.0 / 365.0,
            "week": 1.0 / 52.0,
            "month": 1.0 / 12.0,
            "quarter": 0.25,
            "year": 1.0,
        }
        dt = granularity_to_years.get(gran, 1.0 / 12.0)
        payload["time_series_config"] = {
            "model": ts.model,
            "initial_value": ts.initial_value,
            "horizons": ts.horizons,
            "granularity": gran,
            "dt": dt,
            "drift": _ts_param(ts.drift),
            "volatility": _ts_param(ts.volatility),
            "autocorrelation": ts.autocorrelation,
            "ou_theta": ts.mean_reversion_speed,
            "ou_mu": (ts.long_run_mean if ts.long_run_mean is not None else ts.initial_value),
            "path_expression": ts.path_expression or "",
            "pct_levels": ts.fan_chart_percentiles,
            "output_paths": ts.output_paths,
            "n_sample_paths": ts.n_sample_paths,
        }

        def _to_float(p: Any) -> float:
            if isinstance(p, int | float):
                return float(p)
            d = p if isinstance(p, dict) else {}
            return float(d.get("value", d.get("mean", 0.0)))

        payload["time_series_config"]["drift"] = _to_float(ts.drift)
        payload["time_series_config"]["volatility"] = _to_float(ts.volatility)

    return payload
