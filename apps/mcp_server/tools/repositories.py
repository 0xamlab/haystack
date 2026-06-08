from __future__ import annotations

import json
from typing import Any

from apps.mcp_server.client import api

CREATE_REPOSITORY_SNAPSHOT_SPEC: dict[str, Any] = {
    "name": "create_repository_snapshot",
    "description": (
        "Create or reuse an immutable repository snapshot for a saved repository connector."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id"],
        "properties": {
            "repository_id": {"type": "string", "minLength": 1},
            "ref": {"type": "string"},
            "include_patterns": {"type": "array", "items": {"type": "string"}},
            "exclude_patterns": {"type": "array", "items": {"type": "string"}},
            "max_files": {"type": "integer", "minimum": 1},
            "max_file_size_bytes": {"type": "integer", "minimum": 1024},
        },
        "additionalProperties": False,
    },
}

GET_REPOSITORY_INTELLIGENCE_CAPABILITIES_SPEC: dict[str, Any] = {
    "name": "get_repository_intelligence_capabilities",
    "description": (
        "List globally supported Repository Intelligence languages and ranked support progress."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_REPOSITORY_SNAPSHOT_SPEC: dict[str, Any] = {
    "name": "get_repository_snapshot",
    "description": "Fetch one immutable repository snapshot by repository_id and snapshot_id.",
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "snapshot_id"],
        "properties": {
            "repository_id": {"type": "string", "minLength": 1},
            "snapshot_id": {"type": "string", "minLength": 1},
        },
        "additionalProperties": False,
    },
}

TRIAGE_REPOSITORY_SPEC: dict[str, Any] = {
    "name": "triage_repository",
    "description": (
        "Triage a repository snapshot into a bounded workspace evidence bundle "
        "with suspect files and symbols."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "snapshot_id", "signals"],
        "properties": {
            "repository_id": {"type": "string", "minLength": 1},
            "snapshot_id": {"type": "string", "minLength": 1},
            "signals": {"type": "object"},
            "max_evidence_items": {"type": "integer", "minimum": 1},
            "max_snippet_lines": {"type": "integer", "minimum": 5},
            "token_budget": {"type": "integer", "minimum": 256},
        },
        "additionalProperties": False,
    },
}

