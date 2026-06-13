"""MCP tools for account identity, limits, and API-key lifecycle."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

GET_ME_SPEC: dict[str, Any] = {
    "name": "get_me",
    "description": "Get current user and organization identity for the active API key.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

UPDATE_ME_SPEC: dict[str, Any] = {
    "name": "update_me",
    "description": "Update the current user name and or organization name for the active API key.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "org_name": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}

GET_LIMITS_SPEC: dict[str, Any] = {
    "name": "get_limits",
    "description": "Get current plan quotas and limits for the active API key.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_DISTRIBUTIONS_SPEC: dict[str, Any] = {
    "name": "list_distributions",
    "description": "List supported distribution types for the active API key.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_TEMPLATES_SPEC: dict[str, Any] = {
    "name": "list_templates",
    "description": "List built-in simulation templates for the active API key.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_API_KEYS_SPEC: dict[str, Any] = {
    "name": "list_api_keys",
    "description": "List active API keys for the current organization. Never returns raw secret material.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

CREATE_API_KEY_SPEC: dict[str, Any] = {
    "name": "create_api_key",
    "description": "Create a new API key and return its one-time raw_key value.",
    "inputSchema": {
        "type": "object",
        "required": ["label"],
        "properties": {
            "label": {"type": "string", "minLength": 1},
            "expires_at": {"type": "string", "format": "date-time"},
            "device_limit": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    },
}

REVOKE_API_KEY_SPEC: dict[str, Any] = {
    "name": "revoke_api_key",
    "description": "Revoke one API key by id.",
    "inputSchema": {
        "type": "object",
        "required": ["key_id"],
        "properties": {
            "key_id": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}


async def get_me_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("get_me does not accept arguments.")
    return json.dumps(await api("GET", "/v1/me"), indent=2)


async def update_me_handler(arguments: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    name = arguments.get("name")
    if name is not None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("update_me.name must be a non-empty string.")
        payload["name"] = name.strip()
    org_name = arguments.get("org_name")
    if org_name is not None:
        if not isinstance(org_name, str) or not org_name.strip():
            raise ValueError("update_me.org_name must be a non-empty string.")
        payload["org_name"] = org_name.strip()
    if not payload:
        raise ValueError("update_me requires name and or org_name.")
    return json.dumps(await api("PATCH", "/v1/me", json=payload), indent=2)


async def get_limits_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("get_limits does not accept arguments.")
    return json.dumps(await api("GET", "/v1/limits"), indent=2)


async def list_distributions_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("list_distributions does not accept arguments.")
    payload = await api("GET", "/v1/distributions")
    items = payload if isinstance(payload, list) else payload.get("distributions", payload)
    return json.dumps({"distributions": items}, indent=2)


async def list_templates_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("list_templates does not accept arguments.")
    payload = await api("GET", "/v1/templates")
    items = payload if isinstance(payload, list) else payload.get("templates", payload)
    return json.dumps({"templates": items}, indent=2)


async def list_api_keys_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("list_api_keys does not accept arguments.")
    payload = await api("GET", "/v1/api-keys")
    items = payload if isinstance(payload, list) else payload.get("api_keys", payload)
    return json.dumps({"api_keys": items}, indent=2)


async def create_api_key_handler(arguments: dict[str, Any]) -> str:
    label = arguments.get("label")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("create_api_key requires a non-empty label.")
    payload: dict[str, Any] = {"label": label.strip()}
    expires_at = arguments.get("expires_at")
    if expires_at is not None:
        if not isinstance(expires_at, str) or not expires_at.strip():
            raise ValueError("create_api_key.expires_at must be a non-empty ISO-8601 string.")
        payload["expires_at"] = expires_at
    device_limit = arguments.get("device_limit")
    if device_limit is not None:
        if isinstance(device_limit, bool) or not isinstance(device_limit, int) or device_limit < 0:
            raise ValueError("create_api_key.device_limit must be an integer greater than or equal to 0.")
        payload["device_limit"] = device_limit
    return json.dumps(await api("POST", "/v1/api-keys", json=payload), indent=2)


async def revoke_api_key_handler(arguments: dict[str, Any]) -> str:
    key_id = arguments.get("key_id")
    if not isinstance(key_id, str) or not key_id.strip():
        raise ValueError("revoke_api_key requires a non-empty key_id.")
    await api("DELETE", f"/v1/api-keys/{key_id}")
    return json.dumps({"key_id": key_id, "revoked": True}, indent=2)
