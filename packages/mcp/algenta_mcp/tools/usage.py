"""MCP tool: get_usage."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

SPEC: dict[str, Any] = {
    "name": "get_usage",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get current billing period usage vs quota for this API key. "
        "Read-only and non-destructive; not separately rate-limited."
    ),
    "inputSchema": {"type": "object", "properties": {}},
}


async def handler(arguments: dict[str, Any]) -> str:
    result = await api("GET", "/v1/usage")
    return json.dumps(
        {
            "simulations_used": result.get("simulations_run"),
            "simulations_limit": result.get("quota_limit"),
            "billing_period": result.get("billing_period"),
            "plan": result.get("plan"),
            "api_calls": result.get("api_calls"),
            "pct_used": result.get("quota_used_pct"),
        },
        indent=2,
    )
