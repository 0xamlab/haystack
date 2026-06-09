"""Tests for test_decision_engine_llm_and_agent_client_surface: decision_engine.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-2/tests/test_decision_engine_llm_and_agent_client_surface.py during modularization.
"""
from __future__ import annotations

from tests._test_decision_engine_llm_and_agent_client_surface_helpers import *  # noqa: F401,F403


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


