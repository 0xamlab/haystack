"""Tests for test_decision_engine_query_surface: async_decision_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-1/tests/test_decision_engine_query_surface.py during modularization.
"""
from __future__ import annotations

from tests._test_decision_engine_query_surface_helpers import *  # noqa: F401,F403


async def test_async_decision_engine_client_query_metadata_batch_and_sql_report() -> None:
    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    async def _fake_request_response(method: str, path: str, **kwargs):
        assert (method, path) == ("POST", "/v1/query")
        assert kwargs["json"] == {
            "source_name": "orders",
            "metric_column": "revenue",
            "aggregation": "sum",
        }
        return (
            _query_result_payload(),
            type(
                "Response",
                (),
                {
                    "headers": {
                        "X-Input-Tokens": "120",
                        "X-Output-Tokens": "45",
                        "X-Cost-Usd": "0.0025",
                        "X-Cache-Hit": "true",
                    }
                },
            )(),
        )

    async def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("POST", "/v1/query/batch"):
            assert kwargs["json"]["defaults"]["filter"] == {
                "conditions": [{"dimension_hint": "status", "op": "eq", "value": "closed"}]
            }
            return {
                "request_id": "req_batch",
                "results": [
                    {
                        "key": "overall_otp",
                        "data": _query_result_payload(request_id="req_item"),
                        "metadata": {"request_id": "req_item", "latency_ms": 11.0},
                    }
                ],
            }
        if (method, path) == ("POST", "/v1/query/sql-report"):
            return {
                "columns": ["flight_month", "otp_rate_pct"],
                "rows": [{"flight_month": "2026-04-01", "otp_rate_pct": 92.4}],
                "row_count": 1,
                "truncated": False,
                "request_id": "req_sql",
                "latency_ms": 24.1,
            }
        raise AssertionError(f"unexpected request: {(method, path, kwargs)}")

    client._request_response = _fake_request_response  # type: ignore[method-assign]
    client._request = _fake_request  # type: ignore[method-assign]

    with_metadata = await client.query_with_metadata(
        {"source_name": "orders", "metric_column": "revenue", "aggregation": "sum"}
    )
    batch = await client.query_batch(
        {
            "defaults": {
                "dataset_id": "otp_events",
                "filter": {
                    "conditions": [{"dimension_hint": "status", "op": "eq", "value": "closed"}]
                },
            },
            "queries": [{"key": "overall_otp", "request": {"metric": {"role": "metric"}}}],
        }
    )
    sql_report = await client.query_sql_report(
        {
            "sources": [{"dataset_id": "ds_otp", "alias": "otp"}],
            "sql": "select flight_month, otp_rate_pct from otp",
            "max_rows": 100,
        }
    )

    assert isinstance(with_metadata, QueryWithMetadataResult)
    assert with_metadata.metadata.tokens_out == 45
    assert isinstance(batch, QueryBatchResult)
    assert batch.results[0].metadata.request_id == "req_item"
    assert isinstance(sql_report, QuerySqlReportResult)

    await client.aclose()


async def test_async_decision_engine_client_get_contract_returns_typed_result() -> None:
    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    expected_payload = _platform_contract_payload()

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        return expected_payload

    client._request = _fake_request  # type: ignore[method-assign]

    contract = await client.get_contract()

    assert isinstance(contract, PlatformContractResult)
    assert contract.primary_data_query_contract["api"]["contract_endpoint"] == "/v1/meta/contract"
    assert contract.primary_data_query_contract["mcp"]["contract_tool"] == "get_contract"
    assert_manifest_backed_integrations(contract.integrations)

    await client.aclose()


