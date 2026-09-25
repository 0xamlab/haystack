"""
MCP tools: register_source, list_sources, get_source_schema

Full schema discovery — profile any source, detect column relationships
(A×B≈C formulas), and auto-detect join keys to all other registered sources.

After registration a source is available to query_data by name.
"""

from __future__ import annotations

import json
import time
from typing import Any

from algenta_mcp.client import api

# ── Process-level schema cache ────────────────────────────────────────────────
# Eliminates repeated API roundtrips for the same source_id within a session.
# TTL=60s: fresh enough for interactive use, short enough that schema changes propagate.
_SCHEMA_CACHE: dict[str, tuple[str, float]] = {}  # source_id → (json_str, expires_at)
_SCHEMA_CACHE_TTL = 60.0  # seconds


def _schema_cache_get(source_id: str) -> str | None:
    entry = _SCHEMA_CACHE.get(source_id)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    _SCHEMA_CACHE.pop(source_id, None)
    return None


def _schema_cache_set(source_id: str, result: str) -> None:
    _SCHEMA_CACHE[source_id] = (result, time.monotonic() + _SCHEMA_CACHE_TTL)


def _schema_cache_invalidate(source_id: str) -> None:
    _SCHEMA_CACHE.pop(source_id, None)


REGISTER_SPEC: dict[str, Any] = {
    "name": "register_source",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Advanced tool. Register a data source and get full schema profiling + join "
        "detection. Profiles every column (type, cardinality, fill rate, distribution). "
        "Detects formula relationships (A×B≈C) within the source. Detects join keys to "
        "every already-registered source automatically. After registration the source is "
        "queryable by name via query_data. Safe to call multiple times — re-registration is "
        "a no-op if data is unchanged. Registration persists the source profile under the "
        "active API key's organization. Returns source_id and the profiled schema with "
        "columns, roles, formulas, and detected join keys. Which to use: the advanced "
        "path — full column profiling, formula detection, and join-key detection "
        "across registered sources (browse the results with list_data); use "
        "onboard_dataset for semantic training, or connect_data for refreshable "
        "live connections."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["source"],
        "properties": {
            "source": {
                "type": "object",
                "description": (
                    "Data source definition. Provide exactly one of: records, csv, json_str, url."
                ),
                "required": ["name"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Human-readable label for this source.",
                    },
                    "records": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Inline JSON records (fastest).",
                    },
                    "csv": {"type": "string", "description": "Raw CSV text with header row."},
                    "json_str": {
                        "type": "string",
                        "description": "Raw JSON array or object text.",
                    },
                    "url": {
                        "type": "string",
                        "description": "HTTP(S) URL; format auto-detected.",
                    },
                    "connection": {
                        "type": "object",
                        "description": (
                            "Connector config for databases, S3, REST APIs. "
                            'Example: {"type": "sql", '
                            '"connection_string": "postgresql://...", '
                            '"query": "SELECT ..."}'
                        ),
                    },
                },
            },
            "description": {
                "type": "string",
                "description": "Optional human description of this source.",
            },
        },
    },
}

LIST_SOURCES_SPEC: dict[str, Any] = {
    "name": "list_sources",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Advanced tool. List all registered data sources for this org with their schema "
        "summaries. Use this to discover available tables before calling query_data or "
        "register_source. Use register_source to add a source, get_source_schema for "
        "one source's full profile, and list_data to browse the connect_data store "
        "instead. Read-only and non-destructive; not separately rate-limited. "
        "Returns the sources array with each source's id, name, and schema summary "
        "(columns, roles, detected join keys), plus count, total, page, limit, and pages."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "description": "Page number (default 1)."},
            "limit": {
                "type": "integer",
                "description": (
                    "Results per page (default: all visible sources, max 200 when set)."
                ),
            },
        },
    },
}

GET_SOURCE_SPEC: dict[str, Any] = {
    "name": "get_source_schema",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Advanced tool. Get the full schema for a specific registered source: column types, "
        "cardinality, fill rates, formula relationships, and detected join keys to other "
        "sources. This reads the source-registry profile built by register_source; "
        "use get_data_schema for the dataset-level schema view of the connect_data "
        "flow instead. Read-only and non-destructive; not separately rate-limited. Use "
        "list_sources to find source ids."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["source_id"],
        "properties": {
            "source_id": {
                "type": "string",
                "description": "Source ID from list_sources.",
            },
        },
    },
}


async def register_handler(arguments: dict[str, Any]) -> str:
    body = {
        "source": arguments["source"],
    }
    if "description" in arguments:
        body["description"] = arguments["description"]

    result = await api("POST", "/v1/sources/register", json=body)
    schema = result.get("schema", {})

    # Invalidate any cached schema for this source (data may have changed)
    if sid := result.get("source_id"):
        _schema_cache_invalidate(sid)

    # columns may be a list[{name, role, ...}] or a dict keyed by name
    _cols = schema.get("columns", [])
    if isinstance(_cols, list):
        col_names = [c["name"] if isinstance(c, dict) else c for c in _cols]
    else:
        col_names = list(_cols.keys())

    return json.dumps(
        {
            "source_id": result.get("source_id"),
            "name": result.get("name"),
            "status": result.get("status"),
            "row_count": result.get("row_count"),
            "columns": col_names,
            "formula_relations": schema.get("formula_relations", []),
            "connections_found": result.get("connections_found", []),
            "latency_ms": result.get("latency_ms"),
            "note": (
                "Source registered and available for query_data. "
                f"{len(result.get('connections_found', []))} join key(s) detected to other sources."
            ),
        },
        indent=2,
    )


async def list_sources_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    if "page" in arguments:
        params["page"] = arguments["page"]
    if "limit" in arguments:
        params["limit"] = arguments["limit"]
    result = await api("GET", "/v1/sources", params=params)
    sources = result.get("sources", [])
    return json.dumps(
        {
            "count": result.get("count", len(sources)),
            "total": result.get("total", len(sources)),
            "page": result.get("page", 1),
            "limit": result.get("limit", len(sources)),
            "pages": result.get("pages", 1),
            "sources": [
                {
                    "source_id": s.get("id"),
                    "name": s.get("name"),
                    "row_count": s.get("row_count"),
                    "columns": s.get("columns", []),
                }
                for s in sources
            ],
        },
        indent=2,
    )


async def get_source_handler(arguments: dict[str, Any]) -> str:
    source_id = arguments["source_id"]

    # Return cached result if still fresh (eliminates API roundtrip + Claude round)
    if cached := _schema_cache_get(source_id):
        return cached

    result = await api("GET", f"/v1/sources/{source_id}")
    schema = result.get("schema", {})
    response = json.dumps(
        {
            "source_id": result.get("source_id"),
            "columns": schema.get("columns", {}),
            "formula_relations": schema.get("formula_relations", []),
            "row_count": schema.get("row_count"),
        },
        indent=2,
    )

    _schema_cache_set(source_id, response)
    return response
