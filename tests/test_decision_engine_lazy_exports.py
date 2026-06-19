from __future__ import annotations

import importlib
import sys
from pathlib import Path

from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations_equal,
)

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_decision_engine_root_uses_lazy_exports_for_clients_and_models() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine"
        or module_name.startswith("decision_engine.")
        or module_name == "httpx"
        or module_name.startswith("httpx.")
    }
    for module_name in list(sys.modules):
        if (
            module_name == "decision_engine"
            or module_name.startswith("decision_engine.")
            or module_name == "httpx"
            or module_name.startswith("httpx.")
        ):
            sys.modules.pop(module_name, None)

    try:
        decision_engine = importlib.import_module("decision_engine")

        assert "decision_engine.client" not in sys.modules
        assert "decision_engine.async_client" not in sys.modules
        assert "decision_engine.client_facade" not in sys.modules
        assert "decision_engine.async_client_facade" not in sys.modules
        assert "decision_engine.client_connector_surface" not in sys.modules
        assert "decision_engine.async_client_connector_surface" not in sys.modules
        assert "decision_engine.client_service_surface" not in sys.modules
        assert "decision_engine.async_client_service_surface" not in sys.modules
        assert "decision_engine.client_query_surface" not in sys.modules
        assert "decision_engine.client_simulation_surface" not in sys.modules
        assert "decision_engine.client_source_surface" not in sys.modules
        assert "decision_engine.async_client_query_surface" not in sys.modules
        assert "decision_engine.async_client_simulation_surface" not in sys.modules
        assert "decision_engine.async_client_source_surface" not in sys.modules
        assert "decision_engine.connector_surface_common" not in sys.modules
        assert "decision_engine.request_helpers" not in sys.modules
        assert "decision_engine.request_query_helpers" not in sys.modules
        assert "decision_engine.request_simulation_helpers" not in sys.modules
        assert "decision_engine.request_source_helpers" not in sys.modules
        assert "decision_engine.request_explain_helpers" not in sys.modules
        assert "decision_engine.models" not in sys.modules
        assert "decision_engine.models_query_result" not in sys.modules
        assert "decision_engine.models_connector_info" not in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_decision_envelope" not in sys.modules
        assert "decision_engine.models_metrics_summary" not in sys.modules
        assert "decision_engine.models_percentile_summary" not in sys.modules
        assert "decision_engine.models_run_metadata" not in sys.modules
        assert "decision_engine.models_simulation_common" not in sys.modules
        assert "decision_engine.exceptions" not in sys.modules
        assert "httpx" not in sys.modules

        query_result_cls = decision_engine.QueryResult
        connector_info_cls = decision_engine.ConnectorInfo
        envelope_cls = decision_engine.DecisionEnvelope
        contract_result_cls = decision_engine.PlatformContractResult
        capability_provider_cls = decision_engine.CapabilityProviderResult
        capability_route_cls = decision_engine.CapabilityRoutePlanResult
        capability_execution_cls = decision_engine.CapabilityExecutionResult
        runtime_manifest_result_cls = decision_engine.RuntimeManifestResult
        runtime_supported_channel_enum = decision_engine.RuntimeSupportedChannelResult
        runtime_auxiliary_channel_enum = decision_engine.RuntimeAuxiliaryChannelResult
        runtime_feature_flag_channel_enum = decision_engine.RuntimeFeatureFlagChannelResult
        runtime_benchmark_baseline_enum = decision_engine.RuntimeBenchmarkBaselineResult
        runtime_benchmark_class_code_enum = decision_engine.RuntimeBenchmarkClassCodeResult
        runtime_benchmark_metric_enum = decision_engine.RuntimeBenchmarkMetricResult
        runtime_deployment_mode_enum = decision_engine.RuntimeDeploymentModeResult
        runtime_evaluation_dimension_enum = decision_engine.RuntimeEvaluationDimensionResult
        runtime_evaluation_method_enum = decision_engine.RuntimeEvaluationMethodResult
        runtime_execution_state_field_enum = decision_engine.RuntimeExecutionStateFieldResult
        runtime_execution_validity_rule_enum = decision_engine.RuntimeExecutionValidityRuleResult
        runtime_external_nondeterminism_source_enum = (
            decision_engine.RuntimeExternalNondeterminismSourceResult
        )
        runtime_failure_code_enum = decision_engine.RuntimeFailureCodeResult
        runtime_execution_transition_enum = decision_engine.RuntimeExecutionTransitionResult
        runtime_invariant_name_enum = decision_engine.RuntimeInvariantNameResult
        runtime_artifact_lineage_step_enum = decision_engine.RuntimeArtifactLineageStepResult
        runtime_capability_field_enum = decision_engine.RuntimeCapabilityFieldResult
        runtime_capability_rule_enum = decision_engine.RuntimeCapabilityRuleResult
        runtime_artifact_kind_enum = decision_engine.RuntimeArtifactKindResult
        runtime_compiled_engine_enum = decision_engine.RuntimeCompiledEngineResult
        runtime_benchmark_discovery_rule_enum = (
            decision_engine.RuntimeBenchmarkDiscoveryRuleResult
        )
        runtime_non_shipping_rule_enum = decision_engine.RuntimeNonShippingRuleResult
        runtime_signature_algorithm_enum = decision_engine.RuntimeSignatureAlgorithmResult
        runtime_signature_scope_enum = decision_engine.RuntimeSignatureScopeResult
        runtime_layer_enum = decision_engine.RuntimeLayerResult
        runtime_module_id_enum = decision_engine.RuntimeModuleIdResult
        runtime_public_endpoint_enum = decision_engine.RuntimePublicEndpointResult
        runtime_admin_endpoint_enum = decision_engine.RuntimeAdminEndpointResult
        runtime_feature_flag_endpoint_enum = decision_engine.RuntimeFeatureFlagEndpointResult
        runtime_lineage_node_field_enum = decision_engine.RuntimeLineageNodeFieldResult
        runtime_memory_region_enum = decision_engine.RuntimeMemoryRegionResult
        runtime_memory_rule_enum = decision_engine.RuntimeMemoryRuleResult
        runtime_maturity_enum = decision_engine.RuntimeMaturityResult
        runtime_nondeterminism_artifact_enum = decision_engine.RuntimeNondeterminismArtifactResult
        runtime_proof_obligation_enum = decision_engine.RuntimeProofObligationResult
        runtime_release_artifact_enum = decision_engine.RuntimeReleaseArtifactResult
        runtime_release_blocker_enum = decision_engine.RuntimeReleaseBlockerResult
        runtime_release_condition_enum = decision_engine.RuntimeReleaseConditionResult
        runtime_release_gate_id_enum = decision_engine.RuntimeReleaseGateIdResult
        runtime_risk_level_enum = decision_engine.RuntimeRiskLevelResult
        runtime_scheduler_invariant_enum = decision_engine.RuntimeSchedulerInvariantResult
        runtime_scheduler_maximize_objective_enum = (
            decision_engine.RuntimeSchedulerMaximizeObjectiveResult
        )
        runtime_scheduler_minimize_objective_enum = (
            decision_engine.RuntimeSchedulerMinimizeObjectiveResult
        )
        runtime_scheduler_policy_enum = decision_engine.RuntimeSchedulerPolicyResult
        runtime_threat_class_enum = decision_engine.RuntimeThreatClassResult
        runtime_threat_control_enum = decision_engine.RuntimeThreatControlResult
        runtime_threat_rule_enum = decision_engine.RuntimeThreatRuleResult
        runtime_release_validation_cls = decision_engine.RuntimeReleaseValidationResult
        runtime_slo_budget_applies_to_enum = decision_engine.RuntimeSLOBudgetAppliesToResult
        runtime_slo_budget_name_enum = decision_engine.RuntimeSLOBudgetNameResult
        validation_error_cls = decision_engine.ValidationError
        contract_version = decision_engine.CONTRACT_VERSION
        brand = decision_engine.BRAND
        default_base_url = decision_engine.DEFAULT_BASE_URL
        mcp_endpoint = decision_engine.MCP_ENDPOINT
        auth_scheme = decision_engine.AUTH_SCHEME
        legacy_headers = decision_engine.LEGACY_HEADERS
        deprecation_window_days = decision_engine.DEPRECATION_WINDOW_DAYS
        read_only_default = decision_engine.READ_ONLY_DEFAULT
        integrations = decision_engine.INTEGRATIONS
        primary_contract = decision_engine.PRIMARY_DATA_QUERY_CONTRACT
        capability_plane_contract = decision_engine.CAPABILITY_PLANE_CONTRACT

        assert query_result_cls.__name__ == "QueryResult"
        assert connector_info_cls.__name__ == "ConnectorInfo"
        assert envelope_cls.__name__ == "DecisionEnvelope"
        assert contract_result_cls.__name__ == "PlatformContractResult"
        assert capability_provider_cls.__name__ == "CapabilityProviderResult"
        assert capability_route_cls.__name__ == "CapabilityRoutePlanResult"
        assert capability_execution_cls.__name__ == "CapabilityExecutionResult"
        assert runtime_manifest_result_cls.__name__ == "RuntimeManifestResult"
        assert runtime_supported_channel_enum.__name__ == "RuntimeSupportedChannelResult"
        assert runtime_auxiliary_channel_enum.__name__ == "RuntimeAuxiliaryChannelResult"
        assert runtime_feature_flag_channel_enum.__name__ == "RuntimeFeatureFlagChannelResult"
        assert runtime_benchmark_baseline_enum.__name__ == "RuntimeBenchmarkBaselineResult"
        assert runtime_benchmark_class_code_enum.__name__ == "RuntimeBenchmarkClassCodeResult"
        assert runtime_benchmark_metric_enum.__name__ == "RuntimeBenchmarkMetricResult"
        assert runtime_deployment_mode_enum.__name__ == "RuntimeDeploymentModeResult"
        assert runtime_evaluation_dimension_enum.__name__ == "RuntimeEvaluationDimensionResult"
        assert runtime_evaluation_method_enum.__name__ == "RuntimeEvaluationMethodResult"
        assert runtime_execution_state_field_enum.__name__ == "RuntimeExecutionStateFieldResult"
        assert (
            runtime_execution_validity_rule_enum.__name__
            == "RuntimeExecutionValidityRuleResult"
        )
        assert (
            runtime_external_nondeterminism_source_enum.__name__
            == "RuntimeExternalNondeterminismSourceResult"
        )
        assert runtime_failure_code_enum.__name__ == "RuntimeFailureCodeResult"
        assert runtime_execution_transition_enum.__name__ == "RuntimeExecutionTransitionResult"
        assert runtime_invariant_name_enum.__name__ == "RuntimeInvariantNameResult"
        assert runtime_artifact_lineage_step_enum.__name__ == "RuntimeArtifactLineageStepResult"
        assert runtime_capability_field_enum.__name__ == "RuntimeCapabilityFieldResult"
        assert runtime_capability_rule_enum.__name__ == "RuntimeCapabilityRuleResult"
        assert runtime_artifact_kind_enum.__name__ == "RuntimeArtifactKindResult"
        assert runtime_compiled_engine_enum.__name__ == "RuntimeCompiledEngineResult"
        assert (
            runtime_benchmark_discovery_rule_enum.__name__
            == "RuntimeBenchmarkDiscoveryRuleResult"
        )
        assert runtime_non_shipping_rule_enum.__name__ == "RuntimeNonShippingRuleResult"
        assert (
            runtime_signature_algorithm_enum.__name__
            == "RuntimeSignatureAlgorithmResult"
        )
        assert runtime_signature_scope_enum.__name__ == "RuntimeSignatureScopeResult"
        assert runtime_layer_enum.__name__ == "RuntimeLayerResult"
        assert runtime_module_id_enum.__name__ == "RuntimeModuleIdResult"
        assert runtime_public_endpoint_enum.__name__ == "RuntimePublicEndpointResult"
        assert runtime_admin_endpoint_enum.__name__ == "RuntimeAdminEndpointResult"
        assert (
            runtime_feature_flag_endpoint_enum.__name__
            == "RuntimeFeatureFlagEndpointResult"
        )
        assert runtime_lineage_node_field_enum.__name__ == "RuntimeLineageNodeFieldResult"
        assert runtime_memory_region_enum.__name__ == "RuntimeMemoryRegionResult"
        assert runtime_memory_rule_enum.__name__ == "RuntimeMemoryRuleResult"
        assert runtime_maturity_enum.__name__ == "RuntimeMaturityResult"
        assert (
            runtime_nondeterminism_artifact_enum.__name__
            == "RuntimeNondeterminismArtifactResult"
        )
        assert runtime_proof_obligation_enum.__name__ == "RuntimeProofObligationResult"
        assert runtime_release_artifact_enum.__name__ == "RuntimeReleaseArtifactResult"
        assert runtime_release_blocker_enum.__name__ == "RuntimeReleaseBlockerResult"
        assert runtime_release_condition_enum.__name__ == "RuntimeReleaseConditionResult"
        assert runtime_release_gate_id_enum.__name__ == "RuntimeReleaseGateIdResult"
        assert runtime_risk_level_enum.__name__ == "RuntimeRiskLevelResult"
        assert runtime_scheduler_invariant_enum.__name__ == "RuntimeSchedulerInvariantResult"
        assert (
            runtime_scheduler_maximize_objective_enum.__name__
            == "RuntimeSchedulerMaximizeObjectiveResult"
        )
        assert (
            runtime_scheduler_minimize_objective_enum.__name__
            == "RuntimeSchedulerMinimizeObjectiveResult"
        )
        assert runtime_scheduler_policy_enum.__name__ == "RuntimeSchedulerPolicyResult"
        assert runtime_threat_class_enum.__name__ == "RuntimeThreatClassResult"
        assert runtime_threat_control_enum.__name__ == "RuntimeThreatControlResult"
        assert runtime_threat_rule_enum.__name__ == "RuntimeThreatRuleResult"
        assert runtime_release_validation_cls.__name__ == "RuntimeReleaseValidationResult"
        assert (
            runtime_slo_budget_applies_to_enum.__name__
            == "RuntimeSLOBudgetAppliesToResult"
        )
        assert runtime_slo_budget_name_enum.__name__ == "RuntimeSLOBudgetNameResult"
        assert validation_error_cls.__name__ == "ValidationError"
        assert contract_version == "v1.3"
        assert brand == "Codna"
        assert default_base_url == "https://api.codna.ai"
        assert mcp_endpoint == "https://api.codna.ai/mcp/sse"
        assert auth_scheme == "bearer_api_key"
        assert legacy_headers == ("X-API-Key",)
        assert deprecation_window_days == 90
        assert read_only_default is True
        assert_manifest_backed_integrations_equal(
            integrations,
            sys.modules["decision_engine._contract"].INTEGRATIONS,
        )
        assert primary_contract["api"]["summary_endpoint"] == "/v1/data/{dataset_id}/summary"
        assert primary_contract["api"]["contract_endpoint"] == "/v1/meta/contract"
        assert (
            primary_contract["cli"]["query_batch_command"] == "de data query-batch <request.json>"
        )
        assert primary_contract["mcp"]["contract_tool"] == "get_contract"
        assert (
            capability_plane_contract["api"]["route_capabilities_endpoint"]
            == "/v1/capabilities/route"
        )
        assert (
            capability_plane_contract["direct_sdk"]["typescript"]["route_capabilities_method"]
            == "routeCapabilities"
        )
        assert "decision_engine.models" not in sys.modules
        assert "decision_engine.models_query_result" in sys.modules
        assert "decision_engine.models_connector_info" in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_decision_envelope" in sys.modules
        assert "decision_engine.models_capability_plane" in sys.modules
        assert "decision_engine.models_simulation_common" in sys.modules
        assert "decision_engine.models_metrics_summary" not in sys.modules
        assert "decision_engine.models_percentile_summary" not in sys.modules
        assert "decision_engine.models_run_metadata" not in sys.modules
        assert "decision_engine.exceptions" in sys.modules
        assert "decision_engine.client" not in sys.modules
        assert "decision_engine.async_client" not in sys.modules
        assert "decision_engine.client_facade" not in sys.modules
        assert "decision_engine.async_client_facade" not in sys.modules
        assert "decision_engine.client_connector_surface" not in sys.modules
        assert "decision_engine.async_client_connector_surface" not in sys.modules
        assert "decision_engine.client_service_surface" not in sys.modules
        assert "decision_engine.async_client_service_surface" not in sys.modules
        assert "decision_engine.client_query_surface" not in sys.modules
        assert "decision_engine.client_simulation_surface" not in sys.modules
        assert "decision_engine.client_source_surface" not in sys.modules
        assert "decision_engine.async_client_query_surface" not in sys.modules
        assert "decision_engine.async_client_simulation_surface" not in sys.modules
        assert "decision_engine.async_client_source_surface" not in sys.modules
        assert "decision_engine.connector_surface_common" not in sys.modules
        assert "decision_engine.request_helpers" not in sys.modules
        assert "decision_engine.request_query_helpers" not in sys.modules
        assert "decision_engine.request_simulation_helpers" not in sys.modules
        assert "decision_engine.request_source_helpers" not in sys.modules
        assert "decision_engine.request_explain_helpers" not in sys.modules
        assert "decision_engine._contract" in sys.modules
        assert "httpx" not in sys.modules

        for module_name in (
            "decision_engine.models",
            "decision_engine.models_query_result",
            "decision_engine.models_resolve_result",
            "decision_engine.models_connector_info",
            "decision_engine.models_connector_list_result",
            "decision_engine.models_connector_preview",
            "decision_engine.models_dataset",
            "decision_engine.models_decision_envelope",
            "decision_engine.models_metrics_summary",
            "decision_engine.models_percentile_summary",
            "decision_engine.models_run_metadata",
            "decision_engine.models_simulation_common",
            "decision_engine.models_batch_result",
            "decision_engine.models_simulation",
            "decision_engine.models_account",
        ):
            sys.modules.pop(module_name, None)

        async_client_cls = decision_engine.AsyncDecisionEngineClient
        async_algenta_client_cls = decision_engine.AsyncAlgentaClient

        assert async_client_cls.__name__ == "AsyncDecisionEngineClient"
        assert async_algenta_client_cls.__name__ == "AsyncAlgentaClient"
        assert issubclass(async_algenta_client_cls, async_client_cls)
        assert "decision_engine.async_client" not in sys.modules
        assert "decision_engine.async_client_facade" in sys.modules
        assert "decision_engine.client" not in sys.modules
        assert "decision_engine.client_facade" not in sys.modules
        assert "decision_engine.async_client_connector_surface" not in sys.modules
        assert "decision_engine.client_connector_surface" not in sys.modules
        assert "decision_engine.async_client_service_surface" not in sys.modules
        assert "decision_engine.client_service_surface" not in sys.modules
        assert "decision_engine.async_client_query_surface" not in sys.modules
        assert "decision_engine.async_client_simulation_surface" not in sys.modules
        assert "decision_engine.async_client_source_surface" not in sys.modules
        assert "decision_engine.client_query_surface" not in sys.modules
        assert "decision_engine.client_simulation_surface" not in sys.modules
        assert "decision_engine.client_source_surface" not in sys.modules
        assert "decision_engine.connector_surface_common" not in sys.modules
        assert "decision_engine.request_helpers" not in sys.modules
        assert "decision_engine.request_query_helpers" not in sys.modules
        assert "decision_engine.request_simulation_helpers" not in sys.modules
        assert "decision_engine.request_source_helpers" not in sys.modules
        assert "decision_engine.request_explain_helpers" not in sys.modules
        assert "decision_engine.models" not in sys.modules
        assert "decision_engine.models_query_result" not in sys.modules
        assert "decision_engine.models_connector_info" not in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_decision_envelope" not in sys.modules
        assert "decision_engine.models_simulation" not in sys.modules
        assert "decision_engine.models_account" not in sys.modules
        assert "httpx" not in sys.modules

        for module_name in (
            "decision_engine.models",
            "decision_engine.models_query_result",
            "decision_engine.models_resolve_result",
            "decision_engine.models_connector_info",
            "decision_engine.models_connector_preview",
            "decision_engine.models_dataset",
            "decision_engine.models_decision_envelope",
            "decision_engine.models_metrics_summary",
            "decision_engine.models_percentile_summary",
            "decision_engine.models_run_metadata",
            "decision_engine.models_batch_result",
            "decision_engine.models_simulation",
            "decision_engine.models_account",
        ):
            sys.modules.pop(module_name, None)

        client_cls = decision_engine.DecisionEngineClient
        algenta_client_cls = decision_engine.AlgentaClient

        assert client_cls.__name__ == "DecisionEngineClient"
        assert algenta_client_cls.__name__ == "AlgentaClient"
        assert issubclass(algenta_client_cls, client_cls)
        assert "decision_engine.client" not in sys.modules
        assert "decision_engine.client_facade" in sys.modules
        assert "decision_engine.async_client" not in sys.modules
        assert "decision_engine.client_connector_surface" not in sys.modules
        assert "decision_engine.async_client_connector_surface" not in sys.modules
        assert "decision_engine.client_service_surface" not in sys.modules
        assert "decision_engine.async_client_service_surface" not in sys.modules
        assert "decision_engine.client_query_surface" not in sys.modules
        assert "decision_engine.client_simulation_surface" not in sys.modules
        assert "decision_engine.client_source_surface" not in sys.modules
        assert "decision_engine.async_client_query_surface" not in sys.modules
        assert "decision_engine.async_client_simulation_surface" not in sys.modules
        assert "decision_engine.async_client_source_surface" not in sys.modules
        assert "decision_engine.connector_surface_common" not in sys.modules
        assert "decision_engine.request_helpers" not in sys.modules
        assert "decision_engine.request_query_helpers" not in sys.modules
        assert "decision_engine.request_simulation_helpers" not in sys.modules
        assert "decision_engine.request_source_helpers" not in sys.modules
        assert "decision_engine.request_explain_helpers" not in sys.modules
        assert "decision_engine.models" not in sys.modules
        assert "decision_engine.models_query_result" not in sys.modules
        assert "decision_engine.models_connector_info" not in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_decision_envelope" not in sys.modules
        assert "decision_engine.models_simulation" not in sys.modules
        assert "decision_engine.models_account" not in sys.modules
        assert "httpx" not in sys.modules
    finally:
        for module_name in list(sys.modules):
            if (
                module_name == "decision_engine"
                or module_name.startswith("decision_engine.")
                or module_name == "httpx"
                or module_name.startswith("httpx.")
            ):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
