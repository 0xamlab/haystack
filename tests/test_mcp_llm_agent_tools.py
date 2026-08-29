from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import agent_runs, decisions, llm, recommend

pytestmark = pytest.mark.anyio


def test_list_models_tool_spec_is_zero_argument() -> None:
    assert llm.LIST_MODELS_SPEC["name"] == "list_models"
    assert "routing, failover, timeout, and auth metadata" in llm.LIST_MODELS_SPEC["description"]
    assert llm.LIST_MODELS_SPEC["inputSchema"]["properties"] == {}
    assert llm.LIST_MODELS_SPEC["inputSchema"]["additionalProperties"] is False


@pytest.mark.parametrize(
    ("spec", "required_fields"),
    [
        (llm.RESOLVE_ARTIFACT_BRIDGE_SPEC, {"repo_id", "filename"}),
        (llm.TOKENIZE_SPEC, {"input"}),
        (llm.COUNT_TOKENS_SPEC, {"input"}),
        (llm.CHAT_COMPLETIONS_SPEC, {"messages"}),
        (llm.RESPONSES_SPEC, {"input"}),
        (llm.EMBEDDINGS_SPEC, {"input"}),
        (llm.EMBEDDING_SIMILARITY_SPEC, {"left", "right"}),
        (llm.RERANK_SPEC, {"query_embedding", "documents"}),
        (recommend.SPEC, {"actions"}),
        (recommend.SCORE_SPEC, {"request"}),
        (recommend.BATCH_SPEC, {"items"}),
        (recommend.COMPARE_SPEC, {"scenarios"}),
        (agent_runs.CREATE_AGENT_RUN_SPEC, {"task"}),
        (agent_runs.LIST_AGENT_RUNS_SPEC, set()),
        (agent_runs.GET_AGENT_RUN_SPEC, {"run_id"}),
        (agent_runs.GET_AGENT_RUN_EVENTS_SPEC, {"run_id"}),
        (agent_runs.GET_AGENT_RUN_CHECKPOINTS_SPEC, {"run_id"}),
        (agent_runs.QUERY_AGENT_RUN_CHECKPOINTS_SPEC, set()),
        (agent_runs.GET_AGENT_RUN_MISSION_EVENTS_SPEC, {"run_id"}),
        (agent_runs.QUERY_AGENT_RUN_MISSION_EVENTS_SPEC, set()),
        (agent_runs.GET_AGENT_RUN_TELEMETRY_SPEC, {"run_id"}),
        (agent_runs.QUERY_AGENT_RUN_TELEMETRY_SPEC, set()),
        (agent_runs.RESUME_AGENT_RUN_SPEC, {"run_id"}),
        (agent_runs.CANCEL_AGENT_RUN_SPEC, {"run_id"}),
        (agent_runs.APPROVE_AGENT_RUN_SPEC, {"run_id"}),
        (decisions.LOG_DECISION_SPEC, {"chosen_action"}),
        (decisions.GET_DECISION_SPEC, {"decision_id"}),
        (decisions.RECORD_OUTCOME_SPEC, {"decision_id", "actual_outcome"}),
        (decisions.EXECUTE_DECISION_SPEC, {"decision_id", "webhook_url"}),
        (decisions.DELETE_DECISION_SPEC, {"decision_id"}),
    ],
)
def test_mcp_llm_and_agent_specs_expose_required_fields(
    spec: dict[str, object],
    required_fields: set[str],
) -> None:
    assert required_fields.issubset(set(spec["inputSchema"]["required"]))  # type: ignore[index]
    assert spec["inputSchema"]["additionalProperties"] is False  # type: ignore[index]


def test_plan_decision_tool_spec_has_object_schema() -> None:
    assert decisions.PLAN_DECISION_SPEC["name"] == "plan_decision"
    assert decisions.PLAN_DECISION_SPEC["inputSchema"]["type"] == "object"


