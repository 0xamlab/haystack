"""MCP tool: simulate — run a Monte Carlo simulation."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

SPEC: dict[str, Any] = {
    "name": "simulate",
    "description": (
        "Run a Monte Carlo simulation and get a structured decision recommendation. "
        "Use for: quantifying risk in a decision, comparing expected outcomes, "
        "getting probability-weighted recommendations."
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
                "enum": ["maximize", "minimize", "maximize_net_value"],
                "default": "maximize",
            },
            "n_simulations": {
                "type": "integer",
                "default": 10000,
                "description": "Monte Carlo iteration count (1,000–1,000,000)",
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


async def handler(arguments: dict[str, Any]) -> str:
    variables_raw = arguments.get("variables", [])
    variables = (
        [item for item in variables_raw if isinstance(item, dict)]
        if isinstance(variables_raw, list)
        else []
    )
    mode = arguments.get("mode", "auto")
    objective = arguments.get("objective", "maximize")
    n_sims = int(arguments.get("n_simulations", 10000))

    if not variables:
        return json.dumps({"error": "variables is required"})

    payload: dict[str, Any] = {
        "mode": mode,
        "runs": n_sims,
    }

    if mode == "auto":
        var_dict: dict[str, dict[str, Any]] = {}
        for v in variables:
            var_dict[v["name"]] = {"low": v["low"], "high": v["high"]}
        payload["scenario"] = {"variables": var_dict, "objective": objective}
    else:
        # Expert mode — pass through as-is
        payload["variables"] = variables
        payload["objective_function"] = objective

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
