"""MCP tools: list_runs, get_run."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_RUNS_SPEC: dict[str, Any] = {
    "name": "list_runs",
    "description": "List recent simulation runs with optional filters.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "default": 20,
                "description": "Max results (1-100)",
            },
            "mode": {
                "type": "string",
                "enum": ["auto", "expert"],
                "description": "Filter by mode",
            },
            "status": {"type": "string", "enum": ["completed", "failed", "running"]},
        },
    },
}

GET_RUN_SPEC: dict[str, Any] = {
    "name": "get_run",
    "description": "Fetch a single simulation run by ID.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "UUID of the simulation run"},
        },
        "required": ["run_id"],
    },
}


async def list_runs_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {"limit": arguments.get("limit", 20)}
    if arguments.get("mode"):
        params["mode"] = arguments["mode"]
    if arguments.get("status"):
        params["status"] = arguments["status"]
    result = await api("GET", "/v1/runs", params=params)
    runs = result.get("runs", [])
    return json.dumps(
        {
            "total": result.get("total", len(runs)),
            "runs": [
                {
                    "run_id": r.get("run_id"),
                    "recommended_action": r.get("recommended_action"),
                    "confidence": r.get("confidence"),
                    "expected_value": r.get("expected_value"),
                    "created_at": r.get("created_at"),
                    "mode": r.get("mode"),
                }
                for r in runs[:50]
            ],
        },
        indent=2,
    )


async def get_run_handler(arguments: dict[str, Any]) -> str:
    run_id = arguments.get("run_id")
    if not run_id:
        return json.dumps({"error": "run_id is required"})
    result = await api("GET", f"/v1/runs/{run_id}")
    return json.dumps(result, indent=2)
