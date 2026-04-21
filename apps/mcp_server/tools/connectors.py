"""MCP tool: list_connectors."""
from __future__ import annotations

import json
from typing import Any

from apps.mcp_server.client import api

SPEC: dict[str, Any] = {
    "name": "list_connectors",
    "description": (
        "Advanced tool. List configured data connectors "
        "(databases, spreadsheets, APIs)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["active", "error", "all"], "default": "all"},
        },
    },
}


async def handler(arguments: dict[str, Any]) -> str:
    result = await api("GET", "/v1/connectors")
    connectors = result if isinstance(result, list) else result.get("connectors", [])
    status_filter = arguments.get("status", "all")
    if status_filter != "all":
        connectors = [c for c in connectors if c.get("status") == status_filter]
    return json.dumps({
        "total":      len(connectors),
        "connectors": [
            {
                "id":             c.get("id"),
                "name":           c.get("name"),
                "connector_type": c.get("connector_type"),
                "status":         c.get("status"),
                "last_tested_at": c.get("last_tested_at"),
            }
            for c in connectors
        ],
    }, indent=2)
