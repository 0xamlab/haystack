"""
MCP tools: plan_decision, log_decision, list_decisions, get_decision,
record_outcome, execute_decision, delete_decision

Decision Memory — persist decisions and close the feedback loop by recording
actual outcomes. This turns Algenta into a self-improving system:
  - What was decided? → log_decision
  - What actually happened? → record_outcome
  - How accurate were our predictions? → list_decisions (with outcome_delta)
"""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

PLAN_DECISION_SPEC: dict[str, Any] = {
    "name": "plan_decision",
    "description": (
        "Run a validated simulation-style request (the same payload contract as "
        "simulate) but return only the structured DecisionPlan summary — the compact "
        "plan object with recommended action and calibrated confidence, without the "
        "full DecisionEnvelope metrics. Use this when the caller needs the plan "
        "summary for a dashboard or a follow-up plan_decision-to-log_decision flow; "
        "use simulate for the full envelope. Synchronous; the underlying run is "
        "persisted."
    ),
    "inputSchema": {
        "type": "object",
        "description": "Simulation-style payload forwarded to POST /v1/decisions/plan.",
        "additionalProperties": False,
    },
}

LOG_DECISION_SPEC: dict[str, Any] = {
    "name": "log_decision",
    "description": (
        "Persist a decision to the Decision Memory audit trail. "
        "Link to a simulation run_id to bind the full DecisionPlan context. "
        "Call record_outcome later to close the feedback loop and measure prediction accuracy. "
        "Every logged decision is immutably hashed — no tampering possible."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["chosen_action"],
        "additionalProperties": False,
        "properties": {
            "chosen_action": {
                "type": "string",
                "description": "The action that was decided upon.",
            },
            "run_id": {
                "type": "string",
                "description": (
                    "Simulation run_id that produced this decision (from simulate or recommend)."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Business context — what was the situation when this decision was made?"
                ),
            },
            "options_considered": {
                "type": "array",
                "items": {"type": "string"},
                "description": "All option names that were evaluated.",
            },
            "expected_value": {
                "type": "number",
                "description": "Expected outcome value at decision time.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score (0–1) from the simulation.",
            },
            "rationale": {
                "type": "string",
                "description": "Explanation of why this option was chosen.",
            },
            "risk_p5": {
                "type": "number",
                "description": "5th-percentile downside at decision time.",
            },
            "risk_p95": {
                "type": "number",
                "description": "95th-percentile upside at decision time.",
            },
            "risk_pol": {
                "type": "number",
                "description": "Probability of loss (0–1) at decision time.",
            },
            "request_hash": {
                "type": "string",
                "description": "SHA-256 input fingerprint from the simulation.",
            },
            "result_hash": {
                "type": "string",
                "description": "SHA-256 output fingerprint from the simulation.",
            },
        },
    },
}

LIST_DECISIONS_SPEC: dict[str, Any] = {
    "name": "list_decisions",
    "description": (
        "Retrieve the Decision Memory audit trail — all logged decisions, most recent first. "
        "Use with_outcome_only=true to see only decisions where actual results have been recorded. "
        "outcome_delta = actual_outcome - expected_value: negative means worse than predicted."
    ),
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "page": {"type": "integer", "description": "Page number (default 1)."},
            "limit": {
                "type": "integer",
                "description": "Canonical results per page (default 20, max 200).",
            },
            "page_size": {
                "type": "integer",
                "description": "Results per page (default 20, max 100).",
            },
            "with_outcome_only": {
                "type": "boolean",
                "description": "When true, return only decisions with recorded actual outcomes.",
            },
        },
    },
}

GET_DECISION_SPEC: dict[str, Any] = {
    "name": "get_decision",
    "description": "Fetch one decision-memory record by id.",
    "inputSchema": {
        "type": "object",
        "required": ["decision_id"],
        "additionalProperties": False,
        "properties": {
            "decision_id": {
                "type": "string",
                "description": "Decision ID from log_decision or list_decisions.",
            }
        },
    },
}

RECORD_OUTCOME_SPEC: dict[str, Any] = {
    "name": "record_outcome",
    "description": (
        "Close the feedback loop: record what actually happened after a decision was made. "
        "Sets actual_outcome and computes outcome_delta = actual - expected. "
        "Over time this data measures prediction accuracy and reveals systematic biases."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["decision_id", "actual_outcome"],
        "additionalProperties": False,
        "properties": {
            "decision_id": {
                "type": "string",
                "description": "Decision ID from log_decision or list_decisions.",
            },
            "actual_outcome": {
                "type": "number",
                "description": "The observed real-world outcome value.",
            },
            "outcome_notes": {
                "type": "string",
                "description": "Optional explanation of what happened and why.",
            },
        },
    },
}

EXECUTE_DECISION_SPEC: dict[str, Any] = {
    "name": "execute_decision",
    "description": (
        "Dispatch a logged decision to an external webhook and persist the execution receipt."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["decision_id", "webhook_url"],
        "additionalProperties": False,
        "properties": {
            "decision_id": {
                "type": "string",
                "description": "Decision ID from log_decision or list_decisions.",
            },
            "webhook_url": {
                "type": "string",
                "description": "HTTPS webhook that should receive the decision payload.",
            },
            "timeout_seconds": {
                "type": "number",
                "description": "Webhook timeout in seconds.",
            },
            "force": {
                "type": "boolean",
                "description": "Override the idempotency gate for one re-execution.",
            },
            "override_safety": {
                "type": "boolean",
                "description": "Bypass confidence and risk-floor policy gates for this execution.",
            },
            "metadata": {
                "type": "object",
                "description": "Optional key-value pairs merged into the webhook payload.",
            },
        },
    },
}

