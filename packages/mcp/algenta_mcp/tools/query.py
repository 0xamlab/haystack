"""
MCP tools: query_data, query_batch, query_sql_report

Lets an LLM execute governed exact queries and constrained read-only SQL reports
against the user's authorized datasets. The LLM converts natural-language
questions to structured intent; Algenta handles schema understanding, math
relationships, and execution.

Separation of concerns:
  LLM  → language, intent, ambiguity, UX
  Tool → data truth, fast execution, confidence guarantees
"""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

SPEC: dict[str, Any] = {
    "name": "query_data",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Execute a structured query against connected data sources. "
        "Convert the user's question to a structured intent and call this tool — "
        "do NOT try to write SQL or parse column names yourself. "
        "The engine resolves column meaning from mathematical relationships and "
        "statistical structure only. It works on any dataset without configuration. "
        "The governed filter shape is a record-predicate contract over normalized rows, "
        "not a SQL predicate language, so it also applies to Redis and other non-SQL "
        "sources.\n\n"
        "Structural roles (use in metric.role):\n"
        "- derived_measure: the main financial/operational aggregate (revenue, spend, value)\n"
        "- base_measure: counts, quantities, discrete amounts\n"
        "- unit_measure: per-unit prices, rates\n"
        "- ratio: percentages, margins, fill rates (0-1 range)\n"
        "- metric: let the engine pick the best numeric column\n\n"
        "If clarification_required is true, or if confidence < 0.85, check the candidates "
        "list and ask the user to clarify. Never fabricate column names or SQL. "
        "Read-only against the engine; executes under the active API key with no "
        "separate per-route rate limit. "
        "Returns the query envelope: result, result_type, row_count, confidence, "
        "resolved_column, decision_path, and plan, with candidates and "
        "clarification_required set when the engine cannot resolve deterministically."
    ),
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": "Preferred path. dataset_id returned by connect_data or list_data.",
            },
            "sources": {
                "type": "array",
                "description": (
                    "Data sources to query. Usually omitted when dataset_id is provided."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Human-readable name"},
                        "dataset_id": {
                            "type": "string",
                            "description": "Dataset ID alias for a registered source.",
                        },
                        "source_id": {
                            "type": "string",
                            "description": (
                                "Registered source_id (fastest — avoids re-uploading data)"
                            ),
                        },
                        "table": {
                            "type": "string",
                            "description": ("Registered source name (alternative to source_id)"),
                        },
                        "csv": {
                            "type": "string",
                            "description": (
                                "Raw CSV text (use source_id/table for registered sources)"
                            ),
                        },
                        "json_str": {
                            "type": "string",
                            "description": "Raw JSON array/object text",
                        },
                        "records": {
                            "type": "array",
                            "description": (
                                "Inline JSON records (use source_id/table for registered sources)"
                            ),
                            "items": {"type": "object"},
                        },
                        "url": {
                            "type": "string",
                            "description": "HTTP URL for CSV/JSON source",
                        },
                    },
                },
            },
            "metric": {
                "type": "object",
                "description": "What to measure.",
                "required": ["role"],
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": [
                            "derived_measure",
                            "base_measure",
                            "unit_measure",
                            "ratio",
                            "component",
                            "identifier",
                            "metric",
                        ],
                        "description": "Structural role of the column to aggregate.",
                    },
                    "hint": {
                        "type": "string",
                        "description": (
                            "Optional weak signal from user's question "
                            "(e.g. 'revenue', 'quantity'). Used only as tiebreaker."
                        ),
                    },
                },
            },
            "aggregation": {
                "type": "string",
                "enum": ["sum", "avg", "count", "max", "min"],
                "default": "sum",
                "description": "How to aggregate the metric column.",
            },
            "group_by": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Dimension words from the user's question (e.g. ['customer', 'region']). "
                    "The engine finds the best matching column."
                ),
            },
            "filter": {
                "type": "object",
                "properties": {
                    "time_filter": {
                        "type": "string",
                        "enum": [
                            "last_quarter",
                            "this_quarter",
                            "last_month",
                            "this_month",
                            "last_year",
                            "this_year",
                        ],
                        "description": "Relative time window.",
                    },
                    "conditions": {
                        "type": "array",
                        "description": (
                            "Deterministic non-time predicates applied on the metric source. "
                            "Use exact column when schema is known, or dimension_hint for "
                            "generic status/type/category filters. These are record predicates, "
                            "not SQL clauses."
                        ),
                        "items": {
                            "type": "object",
                            "required": ["op"],
                            "properties": {
                                "column": {
                                    "type": "string",
                                    "description": "Exact source column name for this filter.",
                                },
                                "dimension_hint": {
                                    "type": "string",
                                    "description": (
                                        "Semantic label when the exact column is not known yet."
                                    ),
                                },
                                "op": {
                                    "type": "string",
                                    "enum": [
                                        "eq",
                                        "in",
                                        "gt",
                                        "gte",
                                        "lt",
                                        "lte",
                                        "is_null",
                                        "is_not_null",
                                    ],
                                },
                                "value": {
                                    "description": "Scalar comparison value for eq/gt/gte/lt/lte.",
                                },
                                "values": {
                                    "type": "array",
                                    "description": "List comparison values for in.",
                                    "items": {},
                                },
                            },
                        },
                    },
                },
            },
            "limit": {
                "type": "integer",
                "description": "Top-N limit. Use for 'top 5 customers' type questions.",
            },
            "order": {
                "type": "string",
                "enum": ["desc", "asc"],
                "default": "desc",
            },
        },
    },
}

