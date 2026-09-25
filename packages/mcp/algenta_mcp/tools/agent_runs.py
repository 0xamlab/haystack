"""MCP tools for the deterministic Algenta agent-run lifecycle."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

CREATE_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "create_agent_run",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Create a persisted agent run lifecycle resource for a natural-language task. "
        "With approval_mode=auto (default) the run picks a tool from the task wording, "
        "executes synchronously, and returns completed; approval_mode=manual parks it at "
        "requires_approval until approve_agent_run, and start_paused=true parks it at "
        "paused until resume_agent_run. The run, its step log, append-only events, and a "
        "replayable checkpoint are persisted under the caller's organization and the "
        "creation is audit-logged. Use product_agent_run for the simpler synchronous "
        "helper, list_agent_runs to browse, and get_agent_run_events to follow the "
        "trail. Returns the full run resource with run_id and status."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["task"],
        "properties": {
            "task": {
                "type": "string",
                "minLength": 5,
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
                "default": 10,
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum execution steps, 1-50; defaults to 10.",
            },
            "output_format": {
                "type": "string",
                "default": "text",
                "description": "Result format: text (default), json, or markdown.",
            },
            "approval_mode": {
                "type": "string",
                "enum": ["auto", "manual"],
                "default": "auto",
                "description": (
                    "auto executes immediately (default); manual waits for "
                    "approve_agent_run before executing."
                ),
            },
            "start_paused": {
                "type": "boolean",
                "default": False,
                "description": "Persist the run in paused state until resume_agent_run.",
            },
        },
        "additionalProperties": False,
    },
}

LIST_AGENT_RUNS_SPEC: dict[str, Any] = {
    "name": "list_agent_runs",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the organization's persisted agent runs, paginated (defaults page 1, "
        "limit 25), with lineage-aware filters: status, request_hash (find reruns of "
        "the same request), policy_snapshot_id, and schema_snapshot_id (find runs under "
        "one policy or schema revision). Use get_agent_run for one run's full detail "
        "and query_agent_run_checkpoints to search checkpoints across runs. Read-only. "
        "Returns data, total, page, limit, and pages."
    ),
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "page": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "description": "1-based page number; defaults to 1.",
            },
            "limit": {
                "type": "integer",
                "default": 25,
                "minimum": 1,
                "maximum": 200,
                "description": "Runs per page, up to 200; defaults to 25.",
            },
            "status": {
                "type": "string",
                "enum": ["running", "paused", "requires_approval", "completed", "cancelled"],
                "description": "Keep only runs in this lifecycle status.",
            },
            "request_hash": {
                "type": "string",
                "description": "Keep only runs created from this request hash.",
            },
            "policy_snapshot_id": {
                "type": "string",
                "description": "Keep only runs under this execution-policy snapshot.",
            },
            "schema_snapshot_id": {
                "type": "string",
                "description": "Keep only runs under this schema snapshot.",
            },
        },
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "get_agent_run",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch one persisted agent run by run_id: status, task, selected_tool, steps, "
        "result, tools_used, and the policy/schema snapshot ids it ran under. Use "
        "list_agent_runs to find run ids, get_agent_run_events for its event trail, "
        "and get_agent_run_checkpoints for replay checkpoints. Read-only; an unknown "
        "run_id fails with agent_run_not_found."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Run id returned by create_agent_run or list_agent_runs.",
            },
        },
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_EVENTS_SPEC: dict[str, Any] = {
    "name": "get_agent_run_events",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch the append-only event stream of one agent run — run_created, "
        "tool_selected, tool_executed, run_completed, and the pause/approve/cancel "
        "transitions — in order. Use get_agent_run_mission_events for the canonical "
        "mission-event projection of the same trail. Read-only; an unknown run_id "
        "fails with agent_run_not_found. Returns data plus total_events."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Run id returned by create_agent_run or list_agent_runs.",
            },
            "limit": {
                "type": "integer",
                "default": 1000,
                "minimum": 1,
                "description": "Maximum events returned, up to 1000; defaults to 1000.",
            },
        },
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_CHECKPOINTS_SPEC: dict[str, Any] = {
    "name": "get_agent_run_checkpoints",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List the persisted checkpoints of one agent run — the deterministic snapshots "
        "written at creation and every lifecycle transition that make the run replayable. "
        "Use query_agent_run_checkpoints to search checkpoints across runs. Read-only; an "
        "unknown run_id fails with agent_run_not_found. Returns the run's checkpoint "
        "records."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Run id returned by create_agent_run or list_agent_runs.",
            },
        },
        "additionalProperties": False,
    },
}

QUERY_AGENT_RUN_CHECKPOINTS_SPEC: dict[str, Any] = {
    "name": "query_agent_run_checkpoints",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Search persisted checkpoints across all of the organization's agent runs, "
        "paginated (defaults page 1, limit 25). Filter by run_id or checkpoint_id to "
        "pinpoint one, or by status, request_hash, policy_snapshot_id, or "
        "schema_snapshot_id to audit lineage. Use get_agent_run_checkpoints when you "
        "already know the run_id and want its full checkpoint list. Read-only. "
        "Returns data, total, page, limit, and pages."
    ),
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "page": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "description": "1-based page number; defaults to 1.",
            },
            "limit": {
                "type": "integer",
                "default": 25,
                "minimum": 1,
                "maximum": 200,
                "description": "Checkpoints per page, up to 200; defaults to 25.",
            },
            "status": {
                "type": "string",
                "enum": ["running", "paused", "requires_approval", "completed", "cancelled"],
                "description": "Keep only checkpoints of runs in this status.",
            },
            "request_hash": {
                "type": "string",
                "description": "Keep only checkpoints of runs with this request hash.",
            },
            "policy_snapshot_id": {
                "type": "string",
                "description": "Keep only checkpoints under this execution-policy snapshot.",
            },
            "schema_snapshot_id": {
                "type": "string",
                "description": "Keep only checkpoints under this schema snapshot.",
            },
            "run_id": {
                "type": "string",
                "description": "Keep only checkpoints of this run.",
            },
            "checkpoint_id": {
                "type": "string",
                "description": "Fetch exactly this checkpoint.",
            },
        },
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_MISSION_EVENTS_SPEC: dict[str, Any] = {
    "name": "get_agent_run_mission_events",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch the canonical mission-event records of one agent run — the typed, indexed "
        "projection of its lifecycle used for audit and replay. Use get_agent_run_events "
        "for the raw append-only stream and query_agent_run_mission_events to search "
        "mission events across runs. Read-only; an unknown run_id fails with "
        "agent_run_not_found. Returns the run's canonical mission-event records."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Run id returned by create_agent_run or list_agent_runs.",
            },
            "limit": {
                "type": "integer",
                "default": 1000,
                "minimum": 1,
                "description": "Maximum events returned, up to 1000; defaults to 1000.",
            },
        },
        "additionalProperties": False,
    },
}

QUERY_AGENT_RUN_MISSION_EVENTS_SPEC: dict[str, Any] = {
    "name": "query_agent_run_mission_events",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Search canonical mission-event records across all of the organization's "
        "agent runs, paginated (defaults page 1, limit 25) and newest first. Filter "
        "by run_id or event_type to pinpoint, or by status, request_hash, "
        "policy_snapshot_id, or schema_snapshot_id for lineage audits. Use "
        "get_agent_run_mission_events when you already know the run_id. Read-only. "
        "Returns data, total, page, limit, and pages."
    ),
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "page": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "description": "1-based page number; defaults to 1.",
            },
            "limit": {
                "type": "integer",
                "default": 25,
                "minimum": 1,
                "maximum": 200,
                "description": "Events per page, up to 200; defaults to 25.",
            },
            "status": {
                "type": "string",
                "enum": ["running", "paused", "requires_approval", "completed", "cancelled"],
                "description": "Keep only events of runs in this status.",
            },
            "request_hash": {
                "type": "string",
                "description": "Keep only events of runs with this request hash.",
            },
            "policy_snapshot_id": {
                "type": "string",
                "description": "Keep only events under this execution-policy snapshot.",
            },
            "schema_snapshot_id": {
                "type": "string",
                "description": "Keep only events under this schema snapshot.",
            },
            "run_id": {
                "type": "string",
                "description": "Keep only events of this run.",
            },
            "event_type": {
                "type": "string",
                "description": "Keep only events of this type, e.g. run_completed.",
            },
        },
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_TELEMETRY_SPEC: dict[str, Any] = {
    "name": "get_agent_run_telemetry",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch the runtime telemetry batches recorded for one agent run — the module-level "
        "timing and execution detail captured while it ran. Use query_agent_run_telemetry "
        "to search telemetry across runs by kind or module. Read-only; an unknown run_id "
        "fails with agent_run_not_found. Returns the run's telemetry batches."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Run id returned by create_agent_run or list_agent_runs.",
            },
            "limit": {
                "type": "integer",
                "default": 1000,
                "minimum": 1,
                "description": "Maximum batches returned, up to 1000; defaults to 1000.",
            },
        },
        "additionalProperties": False,
    },
}

QUERY_AGENT_RUN_TELEMETRY_SPEC: dict[str, Any] = {
    "name": "query_agent_run_telemetry",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Search runtime telemetry batches across all of the organization's agent "
        "runs, paginated (defaults page 1, limit 25). Filter by run_id, "
        "telemetry_kind, or module_name to pinpoint, or by status, request_hash, "
        "policy_snapshot_id, or schema_snapshot_id for lineage audits. Use "
        "get_agent_run_telemetry when you already know the run_id. Read-only. "
        "Returns data, total, page, limit, and pages."
    ),
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "page": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "description": "1-based page number; defaults to 1.",
            },
            "limit": {
                "type": "integer",
                "default": 25,
                "minimum": 1,
                "maximum": 200,
                "description": "Batches per page, up to 200; defaults to 25.",
            },
            "status": {
                "type": "string",
                "enum": ["running", "paused", "requires_approval", "completed", "cancelled"],
                "description": "Keep only telemetry of runs in this status.",
            },
            "request_hash": {
                "type": "string",
                "description": "Keep only telemetry of runs with this request hash.",
            },
            "policy_snapshot_id": {
                "type": "string",
                "description": "Keep only telemetry under this execution-policy snapshot.",
            },
            "schema_snapshot_id": {
                "type": "string",
                "description": "Keep only telemetry under this schema snapshot.",
            },
            "run_id": {
                "type": "string",
                "description": "Keep only telemetry of this run.",
            },
            "telemetry_kind": {
                "type": "string",
                "description": "Keep only telemetry batches of this kind.",
            },
            "module_name": {
                "type": "string",
                "description": "Keep only telemetry batches from this runtime module.",
            },
        },
        "additionalProperties": False,
    },
}

RESUME_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "resume_agent_run",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Resume a paused agent run by run_id. A run created with approval_mode=auto "
        "executes to completion synchronously and returns completed; a manual-mode run "
        "moves to requires_approval and still needs approve_agent_run. Resuming "
        "anything that is not paused fails with agent_run_invalid_state; an unknown "
        "run_id fails with agent_run_not_found. The transition is audit-logged and "
        "checkpointed. Returns the updated run resource."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Paused run id from create_agent_run or list_agent_runs.",
            },
        },
        "additionalProperties": False,
    },
}

CANCEL_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "cancel_agent_run",
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Cancel an agent run by run_id, ending its lifecycle at cancelled. Only a "
        "paused or requires_approval run can be cancelled — anything else fails with "
        "agent_run_invalid_state. Cancelling is idempotent: repeating the call on an "
        "already-cancelled or never-existing run_id returns success with "
        "already_absent: true instead of agent_run_not_found. Use resume_agent_run or "
        "approve_agent_run to continue a waiting run instead. The first cancellation "
        "is audit-logged and checkpointed; the run record is kept, not deleted, and "
        "repeats record nothing further. Returns the updated run resource."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Run id from create_agent_run or list_agent_runs.",
            },
        },
        "additionalProperties": False,
    },
}

APPROVE_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "approve_agent_run",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Approve an agent run that is waiting on manual approval (status requires_approval) "
        "and execute it synchronously to completion. Runs in any other state fail with "
        "agent_run_invalid_state; an unknown run_id fails with agent_run_not_found. The "
        "approval is the human-in-the-loop gate for manual-mode runs and is audit-logged "
        "and checkpointed. Returns the updated run resource. Use resume_agent_run for "
        "paused runs instead."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Waiting run id from create_agent_run or list_agent_runs.",
            },
        },
        "additionalProperties": False,
    },
}


async def create_agent_run_handler(arguments: dict[str, Any]) -> str:
    body: dict[str, Any] = {
        "task": arguments["task"],
        "max_steps": int(arguments.get("max_steps", 10)),
        "output_format": arguments.get("output_format", "text"),
        "approval_mode": arguments.get("approval_mode", "auto"),
        "start_paused": bool(arguments.get("start_paused", False)),
    }
    for field in ("context", "tools"):
        if field in arguments:
            body[field] = arguments[field]
    result = await api("POST", "/v1/agent/runs", json=body)
    return json.dumps(result, indent=2)


async def list_agent_runs_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {
        "page": int(arguments.get("page", 1)),
        "limit": int(arguments.get("limit", 25)),
    }
    for field in ("status", "request_hash", "policy_snapshot_id", "schema_snapshot_id"):
        if field in arguments:
            params[field] = arguments[field]
    result = await api("GET", "/v1/agent/runs", params=params)
    return json.dumps(result, indent=2)


async def get_agent_run_handler(arguments: dict[str, Any]) -> str:
    result = await api("GET", f"/v1/agent/runs/{arguments['run_id']}")
    return json.dumps(result, indent=2)


async def get_agent_run_events_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "GET",
        f"/v1/agent/runs/{arguments['run_id']}/events",
        params={"limit": int(arguments.get("limit", 1000))},
    )
    return json.dumps(result, indent=2)


async def get_agent_run_checkpoints_handler(arguments: dict[str, Any]) -> str:
    result = await api("GET", f"/v1/agent/runs/{arguments['run_id']}/checkpoints")
    return json.dumps(result, indent=2)


async def query_agent_run_checkpoints_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {
        "page": int(arguments.get("page", 1)),
        "limit": int(arguments.get("limit", 25)),
    }
    for field in (
        "status",
        "request_hash",
        "policy_snapshot_id",
        "schema_snapshot_id",
        "run_id",
        "checkpoint_id",
    ):
        if field in arguments:
            params[field] = arguments[field]
    result = await api("GET", "/v1/agent/runs/checkpoints", params=params)
    return json.dumps(result, indent=2)


async def get_agent_run_mission_events_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "GET",
        f"/v1/agent/runs/{arguments['run_id']}/mission-events",
        params={"limit": int(arguments.get("limit", 1000))},
    )
    return json.dumps(result, indent=2)


async def query_agent_run_mission_events_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {
        "page": int(arguments.get("page", 1)),
        "limit": int(arguments.get("limit", 25)),
    }
    for field in (
        "status",
        "request_hash",
        "policy_snapshot_id",
        "schema_snapshot_id",
        "run_id",
        "event_type",
    ):
        if field in arguments:
            params[field] = arguments[field]
    result = await api("GET", "/v1/agent/runs/mission-events", params=params)
    return json.dumps(result, indent=2)


async def get_agent_run_telemetry_handler(arguments: dict[str, Any]) -> str:
    result = await api(
        "GET",
        f"/v1/agent/runs/{arguments['run_id']}/telemetry",
        params={"limit": int(arguments.get("limit", 1000))},
    )
    return json.dumps(result, indent=2)


async def query_agent_run_telemetry_handler(arguments: dict[str, Any]) -> str:
    params: dict[str, Any] = {
        "page": int(arguments.get("page", 1)),
        "limit": int(arguments.get("limit", 25)),
    }
    for field in (
        "status",
        "request_hash",
        "policy_snapshot_id",
        "schema_snapshot_id",
        "run_id",
        "telemetry_kind",
        "module_name",
    ):
        if field in arguments:
            params[field] = arguments[field]
    result = await api("GET", "/v1/agent/runs/telemetry", params=params)
    return json.dumps(result, indent=2)


async def resume_agent_run_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", f"/v1/agent/runs/{arguments['run_id']}/resume", json={})
    return json.dumps(result, indent=2)


async def cancel_agent_run_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", f"/v1/agent/runs/{arguments['run_id']}/cancel", json={})
    return json.dumps(result, indent=2)


async def approve_agent_run_handler(arguments: dict[str, Any]) -> str:
    result = await api("POST", f"/v1/agent/runs/{arguments['run_id']}/approve", json={})
    return json.dumps(result, indent=2)
