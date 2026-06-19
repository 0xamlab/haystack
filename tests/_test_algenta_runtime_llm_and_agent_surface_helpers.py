"""Shared imports + helpers for test_algenta_runtime_llm_and_agent_surface_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-3/tests/test_algenta_runtime_llm_and_agent_surface.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

import importlib

import sys

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

ALGENTA_CORE = ROOT / "packages" / "algenta-core"

PYTHON_SDK = ROOT / "packages" / "python-sdk"

for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta = importlib.import_module("algenta")

Runtime = algenta.Runtime

AgentRunEventsOutput = algenta.AgentRunEventsOutput

AgentRunCheckpointListResponseOutput = algenta.AgentRunCheckpointListResponseOutput

AgentRunListOutput = algenta.AgentRunListOutput

AgentRunMissionEventListResponseOutput = algenta.AgentRunMissionEventListResponseOutput

AgentRunMissionEventsOutput = algenta.AgentRunMissionEventsOutput

AgentRunStreamEventOutput = algenta.AgentRunStreamEventOutput

AgentRunTelemetryListOutput = algenta.AgentRunTelemetryListOutput

AgentRunTelemetryOutput = algenta.AgentRunTelemetryOutput

AgentRunOutput = algenta.AgentRunOutput

APIKeyCreatedOutput = algenta.APIKeyCreatedOutput

APIKeyInfoOutput = algenta.APIKeyInfoOutput

ChatCompletionsOutput = algenta.ChatCompletionsOutput

ChatCompletionsStreamChunkOutput = algenta.ChatCompletionsStreamChunkOutput

CountTokensOutput = algenta.CountTokensOutput

DecisionListOutput = algenta.DecisionListOutput

DecisionLogOutput = algenta.DecisionLogOutput

DecisionPlanOutput = algenta.DecisionPlanOutput

DeploymentCostOutput = algenta.DeploymentCostOutput

DeploymentDeleteOutput = algenta.DeploymentDeleteOutput

DeploymentOutput = algenta.DeploymentOutput

DeploymentRegionsOutput = algenta.DeploymentRegionsOutput

EmbeddingSimilarityOutput = algenta.EmbeddingSimilarityOutput

EmbeddingsOutput = algenta.EmbeddingsOutput

ExecutionReceiptOutput = algenta.ExecutionReceiptOutput

LLMModelListOutput = algenta.LLMModelListOutput

ArtifactBridgeResolveOutput = algenta.ArtifactBridgeResolveOutput

ResponseStreamEventOutput = algenta.ResponseStreamEventOutput

ResponsesOutput = algenta.ResponsesOutput

RerankResponseOutput = algenta.RerankResponseOutput

RuntimeConfigurationError = algenta.RuntimeConfigurationError

RuntimeValidationError = algenta.RuntimeValidationError

TokenizeOutput = algenta.TokenizeOutput

UsageOutput = algenta.UsageOutput

def _make_model_list_payload() -> dict[str, object]:
    return {
        "object": "list",
        "data": [
            {
                "id": "text.tokenizer",
                "object": "model",
                "owned_by": "algenta",
                "runtime_module": "text.tokenizer",
                "description": "Deterministic tokenizer utility model",
                "capabilities": ["tokenize", "count_tokens", "chat_completions"],
                "supported_endpoints": [
                    "/v1/models",
                    "/v1/tokenize",
                    "/v1/count_tokens",
                    "/v1/chat/completions",
                    "/v1/responses",
                ],
                "runtime_functions": ["tokenize_text", "count_text_tokens"],
                "tokenizer_kind": "wordpiece",
                "provider_backend": None,
                "routing_targets": [],
                "resolved_routing_targets": [],
                "chat_routing_targets": [],
                "resolved_chat_routing_targets": [],
                "embedding_routing_targets": [],
                "resolved_embedding_routing_targets": [],
                "routing_fallback_policy": None,
                "chat_routing_fallback_policy": None,
                "embedding_routing_fallback_policy": None,
                "routing_fallback_on": [],
                "chat_routing_fallback_on": [],
                "embedding_routing_fallback_on": [],
                "routing_max_attempts": None,
                "chat_routing_max_attempts": None,
                "embedding_routing_max_attempts": None,
                "timeout_seconds": None,
                "chat_timeout_seconds": None,
                "embedding_timeout_seconds": None,
                "required_provider_headers": [],
                "provider_auth_env_vars": [],
                "provider_auth_configured": False,
                "bridge_cache_root": "/tmp/algenta-hf-cache",
                "bridge_auth_env_vars": ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
                "bridge_auth_configured": True,
                "bridge_tokenizer_backends": ["tiktoken", "sentencepiece"],
                "bridge_artifact_backends": ["safetensors", "huggingface_hub"],
                "available": True,
            }
        ],
    }

def _make_decision_plan_payload() -> dict[str, object]:
    return {
        "recommended_action": "Expand sales coverage",
        "confidence": 0.82,
        "expected_value": 128_000.0,
        "risk": {
            "p5": -15_000.0,
            "p95": 240_000.0,
            "probability_of_loss": 0.18,
            "var_95": -15_000.0,
        },
        "options": [
            {
                "name": "Expand sales coverage",
                "rank": 1,
                "expected_value": 128_000.0,
                "risk": {
                    "p5": -15_000.0,
                    "p95": 240_000.0,
                    "probability_of_loss": 0.18,
                    "var_95": -15_000.0,
                },
                "score": 0.82,
            }
        ],
        "rationale": "Projected revenue upside outweighs downside risk.",
        "integrity": {"request_hash": "a" * 64, "result_hash": "b" * 64},
        "calibration": "6 outcomes | bias=-2.0% | hit_rate=83%",
    }

def _make_artifact_bridge_payload() -> dict[str, object]:
    return {
        "object": "artifact_bridge_resolution",
        "backend": "huggingface_hub",
        "artifact_backend": "safetensors",
        "repo_id": "org/model",
        "filename": "model.safetensors",
        "revision": "main",
        "local_files_only": True,
        "status": "not_cached",
        "cache_root": "/tmp/algenta-hf-cache",
        "auth_env_vars": ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
        "auth_configured": True,
        "auth_env_var_used": "HF_TOKEN",
        "resolved_path": None,
    }

def _make_decision_log_payload() -> dict[str, object]:
    return {
        "id": "decision_123",
        "org_id": "org_123",
        "run_id": "run_123",
        "context": "Launch planning",
        "chosen_action": "expand",
        "options_considered": ["expand", "hold"],
        "expected_value": 128_000.0,
        "confidence": 0.82,
        "rationale": "Projected upside outweighs downside risk.",
        "risk_p5": -15_000.0,
        "risk_p95": 240_000.0,
        "risk_pol": 0.18,
        "request_hash": "a" * 64,
        "result_hash": "b" * 64,
        "policy_snapshot_id": "policy-v1",
        "schema_snapshot_id": "schema-v1",
        "manifest_version": "runtime-manifest-v1",
        "actual_outcome": None,
        "outcome_delta": None,
        "outcome_notes": None,
        "outcome_recorded_at": None,
        "executed_at": None,
        "execution_status": None,
        "execution_webhook_url": None,
        "execution_response_code": None,
        "created_at": "2026-05-24T12:00:00Z",
        "updated_at": "2026-05-24T12:00:00Z",
    }

def _make_decision_list_payload() -> dict[str, object]:
    return {
        "decisions": [_make_decision_log_payload()],
        "total": 1,
        "page": 1,
        "limit": 20,
        "pages": 1,
        "page_size": 20,
    }

def _make_recorded_outcome_payload() -> dict[str, object]:
    payload = _make_decision_log_payload()
    payload.update(
        {
            "actual_outcome": 141_000.0,
            "outcome_delta": 13_000.0,
            "outcome_notes": "Launch outperformed baseline",
            "outcome_recorded_at": "2026-05-24T12:30:00Z",
            "updated_at": "2026-05-24T12:30:00Z",
        }
    )
    return payload

def _make_execution_receipt_payload() -> dict[str, object]:
    return {
        "decision_id": "decision_123",
        "webhook_url": "https://hooks.example.test/decision",
        "execution_status": "delivered",
        "response_code": 202,
        "executed_at": "2026-05-24T12:05:00Z",
        "policy_snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
        "schema_snapshot_id": "schema-v1",
        "manifest_version": "runtime-manifest-v1",
        "payload_summary": {
            "chosen_action": "expand",
            "expected_value": 128_000.0,
            "confidence": 0.82,
        },
        "safety_overridden": False,
    }

def _make_agent_run_payload(status: str, pending_action: str | None = None) -> dict[str, object]:
    return {
        "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        "status": status,
        "task": "Search the knowledge base",
        "output_format": "markdown",
        "approval_mode": "manual",
        "pending_action": pending_action,
        "selected_tool": "search",
        "result": {"summary": "Found 3 relevant documents"},
        "tools_available": ["search", "summarize"],
        "tools_used": ["search"],
        "steps": [
            {
                "step": 1,
                "action": "Planning execution for: Search the knowledge base",
                "status": "completed",
            },
            {
                "step": 2,
                "action": "Routing to search tool",
                "tool": "search",
                "result": "Found 3 relevant documents",
                "status": "completed",
            }
        ],
        "request_hash": "a" * 64,
        "decision_hash": "b" * 64,
        "policy_snapshot_id": "policy-v1",
        "schema_snapshot_id": "schema-v1",
        "manifest_version": "runtime-manifest-v1",
        "replayable": True,
        "artifact_refs": ["art_1"],
        "latest_checkpoint_id": "cp_2",
        "checkpoint_count": 2,
        "source_run_id": None,
        "source_checkpoint_id": None,
        "created_at": "2026-05-24T12:00:00Z",
        "updated_at": "2026-05-24T12:00:03Z",
        "latency_ms": 21.5,
    }

def _make_agent_run_events_payload() -> dict[str, object]:
    return {
        "object": "list",
        "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        "data": [
            {
                "event_id": "evt_1",
                "event_type": "run_created",
                "status": "paused",
                "message": "Run created and awaiting approval.",
                "created_at": "2026-05-24T12:00:00Z",
                "details": {"pending_action": "approve"},
            }
        ],
        "total_events": 1,
    }

def _make_agent_run_list_payload() -> dict[str, object]:
    return {
        "object": "list",
        "data": [_make_agent_run_payload("requires_approval", "approve")],
        "total": 1,
        "page": 1,
        "limit": 25,
        "pages": 1,
    }

def _make_agent_run_checkpoints_payload() -> dict[str, object]:
    return {
        "object": "list",
        "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        "data": [
            {
                "checkpoint_id": "cp_1",
                "checkpoint_index": 1,
                "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
                "parent_checkpoint_id": None,
                "status": "requires_approval",
                "event_start_index": 0,
                "event_end_index": 2,
                "request_hash": "a" * 64,
                "decision_hash": "b" * 64,
                "content_hash": "c" * 64,
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "manifest_version": "runtime-manifest-v1",
                "artifact_refs": ["art_1"],
                "created_at": "2026-05-24T12:00:02Z",
            },
            {
                "checkpoint_id": "cp_2",
                "checkpoint_index": 2,
                "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
                "parent_checkpoint_id": "cp_1",
                "status": "completed",
                "event_start_index": 3,
                "event_end_index": 5,
                "request_hash": "a" * 64,
                "decision_hash": "b" * 64,
                "content_hash": "d" * 64,
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "manifest_version": "runtime-manifest-v1",
                "artifact_refs": ["art_1", "art_2"],
                "created_at": "2026-05-24T12:00:03Z",
            },
        ],
        "total_checkpoints": 2,
    }

def _make_agent_run_mission_events_payload() -> dict[str, object]:
    return {
        "object": "list",
        "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        "data": [
            {
                "mission_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
                "thread_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
                "tenant_scope": "org_test",
                "workspace_scope": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
                "event_index": 0,
                "superstep": 1,
                "node_name": "agent_run_service",
                "event_type": "run_created",
                "event_message": "Agent run created.",
                "details_json": '{"approval_mode":"manual","start_paused":false}',
                "event_ts": "2026-05-24T12:00:00Z",
                "request_hash": "a" * 64,
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "manifest_version": "runtime-manifest-v1",
                "checkpoint_id": None,
                "artifact_refs": ["evt_1"],
                "failure_code": None,
                "latency_ms": None,
                "cost_usd_micros": None,
            }
        ],
        "total_events": 1,
    }

def _make_agent_run_mission_event_query_payload() -> dict[str, object]:
    event = _make_agent_run_mission_events_payload()["data"][0]
    return {
        "object": "list",
        "data": [{**event, "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb", "run_status": "completed"}],
        "total": 1,
        "page": 1,
        "limit": 25,
        "pages": 1,
    }

def _make_agent_run_checkpoint_query_payload() -> dict[str, object]:
    checkpoint = _make_agent_run_checkpoints_payload()["data"][1]
    return {
        "object": "list",
        "data": [{**checkpoint, "run_status": "completed"}],
        "total": 1,
        "page": 1,
        "limit": 25,
        "pages": 1,
    }

def _make_agent_run_telemetry_payload() -> dict[str, object]:
    return {
        "object": "list",
        "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        "data": [
            {
                "batch_id": "telemetry_1",
                "telemetry_kind": "agent_run_completion",
                "module_name": "agent_run_service",
                "tenant_scope": "org_test",
                "request_hash": "a" * 64,
                "started_at": "2026-05-24T12:00:00Z",
                "ended_at": "2026-05-24T12:00:03Z",
                "success_count": 1,
                "failure_count": 0,
                "latency_ms_p95": 21.5,
                "cost_usd_micros": 0,
            }
        ],
        "total_batches": 1,
    }

def _make_agent_run_telemetry_query_payload() -> dict[str, object]:
    batch = _make_agent_run_telemetry_payload()["data"][0]
    return {
        "object": "list",
        "data": [{**batch, "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb", "run_status": "completed"}],
        "total": 1,
        "page": 1,
        "limit": 25,
        "pages": 1,
    }

def _make_agent_run_replay_payload() -> dict[str, object]:
    return {
        "object": "agent_run_replay",
        "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        "checkpoint_id": "cp_2",
        "replay_status": "matched",
        "compared_event_count": 3,
        "checkpoint_count": 2,
        "request_hash": "a" * 64,
        "decision_hash": "b" * 64,
        "content_hash": "d" * 64,
        "policy_snapshot_id": "policy-v1",
        "schema_snapshot_id": "schema-v1",
        "manifest_version": "runtime-manifest-v1",
        "failure_code": None,
        "created_at": "2026-05-24T12:00:04Z",
    }

def _make_deployment_regions_payload() -> dict[str, object]:
    return {
        "providers": [
            {
                "id": "algenta_shared",
                "name": "Algenta Managed",
                "description": "Multi-tenant shared pool.",
                "icon": "🌐",
                "regions": [
                    {
                        "id": "algenta-shared",
                        "label": "Algenta Shared",
                        "location": "Global",
                    }
                ],
            }
        ]
    }

def _make_deployment_payload() -> dict[str, object]:
    return {
        "deployment_id": "dep_123",
        "org_id": "org_123",
        "provider": "algenta_shared",
        "region": "algenta-shared",
        "status": "requested",
        "endpoint_url": "https://example.test/runtime",
        "cost_usd_month": 12.5,
        "billable_cost_usd_month": 15.0,
        "billing_markup_pct": 20.0,
        "created_at": "2026-05-24T12:00:00Z",
        "provisioned_at": None,
        "error_message": None,
    }

def _make_deployment_delete_payload() -> dict[str, object]:
    return {"status": "deprovisioning", "deployment_id": "dep_123"}

def _make_deployment_cost_payload() -> dict[str, object]:
    return {
        "deployment_id": "dep_123",
        "provider": "algenta_shared",
        "region": "algenta-shared",
        "year": 2026,
        "month": 5,
        "cost_usd_month": 12.5,
        "billable_cost_usd_month": 15.0,
        "billing_markup_pct": 20.0,
        "last_updated": "2026-05-24T12:30:00Z",
    }

def _make_usage_payload() -> dict[str, object]:
    return {
        "org_id": "08f7453b-7a11-42d5-8b53-4700afbb7f58",
        "billing_period": "2026-05",
        "simulations_run": 120,
        "api_calls": 340,
        "quota_limit": 1000,
        "quota_used_pct": 12.0,
    }

def _make_api_key_info_payload() -> dict[str, object]:
    return {
        "id": "79fc2a0b-6402-4137-b637-b76ee5e745bf",
        "label": "Mission Runtime Key",
        "key_prefix": "de_live_abcd",
        "device_limit": 2,
        "status": "active",
        "created_at": "2026-05-24T12:00:00Z",
        "last_used_at": None,
        "expires_at": "2028-05-24T12:00:00Z",
    }

def _make_api_key_created_payload() -> dict[str, object]:
    return {
        "id": "79fc2a0b-6402-4137-b637-b76ee5e745bf",
        "label": "Mission Runtime Key",
        "key_prefix": "de_live_abcd",
        "device_limit": 2,
        "raw_key": "de_live_abcd_secret_value",
        "created_at": "2026-05-24T12:00:00Z",
        "expires_at": "2028-05-24T12:00:00Z",
    }

def _make_chat_stream_payloads() -> list[dict[str, object]]:
    return [
        {
            "id": "chatcmpl_stream_123",
            "object": "chat.completion.chunk",
            "model": "text.tokenizer",
            "provider_backend": None,
            "provider_model_id": None,
            "provider_attempts": [],
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        },
        {
            "id": "chatcmpl_stream_123",
            "object": "chat.completion.chunk",
            "model": "text.tokenizer",
            "provider_backend": None,
            "provider_model_id": None,
            "provider_attempts": [],
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "Deterministic utility response."},
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": "chatcmpl_stream_123",
            "object": "chat.completion.chunk",
            "model": "text.tokenizer",
            "provider_backend": None,
            "provider_model_id": None,
            "provider_attempts": [],
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        },
    ]

def _make_response_stream_payloads() -> list[dict[str, object]]:
    return [
        {
            "type": "response.created",
            "response": {
                "id": "resp_stream_123",
                "object": "response",
                "status": "in_progress",
                "model": "text.tokenizer",
                "provider_backend": None,
                "provider_model_id": None,
                "provider_attempts": [],
            },
        },
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {
                "id": "resp_stream_123_item_0",
                "object": "response.output",
                "index": 0,
                "provider_backend": None,
                "provider_model_id": None,
                "provider_attempts": [],
                "content": [
                    {
                        "type": "tokenization",
                        "text": "alpha beta",
                        "tokens": ["alpha", "beta"],
                        "token_count": 2,
                        "embedding": None,
                    }
                ],
            },
        },
        {
            "type": "response.completed",
            "response": {
                "id": "resp_stream_123",
                "object": "response",
                "status": "completed",
                "model": "text.tokenizer",
                "provider_backend": None,
                "provider_model_id": None,
                "provider_attempts": [],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        },
    ]

def _make_agent_run_stream_payloads() -> list[dict[str, object]]:
    return [
        {
            "type": "agent.run.event",
            "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
            "event": {
                "event_id": "evt_1",
                "event_type": "run_created",
                "status": "paused",
                "message": "Run created and awaiting approval.",
                "created_at": "2026-05-24T12:00:00Z",
                "details": {"pending_action": "approve"},
            },
        },
        {
            "type": "agent.run.completed",
            "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
            "status": "completed",
            "total_events": 1,
        },
    ]



__all__ = [
    "annotations",
    "importlib",
    "sys",
    "Path",
    "pytest",
    "ROOT",
    "ALGENTA_CORE",
    "PYTHON_SDK",
    "algenta",
    "Runtime",
    "AgentRunEventsOutput",
    "AgentRunCheckpointListResponseOutput",
    "AgentRunListOutput",
    "AgentRunMissionEventListResponseOutput",
    "AgentRunMissionEventsOutput",
    "AgentRunStreamEventOutput",
    "AgentRunTelemetryListOutput",
    "AgentRunTelemetryOutput",
    "AgentRunOutput",
    "APIKeyCreatedOutput",
    "APIKeyInfoOutput",
    "ChatCompletionsOutput",
    "ChatCompletionsStreamChunkOutput",
    "CountTokensOutput",
    "DecisionListOutput",
    "DecisionLogOutput",
    "DecisionPlanOutput",
    "DeploymentCostOutput",
    "DeploymentDeleteOutput",
    "DeploymentOutput",
    "DeploymentRegionsOutput",
    "EmbeddingSimilarityOutput",
    "EmbeddingsOutput",
    "ExecutionReceiptOutput",
    "LLMModelListOutput",
    "ArtifactBridgeResolveOutput",
    "ResponseStreamEventOutput",
    "ResponsesOutput",
    "RerankResponseOutput",
    "RuntimeConfigurationError",
    "RuntimeValidationError",
    "TokenizeOutput",
    "UsageOutput",
    "_make_model_list_payload",
    "_make_decision_plan_payload",
    "_make_artifact_bridge_payload",
    "_make_decision_log_payload",
    "_make_decision_list_payload",
    "_make_recorded_outcome_payload",
    "_make_execution_receipt_payload",
    "_make_agent_run_payload",
    "_make_agent_run_events_payload",
    "_make_agent_run_list_payload",
    "_make_agent_run_checkpoints_payload",
    "_make_agent_run_mission_events_payload",
    "_make_agent_run_mission_event_query_payload",
    "_make_agent_run_checkpoint_query_payload",
    "_make_agent_run_telemetry_payload",
    "_make_agent_run_telemetry_query_payload",
    "_make_agent_run_replay_payload",
    "_make_deployment_regions_payload",
    "_make_deployment_payload",
    "_make_deployment_delete_payload",
    "_make_deployment_cost_payload",
    "_make_usage_payload",
    "_make_api_key_info_payload",
    "_make_api_key_created_payload",
    "_make_chat_stream_payloads",
    "_make_response_stream_payloads",
    "_make_agent_run_stream_payloads",
]
