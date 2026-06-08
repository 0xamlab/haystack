from __future__ import annotations

import importlib
import sys
import warnings
from copy import deepcopy
from pathlib import Path

import pytest

from apps.platform_contract import load_platform_contract_manifest
from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations,
)

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

pytestmark = pytest.mark.anyio

decision_engine = importlib.import_module("decision_engine")
runtime_manifest_models = importlib.import_module("decision_engine.models_runtime_manifest")
AsyncDecisionEngineClient = decision_engine.AsyncDecisionEngineClient
DecisionEngineClient = decision_engine.DecisionEngineClient
DecisionEngineError = decision_engine.DecisionEngineError
QueryBatchResult = decision_engine.QueryBatchResult
NotFoundError = decision_engine.NotFoundError
PlatformContractResult = decision_engine.PlatformContractResult
QuerySqlReportResult = decision_engine.QuerySqlReportResult
QueryWithMetadataResult = decision_engine.QueryWithMetadataResult
RuntimeAdminBenchmarksResult = decision_engine.RuntimeAdminBenchmarksResult
RuntimeAdminModulesResult = decision_engine.RuntimeAdminModulesResult
RuntimeManifestResult = decision_engine.RuntimeManifestResult
RuntimeReleaseValidationResult = decision_engine.RuntimeReleaseValidationResult
RuntimeAuxiliaryChannelResult = runtime_manifest_models.RuntimeAuxiliaryChannelResult
RuntimeBenchmarkBaselineResult = runtime_manifest_models.RuntimeBenchmarkBaselineResult
RuntimeBenchmarkClassCodeResult = runtime_manifest_models.RuntimeBenchmarkClassCodeResult
RuntimeBenchmarkMetricResult = runtime_manifest_models.RuntimeBenchmarkMetricResult
RuntimeCapabilityFieldResult = runtime_manifest_models.RuntimeCapabilityFieldResult
RuntimeCapabilityRuleResult = runtime_manifest_models.RuntimeCapabilityRuleResult
RuntimeArtifactKindResult = runtime_manifest_models.RuntimeArtifactKindResult
RuntimeCompiledEngineResult = runtime_manifest_models.RuntimeCompiledEngineResult
RuntimeBenchmarkDiscoveryRuleResult = (
    runtime_manifest_models.RuntimeBenchmarkDiscoveryRuleResult
)
RuntimeNonShippingRuleResult = runtime_manifest_models.RuntimeNonShippingRuleResult
RuntimeDeploymentModeResult = runtime_manifest_models.RuntimeDeploymentModeResult
RuntimeEvaluationDimensionResult = runtime_manifest_models.RuntimeEvaluationDimensionResult
RuntimeEvaluationMethodResult = runtime_manifest_models.RuntimeEvaluationMethodResult
RuntimeExecutionStateFieldResult = runtime_manifest_models.RuntimeExecutionStateFieldResult
RuntimeExecutionValidityRuleResult = runtime_manifest_models.RuntimeExecutionValidityRuleResult
RuntimeExternalNondeterminismSourceResult = (
    runtime_manifest_models.RuntimeExternalNondeterminismSourceResult
)
RuntimeFailureCodeResult = runtime_manifest_models.RuntimeFailureCodeResult
RuntimeExecutionTransitionResult = runtime_manifest_models.RuntimeExecutionTransitionResult
RuntimeFeatureFlagChannelResult = runtime_manifest_models.RuntimeFeatureFlagChannelResult
RuntimeInvariantNameResult = runtime_manifest_models.RuntimeInvariantNameResult
RuntimeArtifactLineageStepResult = runtime_manifest_models.RuntimeArtifactLineageStepResult
RuntimeAdminEndpointResult = runtime_manifest_models.RuntimeAdminEndpointResult
RuntimeLayerResult = runtime_manifest_models.RuntimeLayerResult
RuntimeLineageNodeFieldResult = runtime_manifest_models.RuntimeLineageNodeFieldResult
RuntimeMemoryRegionResult = runtime_manifest_models.RuntimeMemoryRegionResult
RuntimeMemoryRuleResult = runtime_manifest_models.RuntimeMemoryRuleResult
RuntimeMaturityResult = runtime_manifest_models.RuntimeMaturityResult
RuntimeModuleIdResult = runtime_manifest_models.RuntimeModuleIdResult
RuntimeNondeterminismArtifactResult = runtime_manifest_models.RuntimeNondeterminismArtifactResult
RuntimeProofObligationResult = runtime_manifest_models.RuntimeProofObligationResult
RuntimePublicEndpointResult = runtime_manifest_models.RuntimePublicEndpointResult
RuntimeSignatureAlgorithmResult = runtime_manifest_models.RuntimeSignatureAlgorithmResult
RuntimeSignatureScopeResult = runtime_manifest_models.RuntimeSignatureScopeResult
RuntimeReleaseArtifactResult = runtime_manifest_models.RuntimeReleaseArtifactResult
RuntimeReleaseBlockerResult = runtime_manifest_models.RuntimeReleaseBlockerResult
RuntimeReleaseConditionResult = runtime_manifest_models.RuntimeReleaseConditionResult
RuntimeReleaseGateIdResult = runtime_manifest_models.RuntimeReleaseGateIdResult
RuntimeReplayabilityResult = runtime_manifest_models.RuntimeReplayabilityResult
RuntimeRiskLevelResult = runtime_manifest_models.RuntimeRiskLevelResult
RuntimeSchedulerInvariantResult = runtime_manifest_models.RuntimeSchedulerInvariantResult
RuntimeSchedulerMaximizeObjectiveResult = (
    runtime_manifest_models.RuntimeSchedulerMaximizeObjectiveResult
)
RuntimeSchedulerMinimizeObjectiveResult = (
    runtime_manifest_models.RuntimeSchedulerMinimizeObjectiveResult
)
RuntimeSchedulerPolicyResult = runtime_manifest_models.RuntimeSchedulerPolicyResult
RuntimeSideEffectClassResult = runtime_manifest_models.RuntimeSideEffectClassResult
RuntimeSLOBudgetAppliesToResult = runtime_manifest_models.RuntimeSLOBudgetAppliesToResult
RuntimeSLOBudgetNameResult = runtime_manifest_models.RuntimeSLOBudgetNameResult
RuntimeSupportedChannelResult = runtime_manifest_models.RuntimeSupportedChannelResult
RuntimeFeatureFlagEndpointResult = runtime_manifest_models.RuntimeFeatureFlagEndpointResult
RuntimeThreatClassResult = runtime_manifest_models.RuntimeThreatClassResult
RuntimeThreatControlResult = runtime_manifest_models.RuntimeThreatControlResult
RuntimeThreatRuleResult = runtime_manifest_models.RuntimeThreatRuleResult


