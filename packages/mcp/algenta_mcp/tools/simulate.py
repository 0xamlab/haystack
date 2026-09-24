"""MCP tool: simulate — run a Monte Carlo simulation."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

SPEC: dict[str, Any] = {
    "name": "simulate",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Run a Monte Carlo simulation and get a structured decision recommendation. Use "
        "for: quantifying risk in a decision, comparing expected outcomes, getting "
        "probability-weighted recommendations. Synchronous deterministic compute governed "
        "by the plan's per-minute rate limit and monthly quota (429 on excess); the run is "
        "recorded asynchronously and appears in list_runs. Returns the decision envelope: "
        "recommended_action, expected_value, probability_of_loss, confidence, percentiles, "
        "and run metadata (run_id, execution_ms, scenarios_run). Which to use: the "
        "full decision-envelope analysis on ONE scenario; use compare for named "
        "scenario bake-offs, recommend for a ranked pick among actions, score for "
        "a single weighted number, plan_decision for just the plan summary, or "
        "product_decision for plain-English inputs."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["auto", "expert"],
                "default": "auto",
                "description": "auto = minimal setup; expert = full distribution control",
            },
            "objective": {
                "type": "string",
                "enum": [
                    "maximize_net_value",
                    "maximize_revenue",
                    "minimize_cost",
                    "minimize_risk",
                    "maximize_score",
                ],
                "default": "maximize_net_value",
                "description": "Auto-mode objective. For expert mode, use objective_function.",
            },
            "objective_function": {
                "type": "string",
                "description": (
                    "Expert-mode expression, for example 'revenue - cost'. "
                    "Required when mode='expert'."
                ),
            },
            "n_simulations": {
                "type": "integer",
                "default": 10000,
                "description": (
                    "Monte Carlo iteration count. Auto mode accepts 100–100,000; "
                    "expert mode accepts 100–1,000,000."
                ),
            },
            "variables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "low": {"type": "number"},
                        "mode": {"type": "number"},
                        "high": {"type": "number"},
                    },
                    "required": ["name", "low", "high"],
                },
                "description": (
                    "Input variables as triangular distributions (low, most-likely, high)"
                ),
            },
        },
        "required": ["variables"],
    },
}


def _error(code: str, message: str) -> str:
    return json.dumps({"error": {"code": code, "message": message}})


def _number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field} must be a number")
    return float(value)


def _name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("variable name must be a non-empty string")
    return value.strip()


_AUTO_OBJECTIVES = {
    "maximize_net_value",
    "maximize_revenue",
    "minimize_cost",
    "minimize_risk",
    "maximize_score",
}


async def handler(arguments: dict[str, Any]) -> str:
    variables_raw = arguments.get("variables", [])
    if not isinstance(variables_raw, list) or not all(
        isinstance(item, dict) for item in variables_raw
    ):
        return _error("invalid_argument", "variables must be an array of objects")
    variables = variables_raw
    mode = arguments.get("mode", "auto")
    objective = arguments.get("objective", "maximize_net_value")
    try:
        n_sims = int(arguments.get("n_simulations", 10000))
    except (TypeError, ValueError):
        return _error("invalid_argument", "n_simulations must be an integer")

    if mode not in {"auto", "expert"}:
        return _error("invalid_argument", "mode must be 'auto' or 'expert'")
    if mode == "auto" and (not isinstance(objective, str) or objective not in _AUTO_OBJECTIVES):
        return _error("invalid_argument", "objective must be a supported auto-mode objective")

    if not variables:
        return _error("invalid_argument", "variables is required")

    payload: dict[str, Any] = {
        "mode": mode,
        "runs": n_sims,
    }

    if mode == "auto":
        var_dict: dict[str, dict[str, Any]] = {}
        try:
            for v in variables:
                var_dict[_name(v.get("name"))] = {
                    "low": _number(v.get("low"), field="variable.low"),
                    "high": _number(v.get("high"), field="variable.high"),
                }
        except ValueError as exc:
            return _error("invalid_argument", str(exc))
        payload["scenario"] = {"variables": var_dict, "objective": objective}
    else:
        objective_function = arguments.get("objective_function")
        if not isinstance(objective_function, str) or not objective_function.strip():
            return _error("invalid_argument", "expert mode requires objective_function")
        expert_variables: list[dict[str, Any]] = []
        try:
            for v in variables:
                expert_variables.append(
                    {
                        "name": _name(v.get("name")),
                        "distribution": "triangular",
                        "params": {
                            "low": _number(v.get("low"), field="variable.low"),
                            "mode": _number(v.get("mode"), field="variable.mode"),
                            "high": _number(v.get("high"), field="variable.high"),
                        },
                    }
                )
        except ValueError as exc:
            return _error("invalid_argument", str(exc))
        payload["simulation"] = {
            "variables": expert_variables,
            "objective_function": objective_function.strip(),
        }

    result = await api("POST", "/v1/simulate", json=payload)

    return json.dumps(
        {
            "recommended_action": result.get("recommended_action"),
            "confidence": result.get("confidence"),
            "rationale": result.get("rationale"),
            "expected_value": result.get("metrics", {}).get("expected_value"),
            "probability_of_loss": result.get("metrics", {}).get("probability_of_loss"),
            "p5_downside": result.get("percentiles", {}).get("p5"),
            "p95_upside": result.get("percentiles", {}).get("p95"),
            "scenarios_run": result.get("scenarios_run"),
            "run_id": result.get("run_id"),
        },
        indent=2,
    )
