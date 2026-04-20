"""MCP tool: get_usage."""
from __future__ import annotations

import json
from typing import Any

from apps.mcp_server.client import api

SPEC: dict[str, Any] = {
    "name": "get_usage",
    "description": "Get current billing period usage vs quota for this API key.",
    "inputSchema": {"type": "object", "properties": {}},
}


async def handler(arguments: dict[str, Any]) -> str:
    result = await api("GET", "/v1/account/usage")
    return json.dumps({
        "simulations_used":  result.get("simulations_used"),
        "simulations_limit": result.get("simulations_limit"),
        "billing_period":    result.get("billing_period"),
        "plan":              result.get("plan"),
        "pct_used": (
            round(result["simulations_used"] / result["simulations_limit"] * 100, 1)
            if result.get("simulations_limit")
            else None
        ),
    }, indent=2)