async def test_list_models_handler_forwards_request(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert (method, path, kwargs) == ("GET", "/v1/models", {})
        return {
            "object": "list",
            "data": [
                {
                    "id": "text.tokenizer",
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
                    "chat_required_provider_headers": [],
                    "embedding_required_provider_headers": [],
                    "provider_auth_env_vars": [],
                    "chat_provider_auth_env_vars": [],
                    "embedding_provider_auth_env_vars": [],
                    "provider_auth_configured": False,
                    "chat_provider_auth_configured": False,
                    "embedding_provider_auth_configured": False,
                }
            ],
        }

    monkeypatch.setattr(llm, "api", _fake_api)

    body = json.loads(await llm.list_models_handler({}))
    assert body["data"][0]["id"] == "text.tokenizer"
    assert body["data"][0]["provider_backend"] is None
    assert body["data"][0]["resolved_chat_routing_targets"] == []
    assert body["data"][0]["routing_fallback_policy"] is None
    assert body["data"][0]["chat_routing_fallback_policy"] is None
    assert body["data"][0]["embedding_routing_fallback_policy"] is None
    assert body["data"][0]["routing_fallback_on"] == []
    assert body["data"][0]["chat_routing_fallback_on"] == []
    assert body["data"][0]["embedding_routing_fallback_on"] == []
    assert body["data"][0]["routing_max_attempts"] is None
    assert body["data"][0]["chat_routing_max_attempts"] is None
    assert body["data"][0]["embedding_routing_max_attempts"] is None
    assert body["data"][0]["timeout_seconds"] is None
    assert body["data"][0]["chat_timeout_seconds"] is None
    assert body["data"][0]["embedding_timeout_seconds"] is None
    assert body["data"][0]["provider_auth_env_vars"] == []
    assert body["data"][0]["chat_provider_auth_env_vars"] == []
    assert body["data"][0]["embedding_provider_auth_env_vars"] == []
    assert body["data"][0]["provider_auth_configured"] is False
    assert body["data"][0]["chat_provider_auth_configured"] is False
    assert body["data"][0]["embedding_provider_auth_configured"] is False


@pytest.mark.parametrize(
    ("handler", "expected_path", "arguments", "expected_json"),
    [
        (
            llm.resolve_artifact_bridge_handler,
            "/v1/artifacts/resolve",
            {"repo_id": "org/model", "filename": "model.safetensors"},
            {
                "repo_id": "org/model",
                "filename": "model.safetensors",
                "revision": None,
                "local_files_only": True,
            },
        ),
        (
            llm.tokenize_handler,
            "/v1/tokenize",
            {"input": "hello"},
            {"input": "hello", "model": "text.tokenizer"},
        ),
        (
            llm.count_tokens_handler,
            "/v1/count_tokens",
            {"input": "hello"},
            {"input": "hello", "model": "text.tokenizer"},
        ),
        (
            llm.chat_completions_handler,
            "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "hello"}]},
            {"messages": [{"role": "user", "content": "hello"}], "model": "text.tokenizer"},
        ),
        (
            llm.responses_handler,
            "/v1/responses",
            {"input": "hello", "dimensions": 32},
            {"input": "hello", "model": "text.tokenizer", "dimensions": 32},
        ),
        (
            llm.embeddings_handler,
            "/v1/embeddings",
            {"input": ["hello"], "dimensions": 32},
            {"input": ["hello"], "model": "text.hash_embedding_v1", "dimensions": 32},
        ),
        (
            llm.embedding_similarity_handler,
            "/v1/embeddings/similarity",
            {"left": [0.1], "right": [0.2]},
            {"left": [0.1], "right": [0.2], "model": "embeddings.cosine_similarity"},
        ),
        (
            llm.rerank_handler,
            "/v1/rerank",
            {
                "query_embedding": [0.1],
                "documents": [{"id": "doc-1", "embedding": [0.1]}],
                "top_n": 1,
            },
            {
                "query_embedding": [0.1],
                "documents": [{"id": "doc-1", "embedding": [0.1]}],
                "model": "embeddings.cosine_similarity",
                "top_n": 1,
            },
        ),
    ],
)
async def test_llm_handlers_forward_payloads(
    monkeypatch: pytest.MonkeyPatch,
    handler,
    expected_path: str,
    arguments: dict[str, object],
    expected_json: dict[str, object],
) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == expected_path
        assert kwargs == {"json": expected_json}
        return {"path": path, "ok": True}

    monkeypatch.setattr(llm, "api", _fake_api)

    body = json.loads(await handler(arguments))
    assert body == {"path": expected_path, "ok": True}


async def test_responses_handler_forwards_tools_and_typed_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_json = {
        "input": [
            {"type": "message", "role": "user", "content": "What is the weather in Paris?"}
        ],
        "model": "provider.gpt-4o-mini",
        "dimensions": 64,
        "tools": [{"type": "function", "function": {"name": "get_weather"}}],
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "previous_response_id": "resp_prior",
    }

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/responses"
        assert kwargs == {"json": expected_json}
        return {"id": "resp_new", "object": "response"}

    monkeypatch.setattr(llm, "api", _fake_api)

    body = json.loads(
        await llm.responses_handler(
            {
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": "What is the weather in Paris?",
                    }
                ],
                "model": "provider.gpt-4o-mini",
                "tools": [{"type": "function", "function": {"name": "get_weather"}}],
                "tool_choice": "auto",
                "parallel_tool_calls": False,
                "previous_response_id": "resp_prior",
            }
        )
    )
    assert body == {"id": "resp_new", "object": "response"}


