from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

pytestmark = pytest.mark.anyio

decision_engine = importlib.import_module("decision_engine")

AsyncDecisionEngineClient = decision_engine.AsyncDecisionEngineClient
DecisionEngineClient = decision_engine.DecisionEngineClient
AgentRunEventsResult = decision_engine.AgentRunEventsResult
AgentRunCheckpointListResponseResult = decision_engine.AgentRunCheckpointListResponseResult
AgentRunListResult = decision_engine.AgentRunListResult
AgentRunMissionEventListResponseResult = decision_engine.AgentRunMissionEventListResponseResult
AgentRunMissionEventsResult = decision_engine.AgentRunMissionEventsResult
AgentRunCheckpointsResult = decision_engine.AgentRunCheckpointsResult
AgentRunReplayResult = decision_engine.AgentRunReplayResult
AgentRunStreamEventResult = decision_engine.AgentRunStreamEventResult
AgentRunTelemetryListResult = decision_engine.AgentRunTelemetryListResult
AgentRunTelemetryResult = decision_engine.AgentRunTelemetryResult
AgentRunResult = decision_engine.AgentRunResult
APIKeyInfo = decision_engine.APIKeyInfo
ChatCompletionsResult = decision_engine.ChatCompletionsResult
ChatCompletionsStreamChunkResult = decision_engine.ChatCompletionsStreamChunkResult
CountTokensResult = decision_engine.CountTokensResult
DecisionListResult = decision_engine.DecisionListResult
DecisionLogResult = decision_engine.DecisionLogResult
DecisionPlanResult = decision_engine.DecisionPlanResult
DeploymentCostResult = decision_engine.DeploymentCostResult
DeploymentDeleteResult = decision_engine.DeploymentDeleteResult
DeploymentRegionsResult = decision_engine.DeploymentRegionsResult
DeploymentResult = decision_engine.DeploymentResult
EmbeddingSimilarityResult = decision_engine.EmbeddingSimilarityResult
EmbeddingsResult = decision_engine.EmbeddingsResult
ExecutionReceiptResult = decision_engine.ExecutionReceiptResult
LLMModelListResult = decision_engine.LLMModelListResult
ArtifactBridgeResolveResult = decision_engine.ArtifactBridgeResolveResult
MeResult = decision_engine.MeResult
ResponseStreamEventResult = decision_engine.ResponseStreamEventResult
ResponsesResult = decision_engine.ResponsesResult
RerankResponseResult = decision_engine.RerankResponseResult
TokenizeResult = decision_engine.TokenizeResult
UsageInfo = decision_engine.UsageInfo


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
    return {
        "status": "deprovisioning",
        "deployment_id": "dep_123",
    }


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


def _make_me_payload() -> dict[str, object]:
    return {
        "user": {
            "id": "user_123",
            "email": "owner@example.com",
            "name": "Mission Ops",
            "role": "owner",
            "email_verified": True,
            "created_at": "2026-05-24T12:00:00Z",
        },
        "org": {
            "id": "11890f4c-0f0d-4d99-97fb-4c74312f6285",
            "name": "Algenta Labs",
            "slug": "algenta-labs",
            "plan": "enterprise",
            "status": "active",
            "created_at": "2026-05-24T11:00:00Z",
        },
    }


def _make_usage_payload() -> dict[str, object]:
    return {
        "org_id": "11890f4c-0f0d-4d99-97fb-4c74312f6285",
        "billing_period": "2026-05",
        "simulations_run": 120,
        "api_calls": 340,
        "quota_limit": 1000,
        "quota_used_pct": 12.0,
    }


def _make_limits_payload() -> dict[str, object]:
    return {
        "plan": "enterprise",
        "simulations_per_month": "unlimited",
        "rate_limit_per_minute": 10000,
        "connectors": 64,
        "jobs_enabled": True,
    }


def _make_api_keys_payload() -> list[dict[str, object]]:
    return [
        {
            "id": "6b7a5f04-4031-44f4-91a5-fb3c8382f12a",
            "label": "Mission Runtime Key",
            "key_prefix": "de_live_abcd",
            "device_limit": 2,
            "status": "active",
            "created_at": "2026-05-24T12:00:00Z",
            "last_used_at": "2026-05-24T12:30:00Z",
            "expires_at": None,
        }
    ]


def _make_created_api_key_payload() -> dict[str, object]:
    return {
        "id": "79fc2a0b-6402-4137-b637-b76ee5e745bf",
        "label": "Mission Rotation Key",
        "key_prefix": "de_live_wxyz",
        "device_limit": 3,
        "raw_key": "de_live_wxyz_secret_value",
        "created_at": "2026-05-24T12:00:00Z",
        "expires_at": None,
    }


def _make_chat_stream_lines() -> list[str]:
    return [
        'data: {"id":"chatcmpl_stream_123","object":"chat.completion.chunk","model":"text.tokenizer","provider_backend":null,"provider_model_id":null,"choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_stream_123","object":"chat.completion.chunk","model":"text.tokenizer","provider_backend":null,"provider_model_id":null,"choices":[{"index":0,"delta":{"content":"Deterministic utility response."},"finish_reason":null}]}',
        "",
        'data: {"id":"chatcmpl_stream_123","object":"chat.completion.chunk","model":"text.tokenizer","provider_backend":null,"provider_model_id":null,"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
        "",
        "data: [DONE]",
        "",
    ]


