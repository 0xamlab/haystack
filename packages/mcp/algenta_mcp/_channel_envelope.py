"""VENDORED VERBATIM from apps/api_server/services/repository_intelligence_channel_envelope.py.
Stdlib-only pure formatter (no monorepo deps). Kept byte-identical to the source; a drift-guard
test (tests/test_mcp_vendored_parity.py) fails if they diverge. Do not edit here — edit the source."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _maybe_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _simulation_id(payload: dict[str, Any]) -> str | None:
    validated_inputs = _as_dict(payload.get("validated_inputs"))
    return (
        _maybe_str(validated_inputs.get("simulation_id"))
        or _maybe_str(payload.get("simulation_id"))
        or _maybe_str(payload.get("run_id"))
    )


def _gate_from_simulation(payload: dict[str, Any]) -> tuple[str, list[str]]:
    score_breakdown = _as_dict(payload.get("score_breakdown"))
    apply_gate = _as_dict(score_breakdown.get("apply_gate"))
    if isinstance(apply_gate.get("passed"), bool):
        return (
            "apply_allowed" if apply_gate["passed"] else "apply_blocked",
            [] if apply_gate["passed"] else ["simulation_gate_failed"],
        )
    if payload.get("recommended_action") == "apply_patch":
        return "apply_allowed", []
    if payload:
        return "apply_blocked", ["simulation_gate_failed"]
    return "apply_blocked", ["simulation_missing"]


def _agent_block_from_plan(decision_plan_payload: dict[str, Any]) -> dict[str, Any]:
    decision_plan = _as_dict(decision_plan_payload.get("decision_plan"))
    analysis = _as_dict(decision_plan.get("repository_analysis"))
    return {
        "agent_run_id": _maybe_str(decision_plan_payload.get("agent_run_id"))
        or _maybe_str(analysis.get("agent_run_id")),
        "session_id": _maybe_str(decision_plan_payload.get("session_id"))
        or _maybe_str(analysis.get("session_id")),
        "runtime_kind": _maybe_str(decision_plan_payload.get("runtime_kind"))
        or _maybe_str(analysis.get("planner_engine")),
        "is_stub": decision_plan_payload.get("is_stub")
        if isinstance(decision_plan_payload.get("is_stub"), bool)
        else analysis.get("is_stub")
        if isinstance(analysis.get("is_stub"), bool)
        else None,
        "provider": _maybe_str(decision_plan_payload.get("runtime_provider"))
        or analysis.get("planner_provider_backend"),
        "model": _maybe_str(decision_plan_payload.get("runtime_model"))
        or analysis.get("planner_model_id"),
        "usage": {
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
            "cost_usd": None,
        },
    }


def _numeric_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _usage_from_pipeline_response(payload: dict[str, Any]) -> dict[str, Any] | None:
    telemetry = _as_dict(payload.get("telemetry"))
    counters = _as_dict(telemetry.get("counters"))
    uncached = _numeric_or_none(counters.get("llm_input_tokens_uncached"))
    cache_read = _numeric_or_none(counters.get("llm_input_tokens_cached_read"))
    cache_write = _numeric_or_none(counters.get("llm_input_tokens_cached_write"))
    output = _numeric_or_none(counters.get("llm_output_tokens"))
    values = (uncached, cache_read, cache_write, output)
    if not any(value is not None for value in values):
        return None
    return {
        "input_tokens": (uncached or 0.0) + (cache_read or 0.0) + (cache_write or 0.0),
        "output_tokens": output or 0.0,
        "cache_read_tokens": cache_read or 0.0,
        "cache_write_tokens": cache_write or 0.0,
        "cost_usd": None,
    }


def _usage_from_decision_plan_response(payload: dict[str, Any]) -> dict[str, Any] | None:
    usage = _as_dict(payload.get("planner_usage"))
    required_keys = {
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
    }
    if not required_keys.issubset(set(usage)):
        return None
    normalized = {
        key: _numeric_or_none(usage.get(key))
        for key in (*required_keys, "cost_usd")
    }
    if any(normalized[key] is None for key in required_keys):
        return None
    return normalized


def build_repository_pipeline_envelope(
    *,
    repository_id: str,
    response: dict[str, Any],
) -> dict[str, Any]:
    snapshot = _as_dict(response.get("snapshot"))
    triage = _as_dict(response.get("triage"))
    decision_plan = _as_dict(response.get("decision_plan"))
    simulation = _as_dict(response.get("simulation"))
    gate_decision, gate_reasons = _gate_from_simulation(simulation)
    agent = _agent_block_from_plan(decision_plan)
    usage = _usage_from_pipeline_response(response) or _usage_from_decision_plan_response(
        decision_plan
    )
    if usage is not None:
        agent["usage"] = usage

    return {
        "repository": {
            "id": repository_id,
            "ref": snapshot.get("ref"),
            "worktree": None,
        },
        "pipeline": {
            "snapshot_id": response.get("snapshot_id") or snapshot.get("snapshot_id"),
            "triage_id": triage.get("workspace_evidence_bundle_ref"),
            "plan_id": decision_plan.get("decision_plan_id"),
            "simulation_id": _simulation_id(simulation),
            "apply_id": None,
        },
        "agent": agent,
        "telemetry": {
            "tool_calls_by_name": {},
            "engine_calls_by_name": {},
            "govern_hook_status": "unknown",
            "approval_events": [],
        },
        "gate": {
            "decision": gate_decision,
            "reasons": gate_reasons,
        },
        "artifacts": {
            "pipeline_response": response,
        },
    }


def build_repository_simulate_patch_envelope(
    *,
    repository_id: str,
    snapshot_id: str | None,
    response: dict[str, Any],
) -> dict[str, Any]:
    gate_decision, gate_reasons = _gate_from_simulation(response)
    return {
        "repository": {
            "id": repository_id,
            "ref": None,
            "worktree": None,
        },
        "pipeline": {
            "snapshot_id": snapshot_id,
            "triage_id": None,
            "plan_id": None,
            "simulation_id": _simulation_id(response),
            "apply_id": None,
        },
        "agent": {
            "agent_run_id": None,
            "session_id": None,
            "runtime_kind": None,
            "is_stub": None,
            "provider": None,
            "model": None,
            "usage": {
                "input_tokens": None,
                "output_tokens": None,
                "cache_read_tokens": None,
                "cache_write_tokens": None,
                "cost_usd": None,
            },
        },
        "telemetry": {
            "tool_calls_by_name": {},
            "engine_calls_by_name": {},
            "govern_hook_status": "unknown",
            "approval_events": [],
        },
        "gate": {
            "decision": gate_decision,
            "reasons": gate_reasons,
        },
        "artifacts": {
            "simulation_response": response,
        },
    }


def build_repository_fix_envelope(
    *,
    repository_id: str,
    pipeline_response: dict[str, Any],
    apply_response: dict[str, Any],
) -> dict[str, Any]:
    envelope = build_repository_pipeline_envelope(
        repository_id=repository_id,
        response=pipeline_response,
    )
    envelope["pipeline"]["apply_id"] = _maybe_str(
        apply_response.get("simulation_id")
    ) or _maybe_str(envelope["pipeline"].get("simulation_id"))
    envelope["repository"]["worktree"] = apply_response.get("local_checkout_path")
    envelope["gate"] = {
        "decision": (
            "apply_allowed"
            if _as_dict(apply_response.get("apply_gate")).get("passed") is True
            else "apply_blocked"
        ),
        "reasons": []
        if _as_dict(apply_response.get("apply_gate")).get("passed") is True
        else ["apply_gate_failed"],
    }
    envelope["artifacts"] = {
        "pipeline_response": pipeline_response,
        "apply_response": apply_response,
        "patch": apply_response.get("patch"),
    }
    return envelope


def normalize_repository_channel_envelope(
    envelope: dict[str, Any],
) -> dict[str, Any]:
    def _normalize(value: Any, *, key: str | None = None) -> Any:
        if isinstance(value, dict):
            normalized: dict[str, Any] = {}
            for child_key in sorted(value):
                child = value[child_key]
                if child_key in {
                    "agent_run_id",
                    "session_id",
                    "simulation_id",
                    "apply_id",
                    "run_id",
                    "request_id",
                }:
                    normalized[child_key] = "<dynamic-id>" if child is not None else None
                    continue
                if child_key.endswith("_at") and child is not None:
                    normalized[child_key] = "<timestamp>"
                    continue
                normalized[child_key] = _normalize(child, key=child_key)
            return normalized
        if isinstance(value, list):
            return [_normalize(item, key=key) for item in value]
        if isinstance(value, str) and key and "path" in key:
            return value.replace("\\", "/")
        return deepcopy(value)

    return _normalize(envelope)
