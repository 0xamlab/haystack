"""MCP tools for the deterministic Algenta agent-run lifecycle."""

from __future__ import annotations

import json
from typing import Any

from algenta_mcp.client import api

CREATE_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "create_agent_run",
    "description": "Create a persisted Algenta agent run lifecycle resource.",
    "inputSchema": {
        "type": "object",
        "required": ["task"],
        "properties": {
            "task": {"type": "string", "minLength": 5},
            "context": {"type": "object"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "max_steps": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            "output_format": {"type": "string", "default": "text"},
            "approval_mode": {"type": "string", "enum": ["auto", "manual"], "default": "auto"},
            "start_paused": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    },
}

LIST_AGENT_RUNS_SPEC: dict[str, Any] = {
    "name": "list_agent_runs",
    "description": "List persisted Algenta agent runs for the authenticated org.",
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "page": {"type": "integer", "default": 1, "minimum": 1},
            "limit": {"type": "integer", "default": 25, "minimum": 1, "maximum": 200},
            "status": {
                "type": "string",
                "enum": ["running", "paused", "requires_approval", "completed", "cancelled"],
            },
            "request_hash": {"type": "string"},
            "policy_snapshot_id": {"type": "string"},
            "schema_snapshot_id": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "get_agent_run",
    "description": "Fetch a persisted Algenta agent run by run_id.",
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {"run_id": {"type": "string"}},
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_EVENTS_SPEC: dict[str, Any] = {
    "name": "get_agent_run_events",
    "description": "Fetch the append-only event stream for an Algenta agent run.",
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {"type": "string"},
            "limit": {"type": "integer", "default": 1000, "minimum": 1},
        },
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_CHECKPOINTS_SPEC: dict[str, Any] = {
    "name": "get_agent_run_checkpoints",
    "description": "Fetch persisted checkpoints for an Algenta agent run.",
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {"run_id": {"type": "string"}},
        "additionalProperties": False,
    },
}

QUERY_AGENT_RUN_CHECKPOINTS_SPEC: dict[str, Any] = {
    "name": "query_agent_run_checkpoints",
    "description": "Query persisted checkpoints across Algenta agent runs.",
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "page": {"type": "integer", "default": 1, "minimum": 1},
            "limit": {"type": "integer", "default": 25, "minimum": 1, "maximum": 200},
            "status": {
                "type": "string",
                "enum": ["running", "paused", "requires_approval", "completed", "cancelled"],
            },
            "request_hash": {"type": "string"},
            "policy_snapshot_id": {"type": "string"},
            "schema_snapshot_id": {"type": "string"},
            "run_id": {"type": "string"},
            "checkpoint_id": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_MISSION_EVENTS_SPEC: dict[str, Any] = {
    "name": "get_agent_run_mission_events",
    "description": "Fetch canonical mission-event records for an Algenta agent run.",
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {"type": "string"},
            "limit": {"type": "integer", "default": 1000, "minimum": 1},
        },
        "additionalProperties": False,
    },
}

QUERY_AGENT_RUN_MISSION_EVENTS_SPEC: dict[str, Any] = {
    "name": "query_agent_run_mission_events",
    "description": "Query canonical mission-event records across persisted Algenta agent runs.",
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "page": {"type": "integer", "default": 1, "minimum": 1},
            "limit": {"type": "integer", "default": 25, "minimum": 1, "maximum": 200},
            "status": {
                "type": "string",
                "enum": ["running", "paused", "requires_approval", "completed", "cancelled"],
            },
            "request_hash": {"type": "string"},
            "policy_snapshot_id": {"type": "string"},
            "schema_snapshot_id": {"type": "string"},
            "run_id": {"type": "string"},
            "event_type": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

GET_AGENT_RUN_TELEMETRY_SPEC: dict[str, Any] = {
    "name": "get_agent_run_telemetry",
    "description": "Fetch runtime telemetry batches for an Algenta agent run.",
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {
            "run_id": {"type": "string"},
            "limit": {"type": "integer", "default": 1000, "minimum": 1},
        },
        "additionalProperties": False,
    },
}

QUERY_AGENT_RUN_TELEMETRY_SPEC: dict[str, Any] = {
    "name": "query_agent_run_telemetry",
    "description": "Query runtime telemetry batches across persisted Algenta agent runs.",
    "inputSchema": {
        "type": "object",
        "required": [],
        "properties": {
            "page": {"type": "integer", "default": 1, "minimum": 1},
            "limit": {"type": "integer", "default": 25, "minimum": 1, "maximum": 200},
            "status": {
                "type": "string",
                "enum": ["running", "paused", "requires_approval", "completed", "cancelled"],
            },
            "request_hash": {"type": "string"},
            "policy_snapshot_id": {"type": "string"},
            "schema_snapshot_id": {"type": "string"},
            "run_id": {"type": "string"},
            "telemetry_kind": {"type": "string"},
            "module_name": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

RESUME_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "resume_agent_run",
    "description": "Resume a paused Algenta agent run.",
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {"run_id": {"type": "string"}},
        "additionalProperties": False,
    },
}

CANCEL_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "cancel_agent_run",
    "description": "Cancel an Algenta agent run.",
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {"run_id": {"type": "string"}},
        "additionalProperties": False,
    },
}

APPROVE_AGENT_RUN_SPEC: dict[str, Any] = {
    "name": "approve_agent_run",
    "description": "Approve an Algenta agent run waiting on manual approval.",
    "inputSchema": {
        "type": "object",
        "required": ["run_id"],
        "properties": {"run_id": {"type": "string"}},
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