def _make_response_stream_lines() -> list[str]:
    return [
        'data: {"type":"response.created","response":{"id":"resp_stream_123","object":"response","status":"in_progress","model":"text.tokenizer","provider_backend":null,"provider_model_id":null}}',
        "",
        'data: {"type":"response.output_item.done","output_index":0,"item":{"id":"resp_stream_123_item_0","object":"response.output","index":0,"provider_backend":null,"provider_model_id":null,"content":[{"type":"tokenization","text":"alpha beta","tokens":["alpha","beta"],"token_count":2,"embedding":null}]}}',
        "",
        'data: {"type":"response.completed","response":{"id":"resp_stream_123","object":"response","status":"completed","model":"text.tokenizer","provider_backend":null,"provider_model_id":null,"usage":{"prompt_tokens":2,"total_tokens":2}}}',
        "",
        "data: [DONE]",
        "",
    ]


def _make_agent_run_stream_lines() -> list[str]:
    return [
        'data: {"type":"agent.run.event","run_id":"8e3c9e2c-b67d-42da-b456-1de39d7289fb","event":{"event_id":"evt_1","event_type":"run_created","status":"paused","message":"Run created and awaiting approval.","created_at":"2026-05-24T12:00:00Z","details":{"pending_action":"approve"}}}',
        "",
        'data: {"type":"agent.run.completed","run_id":"8e3c9e2c-b67d-42da-b456-1de39d7289fb","status":"completed","total_events":1}',
        "",
        "data: [DONE]",
        "",
    ]


class _FakeSyncStreamResponse:
    def __init__(self, lines: list[str], *, content_type: str = "text/event-stream") -> None:
        self.status_code = 200
        self.headers = {"content-type": content_type}
        self._lines = lines

    def iter_lines(self):
        yield from self._lines


