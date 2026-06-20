"""Tests for test_algenta_runtime: runtime_api_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-3/tests/test_algenta_runtime.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_helpers import *  # noqa: F401,F403


def test_runtime_api_client_shutdown_clears_global_mojo_pool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from apps.api_server.compute.mojo_pool import MojoEngineError, get_pool_sync

    fake_auth = {
        "org_id": "org_runtime_api",
        "role": "owner",
        "user_id": "u1",
        "key_id": "k1",
    }
    fastapi_app.dependency_overrides[get_current_org] = lambda: fake_auth
    fastapi_app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(reg, "_SOURCES_DIR", tmp_path / "sources")
    asyncio.run(_clear_runtime_api_caches())

    with SyncASGIClient(
        fastapi_app,
        headers={
            "Authorization": "Bearer de_test_runtime",
            "Content-Type": "application/json",
        },
        manage_lifespan=True,
        raise_app_exceptions=False,
    ):
        mojo_pool = getattr(fastapi_app.state, "mojo_pool", None)
        if mojo_pool is not None:
            assert get_pool_sync().running is True
        else:
            with pytest.raises(MojoEngineError, match="Mojo pool not initialized"):
                get_pool_sync()

    with pytest.raises(MojoEngineError, match="Mojo pool not initialized"):
        get_pool_sync()
    assert getattr(fastapi_app.state, "mojo_pool", None) is None
    assert getattr(fastapi_app.state, "redis", None) is None

    asyncio.run(_clear_runtime_api_caches())
    fastapi_app.dependency_overrides.clear()


def test_runtime_api_mode_requires_sdk_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALGENTA_API_KEY", raising=False)
    monkeypatch.delenv("DE_API_KEY", raising=False)
    runtime = Runtime(mode="api")

    with pytest.raises(RuntimeConfigurationError, match="require an API key"):
        runtime.resolve({"metric": "revenue"})


def test_runtime_api_mode_wraps_direct_client(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    captured_verify: dict[str, object] | None = None
    captured_query: dict[str, object] | None = None

    class _FakeClient:
        def resolve(self, request: dict[str, object]) -> object:
            assert request == {
                "preferred_source": "orders",
                "allow_org_scope": True,
                "metric": {"role": "metric", "hint": "revenue"},
                "group_by": ["product_line"],
            }
            return SimpleNamespace(
                model_dump=lambda: {
                    "resolved_plan": {
                        "source_name": "orders",
                        "metric_column": "revenue",
                        "aggregation": "sum",
                        "group_column": "product_line",
                        "schema_revision": "schema_123",
                        "constraints": {},
                        "order": "desc",
                    },
                    "confidence": 1.0,
                    "plan": ["Use source 'orders'."],
                    "explanation": ["Resolved metric 'revenue' to 'revenue'."],
                    "latency_ms": 12.5,
                    "decision_path": "exact_spec",
                    "schema_revision": "schema_123",
                    "validated": True,
                    "deterministic_scope": "api_registered_source",
                    "confidence_source": "schema_match",
                    "clarification_required": False,
                    "rejection_reason": None,
                    "request_id": "req_123",
                    "intent_signature": "intent_123",
                    "plan_hash": "plan_123",
                    "source_set": ["orders"],
                    "join_path": [],
                    "planner_mode": "runtime",
                    "resolved_source": "orders",
                    "resolved_column": "revenue",
                    "resolved_role": "measure",
                    "candidates": [],
                    "source_scores": {"orders": 1.0},
                }
            )

        def verify(self, request: dict[str, object]) -> object:
            nonlocal captured_verify
            captured_verify = request
            return SimpleNamespace(
                model_dump=lambda: {
                    "valid": True,
                    "errors": [],
                    "suggestions": [],
                    "resolved": {"source_name": "orders"},
                    "latency_ms": 1.0,
                    "verified": True,
                    "request_id": "req_verify",
                    "schema_revision": "schema_123",
                    "plan_hash": "plan_123",
                    "verification_mode": "assist",
                    "rejection_reason": None,
                }
            )

        def query(self, request: dict[str, object]) -> object:
            nonlocal captured_query
            captured_query = request
            assert request["resolved_plan"]["metric_column"] == "revenue"
            return SimpleNamespace(
                model_dump=lambda: {
                    "result": [{"product_line": "Electronics", "revenue": 100.0}],
                    "result_type": "table",
                    "confidence": 1.0,
                    "plan": ["Execute exact plan."],
                    "resolved_column": "revenue",
                    "resolved_role": "measure",
                    "resolved_source": "orders",
                    "row_count": 1,
                    "ambiguous": False,
                    "exact_spec": True,
                    "explanation": ["Executed deterministic query."],
                    "latency_ms": 4.2,
                    "decision_path": "exact_spec",
                    "plan_hash": "plan_123",
                    "validated": True,
                    "deterministic_scope": "api_registered_source",
                    "confidence_source": "exact_execution",
                    "schema_revision": "schema_123",
                    "candidates": [],
                    "source_scores": {"orders": 1.0},
                    "clarification_required": False,
                    "rejection_reason": None,
                    "request_id": "req_123",
                    "source_set": ["orders"],
                    "join_path": [],
                    "planner_mode": "runtime",
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    plan = runtime.resolve(
        {"source_name": "orders", "metric": "revenue", "group_by": "product_line"}
    )
    verified = runtime.verify(plan)
    result = runtime.query(plan)

    assert plan.resolved_plan is not None
    assert verified.valid is True
    assert result.result[0]["revenue"] == 100.0
    assert captured_verify is not None
    assert captured_verify["resolved_plan"]["source_name"] == "orders"
    assert captured_verify["resolved_plan"]["metric_column"] == "revenue"
    assert captured_verify["resolved_plan"]["group_column"] == "product_line"
    assert captured_verify["resolved_plan"]["schema_revision"] == "schema_123"
    assert captured_verify["resolved_plan"]["aggregation"] == "sum"
    assert captured_verify["resolved_plan"]["constraints"] == {}
    assert captured_verify["resolved_plan"]["order"] == "desc"
    assert captured_query == captured_verify


def test_runtime_api_mode_exact_resolve_reuses_cached_source_schema_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    runtime._remember_api_registration(
        SourceRegistration(
            source_id="src_1",
            dataset_id="src_1",
            name="orders",
            status="ready",
            source_schema={"fields": ["amount", "customer"]},
            planner_schema_revision="planner_rev_1",
        )
    )

    class _FakeClient:
        def __init__(self) -> None:
            self.source_schema_calls = 0
            self.resolve_calls = 0

        def _request(self, method: str, path: str):  # type: ignore[no-untyped-def]
            assert method == "GET"
            assert path == "/v1/sources/src_1"
            self.source_schema_calls += 1
            return {"entry": {"source_schema_revision": "source_rev_1"}}

        def resolve(self, request: dict[str, object]) -> object:
            self.resolve_calls += 1
            raise AssertionError(
                f"exact runtime resolve should not hit client.resolve: {request!r}"
            )

    client = _FakeClient()
    monkeypatch.setattr(runtime, "_client", lambda: client)

    request = {
        "source_name": "orders",
        "metric": "amount",
        "group_by": "customer",
        "aggregation": "sum",
    }
    first = runtime.resolve(request)
    second = runtime.resolve(request)

    assert first.resolved_plan is not None
    assert second.resolved_plan is not None
    assert first.planner_mode == "runtime_exact_spec"
    assert second.planner_mode == "runtime_exact_spec"
    assert first.resolved_plan.schema_revision == "source_rev_1"
    assert second.resolved_plan.schema_revision == "source_rev_1"
    assert client.source_schema_calls == 1
    assert client.resolve_calls == 0


def test_runtime_api_mode_re_registration_invalidates_cached_source_schema_revision() -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    runtime._api_source_schema_revision_cache["src_1"] = "stale_rev"

    runtime._remember_api_registration(
        SourceRegistration(
            source_id="src_1",
            dataset_id="src_1",
            name="orders",
            status="ready",
            source_schema={"fields": ["amount", "customer"]},
            planner_schema_revision="planner_rev_2",
        )
    )

    assert runtime._api_source_schema_revision_cache == {}


def test_runtime_api_mode_fuzzy_resolve_skips_source_schema_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    runtime._remember_api_registration(
        SourceRegistration(
            source_id="src_1",
            dataset_id="src_1",
            name="orders",
            status="ready",
            source_schema={"fields": ["amount", "customer"]},
            planner_schema_revision="planner_rev_1",
        )
    )
    captured_resolve: list[dict[str, object]] = []

    class _FakeClient:
        def _request(self, method: str, path: str):  # type: ignore[no-untyped-def]
            raise AssertionError(
                f"fuzzy runtime resolve must not fetch source schema revision: {method} {path}"
            )

        def resolve(self, request: dict[str, object]) -> object:
            captured_resolve.append(request)
            return SimpleNamespace(
                model_dump=lambda: {
                    "resolved_plan": {
                        "source_name": "orders",
                        "metric_column": "amount",
                        "aggregation": "sum",
                        "group_column": "customer",
                        "schema_revision": "schema_123",
                        "constraints": {},
                        "order": "desc",
                    },
                    "confidence": 0.91,
                    "plan": ["Use source 'orders'."],
                    "explanation": ["Resolved fuzzy metric 'gross_revenue' to 'amount'."],
                    "latency_ms": 12.5,
                    "decision_path": "schema_match",
                    "schema_revision": "schema_123",
                    "validated": True,
                    "deterministic_scope": "api_registered_source",
                    "confidence_source": "schema_match",
                    "clarification_required": False,
                    "rejection_reason": None,
                    "request_id": "req_123",
                    "intent_signature": "intent_123",
                    "plan_hash": "plan_123",
                    "source_set": ["orders"],
                    "join_path": [],
                    "planner_mode": "runtime",
                    "resolved_source": "orders",
                    "resolved_column": "amount",
                    "resolved_role": "measure",
                    "candidates": [],
                    "source_scores": {"orders": 1.0},
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    resolved = runtime.resolve(
        {
            "source_name": "orders",
            "metric": "gross_revenue",
            "group_by": "customer",
            "aggregation": "sum",
        }
    )

    assert resolved.resolved_plan is not None
    assert resolved.planner_mode == "runtime"
    assert captured_resolve == [
        {
            "preferred_source": "orders",
            "allow_org_scope": True,
            "metric": {"role": "metric", "hint": "gross_revenue"},
            "group_by": ["customer"],
            "aggregation": "sum",
        }
    ]


def test_runtime_api_mode_real_public_rest_connect_resolve_verify_query(
    runtime_api_client: _AsgiRuntimeApiClient,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test_runtime", base_url="http://test")
    runtime._api_client = runtime_api_client

    registration = runtime.connect(PUBLIC_REST_CONNECTION, name="weather_stations")
    assert registration.status == "registered"
    assert registration.row_count is not None
    assert registration.row_count > 0

    plan = runtime.resolve(
        {
            "source_name": registration.name,
            "metric": _registration_metric_field(registration),
            "aggregation": "count",
        }
    )
    verification = runtime.verify(plan)
    result = runtime.query(plan)

    assert plan.resolved_plan is not None
    assert plan.validated is True
    assert verification.valid is True
    assert result.validated is True
    assert result.result_type == "scalar"
    assert _result_scalar_value(result.result) == pytest.approx(float(registration.row_count))


def test_runtime_api_mode_query_metadata_batch_and_sql_report_use_typed_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    seen: dict[str, object] = {}

    class _FakeClient:
        def query_with_metadata(self, request: dict[str, object]) -> object:
            seen["query_with_metadata"] = request
            return SimpleNamespace(
                model_dump=lambda: {
                    "data": {
                        "result": {"value": 97.2},
                        "result_type": "scalar",
                        "confidence": 1.0,
                        "plan": ["Execute exact plan."],
                        "resolved_column": "otp_rate",
                        "resolved_role": "metric",
                        "resolved_source": "otp_events",
                        "row_count": 1,
                        "ambiguous": False,
                        "exact_spec": True,
                        "explanation": ["Executed deterministic query."],
                        "latency_ms": 12.3,
                        "decision_path": "exact_spec",
                        "plan_hash": "plan_otp",
                        "validated": True,
                        "deterministic_scope": "api_registered_source",
                        "confidence_source": "exact_execution",
                        "request_id": "req_query",
                    },
                    "metadata": {
                        "request_id": "req_query",
                        "latency_ms": 12.3,
                        "tokens_in": 120,
                        "tokens_out": 14,
                        "cost_usd": 0.0042,
                        "cache_hit": True,
                    },
                    "headers": {"x-request-id": "req_query"},
                }
            )

        def query_batch(self, request: dict[str, object]) -> object:
            seen["query_batch"] = request
            return SimpleNamespace(
                model_dump=lambda: {
                    "request_id": "req_batch",
                    "results": [
                        {
                            "key": "overall_otp",
                            "data": {
                                "result": {"value": 97.2},
                                "result_type": "scalar",
                                "confidence": 1.0,
                                "plan": ["Execute exact plan."],
                                "resolved_column": "otp_rate",
                                "resolved_role": "metric",
                                "resolved_source": "otp_events",
                                "row_count": 1,
                                "ambiguous": False,
                                "exact_spec": True,
                                "explanation": ["Executed deterministic query."],
                                "latency_ms": 12.3,
                                "decision_path": "exact_spec",
                                "plan_hash": "plan_otp",
                                "validated": True,
                                "deterministic_scope": "api_registered_source",
                                "confidence_source": "exact_execution",
                                "request_id": "req_batch_item",
                            },
                            "metadata": {
                                "request_id": "req_batch_item",
                                "latency_ms": 12.3,
                            },
                        },
                        {
                            "key": "avg_delay",
                            "error": {
                                "code": "metric_not_found",
                                "message": "Metric average_delay_minutes was not found.",
                                "details": {"metric": "average_delay_minutes"},
                            },
                        },
                    ],
                }
            )

        def query_sql_report(self, request: dict[str, object]) -> object:
            seen["query_sql_report"] = request
            return SimpleNamespace(
                model_dump=lambda: {
                    "columns": ["flight_month", "otp_rate_pct"],
                    "rows": [{"flight_month": "2026-04-01", "otp_rate_pct": 97.2}],
                    "row_count": 1,
                    "truncated": False,
                    "request_id": "req_report",
                    "latency_ms": 8.5,
                }
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with_metadata = runtime.query_with_metadata(
        {"dataset_id": "otp_events", "metric": {"role": "metric", "hint": "otp_rate"}}
    )
    batch = runtime.query_batch(
        {
            "defaults": {"dataset_id": "otp_events"},
            "queries": [
                {
                    "key": "overall_otp",
                    "request": {"metric": {"role": "metric", "hint": "otp_rate"}},
                },
                {
                    "key": "avg_delay",
                    "request": {
                        "metric": {"role": "metric", "hint": "average_delay_minutes"},
                    },
                },
            ],
        }
    )
    report = runtime.query_sql_report(
        {
            "sources": [{"dataset_id": "otp_events", "alias": "otp"}],
            "sql": "select flight_month, otp_rate_pct from otp",
            "max_rows": 100,
        }
    )

    assert isinstance(with_metadata, QueryWithMetadataOutput)
    assert with_metadata.metadata.tokens_in == 120
    assert with_metadata.headers["x-request-id"] == "req_query"
    assert isinstance(batch, QueryBatchOutput)
    assert batch.results[0].data is not None
    assert batch.results[1].error is not None
    assert batch.results[1].error.code == "metric_not_found"
    assert isinstance(report, QuerySqlReportOutput)
    assert report.columns == ["flight_month", "otp_rate_pct"]
    assert seen["query_with_metadata"] == {
        "dataset_id": "otp_events",
        "metric": {"role": "metric", "hint": "otp_rate"},
    }
    assert seen["query_batch"] == {
        "defaults": {"dataset_id": "otp_events"},
        "queries": [
            {"key": "overall_otp", "request": {"metric": {"role": "metric", "hint": "otp_rate"}}},
            {
                "key": "avg_delay",
                "request": {"metric": {"role": "metric", "hint": "average_delay_minutes"}},
            },
        ],
    }
    assert seen["query_sql_report"] == {
        "sources": [{"dataset_id": "otp_events", "alias": "otp"}],
        "sql": "select flight_month, otp_rate_pct from otp",
        "max_rows": 100,
    }


def test_runtime_api_mode_get_contract_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    expected_payload = _platform_contract_payload()

    class _FakeClient:
        def get_contract(self) -> object:
            return SimpleNamespace(model_dump=lambda: expected_payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    contract = runtime.get_contract()

    assert isinstance(contract, PlatformContractOutput)
    assert contract.primary_data_query_contract["api"]["contract_endpoint"] == "/v1/meta/contract"
    assert contract.primary_data_query_contract["mcp"]["contract_tool"] == "get_contract"
    assert_manifest_backed_integrations(contract.integrations)


def test_runtime_api_mode_get_contract_rejects_invalid_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeClient:
        def get_contract(self) -> object:
            def _payload() -> dict[str, object]:
                payload = _platform_contract_payload()
                payload["api_key_prefixes"] = {"live": "de_live_"}
                return payload

            return SimpleNamespace(model_dump=_payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()
    assert exc.value.code == "invalid_contract_payload"


def test_runtime_api_mode_get_contract_rejects_invalid_nested_contract_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeClient:
        def get_contract(self) -> object:
            def _payload() -> dict[str, object]:
                payload = _platform_contract_payload()
                payload["primary_data_query_contract"]["recommended_flows"].pop(
                    "machine_readable_contract"
                )
                return payload

            return SimpleNamespace(model_dump=_payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()
    assert exc.value.code == "invalid_contract_payload"


def test_runtime_api_mode_get_contract_rejects_invalid_typed_contract_model_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision_engine = importlib.import_module("decision_engine")
    typed_payload = decision_engine.PlatformContractResult.model_validate(
        _platform_contract_payload()
    ).model_copy(
        update={
            "defaults": {
                "read_only_default": "nope",
                "write_confirmation_required": True,
                "plan_limits": {},
            }
        }
    )
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeClient:
        def get_contract(self) -> object:
            return typed_payload

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
            runtime.get_contract()

    assert caught == []
    assert exc.value.code == "invalid_contract_payload"


def test_runtime_api_mode_get_contract_rejects_tuple_backed_contract_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeClient:
        def get_contract(self) -> object:
            payload = _platform_contract_payload()
            payload["compatibility"]["legacy_headers"] = ("X-Deprecated-Key",)
            return payload

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()

    assert exc.value.code == "invalid_contract_payload"
    assert exc.value.details["cause"] == "compatibility.legacy_headers"
    assert exc.value.validation_errors[0]["message"] == "must be a list of non-empty strings."


def test_runtime_api_mode_get_contract_normalizes_client_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeContractError(Exception):
        def __init__(self) -> None:
            super().__init__("OpenAPI contract fallback is missing x-primary-data-query-contract.")
            self.error_code = "contract_extension_missing"

    class _FakeClient:
        def get_contract(self) -> object:
            raise _FakeContractError()

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()
    assert exc.value.code == "invalid_contract_payload"
    assert exc.value.details["source_error_code"] == "contract_extension_missing"


def test_runtime_api_mode_get_contract_preserves_upstream_contract_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeContractError(Exception):
        def __init__(self) -> None:
            super().__init__(
                "OpenAPI contract fallback returned an invalid payload: "
                "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
            )
            self.error_code = "invalid_contract_payload"
            self.status_code = 0
            self.details = {
                "cause": "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
                "validation_errors": [
                    {
                        "path": (
                            "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
                        ),
                        "message": "Field required",
                        "type": "missing",
                    }
                ],
            }

    class _FakeClient:
        def get_contract(self) -> object:
            raise _FakeContractError()

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid payload") as exc:
        runtime.get_contract()
    assert exc.value.code == "invalid_contract_payload"
    assert exc.value.details["source_error_code"] == "invalid_contract_payload"
    assert exc.value.details["source_status_code"] == 0
    assert exc.value.details["source_error_details"] == {
        "cause": "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
        "validation_errors": [
            {
                "path": "primary_data_query_contract.runtime_sdk.typescript.runtime_class",
                "message": "Field required",
                "type": "missing",
            }
        ],
    }
    assert exc.value.validation_errors[0]["path"] == (
        "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    )
    assert exc.value.field_errors[0]["path"] == (
        "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    )


@pytest.mark.parametrize(
    ("method_name", "client_method_name"),
    [
        ("get_runtime_manifest", "get_runtime_manifest"),
        ("get_runtime_modules", "get_runtime_modules"),
        ("get_runtime_benchmarks", "get_runtime_benchmarks"),
        ("get_runtime_release_validation", "get_runtime_release_validation"),
    ],
)
def test_runtime_api_mode_runtime_proof_surfaces_normalize_client_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    client_method_name: str,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeRuntimeProofError(Exception):
        def __init__(self) -> None:
            super().__init__("signed runtime proof payload is invalid")
            self.error_code = "invalid_runtime_contract_payload"

    class _FakeClient:
        def __getattr__(self, name: str):
            if name != client_method_name:
                raise AttributeError(name)

            def _raise_error() -> object:
                raise _FakeRuntimeProofError()

            return _raise_error

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc:
        getattr(runtime, method_name)()
    assert exc.value.code == "invalid_runtime_contract_payload"
    assert exc.value.details["source_error_code"] == "invalid_runtime_contract_payload"


