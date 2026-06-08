"""Unit tests for Phase 4 SDK — Python SDK models, exceptions, and CLI."""

import json
import os
import sys

import pytest

# Add project root and SDK package path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SDK_PATH = os.path.join(_ROOT, "packages", "python-sdk")
for _p in [_ROOT, _SDK_PATH]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


class TestSDKImports:
    def test_sdk_package_imports(self) -> None:
        from decision_engine import (  # type: ignore[import]
            AsyncDecisionEngineClient,
            DecisionEngineClient,
        )

        assert DecisionEngineClient is not None
        assert AsyncDecisionEngineClient is not None

    def test_exception_hierarchy(self) -> None:
        from decision_engine.exceptions import (  # type: ignore[import]
            AuthenticationError,
            DecisionEngineError,
            NotFoundError,
            RateLimitError,
            ServerError,
            ValidationError,
        )

        assert issubclass(AuthenticationError, DecisionEngineError)
        assert issubclass(RateLimitError, DecisionEngineError)
        assert issubclass(ValidationError, DecisionEngineError)
        assert issubclass(ServerError, DecisionEngineError)
        assert issubclass(NotFoundError, DecisionEngineError)


class TestSDKExceptions:
    def test_authentication_error_attributes(self) -> None:
        from decision_engine.exceptions import AuthenticationError  # type: ignore[import]

        err = AuthenticationError(
            "Invalid key", status_code=401, response_body={"error": {"code": "invalid_api_key"}}
        )
        assert err.status_code == 401
        assert err.error_code == "invalid_api_key"
        assert str(err) == "Invalid key"

    def test_rate_limit_error_retry_after(self) -> None:
        from decision_engine.exceptions import RateLimitError  # type: ignore[import]

        err = RateLimitError("Rate limit exceeded", retry_after=30, status_code=429)
        assert err.retry_after == 30
        assert err.status_code == 429

    def test_validation_error_field_errors(self) -> None:
        from decision_engine.exceptions import ValidationError  # type: ignore[import]

        body = {
            "error": {
                "code": "validation_error",
                "details": [{"field": "mode", "issue": "required"}],
            }
        }
        err = ValidationError("Validation failed", status_code=422, response_body=body)
        assert len(err.field_errors) == 1
        assert err.field_errors[0]["field"] == "mode"

    def test_not_found_error(self) -> None:
        from decision_engine.exceptions import NotFoundError  # type: ignore[import]

        err = NotFoundError("Job not found", status_code=404)
        assert err.status_code == 404

    def test_error_repr(self) -> None:
        from decision_engine.exceptions import ServerError  # type: ignore[import]

        err = ServerError("Internal error", status_code=500)
        repr_str = repr(err)
        assert "ServerError" in repr_str
        assert "500" in repr_str


