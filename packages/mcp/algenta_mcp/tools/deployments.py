"""MCP tools for deployment control-plane surfaces."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

LIST_DEPLOYMENT_REGIONS_SPEC: dict[str, Any] = {
    "name": "list_deployment_regions",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List available deployment providers and regions for the current organization. "
        "Read-only and non-destructive; not separately rate-limited. Call this before "
        "create_deployment to pick a valid provider/region pair. Returns the providers "
        "array with each provider's id, name, description, and regions (use a region id "
        "when creating)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_DEPLOYMENT_SPEC: dict[str, Any] = {
    "name": "get_deployment",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch the current deployment for the active organization, if one exists. Read-only "
        "and non-destructive; not separately rate-limited. Poll this after "
        "create_deployment until status is active. Returns the deployment record "
        "(deployment_id, provider, region, status, config, created_at) or null when the "
        "organization is on the shared pool."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

CREATE_DEPLOYMENT_SPEC: dict[str, Any] = {
    "name": "create_deployment",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Request a new isolated engine deployment for the active organization on the "
        "chosen provider and region. Returns immediately with status requested — "
        "provisioning is asynchronous, so poll get_deployment until status is active; "
        "API calls then route to the isolated deployment automatically. Requires an "
        "owner API key. Only one active or in-progress deployment is allowed per org "
        "(deployment_exists otherwise — call delete_deployment first), and unknown "
        "provider/region pairs fail validation; list_deployment_regions shows the "
        "valid combinations."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "Cloud provider: algenta_shared (default), aws, azure, or gcp."
                ),
            },
            "region": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "Region id from list_deployment_regions; defaults to "
                    "algenta-shared."
                ),
            },
            "config": {
                "type": "object",
                "description": "Optional provider-specific configuration.",
            },
            "billing_markup_pct": {
                "type": "number",
                "minimum": 0,
                "maximum": 200,
                "description": "Billing markup percentage applied to this deployment, 0-200.",
            },
        },
        "additionalProperties": False,
    },
}

GET_DEPLOYMENT_COST_SPEC: dict[str, Any] = {
    "name": "get_deployment_cost",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get the current-month cost details of one deployment by id: provider, "
        "region, cost_usd_month, billable_cost_usd_month after markup, the applied "
        "billing_markup_pct, and last_updated. Requires an admin API key; an unknown "
        "deployment_id fails with not_found. Use get_deployment to find the active "
        "deployment first, and get_billing_info for the organization's plan and "
        "subscription state instead of per-deployment cost. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["deployment_id"],
        "properties": {
            "deployment_id": {
                "type": "string",
                "minLength": 1,
                "description": "Deployment id from get_deployment.",
            },
        },
        "additionalProperties": False,
    },
}

DELETE_DEPLOYMENT_SPEC: dict[str, Any] = {
    "name": "delete_deployment",
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Request deprovisioning for one deployment by id. Deprovision with this before "
        "create_deployment when a deployment already exists. Deleting is idempotent: "
        "repeating the call on an already-deprovisioned or never-existing id returns "
        "success with already_absent: true instead of an error. Returns status "
        "'deprovisioning' with the deployment_id; deprovisioning is asynchronous."
    ),
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