async def test_plan_decision_handler_forwards_request(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"mode": "auto", "scenario": {"variables": {"revenue": {"low": 1, "high": 2}}}}

    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/decisions/plan"
        assert kwargs == {"json": payload}
        return {"recommended_action": "expand"}

    monkeypatch.setattr(decisions, "api", _fake_api)

    body = json.loads(await decisions.plan_decision_handler(payload))
    assert body["recommended_action"] == "expand"


@pytest.mark.parametrize(
    ("handler", "method", "path", "arguments", "expected_json", "expected_assertion"),
    [
        (
            decisions.log_decision_handler,
            "POST",
            "/v1/decisions",
            {"chosen_action": "expand", "context": "Launch planning", "expected_value": 128000.0},
            {"chosen_action": "expand", "context": "Launch planning", "expected_value": 128000.0},
            lambda body: (
                body["decision_id"] == "decision_123"
                and body["chosen_action"] == "expand"
                and body["note"].startswith("Decision logged.")
            ),
        ),
        (
            decisions.list_decisions_handler,
            "GET",
            "/v1/decisions",
            {"page": 1, "limit": 20, "with_outcome_only": True},
            {"page": 1, "limit": 20, "with_outcome_only": "true"},
            lambda body: (
                body["total"] == 1
                and body["decisions"][0]["id"] == "decision_123"
                and "Avg outcome_delta" in body["accuracy_summary"]
            ),
        ),
        (
            decisions.get_decision_handler,
            "GET",
            "/v1/decisions/decision_123",
            {"decision_id": "decision_123"},
            None,
            lambda body: body["id"] == "decision_123" and body["chosen_action"] == "expand",
        ),
        (
            decisions.record_outcome_handler,
            "PATCH",
            "/v1/decisions/decision_123/outcome",
            {
                "decision_id": "decision_123",
                "actual_outcome": 141000.0,
                "outcome_notes": "Launch outperformed baseline",
            },
            {"actual_outcome": 141000.0, "outcome_notes": "Launch outperformed baseline"},
            lambda body: (
                body["decision_id"] == "decision_123"
                and body["outcome_delta"] == 13000.0
                and "under-optimistic" in body["summary"]
            ),
        ),
        (
            decisions.execute_decision_handler,
            "POST",
            "/v1/decisions/decision_123/execute",
            {
                "decision_id": "decision_123",
                "webhook_url": "https://hooks.example.test/decision",
                "timeout_seconds": 15,
            },
            {"webhook_url": "https://hooks.example.test/decision", "timeout_seconds": 15},
            lambda body: (
                body["decision_id"] == "decision_123"
                and body["execution_status"] == "delivered"
                and body["policy_snapshot_id"] == "execution-policy-v1-r2:abcd1234abcd1234"
            ),
        ),
        (
            decisions.delete_decision_handler,
            "DELETE",
            "/v1/decisions/decision_123",
            {"decision_id": "decision_123"},
            None,
            lambda body: body == {"decision_id": "decision_123", "deleted": True},
        ),
    ],
)
async def test_decision_memory_handlers_forward_requests(
    monkeypatch: pytest.MonkeyPatch,
    handler,
    method: str,
    path: str,
    arguments: dict[str, object],
    expected_json: dict[str, object] | None,
    expected_assertion,
) -> None:
    async def _fake_api(call_method: str, call_path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert call_method == method
        assert call_path == path
        if method == "GET" and path == "/v1/decisions":
            assert kwargs == {"params": expected_json}
            return {
                "total": 1,
                "page": 1,
                "limit": 20,
                "pages": 1,
                "decisions": [
                    {
                        "id": "decision_123",
                        "chosen_action": "expand",
                        "expected_value": 128000.0,
                        "actual_outcome": 141000.0,
                        "outcome_delta": 13000.0,
                        "confidence": 0.82,
                        "context": "Launch planning",
                        "created_at": "2026-05-24T12:00:00Z",
                        "outcome_recorded_at": "2026-05-24T12:30:00Z",
                    }
                ],
            }
        elif expected_json is None:
            assert kwargs == {}
        else:
            assert kwargs == {"json": expected_json}

        if path == "/v1/decisions":
            return {
                "id": "decision_123",
                "chosen_action": "expand",
                "expected_value": 128000.0,
                "confidence": 0.82,
                "created_at": "2026-05-24T12:00:00Z",
            }
        if path == "/v1/decisions/decision_123":
            return {"id": "decision_123", "chosen_action": "expand"}
        if path.endswith("/outcome"):
            return {
                "id": "decision_123",
                "chosen_action": "expand",
                "expected_value": 128000.0,
                "actual_outcome": 141000.0,
                "outcome_delta": 13000.0,
            }
        if path.endswith("/execute"):
            return {
                "decision_id": "decision_123",
                "execution_status": "delivered",
                "webhook_url": "https://hooks.example.test/decision",
                "policy_snapshot_id": "execution-policy-v1-r2:abcd1234abcd1234",
            }
        return {}

    monkeypatch.setattr(decisions, "api", _fake_api)

    body = json.loads(await handler(arguments))
    assert expected_assertion(body)


@pytest.mark.parametrize(
    ("handler", "expected_path", "arguments", "expected_json", "expected_key"),
    [
        (
            recommend.handler,
            "/v1/recommend",
            {
                "actions": [
                    {
                        "name": "expand",
                        "variables": {"revenue": {"low": 1, "high": 2}},
                    },
                    {
                        "name": "hold",
                        "variables": {"revenue": {"low": 1, "high": 2}},
                    },
                ],
                "n_simulations": 500,
            },
            {
                "actions": [
                    {
                        "name": "expand",
                        "request": {
                            "mode": "auto",
                            "runs": 500,
                            "scenario": {
                                "variables": {"revenue": {"low": 1, "high": 2}},
                                "objective": "maximize",
                            },
                        },
                    },
                    {
                        "name": "hold",
                        "request": {
                            "mode": "auto",
                            "runs": 500,
                            "scenario": {
                                "variables": {"revenue": {"low": 1, "high": 2}},
                                "objective": "maximize",
                            },
                        },
                    },
                ]
            },
            "recommended_action",
        ),
        (
            recommend.score_handler,
            "/v1/score",
            {
                "request": {"mode": "expert", "simulation": {"variables": []}},
                "scoring_weights": {"expected_value": 0.7, "downside_risk": 0.3},
            },
            {
                "request": {"mode": "expert", "simulation": {"variables": []}},
                "scoring_weights": {"expected_value": 0.7, "downside_risk": 0.3},
            },
            "score",
        ),
        (
            recommend.batch_handler,
            "/v1/batch",
            {"items": [{"mode": "expert", "simulation": {"variables": []}}]},
            {"items": [{"mode": "expert", "simulation": {"variables": []}}]},
            "results",
        ),
        (
            recommend.compare_handler,
            "/v1/compare",
            {
                "scenarios": [
                    {"name": "base", "request": {"mode": "expert", "simulation": {"variables": []}}},
                    {"name": "stretch", "request": {"mode": "expert", "simulation": {"variables": []}}},
                ],
                "runs": 200,
            },
            {
                "scenarios": [
                    {"name": "base", "request": {"mode": "expert", "simulation": {"variables": []}}},
                    {"name": "stretch", "request": {"mode": "expert", "simulation": {"variables": []}}},
                ],
                "runs": 200,
            },
            "winner",
        ),
    ],
)
async def test_decision_runtime_handlers_forward_requests(
    monkeypatch: pytest.MonkeyPatch,
    handler,
    expected_path: str,
    arguments: dict[str, object],
    expected_json: dict[str, object],
    expected_key: str,
) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == expected_path
        assert kwargs == {"json": expected_json}
        if path == "/v1/recommend":
            return {"recommended_action": "expand", "action_results": []}
        if path == "/v1/score":
            return {
                "envelope": {"recommended_action": "expand", "expected_value": 42, "probability_of_loss": 0.1},
                "score": 0.82,
                "score_breakdown": {"expected_value_component": 0.6},
            }
        if path == "/v1/batch":
            return {"total": 1, "succeeded": 1, "failed": 0, "results": [{"index": 0, "success": True, "envelope": {"recommended_action": "expand", "expected_value": 42}}]}
        return {
            "winner": "stretch",
            "margin": {"score_delta": 0.1},
            "scenarios": [{"name": "stretch", "envelope": {"recommended_action": "expand", "expected_value": 42, "probability_of_loss": 0.1}}],
        }

    monkeypatch.setattr(recommend, "api", _fake_api)

    body = json.loads(await handler(arguments))
    assert expected_key in body


async def test_create_agent_run_handler_forwards_request(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_api(method: str, path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert path == "/v1/agent/runs"
        assert kwargs == {
            "json": {
                "task": "Inspect customer churn",
                "max_steps": 12,
                "output_format": "markdown",
                "approval_mode": "manual",
                "start_paused": True,
                "context": {"segment": "enterprise"},
                "tools": ["query", "summarize"],
            }
        }
        return {"run_id": "run_123", "status": "paused"}

    monkeypatch.setattr(agent_runs, "api", _fake_api)

    body = json.loads(
        await agent_runs.create_agent_run_handler(
            {
                "task": "Inspect customer churn",
                "max_steps": 12,
                "output_format": "markdown",
                "approval_mode": "manual",
                "start_paused": True,
                "context": {"segment": "enterprise"},
                "tools": ["query", "summarize"],
            }
        )
    )
    assert body["run_id"] == "run_123"
    assert body["status"] == "paused"


@pytest.mark.parametrize(
    ("handler", "path", "arguments", "expected_kwargs"),
    [
        (
            agent_runs.list_agent_runs_handler,
            "/v1/agent/runs",
            {"page": 1, "limit": 25, "status": "requires_approval"},
            {"params": {"page": 1, "limit": 25, "status": "requires_approval"}},
        ),
        (
            agent_runs.get_agent_run_handler,
            "/v1/agent/runs/run_123",
            {"run_id": "run_123"},
            {},
        ),
        (
            agent_runs.get_agent_run_events_handler,
            "/v1/agent/runs/run_123/events",
            {"run_id": "run_123", "limit": 25},
            {"params": {"limit": 25}},
        ),
        (
            agent_runs.get_agent_run_checkpoints_handler,
            "/v1/agent/runs/run_123/checkpoints",
            {"run_id": "run_123"},
            {},
        ),
        (
            agent_runs.get_agent_run_mission_events_handler,
            "/v1/agent/runs/run_123/mission-events",
            {"run_id": "run_123", "limit": 25},
            {"params": {"limit": 25}},
        ),
        (
            agent_runs.query_agent_run_checkpoints_handler,
            "/v1/agent/runs/checkpoints",
            {
                "page": 2,
                "limit": 10,
                "status": "completed",
                "request_hash": "hash_123",
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "run_id": "run_123",
                "checkpoint_id": "cp_2",
            },
            {
                "params": {
                    "page": 2,
                    "limit": 10,
                    "status": "completed",
                    "request_hash": "hash_123",
                    "policy_snapshot_id": "policy-v1",
                    "schema_snapshot_id": "schema-v1",
                    "run_id": "run_123",
                    "checkpoint_id": "cp_2",
                }
            },
        ),
        (
            agent_runs.query_agent_run_mission_events_handler,
            "/v1/agent/runs/mission-events",
            {
                "page": 1,
                "limit": 25,
                "status": "completed",
                "request_hash": "a" * 64,
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "run_id": "run_123",
                "event_type": "run_completed",
            },
            {
                "params": {
                    "page": 1,
                    "limit": 25,
                    "status": "completed",
                    "request_hash": "a" * 64,
                    "policy_snapshot_id": "policy-v1",
                    "schema_snapshot_id": "schema-v1",
                    "run_id": "run_123",
                    "event_type": "run_completed",
                }
            },
        ),
        (
            agent_runs.get_agent_run_telemetry_handler,
            "/v1/agent/runs/run_123/telemetry",
            {"run_id": "run_123", "limit": 25},
            {"params": {"limit": 25}},
        ),
        (
            agent_runs.query_agent_run_telemetry_handler,
            "/v1/agent/runs/telemetry",
            {
                "page": 1,
                "limit": 25,
                "status": "completed",
                "request_hash": "a" * 64,
                "policy_snapshot_id": "policy-v1",
                "schema_snapshot_id": "schema-v1",
                "run_id": "run_123",
                "telemetry_kind": "agent_run_completion",
                "module_name": "agent_run_service",
            },
            {
                "params": {
                    "page": 1,
                    "limit": 25,
                    "status": "completed",
                    "request_hash": "a" * 64,
                    "policy_snapshot_id": "policy-v1",
                    "schema_snapshot_id": "schema-v1",
                    "run_id": "run_123",
                    "telemetry_kind": "agent_run_completion",
                    "module_name": "agent_run_service",
                }
            },
        ),
        (
            agent_runs.resume_agent_run_handler,
            "/v1/agent/runs/run_123/resume",
            {"run_id": "run_123"},
            {"json": {}},
        ),
        (
            agent_runs.cancel_agent_run_handler,
            "/v1/agent/runs/run_123/cancel",
            {"run_id": "run_123"},
            {"json": {}},
        ),
        (
            agent_runs.approve_agent_run_handler,
            "/v1/agent/runs/run_123/approve",
            {"run_id": "run_123"},
            {"json": {}},
        ),
    ],
)
async def test_agent_run_handlers_forward_requests(
    monkeypatch: pytest.MonkeyPatch,
    handler,
    path: str,
    arguments: dict[str, object],
    expected_kwargs: dict[str, object],
) -> None:
    get_handlers = {
        agent_runs.list_agent_runs_handler,
        agent_runs.get_agent_run_handler,
        agent_runs.get_agent_run_events_handler,
        agent_runs.get_agent_run_checkpoints_handler,
        agent_runs.query_agent_run_checkpoints_handler,
        agent_runs.get_agent_run_mission_events_handler,
        agent_runs.query_agent_run_mission_events_handler,
        agent_runs.get_agent_run_telemetry_handler,
        agent_runs.query_agent_run_telemetry_handler,
    }
    expected_method = "GET" if handler in get_handlers else "POST"

    async def _fake_api(method: str, actual_path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == expected_method
        assert actual_path == path
        assert kwargs == expected_kwargs
        return {"path": actual_path, "status": "ok"}

    monkeypatch.setattr(agent_runs, "api", _fake_api)

    body = json.loads(await handler(arguments))
    assert body["path"] == path
    assert body["status"] == "ok"
