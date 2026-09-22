"""MCP tools for the high-level Connections/Datasets flow."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp import config
from algenta_mcp.client import api


def _strip_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


CONNECT_SPEC: dict[str, Any] = {
    "name": "connect_data",
    "description": (
        "High-level data onboarding flow. "
        "Use this instead of advanced connector/source tools for normal users. "
        "Connect data once, pick the table/file/endpoint, and get a reusable dataset_id. "
        "If the result status is needs_selection, call connect_data again with "
        "connection_id and the chosen selection."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["dataset_name"],
        "properties": {
            "connection_type": {
                "type": "string",
                "enum": ["database", "api", "object_storage", "file_upload"],
                "description": (
                    "Legacy compatibility field. Prefer connector.type with the "
                    "canonical connector envelope."
                ),
            },
            "dataset_name": {
                "type": "string",
                "description": "Name to save and reuse later.",
            },
            "provider": {
                "type": "string",
                "description": (
                    "Legacy compatibility field for provider selection. Prefer "
                    "connector.type plus connector.location/auth/options."
                ),
            },
            "connector": {
                "type": "object",
                "description": (
                    "Canonical connector envelope with type/location/auth/options. "
                    "Preferred when the same request shape should work across "
                    "Python Runtime, TypeScript Runtime, and MCP."
                ),
            },
            "connection_id": {
                "type": "string",
                "description": "Existing saved connection_id when resuming after selection.",
            },
            "connection_name": {
                "type": "string",
                "description": "Optional label for the saved connection.",
            },
            "connection_config": {
                "type": "object",
                "description": (
                    "Legacy compatibility field for connector credentials/config. "
                    "Prefer connector.location and connector.auth.credentials."
                ),
            },
            "selection": {
                "type": "object",
                "description": (
                    "Legacy compatibility field for chosen table/query/path. "
                    "Use the selection object returned in choices when resuming "
                    "a legacy connection flow."
                ),
            },
            "description": {"type": "string"},
            "visibility": {
                "type": "string",
                "enum": ["private", "shared"],
                "description": "Shared requires admin/owner permissions.",
            },
            "records": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Inline JSON records for direct file_upload datasets.",
            },
            "csv": {
                "type": "string",
                "description": "Raw CSV text for direct file_upload datasets.",
            },
            "json_str": {
                "type": "string",
                "description": "Raw JSON text for direct file_upload datasets.",
            },
            "url": {"type": "string", "description": "URL for direct file_upload or API datasets."},
            "excel_b64": {"type": "string", "description": "Base64-encoded Excel payload."},
            "parquet_b64": {"type": "string", "description": "Base64-encoded Parquet payload."},
        },
    },
}

LIST_SPEC: dict[str, Any] = {
    "name": "list_data",
    "description": (
        "List visible datasets for the current user. "
        "Use search plus compact mode first for low-token dataset discovery, "
        "then get_data_schema on the chosen dataset_id."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "description": "Page number (default 1)."},
            "limit": {
                "type": "integer",
                "description": (
                    "Results per page (default: all visible datasets, max 200 when set)."
                ),
            },
            "search": {
                "type": "string",
                "description": (
                    "Deterministic lexical filter over dataset_id, name, and source_names."
                ),
            },
            "status": {
                "type": "string",
                "description": "Optional dataset readiness filter such as ready or training.",
            },
            "source_name": {
                "type": "string",
                "description": "Optional source-name filter for narrowed dataset discovery.",
            },
            "compact": {
                "type": "boolean",
                "description": "When true, request the low-token compact dataset discovery shape.",
            },
        },
    },
}

GET_SCHEMA_SPEC: dict[str, Any] = {
    "name": "get_data_schema",
    "description": "Get a saved dataset plus its schema and relationship metadata by dataset_id.",
    "inputSchema": {
        "type": "object",
        "required": ["dataset_id"],
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": "Dataset ID from connect_data or list_data.",
            },
        },
    },
}

GET_SUMMARY_SPEC: dict[str, Any] = {
    "name": "get_data_summary",
    "description": (
        "Get the low-token dataset selection summary for a saved dataset_id. "
        "Use this after list_data(search=..., compact=true) before paying for "
        "the full schema payload."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["dataset_id"],
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": "Dataset ID from connect_data or list_data.",
            },
        },
    },
}

REFRESH_SPEC: dict[str, Any] = {
    "name": "refresh_data",
    "description": (
        "Re-pull a saved dataset from its original database, API, or object-store "
        "origin using the stored connection and selection, and return the same "
        "envelope as connect_data (status, schema_summary, refreshable). Only datasets "
        "created from a live connection can refresh — an inline upload fails with "
        "not_refreshable (check the refreshable flag in list_data first), and an "
        "unknown dataset_id fails with not_found."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["dataset_id"],
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": "Dataset ID from connect_data or list_data.",
            },
        },
    },
}

DISCONNECT_SPEC: dict[str, Any] = {
    "name": "disconnect_data",
    "description": (
        "Delete a saved dataset and disconnect it from future use. When no other "
        "dataset in the workspace still uses the backing saved connection, that "
        "connection is deleted too and connection_deleted is true in the response. "
        "Requires manage permission on the dataset (access_scope_denied otherwise); "
        "an unknown dataset_id fails with not_found. Use list_data to confirm the "
        "dataset first — deletion is immediate. Returns dataset_id, status 'deleted', "
        "and connection_deleted."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["dataset_id"],
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": "Dataset ID from connect_data or list_data.",
            },
        },
    },
}


async def connect_handler(arguments: dict[str, Any]) -> str:
    body = _strip_none(
        {
            "connection_type": arguments.get("connection_type"),
            "dataset_name": arguments.get("dataset_name"),
            "provider": arguments.get("provider"),
            "connector": arguments.get("connector"),
            "connection_id": arguments.get("connection_id"),
            "connection_name": arguments.get("connection_name"),
            "connection_config": arguments.get("connection_config"),
            "selection": arguments.get("selection"),
            "description": arguments.get("description"),
            "visibility": arguments.get("visibility"),
            "records": arguments.get("records"),
            "csv": arguments.get("csv"),
            "json_str": arguments.get("json_str"),
            "url": arguments.get("url"),
            "excel_b64": arguments.get("excel_b64"),
            "parquet_b64": arguments.get("parquet_b64"),
        }
    )
    result = await api(
        "POST",
        "/v1/data/connect",
        json=body,
        timeout=config.CONNECT_TIMEOUT,
    )
    output = _strip_none(
        {
            "status": result.get("status"),
            "message": result.get("message"),
            "dataset_id": result.get("dataset_id"),
            "connection_id": result.get("connection_id"),
            "connection_type": result.get("connection_type"),
            "provider": result.get("provider"),
            "visibility": result.get("visibility"),
            "selection": result.get("selection"),
            "schema_summary": result.get("schema_summary"),
            "refreshable": result.get("refreshable"),
            "latency_ms": result.get("latency_ms"),
            "choices": result.get("choices"),
        }
    )
    return json.dumps(output, indent=2)


async def list_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    if "page" in arguments:
        params["page"] = arguments["page"]
    if "limit" in arguments:
        params["limit"] = arguments["limit"]
    if "search" in arguments:
        params["search"] = arguments["search"]
    if "status" in arguments:
        params["status"] = arguments["status"]
    if "source_name" in arguments:
        params["source_name"] = arguments["source_name"]
    if "compact" in arguments:
        params["compact"] = arguments["compact"]
    result = await api("GET", "/v1/data", params=params)
    datasets = result.get("datasets", [])
    return json.dumps(
        {
            "count": result.get("count", len(datasets)),
            "total": result.get("total", len(datasets)),
            "matched_total": result.get("matched_total", result.get("count", len(datasets))),
            "page": result.get("page", 1),
            "limit": result.get("limit", len(datasets)),
            "pages": result.get("pages", 1),
            "datasets": [
                {
                    "dataset_id": dataset.get("dataset_id"),
                    "dataset_name": dataset.get("dataset_name") or dataset.get("name"),
                    "name": dataset.get("name") or dataset.get("dataset_name"),
                    "status": dataset.get("status"),
                    "source_names": dataset.get("source_names", []),
                    "connection_type": dataset.get("connection_type"),
                    "provider": dataset.get("provider"),
                    "visibility": dataset.get("visibility"),
                    "row_count": dataset.get("row_count"),
                    "column_count": dataset.get("column_count", dataset.get("columns")),
                    "columns": dataset.get("columns"),
                    "registered_at": dataset.get("registered_at"),
                    "refreshable": dataset.get("refreshable"),
                }
                for dataset in datasets
            ],
        },
        indent=2,
    )


async def schema_handler(arguments: dict[str, Any]) -> str:
    dataset_id = arguments["dataset_id"]
    result = await api("GET", f"/v1/data/{dataset_id}")
    dataset = result.get("dataset", {})
    schema = result.get("schema", {})
    return json.dumps(
        {
            "dataset": dataset,
            "schema": {
                "row_count": schema.get("row_count"),
                "columns": schema.get("columns", []),
                "roles_summary": schema.get("roles_summary", {}),
                "formulas": schema.get("formulas", []),
                "query_hints": schema.get("query_hints", []),
            },
        },
        indent=2,
    )


async def summary_handler(arguments: dict[str, Any]) -> str:
    dataset_id = arguments["dataset_id"]
    result = await api("GET", f"/v1/data/{dataset_id}/summary")
    return json.dumps(
        {
            "dataset_id": result.get("dataset_id"),
            "name": result.get("name"),
            "status": result.get("status"),
            "source_names": result.get("source_names", []),
            "row_count": result.get("row_count"),
            "column_count": result.get("column_count"),
            "registered_at": result.get("registered_at"),
            "query_hints": result.get("query_hints", []),
        },
        indent=2,
    )


async def refresh_handler(arguments: dict[str, Any]) -> str:
    dataset_id = arguments["dataset_id"]
    result = await api("POST", f"/v1/data/{dataset_id}/refresh", json={})
    return json.dumps(result, indent=2)


async def disconnect_handler(arguments: dict[str, Any]) -> str:
    dataset_id = arguments["dataset_id"]
    result = await api("DELETE", f"/v1/data/{dataset_id}")
    return json.dumps(result, indent=2)
