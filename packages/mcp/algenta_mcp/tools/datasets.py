"""
MCP tool: onboard_dataset + list_datasets

Lets an LLM onboard any data source and check training status.
The LLM passes column names or inline records; Algenta profiles the schema,
auto-suggests aliases, and fires background semantic training.
"""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

ONBOARD_SPEC: dict[str, Any] = {
    "name": "onboard_dataset",
    "description": (
        "Register a dataset for semantic querying. "
        "Pass column names, inline records, or raw CSV. "
        "The engine profiles roles automatically and starts background training. "
        "Queries work immediately via a fallback model — accuracy improves "
        "once schema-specific training completes (poll status with list_datasets)."
    ),
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "name": {
                "type": "string",
                "description": "Human-readable name for this dataset.",
                "default": "dataset",
            },
            "columns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Column names only — fastest path, no data required.",
            },
            "records": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Sample rows as JSON records (list of dicts). Up to 200 rows.",
            },
            "csv": {
                "type": "string",
                "description": "Raw CSV text with header row.",
            },
            "domain_aliases": {
                "type": "object",
                "description": (
                    "Optional map of abbreviation → expansions. "
                    'Example: {"ppa": ["per", "person", "average"]}. '
                    "Auto-suggested if omitted."
                ),
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "async_train": {
                "type": "boolean",
                "description": "Start background semantic training immediately (default: true).",
                "default": True,
            },
        },
    },
}

LIST_SPEC: dict[str, Any] = {
    "name": "list_datasets",
    "description": (
        "List registered datasets and their current model tier. "
        "Use search plus compact mode for low-token discovery, then poll "
        "status or use the primary data tools once you choose a dataset."
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


async def onboard_handler(arguments: dict[str, Any]) -> str:
    # Determine which input format to send
    body: dict[str, Any] = {
        "name": arguments.get("name", "dataset"),
        "async_train": arguments.get("async_train", True),
    }
    if "domain_aliases" in arguments:
        body["domain_aliases"] = arguments["domain_aliases"]

    if "records" in arguments:
        body["records"] = arguments["records"]
    elif "csv" in arguments:
        body["csv"] = arguments["csv"]
    elif "columns" in arguments:
        body["columns"] = arguments["columns"]
    else:
        return json.dumps({"error": "Provide one of: columns, records, or csv"})

    result = await api("POST", "/v1/datasets/onboard", json=body)

    return json.dumps(
        {
            "dataset_id": result.get("dataset_id"),
            "schema_hash": result.get("schema_hash"),
            "status": result.get("status"),
            "model_tier": result.get("model_tier"),
            "column_count": result.get("column_count"),
            "suggested_aliases": result.get("suggested_aliases", {}),
            "note": (
                "Queries work immediately. "
                "Call list_datasets to check when schema training completes."
                if result.get("status") == "training"
                else "Dataset ready."
            ),
        },
        indent=2,
    )


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
    result = await api("GET", "/v1/datasets", params=params)
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
                    "dataset_id": d.get("dataset_id"),
                    "dataset_name": d.get("dataset_name") or d.get("name"),
                    "name": d.get("name") or d.get("dataset_name"),
                    "status": d.get("status"),
                    "model_tier": d.get("model_tier"),
                    "source_names": d.get("source_names", []),
                    "column_count": d.get("column_count"),
                    "registered_at": d.get("registered_at"),
                }
                for d in datasets
            ],
        },
        indent=2,
    )


STATUS_SPEC: dict[str, Any] = {
    "name": "get_dataset_status",
    "description": (
        "Get live training status and model tier for a specific dataset. "
        "model_tier: 'none' = deterministic only, 'base' = generic model, "
        "'schema' = fully trained schema-specific model (best quality)."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["dataset_id"],
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": "Dataset ID from onboard_dataset or list_datasets.",
            },
        },
    },
}

RETRAIN_SPEC: dict[str, Any] = {
    "name": "retrain_dataset",
    "description": (
        "Re-trigger semantic training for a dataset. "
        "Use after schema changes, alias updates, or to force a fresh model build."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["dataset_id"],
        "properties": {
            "dataset_id": {"type": "string"},
            "epochs": {"type": "integer", "default": 80},
        },
    },
}


async def status_handler(arguments: dict[str, Any]) -> str:
    dataset_id = arguments["dataset_id"]
    result = await api("GET", f"/v1/datasets/{dataset_id}/status")
    return json.dumps(
        {
            "dataset_id": result.get("dataset_id"),
            "name": result.get("name"),
            "status": result.get("status"),
            "model_tier": result.get("model_tier"),
            "column_count": result.get("column_count"),
            "updated_at": result.get("updated_at"),
        },
        indent=2,
    )


async def retrain_handler(arguments: dict[str, Any]) -> str:
    dataset_id = arguments["dataset_id"]
    body: dict[str, Any] = {}
    if "epochs" in arguments:
        body["epochs"] = arguments["epochs"]
    result = await api("POST", f"/v1/datasets/{dataset_id}/retrain", json=body)
    return json.dumps(
        {
            "dataset_id": result.get("dataset_id"),
            "status": result.get("status"),
            "message": result.get("message"),
        },
        indent=2,
    )
