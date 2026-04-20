"""MCP tool: recommend — compare actions and get a ranked recommendation."""
from __future__ import annotations

import json
from typing import Any

from apps.mcp_server.client import api

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
                        "name":      {"type": "string"},
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
    },
}


async def handler(arguments: dict[str, Any]) -> str:
    actions  = arguments.get("actions", [])
    n_sims   = int(arguments.get("n_simulations", 10000))

    if len(actions) < 2:
        return json.dumps({"error": "At least 2 actions required for comparison"})

    formatted = []
    for action in actions:
        formatted.append({
            "name": action["name"],
            "request": {
                "mode": "auto",
                "n_simulations": n_sims,
                "scenario": {
                    "variables": action["variables"],
                    "objective": action.get("objective", "maximize"),
                },
            },
        })

    result = await api("POST", "/v1/recommend", json={"actions": formatted})
    return json.dumps({
        "recommended_action": result.get("recommended_action"),
        "confidence":         result.get("confidence"),
        "rationale":          result.get("rationale"),
        "ranking": [
            {
                "rank":           a.get("rank"),
                "name":           a.get("name"),
                "expected_value": a.get("expected_value"),
                "score":          a.get("score"),
            }
            for a in result.get("action_results", [])
        ],
    }, indent=2)
