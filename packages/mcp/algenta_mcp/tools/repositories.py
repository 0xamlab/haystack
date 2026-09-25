from __future__ import annotations

import json
from typing import Any

from algenta_mcp._channel_envelope import (
    build_repository_fix_envelope,
    build_repository_pipeline_envelope,
    build_repository_simulate_patch_envelope,
)
from algenta_mcp.client import api

CREATE_REPOSITORY_SNAPSHOT_SPEC: dict[str, Any] = {
    "name": "create_repository_snapshot",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": True},
    "description": (
        "Create or reuse an immutable, content-hashed snapshot of a saved repository "
        "connector (a connector of a repository type — find its id with list_connectors). "
        "Re-running with identical inputs returns the existing snapshot "
        "(status='existing') instead of duplicating it. The snapshot is the input to "
        "triage_repository and query_repository_graph; every later stage references it by "
        "snapshot_id. Reads the repository and persists snapshot, symbol, and dependency "
        "graph artifacts; it never writes to the repository. Returns snapshot_id, "
        "resolved_revision, content_hash, file_count, language_counts, and artifact "
        "refs. Use get_repository_snapshot to fetch an existing snapshot by id instead."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "ref": {
                "type": "string",
                "description": "Git ref to snapshot; defaults to the connector's default ref.",
            },
            "include_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Glob patterns limiting which files are snapshotted.",
            },
            "exclude_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Glob patterns excluding files from the snapshot.",
            },
            "max_files": {
                "type": "integer",
                "minimum": 1,
                "description": "File-count cap, up to 200000; defaults to 20000.",
            },
            "max_file_size_bytes": {
                "type": "integer",
                "minimum": 1024,
                "description": (
                    "Per-file size cap in bytes, 1024-10000000; defaults to 1000000."
                ),
            },
        },
        "additionalProperties": False,
    },
}

GET_REPOSITORY_INTELLIGENCE_CAPABILITIES_SPEC: dict[str, Any] = {
    "name": "get_repository_intelligence_capabilities",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "List globally supported Repository Intelligence languages and ranked support "
        "progress. Read-only and non-destructive. Check language support here before "
        "create_repository_snapshot. Returns supported_languages and support_progress "
        "(ranked target counts, progress fraction, and label)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

GET_REPOSITORY_SNAPSHOT_SPEC: dict[str, Any] = {
    "name": "get_repository_snapshot",
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Fetch one persisted immutable repository snapshot by repository_id and "
        "snapshot_id, including its resolved_revision, content_hash, file_count, "
        "language_counts, and graph artifact refs. Use this to re-read a snapshot created "
        "earlier with create_repository_snapshot (or through run_repository_pipeline). "
        "Read-only; an unknown snapshot or repository id fails with not_found."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "snapshot_id"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Snapshot id returned by create_repository_snapshot.",
            },
        },
        "additionalProperties": False,
    },
}

TRIAGE_REPOSITORY_SPEC: dict[str, Any] = {
    "name": "triage_repository",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Condense one repository snapshot into a bounded workspace evidence bundle for "
        "the planner: ranked suspect files and symbols with scored, budget-capped "
        "snippets. signals seeds the search — pass issue_text, diagnostics, "
        "failing_tests, changed_files, and/or workspace_context. The returned "
        "workspace_evidence_bundle_ref is the required input to "
        "create_repository_decision_plan; use run_repository_pipeline to chain both "
        "stages in one call. Read-only against the repository; persists the bundle "
        "artifact. Returns suspect_files, suspect_symbols, evidence_items, and token "
        "reduction stats."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "snapshot_id", "signals"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Snapshot id from create_repository_snapshot.",
            },
            "signals": {
                "type": "object",
                "description": (
                    "Evidence seeds: issue_text, diagnostics, failing_tests, "
                    "changed_files, workspace_context."
                ),
            },
            "max_evidence_items": {
                "type": "integer",
                "minimum": 1,
                "description": "Evidence item cap, 1-64; defaults to 16.",
            },
            "max_snippet_lines": {
                "type": "integer",
                "minimum": 5,
                "description": "Per-snippet line cap, 5-200; defaults to 40.",
            },
            "token_budget": {
                "type": "integer",
                "minimum": 256,
                "description": (
                    "Total evidence token budget, 256-32000; defaults to 6000."
                ),
            },
        },
        "additionalProperties": False,
    },
}