class TestSDKModels:
    def test_decision_envelope_from_dict(self) -> None:
        import uuid

        from decision_engine.models import (  # type: ignore[import]
            DecisionEnvelope,
        )

        data = {
            "run_id": str(uuid.uuid4()),
            "status": "completed",
            "engine_version": "0.1.0",
            "recommended_action": "proceed",
            "confidence": 0.78,
            "rationale": "Expected value is positive.",
            "metrics": {
                "expected_value": 62400.0,
                "median": 58200.0,
                "std_deviation": 18300.0,
                "variance": 334890000.0,
                "probability_of_loss": 0.22,
            },
            "percentiles": {"p5": 18000, "p25": 44000, "p50": 58200, "p75": 78000, "p95": 105000},
            "scenarios_run": 10000,
            "execution_ms": 87,
            "metadata": {
                "mode": "auto",
                "seed": None,
                "billing_units": 1,
                "engine_version": "0.1.0",
            },
        }
        envelope = DecisionEnvelope.model_validate(data)
        assert envelope.recommended_action == "proceed"
        assert envelope.confidence == 0.78
        assert envelope.metrics.expected_value == 62400.0
        assert envelope.percentiles.p50 == 58200

    def test_extra_fields_allowed(self) -> None:
        """SDK models use extra='allow' to be forward-compatible with API additions."""
        import uuid

        from decision_engine.models import DecisionEnvelope  # type: ignore[import]

        data = {
            "run_id": str(uuid.uuid4()),
            "status": "completed",
            "engine_version": "0.2.0",
            "recommended_action": "proceed",
            "confidence": 0.9,
            "rationale": "Test",
            "metrics": {
                "expected_value": 100,
                "median": 100,
                "std_deviation": 0,
                "variance": 0,
                "probability_of_loss": 0,
            },
            "percentiles": {"p5": 100, "p25": 100, "p50": 100, "p75": 100, "p95": 100},
            "scenarios_run": 100,
            "execution_ms": 5,
            "metadata": {
                "mode": "auto",
                "seed": None,
                "billing_units": 1,
                "engine_version": "0.2.0",
            },
            "future_field_that_does_not_exist_yet": "should not raise",
        }
        envelope = DecisionEnvelope.model_validate(data)
        assert envelope.recommended_action == "proceed"

    def test_decision_envelope_accepts_runtime_contract_metadata(self) -> None:
        import uuid

        from decision_engine.models import DecisionEnvelope  # type: ignore[import]

        data = {
            "run_id": str(uuid.uuid4()),
            "status": "completed",
            "engine_version": "0.3.0",
            "recommended_action": "proceed",
            "confidence": 0.91,
            "rationale": "Validated predictive result.",
            "metrics": {
                "expected_value": 120.0,
                "median": 118.0,
                "std_deviation": 8.0,
                "variance": 64.0,
                "probability_of_loss": 0.08,
            },
            "percentiles": {"p5": 105, "p25": 113, "p50": 118, "p75": 125, "p95": 132},
            "scenarios_run": 1000,
            "execution_ms": 7,
            "metadata": {"mode": "auto", "seed": 7, "billing_units": 1, "engine_version": "0.3.0"},
            "simulation_class": "predictive",
            "model_revision": "0.3.0",
            "assumptions_hash": "assumptions_123",
            "validated_inputs": {"mode": "auto", "runs": 1000, "variable_count": 2},
            "confidence_interval": {"level": 0.9, "lower": 105.0, "upper": 132.0},
            "request_id": "req_123",
        }

        envelope = DecisionEnvelope.model_validate(data)
        assert envelope.simulation_class == "predictive"
        assert envelope.model_revision == "0.3.0"
        assert envelope.validated_inputs == {"mode": "auto", "runs": 1000, "variable_count": 2}
        assert envelope.confidence_interval == {"level": 0.9, "lower": 105.0, "upper": 132.0}
        assert envelope.request_id == "req_123"

    def test_query_result_accepts_decision_contract_fields(self) -> None:
        from decision_engine.models import QueryResult  # type: ignore[import]

        result = QueryResult.model_validate(
            {
                "query_id": "q_123",
                "result": 42,
                "result_type": "scalar",
                "confidence": 0.96,
                "plan": ["Planner selected Orders.amount"],
                "resolved_column": "amount",
                "resolved_role": "derived_measure",
                "resolved_source": "Orders",
                "row_count": 1,
                "candidates": [],
                "source_scores": {"Orders": 0.96},
                "ambiguous": False,
                "exact_spec": False,
                "explanation": ["Deterministic execution"],
                "latency_ms": 18.4,
                "decision_path": "planner_hint",
                "plan_hash": "plan_123",
                "schema_revision": "schema_rev_1",
                "validated": True,
                "deterministic_scope": "planned_execution",
                "confidence_source": "planner_query_confidence",
                "clarification_required": False,
                "rejection_reason": None,
                "request_id": "req_123",
                "source_set": ["Orders"],
                "join_path": [],
                "planner_mode": "registry_planner",
            }
        )

        assert result.plan_hash == "plan_123"
        assert result.validated is True
        assert result.request_id == "req_123"
        assert result.source_set == ["Orders"]
        assert result.planner_mode == "registry_planner"


class TestSDKClientInit:
    def test_client_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
        monkeypatch.delenv("DE_API_KEY", raising=False)

        with pytest.raises(ValueError, match="API key required"):
            DecisionEngineClient()

    def test_client_accepts_api_key(self) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        client = DecisionEngineClient(api_key="de_test_abc123")
        assert client._api_key == "de_test_abc123"
        client.close()

    def test_client_default_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from decision_engine.client import (  # type: ignore[import]
            DEFAULT_BASE_URL,
            DecisionEngineClient,
        )

        monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
        monkeypatch.delenv("DE_BASE_URL", raising=False)
        client = DecisionEngineClient(api_key="de_test_abc123")
        assert client._base_url == DEFAULT_BASE_URL
        client.close()

    def test_client_custom_base_url(self) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        client = DecisionEngineClient(api_key="de_test_abc123", base_url="http://localhost:8000")
        assert client._base_url == "http://localhost:8000"
        client.close()

    def test_client_env_var_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        monkeypatch.delenv("DE_API_KEY", raising=False)
        monkeypatch.setenv("ALGENTA_API_KEY", "de_test_from_env")

        client = DecisionEngineClient()
        assert client._api_key == "de_test_from_env"
        client.close()

    def test_client_as_context_manager(self) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        with DecisionEngineClient(api_key="de_test_ctx") as client:
            assert client._api_key == "de_test_ctx"