class _FakeSyncStreamContext:
    def __init__(self, response: _FakeSyncStreamResponse) -> None:
        self._response = response

    def __enter__(self) -> _FakeSyncStreamResponse:
        return self._response

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeAsyncStreamResponse:
    def __init__(self, lines: list[str], *, content_type: str = "text/event-stream") -> None:
        self.status_code = 200
        self.headers = {"content-type": content_type}
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeAsyncStreamContext:
    def __init__(self, response: _FakeAsyncStreamResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeAsyncStreamResponse:
        return self._response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _fake_payload_for_path(path: str) -> dict[str, object]:
    payloads: dict[str, dict[str, object]] = {
        "/v1/models": _make_model_list_payload(),
        "/v1/artifacts/resolve": _make_artifact_bridge_payload(),
        "/v1/tokenize": {
            "object": "tokenization",
            "model": "text.tokenizer",
            "tokenizer_kind": "wordpiece",
            "tokens": ["expand", "sales", "coverage"],
            "token_count": 3,
        },
        "/v1/count_tokens": {
            "object": "token_count",
            "model": "text.tokenizer",
            "tokenizer_kind": "wordpiece",
            "token_count": 3,
        },
        "/v1/chat/completions": {
            "id": "chatcmpl_123",
            "object": "chat.completion",
            "model": "text.tokenizer",
            "provider_backend": None,
            "provider_model_id": None,
            "provider_attempts": [],
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Deterministic utility response."},
                }
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
        },
        "/v1/responses": {
            "id": "resp_123",
            "object": "response",
            "status": "completed",
            "model": "provider.gpt-4o-mini",
            "provider_backend": "openai_compatible",
            "provider_model_id": "provider.gpt-4o-mini",
            "provider_attempts": [
                {
                    "provider_backend": "groq",
                    "provider_model_id": "provider.fast",
                    "outcome": "failed",
                    "error_code": "provider_backend_error",
                },
                {
                    "provider_backend": "openai_compatible",
                    "provider_model_id": "provider.gpt-4o-mini",
                    "outcome": "selected",
                    "error_code": None,
                },
            ],
            "output": [
                {
                    "id": "out_1",
                    "object": "response.output",
                    "index": 0,
                    "provider_backend": "openai_compatible",
                    "provider_model_id": "provider.gpt-4o-mini",
                    "provider_attempts": [
                        {
                            "provider_backend": "groq",
                            "provider_model_id": "provider.fast",
                            "outcome": "failed",
                            "error_code": "provider_backend_error",
                        },
                        {
                            "provider_backend": "openai_compatible",
                            "provider_model_id": "provider.gpt-4o-mini",
                            "outcome": "selected",
                            "error_code": None,
                        },
                    ],
                    "content": [
                        {
                            "type": "text",
                            "text": "expand sales coverage",
                            "token_count": 3,
                            "embedding": None,
                        }
                    ],
                }
            ],
            "usage": {"prompt_tokens": 7, "total_tokens": 7},
        },
        "/v1/embeddings": {
            "object": "list",
            "model": "text.hash_embedding_v1",
            "dimensions": 3,
            "provider_backend": None,
            "provider_model_id": None,
            "provider_attempts": [],
            "data": [
                {
                    "object": "embedding",
                    "index": 0,
                    "embedding": [0.1, 0.2, 0.3],
                    "token_count": 3,
                }
            ],
            "usage": {"prompt_tokens": 3, "total_tokens": 3},
        },
        "/v1/embeddings/similarity": {
            "object": "embedding_similarity",
            "model": "embeddings.cosine_similarity",
            "similarity_metric": "cosine",
            "score": 0.94,
            "dimension": 3,
        },
        "/v1/rerank": {
            "object": "list",
            "model": "embeddings.cosine_similarity",
            "similarity_metric": "cosine",
            "total_documents": 2,
            "returned_documents": 1,
            "data": [
                {
                    "object": "rerank_result",
                    "id": "doc-1",
                    "index": 0,
                    "rank": 1,
                    "score": 0.94,
                    "text": "Top document",
                    "metadata": {"source": "kb"},
                }
            ],
        },
        "/v1/decisions/plan": _make_decision_plan_payload(),
        "/v1/decisions": _make_decision_log_payload(),
        "/v1/decisions/decision_123": _make_decision_log_payload(),
        "/v1/decisions/decision_123/outcome": _make_recorded_outcome_payload(),
        "/v1/decisions/decision_123/execute": _make_execution_receipt_payload(),
        "/v1/agent/runs": _make_agent_run_payload("requires_approval", "approve"),
        "/v1/agent/runs?page=1&limit=25&status=requires_approval&request_hash=None&policy_snapshot_id=None&schema_snapshot_id=None": (
            _make_agent_run_list_payload()
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb": _make_agent_run_payload(
            "requires_approval",
            "approve",
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/events?limit=25": (
            _make_agent_run_events_payload()
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/mission-events?limit=25": (
            _make_agent_run_mission_events_payload()
        ),
        "/v1/agent/runs/mission-events?page=1&limit=25&status=completed&request_hash="
        + ("a" * 64)
        + "&policy_snapshot_id=policy-v1&schema_snapshot_id=schema-v1"
        + "&run_id=8e3c9e2c-b67d-42da-b456-1de39d7289fb&event_type=run_created": (
            _make_agent_run_mission_event_query_payload()
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/checkpoints": (
            _make_agent_run_checkpoints_payload()
        ),
        "/v1/agent/runs/checkpoints?page=1&limit=25&status=completed&request_hash="
        + ("a" * 64)
        + "&policy_snapshot_id=policy-v1&schema_snapshot_id=schema-v1"
        + "&run_id=8e3c9e2c-b67d-42da-b456-1de39d7289fb&checkpoint_id=cp_2": (
            _make_agent_run_checkpoint_query_payload()
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/telemetry?limit=25": (
            _make_agent_run_telemetry_payload()
        ),
        "/v1/agent/runs/telemetry?page=1&limit=25&status=completed&request_hash="
        + ("a" * 64)
        + "&policy_snapshot_id=policy-v1&schema_snapshot_id=schema-v1"
        + "&run_id=8e3c9e2c-b67d-42da-b456-1de39d7289fb"
        + "&telemetry_kind=agent_run_completion&module_name=agent_run_service": (
            _make_agent_run_telemetry_query_payload()
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/replay": (
            _make_agent_run_replay_payload()
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/fork": _make_agent_run_payload(
            "paused",
            "resume",
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/resume": _make_agent_run_payload(
            "requires_approval",
            "approve",
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/cancel": _make_agent_run_payload(
            "cancelled",
            None,
        ),
        "/v1/agent/runs/8e3c9e2c-b67d-42da-b456-1de39d7289fb/approve": _make_agent_run_payload(
            "completed",
            None,
        ),
        "/v1/deployments/regions": _make_deployment_regions_payload(),
        "/v1/deployments": _make_deployment_payload(),
        "/v1/deployments/dep_123": _make_deployment_delete_payload(),
        "/v1/deployments/dep_123/cost": _make_deployment_cost_payload(),
    }
    return payloads[path]


