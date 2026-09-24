"""MCP tools for the simplified product API surface."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

PRODUCT_DECISION_SPEC: dict[str, Any] = {
    "name": "product_decision",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Recommend an action for a business decision from plain inputs, and return the "
        "risk summary behind it. Each input becomes a simulation variable: fixed at "
        "value, or triangular when low and high bounds are given; inputs named "
        "cost/costs/expense/expenses/spending are subtracted in the objective. The "
        "engine evaluates scenarios (default 10000) and maps the loss probability to "
        "an action: over 50% -> reject, over the risk_tolerance threshold (low 5%, "
        "medium 15%, high 30%) -> pause, otherwise proceed. Use simulate for the raw "
        "distribution and plan_decision for the structured plan. Synchronous "
        "deterministic compute; nothing is persisted. Returns decision_id, action, "
        "confidence, reasoning and why bullets, expected_outcome, downside_risk "
        "(p5), upside_potential (p95), and probability_of_loss. Which to use: a "
        "proceed/pause/reject answer from plain business inputs; use simulate for "
        "full distribution control and the envelope."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["inputs"],
        "additionalProperties": False,
        "properties": {
            "inputs": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Business inputs as {name, value, low?, high?, unit?} objects; low+high "
                    "turn a value into a triangular uncertainty range."
                ),
            },
            "objective": {
                "type": "string",
                "description": (
                    "Goal label such as maximize_value, minimize_risk, maximize_profit, or "
                    "minimize_cost; defaults to maximize_value."
                ),
            },
            "risk_tolerance": {
                "type": "string",
                "description": (
                    "Loss-probability ceiling for a proceed recommendation: low, medium "
                    "(default), or high."
                ),
            },
            "scenarios": {
                "type": "integer",
                "description": "Scenarios to evaluate, 1000-1000000; defaults to 10000.",
            },
            "engine": {
                "type": "string",
                "description": (
                    "Simulation engine; auto (default) selects one from the data shape. "
                    "Options: monte_carlo, lhs, qmc_sobol, bootstrap, mcmc, "
                    "importance_sampling, time_series, sensitivity."
                ),
            },
            "label": {
                "type": "string",
                "description": "Optional caller label stored with the decision.",
            },
        },
    },
}

PRODUCT_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "product_agent_run",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Execute a natural-language task synchronously with the simple product agent and "
        "return a compact task result. The agent picks one tool from the task wording "
        "(optimize for best/maximum-style tasks, simulate for risk/forecast-style, search "
        "for find/lookup-style, otherwise calculate), runs it, and formats the answer as "
        "text, json, or markdown. Use this for one-shot task execution; use "
        "create_agent_run when you need a paused or approval-gated lifecycle, and "
        "get_agent_run to re-fetch the persisted record. The run, its step log, events, "
        "and a replayable checkpoint are persisted under the caller's organization. "
        "Returns run_id, status (completed on success), result, the step list, "
        "tools_used, and latency_ms."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["task"],
        "additionalProperties": False,
        "properties": {
            "task": {
                "type": "string",
                "description": "What the agent should do, in plain words (min 5 characters).",
            },
            "context": {
                "type": "object",
                "description": "Optional structured context or data for the task.",
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Restrict the tools the agent may pick from; defaults to search, "
                    "simulate, optimize, calculate, summarize."
                ),
            },
            "max_steps": {
                "type": "integer",
                "description": "Maximum execution steps, 1-50; defaults to 10.",
            },
            "output_format": {
                "type": "string",
                "description": "Result format: text (default), json, or markdown.",
            },
        },
    },
}

PRODUCT_OPTIMIZE_SPEC: dict[str, Any] = {
    "name": "product_optimize",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Estimate the best value for each decision variable given a plain-English "
        "objective, and return the per-variable optima. Every variable is sampled "
        "uniformly over its [min, max] range; an objective containing 'maximize' favors "
        "each variable's max, anything else favors the min, and the returned optimum "
        "blends that endpoint with the range midpoint. Use product_decision when you want "
        "a proceed/pause/reject recommendation instead of raw optima. Synchronous "
        "deterministic compute; nothing is persisted. Returns optimal_values, "
        "objective_value, improvement_vs_midpoint (percent), constraints_satisfied, "
        "and iterations_run."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["objective", "variables"],
        "additionalProperties": False,
        "properties": {
            "objective": {
                "type": "string",
                "description": (
                    "What to optimize, e.g. 'maximize profit' or 'minimize cost'; the "
                    "wording sets the search direction."
                ),
            },
            "variables": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Variables as {name, min, max, unit?} objects with their allowed ranges."
                ),
            },
            "constraints": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Business constraints the answer must respect.",
            },
            "iterations": {
                "type": "integer",
                "description": "Search iterations, 100-100000; defaults to 1000.",
            },
            "engine": {
                "type": "string",
                "description": (
                    "Simulation engine; auto (default) selects one, lhs is recommended for "
                    "optimization. Options: lhs, monte_carlo, qmc_sobol."
                ),
            },
        },
    },
}

PRODUCT_RETRIEVE_SPEC: dict[str, Any] = {
    "name": "product_retrieve",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Rank caller-supplied documents against a search query and return the top matches "
        "with snippets. Scoring is deterministic lexical word-overlap between query and "
        "document plus a bonus when the query prefix appears in the document; results sort "
        "by relevance_score with rank starting at 1. Provide documents or a collection_id "
        "- a call with neither fails with missing_source. Use query_data for analytics "
        "over connected datasets instead. Read-only; nothing is stored. Returns results "
        "(rank, document_id, content excerpt, relevance_score, snippet) and "
        "total_searched."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["query"],
        "additionalProperties": False,
        "properties": {
            "query": {
                "type": "string",
                "description": "What you are looking for (min 3 characters).",
            },
            "documents": {
                "type": "array",
                "items": {"type": "object"},
                "description": (
                    "Inline documents as {id?, content, metadata?} objects; the set that "
                    "actually gets ranked."
                ),
            },
            "collection_id": {
                "type": "string",
                "description": "ID of a connected data source to search.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return, 1-50; defaults to 5.",
            },
            "rerank": {
                "type": "boolean",
                "description": (
                    "Accepted for compatibility; ranking is always the deterministic "
                    "lexical score."
                ),
            },
        },
    },
}

PRODUCT_FORECAST_SPEC: dict[str, Any] = {
    "name": "product_forecast",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Forecast a business metric horizon periods ahead from its historical series and "
        "return per-period point forecasts with confidence intervals. The trend comes from "
        "the last up-to-6 history values, volatility from the mean absolute period change, "
        "and a 5000-scenario simulation quantifies uncertainty; seasonality=true applies "
        "an alternating +/-5% seasonal factor. Use query_data to build the history from a "
        "connected dataset first. Synchronous deterministic compute; nothing is "
        "persisted. Returns baseline (most recent value), forecast_mean (final period), "
        "total_change_pct, and one {period, forecast, lower_bound, upper_bound, trend} "
        "item per period with trend up, down, or stable."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["metric", "history"],
        "additionalProperties": False,
        "properties": {
            "metric": {
                "type": "string",
                "description": "Name of what you are forecasting, e.g. monthly_revenue.",
            },
            "history": {
                "type": "array",
                "items": {"type": "number"},
                "description": (
                    "Historical values in chronological order, most recent last; 3-1000 "
                    "points."
                ),
            },
            "horizon": {
                "type": "integer",
                "description": "How many periods ahead to forecast, 1-120; defaults to 12.",
            },
            "seasonality": {
                "type": "boolean",
                "description": "Account for seasonal patterns; defaults to true.",
            },
            "confidence_level": {
                "type": "number",
                "description": (
                    "Confidence interval width, 0.5-0.99; defaults to 0.90. The z-value "
                    "comes from the nearest of 0.90, 0.95, 0.99."
                ),
            },
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