CREATE_REPOSITORY_DECISION_PLAN_SPEC: dict[str, Any] = {
    "name": "create_repository_decision_plan",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Create one stored, immutable repository DecisionPlan revision from a triage "
        "workspace evidence bundle and return its decision_plan_id plus the validated patch "
        "diff inline. snapshot_id is resolved from the bundle when omitted. This is the "
        "only LLM-touching stage of the repository chain; model optionally picks the "
        "planner model. The decision_plan_id feeds simulate_repository and "
        "apply_repository. Persists the plan revision. Use run_repository_pipeline to chain "
        "snapshot, triage, plan, and simulate in one call instead."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "workspace_evidence_bundle_ref"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "Snapshot id; resolved from the evidence bundle when omitted."
                ),
            },
            "workspace_evidence_bundle_ref": {
                "type": "string",
                "minLength": 1,
                "description": "Bundle ref returned by triage_repository.",
            },
            "model": {
                "type": "string",
                "description": "Optional planner model override.",
            },
        },
        "additionalProperties": False,
    },
}

QUERY_REPOSITORY_GRAPH_SPEC: dict[str, Any] = {
    "name": "query_repository_graph",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": True, "openWorldHint": False},
    "description": (
        "Walk the dependency graph of one persisted repository snapshot from optional "
        "file_path/symbol_name seeds and return impacted files and symbols with "
        "change-risk scores. Seed scope comes from snapshot_id or a triage "
        "workspace_evidence_bundle_ref — one of the two is required. direction inbound "
        "follows dependents, outbound follows dependencies, both (default) walks both. "
        "Use this before simulate_repository or apply_repository to size the blast "
        "radius of a change. Read-only against the repository; persists a lookup "
        "artifact. Returns seed "
        "files/symbols, direct dependencies and dependents, impacted files/symbols, "
        "graph nodes and edges, and top_change_risk_files."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": (
                    "Snapshot id from create_repository_snapshot; required unless "
                    "workspace_evidence_bundle_ref is given."
                ),
            },
            "file_path": {
                "type": "string",
                "description": "Optional seed file to walk the graph from.",
            },
            "symbol_name": {
                "type": "string",
                "description": "Optional seed symbol to walk the graph from.",
            },
            "workspace_evidence_bundle_ref": {
                "type": "string",
                "description": (
                    "Triage bundle ref; alternative seed scope to snapshot_id."
                ),
            },
            "direction": {
                "type": "string",
                "enum": ["inbound", "outbound", "both"],
                "description": (
                    "Edge direction to walk: inbound = dependents, outbound = "
                    "dependencies; defaults to both."
                ),
            },
            "max_depth": {
                "type": "integer",
                "minimum": 1,
                "maximum": 6,
                "description": "Traversal depth from the seeds, 1-6; defaults to 2.",
            },
            "max_nodes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1024,
                "description": "Graph node cap, 1-1024; defaults to 128.",
            },
        },
        "additionalProperties": False,
    },
}

SIMULATE_REPOSITORY_SPEC: dict[str, Any] = {
    "name": "simulate_repository",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Score the patch risk of a stored repository DecisionPlan with the "
        "deterministic simulation engine and return the gated DecisionEnvelope whose "
        "apply gate apply_repository checks. snapshot_id is resolved from the plan when "
        "omitted. runs pins the scenario count (100 or more; omit for the "
        "complexity-adaptive count) and seed (default 42) makes repeated calls "
        "reproducible — no LLM is involved in this stage. Call "
        "create_repository_decision_plan first; use simulate_repository_patch instead "
        "for a patch that has no stored plan."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "decision_plan_id"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Snapshot id; resolved from the decision plan when omitted.",
            },
            "decision_plan_id": {
                "type": "string",
                "minLength": 1,
                "description": "Plan id from create_repository_decision_plan.",
            },
            "runs": {
                "type": "integer",
                "minimum": 100,
                "description": (
                    "Scenario count, 100-250000; omit for the complexity-adaptive count."
                ),
            },
            "seed": {
                "type": "integer",
                "minimum": 0,
                "description": "Simulation seed for reproducible results; defaults to 42.",
            },
        },
        "additionalProperties": False,
    },
}