def _platform_contract_payload() -> dict[str, object]:
    return deepcopy(load_platform_contract_manifest())

def _query_result_payload(**overrides):
    return {
        "query_id": "query_1",
        "result": {"rows": []},
        "result_type": "table",
        "confidence": 0.98,
        "plan": ["resolve metric", "execute query"],
        "resolved_column": "revenue",
        "resolved_role": "metric",
        "resolved_source": "orders",
        "row_count": 1,
        "candidates": [],
        "source_scores": {"orders": 0.98},
        "ambiguous": False,
        "exact_spec": True,
        "explanation": ["used exact spec"],
        "latency_ms": 12.5,
        "decision_path": "exact_spec",
        "plan_hash": "plan_1",
        "validated": True,
        "deterministic_scope": "exact",
        "confidence_source": "schema_truth",
        "request_id": "req_query",
        **overrides,
    }


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
    assert contract.mcp_endpoint == "https://example.test/self-host/mcp/sse"
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
        is RuntimeAuxiliaryChannelResult.daemon_client
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
    assert manifest.validated_auxiliary_channels[0] is RuntimeAuxiliaryChannelResult.daemon_client
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


def test_decision_engine_client_get_runtime_release_validation_returns_typed_result(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_release_validation().model_dump(mode="json")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/validation")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    validation = client.get_runtime_release_validation()

    assert isinstance(validation, RuntimeReleaseValidationResult)
    assert validation.valid_release is True
    assert validation.conditions[0].condition is RuntimeReleaseConditionResult.manifest_listed
    assert validation.deployment_mode is RuntimeDeploymentModeResult.local_dev_daemon
    assert validation.deployment_mode_raw == "local_dev_daemon"
    assert validation.signature.scope is RuntimeSignatureScopeResult.control_plane_hmac_v1


def test_decision_engine_client_get_runtime_release_validation_rejects_boolean_coercion(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["valid_release"] = "yes"
    payload["conditions"][0]["satisfied"] = "no"

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/validation")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_release_validation()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "valid_release"
    assert exc_info.value.validation_errors[0]["path"] == "valid_release"
    assert any(
        item["path"] == "conditions.0.satisfied" for item in exc_info.value.validation_errors
    )


def test_decision_engine_client_get_runtime_manifest_rejects_tuple_backed_supported_channels(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"] = ("python_sdk", "typescript_sdk", "cli", "mcp")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "supported_channels"
    assert exc_info.value.validation_errors[0]["path"] == "supported_channels"


def test_decision_engine_client_get_runtime_manifest_rejects_duplicate_release_conditions(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["formal_release_theorem"]["required_conditions"].append("manifest-listed")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "formal_release_theorem.required_conditions"
    assert exc_info.value.validation_errors[0]["path"] == (
        "formal_release_theorem.required_conditions"
    )


def test_decision_engine_client_get_runtime_manifest_rejects_duplicate_module_public_channels(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["public_supported_channels"].append("python_sdk")

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "modules.0.public_supported_channels"
    assert exc_info.value.validation_errors[0]["path"] == (
        "modules.0.public_supported_channels"
    )


def test_decision_engine_client_get_runtime_manifest_rejects_duplicate_module_functions(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["functions"].append(payload["modules"][0]["functions"][0])

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "modules.0.functions"
    assert exc_info.value.validation_errors[0]["path"] == "modules.0.functions"


def test_decision_engine_client_get_runtime_manifest_rejects_invalid_artifact_kind(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["compiled_artifacts"][0]["kind"] = "ghost_bundle"

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "compiled_artifacts.0.kind"
    assert exc_info.value.validation_errors[0]["path"] == "compiled_artifacts.0.kind"
    assert exc_info.value.field_errors[0]["path"] == "compiled_artifacts.0.kind"


def test_decision_engine_client_get_runtime_manifest_rejects_invalid_benchmark_discovery_rule(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_contract.benchmark_discovery_rule"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )


def test_decision_engine_client_get_runtime_manifest_rejects_benchmark_shipping_function_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["shipping_manifest_functions"] += 1

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/runtime/manifest")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_manifest()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == (
        "benchmark_discovery_lane.shipping_manifest_functions"
    )
    assert exc_info.value.validation_errors[0]["path"] == (
        "benchmark_discovery_lane.shipping_manifest_functions"
    )


def test_decision_engine_client_get_runtime_modules_rejects_duplicate_proof_matrix_layers(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"].append(dict(payload["proof_matrix"][0]))

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_modules()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "proof_matrix"
    assert exc_info.value.validation_errors[0]["path"] == "proof_matrix"


def test_decision_engine_client_get_runtime_modules_rejects_invalid_benchmark_discovery_rule(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_modules()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_contract.benchmark_discovery_rule"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )


def test_decision_engine_client_get_runtime_modules_rejects_summary_function_count_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["summary"]["function_count"] += 1

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_modules()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "summary.function_count"
    assert exc_info.value.validation_errors[0]["path"] == "summary.function_count"


def test_decision_engine_client_runtime_proof_surfaces_fail_closed_on_invalid_payloads(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import (
        get_runtime_admin_benchmarks,
        get_runtime_admin_modules,
        get_runtime_manifest,
        get_runtime_release_validation,
    )

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payloads = {
        "/v1/runtime/manifest": get_runtime_manifest().model_dump(mode="json"),
        "/v1/admin/runtime/modules": get_runtime_admin_modules().model_dump(mode="json"),
        "/v1/admin/runtime/benchmarks": get_runtime_admin_benchmarks().model_dump(mode="json"),
        "/v1/admin/runtime/validation": get_runtime_release_validation().model_dump(mode="json"),
    }
    payloads["/v1/runtime/manifest"]["maturity"]["bpe_tokenizer"] = "legendary"
    payloads["/v1/admin/runtime/modules"]["proof_matrix"][0]["status"] = "unknown_status"
    payloads["/v1/admin/runtime/benchmarks"]["module_benchmarks"][0]["compiled_engine"] = (
        "warp_core"
    )
    payloads["/v1/admin/runtime/validation"]["conditions"][0]["condition"] = (
        "teleport-validated"
    )

    def _fake_request(method: str, path: str, **kwargs):
        assert method == "GET"
        assert kwargs == {}
        return payloads[path]

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as manifest_exc:
        client.get_runtime_manifest()
    assert manifest_exc.value.error_code == "invalid_runtime_contract_payload"
    assert manifest_exc.value.details["cause"] == "maturity.bpe_tokenizer"
    assert manifest_exc.value.validation_errors[0]["path"] == "maturity.bpe_tokenizer"
    assert manifest_exc.value.field_errors[0]["path"] == "maturity.bpe_tokenizer"

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as modules_exc:
        client.get_runtime_modules()
    assert modules_exc.value.error_code == "invalid_runtime_contract_payload"
    assert modules_exc.value.details["cause"] == "proof_matrix.0.status"
    assert modules_exc.value.validation_errors[0]["path"] == "proof_matrix.0.status"

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as benchmarks_exc:
        client.get_runtime_benchmarks()
    assert benchmarks_exc.value.error_code == "invalid_runtime_contract_payload"
    assert benchmarks_exc.value.details["cause"] == "module_benchmarks.0.compiled_engine"
    assert benchmarks_exc.value.validation_errors[0]["path"] == (
        "module_benchmarks.0.compiled_engine"
    )

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as validation_exc:
        client.get_runtime_release_validation()
    assert validation_exc.value.error_code == "invalid_runtime_contract_payload"
    assert validation_exc.value.details["cause"] == "conditions.0.condition"
    assert validation_exc.value.validation_errors[0]["path"] == "conditions.0.condition"


def test_decision_engine_client_get_runtime_benchmarks_rejects_shipping_module_count_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["shipping_manifest_modules"] += 1

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "benchmark_discovery_lane.shipping_manifest_modules"
    assert exc_info.value.validation_errors[0]["path"] == (
        "benchmark_discovery_lane.shipping_manifest_modules"
    )


def test_decision_engine_client_get_runtime_benchmarks_rejects_shipping_function_count_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_function_counts"][0] += 1

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_function_counts.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_function_counts.0"


def test_decision_engine_client_get_runtime_benchmarks_rejects_shipping_module_identity_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_modules"][0], payload["shipping_runtime_modules"][1] = (
        payload["shipping_runtime_modules"][1],
        payload["shipping_runtime_modules"][0],
    )

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_modules.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_modules.0"


def test_decision_engine_client_get_runtime_benchmarks_rejects_quality_gate_summary_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["evaluation_summary"]["benchmark_class_count"] += 1

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "evaluation_summary.benchmark_class_count"
    assert exc_info.value.validation_errors[0]["path"] == "evaluation_summary.benchmark_class_count"


def test_decision_engine_client_get_runtime_benchmarks_rejects_missing_discovered_shipping_module(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    discovery_index = next(
        index
        for index, entry in enumerate(payload["benchmark_discovery_lane"]["discovered_source_inventory"])
        if entry["import_path"] == payload["module_benchmarks"][0]["name"]
    )
    replacement_import_path = f"{payload['module_benchmarks'][0]['name']}_shadow"
    payload["benchmark_discovery_lane"]["discovered_source_inventory"][discovery_index][
        "import_path"
    ] = replacement_import_path

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.details["cause"] == "benchmark_discovery_lane.discovered_source_inventory"
    )
    assert exc_info.value.validation_errors[0]["path"] == (
        "benchmark_discovery_lane.discovered_source_inventory"
    )


def test_decision_engine_client_get_runtime_benchmarks_rejects_shipping_benchmark_artifact_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_artifacts"][0], payload["shipping_runtime_benchmark_artifacts"][1] = (
        payload["shipping_runtime_benchmark_artifacts"][1],
        payload["shipping_runtime_benchmark_artifacts"][0],
    )

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_benchmark_artifacts.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_benchmark_artifacts.0"


def test_decision_engine_client_get_runtime_benchmarks_rejects_shipping_compiled_artifact_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_artifacts"][0] = "build/mismatched-runtime-compiled-artifact.json"

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_compiled_artifacts.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_artifacts.0"


def test_decision_engine_client_get_runtime_benchmarks_rejects_shipping_compiled_engine_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_engines"][0] = "python_fallback"

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_compiled_engines.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_engines.0"


def test_decision_engine_client_get_runtime_benchmarks_rejects_invalid_slo_budget_applies_to(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["slo_budgets"][0]["applies_to"] = "shadow_realm_lane"

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "slo_budgets.0.applies_to"
    assert exc_info.value.validation_errors[0]["path"] == "slo_budgets.0.applies_to"


def test_decision_engine_client_get_runtime_benchmarks_rejects_invalid_non_shipping_rule(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["non_shipping_rule"] = "shadow_inventory_lane"

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "benchmark_discovery_lane.non_shipping_rule"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "benchmark_discovery_lane.non_shipping_rule"
    )


@pytest.mark.parametrize(
    ("shipping_field", "benchmark_field"),
    [
        ("shipping_runtime_max_cold_ms", "max_cold_ms"),
        ("shipping_runtime_max_warm_ms", "max_warm_ms"),
        ("shipping_runtime_max_hot_ms", "max_hot_ms"),
    ],
)
def test_decision_engine_client_get_runtime_benchmarks_rejects_shipping_latency_mismatch(
    monkeypatch,
    shipping_field: str,
    benchmark_field: str,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = DecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload[shipping_field][0] = payload["module_benchmarks"][0][benchmark_field] + 1.0

    def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == f"{shipping_field}.0"
    assert exc_info.value.validation_errors[0]["path"] == f"{shipping_field}.0"


@pytest.mark.parametrize(
    "method_name,path",
    [
        ("get_runtime_modules", "/v1/admin/runtime/modules"),
        ("get_runtime_benchmarks", "/v1/admin/runtime/benchmarks"),
        ("get_runtime_release_validation", "/v1/admin/runtime/validation"),
    ],
)
def test_decision_engine_client_runtime_admin_routes_propagate_missing_route(
    monkeypatch,
    method_name: str,
    path: str,
) -> None:
    client = DecisionEngineClient(api_key="de_test", base_url="https://example.test/self-host")

    def _fake_request(method: str, request_path: str, **kwargs):
        assert (method, request_path) == ("GET", path)
        raise NotFoundError(
            "missing",
            status_code=404,
            response_body={"error": {"code": "not_found"}},
        )

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(NotFoundError):
        getattr(client, method_name)()


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
    assert benchmarks.benchmarking.baselines[-1] == "Algenta Mojo-native path"
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


async def test_async_decision_engine_client_get_runtime_modules_rejects_invalid_benchmark_discovery_rule(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/modules")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_modules()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_contract.benchmark_discovery_rule"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_duplicate_benchmark_classes(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmarking"]["classes"].append(dict(payload["benchmarking"]["classes"][0]))

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "benchmarking.classes"
    assert exc_info.value.validation_errors[0]["path"] == "benchmarking.classes"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_duplicate_compiled_artifacts(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["compiled_artifacts"].append(dict(payload["compiled_artifacts"][0]))

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "compiled_artifacts"
    assert exc_info.value.validation_errors[0]["path"] == "compiled_artifacts"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_function_count_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_function_counts"][0] += 1

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_function_counts.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_function_counts.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_module_identity_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_modules"][0], payload["shipping_runtime_modules"][1] = (
        payload["shipping_runtime_modules"][1],
        payload["shipping_runtime_modules"][0],
    )

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_modules.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_modules.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_missing_discovered_shipping_module(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    discovery_index = next(
        index
        for index, entry in enumerate(payload["benchmark_discovery_lane"]["discovered_source_inventory"])
        if entry["import_path"] == payload["module_benchmarks"][0]["name"]
    )
    replacement_import_path = f"{payload['module_benchmarks'][0]['name']}_shadow"
    payload["benchmark_discovery_lane"]["discovered_source_inventory"][discovery_index][
        "import_path"
    ] = replacement_import_path

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.details["cause"] == "benchmark_discovery_lane.discovered_source_inventory"
    )
    assert exc_info.value.validation_errors[0]["path"] == (
        "benchmark_discovery_lane.discovered_source_inventory"
    )

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_benchmark_artifact_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_artifacts"][0], payload["shipping_runtime_benchmark_artifacts"][1] = (
        payload["shipping_runtime_benchmark_artifacts"][1],
        payload["shipping_runtime_benchmark_artifacts"][0],
    )

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_benchmark_artifacts.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_benchmark_artifacts.0"


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_compiled_artifact_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_artifacts"][0] = "build/mismatched-runtime-compiled-artifact.json"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_compiled_artifacts.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_artifacts.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_compiled_engine_mismatch(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_engines"][0] = "python_fallback"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "shipping_runtime_compiled_engines.0"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_compiled_engines.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_invalid_slo_budget_applies_to(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["slo_budgets"][0]["applies_to"] = "shadow_realm_lane"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "slo_budgets.0.applies_to"
    assert exc_info.value.validation_errors[0]["path"] == "slo_budgets.0.applies_to"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_invalid_non_shipping_rule(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["non_shipping_rule"] = "shadow_inventory_lane"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "benchmark_discovery_lane.non_shipping_rule"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "benchmark_discovery_lane.non_shipping_rule"
    )

    await client.aclose()


@pytest.mark.parametrize(
    ("shipping_field", "benchmark_field"),
    [
        ("shipping_runtime_max_cold_ms", "max_cold_ms"),
        ("shipping_runtime_max_warm_ms", "max_warm_ms"),
        ("shipping_runtime_max_hot_ms", "max_hot_ms"),
    ],
)
async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_shipping_latency_mismatch(
    monkeypatch,
    shipping_field: str,
    benchmark_field: str,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload[shipping_field][0] = payload["module_benchmarks"][0][benchmark_field] + 1.0

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == f"{shipping_field}.0"
    assert exc_info.value.validation_errors[0]["path"] == f"{shipping_field}.0"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_benchmarks_rejects_missing_compiled_artifact_reference(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["compiled_artifact"] = "build/missing-runtime-benchmark.json"
    payload["shipping_runtime_compiled_artifacts"][0] = "build/missing-runtime-benchmark.json"

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/benchmarks")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_benchmarks()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "module_benchmarks.0.compiled_artifact"
    assert exc_info.value.validation_errors[0]["path"] == "module_benchmarks.0.compiled_artifact"

    await client.aclose()


async def test_async_decision_engine_client_get_runtime_release_validation_rejects_duplicate_condition_evidence_paths(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["evidence_paths"].append(payload["conditions"][0]["evidence_paths"][0])

    async def _fake_request(method: str, path: str, **kwargs):
        assert (method, path) == ("GET", "/v1/admin/runtime/validation")
        assert kwargs == {}
        return payload

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as exc_info:
        await client.get_runtime_release_validation()

    assert exc_info.value.error_code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "conditions.0.evidence_paths"
    assert exc_info.value.validation_errors[0]["path"] == "conditions.0.evidence_paths"

    await client.aclose()


async def test_async_decision_engine_client_runtime_proof_surfaces_fail_closed_on_invalid_payloads(
    monkeypatch,
) -> None:
    from apps.runtime_manifest import (
        get_runtime_admin_benchmarks,
        get_runtime_admin_modules,
        get_runtime_manifest,
        get_runtime_release_validation,
    )

    client = AsyncDecisionEngineClient(api_key="de_test", base_url="http://localhost:8000")
    payloads = {
        "/v1/runtime/manifest": get_runtime_manifest().model_dump(mode="json"),
        "/v1/admin/runtime/modules": get_runtime_admin_modules().model_dump(mode="json"),
        "/v1/admin/runtime/benchmarks": get_runtime_admin_benchmarks().model_dump(mode="json"),
        "/v1/admin/runtime/validation": get_runtime_release_validation().model_dump(mode="json"),
    }
    payloads["/v1/runtime/manifest"]["maturity"]["bpe_tokenizer"] = "legendary"
    payloads["/v1/admin/runtime/modules"]["proof_matrix"][0]["status"] = "unknown_status"
    payloads["/v1/admin/runtime/benchmarks"]["module_benchmarks"][0]["compiled_engine"] = (
        "warp_core"
    )
    payloads["/v1/admin/runtime/validation"]["conditions"][0]["condition"] = (
        "teleport-validated"
    )

    async def _fake_request(method: str, path: str, **kwargs):
        assert method == "GET"
        assert kwargs == {}
        return payloads[path]

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as manifest_exc:
        await client.get_runtime_manifest()
    assert manifest_exc.value.error_code == "invalid_runtime_contract_payload"
    assert manifest_exc.value.details["cause"] == "maturity.bpe_tokenizer"
    assert manifest_exc.value.validation_errors[0]["path"] == "maturity.bpe_tokenizer"
    assert manifest_exc.value.field_errors[0]["path"] == "maturity.bpe_tokenizer"

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as modules_exc:
        await client.get_runtime_modules()
    assert modules_exc.value.error_code == "invalid_runtime_contract_payload"
    assert modules_exc.value.details["cause"] == "proof_matrix.0.status"
    assert modules_exc.value.validation_errors[0]["path"] == "proof_matrix.0.status"

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as benchmarks_exc:
        await client.get_runtime_benchmarks()
    assert benchmarks_exc.value.error_code == "invalid_runtime_contract_payload"
    assert benchmarks_exc.value.details["cause"] == "module_benchmarks.0.compiled_engine"
    assert benchmarks_exc.value.validation_errors[0]["path"] == (
        "module_benchmarks.0.compiled_engine"
    )

    with pytest.raises(DecisionEngineError, match="invalid signed payload") as validation_exc:
        await client.get_runtime_release_validation()
    assert validation_exc.value.error_code == "invalid_runtime_contract_payload"
    assert validation_exc.value.details["cause"] == "conditions.0.condition"
    assert validation_exc.value.validation_errors[0]["path"] == "conditions.0.condition"

    await client.aclose()


@pytest.mark.parametrize(
    "method_name,path",
    [
        ("get_runtime_modules", "/v1/admin/runtime/modules"),
        ("get_runtime_benchmarks", "/v1/admin/runtime/benchmarks"),
        ("get_runtime_release_validation", "/v1/admin/runtime/validation"),
    ],
)
async def test_async_decision_engine_client_runtime_admin_routes_propagate_missing_route(
    monkeypatch,
    method_name: str,
    path: str,
) -> None:
    client = AsyncDecisionEngineClient(
        api_key="de_test",
        base_url="https://example.test/self-host",
    )

    async def _fake_request(method: str, request_path: str, **kwargs):
        assert (method, request_path) == ("GET", path)
        raise NotFoundError(
            "missing",
            status_code=404,
            response_body={"error": {"code": "not_found"}},
        )

    monkeypatch.setattr(client, "_request", _fake_request)

    with pytest.raises(NotFoundError):
        await getattr(client, method_name)()

    await client.aclose()
