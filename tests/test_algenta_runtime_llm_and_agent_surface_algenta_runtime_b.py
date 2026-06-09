"""Tests for test_algenta_runtime_llm_and_agent_surface: algenta_runtime_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-3/tests/test_algenta_runtime_llm_and_agent_surface.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_llm_and_agent_surface_helpers import *  # noqa: F401,F403


def test_algenta_runtime_agent_step_parser_accepts_legacy_agent_step_shape() -> None:
    step = AgentRunOutput.from_api(
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

    assert step.steps[0].step_number == 1
    assert step.steps[0].tool_name == "search"
    assert step.steps[0].rationale == "Search is the lowest-risk first step."


def test_algenta_runtime_agent_run_parser_accepts_typed_sdk_datetime_payload() -> None:
    from decision_engine.models_agent_runs import AgentRunResult

    payload = AgentRunResult.model_validate(_make_agent_run_payload("requires_approval", "approve"))
    run = AgentRunOutput.from_api(payload)

    assert run.created_at.startswith("2026-05-24T12:00:00")
    assert run.updated_at.startswith("2026-05-24T12:00:03")
    assert run.steps[1].tool_name == "search"


def test_algenta_runtime_decision_memory_models_accept_typed_sdk_payloads() -> None:
    from decision_engine.models_decision_memory import (
        DecisionListResult,
        DecisionLogResult,
        ExecutionReceiptResult,
    )

    logged = DecisionLogOutput.from_api(DecisionLogResult.model_validate(_make_decision_log_payload()))
    listed = DecisionListOutput.from_api(DecisionListResult.model_validate(_make_decision_list_payload()))
    recorded = DecisionLogOutput.from_api(
        DecisionLogResult.model_validate(_make_recorded_outcome_payload())
    )
    receipt = ExecutionReceiptOutput.from_api(
        ExecutionReceiptResult.model_validate(_make_execution_receipt_payload())
    )

    assert logged.id == "decision_123"
    assert logged.policy_snapshot_id == "policy-v1"
    assert listed.total == 1
    assert listed.decisions[0].schema_snapshot_id == "schema-v1"
    assert recorded.outcome_delta == 13_000.0
    assert recorded.manifest_version == "runtime-manifest-v1"
    assert receipt.response_code == 202
    assert receipt.policy_snapshot_id == "execution-policy-v1-r2:abcd1234abcd1234"
    assert receipt.schema_snapshot_id == "schema-v1"
    assert receipt.manifest_version == "runtime-manifest-v1"


def test_algenta_runtime_deployment_parser_accepts_typed_sdk_datetime_payload() -> None:
    from decision_engine.models_deployments import DeploymentResult

    payload = DeploymentResult.model_validate(_make_deployment_payload())
    deployment = DeploymentOutput.from_api(payload)

    assert deployment.deployment_id == "dep_123"
    assert deployment.org_id == "org_123"
    assert deployment.created_at.startswith("2026-05-24T12:00:00")


def test_algenta_runtime_plan_aligned_api_methods_require_api_transport() -> None:
    runtime = Runtime()

    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.me()
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.usage()
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.limits()
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.list_api_keys()
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.create_api_key(label="Mission Runtime Key")
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.revoke_api_key("key_1")
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.recommend([{"name": "expand"}], metric="profit")
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.list_deployment_regions()
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.score({"mode": "expert", "simulation": {"variables": []}})
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.batch([{"mode": "expert", "simulation": {"variables": []}}])
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.compare([{"name": "base"}], metric="profit")
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.list_models()
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.plan_decision({"metric": "profit"})
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.log_decision({"chosen_action": "expand"})
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.list_decisions()
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.get_decision("decision_123")
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.record_outcome("decision_123", actual_outcome=1.0)
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.execute_decision(
            "decision_123",
            webhook_url="https://hooks.example.test/decision",
        )
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.delete_decision("decision_123")
    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.create_agent_run(task="Search the knowledge base")


def test_algenta_runtime_api_bridge_uses_zero_retry_decision_engine_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")
    created: list[object] = []

    class _FakeDecisionEngineClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            created.append(self)

    fake_module = type("FakeDecisionEngineModule", (), {"DecisionEngineClient": _FakeDecisionEngineClient})
    monkeypatch.setitem(sys.modules, "decision_engine", fake_module)

    first = runtime._client()
    second = runtime._client()

    assert first is second
    assert created == [first]
    assert first.kwargs == {
        "api_key": "de_test",
        "base_url": "http://localhost:8000",
        "max_retries": 0,
    }


def test_algenta_runtime_plan_aligned_api_methods_reject_invalid_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test", base_url="http://localhost:8000")

    class _FakeClient:
        def recommend(self, actions: list[dict[str, object]], **kwargs: object) -> object:
            return "invalid"

        def list_models(self) -> object:
            return {"object": "list", "data": [{"id": "text.tokenizer"}]}

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as recommend_exc_info:
        runtime.recommend([{"name": "expand"}], metric="profit")

    assert recommend_exc_info.value.code == "invalid_runtime_api_payload"
    assert recommend_exc_info.value.details["expected_type"] == "mapping"

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc_info:
        runtime.list_models()

    assert exc_info.value.code == "invalid_runtime_api_payload"
    assert exc_info.value.validation_errors[0]["path"] == "models.item.available"
    assert exc_info.value.field_errors[0]["message"] == "must be a boolean."