APPLY_REPOSITORY_SPEC: dict[str, Any] = {
    "name": "apply_repository",
    "annotations": {"readOnlyHint": False, "destructiveHint": True,
        "idempotentHint": False, "openWorldHint": True},
    "description": (
        "Materialize a simulated repository decision in one of three modes. patch_only "
        "just returns the validated patch diff with applied=false and writes nothing. "
        "local_branch commits the patch to a new branch (default algenta/<plan-suffix>) "
        "in the engine-side checkout and returns commit_sha and local_checkout_path. "
        "remote_pr additionally pushes the branch and opens a pull request, returning "
        "pull_request_url. Both write modes are hard-gated: the simulation must satisfy "
        "policy thresholds (otherwise repository_apply_gate_failed) and "
        "write_permission=true must be passed explicitly (otherwise "
        "repository_write_permission_required). Use patch_only to review the diff "
        "before writing anything, and run_repository_fix to chain the whole flow. "
        "Requires decision_plan_id and simulation_id from simulate_repository."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "decision_plan_id", "simulation_id", "mode"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Snapshot id; resolved from the decision plan when omitted.",
            },
            "decision_plan_id": {
                "type": "string",
                "minLength": 1,
                "description": "Plan id from create_repository_decision_plan.",
            },
            "simulation_id": {
                "type": "string",
                "minLength": 1,
                "description": "Simulation id from simulate_repository.",
            },
            "mode": {
                "type": "string",
                "enum": ["patch_only", "local_branch", "remote_pr"],
                "description": (
                    "patch_only returns the diff; local_branch commits it; remote_pr "
                    "pushes and opens a PR."
                ),
            },
            "write_permission": {
                "type": "boolean",
                "description": (
                    "Must be true for local_branch and remote_pr; ignored for patch_only."
                ),
            },
            "branch_name": {
                "type": "string",
                "description": "Branch to create; defaults to algenta/<plan-suffix>.",
            },
            "commit_message": {
                "type": "string",
                "description": "Commit message; a default naming the plan id is used otherwise.",
            },
            "base_branch": {
                "type": "string",
                "description": (
                    "Branch the patch applies onto and the PR targets; defaults to the "
                    "connector's default branch."
                ),
            },
            "pull_request_title": {
                "type": "string",
                "description": "PR title for remote_pr mode.",
            },
            "pull_request_body": {
                "type": "string",
                "description": "PR body for remote_pr mode.",
            },
        },
        "additionalProperties": False,
    },
}

RUN_REPOSITORY_PIPELINE_SPEC: dict[str, Any] = {
    "name": "run_repository_pipeline",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Run the whole repository-intelligence chain — snapshot, triage, plan, simulate "
        "— in one call and return the canonical repository envelope with every stage's "
        "response, stage timings, and the ids (snapshot_id, plan_id, simulation_id) the "
        "apply step needs. Pass snapshot_id to reuse an existing snapshot or snapshot to "
        "create one inline; stop_after halts the chain early (triage skips the LLM "
        "planner, plan also skips the deterministic simulate). Signals, triage bounds, "
        "model, runs, and seed mirror the standalone stage tools. Use the single-stage "
        "tools when you need to inspect or adjust between stages."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Existing snapshot id to reuse.",
            },
            "snapshot": {
                "type": "object",
                "description": (
                    "Inline create_repository_snapshot arguments when no snapshot_id is "
                    "given."
                ),
            },
            "signals": {
                "type": "object",
                "description": "Triage evidence seeds (see triage_repository).",
            },
            "max_evidence_items": {
                "type": "integer",
                "minimum": 1,
                "description": "Triage evidence item cap; defaults to 16.",
            },
            "max_snippet_lines": {
                "type": "integer",
                "minimum": 5,
                "description": "Triage per-snippet line cap; defaults to 40.",
            },
            "token_budget": {
                "type": "integer",
                "minimum": 256,
                "description": "Triage evidence token budget; defaults to 6000.",
            },
            "model": {
                "type": "string",
                "description": "Optional planner model override for the plan stage.",
            },
            "runs": {
                "type": "integer",
                "minimum": 100,
                "description": (
                    "Simulation scenario count; omit for the complexity-adaptive count."
                ),
            },
            "seed": {
                "type": "integer",
                "minimum": 0,
                "description": "Simulation seed; defaults to 42.",
            },
            "stop_after": {
                "type": "string",
                "enum": ["snapshot", "triage", "plan", "simulate"],
                "description": "Stage to halt after; defaults to simulate (full chain).",
            },
        },
        "additionalProperties": False,
    },
}

SIMULATE_REPOSITORY_PATCH_SPEC: dict[str, Any] = {
    "name": "simulate_repository_patch",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Simulate the risk of an in-flight unified diff against one persisted snapshot "
        "and return the canonical repository envelope — without creating a stored "
        "decision plan. Use this to verify a working-tree patch mid-run; use "
        "simulate_repository when a stored DecisionPlan already exists. Deterministic; "
        "no LLM is involved. Returns the gated DecisionEnvelope including the apply "
        "gate verdict."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id", "snapshot_id", "patch_diff"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "snapshot_id": {
                "type": "string",
                "minLength": 1,
                "description": "Snapshot id from create_repository_snapshot.",
            },
            "patch_diff": {
                "type": "string",
                "minLength": 1,
                "description": "Unified diff of the in-flight patch to evaluate.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Optional caller confidence recorded with the simulation.",
            },
        },
        "additionalProperties": False,
    },
}

