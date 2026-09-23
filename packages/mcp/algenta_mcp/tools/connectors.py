"""MCP tools for saved connector lifecycle management."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from algenta_mcp.client import api

LIST_CONNECTORS_SPEC: dict[str, Any] = {
    "name": "list_connectors",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the data connectors saved under the caller's organization — databases, "
        "APIs, file-backed, and repository sources — with id, name, connector_type, "
        "status (untested, live, error), and visibility; stored credentials are never "
        "returned. Paginated with page and limit; status filters the returned page "
        "client-side. Use this first to find a connector_id for get_connector, "
        "test_connector, browse_connector, or the repository tools, and "
        "create_connector to add one. Read-only."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {
                "type": "integer",
                "minimum": 1,
                "default": 1,
                "description": "1-based page number; defaults to 1.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "default": 25,
                "description": "Connectors per page; defaults to 25.",
            },
            "status": {
                "type": "string",
                "enum": ["untested", "live", "error", "all"],
                "default": "all",
                "description": "Keep only connectors in this health status; defaults to all.",
            },
        },
        "additionalProperties": False,
    },
}

CREATE_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "create_connector",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Save one connector configuration (host, credentials, options) for later data "
        "onboarding, health checks, and schema browsing. config is encrypted at rest "
        "and the new connector starts untested — call test_connector to verify it "
        "reaches the source, then browse_connector to discover what it exposes. Returns "
        "the saved connector with its connector_id, persisted under the active API "
        "key's organization. To try a definition without saving anything, call "
        "preview_test_connector instead."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["name", "connector_type"],
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "description": "Human-readable connector name.",
            },
            "connector_type": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "Connector type id, e.g. a database, API, file, or repository type."
                ),
            },
            "config": {
                "type": "object",
                "description": (
                    "Type-specific connection settings and credentials; encrypted at "
                    "rest and never returned."
                ),
            },
            "description": {
                "type": "string",
                "description": "Optional note on what this connector is for.",
            },
            "visibility": {
                "type": "string",
                "enum": ["private", "organization", "public"],
                "description": "Who can see the connector; defaults to private.",
            },
        },
        "additionalProperties": False,
    },
}

GET_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "get_connector",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch one saved connector by connector_id: name, connector_type, status, "
        "visibility, timestamps, and the config fingerprint — never the stored "
        "credentials. Use list_connectors to find ids. Read-only; an unknown or "
        "invisible id fails with not_found."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["connector_id"],
        "properties": {
            "connector_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved connector id from list_connectors.",
            },
        },
        "additionalProperties": False,
    },
}

UPDATE_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "update_connector",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Partially update one saved connector: only the supplied fields change. Passing a "
        "new config replaces the encrypted credentials and resets the connector to "
        "untested, so call test_connector again afterwards. Requires manage permission on "
        "the connector (access_scope_denied otherwise) and at least one field; an unknown "
        "id fails with not_found. Returns the updated connector. Use preview_test_connector "
        "to validate a new config before applying it here."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["connector_id"],
        "properties": {
            "connector_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved connector id from list_connectors.",
            },
            "name": {
                "type": "string",
                "minLength": 1,
                "description": "New human-readable name.",
            },
            "description": {
                "type": "string",
                "description": "New description note.",
            },
            "visibility": {
                "type": "string",
                "enum": ["private", "organization", "public"],
                "description": "New visibility.",
            },
            "config": {
                "type": "object",
                "description": (
                    "Replacement connection config; resets health status to untested."
                ),
            },
        },
        "additionalProperties": False,
    },
}

TEST_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "test_connector",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Run a real connectivity test against one saved connector's stored config and "
        "persist the outcome as its live or error status with last_tested_at. This "
        "opens an actual connection to the source. Use preview_test_connector for an "
        "unsaved inline definition, and browse_connector once the connector is live. "
        "Returns success, message, latency_ms, status, error_type, and recoverable."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["connector_id"],
        "properties": {
            "connector_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved connector id from list_connectors.",
            },
        },
        "additionalProperties": False,
    },
}

BROWSE_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "browse_connector",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Discover what one saved connector exposes — files, tables, endpoints, or "
        "items — with discovery labels and metadata for choosing what to onboard. The "
        "connector must be live: an untested or errored connector fails with "
        "not_connected, so run test_connector first. Use preview_browse_connector for "
        "an unsaved inline definition. Read-only against the source. Returns "
        "connector_type, items, total, message, labels, and discovery."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["connector_id"],
        "properties": {
            "connector_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved connector id from list_connectors.",
            },
        },
        "additionalProperties": False,
    },
}

PREVIEW_TEST_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "preview_test_connector",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Run a real connectivity test against an inline connector definition without "
        "saving anything — the dry run for create_connector. This opens an actual "
        "connection to the source, is rate-limited per organization, and caches "
        "successful outcomes briefly. Nothing is persisted. Returns success, message, "
        "latency_ms, status, error_type, and recoverable; call create_connector once "
        "the definition passes."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["connector_type"],
        "properties": {
            "connector_type": {
                "type": "string",
                "minLength": 1,
                "description": "Connector type id to test.",
            },
            "config": {
                "type": "object",
                "description": "Inline connection settings and credentials to test.",
            },
        },
        "additionalProperties": False,
    },
}

PREVIEW_BROWSE_CONNECTOR_SPEC: dict[str, Any] = {
    "name": "preview_browse_connector",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Browse one inline connector definition without saving it to discover files, "
        "tables, endpoints, or items. This opens a real connection to the source and is "
        "rate-limited per organization; nothing is saved. Use browse_connector for saved "
        "connectors. Returns connector_type, items, total, message, labels, and discovery "
        "metadata."
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
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Delete one saved connector by id. Use update_connector to change config without "
        "losing the saved definition. Returns connector_id with deleted: true."
    ),
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