CREATE_REPOSITORY_DECISION_PLAN_SPEC: dict[str, Any] = {
    "name": "create_repository_decision_plan",
    "description": (
        "Create one immutable repository DecisionPlan revision from a workspace "
        "evidence bundle, resolving snapshot_id from triage when omitted."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "workspace_evidence_bundle_ref"],
        "properties": {
            "repository_id": {"type": "string", "minLength": 1},
            "snapshot_id": {"type": "string", "minLength": 1},
            "workspace_evidence_bundle_ref": {"type": "string", "minLength": 1},
            "model": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

QUERY_REPOSITORY_GRAPH_SPEC: dict[str, Any] = {
    "name": "query_repository_graph",
    "description": (
        "Query one persisted repository snapshot for dependency, dependent, "
        "and change-risk graph edges."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id"],
        "properties": {
            "repository_id": {"type": "string", "minLength": 1},
            "snapshot_id": {"type": "string", "minLength": 1},
            "file_path": {"type": "string"},
            "symbol_name": {"type": "string"},
            "workspace_evidence_bundle_ref": {"type": "string"},
            "direction": {"type": "string", "enum": ["inbound", "outbound", "both"]},
            "max_depth": {"type": "integer", "minimum": 1, "maximum": 6},
            "max_nodes": {"type": "integer", "minimum": 1, "maximum": 1024},
        },
        "additionalProperties": False,
    },
}

SIMULATE_REPOSITORY_SPEC: dict[str, Any] = {
    "name": "simulate_repository",
    "description": (
        "Simulate repository patch risk and return the gated DecisionEnvelope, "
        "resolving snapshot_id from the decision plan when omitted."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "decision_plan_id"],
        "properties": {
            "repository_id": {"type": "string", "minLength": 1},
            "snapshot_id": {"type": "string", "minLength": 1},
            "decision_plan_id": {"type": "string", "minLength": 1},
            "runs": {"type": "integer", "minimum": 100},
            "seed": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    },
}

APPLY_REPOSITORY_SPEC: dict[str, Any] = {
    "name": "apply_repository",
    "description": (
        "Apply a simulated repository decision as patch_only, local_branch, or remote_pr."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "decision_plan_id", "simulation_id", "mode"],
        "properties": {
            "repository_id": {"type": "string", "minLength": 1},
            "snapshot_id": {"type": "string", "minLength": 1},
            "decision_plan_id": {"type": "string", "minLength": 1},
            "simulation_id": {"type": "string", "minLength": 1},
            "mode": {"type": "string", "enum": ["patch_only", "local_branch", "remote_pr"]},
            "write_permission": {"type": "boolean"},
            "branch_name": {"type": "string"},
            "commit_message": {"type": "string"},
            "base_branch": {"type": "string"},
            "pull_request_title": {"type": "string"},
            "pull_request_body": {"type": "string"},
        },
        "additionalProperties": False,
    },
}


def _require_string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required.")
    return value.strip()


async def create_repository_snapshot_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    payload = {
        key: value
        for key, value in arguments.items()
        if key
        in {"ref", "include_patterns", "exclude_patterns", "max_files", "max_file_size_bytes"}
    }
    return json.dumps(
        await api("POST", f"/v1/repositories/{repository_id}/snapshots", json=payload),
        indent=2,
    )


async def get_repository_intelligence_capabilities_handler(arguments: dict[str, Any]) -> str:
    if arguments:
        raise ValueError("get_repository_intelligence_capabilities does not accept arguments.")
    return json.dumps(await api("GET", "/v1/repositories/capabilities"), indent=2)


async def get_repository_snapshot_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    snapshot_id = _require_string(arguments, "snapshot_id")
    return json.dumps(
        await api("GET", f"/v1/repositories/{repository_id}/snapshots/{snapshot_id}"),
        indent=2,
    )


async def triage_repository_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    snapshot_id = _require_string(arguments, "snapshot_id")
    signals = arguments.get("signals")
    if not isinstance(signals, dict):
        raise ValueError("signals is required.")
    payload = {
        "snapshot_id": snapshot_id,
        "signals": signals,
    }
    for key in ("max_evidence_items", "max_snippet_lines", "token_budget"):
        if key in arguments:
            payload[key] = arguments[key]
    return json.dumps(
        await api("POST", f"/v1/repositories/{repository_id}/triage", json=payload), indent=2
    )


async def create_repository_decision_plan_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    workspace_evidence_bundle_ref = _require_string(arguments, "workspace_evidence_bundle_ref")
    payload: dict[str, Any] = {"workspace_evidence_bundle_ref": workspace_evidence_bundle_ref}
    snapshot_id = arguments.get("snapshot_id")
    if isinstance(snapshot_id, str) and snapshot_id.strip():
        payload["snapshot_id"] = snapshot_id.strip()
    if "model" in arguments:
        payload["model"] = arguments["model"]
    return json.dumps(
        await api("POST", f"/v1/repositories/{repository_id}/decision-plans", json=payload),
        indent=2,
    )


async def query_repository_graph_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    payload: dict[str, Any] = {}
    snapshot_id = arguments.get("snapshot_id")
    if isinstance(snapshot_id, str) and snapshot_id.strip():
        payload["snapshot_id"] = snapshot_id.strip()
    workspace_evidence_bundle_ref = arguments.get("workspace_evidence_bundle_ref")
    has_workspace_evidence_bundle_ref = (
        isinstance(workspace_evidence_bundle_ref, str)
        and bool(workspace_evidence_bundle_ref.strip())
    )
    if not payload.get("snapshot_id") and not has_workspace_evidence_bundle_ref:
        raise ValueError("snapshot_id or workspace_evidence_bundle_ref is required.")
    for key in (
        "file_path",
        "symbol_name",
        "workspace_evidence_bundle_ref",
        "direction",
        "max_depth",
        "max_nodes",
    ):
        if key in arguments:
            payload[key] = arguments[key]
    return json.dumps(
        await api("POST", f"/v1/repositories/{repository_id}/graph-query", json=payload),
        indent=2,
    )


async def simulate_repository_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    decision_plan_id = _require_string(arguments, "decision_plan_id")
    payload: dict[str, Any] = {"decision_plan_id": decision_plan_id}
    snapshot_id = arguments.get("snapshot_id")
    if isinstance(snapshot_id, str) and snapshot_id.strip():
        payload["snapshot_id"] = snapshot_id.strip()
    for key in ("runs", "seed"):
        if key in arguments:
            payload[key] = arguments[key]
    return json.dumps(
        await api("POST", f"/v1/repositories/{repository_id}/simulate", json=payload), indent=2
    )


async def apply_repository_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    payload = {
        key: value
        for key, value in arguments.items()
        if key
        in {
            "snapshot_id",
            "decision_plan_id",
            "simulation_id",
            "mode",
            "write_permission",
            "branch_name",
            "commit_message",
            "base_branch",
            "pull_request_title",
            "pull_request_body",
        }
    }
    for key in ("decision_plan_id", "simulation_id", "mode"):
        if key not in payload:
            raise ValueError(f"{key} is required.")
    return json.dumps(
        await api("POST", f"/v1/repositories/{repository_id}/apply", json=payload), indent=2
    )
