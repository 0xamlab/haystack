"""MCP tools for the simplified product API surface."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

PRODUCT_DECISION_SPEC: dict[str, Any] = {
    "name": "product_decision",
    "description": "Run the simple product decision helper and return the chosen action plus risk summary.",
    "inputSchema": {
        "type": "object",
        "required": ["inputs"],
        "additionalProperties": False,
        "properties": {
            "inputs": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Business inputs with current value and optional low/high bounds.",
            },
            "objective": {"type": "string"},
            "risk_tolerance": {"type": "string"},
            "scenarios": {"type": "integer"},
            "engine": {"type": "string"},
            "label": {"type": "string"},
        },
    },
}

PRODUCT_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "product_agent_run",
    "description": "Run the simple product task-execution helper and return a compact task result.",
    "inputSchema": {
        "type": "object",
        "required": ["task"],
        "additionalProperties": False,
        "properties": {
            "task": {"type": "string"},
            "context": {"type": "object"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "max_steps": {"type": "integer"},
            "output_format": {"type": "string"},
        },
    },
}

PRODUCT_OPTIMIZE_SPEC: dict[str, Any] = {
    "name": "product_optimize",
    "description": "Run the simple product optimization helper and return the best variable values.",
    "inputSchema": {
        "type": "object",
        "required": ["objective", "variables"],
        "additionalProperties": False,
        "properties": {
            "objective": {"type": "string"},
            "variables": {"type": "array", "items": {"type": "object"}},
            "constraints": {"type": "array", "items": {"type": "object"}},
            "iterations": {"type": "integer"},
            "engine": {"type": "string"},
        },
    },
}

PRODUCT_RETRIEVE_SPEC: dict[str, Any] = {
    "name": "product_retrieve",
    "description": "Run the simple product retrieval helper over caller-supplied documents or a collection id.",
    "inputSchema": {
        "type": "object",
        "required": ["query"],
        "additionalProperties": False,
        "properties": {
            "query": {"type": "string"},
            "documents": {"type": "array", "items": {"type": "object"}},
            "collection_id": {"type": "string"},
            "top_k": {"type": "integer"},
            "rerank": {"type": "boolean"},
        },
    },
}

PRODUCT_FORECAST_SPEC: dict[str, Any] = {
    "name": "product_forecast",
    "description": "Run the simple product forecast helper over a historical metric series.",
    "inputSchema": {
        "type": "object",
        "required": ["metric", "history"],
        "additionalProperties": False,
        "properties": {
            "metric": {"type": "string"},
            "history": {"type": "array", "items": {"type": "number"}},
            "horizon": {"type": "integer"},
            "seasonality": {"type": "boolean"},
            "confidence_level": {"type": "number"},
        },
    },
}


async def product_decision_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/decision", json=arguments)
    return json.dumps(result, indent=2)


async def product_agent_run_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/agent/run", json=arguments)
    return json.dumps(result, indent=2)


async def product_optimize_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/optimize", json=arguments)
    return json.dumps(result, indent=2)


async def product_retrieve_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/retrieve", json=arguments)
    return json.dumps(result, indent=2)


async def product_forecast_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/forecast", json=arguments)
    return json.dumps(result, indent=2)
