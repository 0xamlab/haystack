"""MCP tools for saved connector lifecycle management."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from algenta_mcp.client import api

LIST_CONNECTORS_SPEC: dict[str, Any] = {
    "name": "list_connectors",
    "description": (
        "List saved data connectors such as databases, APIs, and file-backed sources. "
        "Use this before get_connector, test_connector, or browse_connector."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "limit": {"type": "integer", "minimum": 1, "default": 25},
            "status": {
                "type": "string",
                "enum": ["untested", "live", "error", "all"],
                "default": "all",
            },
        },
        "additionalProperties": False,
    },
}

CREATE_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "create_connector",
    "description": (
        "Create and save one connector configuration for later data onboarding, health checks, "
        "and schema browsing."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["name", "connector_type"],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "connector_type": {"type": "string", "minLength": 1},
            "config": {"type": "object"},
            "description": {"type": "string"},
            "visibility": {"type": "string", "enum": ["private", "organization", "public"]},
        },
        "additionalProperties": False,
    },
}

GET_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "get_connector",
    "description": "Fetch one saved connector by id.",
    "inputSchema": {
        "type": "object",
        "required": ["connector_id"],
        "properties": {
            "connector_id": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}

UPDATE_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "update_connector",
    "description": "Update one saved connector name, description, visibility, or config.",
    "inputSchema": {
        "type": "object",
        "required": ["connector_id"],
        "properties": {
            "connector_id": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "description": {"type": "string"},
            "visibility": {"type": "string", "enum": ["private", "organization", "public"]},
            "config": {"type": "object"},
        },
        "additionalProperties": False,
    },
}

TEST_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "test_connector",
    "description": "Run a real connectivity test for one saved connector and persist its live/error status.",
    "inputSchema": {
        "type": "object",
        "required": ["connector_id"],
        "properties": {
            "connector_id": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}

BROWSE_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "browse_connector",
    "description": "Browse one saved live connector to discover files, tables, endpoints, or items.",
    "inputSchema": {
        "type": "object",
        "required": ["connector_id"],
        "properties": {
            "connector_id": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}

PREVIEW_TEST_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "preview_test_connector",
    "description": (
        "Run a real connectivity test for one inline connector definition without saving it."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["connector_type"],
        "properties": {
            "connector_type": {"type": "string", "minLength": 1},
            "config": {"type": "object"},
        },
        "additionalProperties": False,
    },
}

PREVIEW_BROWSE_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "preview_browse_connector",
    "description": (
        "Browse one inline connector definition without saving it to discover files, tables, "
        "endpoints, or items."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["connector_type"],
        "properties": {
            "connector_type": {"type": "string", "minLength": 1},
            "config": {"type": "object"},
        },
        "additionalProperties": False,
    },
}

DELETE_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "delete_connector",
    "description": "Delete one saved connector by id.",
    "inputSchema": {
        "type": "object",
        "required": ["connector_id"],
        "properties": {
            "connector_id": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}


def _normalized_connector_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        raw_items = payload.get("connectors")
        if isinstance(raw_items, list):
            return [item for item in raw_items if isinstance(item, dict)]
    return []


def _connector_id(arguments: dict[str, Any]) -> str | None:
    connector_id = arguments.get("connector_id")
    if not isinstance(connector_id, str) or not connector_id.strip():
        return None
    return connector_id.strip()


async def list_connectors_handler(arguments: dict[str, Any]) -> str:
    page = int(arguments.get("page", 1))
    limit = int(arguments.get("limit", 25))
    if page < 1:
        raise ValueError("list_connectors.page must be at least 1.")
    if limit < 1:
        raise ValueError("list_connectors.limit must be at least 1.")
    path = f"/v1/connectors?{urlencode({'page': page, 'limit': limit})}"
    payload = await api("GET", path)
    connectors = _normalized_connector_items(payload)
    status_filter = arguments.get("status", "all")
    if status_filter != "all":
        connectors = [item for item in connectors if item.get("status") == status_filter]
    total = len(connectors)
    if isinstance(payload, dict) and isinstance(payload.get("total"), int) and status_filter == "all":
        total = payload["total"]
    return json.dumps(
        {
            "page": page,
            "limit": limit,
            "total": total,
            "connectors": connectors,
        },
        indent=2,
    )


async def create_connector_handler(arguments: dict[str, Any]) -> str:
    name = arguments.get("name")
    connector_type = arguments.get("connector_type")
    if not isinstance(name, str) or not name.strip():
        return json.dumps({"error": "name is required"})
    if not isinstance(connector_type, str) or not connector_type.strip():
        return json.dumps({"error": "connector_type is required"})
    payload: dict[str, Any] = {
        "name": name.strip(),
        "connector_type": connector_type.strip(),
    }
    config = arguments.get("config")
    if config is not None:
        if not isinstance(config, dict):
            raise ValueError("create_connector.config must be an object when provided.")
        payload["config"] = config
    description = arguments.get("description")
    if description is not None:
        if not isinstance(description, str):
            raise ValueError("create_connector.description must be a string when provided.")
        payload["description"] = description
    visibility = arguments.get("visibility")
    if visibility is not None:
        if not isinstance(visibility, str) or visibility not in {"private", "organization", "public"}:
            raise ValueError(
                "create_connector.visibility must be one of private, organization, or public."
            )
        payload["visibility"] = visibility
    return json.dumps(await api("POST", "/v1/connectors", json=payload), indent=2)


async def get_connector_handler(arguments: dict[str, Any]) -> str:
    connector_id = _connector_id(arguments)
    if connector_id is None:
        return json.dumps({"error": "connector_id is required"})
    return json.dumps(await api("GET", f"/v1/connectors/{connector_id}"), indent=2)


async def update_connector_handler(arguments: dict[str, Any]) -> str:
    connector_id = _connector_id(arguments)
    if connector_id is None:
        return json.dumps({"error": "connector_id is required"})
    payload: dict[str, Any] = {}
    name = arguments.get("name")
    if name is not None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("update_connector.name must be a non-empty string when provided.")
        payload["name"] = name.strip()
    description = arguments.get("description")
    if description is not None:
        if not isinstance(description, str):
            raise ValueError("update_connector.description must be a string when provided.")
        payload["description"] = description
    visibility = arguments.get("visibility")
    if visibility is not None:
        if not isinstance(visibility, str) or visibility not in {"private", "organization", "public"}:
            raise ValueError(
                "update_connector.visibility must be one of private, organization, or public."
            )
        payload["visibility"] = visibility
    config = arguments.get("config")
    if config is not None:
        if not isinstance(config, dict):
            raise ValueError("update_connector.config must be an object when provided.")
        payload["config"] = config
    if not payload:
        return json.dumps({"error": "update_connector requires at least one field to update"})
    return json.dumps(await api("PATCH", f"/v1/connectors/{connector_id}", json=payload), indent=2)


async def test_connector_handler(arguments: dict[str, Any]) -> str:
    connector_id = _connector_id(arguments)
    if connector_id is None:
        return json.dumps({"error": "connector_id is required"})
    return json.dumps(await api("POST", f"/v1/connectors/{connector_id}/test"), indent=2)


async def preview_test_connector_handler(arguments: dict[str, Any]) -> str:
    connector_type = arguments.get("connector_type")
    if not isinstance(connector_type, str) or not connector_type.strip():
        return json.dumps({"error": "connector_type is required"})
    payload: dict[str, Any] = {"connector_type": connector_type.strip()}
    config = arguments.get("config")
    if config is not None:
        if not isinstance(config, dict):
            raise ValueError("preview_test_connector.config must be an object when provided.")
        payload["config"] = config
    return json.dumps(await api("POST", "/v1/connectors/test", json=payload), indent=2)


async def browse_connector_handler(arguments: dict[str, Any]) -> str:
    connector_id = _connector_id(arguments)
    if connector_id is None:
        return json.dumps({"error": "connector_id is required"})
    return json.dumps(await api("GET", f"/v1/connectors/{connector_id}/browse"), indent=2)


async def preview_browse_connector_handler(arguments: dict[str, Any]) -> str:
    connector_type = arguments.get("connector_type")
    if not isinstance(connector_type, str) or not connector_type.strip():
        return json.dumps({"error": "connector_type is required"})
    payload: dict[str, Any] = {"connector_type": connector_type.strip()}
    config = arguments.get("config")
    if config is not None:
        if not isinstance(config, dict):
            raise ValueError("preview_browse_connector.config must be an object when provided.")
        payload["config"] = config
    return json.dumps(await api("POST", "/v1/connectors/browse", json=payload), indent=2)


async def delete_connector_handler(arguments: dict[str, Any]) -> str:
    connector_id = _connector_id(arguments)
    if connector_id is None:
        return json.dumps({"error": "connector_id is required"})
    await api("DELETE", f"/v1/connectors/{connector_id}")
    return json.dumps({"connector_id": connector_id, "deleted": True}, indent=2)


# Backward-compatible aliases used by older focused tests.
SPEC = LIST_CONNECTORS_SPEC
handler = list_connectors_handler
