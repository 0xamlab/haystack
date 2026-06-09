"""Tests for test_algenta_runtime_llm_and_agent_surface: algenta_runtime_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-3/tests/test_algenta_runtime_llm_and_agent_surface.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_llm_and_agent_surface_helpers import *  # noqa: F401,F403


def test_algenta_runtime_api_llm_and_agent_methods_return_typed_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")

    class _FakeClient:
        def plan_decision(self, request: dict[str, object]) -> object:
            assert request["metric"] == "profit"
            return _make_decision_plan_payload()

        def log_decision(self, request: dict[str, object]) -> object:
            assert request == {
                "chosen_action": "expand",
                "context": "Launch planning",
                "expected_value": 128000.0,
            }
            return _make_decision_log_payload()

        def list_decisions(
            self,
            *,
            page: int | None = None,
            limit: int | None = None,
            page_size: int | None = None,
            with_outcome_only: bool | None = None,
        ) -> object:
            assert page == 1
            assert limit == 20
            assert page_size is None
            assert with_outcome_only is True
            return _make_decision_list_payload()

        def get_decision(self, decision_id: str) -> object:
            assert decision_id == "decision_123"
            return _make_decision_log_payload()

        def record_outcome(
            self,
            decision_id: str,
            *,
            actual_outcome: float,
            outcome_notes: str | None = None,
        ) -> object:
            assert decision_id == "decision_123"
            assert actual_outcome == 141000.0
            assert outcome_notes == "Launch outperformed baseline"
            return _make_recorded_outcome_payload()

        def execute_decision(
            self,
            decision_id: str,
            *,
            webhook_url: str,
            timeout_seconds: float = 10.0,
            force: bool = False,
            override_safety: bool = False,
            metadata: dict[str, object] | None = None,
        ) -> object:
            assert decision_id == "decision_123"
            assert webhook_url == "https://hooks.example.test/decision"
            assert timeout_seconds == 10.0
            assert force is False
            assert override_safety is False
            assert metadata is None
            return _make_execution_receipt_payload()

        def delete_decision(self, decision_id: str) -> object:
            assert decision_id == "decision_123"
            return {}

        def recommend(self, actions: list[dict[str, object]], **kwargs: object) -> object:
            assert actions[0]["name"] == "expand"
            assert kwargs["metric"] == "profit"
            return {
                "recommended_action": "expand",
                "scores": [{"name": "expand", "score": 0.82}],
            }

        def score(
            self,
            request: dict[str, object],
            *,
            scoring_weights: dict[str, float] | None = None,
        ) -> object:
            assert request["mode"] == "expert"
            assert scoring_weights == {"risk": 0.2}
            return {"score": 0.77, "weights": scoring_weights}

        def batch(self, items: list[dict[str, object]]) -> object:
            assert len(items) == 2
            return [
                {"request_id": "req_1", "score": 0.75},
                {"request_id": "req_2", "score": 0.81},
            ]

        def compare(self, scenarios: list[dict[str, object]], **kwargs: object) -> object:
            assert len(scenarios) == 2
            assert kwargs["metric"] == "profit"
            return {
                "winner": "stretch",
                "scenarios": [{"name": "base"}, {"name": "stretch"}],
            }

        def me(self) -> object:
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
                    "id": "08f7453b-7a11-42d5-8b53-4700afbb7f58",
                    "name": "Mission Control",
                    "slug": "mission-control",
                    "plan": "enterprise",
                    "status": "active",
                    "created_at": "2026-05-24T11:00:00Z",
                },
            }

        def usage(self) -> object:
            from decision_engine.models_account import UsageInfo

            return UsageInfo.model_validate(_make_usage_payload())

        def limits(self) -> object:
            return {
                "plan": "enterprise",
                "simulations": {"limit": 1000, "used": 120},
            }

        def list_api_keys(self) -> object:
            from decision_engine.models_account import APIKeyInfo

            return [APIKeyInfo.model_validate(_make_api_key_info_payload())]

        def create_api_key(
            self,
            label: str | None = None,
            *,
            name: str | None = None,
            expires_at: object = None,
            device_limit: int | None = None,
        ) -> object:
            assert label == "Mission Runtime Key"
            assert name is None
            assert expires_at == "2028-05-24T12:00:00Z"
            assert device_limit == 2
            return _make_api_key_created_payload()

        def revoke_api_key(self, key_id: str) -> object:
            assert key_id == "79fc2a0b-6402-4137-b637-b76ee5e745bf"
            return {}

        def list_models(self) -> object:
            return _make_model_list_payload()

        def resolve_artifact_bridge(
            self,
            *,
            repo_id: str,
            filename: str,
            revision: str | None = None,
            local_files_only: bool = True,
        ) -> object:
            assert repo_id == "org/model"
            assert filename == "model.safetensors"
            assert revision == "main"
            assert local_files_only is True
            return _make_artifact_bridge_payload()

        def tokenize(self, text: str, *, model: str) -> object:
            assert text == "expand sales coverage"
            assert model == "text.tokenizer"
            return {
                "object": "tokenization",
                "model": model,
                "tokenizer_kind": "wordpiece",
                "tokens": ["expand", "sales", "coverage"],
                "token_count": 3,
            }

        def count_tokens(self, text: str, *, model: str) -> object:
            assert text == "expand sales coverage"
            assert model == "text.tokenizer"
            return {
                "object": "token_count",
                "model": model,
                "tokenizer_kind": "wordpiece",
                "token_count": 3,
            }

        def chat_completions(self, messages: list[dict[str, str]], *, model: str) -> object:
            assert messages[0]["content"] == "hello"
            assert model == "text.tokenizer"
            return {
                "id": "chatcmpl_123",
                "object": "chat.completion",
                "model": model,
                "provider_backend": None,
                "provider_model_id": None,
                "provider_attempts": [],
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "Deterministic utility response.",
                        },
                    }
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
            }

        def stream_chat_completions(
            self,
            messages: list[dict[str, str]],
            *,
            model: str,
        ):
            assert messages[0]["content"] == "hello"
            assert model == "text.tokenizer"
            return iter(_make_chat_stream_payloads())

        def responses(
            self,
            input_value: str | list[str],
            *,
            model: str,
            dimensions: int,
        ) -> object:
            assert input_value == "expand sales coverage"
            assert model == "text.tokenizer"
            assert dimensions == 64
            return {
                "id": "resp_123",
                "object": "response",
                "status": "completed",
                "model": "text.hash_embedding_v1",
                "provider_backend": None,
                "provider_model_id": None,
                "provider_attempts": [],
                "output": [
                    {
                        "id": "out_1",
                        "object": "response.output",
                        "index": 0,
                        "provider_backend": None,
                        "provider_model_id": None,
                        "provider_attempts": [],
                        "content": [
                            {
                                "type": "embedding",
                                "text": "expand sales coverage",
                                "token_count": 3,
                                "embedding": [0.1, 0.2, 0.3],
                            }
                        ],
                    }
                ],
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            }

        def stream_responses(
            self,
            input_value: str | list[str],
            *,
            model: str,
            dimensions: int,
        ):
            assert input_value == "expand sales coverage"
            assert model == "text.tokenizer"
            assert dimensions == 64
            return iter(_make_response_stream_payloads())

        def embeddings(
            self,
            input_value: str | list[str],
            *,
            model: str,
            dimensions: int,
        ) -> object:
            assert input_value == "expand sales coverage"
            assert model == "text.hash_embedding_v1"
            assert dimensions == 64
            return {
                "object": "list",
                "model": model,
                "dimensions": 3,
                "provider_backend": None,
                "provider_model_id": None,
                "data": [
                    {
                        "object": "embedding",
                        "index": 0,
                        "embedding": [0.1, 0.2, 0.3],
                        "token_count": 3,
                    }
                ],
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            }

        def embedding_similarity(
            self,
            left: list[float],
            right: list[float],
            *,
            model: str,
        ) -> object:
            assert left == [0.1, 0.2, 0.3]
            assert right == [0.3, 0.2, 0.1]
            assert model == "embeddings.cosine_similarity"
            return {
                "object": "embedding_similarity",
                "model": model,
                "similarity_metric": "cosine",
                "score": 0.94,
                "dimension": 3,
            }

        def rerank(
            self,
            query_embedding: list[float],
            documents: list[dict[str, object]],
            *,
            model: str,
            top_n: int | None,
        ) -> object:
            assert query_embedding == [0.1, 0.2, 0.3]
            assert documents[0]["id"] == "doc-1"
            assert model == "embeddings.cosine_similarity"
            assert top_n == 1
            return {
                "object": "list",
                "model": model,
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
            }

        def create_agent_run(self, **kwargs) -> object:
            assert kwargs["task"] == "Search the knowledge base"
            return _make_agent_run_payload("requires_approval", "approve")

        def get_agent_run(self, run_id: str) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            return _make_agent_run_payload("requires_approval", "approve")

        def list_agent_runs(self, **kwargs) -> object:
            assert kwargs["page"] == 1
            assert kwargs["limit"] == 25
            assert kwargs["status"] == "requires_approval"
            return _make_agent_run_list_payload()

        def get_agent_run_events(self, run_id: str, *, limit: int) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            assert limit == 25
            return _make_agent_run_events_payload()

        def stream_agent_run_events(self, run_id: str, *, limit: int):
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            assert limit == 25
            return iter(_make_agent_run_stream_payloads())

        def list_agent_run_checkpoints(self, run_id: str) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            return _make_agent_run_checkpoints_payload()

        def query_agent_run_checkpoints(self, **kwargs) -> object:
            assert kwargs["status"] == "completed"
            assert kwargs["request_hash"] == "a" * 64
            assert kwargs["policy_snapshot_id"] == "policy-v1"
            assert kwargs["schema_snapshot_id"] == "schema-v1"
            assert kwargs["run_id"] == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            assert kwargs["checkpoint_id"] == "cp_2"
            return _make_agent_run_checkpoint_query_payload()

        def list_agent_run_mission_events(self, run_id: str, *, limit: int) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            assert limit == 25
            return _make_agent_run_mission_events_payload()

        def query_agent_run_mission_events(self, **kwargs) -> object:
            assert kwargs["status"] == "completed"
            assert kwargs["request_hash"] == "a" * 64
            assert kwargs["policy_snapshot_id"] == "policy-v1"
            assert kwargs["schema_snapshot_id"] == "schema-v1"
            assert kwargs["run_id"] == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            assert kwargs["event_type"] == "run_created"
            return _make_agent_run_mission_event_query_payload()

        def list_agent_run_telemetry(self, run_id: str, *, limit: int) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            assert limit == 25
            return _make_agent_run_telemetry_payload()

        def query_agent_run_telemetry(self, **kwargs) -> object:
            assert kwargs["status"] == "completed"
            assert kwargs["request_hash"] == "a" * 64
            assert kwargs["policy_snapshot_id"] == "policy-v1"
            assert kwargs["schema_snapshot_id"] == "schema-v1"
            assert kwargs["run_id"] == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            assert kwargs["telemetry_kind"] == "agent_run_completion"
            assert kwargs["module_name"] == "agent_run_service"
            return _make_agent_run_telemetry_query_payload()

        def replay_agent_run(self, run_id: str, *, checkpoint_id: str | None = None) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            assert checkpoint_id in {None, "cp_2"}
            return _make_agent_run_replay_payload()

        def fork_agent_run(self, run_id: str, *, checkpoint_id: str | None = None) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            assert checkpoint_id in {None, "cp_1"}
            payload = _make_agent_run_payload("paused", "resume")
            payload["source_run_id"] = run_id
            payload["source_checkpoint_id"] = checkpoint_id or "cp_1"
            return payload

        def resume_agent_run(self, run_id: str) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            return _make_agent_run_payload("requires_approval", "approve")

        def cancel_agent_run(self, run_id: str) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            return _make_agent_run_payload("cancelled", None)

        def approve_agent_run(self, run_id: str) -> object:
            assert run_id == "8e3c9e2c-b67d-42da-b456-1de39d7289fb"
            return _make_agent_run_payload("completed", None)

        def list_deployment_regions(self) -> object:
            return _make_deployment_regions_payload()

        def get_deployment(self) -> object:
            return _make_deployment_payload()

        def create_deployment(
            self,
            *,
            provider: str,
            region: str,
            config: dict[str, object] | None,
            billing_markup_pct: float,
        ) -> object:
            assert provider == "algenta_shared"
            assert region == "algenta-shared"
            assert config is None
            assert billing_markup_pct == 20.0
            return _make_deployment_payload()

        def get_deployment_cost(self, deployment_id: str) -> object:
            assert deployment_id == "dep_123"
            return _make_deployment_cost_payload()

        def delete_deployment(self, deployment_id: str) -> object:
            assert deployment_id == "dep_123"
            return _make_deployment_delete_payload()

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    plan = runtime.plan_decision({"metric": "profit", "options": ["expand"]})
    recommendation = runtime.recommend([{"name": "expand", "score": 0.82}], metric="profit")
    scored = runtime.score(
        {"mode": "expert", "simulation": {"variables": []}},
        scoring_weights={"risk": 0.2},
    )
    batch = runtime.batch(
        [
            {"mode": "expert", "simulation": {"variables": []}},
            {"mode": "expert", "simulation": {"variables": []}},
        ]
    )
    compared = runtime.compare([{"name": "base"}, {"name": "stretch"}], metric="profit")
    me = runtime.me()
    usage = runtime.usage()
    limits = runtime.limits()
    api_keys = runtime.list_api_keys()
    created_api_key = runtime.create_api_key(
        label="Mission Runtime Key",
        expires_at="2028-05-24T12:00:00Z",
        device_limit=2,
    )
    revoked_api_key = runtime.revoke_api_key("79fc2a0b-6402-4137-b637-b76ee5e745bf")
    models = runtime.list_models()
    bridge = runtime.resolve_artifact_bridge(
        repo_id="org/model",
        filename="model.safetensors",
        revision="main",
    )
    tokens = runtime.tokenize("expand sales coverage")
    token_count = runtime.count_tokens("expand sales coverage")
    completion = runtime.chat_completions([{"role": "user", "content": "hello"}])
    stream_completion = list(runtime.stream_chat_completions([{"role": "user", "content": "hello"}]))
    response = runtime.responses("expand sales coverage")
    stream_response = list(runtime.stream_responses("expand sales coverage"))
    embeddings = runtime.embeddings("expand sales coverage")
    similarity = runtime.embedding_similarity([0.1, 0.2, 0.3], [0.3, 0.2, 0.1])
    deployment_regions = runtime.list_deployment_regions()
    deployment = runtime.get_deployment()
    created_deployment = runtime.create_deployment()
    deployment_cost = runtime.get_deployment_cost("dep_123")
    deleted_deployment = runtime.delete_deployment("dep_123")
    logged_decision = runtime.log_decision(
        {"chosen_action": "expand", "context": "Launch planning", "expected_value": 128000.0}
    )
    listed_decisions = runtime.list_decisions(page=1, limit=20, with_outcome_only=True)
    fetched_decision = runtime.get_decision("decision_123")
    recorded_outcome = runtime.record_outcome(
        "decision_123",
        actual_outcome=141000.0,
        outcome_notes="Launch outperformed baseline",
    )
    execution_receipt = runtime.execute_decision(
        "decision_123",
        webhook_url="https://hooks.example.test/decision",
    )
    deleted_decision = runtime.delete_decision("decision_123")
    rerank = runtime.rerank(
        [0.1, 0.2, 0.3],
        [
            {"id": "doc-1", "embedding": [0.1, 0.2, 0.3], "text": "Top document"},
            {"id": "doc-2", "embedding": [0.0, 0.1, 0.2], "text": "Other"},
        ],
        top_n=1,
    )
    created = runtime.create_agent_run(
        task="Search the knowledge base",
        context={"scope": "kb"},
        tools=["search"],
        output_format="markdown",
        approval_mode="manual",
    )
    listed_runs = runtime.list_agent_runs(status="requires_approval")
    fetched = runtime.get_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    events = runtime.get_agent_run_events("8e3c9e2c-b67d-42da-b456-1de39d7289fb", limit=25)
    streamed_events = list(
        runtime.stream_agent_run_events("8e3c9e2c-b67d-42da-b456-1de39d7289fb", limit=25)
    )
    checkpoints = runtime.list_agent_run_checkpoints("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    checkpoint_query = runtime.query_agent_run_checkpoints(
        status="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        checkpoint_id="cp_2",
    )
    mission_events = runtime.list_agent_run_mission_events(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        limit=25,
    )
    mission_event_query = runtime.query_agent_run_mission_events(
        status="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        event_type="run_created",
    )
    telemetry = runtime.list_agent_run_telemetry(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        limit=25,
    )
    telemetry_query = runtime.query_agent_run_telemetry(
        status="completed",
        request_hash="a" * 64,
        policy_snapshot_id="policy-v1",
        schema_snapshot_id="schema-v1",
        run_id="8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        telemetry_kind="agent_run_completion",
        module_name="agent_run_service",
    )
    replay = runtime.replay_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    forked = runtime.fork_agent_run(
        "8e3c9e2c-b67d-42da-b456-1de39d7289fb",
        checkpoint_id="cp_1",
    )
    resumed = runtime.resume_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    cancelled = runtime.cancel_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")
    approved = runtime.approve_agent_run("8e3c9e2c-b67d-42da-b456-1de39d7289fb")

    assert isinstance(plan, DecisionPlanOutput)
    assert recommendation["recommended_action"] == "expand"
    assert scored["score"] == 0.77
    assert len(batch) == 2
    assert compared["winner"] == "stretch"
    assert isinstance(me, dict)
    assert me["user"]["email"] == "owner@example.com"
    assert me["org"]["plan"] == "enterprise"
    assert isinstance(usage, UsageOutput)
    assert limits["plan"] == "enterprise"
    assert len(api_keys) == 1
    assert isinstance(api_keys[0], APIKeyInfoOutput)
    assert isinstance(created_api_key, APIKeyCreatedOutput)
    assert revoked_api_key == {}
    assert isinstance(models, LLMModelListOutput)
    assert isinstance(bridge, ArtifactBridgeResolveOutput)
    assert isinstance(tokens, TokenizeOutput)
    assert isinstance(token_count, CountTokensOutput)
    assert isinstance(completion, ChatCompletionsOutput)
    assert all(isinstance(item, ChatCompletionsStreamChunkOutput) for item in stream_completion)
    assert isinstance(response, ResponsesOutput)
    assert all(isinstance(item, ResponseStreamEventOutput) for item in stream_response)
    assert isinstance(embeddings, EmbeddingsOutput)
    assert isinstance(similarity, EmbeddingSimilarityOutput)
    assert isinstance(deployment_regions, DeploymentRegionsOutput)
    assert isinstance(deployment, DeploymentOutput)
    assert isinstance(created_deployment, DeploymentOutput)
    assert isinstance(deployment_cost, DeploymentCostOutput)
    assert isinstance(deleted_deployment, DeploymentDeleteOutput)
    assert isinstance(logged_decision, DecisionLogOutput)
    assert isinstance(listed_decisions, DecisionListOutput)
    assert isinstance(fetched_decision, DecisionLogOutput)
    assert isinstance(recorded_outcome, DecisionLogOutput)
    assert isinstance(execution_receipt, ExecutionReceiptOutput)
    assert isinstance(rerank, RerankResponseOutput)
    assert isinstance(created, AgentRunOutput)
    assert isinstance(listed_runs, AgentRunListOutput)
    assert isinstance(fetched, AgentRunOutput)
    assert isinstance(events, AgentRunEventsOutput)
    assert all(isinstance(item, AgentRunStreamEventOutput) for item in streamed_events)
    assert isinstance(checkpoint_query, AgentRunCheckpointListResponseOutput)
    assert isinstance(mission_events, AgentRunMissionEventsOutput)
    assert isinstance(mission_event_query, AgentRunMissionEventListResponseOutput)
    assert isinstance(telemetry, AgentRunTelemetryOutput)
    assert isinstance(telemetry_query, AgentRunTelemetryListOutput)
    assert checkpoints.total_checkpoints == 2
    assert checkpoint_query.total == 1
    assert checkpoint_query.data[0].run_status == "completed"
    assert checkpoint_query.data[0].checkpoint_id == "cp_2"
    assert replay.replay_status == "matched"
    assert forked.source_checkpoint_id == "cp_1"
    assert isinstance(resumed, AgentRunOutput)
    assert isinstance(cancelled, AgentRunOutput)
    assert isinstance(approved, AgentRunOutput)
    assert listed_runs.total == 1
    assert listed_runs.data[0].status == "requires_approval"
    assert plan.recommended_action == "Expand sales coverage"
    assert models.data[0].id == "text.tokenizer"
    assert tokens.tokens == ["expand", "sales", "coverage"]
    assert stream_completion[0].choices[0].delta.role == "assistant"
    assert stream_completion[-1].choices[0].finish_reason == "stop"
    assert stream_completion[0].provider_backend is None
    assert stream_completion[0].provider_model_id is None
    assert stream_response[0].type == "response.created"
    assert stream_response[-1].response is not None
    assert stream_response[-1].response.status == "completed"
    assert stream_response[0].response is not None
    assert stream_response[0].response.provider_backend is None
    assert stream_response[0].response.provider_model_id is None
    assert usage.org_id == "08f7453b-7a11-42d5-8b53-4700afbb7f58"
    assert api_keys[0].id == "79fc2a0b-6402-4137-b637-b76ee5e745bf"
    assert api_keys[0].device_limit == 2
    assert created_api_key.raw_key == "de_live_abcd_secret_value"
    assert deployment_regions.providers[0].regions[0].id == "algenta-shared"
    assert logged_decision.policy_snapshot_id == "policy-v1"
    assert listed_decisions.decisions[0].schema_snapshot_id == "schema-v1"
    assert fetched_decision.manifest_version == "runtime-manifest-v1"
    assert deployment_regions.providers[0].regions[0].name == "Algenta Shared"
    assert deployment.deployment_id == "dep_123"
    assert created_deployment.status == "requested"
    assert deployment_cost.month == 5
    assert deleted_deployment.status == "deprovisioning"
    assert logged_decision.id == "decision_123"
    assert listed_decisions.decisions[0].id == "decision_123"
    assert fetched_decision.context == "Launch planning"
    assert recorded_outcome.outcome_delta == 13_000.0
    assert execution_receipt.execution_status == "delivered"
    assert execution_receipt.policy_snapshot_id == "execution-policy-v1-r2:abcd1234abcd1234"
    assert deleted_decision == {}
    assert rerank.data[0].id == "doc-1"
    assert events.total_events == 1
    assert mission_events.total_events == 1
    assert mission_events.data[0].event_message == "Agent run created."
    assert mission_event_query.total == 1
    assert mission_event_query.data[0].run_status == "completed"
    assert telemetry.total_batches == 1
    assert telemetry.data[0].telemetry_kind == "agent_run_completion"
    assert telemetry_query.total == 1
    assert telemetry_query.data[0].module_name == "agent_run_service"
    assert streamed_events[0].event is not None
    assert streamed_events[0].event.event_type == "run_created"
    assert streamed_events[-1].status == "completed"
    assert created.latest_checkpoint_id == "cp_2"
    assert created.steps[0].action == "Planning execution for: Search the knowledge base"
    assert created.steps[1].tool_name == "search"
    assert approved.status == "completed"
    assert models.data[0].provider_backend is None
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
    assert bridge.status == "not_cached"
    assert bridge.auth_env_var_used == "HF_TOKEN"
    assert completion.provider_backend is None
    assert completion.provider_model_id is None
    assert completion.provider_attempts == []
    assert response.provider_backend is None
    assert response.provider_model_id is None
    assert response.provider_attempts == []
    assert response.output[0].provider_backend is None
    assert response.output[0].provider_model_id is None
    assert response.output[0].provider_attempts == []
    assert embeddings.provider_backend is None
    assert embeddings.provider_model_id is None


