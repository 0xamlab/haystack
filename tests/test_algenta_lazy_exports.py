from __future__ import annotations

import importlib
import sys
from pathlib import Path

from tests._manifest_backed_integrations import (
    assert_manifest_backed_integrations_equal,
)

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_algenta_root_uses_lazy_exports_for_heavy_surfaces() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "algenta" or module_name.startswith("algenta.")
    }
    for module_name in list(sys.modules):
        if module_name == "algenta" or module_name.startswith("algenta."):
            sys.modules.pop(module_name, None)

    try:
        algenta = importlib.import_module("algenta")

        assert "algenta.runtime" not in sys.modules
        assert "algenta.runtime_facade" not in sys.modules
        assert "algenta.mojo" not in sys.modules
        assert "algenta.mojo_entrypoints" not in sys.modules
        assert "algenta.mojo_errors" not in sys.modules
        assert "algenta.map" not in sys.modules
        assert "algenta.map_matching" not in sys.modules
        assert "algenta.map_query" not in sys.modules
        assert "algenta.map_models" not in sys.modules
        assert "algenta.runtime_connectors" not in sys.modules
        assert "algenta.runtime_connector_preview" not in sys.modules
        assert "algenta.runtime_connector_preview_cleanup" not in sys.modules
        assert "algenta.runtime_connector_preview_errors" not in sys.modules
        assert "algenta.runtime_connector_models" not in sys.modules
        assert "algenta.runtime_connector_model_common" not in sys.modules
        assert "algenta.runtime_connector_model_metadata" not in sys.modules
        assert "algenta.runtime_connector_model_preview" not in sys.modules
        assert "algenta.runtime_connector_model_dataset" not in sys.modules
        assert "algenta.simple" not in sys.modules

        query_output_cls = algenta.QueryOutput
        connector_metadata_cls = algenta.ConnectorMetadata
        contract_output_cls = algenta.PlatformContractOutput
        capability_provider_cls = algenta.CapabilityProviderOutput
        capability_route_cls = algenta.CapabilityRoutePlanOutput
        capability_execution_cls = algenta.CapabilityExecutionOutput
        runtime_manifest_output_cls = algenta.RuntimeManifestOutput
        runtime_supported_channel_enum = algenta.RuntimeSupportedChannel
        runtime_auxiliary_channel_enum = algenta.RuntimeAuxiliaryChannel
        runtime_feature_flag_channel_enum = algenta.RuntimeFeatureFlagChannel
        runtime_benchmark_baseline_enum = algenta.RuntimeBenchmarkBaseline
        runtime_benchmark_class_code_enum = algenta.RuntimeBenchmarkClassCode
        runtime_benchmark_metric_enum = algenta.RuntimeBenchmarkMetric
        runtime_deployment_mode_enum = algenta.RuntimeDeploymentMode
        runtime_evaluation_dimension_enum = algenta.RuntimeEvaluationDimension
        runtime_evaluation_method_enum = algenta.RuntimeEvaluationMethod
        runtime_execution_state_field_enum = algenta.RuntimeExecutionStateField
        runtime_execution_validity_rule_enum = algenta.RuntimeExecutionValidityRule
        runtime_external_nondeterminism_source_enum = (
            algenta.RuntimeExternalNondeterminismSource
        )
        runtime_failure_code_enum = algenta.RuntimeFailureCode
        runtime_execution_transition_enum = algenta.RuntimeExecutionTransition
        runtime_invariant_name_enum = algenta.RuntimeInvariantName
        runtime_artifact_lineage_step_enum = algenta.RuntimeArtifactLineageStep
        runtime_capability_field_enum = algenta.RuntimeCapabilityField
        runtime_capability_rule_enum = algenta.RuntimeCapabilityRule
        runtime_artifact_kind_enum = algenta.RuntimeArtifactKind
        runtime_compiled_engine_enum = algenta.RuntimeCompiledEngine
        runtime_benchmark_discovery_rule_enum = algenta.RuntimeBenchmarkDiscoveryRule
        runtime_non_shipping_rule_enum = algenta.RuntimeNonShippingRule
        runtime_signature_algorithm_enum = algenta.RuntimeSignatureAlgorithm
        runtime_signature_scope_enum = algenta.RuntimeSignatureScope
        runtime_layer_enum = algenta.RuntimeLayer
        runtime_module_id_enum = algenta.RuntimeModuleId
        runtime_public_endpoint_enum = algenta.RuntimePublicEndpoint
        runtime_admin_endpoint_enum = algenta.RuntimeAdminEndpoint
        runtime_feature_flag_endpoint_enum = algenta.RuntimeFeatureFlagEndpoint
        runtime_lineage_node_field_enum = algenta.RuntimeLineageNodeField
        runtime_memory_region_enum = algenta.RuntimeMemoryRegion
        runtime_memory_rule_enum = algenta.RuntimeMemoryRule
        runtime_maturity_enum = algenta.RuntimeMaturity
        runtime_nondeterminism_artifact_enum = algenta.RuntimeNondeterminismArtifact
        runtime_proof_obligation_enum = algenta.RuntimeProofObligation
        runtime_release_artifact_enum = algenta.RuntimeReleaseArtifact
        runtime_release_blocker_enum = algenta.RuntimeReleaseBlocker
        runtime_release_condition_enum = algenta.RuntimeReleaseCondition
        runtime_release_gate_id_enum = algenta.RuntimeReleaseGateId
        runtime_risk_level_enum = algenta.RuntimeRiskLevel
        runtime_scheduler_invariant_enum = algenta.RuntimeSchedulerInvariant
        runtime_scheduler_maximize_objective_enum = algenta.RuntimeSchedulerMaximizeObjective
        runtime_scheduler_minimize_objective_enum = algenta.RuntimeSchedulerMinimizeObjective
        runtime_scheduler_policy_enum = algenta.RuntimeSchedulerPolicy
        runtime_threat_class_enum = algenta.RuntimeThreatClass
        runtime_threat_control_enum = algenta.RuntimeThreatControl
        runtime_threat_rule_enum = algenta.RuntimeThreatRule
        runtime_release_validation_cls = algenta.RuntimeReleaseValidationOutput
        runtime_slo_budget_applies_to_enum = algenta.RuntimeSLOBudgetAppliesTo
        runtime_slo_budget_name_enum = algenta.RuntimeSLOBudgetName
        runtime_error_cls = algenta.AlgentaRuntimeError
        map_data_fn = algenta.map_data
        contract_version = algenta.CONTRACT_VERSION
        brand = algenta.BRAND
        default_base_url = algenta.DEFAULT_BASE_URL
        mcp_endpoint = algenta.MCP_ENDPOINT
        auth_scheme = algenta.AUTH_SCHEME
        legacy_headers = algenta.LEGACY_HEADERS
        deprecation_window_days = algenta.DEPRECATION_WINDOW_DAYS
        read_only_default = algenta.READ_ONLY_DEFAULT
        integrations = algenta.INTEGRATIONS
        primary_contract = algenta.PRIMARY_DATA_QUERY_CONTRACT
        capability_plane_contract = algenta.CAPABILITY_PLANE_CONTRACT

        assert query_output_cls.__name__ == "QueryOutput"
        assert connector_metadata_cls.__name__ == "ConnectorMetadata"
        assert contract_output_cls.__name__ == "PlatformContractOutput"
        assert capability_provider_cls.__name__ == "CapabilityProviderOutput"
        assert capability_route_cls.__name__ == "CapabilityRoutePlanOutput"
        assert capability_execution_cls.__name__ == "CapabilityExecutionOutput"
        assert runtime_manifest_output_cls.__name__ == "RuntimeManifestOutput"
        assert runtime_supported_channel_enum.__name__ == "RuntimeSupportedChannel"
        assert runtime_auxiliary_channel_enum.__name__ == "RuntimeAuxiliaryChannel"
        assert runtime_feature_flag_channel_enum.__name__ == "RuntimeFeatureFlagChannel"
        assert runtime_benchmark_baseline_enum.__name__ == "RuntimeBenchmarkBaseline"
        assert runtime_benchmark_class_code_enum.__name__ == "RuntimeBenchmarkClassCode"
        assert runtime_benchmark_metric_enum.__name__ == "RuntimeBenchmarkMetric"
        assert runtime_deployment_mode_enum.__name__ == "RuntimeDeploymentMode"
        assert runtime_evaluation_dimension_enum.__name__ == "RuntimeEvaluationDimension"
        assert runtime_evaluation_method_enum.__name__ == "RuntimeEvaluationMethod"
        assert runtime_execution_state_field_enum.__name__ == "RuntimeExecutionStateField"
        assert runtime_execution_validity_rule_enum.__name__ == "RuntimeExecutionValidityRule"
        assert (
            runtime_external_nondeterminism_source_enum.__name__
            == "RuntimeExternalNondeterminismSource"
        )
        assert runtime_failure_code_enum.__name__ == "RuntimeFailureCode"
        assert runtime_execution_transition_enum.__name__ == "RuntimeExecutionTransition"
        assert runtime_invariant_name_enum.__name__ == "RuntimeInvariantName"
        assert runtime_artifact_lineage_step_enum.__name__ == "RuntimeArtifactLineageStep"
        assert runtime_capability_field_enum.__name__ == "RuntimeCapabilityField"
        assert runtime_capability_rule_enum.__name__ == "RuntimeCapabilityRule"
        assert runtime_artifact_kind_enum.__name__ == "RuntimeArtifactKind"
        assert runtime_compiled_engine_enum.__name__ == "RuntimeCompiledEngine"
        assert (
            runtime_benchmark_discovery_rule_enum.__name__
            == "RuntimeBenchmarkDiscoveryRule"
        )
        assert runtime_non_shipping_rule_enum.__name__ == "RuntimeNonShippingRule"
        assert runtime_signature_algorithm_enum.__name__ == "RuntimeSignatureAlgorithm"
        assert runtime_signature_scope_enum.__name__ == "RuntimeSignatureScope"
        assert runtime_layer_enum.__name__ == "RuntimeLayer"
        assert runtime_module_id_enum.__name__ == "RuntimeModuleId"
        assert runtime_public_endpoint_enum.__name__ == "RuntimePublicEndpoint"
        assert runtime_admin_endpoint_enum.__name__ == "RuntimeAdminEndpoint"
        assert runtime_feature_flag_endpoint_enum.__name__ == "RuntimeFeatureFlagEndpoint"
        assert runtime_lineage_node_field_enum.__name__ == "RuntimeLineageNodeField"
        assert runtime_memory_region_enum.__name__ == "RuntimeMemoryRegion"
        assert runtime_memory_rule_enum.__name__ == "RuntimeMemoryRule"
        assert runtime_maturity_enum.__name__ == "RuntimeMaturity"
        assert (
            runtime_nondeterminism_artifact_enum.__name__
            == "RuntimeNondeterminismArtifact"
        )
        assert runtime_proof_obligation_enum.__name__ == "RuntimeProofObligation"
        assert runtime_release_artifact_enum.__name__ == "RuntimeReleaseArtifact"
        assert runtime_release_blocker_enum.__name__ == "RuntimeReleaseBlocker"
        assert runtime_release_condition_enum.__name__ == "RuntimeReleaseCondition"
        assert runtime_release_gate_id_enum.__name__ == "RuntimeReleaseGateId"
        assert runtime_risk_level_enum.__name__ == "RuntimeRiskLevel"
        assert runtime_scheduler_invariant_enum.__name__ == "RuntimeSchedulerInvariant"
        assert (
            runtime_scheduler_maximize_objective_enum.__name__
            == "RuntimeSchedulerMaximizeObjective"
        )
        assert (
            runtime_scheduler_minimize_objective_enum.__name__
            == "RuntimeSchedulerMinimizeObjective"
        )
        assert runtime_scheduler_policy_enum.__name__ == "RuntimeSchedulerPolicy"
        assert runtime_threat_class_enum.__name__ == "RuntimeThreatClass"
        assert runtime_threat_control_enum.__name__ == "RuntimeThreatControl"
        assert runtime_threat_rule_enum.__name__ == "RuntimeThreatRule"
        assert runtime_release_validation_cls.__name__ == "RuntimeReleaseValidationOutput"
        assert runtime_slo_budget_applies_to_enum.__name__ == "RuntimeSLOBudgetAppliesTo"
        assert runtime_slo_budget_name_enum.__name__ == "RuntimeSLOBudgetName"
        assert runtime_error_cls is algenta.CodnaRuntimeError
        assert callable(map_data_fn)
        assert contract_version == "v1.3"
        assert brand == "Algenta"
        assert default_base_url == "https://api.algenta.ai"
        assert mcp_endpoint == "https://api.algenta.ai/mcp/sse"
        assert auth_scheme == "bearer_api_key"
        assert legacy_headers == ("X-API-Key",)
        assert deprecation_window_days == 90
        assert read_only_default is True
        assert_manifest_backed_integrations_equal(
            integrations,
            sys.modules["algenta._contract"].INTEGRATIONS,
        )
        assert primary_contract["api"]["discovery_endpoint"] == "/v1/data"
        assert primary_contract["api"]["contract_endpoint"] == "/v1/meta/contract"
        assert primary_contract["mcp"]["query_batch_tool"] == "query_batch"
        assert primary_contract["mcp"]["contract_tool"] == "get_contract"
        assert (
            capability_plane_contract["api"]["route_capabilities_endpoint"]
            == "/v1/capabilities/route"
        )
        assert (
            capability_plane_contract["direct_sdk"]["typescript"]["route_capabilities_method"]
            == "routeCapabilities"
        )
        assert "algenta.runtime" not in sys.modules
        assert "algenta.runtime_facade" not in sys.modules
        assert "algenta.runtime_models" not in sys.modules
        assert "algenta.runtime_model_query_output" in sys.modules
        assert "algenta.runtime_model_capability_plane" in sys.modules
        assert "algenta.runtime_connector_models" not in sys.modules
        assert "algenta.runtime_connector_model_common" in sys.modules
        assert "algenta.runtime_connector_model_metadata" in sys.modules
        assert "algenta.runtime_connector_model_preview" not in sys.modules
        assert "algenta.runtime_connector_model_dataset" not in sys.modules
        assert "algenta.runtime_errors" in sys.modules
        assert "algenta._contract" in sys.modules
        assert "algenta.map" not in sys.modules
        assert "algenta.map_matching" in sys.modules
        assert "algenta.map_query" not in sys.modules
        assert "algenta.map_models" not in sys.modules
        assert "algenta.map_parsing" not in sys.modules

        for module_name in (
            "algenta.map",
            "algenta.map_matching",
            "algenta.map_models",
            "algenta.map_parsing",
            "algenta.map_query",
            "algenta.runtime_models",
            "algenta.runtime_facade",
            "algenta.runtime_model_query_output",
            "algenta.runtime_connector_models",
            "algenta.runtime_connector_model_common",
            "algenta.runtime_connector_model_metadata",
            "algenta.runtime_connector_model_preview",
            "algenta.runtime_connector_model_dataset",
            "algenta.runtime_errors",
        ):
            sys.modules.pop(module_name, None)

        runtime_cls = algenta.Runtime
        libraries_fn = algenta.libraries
        mojo_runtime_cls = algenta.MojoRuntime

        assert runtime_cls.__name__ == "Runtime"
        assert callable(libraries_fn)
        assert mojo_runtime_cls.__name__ == "MojoRuntime"
        assert "algenta.runtime" not in sys.modules
        assert "algenta.runtime_facade" in sys.modules
        assert "algenta.mojo" not in sys.modules
        assert "algenta.mojo_entrypoints" in sys.modules
        assert "algenta.mojo_errors" in sys.modules
        assert "algenta.mojo_runtime" in sys.modules
        assert "algenta.map" not in sys.modules
        assert "algenta.map_matching" not in sys.modules
        assert "algenta.map_models" not in sys.modules
        assert "algenta.map_parsing" not in sys.modules
        assert "algenta.map_query" not in sys.modules
        assert "algenta.runtime_models" not in sys.modules
        assert "algenta.runtime_connector_models" not in sys.modules
        assert "algenta.runtime_connector_model_common" not in sys.modules
        assert "algenta.runtime_connector_model_metadata" not in sys.modules
        assert "algenta.runtime_connector_model_preview" not in sys.modules
        assert "algenta.runtime_connector_model_dataset" not in sys.modules
        assert "algenta.runtime_connectors" not in sys.modules
        assert "algenta.runtime_connector_preview" not in sys.modules
        assert "algenta.runtime_connector_preview_cleanup" not in sys.modules
        assert "algenta.runtime_connector_preview_errors" not in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "algenta" or module_name.startswith("algenta."):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
