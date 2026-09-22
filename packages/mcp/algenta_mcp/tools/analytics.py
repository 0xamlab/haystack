"""MCP tool: get_analytics."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

SPEC: dict[str, Any] = {
    "name": "get_analytics",
    "description": (
        "Get aggregate usage analytics over the organization's simulation runs inside "
        "a lookback window: total_simulations, avg_confidence, action_breakdown (how "
        "recommended actions distribute), and latency_p95_ms. days sets the window "
        "(default 30, range 1-365). Use list_runs for individual runs instead of "
        "aggregates. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "default": 30,
                "description": "Lookback window in days",
            },
        },
    },
}


async def handler(arguments: dict[str, Any]) -> str:
    days = int(arguments.get("days", 30))
    result = await api("GET", "/v1/runs/analytics", params={"days": days})
    return json.dumps(
        {
            "total_simulations": result.get("total_simulations"),
            "avg_confidence": result.get("avg_confidence"),
            "action_breakdown": result.get("action_breakdown"),
            "latency_p95_ms": result.get("latency_p95_ms"),
            "period_days": days,
        },
        indent=2,
    )
