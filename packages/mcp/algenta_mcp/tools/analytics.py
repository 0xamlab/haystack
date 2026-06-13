"""MCP tool: get_analytics."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

SPEC: dict[str, Any] = {
    "name": "get_analytics",
    "description": "Get usage analytics: simulation volume, latency p95, outcome distributions.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "days": {"type": "integer", "default": 30, "description": "Lookback window in days"},
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
