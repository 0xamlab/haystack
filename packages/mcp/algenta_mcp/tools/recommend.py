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
        "Run one simulation request (the same payload shape as simulate) and return "
        "the decision envelope fields plus a composite score with its breakdown. The "
        "score blends the normalized expected value and one minus the probability of "
        "loss; scoring_weights tunes the blend (expected_value default 0.6, "
        "downside_risk default 0.4). Use simulate when you need the full envelope "
        "without scoring, and compare to rank several scenarios. Synchronous; the "
        "underlying run is persisted. Returns recommended_action, expected_value, "
        "probability_of_loss, score, and score_breakdown."
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
        "Run 2-10 named scenarios side by side and return the winner plus each "
        "scenario's deltas versus the best one. The winner is the scenario with the "
        "highest expected value; every entry reports its recommended_action, "
        "expected_value, probability_of_loss, and delta_vs_best. Each scenario's "
        "request uses the simulate payload shape; runs and seed are forwarded for "
        "reproducibility. Use recommend for a ranked recommendation over actions "
        "instead. Synchronous; the underlying runs are persisted."
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
                "description": (
                    "Named scenarios, each {name, request} with request in the "
                    "simulate payload shape; 2-10 items."
                ),
            },
            "runs": {
                "type": "integer",
                "description": "Scenario count per simulation; forwarded to each run.",
            },
            "seed": {
                "type": "integer",
                "description": "Simulation seed for reproducible results.",
            },
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
