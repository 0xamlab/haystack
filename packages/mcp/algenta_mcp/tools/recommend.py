"""MCP tools: recommend, score, batch, compare."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

SPEC: dict[str, Any] = {
    "name": "recommend",
    "description": (
        "Compare multiple named actions/options and get a ranked recommendation. "
        "Use when you need to choose between two or more alternatives with uncertainty."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "variables": {
                            "type": "object",
                            "description": "Variable dict: {name: {low, high}}",
                        },
                        "objective": {"type": "string", "default": "maximize"},
                    },
                    "required": ["name", "variables"],
                },
                "description": "List of options to compare (minimum 2)",
                "minItems": 2,
            },
            "n_simulations": {"type": "integer", "default": 10000},
        },
        "required": ["actions"],
        "additionalProperties": False,
    },
}

SCORE_SPEC: dict[str, Any] = {
    "name": "score",
    "description": (
        "Score a single simulation request with explicit weights and return the "
        "decision envelope plus score breakdown."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "request": {
                "type": "object",
                "description": "Simulation request forwarded to POST /v1/score.",
            },
            "scoring_weights": {
                "type": "object",
                "description": "Optional expected_value/downside_risk weights.",
            },
        },
        "required": ["request"],
        "additionalProperties": False,
    },
}

BATCH_SPEC: dict[str, Any] = {
    "name": "batch",
    "description": (
        "Run multiple simulation requests in one call and return per-item success "
        "or failure details."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "object"},
                "minItems": 1,
                "description": "Simulation requests forwarded to POST /v1/batch.",
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
}

COMPARE_SPEC: dict[str, Any] = {
    "name": "compare",
    "description": (
        "Run named scenarios side by side and return the winner plus deltas versus "
        "the best scenario."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "scenarios": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "request": {"type": "object"},
                    },
                    "required": ["name", "request"],
                    "additionalProperties": False,
                },
                "minItems": 2,
                "description": "Named scenarios forwarded to POST /v1/compare.",
            },
            "runs": {"type": "integer"},
            "seed": {"type": "integer"},
        },
        "required": ["scenarios"],
        "additionalProperties": False,
    },
}


async def handler(arguments: dict[str, Any]) -> str:
    actions = arguments.get("actions", [])
    n_sims = int(arguments.get("n_simulations", 10000))

    if len(actions) < 2:
        return json.dumps({"error": "At least 2 actions required for comparison"})

    formatted = []
    for action in actions:
        formatted.append(
            {
                "name": action["name"],
                "request": {
                    "mode": "auto",
                    "runs": n_sims,
                    "scenario": {
                        "variables": action["variables"],
                        "objective": action.get("objective", "maximize"),
                    },
                },
            }
        )

    result = await api("POST", "/v1/recommend", json={"actions": formatted})
    return json.dumps(
        {
            "recommended_action": result.get("recommended_action"),
            "confidence": result.get("confidence"),
            "rationale": result.get("rationale"),
            "ranking": [
                {
                    "rank": a.get("rank"),
                    "name": a.get("name"),
                    "expected_value": a.get("expected_value"),
                    "score": a.get("score"),
                }
                for a in result.get("action_results", [])
            ],
        },
        indent=2,
    )


async def score_handler(arguments: dict[str, Any]) -> str:
    body: dict[str, Any] = {"request": arguments["request"]}
    if "scoring_weights" in arguments:
        body["scoring_weights"] = arguments["scoring_weights"]
    result = await api("POST", "/v1/score", json=body)
    envelope = result.get("envelope", {})
    return json.dumps(
        {
            "recommended_action": envelope.get("recommended_action"),
            "expected_value": envelope.get("expected_value"),
            "probability_of_loss": envelope.get("probability_of_loss"),
            "score": result.get("score"),
            "score_breakdown": result.get("score_breakdown"),
        },
        indent=2,
    )


async def batch_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/batch", json={"items": arguments["items"]})
    return json.dumps(
        {
            "total": result.get("total"),
            "succeeded": result.get("succeeded"),
            "failed": result.get("failed"),
            "results": [
                {
                    "index": item.get("index"),
                    "success": item.get("success"),
                    "recommended_action": (item.get("envelope") or {}).get("recommended_action"),
                    "expected_value": (item.get("envelope") or {}).get("expected_value"),
                    "error": item.get("error"),
                }
                for item in result.get("results", [])
            ],
        },
        indent=2,
    )


async def compare_handler(arguments: dict[str, Any]) -> str:
    body: dict[str, Any] = {"scenarios": arguments["scenarios"]}
    if "runs" in arguments:
        body["runs"] = arguments["runs"]
    if "seed" in arguments:
        body["seed"] = arguments["seed"]
    result = await api("POST", "/v1/compare", json=body)
    return json.dumps(
        {
            "winner": result.get("winner"),
            "margin": result.get("margin"),
            "scenarios": [
                {
                    "name": item.get("name"),
                    "recommended_action": (item.get("envelope") or {}).get("recommended_action"),
                    "expected_value": (item.get("envelope") or {}).get("expected_value"),
                    "probability_of_loss": (item.get("envelope") or {}).get("probability_of_loss"),
                    "delta_vs_best": item.get("delta_vs_best"),
                }
                for item in result.get("scenarios", [])
            ],
        },
        indent=2,
    )