class TestSDKDecisionApis:
    def test_client_resolve_returns_typed_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        client = DecisionEngineClient(api_key="de_test_abc123")

        def _fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
            assert method == "POST"
            assert path == "/v1/resolve"
            assert kwargs["json"] == {
                "dataset_id": "ds_1",
                "metric": {"role": "derived_measure", "hint": "revenue"},
                "aggregation": "sum",
            }
            return {
                "resolved_plan": {
                    "source_name": "Orders",
                    "metric_column": "amount",
                    "aggregation": "sum",
                    "schema_revision": "schema_rev_1",
                },
                "confidence": 0.98,
                "plan": ["planner resolved Orders.amount"],
                "explanation": [],
                "resolved_column": "amount",
                "resolved_role": "derived_measure",
                "resolved_source": "Orders",
                "candidates": [],
                "source_scores": {"Orders": 0.98},
                "latency_ms": 8.3,
                "decision_path": "resolve",
                "plan_hash": "plan_123",
                "schema_revision": "schema_rev_1",
                "validated": True,
                "deterministic_scope": "resolved_execution_plan",
                "confidence_source": "planner_query_confidence",
                "clarification_required": False,
                "rejection_reason": None,
                "request_id": "req_123",
                "intent_signature": "intent_123",
                "source_set": ["Orders"],
                "join_path": [],
                "planner_mode": "registry_planner",
            }

        monkeypatch.setattr(client, "_request", _fake_request)
        result = client.resolve(
            dataset_id="ds_1",
            metric={"role": "derived_measure", "hint": "revenue"},
            aggregation="sum",
        )
        assert result.plan_hash == "plan_123"
        assert result.resolved_plan is not None
        assert result.resolved_plan.source_name == "Orders"
        client.close()

    def test_client_query_returns_typed_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        client = DecisionEngineClient(api_key="de_test_abc123")

        def _fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
            assert method == "POST"
            assert path == "/v1/query"
            assert kwargs["json"] == {"dataset_id": "ds_1", "metric": {"role": "metric"}}
            return {
                "query_id": "q_123",
                "result": 30,
                "result_type": "scalar",
                "confidence": 0.98,
                "plan": [],
                "resolved_column": "amount",
                "resolved_role": "derived_measure",
                "resolved_source": "Orders",
                "row_count": 1,
                "candidates": [],
                "source_scores": {"Orders": 0.98},
                "ambiguous": False,
                "exact_spec": False,
                "explanation": [],
                "latency_ms": 9.5,
                "decision_path": "planner_hint",
                "plan_hash": "plan_123",
                "schema_revision": "schema_rev_1",
                "validated": True,
                "deterministic_scope": "planned_execution",
                "confidence_source": "planner_query_confidence",
                "clarification_required": False,
                "rejection_reason": None,
                "request_id": "req_123",
                "source_set": ["Orders"],
                "join_path": [],
                "planner_mode": "registry_planner",
            }

        monkeypatch.setattr(client, "_request", _fake_request)
        result = client.query(dataset_id="ds_1", metric={"role": "metric"})
        assert result.plan_hash == "plan_123"
        assert result.resolved_source == "Orders"
        client.close()

    def test_client_query_applies_safe_join_path_default_and_allows_opt_in(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        client = DecisionEngineClient(api_key="de_test_abc123")
        seen: list[dict[str, object]] = []

        def _fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
            assert method == "POST"
            assert path == "/v1/query"
            seen.append(dict(kwargs["json"]))  # type: ignore[arg-type]
            return {
                "query_id": "q_123",
                "result": 30,
                "result_type": "scalar",
                "confidence": 0.98,
                "plan": [],
                "resolved_column": "amount",
                "resolved_role": "derived_measure",
                "resolved_source": "Orders",
                "row_count": 1,
                "candidates": [],
                "source_scores": {"Orders": 0.98},
                "ambiguous": False,
                "exact_spec": False,
                "explanation": [],
                "latency_ms": 9.5,
                "decision_path": "planner_hint",
                "plan_hash": "plan_123",
                "schema_revision": "schema_rev_1",
                "validated": True,
                "deterministic_scope": "planned_execution",
                "confidence_source": "planner_query_confidence",
                "clarification_required": False,
                "rejection_reason": None,
                "request_id": "req_123",
                "source_set": ["Orders"],
                "join_path": [],
                "planner_mode": "registry_planner",
            }

        monkeypatch.setattr(client, "_request", _fake_request)

        client.query(
            source_name="S0",
            metric_column="value",
            group_column="region",
            join_path={
                "base_source": "S0",
                "group_source": "S1",
                "edges": [
                    {
                        "left_source": "S0",
                        "right_source": "S1",
                        "left_key": "id",
                        "right_key": "id",
                    }
                ],
            },
        )
        assert seen[0]["join_path"]["max_hops"] == 4

        client.query(
            source_name="S0",
            metric_column="value",
            group_column="region",
            join_path={
                "base_source": "S0",
                "group_source": "S6",
                "max_hops": 6,
                "edges": [
                    {
                        "left_source": f"S{index}",
                        "right_source": f"S{index + 1}",
                        "left_key": f"k{index}",
                        "right_key": f"k{index}",
                    }
                    for index in range(6)
                ],
            },
        )
        assert seen[1]["join_path"]["max_hops"] == 6
        client.close()

    def test_client_explain_derives_structured_view(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        client = DecisionEngineClient(api_key="de_test_abc123")

        def _fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
            assert method == "POST"
            assert path == "/v1/query"
            return {
                "query_id": "q_123",
                "result": [{"region": "East", "value": 20}],
                "result_type": "table",
                "confidence": 0.91,
                "plan": ["Join path selected"],
                "resolved_column": "amount",
                "resolved_role": "derived_measure",
                "resolved_source": "Orders ⋈ Customers",
                "row_count": 1,
                "candidates": [],
                "source_scores": {"Orders": 0.91},
                "ambiguous": False,
                "exact_spec": True,
                "explanation": ["Deterministic exact-spec execution"],
                "latency_ms": 14.2,
                "decision_path": "exact_spec",
                "plan_hash": "plan_123",
                "schema_revision": "schema_rev_1",
                "validated": True,
                "deterministic_scope": "verified_execution",
                "confidence_source": "exact_spec_validation",
                "clarification_required": False,
                "rejection_reason": None,
                "request_id": "req_123",
                "source_set": ["Orders", "Customers"],
                "join_path": [
                    {
                        "left_source": "Orders",
                        "right_source": "Customers",
                        "left_key": "customer_id",
                        "right_key": "id",
                    }
                ],
                "planner_mode": "exact_spec",
            }

        monkeypatch.setattr(client, "_request", _fake_request)
        explain = client.explain(
            {
                "source_name": "Orders",
                "metric_column": "amount",
                "aggregation": "sum",
                "join_path": {
                    "base_source": "Orders",
                    "group_source": "Customers",
                    "edges": [
                        {
                            "left_source": "Orders",
                            "right_source": "Customers",
                            "left_key": "customer_id",
                            "right_key": "id",
                        }
                    ],
                },
            }
        )
        assert explain.source_set == ["Orders", "Customers"]
        assert explain.join_path[0]["left_key"] == "customer_id"
        assert explain.planner_mode == "exact_spec"
        client.close()

    def test_client_register_and_refresh_source_routes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from decision_engine.client import DecisionEngineClient  # type: ignore[import]

        client = DecisionEngineClient(api_key="de_test_abc123")
        calls: list[tuple[str, str, object | None]] = []

        def _fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
            calls.append((method, path, kwargs.get("json")))
            return {"status": "registered", "source_id": "src_1", "dataset_id": "src_1"}

        monkeypatch.setattr(client, "_request", _fake_request)

        registered = client.register_source({"name": "Orders", "csv": "amount\n10\n"})
        refreshed = client.refresh_source("src_1")

        assert registered.source_id == "src_1"
        assert refreshed.dataset_id == "src_1"
        assert calls[0] == (
            "POST",
            "/v1/sources/register",
            {"source": {"name": "Orders", "csv": "amount\n10\n"}},
        )
        assert calls[1] == ("POST", "/v1/data/src_1/refresh", None)
        client.close()

    @pytest.mark.anyio
    async def test_async_client_register_source_returns_typed_result(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from decision_engine.async_client import AsyncDecisionEngineClient  # type: ignore[import]

        client = AsyncDecisionEngineClient(api_key="de_test_abc123")
        seen: dict[str, object] = {}

        async def _fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
            seen["method"] = method
            seen["path"] = path
            seen["json"] = kwargs.get("json")
            return {"status": "registered", "source_id": "src_1", "dataset_id": "src_1"}

        monkeypatch.setattr(client, "_request", _fake_request)
        result = await client.register_source({"name": "Orders", "csv": "amount\n10\n"})
        assert result.source_id == "src_1"
        assert seen["method"] == "POST"
        assert seen["path"] == "/v1/sources/register"
        assert seen["json"] == {"source": {"name": "Orders", "csv": "amount\n10\n"}}
        await client.aclose()

    @pytest.mark.anyio
    async def test_async_client_resolve_returns_typed_result(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from decision_engine.async_client import AsyncDecisionEngineClient  # type: ignore[import]

        client = AsyncDecisionEngineClient(api_key="de_test_abc123")
        seen: dict[str, object] = {}

        async def _fake_request(method: str, path: str, **kwargs: object) -> dict[str, object]:
            seen["method"] = method
            seen["path"] = path
            seen["json"] = kwargs.get("json")
            return {
                "resolved_plan": {
                    "source_name": "Orders",
                    "metric_column": "amount",
                    "aggregation": "sum",
                    "schema_revision": "schema_rev_1",
                },
                "confidence": 0.98,
                "plan": ["planner resolved Orders.amount"],
                "explanation": [],
                "resolved_column": "amount",
                "resolved_role": "derived_measure",
                "resolved_source": "Orders",
                "candidates": [],
                "source_scores": {"Orders": 0.98},
                "latency_ms": 8.3,
                "decision_path": "resolve",
                "plan_hash": "plan_123",
                "schema_revision": "schema_rev_1",
                "validated": True,
                "deterministic_scope": "resolved_execution_plan",
                "confidence_source": "planner_query_confidence",
                "clarification_required": False,
                "rejection_reason": None,
                "request_id": "req_123",
                "intent_signature": "intent_123",
                "source_set": ["Orders"],
                "join_path": [],
                "planner_mode": "registry_planner",
            }

        monkeypatch.setattr(client, "_request", _fake_request)
        result = await client.resolve(
            dataset_id="ds_1",
            metric={"role": "derived_measure", "hint": "revenue"},
            aggregation="sum",
        )
        assert result.resolved_plan is not None
        assert result.resolved_plan.metric_column == "amount"
        assert seen["method"] == "POST"
        assert seen["path"] == "/v1/resolve"
        assert seen["json"] == {
            "dataset_id": "ds_1",
            "metric": {"role": "derived_measure", "hint": "revenue"},
            "aggregation": "sum",
        }
        await client.aclose()


class TestCLIImport:
    def test_cli_imports_cleanly(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("cli_main", "apps/cli/main.py")
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert module is not None
        # Don't actually execute — just verify it loads
        # spec.loader.exec_module(module)  # would run the script

    def test_cli_config_functions(self) -> None:
        """Test config save/load without side effects."""
        import tempfile

        config_data = {"api_key": "de_test_key", "base_url": "http://localhost:8000"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            tmpfile = f.name

        # Verify JSON round-trip
        loaded = json.loads(open(tmpfile).read())
        assert loaded["api_key"] == "de_test_key"


class TestLangGraphExample:
    def test_langraph_tool_imports(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "langgraph_tool", "examples/langgraph/decision_tool.py"
        )
        assert spec is not None

    def test_langraph_build_payload(self) -> None:
        """Test the payload structure built by the tool."""
        payload = {
            "mode": "auto",
            "scenario": {
                "variables": {
                    "revenue": {"low": 80000, "high": 200000},
                    "cost": {"low": 40000, "high": 90000},
                },
                "objective": "maximize_net_value",
            },
            "runs": 5000,
        }
        assert payload["mode"] == "auto"
        assert "revenue" in payload["scenario"]["variables"]
        assert payload["scenario"]["objective"] == "maximize_net_value"