QUERY_BATCH_SPEC: dict[str, Any] = {
    "name": "query_batch",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Execute several governed exact queries in one API call. Use this for multi-metric "
        "prompts after choosing a dataset with list_data and get_data_summary. Each item "
        "reuses the same structured query contract as query_data; defaults may provide "
        "shared dataset_id, filter, limit, and order. Read-only against the engine; "
        "executes under the active API key with no separate per-route rate limit. Returns "
        "request_id and a results array with each item's key, data envelope, metadata, or "
        "error."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["queries"],
        "properties": {
            "defaults": {
                "type": "object",
                "description": (
                    "Optional shared exact-query fields applied to each item before execution."
                ),
                "properties": {
                    "dataset_id": {"type": "string"},
                    "filter": SPEC["inputSchema"]["properties"]["filter"],
                    "limit": {"type": "integer"},
                    "order": {"type": "string", "enum": ["desc", "asc"]},
                },
            },
            "queries": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["key", "request"],
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Stable identifier for this batch item.",
                        },
                        "request": {
                            "type": "object",
                            "description": (
                                "Exact query_data payload for this item after defaults merge."
                            ),
                        },
                    },
                },
            },
        },
    },
}

QUERY_SQL_REPORT_SPEC: dict[str, Any] = {
    "name": "query_sql_report",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Execute a constrained read-only SQL rowset query over authorized datasets. Use "
        "this only for wide reports that do not fit the governed exact-query surface. SQL "
        "must be a single SELECT/WITH statement over the provided dataset aliases. Returns "
        "columns, rows, row_count, truncated, request_id, and latency_ms."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["sources", "sql"],
        "properties": {
            "sources": {
                "type": "array",
                "minItems": 1,
                "description": "Authorized datasets made available to the SQL report.",
                "items": {
                    "type": "object",
                    "required": ["dataset_id"],
                    "properties": {
                        "dataset_id": {"type": "string"},
                        "alias": {
                            "type": "string",
                            "description": "Optional SQL table alias for this dataset.",
                        },
                    },
                },
            },
            "sql": {
                "type": "string",
                "description": "Single read-only SELECT or WITH statement.",
            },
            "max_rows": {
                "type": "integer",
                "description": "Optional row cap, up to the API maximum.",
            },
        },
    },
}


def _format_query_result(result: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {
        "decision_path": result.get("decision_path"),
        "plan_hash": result.get("plan_hash"),
        "schema_revision": result.get("schema_revision"),
        "planner_mode": result.get("planner_mode"),
        "source_set": result.get("source_set", []),
        "join_path": result.get("join_path", []),
        "validated": result.get("validated"),
        "clarification_required": result.get("clarification_required", False),
        "rejection_reason": result.get("rejection_reason"),
        "request_id": result.get("request_id"),
        "result_type": result.get("result_type"),
        "confidence": result.get("confidence"),
        "resolved_column": result.get("resolved_column"),
        "resolved_role": result.get("resolved_role"),
        "resolved_source": result.get("resolved_source"),
        "row_count": result.get("row_count"),
        "result": result.get("result"),
        "plan": result.get("plan", []),
    }

    if result.get("clarification_required") or result.get("confidence", 1.0) < 0.85:
        output["candidates"] = result.get("candidates", [])
        output["note"] = (
            "Clarification required before deterministic execution. "
            "Check 'candidates' and ask the user to clarify the intended field or join."
        )
    elif result.get("rejection_reason"):
        output["note"] = (
            "The engine rejected execution before running the query. "
            "Inspect rejection_reason and candidates instead of guessing."
        )

    return output


async def handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/query", json=arguments)
    return json.dumps(_format_query_result(result), indent=2)


async def query_batch_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/query/batch", json=arguments)
    output = {
        "request_id": result.get("request_id"),
        "results": [
            {
                "key": item.get("key"),
                "data": (
                    _format_query_result(item["data"])
                    if isinstance(item.get("data"), dict)
                    else None
                ),
                "metadata": item.get("metadata"),
                "error": item.get("error"),
            }
            for item in result.get("results", [])
        ],
    }
    return json.dumps(output, indent=2)


async def query_sql_report_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/query/sql-report", json=arguments)
    output = {
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
        "row_count": result.get("row_count"),
        "truncated": result.get("truncated", False),
        "request_id": result.get("request_id"),
        "latency_ms": result.get("latency_ms"),
    }
    if output["truncated"]:
        output["note"] = (
            "Result rows were truncated by the SQL report guardrails. "
            "Tighten the SQL or lower max_rows for a smaller rowset."
        )
    return json.dumps(output, indent=2)
