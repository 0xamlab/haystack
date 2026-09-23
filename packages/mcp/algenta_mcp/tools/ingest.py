"""
MCP tool: ingest_data

Auto-map any tabular data to a ready-to-run simulation payload.
Detects distributions, polarity, units, and objective function automatically.
Set run_simulation=true to execute immediately and get results.
"""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

SPEC: dict[str, Any] = {
    "name": "ingest_data",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Auto-map tabular data to a simulation payload. "
        "Detects variable distributions, polarity (revenue=positive, cost=negative), "
        "units, and builds the objective function automatically. "
        "Set run_simulation=true to execute the simulation immediately and get results. "
        "Multiple tables: auto-detects join keys and merges before analysis."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["tables"],
        "properties": {
            "tables": {
                "type": "array",
                "description": "One or more data tables. First table is primary.",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "records": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "JSON records.",
                        },
                        "csv": {"type": "string", "description": "Raw CSV text."},
                    },
                },
            },
            "run_simulation": {
                "type": "boolean",
                "default": False,
                "description": "Execute the simulation immediately and return results.",
            },
            "runs": {
                "type": "integer",
                "default": 10000,
                "description": "Scenarios to evaluate (1,000–1,000,000).",
            },
            "domain": {
                "type": "string",
                "description": (
                    "Optional domain hint (finance, supply_chain, hr) for better field mapping."
                ),
            },
        },
    },
}


async def handler(arguments: dict[str, Any]) -> str:
    body = {
        "tables": arguments["tables"],
        "auto_run": arguments.get("run_simulation", False),
        "runs": arguments.get("runs", 10000),
    }
    if "domain" in arguments:
        body["domain"] = arguments["domain"]

    result = await api("POST", "/v1/ingest", json=body)

    output: dict[str, Any] = {
        "fields_detected": result.get("fields_detected"),
        "records_analyzed": result.get("records_analyzed"),
        "join_applied": result.get("join_applied"),
        "engine": result.get("engine"),
        "objective_function": result.get("objective_function"),
        "variables": result.get("variables", []),
        "simulation_payload": result.get("simulation_payload"),
        "latency_ms": result.get("latency_ms"),
    }

    if result.get("simulation_result"):
        r = result["simulation_result"]
        output["simulation_result"] = {
            "recommended_action": r.get("recommended_action"),
            "confidence": r.get("confidence"),
            "expected_value": r.get("expected_value"),
            "probability_of_loss": r.get("probability_of_loss"),
            "scenarios_run": r.get("scenarios_run"),
        }

    return json.dumps(output, indent=2)