DELETE_DECISION_SPEC: dict[str, Any] = {
    "name": "delete_decision",
    "description": "Delete one decision-memory record by id.",
    "inputSchema": {
        "type": "object",
        "required": ["decision_id"],
        "additionalProperties": False,
        "properties": {
            "decision_id": {
                "type": "string",
                "description": "Decision ID to delete.",
            }
        },
    },
}


async def plan_decision_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", "/v1/decisions/plan", json=arguments)
    return json.dumps(result, indent=2)


async def log_decision_handler(arguments: dict[str, Any]) -> str:
    body: dict[str, Any] = {
        "chosen_action": arguments["chosen_action"],
    }
    for field in (
        "run_id",
        "context",
        "options_considered",
        "expected_value",
        "confidence",
        "rationale",
        "risk_p5",
        "risk_p95",
        "risk_pol",
        "request_hash",
        "result_hash",
    ):
        if field in arguments:
            body[field] = arguments[field]

    result = await api("POST", "/v1/decisions", json=body)
    return json.dumps(
        {
            "decision_id": result.get("id"),
            "chosen_action": result.get("chosen_action"),
            "expected_value": result.get("expected_value"),
            "confidence": result.get("confidence"),
            "created_at": result.get("created_at"),
            "note": "Decision logged. Call record_outcome later to close the feedback loop.",
        },
        indent=2,
    )


async def list_decisions_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {}
    if "page" in arguments:
        params["page"] = arguments["page"]
    if "limit" in arguments:
        params["limit"] = arguments["limit"]
    if "page_size" in arguments:
        params["page_size"] = arguments["page_size"]
    if "with_outcome_only" in arguments:
        params["with_outcome_only"] = str(arguments["with_outcome_only"]).lower()

    result = await api("GET", "/v1/decisions", params=params)
    decisions = result.get("decisions", [])

    # Summarise outcome accuracy if outcomes exist
    with_outcomes = [d for d in decisions if d.get("actual_outcome") is not None]
    accuracy_note = None
    if with_outcomes:
        deltas = [d["outcome_delta"] for d in with_outcomes if d.get("outcome_delta") is not None]
        if deltas:
            avg_delta = sum(deltas) / len(deltas)
            direction = (
                "over-optimistic"
                if avg_delta < 0
                else "under-optimistic"
                if avg_delta > 0
                else "accurate"
            )
            accuracy_note = (
                f"{len(with_outcomes)} decisions with recorded outcomes. "
                f"Avg outcome_delta: {avg_delta:+.2f} "
                f"({direction})"
            )

    return json.dumps(
        {
            "total": result.get("total"),
            "page": result.get("page"),
            "limit": result.get("limit", result.get("page_size")),
            "pages": result.get("pages"),
            "decisions": [
                {
                    "id": d.get("id"),
                    "chosen_action": d.get("chosen_action"),
                    "expected_value": d.get("expected_value"),
                    "actual_outcome": d.get("actual_outcome"),
                    "outcome_delta": d.get("outcome_delta"),
                    "confidence": d.get("confidence"),
                    "context": d.get("context"),
                    "created_at": d.get("created_at"),
                    "outcome_recorded_at": d.get("outcome_recorded_at"),
                }
                for d in decisions
            ],
            "accuracy_summary": accuracy_note,
        },
        indent=2,
    )


async def get_decision_handler(arguments: dict[str, Any]) -> str:
    decision_id = arguments["decision_id"]
    result = await api("GET", f"/v1/decisions/{decision_id}")
    return json.dumps(result, indent=2)


async def record_outcome_handler(arguments: dict[str, Any]) -> str:
    decision_id = arguments["decision_id"]
    body: dict[str, Any] = {"actual_outcome": arguments["actual_outcome"]}
    if "outcome_notes" in arguments:
        body["outcome_notes"] = arguments["outcome_notes"]

    result = await api("PATCH", f"/v1/decisions/{decision_id}/outcome", json=body)
    delta = result.get("outcome_delta")
    direction = ""
    if delta is not None:
        direction = (
            " (over-optimistic)"
            if delta < 0
            else " (under-optimistic)"
            if delta > 0
            else " (accurate)"
        )

    return json.dumps(
        {
            "decision_id": result.get("id"),
            "chosen_action": result.get("chosen_action"),
            "expected_value": result.get("expected_value"),
            "actual_outcome": result.get("actual_outcome"),
            "outcome_delta": delta,
            "summary": f"Δ = {delta:+.2f}{direction}" if delta is not None else "Outcome recorded.",
        },
        indent=2,
    )


async def execute_decision_handler(arguments: dict[str, Any]) -> str:
    decision_id = arguments["decision_id"]
    body: dict[str, Any] = {"webhook_url": arguments["webhook_url"]}
    for field in ("timeout_seconds", "force", "override_safety", "metadata"):
        if field in arguments:
            body[field] = arguments[field]
    result = await api("POST", f"/v1/decisions/{decision_id}/execute", json=body)
    return json.dumps(result, indent=2)


async def delete_decision_handler(arguments: dict[str, Any]) -> str:
    decision_id = arguments["decision_id"]
    await api("DELETE", f"/v1/decisions/{decision_id}")
    return json.dumps({"decision_id": decision_id, "deleted": True}, indent=2)