def test_decision_engine_sync_llm_and_agent_methods_return_typed_models(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    seen: list[tuple[str, str, dict[str, object]]] = []

    def _fake_request(method: str, path: str, **kwargs):
        seen.append((method, path, kwargs))
        if method == "GET" and path == "/v1/decisions":
            return _make_decision_list_payload()
        if method == "DELETE" and path == "/v1/decisions/decision_123":
            return {}
        return _fake_payload_for_path(path)

    monkeypatch.setattr(client, "_request", _fake_request)

    models = client.list_models()
    tokenized = client.tokenize("expand sales coverage")
    counted = client.count_tokens("expand sales coverage")
    bridge = client.resolve_artifact_bridge(
        repo_id="org/model",
        filename="model.safetensors",
        revision="main",
    )
    chat = client.chat_completions([{"role": "user", "content": "Summarize"}])
    response = client.responses(["expand sales coverage"], model="provider.gpt-4o-mini")
    embeddings = client.embeddings("expand sales coverage", dimensions=3)
    similarity = client.embedding_similarity([0.1, 0.2, 0.3], [0.1, 0.2, 0.3])
    reranked = client.rerank(
        [0.1, 0.2, 0.3],
        [{"id": "doc-1", "embedding": [0.1, 0.2, 0.3], "text": "Top document"}],
        top_n=1,
    )
    deployment_regions = client.list_deployment_regions()
    deployment = client.get_deployment()
    created_deployment = client.create_deployment()
    deployment_cost = client.get_deployment_cost("dep_123")
    deleted_deployment = client.delete_deployment("dep_123")
    plan = client.plan_decision({"mode": "auto", "scenario": {"variables": {}, "objective": "maximize_score"}})
    logged_decision = client.log_decision(
        {"chosen_action": "expand", "context": "Launch planning", "expected_value": 128000.0}
    )
    listed_decisions = client.list_decisions(page=1, limit=20, with_outcome_only=True)
    decision_detail = client.get_decision("decision_123")
    recorded_outcome = client.record_outcome(
        "decision_123",
        actual_outcome=141000.0,
        outcome_notes="Launch outperformed baseline",
    )
    execution_receipt = client.execute_decision(
        "decision_123",
        webhook_url="https://hooks.example.test/decision",
    )
    deleted_decision = client.delete_decision("decision_123")
    run = client.create_agent_run(
        task="Search the knowledge base",
        approval_mode="manual",
        output_format="markdown",
    )
    run_list = client.list_agent_runs(status="requires_approval")
    run_detail = client.get_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    events = client.get_agent_run_events("8e3c9e2c-b67d-42da-b456-1de39d7289fb", limit=25)
    checkpoints = client.list_agent_run_checkpoints("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    checkpoint_query = client.query_agent_run_checkpoints(
        status="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        checkpoint_id="cp_2",
    )
    mission_events = client.list_agent_run_mission_events(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        limit=25,
    )
    mission_event_query = client.query_agent_run_mission_events(
        status="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        event_type="run_created",
    )
    telemetry = client.list_agent_run_telemetry(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        limit=25,
    )
    telemetry_query = client.query_agent_run_telemetry(
        status="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        telemetry_kind="agent_run_completion",
        module_name="agent_run_service",
    )
    replay = client.replay_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    forked = client.fork_agent_run(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        checkpoint_id="cp_1",
    )
    resumed = client.resume_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    cancelled = client.cancel_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    approved = client.approve_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")

    assert isinstance(models, LLMModelListResult)
    assert isinstance(tokenized, TokenizeResult)
    assert isinstance(counted, CountTokensResult)
    assert isinstance(bridge, ArtifactBridgeResolveResult)
    assert isinstance(chat, ChatCompletionsResult)
    assert isinstance(response, ResponsesResult)
    assert isinstance(embeddings, EmbeddingsResult)
    assert isinstance(similarity, EmbeddingSimilarityResult)
    assert isinstance(reranked, RerankResponseResult)
    assert isinstance(deployment_regions, DeploymentRegionsResult)
    assert isinstance(deployment, DeploymentResult)
    assert isinstance(created_deployment, DeploymentResult)
    assert isinstance(deployment_cost, DeploymentCostResult)
    assert isinstance(deleted_deployment, DeploymentDeleteResult)
    assert isinstance(plan, DecisionPlanResult)
    assert isinstance(logged_decision, DecisionLogResult)
    assert isinstance(listed_decisions, DecisionListResult)
    assert isinstance(decision_detail, DecisionLogResult)
    assert isinstance(recorded_outcome, DecisionLogResult)
    assert isinstance(execution_receipt, ExecutionReceiptResult)
    assert isinstance(run, AgentRunResult)
    assert isinstance(run_list, AgentRunListResult)
    assert isinstance(run_detail, AgentRunResult)
    assert isinstance(events, AgentRunEventsResult)
    assert isinstance(checkpoints, AgentRunCheckpointsResult)
    assert isinstance(checkpoint_query, AgentRunCheckpointListResponseResult)
    assert isinstance(mission_events, AgentRunMissionEventsResult)
    assert isinstance(mission_event_query, AgentRunMissionEventListResponseResult)
    assert isinstance(telemetry, AgentRunTelemetryResult)
    assert isinstance(telemetry_query, AgentRunTelemetryListResult)
    assert isinstance(replay, AgentRunReplayResult)
    assert isinstance(forked, AgentRunResult)
    assert isinstance(resumed, AgentRunResult)
    assert isinstance(cancelled, AgentRunResult)
    assert isinstance(approved, AgentRunResult)
    assert models.data[0].id == "text.tokenizer"
    assert tokenized.token_count == 3
    assert counted.token_count == 3
    assert bridge.status == "not_cached"
    assert bridge.auth_env_var_used == "HF_TOKEN"
    assert chat.choices[0].message.content == "Deterministic utility response."
    assert chat.provider_backend is None
    assert chat.provider_model_id is None
    assert chat.provider_attempts == []
    assert response.provider_backend == "openai_compatible"
    assert response.provider_model_id == "provider.gpt-4o-mini"
    assert response.provider_attempts[0].provider_backend == "groq"
    assert response.provider_attempts[1].outcome == "selected"
    assert response.output[0].provider_backend == "openai_compatible"
    assert response.output[0].provider_model_id == "provider.gpt-4o-mini"
    assert response.output[0].provider_attempts[1].provider_model_id == "provider.gpt-4o-mini"
    assert response.output[0].content[0].type == "text"
    assert response.output[0].content[0].embedding is None
    assert embeddings.data[0].embedding == [0.1, 0.2, 0.3]
    assert embeddings.provider_backend is None
    assert embeddings.provider_model_id is None
    assert embeddings.provider_attempts == []
    assert similarity.score == 0.94
    assert reranked.data[0].rank == 1
    assert deployment_regions.providers[0].regions[0].id == "algenta-shared"
    assert deployment_regions.providers[0].regions[0].name == "Algenta Shared"
    assert deployment.deployment_id == "dep_123"
    assert created_deployment.status == "requested"
    assert deployment_cost.month == 5
    assert deleted_deployment.status == "deprovisioning"
    assert plan.options[0].rank == 1
    assert logged_decision.chosen_action == "expand"
    assert logged_decision.policy_snapshot_id == "policy-v1"
    assert listed_decisions.decisions[0].id == "decision_123"
    assert listed_decisions.decisions[0].schema_snapshot_id == "schema-v1"
    assert decision_detail.context == "Launch planning"
    assert decision_detail.manifest_version == "runtime-manifest-v1"
    assert recorded_outcome.outcome_delta == 13_000.0
    assert execution_receipt.execution_status == "delivered"
    assert run_list.data[0].run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
    assert run_list.total == 1
    assert execution_receipt.policy_snapshot_id == "execution-policy-v1-r2:abcd1234abcd1234"
    assert execution_receipt.schema_snapshot_id == "schema-v1"
    assert execution_receipt.manifest_version == "runtime-manifest-v1"
    assert deleted_decision == {}
    assert run.pending_action == "approve"
    assert run.latest_checkpoint_id == "cp_2"
    assert run.steps[0].action == "Planning execution for: Search the knowledge base"
    assert run.steps[1].tool_name == "search"
    assert events.total_events == 1
    assert checkpoints.total_checkpoints == 2
    assert checkpoint_query.total == 1
    assert checkpoint_query.data[0].run_status == "completed"
    assert checkpoint_query.data[0].checkpoint_id == "cp_2"
    assert mission_events.total_events == 1
    assert mission_events.data[0].event_message == "Agent run created."
    assert mission_event_query.total == 1
    assert mission_event_query.data[0].run_status == "completed"
    assert telemetry.total_batches == 1
    assert telemetry.data[0].telemetry_kind == "agent_run_completion"
    assert telemetry_query.total == 1
    assert telemetry_query.data[0].module_name == "agent_run_service"
    assert replay.replay_status == "matched"
    assert forked.pending_action == "resume"
    assert cancelled.status == "cancelled"
    assert approved.status == "completed"
    assert models.data[0].routing_targets == []
    assert models.data[0].resolved_routing_targets == []
    assert models.data[0].chat_routing_targets == []
    assert models.data[0].resolved_chat_routing_targets == []
    assert models.data[0].embedding_routing_targets == []
    assert models.data[0].resolved_embedding_routing_targets == []
    assert models.data[0].required_provider_headers == []
    assert models.data[0].provider_auth_env_vars == []
    assert models.data[0].provider_auth_configured is False
    assert models.data[0].routing_fallback_policy is None
    assert models.data[0].chat_routing_fallback_policy is None
    assert models.data[0].embedding_routing_fallback_policy is None
    assert models.data[0].routing_fallback_on == []
    assert models.data[0].chat_routing_fallback_on == []
    assert models.data[0].embedding_routing_fallback_on == []
    assert models.data[0].routing_max_attempts is None
    assert models.data[0].chat_routing_max_attempts is None
    assert models.data[0].embedding_routing_max_attempts is None
    assert models.data[0].timeout_seconds is None
    assert models.data[0].chat_timeout_seconds is None
    assert models.data[0].embedding_timeout_seconds is None
    assert models.data[0].bridge_cache_root == "/tmp/algenta-hf-cache"
    assert models.data[0].bridge_auth_env_vars == ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"]
    assert models.data[0].bridge_auth_configured is True
    assert models.data[0].bridge_tokenizer_backends == ["tiktoken", "sentencepiece"]
    assert models.data[0].bridge_artifact_backends == ["safetensors", "huggingface_hub"]
    assert seen[0] == ("GET", "/v1/models", {})
    assert any(path.endswith("/events?limit=25") for _, path, _ in seen)


def test_decision_engine_sync_account_methods_return_typed_models(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    seen: list[tuple[str, str, dict[str, object]]] = []

    def _fake_request(method: str, path: str, **kwargs):
        seen.append((method, path, kwargs))
        if (method, path) == ("GET", "/v1/me"):
            return _make_me_payload()
        if (method, path) == ("GET", "/v1/usage"):
            return _make_usage_payload()
        if (method, path) == ("GET", "/v1/limits"):
            return _make_limits_payload()
        if (method, path) == ("GET", "/v1/api-keys"):
            return _make_api_keys_payload()
        if (method, path) == ("POST", "/v1/api-keys"):
            return _make_created_api_key_payload()
        if (method, path) == ("DELETE", "/v1/api-keys/79fc2a0b-6402-4137-b637-b76ee5e745bf"):
            return {}
        raise AssertionError(f"unexpected request {(method, path)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    me = client.me()
    usage = client.usage()
    limits = client.limits()
    api_keys = client.list_api_keys()
    created = client.create_api_key(name="Mission Rotation Key", device_limit=3)
    revoked = client.revoke_api_key("79fc2a0b-6402-4137-b637-b76ee5e745bf")

    assert isinstance(me, MeResult)
    assert me.user.email == "owner@example.com"
    assert me.org.plan == "enterprise"
    assert isinstance(usage, UsageInfo)
    assert usage.billing_period == "2026-05"
    assert usage.simulations_run == 120
    assert limits["plan"] == "enterprise"
    assert len(api_keys) == 1
    assert isinstance(api_keys[0], APIKeyInfo)
    assert api_keys[0].label == "Mission Runtime Key"
    assert created["raw_key"] == "de_live_wxyz_secret_value"
    assert revoked == {}
    assert seen == [
        ("GET", "/v1/me", {}),
        ("GET", "/v1/usage", {}),
        ("GET", "/v1/limits", {}),
        ("GET", "/v1/api-keys", {}),
        ("POST", "/v1/api-keys", {"json": {"label": "Mission Rotation Key", "device_limit": 3}}),
        ("DELETE", "/v1/api-keys/79fc2a0b-6402-4137-b637-b76ee5e745bf", {}),
    ]


async def test_decision_engine_async_llm_and_agent_methods_return_typed_models(monkeypatch) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    async def _fake_request(method: str, path: str, **kwargs):
        if method == "GET" and path == "/v1/decisions":
            return _make_decision_list_payload()
        if method == "DELETE" and path == "/v1/decisions/decision_123":
            return {}
        return _fake_payload_for_path(path)

    monkeypatch.setattr(client, "_request", _fake_request)

    models = await client.list_models()
    bridge = await client.resolve_artifact_bridge(
        repo_id="org/model",
        filename="model.safetensors",
        revision="main",
    )
    deployment_regions = await client.list_deployment_regions()
    deployment = await client.get_deployment()
    created_deployment = await client.create_deployment()
    deployment_cost = await client.get_deployment_cost("dep_123")
    deleted_deployment = await client.delete_deployment("dep_123")
    plan = await client.plan_decision(
        {"mode": "auto", "scenario": {"variables": {}, "objective": "maximize_score"}}
    )
    logged_decision = await client.log_decision(
        {"chosen_action": "expand", "context": "Launch planning", "expected_value": 128000.0}
    )
    listed_decisions = await client.list_decisions(page=1, limit=20, with_outcome_only=True)
    decision_detail = await client.get_decision("decision_123")
    recorded_outcome = await client.record_outcome(
        "decision_123",
        actual_outcome=141000.0,
        outcome_notes="Launch outperformed baseline",
    )
    execution_receipt = await client.execute_decision(
        "decision_123",
        webhook_url="https://hooks.example.test/decision",
    )
    deleted_decision = await client.delete_decision("decision_123")
    embeddings = await client.embeddings(["expand sales coverage"], dimensions=3)
    run = await client.create_agent_run(task="Search the knowledge base", approval_mode="manual")
    run_list = await client.list_agent_runs(status="requires_approval")
    events = await client.get_agent_run_events(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        limit=25,
    )
    checkpoints = await client.list_agent_run_checkpoints("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    checkpoint_query = await client.query_agent_run_checkpoints(
        status="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        checkpoint_id="cp_2",
    )
    mission_events = await client.list_agent_run_mission_events(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        limit=25,
    )
    mission_event_query = await client.query_agent_run_mission_events(
        status="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        event_type="run_created",
    )
    telemetry = await client.list_agent_run_telemetry(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        limit=25,
    )
    telemetry_query = await client.query_agent_run_telemetry(
        status="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        telemetry_kind="agent_run_completion",
        module_name="agent_run_service",
    )
    replay = await client.replay_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    forked = await client.fork_agent_run(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        checkpoint_id="cp_1",
    )
    approved = await client.approve_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")

    assert isinstance(models, LLMModelListResult)
    assert isinstance(bridge, ArtifactBridgeResolveResult)
    assert isinstance(deployment_regions, DeploymentRegionsResult)
    assert isinstance(deployment, DeploymentResult)
    assert isinstance(created_deployment, DeploymentResult)
    assert isinstance(deployment_cost, DeploymentCostResult)
    assert isinstance(deleted_deployment, DeploymentDeleteResult)
    assert isinstance(plan, DecisionPlanResult)
    assert isinstance(logged_decision, DecisionLogResult)
    assert isinstance(listed_decisions, DecisionListResult)
    assert isinstance(decision_detail, DecisionLogResult)
    assert isinstance(recorded_outcome, DecisionLogResult)
    assert isinstance(execution_receipt, ExecutionReceiptResult)
    assert isinstance(run_list, AgentRunListResult)
    assert isinstance(embeddings, EmbeddingsResult)
    assert isinstance(run, AgentRunResult)
    assert run_list.data[0].status == "requires_approval"
    assert isinstance(events, AgentRunEventsResult)
    assert isinstance(checkpoints, AgentRunCheckpointsResult)
    assert isinstance(checkpoint_query, AgentRunCheckpointListResponseResult)
    assert isinstance(replay, AgentRunReplayResult)
    assert isinstance(forked, AgentRunResult)
    assert isinstance(approved, AgentRunResult)
    assert plan.recommended_action == "Expand sales coverage"
    assert deployment_regions.providers[0].id == "algenta_shared"
    assert deployment.deployment_id == "dep_123"
    assert created_deployment.provider == "algenta_shared"
    assert deployment_cost.deployment_id == "dep_123"
    assert deleted_deployment.deployment_id == "dep_123"
    assert logged_decision.id == "decision_123"
    assert logged_decision.policy_snapshot_id == "policy-v1"
    assert listed_decisions.total == 1
    assert listed_decisions.decisions[0].schema_snapshot_id == "schema-v1"
    assert decision_detail.chosen_action == "expand"
    assert decision_detail.manifest_version == "runtime-manifest-v1"
    assert recorded_outcome.outcome_delta == 13_000.0
    assert execution_receipt.response_code == 202
    assert execution_receipt.schema_snapshot_id == "schema-v1"
    assert execution_receipt.manifest_version == "runtime-manifest-v1"
    assert deleted_decision == {}
    assert embeddings.dimensions == 3
    assert run.status == "requires_approval"
    assert events.data[0].event_type == "run_created"
    assert checkpoints.total_checkpoints == 2
    assert checkpoint_query.total == 1
    assert checkpoint_query.data[0].run_status == "completed"
    assert checkpoint_query.data[0].checkpoint_id == "cp_2"
    assert mission_events.total_events == 1
    assert mission_event_query.total == 1
    assert mission_event_query.data[0].run_status == "completed"
    assert telemetry.total_batches == 1
    assert telemetry_query.total == 1
    assert telemetry_query.data[0].module_name == "agent_run_service"
    assert replay.replay_status == "matched"
    assert forked.pending_action == "resume"
    assert approved.status == "completed"
    assert bridge.status == "not_cached"
    assert bridge.filename == "model.safetensors"

    await client.aclose()


async def test_decision_engine_async_account_methods_return_typed_models(monkeypatch) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    seen: list[tuple[str, str, dict[str, object]]] = []

    async def _fake_request(method: str, path: str, **kwargs):
        seen.append((method, path, kwargs))
        if (method, path) == ("GET", "/v1/me"):
            return _make_me_payload()
        if (method, path) == ("GET", "/v1/usage"):
            return _make_usage_payload()
        if (method, path) == ("GET", "/v1/limits"):
            return _make_limits_payload()
        if (method, path) == ("GET", "/v1/api-keys"):
            return _make_api_keys_payload()
        if (method, path) == ("POST", "/v1/api-keys"):
            return _make_created_api_key_payload()
        if (method, path) == ("DELETE", "/v1/api-keys/79fc2a0b-6402-4137-b637-b76ee5e745bf"):
            return {}
        raise AssertionError(f"unexpected request {(method, path)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    me = await client.me()
    usage = await client.usage()
    limits = await client.limits()
    api_keys = await client.list_api_keys()
    created = await client.create_api_key(name="Mission Rotation Key", device_limit=3)
    revoked = await client.revoke_api_key("79fc2a0b-6402-4137-b637-b76ee5e745bf")

    assert isinstance(me, MeResult)
    assert me.org.name == "Algenta Labs"
    assert isinstance(usage, UsageInfo)
    assert usage.api_calls == 340
    assert limits["jobs_enabled"] is True
    assert len(api_keys) == 1
    assert isinstance(api_keys[0], APIKeyInfo)
    assert api_keys[0].key_prefix == "de_live_abcd"
    assert created["label"] == "Mission Rotation Key"
    assert revoked == {}
    assert seen == [
        ("GET", "/v1/me", {}),
        ("GET", "/v1/usage", {}),
        ("GET", "/v1/limits", {}),
        ("GET", "/v1/api-keys", {}),
        ("POST", "/v1/api-keys", {"json": {"label": "Mission Rotation Key", "device_limit": 3}}),
        ("DELETE", "/v1/api-keys/79fc2a0b-6402-4137-b637-b76ee5e745bf", {}),
    ]

    await client.aclose()


def test_decision_engine_sync_stream_methods_parse_typed_sse_events(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    seen: list[tuple[str, str, dict[str, object]]] = []

    def _fake_stream(method: str, path: str, **kwargs):
        seen.append((method, path, kwargs))
        if path == "/v1/chat/completions":
            return _FakeSyncStreamContext(_FakeSyncStreamResponse(_make_chat_stream_lines()))
        if path == "/v1/responses":
            return _FakeSyncStreamContext(_FakeSyncStreamResponse(_make_response_stream_lines()))
        if path.endswith("/events?limit=25&stream=true"):
            return _FakeSyncStreamContext(_FakeSyncStreamResponse(_make_agent_run_stream_lines()))
        raise AssertionError(f"unexpected stream path: {path}")

    monkeypatch.setattr(client, "_store_device_binding_token", lambda response: None)
    monkeypatch.setattr(client, "_client", SimpleNamespace(stream=_fake_stream))

    chat_chunks = list(client.stream_chat_completions([{"role": "user", "content": "alpha beta"}]))
    response_events = list(client.stream_responses("alpha beta"))
    run_events = list(
        client.stream_agent_run_events("8e3c9e2c-b67d-42da-b456-1de39d7289fb", limit=25)
    )

    assert all(isinstance(item, ChatCompletionsStreamChunkResult) for item in chat_chunks)
    assert chat_chunks[0].choices[0].delta.role == "assistant"
    assert chat_chunks[1].choices[0].delta.content == "Deterministic utility response."
    assert chat_chunks[2].choices[0].finish_reason == "stop"
    assert chat_chunks[0].provider_backend is None
    assert chat_chunks[0].provider_model_id is None

    assert all(isinstance(item, ResponseStreamEventResult) for item in response_events)
    assert response_events[0].type == "response.created"
    assert response_events[0].response is not None
    assert response_events[0].response.provider_backend is None
    assert response_events[0].response.provider_model_id is None
    assert response_events[1].item is not None
    assert response_events[1].item.provider_backend is None
    assert response_events[1].item.provider_model_id is None
    assert response_events[1].item.content[0].tokens == ["alpha", "beta"]
    assert response_events[2].response is not None
    assert response_events[2].response.status == "completed"

    assert all(isinstance(item, AgentRunStreamEventResult) for item in run_events)
    assert run_events[0].event is not None
    assert run_events[0].event.event_type == "run_created"
    assert run_events[1].status == "completed"
    assert run_events[1].total_events == 1

    assert seen[0][2]["json"]["stream"] is True
    assert seen[1][2]["json"]["stream"] is True
    assert seen[2][1].endswith("/events?limit=25&stream=true")


async def test_decision_engine_async_stream_methods_parse_typed_sse_events(monkeypatch) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    seen: list[tuple[str, str, dict[str, object]]] = []

    def _fake_stream(method: str, path: str, **kwargs):
        seen.append((method, path, kwargs))
        if path == "/v1/chat/completions":
            return _FakeAsyncStreamContext(_FakeAsyncStreamResponse(_make_chat_stream_lines()))
        if path == "/v1/responses":
            return _FakeAsyncStreamContext(_FakeAsyncStreamResponse(_make_response_stream_lines()))
        if path.endswith("/events?limit=25&stream=true"):
            return _FakeAsyncStreamContext(_FakeAsyncStreamResponse(_make_agent_run_stream_lines()))
        raise AssertionError(f"unexpected stream path: {path}")

    monkeypatch.setattr(client, "_store_device_binding_token", lambda response: None)
    monkeypatch.setattr(client, "_client", SimpleNamespace(stream=_fake_stream, aclose=lambda: None))

    chat_chunks = [item async for item in client.stream_chat_completions([{"role": "user", "content": "alpha beta"}])]
    response_events = [item async for item in client.stream_responses("alpha beta")]
    run_events = [
        item
        async for item in client.stream_agent_run_events(
            "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
            limit=25,
        )
    ]

    assert chat_chunks[0].choices[0].delta.role == "assistant"
    assert chat_chunks[0].provider_backend is None
    assert response_events[1].item is not None
    assert response_events[1].item.provider_model_id is None
    assert response_events[1].item.content[0].token_count == 2
    assert run_events[0].event is not None
    assert run_events[1].status == "completed"
    assert seen[0][2]["json"]["stream"] is True
    assert seen[1][2]["json"]["stream"] is True


def test_decision_engine_agent_step_result_accepts_legacy_agent_step_shape() -> None:
    run = AgentRunResult.model_validate(
        {
            "run_id": "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
            "status": "completed",
            "task": "Search the knowledge base",
            "output_format": "markdown",
            "approval_mode": "manual",
            "result": {"summary": "Found 3 relevant documents"},
            "tools_available": ["search", "summarize"],
            "tools_used": ["search"],
            "steps": [
                {
                    "step_number": 1,
                    "tool_name": "search",
                    "input": {"query": "knowledge base"},
                    "output": {"hits": 3},
                    "rationale": "Search is the lowest-risk first step.",
                }
            ],
            "created_at": "2026-05-24T12:00:00Z",
            "updated_at": "2026-05-24T12:00:03Z",
            "latency_ms": 21.5,
        }
    )

    assert run.steps[0].step_number == 1
    assert run.steps[0].tool_name == "search"
    assert run.steps[0].rationale == "Search is the lowest-risk first step."
