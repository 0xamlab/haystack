"""MCP tools for account identity, limits, and API-key lifecycle."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

GET_ME_SPEC: dict[str, Any] = {
    "name": "get_me",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get current user and organization identity for the active API key. Read-only and "
        "non-destructive; not separately rate-limited. Use update_me to change the returned "
        "names. Returns user_id, name, email, role, and the organization id, name, and "
        "plan."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

UPDATE_ME_SPEC: dict[str, Any] = {
    "name": "update_me",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Update the current user's name and/or the organization name for the active "
        "API key; only the supplied fields change. Renaming the organization requires "
        "an admin or owner key (access_scope_denied otherwise), and the key must be "
        "linked to a user (user_not_found for service keys). At least one of name or "
        "org_name is required. Returns the updated identity; read it first with "
        "get_me."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "description": "New display name for the calling user.",
            },
            "org_name": {
                "type": "string",
                "minLength": 1,
                "description": "New organization name; requires admin or owner role.",
            },
        },
        "additionalProperties": False,
    },
}

GET_LIMITS_SPEC: dict[str, Any] = {
    "name": "get_limits",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Get current plan quotas and limits for the active API key. Read-only and "
        "non-destructive; not separately rate-limited. Use get_usage for current "
        "consumption against these limits. Returns the plan's quota ceilings, including "
        "rate, concurrency, storage, and LLM spend cap."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_DISTRIBUTIONS_SPEC: dict[str, Any] = {
    "name": "list_distributions",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the probability distribution types supported in simulation variables — "
        "normal, uniform, triangular, lognormal, and fixed — each with its required "
        "parameters and a ready-to-use example. Read this before writing variable "
        "definitions for simulate, score, compare, or submit_job. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_TEMPLATES_SPEC: dict[str, Any] = {
    "name": "list_templates",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the built-in simulation templates available to the active API key, "
        "each with its id and intended use. A template id pre-fills a simulation "
        "request, so start here instead of hand-writing variables for common cases "
        "such as a product launch. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

LIST_API_KEYS_SPEC: dict[str, Any] = {
    "name": "list_api_keys",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List active API keys for the current organization. Never returns raw secret "
        "material. Read-only and non-destructive; not separately rate-limited. Use "
        "create_api_key to mint one and revoke_api_key to retire one. Returns the key "
        "records with id, label, key_prefix, device_limit, status, created_at, "
        "last_used_at, and expires_at."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

CREATE_API_KEY_SPEC: dict[str, Any] = {
    "name": "create_api_key",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Create a new API key for the current organization and return its raw_key "
        "value exactly once — it is never shown again, so store it immediately. "
        "expires_at optionally sets an ISO-8601 expiry and device_limit caps how many "
        "devices the key may register (validated against the plan ceiling, "
        "invalid_device_limit on excess). Key creation is rate-limited per "
        "organization (api_key_create_rate_limited). Use list_api_keys to see "
        "existing keys and revoke_api_key to retire one."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["label"],
        "properties": {
            "label": {
                "type": "string",
                "minLength": 1,
                "description": "Human-readable label identifying the key's purpose.",
            },
            "expires_at": {
                "type": "string",
                "format": "date-time",
                "description": "Optional ISO-8601 expiry timestamp for the key.",
            },
            "device_limit": {
                "type": "integer",
                "minimum": 0,
                "description": (
                    "Optional per-key device cap; must not exceed the plan ceiling."
                ),
            },
        },
        "additionalProperties": False,
    },
}

REVOKE_API_KEY_SPEC: dict[str, Any] = {
    "name": "revoke_api_key",
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Revoke one API key by id (find ids with list_api_keys). The key stops "
        "authenticating and the revocation cannot be undone from this tool. Guardrails: "
        "an unknown key_id fails with api_key_not_found, and revoking the "
        "organization's last active key is refused with cannot_revoke_last_key — "
        "create a replacement with create_api_key first. Returns key_id with revoked: "
        "true."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["key_id"],
        "properties": {
            "key_id": {
                "type": "string",
                "minLength": 1,
                "description": "API key id from list_api_keys.",
            },
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