RUN_REPOSITORY_FIX_SPEC: dict[str, Any] = {
    "name": "run_repository_fix",
    "annotations": {"readOnlyHint": False, "destructiveHint": False,
        "idempotentHint": False, "openWorldHint": False},
    "description": (
        "Run the repository pipeline and then apply its result in one call, returning "
        "the canonical repository envelope for both stages. pipeline takes "
        "run_repository_pipeline's arguments and must complete through simulate (the "
        "call fails otherwise); apply takes apply_repository's arguments with mode "
        "defaulting to patch_only — the write modes still require the simulation gate "
        "to pass and write_permission=true. Use the separate stage tools when you need "
        "to review the plan or simulation before anything is written."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["repository_id"],
        "properties": {
            "repository_id": {
                "type": "string",
                "minLength": 1,
                "description": "Saved repository connector id from list_connectors.",
            },
            "pipeline": {
                "type": "object",
                "description": "run_repository_pipeline arguments; defaults to {}.",
            },
            "apply": {
                "type": "object",
                "description": (
                    "apply_repository arguments (branch, message, PR fields, "
                    "write_permission); mode defaults to patch_only."
                ),
            },
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


async def run_repository_pipeline_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    payload = {
        key: value
        for key, value in arguments.items()
        if key
        in {
            "snapshot_id",
            "snapshot",
            "signals",
            "max_evidence_items",
            "max_snippet_lines",
            "token_budget",
            "model",
            "runs",
            "seed",
            "stop_after",
        }
    }
    response = await api("POST", f"/v1/repositories/{repository_id}/pipeline", json=payload)
    envelope = build_repository_pipeline_envelope(repository_id=repository_id, response=response)
    return json.dumps(envelope, indent=2)


async def simulate_repository_patch_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    snapshot_id = _require_string(arguments, "snapshot_id")
    patch_diff = _require_string(arguments, "patch_diff")
    payload: dict[str, Any] = {"snapshot_id": snapshot_id, "patch_diff": patch_diff}
    if "confidence" in arguments:
        payload["confidence"] = arguments["confidence"]
    response = await api("POST", f"/v1/repositories/{repository_id}/simulate-patch", json=payload)
    envelope = build_repository_simulate_patch_envelope(
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        response=response,
    )
    return json.dumps(envelope, indent=2)


async def run_repository_fix_handler(arguments: dict[str, Any]) -> str:
    repository_id = _require_string(arguments, "repository_id")
    pipeline_payload = arguments.get("pipeline")
    if pipeline_payload is None:
        pipeline_payload = {}
    if not isinstance(pipeline_payload, dict):
        raise ValueError("pipeline must be an object.")
    apply_payload = arguments.get("apply")
    if apply_payload is None:
        apply_payload = {}
    if not isinstance(apply_payload, dict):
        raise ValueError("apply must be an object.")

    pipeline_response = await api(
        "POST", f"/v1/repositories/{repository_id}/pipeline", json=pipeline_payload
    )
    pipeline_envelope = build_repository_pipeline_envelope(
        repository_id=repository_id,
        response=pipeline_response,
    )
    snapshot_id = pipeline_envelope["pipeline"]["snapshot_id"]
    decision_plan_id = pipeline_envelope["pipeline"]["plan_id"]
    simulation_id = pipeline_envelope["pipeline"]["simulation_id"]
    if not decision_plan_id or not simulation_id:
        raise ValueError("pipeline must complete through simulate before fix can apply.")

    resolved_apply_payload = {
        "snapshot_id": snapshot_id,
        "decision_plan_id": decision_plan_id,
        "simulation_id": simulation_id,
        "mode": apply_payload.get("mode", "patch_only"),
        **{
            key: value
            for key, value in apply_payload.items()
            if key
            in {
                "write_permission",
                "branch_name",
                "commit_message",
                "base_branch",
                "pull_request_title",
                "pull_request_body",
            }
        },
    }
    apply_response = await api(
        "POST", f"/v1/repositories/{repository_id}/apply", json=resolved_apply_payload
    )
    envelope = build_repository_fix_envelope(
        repository_id=repository_id,
        pipeline_response=pipeline_response,
        apply_response=apply_response,
    )
    return json.dumps(envelope, indent=2)
