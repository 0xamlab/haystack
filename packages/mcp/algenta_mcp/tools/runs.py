"""MCP tools: list_runs, get_run."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_RUNS_SPEC: dict[str, Any] = {
    "name": "list_runs",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the organization's recent simulation runs, newest first, with their "
        "recommended_action, confidence, expected_value, mode, and created_at. "
        "Optional filters narrow by mode (auto or expert) and status (completed, "
        "failed, running); limit caps the results (default 20, up to 100). Use "
        "get_run for one run's full detail and get_analytics for aggregate trends. "
        "Read-only. Returns runs plus total."
    ),
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
            "status": {
                "type": "string",
                "enum": ["completed", "failed", "running"],
                "description": "Keep only runs in this status.",
            },
        },
    },
}

GET_RUN_SPEC: dict[str, Any] = {
    "name": "get_run",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch one simulation run by run_id with its full detail — the decision metrics and "
        "the request context it ran under. Use list_runs to find run ids. Read-only; an "
        "unknown run_id fails with not_found. Returns the run record: run_id, "
        "recommended_action, confidence, expected_value, mode, and created_at."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "run_id": {
                "type": "string",
                "description": "UUID of the simulation run",
            },
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
