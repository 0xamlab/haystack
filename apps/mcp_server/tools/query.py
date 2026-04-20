"""
MCP tool: query_data

Lets an LLM execute structured queries against the user's data sources.
The LLM converts natural-language questions to structured intent;
Algenta handles schema understanding, math relationships, and execution.

Separation of concerns:
  LLM  → language, intent, ambiguity, UX
  Tool → data truth, fast execution, confidence guarantees
"""
from __future__ import annotations

import json
from typing import Any

from apps.mcp_server.client import api

SPEC: dict[str, Any] = {
    "name": "query_data",
    "description": (
        "Execute a structured query against connected data sources. "
        "Convert the user's question to a structured intent and call this tool — "
        "do NOT try to write SQL or parse column names yourself. "
        "The engine resolves column meaning from mathematical relationships and "
        "statistical structure only. It works on any dataset without configuration.\n\n"
        "Structural roles (use in metric.role):\n"
        "- derived_measure: the main financial/operational aggregate (revenue, spend, value)\n"
        "- base_measure: counts, quantities, discrete amounts\n"
        "- unit_measure: per-unit prices, rates\n"
        "- ratio: percentages, margins, fill rates (0-1 range)\n"
        "- metric: let the engine pick the best numeric column\n\n"
        "If clarification_required is true, or if confidence < 0.85, check the candidates "
        "list and ask the user to clarify. Never fabricate column names or SQL."
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
                    "Data sources to query. "
                    "Usually omitted when dataset_id is provided."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name":      {"type": "string", "description": "Human-readable name"},
                        "dataset_id": {
                            "type": "string",
                            "description": "Dataset ID alias for a registered source.",
                        },
                        "source_id": {
                            "type": "string",
                            "description": (
                                "Registered source_id "
                                "(fastest — avoids re-uploading data)"
                            ),
                        },
                        "table": {
                            "type": "string",
                            "description": (
                                "Registered source name "
                                "(alternative to source_id)"
                            ),
                        },
                        "csv": {
                            "type": "string",
                            "description": (
                                "Raw CSV text "
                                "(use source_id/table for registered sources)"
                            ),
                        },
                        "json_str": {
                            "type": "string",
                            "description": "Raw JSON array/object text",
                        },
                        "records":   {
                            "type": "array",
                            "description": (
                                "Inline JSON records "
                                "(use source_id/table for registered sources)"
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
                            "derived_measure", "base_measure", "unit_measure",
                            "ratio", "component", "identifier", "metric",
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
                            "last_quarter", "this_quarter",
                            "last_month", "this_month",
                            "last_year", "this_year",
                        ],
                        "description": "Relative time window.",
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


async def handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/query", json=arguments)

    # Format for LLM consumption
    output: dict[str, Any] = {
        "decision_path":     result.get("decision_path"),
        "plan_hash":         result.get("plan_hash"),
        "schema_revision":   result.get("schema_revision"),
        "planner_mode":      result.get("planner_mode"),
        "source_set":        result.get("source_set", []),
        "join_path":         result.get("join_path", []),
        "validated":         result.get("validated"),
        "clarification_required": result.get("clarification_required", False),
        "rejection_reason":  result.get("rejection_reason"),
        "request_id":        result.get("request_id"),
        "result_type":       result.get("result_type"),
        "confidence":        result.get("confidence"),
        "resolved_column":   result.get("resolved_column"),
        "resolved_role":     result.get("resolved_role"),
        "resolved_source":   result.get("resolved_source"),
        "row_count":         result.get("row_count"),
        "result":            result.get("result"),
        "plan":              result.get("plan", []),
    }

    # Include candidates when the engine requests clarification.
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

    return json.dumps(output, indent=2)
