"""
MCP tools: register_trigger, list_triggers, fire_trigger, pause_trigger, delete_trigger

Real-time trigger layer — watch data sources for threshold crossings and
automatically fire simulations when conditions are met.

Usage pattern:
  1. register_trigger  → set condition + simulation template
  2. fire_trigger      → manually execute (or auto-fired by background worker)
  3. list_triggers     → inspect active triggers and last-fired state
  4. pause_trigger     → pause or resume one trigger
"""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

REGISTER_TRIGGER_SPEC: dict[str, Any] = {
    "name": "register_trigger",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Register a real-time trigger that watches a data source for a threshold condition. "
        "When the condition is met, the engine auto-runs the simulation template and optionally "
        "fires a webhook. Examples: 'alert me when monthly revenue drops below $80k', "
        "'simulate expansion if Downtown revenue exceeds $200k'."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["name", "condition", "simulation_template"],
        "properties": {
            "name": {"type": "string", "description": "Human-readable trigger name."},
            "condition": {
                "type": "object",
                "description": "Threshold condition to watch.",
                "required": ["source_id", "metric_hint", "threshold", "direction"],
                "properties": {
                    "source_id": {"type": "string", "description": "Data source to watch."},
                    "metric_hint": {
                        "type": "string",
                        "description": (
                            "Column or metric name to evaluate "
                            "(for example 'net_sales' or 'revenue')."
                        ),
                    },
                    "threshold": {"type": "number", "description": "Numeric threshold value."},
                    "direction": {
                        "type": "string",
                        "enum": ["above", "below", "change"],
                        "description": (
                            "'above' fires when metric > threshold; "
                            "'below' when < threshold; 'change' fires on any "
                            "significant change."
                        ),
                    },
                    "aggregation": {
                        "type": "string",
                        "enum": ["sum", "avg", "max", "min", "count"],
                        "description": (
                            "Aggregation to apply before comparing to threshold (default: sum)."
                        ),
                    },
                },
            },
            "simulation_template": {
                "type": "object",
                "description": "SimulateRequest-compatible payload to run when trigger fires.",
            },
            "webhook_url": {
                "type": "string",
                "description": "Optional HTTPS URL to POST results to when the trigger fires.",
            },
            "execution_webhook_url": {
                "type": "string",
                "description": (
                    "Optional HTTPS URL to POST the DecisionPlan execution payload to "
                    "when auto_execute is enabled."
                ),
            },
            "auto_execute": {
                "type": "boolean",
                "description": (
                    "When true, automatically dispatch the decision plan to "
                    "execution_webhook_url after the trigger fires."
                ),
            },
            "description": {
                "type": "string",
                "description": "Human-readable description of what this trigger monitors.",
            },
        },
    },
}

LIST_TRIGGERS_SPEC: dict[str, Any] = {
    "name": "list_triggers",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List all registered triggers with their current status, "
        "last-checked time, and last-fired simulation result summary. "
        "Read-only and non-destructive; not separately rate-limited."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["active", "paused", "all"],
                "description": "Filter by trigger status (default: all).",
            },
            "page": {"type": "integer", "description": "Page number (default 1)."},
            "limit": {
                "type": "integer",
                "description": (
                    "Results per page (default: all visible triggers, max 200 when set)."
                ),
            },
        },
    },
}

FIRE_TRIGGER_SPEC: dict[str, Any] = {
    "name": "fire_trigger",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Manually fire a trigger — evaluates its condition and runs the simulation template "
        "regardless of whether the threshold is currently met. "
        "Useful for testing triggers or forcing an immediate evaluation."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["trigger_id"],
        "properties": {
            "trigger_id": {
                "type": "string",
                "description": "Trigger ID from register_trigger or list_triggers.",
            },
            "force": {
                "type": "boolean",
                "description": (
                    "When true, run simulation even if the condition is not "
                    "currently met (default: false)."
                ),
            },
        },
    },
}

DELETE_TRIGGER_SPEC: dict[str, Any] = {
    "name": "delete_trigger",
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Delete one trigger by trigger_id (find ids with list_triggers). The trigger "
        "is removed immediately and will no longer fire automatically; its "
        "registration cannot be recovered from this tool. To stop a trigger "
        "temporarily instead, use pause_trigger. An unknown trigger_id fails with "
        "not_found. Returns trigger_id with deleted: true."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["trigger_id"],
        "properties": {
            "trigger_id": {
                "type": "string",
                "description": "Trigger ID to delete.",
            },
        },
    },
}

