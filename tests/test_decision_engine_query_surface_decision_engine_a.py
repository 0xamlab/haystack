"""Tests for test_decision_engine_query_surface: decision_engine_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-1/tests/test_decision_engine_query_surface.py during modularization.
"""
from __future__ import annotations

from tests._test_decision_engine_query_surface_helpers import *  # noqa: F401,F403


def test_decision_engine_client_query_metadata_batch_and_sql_report(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    def _fake_request_response(method: str, path: str, **kwargs):
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

    def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("POST", "/v1/query/batch"):
            assert kwargs["json"]["defaults"]["dataset_id"] == "otp_events"
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
                    },
                    {
                        "key": "avg_delay",
                        "error": {
                            "code": "metric_not_found",
                            "message": "Metric average_delay_minutes was not found.",
                        },
                    },
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

    monkeypatch.setattr(client, "_request_response", _fake_request_response)
    monkeypatch.setattr(client, "_request", _fake_request)

    with_metadata = client.query_with_metadata(
        {"source_name": "orders", "metric_column": "revenue", "aggregation": "sum"}
    )
    batch = client.query_batch(
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
    sql_report = client.query_sql_report(
        {
            "sources": [{"dataset_id": "ds_otp", "alias": "otp"}],
            "sql": "select flight_month, otp_rate_pct from otp",
            "max_rows": 100,
        }
    )

    assert isinstance(with_metadata, QueryWithMetadataResult)
    assert with_metadata.metadata.tokens_in == 120
    assert with_metadata.metadata.cache_hit is True
    assert with_metadata.headers["x-cache-hit"] == "true"
    assert isinstance(batch, QueryBatchResult)
    assert batch.results[1].error.code == "metric_not_found"
    assert isinstance(sql_report, QuerySqlReportResult)
    assert sql_report.columns == ["flight_month", "otp_rate_pct"]


def test_decision_engine_client_get_contract_returns_typed_result(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    expected_payload = _platform_contract_payload()

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        return expected_payload

    monkeypatch.setattr(client, "_request", _fake_request)

    contract = client.get_contract()

    assert isinstance(contract, PlatformContractResult)
    assert contract.primary_data_query_contract["api"]["contract_endpoint"] == "/v1/meta/contract"
    assert contract.primary_data_query_contract["mcp"]["contract_tool"] == "get_contract"
    assert_manifest_backed_integrations(contract.integrations)


def test_decision_engine_client_get_contract_rejects_invalid_payload(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        payload = _platform_contract_payload()
        payload["api_key_prefixes"] = {"live": "de_live_"}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid payload") as exc:
        client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"
    details = exc.value.details
    assert details["cause"] == "api_key_prefixes.test"
    assert exc.value.validation_errors[0]["path"] == "api_key_prefixes.test"
    assert exc.value.field_errors[0]["path"] == "api_key_prefixes.test"


def test_decision_engine_client_get_contract_rejects_invalid_nested_contract_payload(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        payload = _platform_contract_payload()
        payload["primary_data_query_contract"]["runtime_sdk"]["typescript"].pop("runtime_class")
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid payload") as exc:
        client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"
    details = exc.value.details
    assert details["cause"] == "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    assert exc.value.validation_errors[0]["path"] == (
        "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    )


def test_decision_engine_client_get_contract_rejects_invalid_typed_model_instance(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    typed_payload = PlatformContractResult.model_validate(_platform_contract_payload()).model_copy(
        update={"api_key_prefixes": {"live": "de_live_", "test": 7}}
    )

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        return typed_payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(DecisionEngineError, match="invalid payload") as exc:
            client.get_contract()

    assert caught == []
    assert exc.value.error_code == "invalid_contract_payload"
    assert exc.value.details["cause"] == "api_key_prefixes.test"
    assert exc.value.validation_errors[0]["path"] == "api_key_prefixes.test"


def test_decision_engine_client_get_contract_rejects_tuple_backed_list_payload(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/meta/contract")
        assert kwargs == {}
        payload = _platform_contract_payload()
        payload["compatibility"]["legacy_headers"] = ("X-Deprecated-Key",)
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid payload") as exc:
        client.get_contract()

    assert exc.value.error_code == "invalid_contract_payload"
    assert exc.value.details["cause"] == "compatibility"
    assert (
        exc.value.validation_errors[0]["message"] == "Value error, legacy_headers must be provided as a list."
    )


def test_decision_engine_client_get_contract_falls_back_to_openapi_extension(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )
    seen: list[tuple[str, str, dict[str, object]]] = []

    def _fake_request(method: str, path: str, **kwargs):
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
                        "query_batch_endpoint": "/v1/query/batch",
                    },
                    "mcp": {"contract_tool": "get_contract"},
                },
            }
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    contract = client.get_contract()

    assert isinstance(contract, PlatformContractResult)
    assert contract.api_base_url == "https://example.test/self-host"
    assert contract.mcp_endpoint == "https://example.test/self-host/mcp"
    assert contract.mcp_tools_endpoint == "https://example.test/self-host/mcp/tools"
    assert contract.defaults.read_only_default is True
    assert contract.integrations
    assert_manifest_backed_integrations(contract.integrations)
    assert contract.primary_data_query_contract["api"]["query_batch_endpoint"] == "/v1/query/batch"
    assert seen == [
        ("GET", "/v1/meta/contract", {}),
        ("GET", "/openapi.json", {}),
    ]


def test_decision_engine_client_get_contract_rejects_invalid_openapi_fallback(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    def _fake_request(method: str, path: str, **kwargs):
        if (method, path) == ("GET", "/v1/meta/contract"):
            raise NotFoundError(
                "missing",
                status_code=404,
                response_body={"error": {"code": "not_found"}},
            )
        if (method, path) == ("GET", "/openapi.json"):
            return {"openapi": "3.1.0"}
        raise AssertionError(f"unexpected call {(method, path)}")

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="x-primary-data-query-contract") as exc:
        client.get_contract()
    assert exc.value.error_code == "contract_extension_missing"


def test_decision_engine_client_get_contract_rejects_openapi_fallback_missing_api_section(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    def _fake_request(method: str, path: str, **kwargs):
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

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="api contract section") as exc:
        client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"


def test_decision_engine_client_get_contract_rejects_openapi_fallback_missing_contract_endpoint(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    def _fake_request(method: str, path: str, **kwargs):
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

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="api.contract_endpoint") as exc:
        client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"


def test_decision_engine_client_get_contract_rejects_openapi_fallback_invalid_nested_contract_override(
    monkeypatch,
) -> None:
    client = DecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    def _fake_request(method: str, path: str, **kwargs):
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

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(
        DecisionEngineError,
        match="runtime_sdk.typescript.runtime_class",
    ) as exc:
        client.get_contract()
    assert exc.value.error_code == "invalid_contract_payload"
    details = exc.value.response_body["error"]["details"]
    assert details["cause"] == "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    assert details["validation_errors"][0]["path"] == (
        "primary_data_query_contract.runtime_sdk.typescript.runtime_class"
    )


def test_decision_engine_client_get_runtime_manifest_returns_typed_result(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    manifest_payload = get_runtime_manifest().model_dump(mode="json")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return manifest_payload

    monkeypatch.setattr(client, "_request", _fake_request)

    manifest = client.get_runtime_manifest()

    assert isinstance(manifest, RuntimeManifestResult)
    assert manifest.llm_core_manifest == "llm-core-v1"
    assert manifest.shipping_contract.module_count == 22
    assert manifest.modules[0].name == "bpe_tokenizer"
    assert manifest.modules[0].promotion_status.value == "shipping"
    assert isinstance(manifest.modules[0].maturity, RuntimeMaturityResult)
    assert manifest.modules[0].maturity is RuntimeMaturityResult.channel_covered
    assert manifest.modules[0].public_supported_channels[0] is RuntimeSupportedChannelResult.python_sdk
    assert (
        manifest.modules[0].validated_auxiliary_channels[0]
        is RuntimeAuxiliaryChannelResult.bundled_worker
    )
    assert (
        manifest.modules[0].feature_flag_channels[0]
        is RuntimeFeatureFlagChannelResult.http_api_feature_flag
    )
    assert manifest.system_invariants[0].name is RuntimeInvariantNameResult.manifest_truth
    assert manifest.execution_model.state_fields[0] is RuntimeExecutionStateFieldResult.request
    assert (
        manifest.execution_model.validity_rules[0]
        is RuntimeExecutionValidityRuleResult.schema_valid
    )
    assert (
        manifest.execution_model.allowed_transitions[0]
        is RuntimeExecutionTransitionResult.model_call_started
    )
    assert (
        manifest.external_nondeterminism.sources[0]
        is RuntimeExternalNondeterminismSourceResult.provider_responses
    )
    assert (
        manifest.external_nondeterminism.required_artifacts[0]
        is RuntimeNondeterminismArtifactResult.provider_response_record
    )
    assert (
        manifest.external_nondeterminism.failure_codes[0]
        is RuntimeFailureCodeResult.replay_mismatch
    )
    assert manifest.artifact_lineage.artifact_flow[0] is RuntimeArtifactLineageStepResult.input
    assert manifest.artifact_lineage.required_node_fields[0] is RuntimeLineageNodeFieldResult.node_id
    assert manifest.capability_algebra.required_fields[0] is RuntimeCapabilityFieldResult.tool_name
    assert (
        manifest.capability_algebra.rules[0]
        is RuntimeCapabilityRuleResult.mcp_tools_are_untrusted_by_default
    )
    assert isinstance(
        manifest.capability_algebra.enums.side_effect_class[0],
        RuntimeSideEffectClassResult,
    )
    assert isinstance(manifest.capability_algebra.enums.risk_level[-1], RuntimeRiskLevelResult)
    assert manifest.capability_algebra.enums.risk_level[-1] is RuntimeRiskLevelResult.critical
    assert isinstance(
        manifest.capability_algebra.enums.replayability[0],
        RuntimeReplayabilityResult,
    )
    assert manifest.modules[0].layer is RuntimeLayerResult.mojo_llm_runtime_core
    assert manifest.shipping_contract.runtime_core_layer is RuntimeLayerResult.mojo_llm_runtime_core
    assert (
        manifest.shipping_contract.benchmark_discovery_rule
        is RuntimeBenchmarkDiscoveryRuleResult.shipping_llm_rollout_only
    )
    assert (
        manifest.benchmark_discovery_lane.non_shipping_rule
        is RuntimeNonShippingRuleResult.broader_mojo_inventory_not_advertised
    )
    assert len(manifest.benchmark_discovery_lane.discovered_source_inventory) == (
        manifest.benchmark_discovery_lane.discovered_source_modules
    )
    assert sum(
        entry.public_function_count
        for entry in manifest.benchmark_discovery_lane.discovered_source_inventory
    ) == manifest.benchmark_discovery_lane.discovered_public_functions
    assert manifest.modules[0].name.value in {
        entry.import_path for entry in manifest.benchmark_discovery_lane.discovered_source_inventory
    }
    assert (
        manifest.modules[0].proof_obligations[0]
        is RuntimeProofObligationResult.numerical_parity
    )
    assert manifest.proof_matrix[0].layer is RuntimeLayerResult.mojo_llm_runtime_core
    assert isinstance(manifest.proof_matrix[0].status, RuntimeMaturityResult)
    assert manifest.proof_matrix[0].status is RuntimeMaturityResult.channel_covered
    assert (
        manifest.proof_matrix[0].obligations[0]
        is RuntimeProofObligationResult.numerical_parity
    )
    assert (
        manifest.maturity[RuntimeModuleIdResult.bpe_tokenizer]
        is RuntimeMaturityResult.channel_covered
    )
    assert manifest.supported_channels[0] is RuntimeSupportedChannelResult.python_sdk
    assert manifest.validated_auxiliary_channels[0] is RuntimeAuxiliaryChannelResult.bundled_worker
    assert (
        manifest.feature_flag_channels[0]
        is RuntimeFeatureFlagChannelResult.http_api_feature_flag
    )
    assert isinstance(manifest.deployment_mode, RuntimeDeploymentModeResult)
    assert manifest.deployment_mode is RuntimeDeploymentModeResult.local_dev_daemon
    assert manifest.deployment_modes.current is RuntimeDeploymentModeResult.local_dev_daemon
    assert manifest.deployment_modes.supported_modes[0] is RuntimeDeploymentModeResult.saas
    assert (
        manifest.benchmarking.classes[0].code
        is RuntimeBenchmarkClassCodeResult.microkernel_latency
    )
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
    assert manifest.benchmarking.required_metrics[0] is RuntimeBenchmarkMetricResult.p50
    assert (
        manifest.benchmarking.baselines[-1]
        is RuntimeBenchmarkBaselineResult.algenta_mojo_native_path
    )
    assert manifest.slo_budgets[0].name is RuntimeSLOBudgetNameResult.runtime_manifest_load
    assert (
        manifest.slo_budgets[0].applies_to
        is RuntimeSLOBudgetAppliesToResult.first_party_runtime_manifest_route
    )
    assert manifest.scheduler_model.policies[0] is RuntimeSchedulerPolicyResult.fifo
    assert (
        manifest.scheduler_model.minimize[0]
        is RuntimeSchedulerMinimizeObjectiveResult.tail_latency
    )
    assert (
        manifest.scheduler_model.maximize[0]
        is RuntimeSchedulerMaximizeObjectiveResult.gpu_or_cpu_utilization
    )
    assert (
        manifest.scheduler_model.invariants[0]
        is RuntimeSchedulerInvariantResult.no_request_starves_indefinitely
    )
    assert manifest.memory_model.regions[0] is RuntimeMemoryRegionResult.model_weights
    assert manifest.memory_model.rules[0] is RuntimeMemoryRuleResult.kv_pages_are_tenant_scoped
    assert manifest.memory_model.failure_codes[0] is RuntimeFailureCodeResult.kv_cache_exhausted
    assert (
        manifest.evaluation_science.dimensions[0]
        is RuntimeEvaluationDimensionResult.answer_correctness
    )
    assert (
        manifest.evaluation_science.methods[0]
        is RuntimeEvaluationMethodResult.bootstrap_confidence_intervals
    )
    assert (
        manifest.evaluation_science.release_blockers[0]
        is RuntimeReleaseBlockerResult.replay_success_regression
    )
    assert manifest.typed_failures[0].code is RuntimeFailureCodeResult.provider_timeout
    assert manifest.threat_model.threat_classes[0] is RuntimeThreatClassResult.prompt_injection
    assert manifest.threat_model.controls[0] is RuntimeThreatControlResult.tool_allowlists
    assert (
        manifest.threat_model.non_negotiable_rules[0]
        is RuntimeThreatRuleResult.mcp_tools_are_untrusted_by_default
    )
    assert (
        manifest.release_artifact_bundle.required_artifacts[0]
        is RuntimeReleaseArtifactResult.signed_runtime_manifest
    )
    assert manifest.release_gates[0].gate is RuntimeReleaseGateIdResult.gate_a
    assert manifest.immediate_implementation_sequence[0].pr == "PR 0"
    assert manifest.compiled_artifacts[0].kind is RuntimeArtifactKindResult.proof_bundle
    assert manifest.signature.algorithm is RuntimeSignatureAlgorithmResult.hmac_sha256
    assert manifest.signature.scope is RuntimeSignatureScopeResult.control_plane_hmac_v1
    assert manifest.modules[0].name is RuntimeModuleIdResult.bpe_tokenizer
    assert (
        manifest.advertised_capabilities.runtime_modules[0]
        is RuntimeModuleIdResult.bpe_tokenizer
    )
    assert (
        manifest.advertised_capabilities.public_endpoints[0]
        is RuntimePublicEndpointResult.meta_contract
    )
    assert (
        manifest.advertised_capabilities.admin_endpoints[0]
        is RuntimeAdminEndpointResult.runtime_modules
    )
    assert (
        manifest.advertised_capabilities.feature_flag_endpoints[0]
        is RuntimeFeatureFlagEndpointResult.libraries
    )
    assert manifest.model_dump(mode="json")["supported_channels"][0] == "python_sdk"
    assert manifest.model_dump(mode="json")["deployment_mode"] == "local_dev_daemon"
    assert manifest.model_dump(mode="json")["maturity"]["bpe_tokenizer"] == "channel_covered"


def test_decision_engine_client_get_runtime_manifest_propagates_missing_route(monkeypatch) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="https://example.test/self-host")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        raise NotFoundError(
            "missing",
            status_code=404,
            response_body={"error": {"code": "not_found"}},
        )

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(NotFoundError):
        client.get_runtime_manifest()


def test_decision_engine_client_get_runtime_modules_returns_typed_result(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_modules().model_dump(mode="json")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    modules = client.get_runtime_modules()

    assert isinstance(modules, RuntimeAdminModulesResult)
    assert modules.summary.module_count == 22
    assert modules.modules[0].name == "bpe_tokenizer"
    assert (
        modules.shipping_contract.benchmark_discovery_rule
        is RuntimeBenchmarkDiscoveryRuleResult.shipping_llm_rollout_only
    )
    assert modules.modules[0].layer is RuntimeLayerResult.mojo_llm_runtime_core
    assert modules.modules[0].maturity is RuntimeMaturityResult.channel_covered
    assert modules.modules[0].public_supported_channels[0] is RuntimeSupportedChannelResult.python_sdk
    assert modules.summary.maturity_counts[RuntimeMaturityResult.channel_covered] == 22
    assert modules.summary.layer_counts[RuntimeLayerResult.mojo_llm_runtime_core] == 22
    assert modules.proof_matrix[0].layer is RuntimeLayerResult.mojo_llm_runtime_core
    assert (
        modules.modules[0].proof_obligations[0]
        is RuntimeProofObligationResult.numerical_parity
    )
    assert (
        modules.proof_matrix[0].obligations[0]
        is RuntimeProofObligationResult.numerical_parity
    )
    assert modules.proof_matrix[0].status is RuntimeMaturityResult.channel_covered


def test_decision_engine_client_get_runtime_benchmarks_returns_typed_result(monkeypatch) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    benchmarks = client.get_runtime_benchmarks()

    assert isinstance(benchmarks, RuntimeAdminBenchmarksResult)
    assert benchmarks.module_benchmarks[0].name is RuntimeModuleIdResult.bpe_tokenizer
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
    assert benchmarks.slo_budgets
    assert (
        benchmarks.benchmarking.classes[0].code
        is RuntimeBenchmarkClassCodeResult.microkernel_latency
    )
    assert any(
        entry.code is RuntimeBenchmarkClassCodeResult.provider_routing_overhead
        and entry.description == "provider routing overhead"
        and entry.evidence_paths
        == [
            "build/provider_routing_overhead_benchmark.json",
            "benchmarks/provider_routing_overhead_benchmark.py",
            "tests/test_provider_routing_overhead_benchmark.py",
        ]
        for entry in benchmarks.benchmarking.classes
    )
    assert benchmarks.benchmarking.required_metrics[0] is RuntimeBenchmarkMetricResult.p50
    assert (
        benchmarks.benchmarking.baselines[-1]
        is RuntimeBenchmarkBaselineResult.algenta_mojo_native_path
    )
    assert (
        benchmarks.slo_budgets[0].applies_to
        is RuntimeSLOBudgetAppliesToResult.first_party_runtime_manifest_route
    )
    assert benchmarks.evaluation_science.dimensions[0] is RuntimeEvaluationDimensionResult.answer_correctness
    assert (
        benchmarks.quality_gate_benchmark_classes[0].code
        is RuntimeBenchmarkClassCodeResult.checkpoint_replay_overhead
    )
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
    assert {entry.code.value for entry in benchmarks.quality_gate_benchmark_classes} == {
        "B6",
        "B7",
        "B9",
        "B10",
    }
    assert [entry.name.value for entry in benchmarks.quality_gate_slo_budgets] == [
        "mcp_call_first_party",
        "decision_plan_creation",
        "replay",
    ]
    assert benchmarks.evaluation_summary.replay_gate_enabled is True
    assert benchmarks.evaluation_summary.tool_call_quality_gate_enabled is True
    assert benchmarks.evaluation_summary.rag_quality_gate_enabled is True
    assert benchmarks.evaluation_summary.decision_quality_gate_enabled is True