async def test_async_decision_engine_client_get_contract_rejects_invalid_payload(
    monkeypatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        payload = _platform_contract_payload()
        payload["api_key_prefixes"] = {"live": "de_live_"}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid payload") as exc:
        await client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"
    details = exc.value.details
    assert details["cause"] == "api_key_prefixes.test"
    assert exc.value.validation_errors[0]["path"] == "api_key_prefixes.test"
    assert exc.value.field_errors[0]["path"] == "api_key_prefixes.test"

    await client.aclose()


async def test_async_decision_engine_client_get_contract_rejects_invalid_nested_contract_payload(
    monkeypatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        payload = _platform_contract_payload()
        payload["primary_data_query_contract"]["cli"]["runtime_modules_command"] = None
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid payload") as exc:
        await client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"
    details = exc.value.details
    assert details["cause"] == "primary_data_query_contract.cli.runtime_modules_command"
    assert exc.value.validation_errors[0]["path"] == (
        "primary_data_query_contract.cli.runtime_modules_command"
    )

    await client.aclose()


async def test_async_decision_engine_client_get_contract_rejects_invalid_typed_model_instance(
    monkeypatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    typed_payload = PlatformContractResult.model_validate(_platform_contract_payload()).model_copy(
        update={"api_key_prefixes": {"live": "de_live_", "test": 7}}
    )

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        return typed_payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(DecisionEngineError, match="invalid payload") as exc:
            await client.get_contract()

    assert caught == []
    assert exc.value.error_code == "invalid_contract_payload"
    assert exc.value.details["cause"] == "api_key_prefixes.test"
    assert exc.value.validation_errors[0]["path"] == "api_key_prefixes.test"

    await client.aclose()


async def test_async_decision_engine_client_get_contract_rejects_tuple_backed_list_payload(
    monkeypatch,
) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        payload = _platform_contract_payload()
        payload["compatibility"]["legacy_headers"] = ("X-Deprecated-Key",)
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid payload") as exc:
        await client.get_contract()

    assert exc.value.error_code == "invalid_contract_payload"
    assert exc.value.details["cause"] == "compatibility"
    assert (
        exc.value.validation_errors[0]["message"] == "Value error, legacy_headers must be provided as a list."
    )

    await client.aclose()


async def test_async_decision_engine_client_get_contract_falls_back_to_openapi_extension() -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )
    seen: list[tuple[str, str, dict[str, object]]] = []

    async def _fake_request(method: str, path: str, **kwargs):
        seen.append((method, path, kwargs))
        if (method, path) == ("GET", "/v1/meta/contract"):
            raise NotFoundError(
                "missing",
                status_code=404,
                response_body={"error": {"code": "not_found"}},
            )
        if (method, path) == ("GET", "/openapi.json"):
            return {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {
                        "contract_endpoint": "/v1/meta/contract",
                        "query_sql_report_endpoint": "/v1/query/sql-report",
                    },
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    client._request = _fake_request  # type: ignore[method-assign]

    contract = await client.get_contract()

    assert isinstance(contract, PlatformContractResult)
    assert contract.api_base_url == "https://example.test/self-host"
    assert contract.mcp_endpoint == "https://example.test/self-host/mcp/sse"
    assert contract.mcp_tools_endpoint == "https://example.test/self-host/mcp/tools"
    assert contract.defaults.write_confirmation_required is True
    assert contract.integrations
    assert_manifest_backed_integrations(contract.integrations)
    assert (
        contract.primary_data_query_contract["api"]["query_sql_report_endpoint"]
        == "/v1/query/sql-report"
    )
    assert seen == [
        ("GET", "/v1/meta/contract", {}),
        ("GET", "/openapi.json", {}),
    ]


async def test_async_decision_engine_client_get_contract_rejects_invalid_openapi_fallback() -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    async def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("GET", "/v1/meta/contract"):
            raise NotFoundError(
                "missing",
                status_code=404,
                response_body={"error": {"code": "not_found"}},
            )
        if (method, path) == ("GET", "/openapi.json"):
            return {"openapi": "3.1.0"}
        raise AssertionError(f"unexpected call {(method, path)}")

    client._request = _fake_request  # type: ignore[method-assign]

    with pytest.raises(DecisionEngineError, match="x-primary-data-query-contract") as exc:
        await client.get_contract()
    assert exc.value.error_code == "contract_extension_missing"

    await client.aclose()


async def test_async_decision_engine_client_get_contract_rejects_openapi_fallback_missing_api_section() -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    async def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("GET", "/v1/meta/contract"):
            raise NotFoundError(
                "missing",
                status_code=404,
                response_body={"error": {"code": "not_found"}},
            )
        if (method, path) == ("GET", "/openapi.json"):
            return {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    client._request = _fake_request  # type: ignore[method-assign]

    with pytest.raises(DecisionEngineError, match="api contract section") as exc:
        await client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"

    await client.aclose()


async def test_async_decision_engine_client_get_contract_rejects_openapi_fallback_missing_contract_endpoint() -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    async def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("GET", "/v1/meta/contract"):
            raise NotFoundError(
                "missing",
                status_code=404,
                response_body={"error": {"code": "not_found"}},
            )
        if (method, path) == ("GET", "/openapi.json"):
            return {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {"query_batch_endpoint": "/v1/query/batch"},
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    client._request = _fake_request  # type: ignore[method-assign]

    with pytest.raises(DecisionEngineError, match="api.contract_endpoint") as exc:
        await client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"

    await client.aclose()


async def test_async_decision_engine_client_get_contract_rejects_openapi_fallback_invalid_nested_contract_override() -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    async def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("GET", "/v1/meta/contract"):
            raise NotFoundError(
                "missing",
                status_code=404,
                response_body={"error": {"code": "not_found"}},
            )
        if (method, path) == ("GET", "/openapi.json"):
            return {
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {"contract_endpoint": "/v1/meta/contract"},
                    "mcp": {"contract_tool": "get_contract"},
                    "runtime_sdk": {
                        "typescript": {"runtime_class": None},
                    },
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    client._request = _fake_request  # type: ignore[method-assign]

    with pytest.raises(
        DecisionEngineError,
        match="runtime_sdk.typescript.runtime_class",
    ) as exc:
        await client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"
    details = exc.value.response_body["error"]["details"]
    assert details["cause"] == "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    assert details["validation_errors"][0]["path"] == (
        "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    )

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_manifest_returns_typed_result(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    manifest_payload = get_runtime_manifest().model_dump(mode="json")

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return manifest_payload

    monkeypatch.setattr(client, "_request", _fake_request)

    manifest = await client.get_runtime_manifest()

    assert isinstance(manifest, RuntimeManifestResult)
    assert manifest.manifest_digest
    assert manifest.compiled_artifacts[0].kind is RuntimeArtifactKindResult.proof_bundle
    assert manifest.signature.algorithm is RuntimeSignatureAlgorithmResult.hmac_sha256
    assert manifest.shipping_contract.function_count == 209
    assert (
        manifest.shipping_contract.benchmark_discovery_rule
        is RuntimeBenchmarkDiscoveryRuleResult.shipping_llm_rollout_only
    )
    assert (
        manifest.benchmark_discovery_lane.non_shipping_rule
        is RuntimeNonShippingRuleResult.broader_mojo_inventory_not_advertised
    )
    assert manifest.system_invariants[0].name is RuntimeInvariantNameResult.manifest_truth
    assert (
        manifest.execution_model.allowed_transitions[0]
        is RuntimeExecutionTransitionResult.model_call_started
    )
    assert manifest.proof_matrix[0].layer is RuntimeLayerResult.mojo_llm_runtime_core
    assert manifest.proof_matrix[0].status is RuntimeMaturityResult.channel_covered
    assert manifest.advertised_capabilities.admin_endpoints == [
        "/v1/admin/runtime/modules",
        "/v1/admin/runtime/benchmarks",
        "/v1/admin/runtime/validation",
    ]
    assert any(
        entry.code is RuntimeBenchmarkClassCodeResult.provider_routing_overhead
        and entry.description == "provider routing overhead"
        and entry.evidence_paths
        == [
            "build/provider_routing_overhead_benchmark.json",
            "benchmarks/provider_routing_overhead_benchmark.py",
            "tests/test_provider_routing_overhead_benchmark.py",
        ]
        for entry in manifest.benchmarking.classes
    )
    assert any(
        entry.code is RuntimeBenchmarkClassCodeResult.checkpoint_replay_overhead
        and entry.description == "checkpoint and replay overhead"
        and entry.evidence_paths == []
        for entry in manifest.benchmarking.classes
    )


async def test_async_decision_engine_client_get_runtime_manifest_propagates_missing_route(
    monkeypatch,
) -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        raise NotFoundError(
            "missing",
            status_code=404,
            response_body={"error": {"code": "not_found"}},
        )

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(NotFoundError):
        await client.get_runtime_manifest()

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_modules_returns_typed_result(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_modules().model_dump(mode="json")

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    modules = await client.get_runtime_modules()

    assert isinstance(modules, RuntimeAdminModulesResult)
    assert modules.summary.function_count == 209
    assert (
        modules.shipping_contract.benchmark_discovery_rule
        is RuntimeBenchmarkDiscoveryRuleResult.shipping_llm_rollout_only
    )
    assert modules.modules[0].layer is RuntimeLayerResult.mojo_llm_runtime_core
    assert modules.proof_matrix[0].evidence_paths


async def test_async_decision_engine_client_get_runtime_benchmarks_returns_typed_result(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks
    from apps import runtime_manifest as _runtime_manifest_module

    # The compiled_mojo_binary artifact entry is only emitted when
    # mojo_build/simulate exists on disk. In CI the binary is not built,
    # so materialize a stub at the expected path so the entry is emitted
    # and the typed client can deserialize the kind. No-op locally where
    # a real binary already exists. Also clear the @lru_cache on
    # load_runtime_manifest so an earlier test that ran before the stub
    # existed doesn't return a stale cached result.
    binary_path = _runtime_manifest_module._MOJO_BINARY_PATH
    if not binary_path.exists():
        binary_path.parent.mkdir(parents=True, exist_ok=True)
        binary_path.write_bytes(b"#!/bin/sh\nexit 0\n")
    _runtime_manifest_module.load_runtime_manifest.cache_clear()

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    benchmarks = await client.get_runtime_benchmarks()

    assert isinstance(benchmarks, RuntimeAdminBenchmarksResult)
    assert benchmarks.module_benchmarks[0].function_count > 0
    assert (
        benchmarks.benchmark_discovery_lane.non_shipping_rule
        is RuntimeNonShippingRuleResult.broader_mojo_inventory_not_advertised
    )
    assert len(benchmarks.benchmark_discovery_lane.discovered_source_inventory) == (
        benchmarks.benchmark_discovery_lane.discovered_source_modules
    )
    assert sum(
        entry.public_function_count
        for entry in benchmarks.benchmark_discovery_lane.discovered_source_inventory
    ) == benchmarks.benchmark_discovery_lane.discovered_public_functions
    assert benchmarks.shipping_runtime_modules[0] is RuntimeModuleIdResult.bpe_tokenizer
    assert benchmarks.shipping_runtime_function_counts[0] == benchmarks.module_benchmarks[0].function_count
    assert (
        benchmarks.shipping_runtime_benchmark_artifacts[0]
        == benchmarks.module_benchmarks[0].benchmark_artifact
    )
    assert (
        benchmarks.shipping_runtime_compiled_artifacts[0]
        == benchmarks.module_benchmarks[0].compiled_artifact
    )
    assert benchmarks.compiled_artifacts[0].kind is RuntimeArtifactKindResult.proof_bundle
    assert benchmarks.module_benchmarks[0].compiled_engine is RuntimeCompiledEngineResult.mojo
    assert (
        benchmarks.shipping_runtime_compiled_engines[0]
        == benchmarks.module_benchmarks[0].compiled_engine
    )
    assert benchmarks.shipping_runtime_max_cold_ms[0] == benchmarks.module_benchmarks[0].max_cold_ms
    assert benchmarks.shipping_runtime_max_warm_ms[0] == benchmarks.module_benchmarks[0].max_warm_ms
    assert benchmarks.shipping_runtime_max_hot_ms[0] == benchmarks.module_benchmarks[0].max_hot_ms
    assert RuntimeArtifactKindResult.compiled_mojo_binary in {
        artifact.kind for artifact in benchmarks.compiled_artifacts
    }
    assert benchmarks.benchmarking.baselines[-1] == "Codna Mojo-native path"
    assert benchmarks.slo_budgets[0].name is RuntimeSLOBudgetNameResult.runtime_manifest_load
    assert (
        benchmarks.slo_budgets[0].applies_to
        is RuntimeSLOBudgetAppliesToResult.first_party_runtime_manifest_route
    )
    assert {entry.code.value for entry in benchmarks.quality_gate_benchmark_classes} == {
        "B6",
        "B7",
        "B9",
        "B10",
    }
    assert any(
        entry.code is RuntimeBenchmarkClassCodeResult.decision_workflow_completion_latency
        and entry.description == "decision workflow completion latency"
        and entry.evidence_paths
        == [
            "build/repository_intelligence_benchmark.json",
            "benchmarks/repository_intelligence_benchmark.py",
            "tests/test_repository_intelligence_benchmark.py",
        ]
        for entry in benchmarks.quality_gate_benchmark_classes
    )
    assert [entry.name.value for entry in benchmarks.quality_gate_slo_budgets] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert benchmarks.evaluation_summary.replay_gate_enabled is True
    assert benchmarks.evaluation_summary.tool_call_quality_gate_enabled is True
    assert benchmarks.evaluation_summary.rag_quality_gate_enabled is True
    assert benchmarks.evaluation_summary.decision_quality_gate_enabled is True


async def test_async_decision_engine_client_get_runtime_release_validation_returns_typed_result(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_release_validation().model_dump(mode="json")

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/validation")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    validation = await client.get_runtime_release_validation()

    assert isinstance(validation, RuntimeReleaseValidationResult)
    assert validation.signature.scope is RuntimeSignatureScopeResult.control_plane_hmac_v1
    assert validation.conditions[0].condition is RuntimeReleaseConditionResult.manifest_listed
    assert validation.deployment_mode_raw == "local_dev_daemon"


async def test_async_decision_engine_client_get_runtime_release_validation_rejects_boolean_coercion(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["valid_release"] = "yes"
    payload["conditions"][0]["satisfied"] = "no"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/validation")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_release_validation()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "valid_release"
    assert exc_info.value.validation_errors[0]["path"] == "valid_release"
    assert any(
        item["path"] == "conditions.0.satisfied" for item in exc_info.value.validation_errors
    )

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_manifest_rejects_tuple_backed_supported_channels(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"] = ("python_sdk", "typescript_sdk", "cli", "mcp")

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "supported_channels"
    assert exc_info.value.validation_errors[0]["path"] == "supported_channels"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_manifest_rejects_duplicate_release_conditions(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["formal_release_theorem"]["required_conditions"].append("manifest-listed")

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "formal_release_theorem.required_conditions"
    assert exc_info.value.validation_errors[0]["path"] == (
        "formal_release_theorem.required_conditions"
    )

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_manifest_rejects_invalid_artifact_kind(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["compiled_artifacts"][0]["kind"] = "ghost_bundle"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "compiled_artifacts.0.kind"
    assert exc_info.value.validation_errors[0]["path"] == "compiled_artifacts.0.kind"
    assert exc_info.value.field_errors[0]["path"] == "compiled_artifacts.0.kind"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_manifest_rejects_invalid_benchmark_discovery_rule(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_contract.benchmark_discovery_rule"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_modules_rejects_duplicate_proof_matrix_layers(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"].append(dict(payload["proof_matrix"][0]))

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_modules()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "proof_matrix"
    assert exc_info.value.validation_errors[0]["path"] == "proof_matrix"

    await client.aclose()