PAUSE_TRIGGER_SPEC: dict[str, Any] = {
    "name": "pause_trigger",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": "Pause or resume an existing trigger without deleting it.",
    "inputSchema": {
        "type": "object",
        "required": ["trigger_id"],
        "properties": {
            "trigger_id": {"type": "string", "description": "Trigger ID to update."},
            "paused": {
                "type": "boolean",
                "description": "Set true to pause, false to resume (default: true).",
            },
        },
    },
}


async def register_trigger_handler(arguments: dict[str, Any]) -> str:
    for field in ("name", "condition", "simulation_template"):
        if field not in arguments:
            return json.dumps({"error": f"{field} is required"})
    body: dict[str, Any] = {
        "name": arguments["name"],
        "condition": arguments["condition"],
        "simulation_template": arguments["simulation_template"],
    }
    for field in ("webhook_url", "execution_webhook_url", "description"):
        if field in arguments:
            body[field] = arguments[field]
    if "auto_execute" in arguments:
        body["auto_execute"] = arguments["auto_execute"]

    result = await api("POST", "/v1/triggers", json=body)
    return json.dumps(
        {
            "trigger_id": result.get("trigger_id"),
            "name": result.get("name"),
            "status": result.get("status"),
            "condition": result.get("condition"),
            "created_at": result.get("created_at"),
            "note": (
                "Trigger registered. It will auto-evaluate when source data updates. "
                "Use fire_trigger to test it immediately."
            ),
        },
        indent=2,
    )


async def list_triggers_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    status = arguments.get("status", "all")
    if status != "all":
        params["status"] = status
    if "page" in arguments:
        params["page"] = arguments["page"]
    if "limit" in arguments:
        params["limit"] = arguments["limit"]

    result = await api("GET", "/v1/triggers", params=params)
    triggers = result.get("triggers", [])
    return json.dumps(
        {
            "count": result.get("count", len(triggers)),
            "total": result.get("total", len(triggers)),
            "page": result.get("page", 1),
            "limit": result.get("limit", len(triggers)),
            "pages": result.get("pages", 1),
            "triggers": [
                {
                    "trigger_id": t.get("trigger_id"),
                    "name": t.get("name"),
                    "status": t.get("status"),
                    "condition": t.get("condition"),
                    "last_checked_at": t.get("last_checked_at"),
                    "last_fired_at": t.get("last_fired_at"),
                    "last_result_summary": t.get("last_result_summary"),
                }
                for t in triggers
            ],
        },
        indent=2,
    )


async def fire_trigger_handler(arguments: dict[str, Any]) -> str:
    trigger_id = arguments.get("trigger_id")
    if not trigger_id:
        return json.dumps({"error": "trigger_id is required"})
    body: dict[str, Any] = {"force": arguments.get("force", False)}
    result = await api("POST", f"/v1/triggers/{trigger_id}/fire", json=body)
    return json.dumps(
        {
            "trigger_id": result.get("trigger_id"),
            "condition_met": result.get("condition_met"),
            "fired": result.get("fired"),
            "simulation_run_id": result.get("simulation_run_id"),
            "recommended_action": result.get("recommended_action"),
            "expected_value": result.get("expected_value"),
            "confidence": result.get("confidence"),
            "fired_at": result.get("fired_at"),
        },
        indent=2,
    )


async def pause_trigger_handler(arguments: dict[str, Any]) -> str:
    trigger_id = arguments.get("trigger_id")
    if not trigger_id:
        return json.dumps({"error": "trigger_id is required"})
    paused = bool(arguments.get("paused", True))
    result = await api(
        "PATCH",
        f"/v1/triggers/{trigger_id}/pause?paused={'true' if paused else 'false'}",
    )
    return json.dumps(
        {
            "trigger_id": result.get("trigger_id"),
            "status": result.get("status"),
        },
        indent=2,
    )


async def delete_trigger_handler(arguments: dict[str, Any]) -> str:
    trigger_id = arguments.get("trigger_id")
    if not trigger_id:
        return json.dumps({"error": "trigger_id is required"})
    await api("DELETE", f"/v1/triggers/{trigger_id}")
    return json.dumps({"trigger_id": trigger_id, "deleted": True})
