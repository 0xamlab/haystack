from __future__ import annotations

from apps.api_server.services.repository_intelligence_channel_envelope import (
    build_repository_pipeline_envelope,
    normalize_repository_channel_envelope,
)


def test_normalize_repository_channel_envelope_stabilizes_dynamic_fields() -> None:
    envelope = build_repository_pipeline_envelope(
        repository_id="repo_123",
        response={
            "repository_id": "repo_123",
            "snapshot_id": "snapshot_123",
            "snapshot": {"snapshot_id": "snapshot_123", "ref": "main"},
            "triage": {"workspace_evidence_bundle_ref": "bundle_123"},
            "decision_plan": {
                "decision_plan_id": "plan_123",
                "decision_plan": {
                    "repository_analysis": {
                        "planner_engine": "cline",
                        "agent_run_id": "run_abc",
                        "session_id": "session_xyz",
                        "planner_model_id": "repo-fix-model",
                    }
                },
            },
            "simulation": {
                "run_id": "simulation_456",
                "recommended_action": "apply_patch",
            },
            "created_at": "2026-06-10T12:00:00Z",
        },
    )

    normalized = normalize_repository_channel_envelope(envelope)

    assert normalized["agent"]["agent_run_id"] == "<dynamic-id>"
    assert normalized["agent"]["session_id"] == "<dynamic-id>"
    assert normalized["pipeline"]["simulation_id"] == "<dynamic-id>"
    assert normalized["artifacts"]["pipeline_response"]["created_at"] == "<timestamp>"


def test_build_repository_pipeline_envelope_maps_pipeline_telemetry_to_usage() -> None:
    envelope = build_repository_pipeline_envelope(
        repository_id="repo_123",
        response={
            "repository_id": "repo_123",
            "snapshot_id": "snapshot_123",
            "snapshot": {"snapshot_id": "snapshot_123", "ref": "main"},
            "decision_plan": {
                "decision_plan": {
                    "repository_analysis": {
                        "planner_model_id": "repo-fix-model",
                    }
                },
            },
            "simulation": {
                "run_id": "simulation_456",
                "recommended_action": "apply_patch",
            },
            "telemetry": {
                "counters": {
                    "llm_input_tokens_uncached": 900,
                    "llm_input_tokens_cached_read": 300,
                    "llm_input_tokens_cached_write": 50,
                    "llm_output_tokens": 120,
                }
            },
        },
    )

    assert envelope["agent"]["usage"] == {
        "input_tokens": 1250.0,
        "output_tokens": 120.0,
        "cache_read_tokens": 300.0,
        "cache_write_tokens": 50.0,
        "cost_usd": None,
    }


def test_build_repository_pipeline_envelope_falls_back_to_decision_plan_usage() -> None:
    envelope = build_repository_pipeline_envelope(
        repository_id="repo_123",
        response={
            "repository_id": "repo_123",
            "snapshot_id": "snapshot_123",
            "snapshot": {"snapshot_id": "snapshot_123", "ref": "main"},
            "decision_plan": {
                "decision_plan": {
                    "repository_analysis": {
                        "planner_model_id": "repo-fix-model",
                    }
                },
                "planner_usage": {
                    "input_tokens": 1250.0,
                    "output_tokens": 120.0,
                    "cache_read_tokens": 300.0,
                    "cache_write_tokens": 50.0,
                    "cost_usd": None,
                },
            },
            "simulation": {
                "run_id": "simulation_456",
                "recommended_action": "apply_patch",
            },
        },
    )

    assert envelope["agent"]["usage"]["input_tokens"] == 1250.0
    assert envelope["agent"]["usage"]["cache_read_tokens"] == 300.0


def test_build_repository_pipeline_envelope_prefers_top_level_runtime_metadata() -> None:
    envelope = build_repository_pipeline_envelope(
        repository_id="repo_123",
        response={
            "repository_id": "repo_123",
            "snapshot_id": "snapshot_123",
            "snapshot": {"snapshot_id": "snapshot_123", "ref": "main"},
            "decision_plan": {
                "decision_plan_id": "plan_123",
                "agent_run_id": "run_123",
                "session_id": "session_123",
                "runtime_kind": "cline",
                "is_stub": False,
                "runtime_provider": "anthropic",
                "runtime_model": "claude-sonnet-4-6",
                "decision_plan": {
                    "repository_analysis": {
                        "planner_model_id": "repository.verified_agentic_v1",
                    }
                },
                "planner_usage": {
                    "input_tokens": 1250.0,
                    "output_tokens": 120.0,
                    "cache_read_tokens": 300.0,
                    "cache_write_tokens": 50.0,
                    "cost_usd": None,
                },
            },
            "simulation": {
                "run_id": "simulation_456",
                "recommended_action": "apply_patch",
            },
        },
    )

    assert envelope["agent"]["agent_run_id"] == "run_123"
    assert envelope["agent"]["session_id"] == "session_123"
    assert envelope["agent"]["runtime_kind"] == "cline"
    assert envelope["agent"]["is_stub"] is False
    assert envelope["agent"]["provider"] == "anthropic"
    assert envelope["agent"]["model"] == "claude-sonnet-4-6"
