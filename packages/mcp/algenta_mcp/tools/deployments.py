"""MCP tools for deployment control-plane surfaces."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_DEPLOYMENT_REGIONS_SPEC: dict[str, Any] = {
    "name": "list_deployment_regions",
    "description": "List available deployment providers and regions for the current organization.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_DEPLOYMENT_SPEC: dict[str, Any] = {
    "name": "get_deployment",
    "description": "Fetch the current deployment for the active organization, if one exists.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

CREATE_DEPLOYMENT_SPEC: dict[str, Any] = {
    "name": "create_deployment",
    "description": "Request a new isolated deployment for the active organization.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "provider": {"type": "string", "minLength": 1},
            "region": {"type": "string", "minLength": 1},
            "config": {"type": "object"},
            "billing_markup_pct": {"type": "number", "minimum": 0, "maximum": 200},
        },
        "additionalProperties": False,
    },
}

GET_DEPLOYMENT_COST_SPEC: dict[str, Any] = {
    "name": "get_deployment_cost",
    "description": "Get current-month cost details for one deployment by id.",
    "inputSchema": {
        "type": "object",
        "required": ["deployment_id"],
        "properties": {
            "deployment_id": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}

DELETE_DEPLOYMENT_SPEC: dict[str, Any] = {
    "name": "delete_deployment",
    "description": "Request deprovisioning for one deployment by id.",
    "inputSchema": {
        "type": "object",
        "required": ["deployment_id"],
        "properties": {
            "deployment_id": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}


async def list_deployment_regions_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("list_deployment_regions does not accept arguments.")
    return json.dumps(await api("GET", "/v1/deployments/regions"), indent=2)


async def get_deployment_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("get_deployment does not accept arguments.")
    return json.dumps(await api("GET", "/v1/deployments"), indent=2)


async def create_deployment_handler(arguments: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    provider = arguments.get("provider")
    if provider is not None:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("create_deployment.provider must be a non-empty string.")
        payload["provider"] = provider.strip()
    region = arguments.get("region")
    if region is not None:
        if not isinstance(region, str) or not region.strip():
            raise ValueError("create_deployment.region must be a non-empty string.")
        payload["region"] = region.strip()
    config = arguments.get("config")
    if config is not None:
        if not isinstance(config, dict):
            raise ValueError("create_deployment.config must be a JSON object.")
        payload["config"] = config
    billing_markup_pct = arguments.get("billing_markup_pct")
    if billing_markup_pct is not None:
        if isinstance(billing_markup_pct, bool) or not isinstance(billing_markup_pct, (int, float)):
            raise ValueError("create_deployment.billing_markup_pct must be a number.")
        payload["billing_markup_pct"] = float(billing_markup_pct)
    return json.dumps(await api("POST", "/v1/deployments", json=payload), indent=2)


async def get_deployment_cost_handler(arguments: dict[str, Any]) -> str:
    deployment_id = arguments.get("deployment_id")
    if not isinstance(deployment_id, str) or not deployment_id.strip():
        raise ValueError("get_deployment_cost requires a non-empty deployment_id.")
    return json.dumps(await api("GET", f"/v1/deployments/{deployment_id}/cost"), indent=2)


async def delete_deployment_handler(arguments: dict[str, Any]) -> str:
    deployment_id = arguments.get("deployment_id")
    if not isinstance(deployment_id, str) or not deployment_id.strip():
        raise ValueError("delete_deployment requires a non-empty deployment_id.")
    return json.dumps(await api("DELETE", f"/v1/deployments/{deployment_id}"), indent=2)
