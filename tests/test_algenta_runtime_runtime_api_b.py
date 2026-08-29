"""Tests for test_algenta_runtime: runtime_api_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-3/tests/test_algenta_runtime.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_helpers import *  # noqa: F401,F403


@pytest.mark.parametrize(
    ("method_name", "client_method_name"),
    [
        ("get_runtime_manifest", "get_runtime_manifest"),
        ("get_runtime_modules", "get_runtime_modules"),
        ("get_runtime_benchmarks", "get_runtime_benchmarks"),
        ("get_runtime_release_validation", "get_runtime_release_validation"),
    ],
)
def test_runtime_api_mode_runtime_proof_surfaces_preserve_upstream_error_details(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    client_method_name: str,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")

    class _FakeRuntimeProofError(Exception):
        def __init__(self) -> None:
            super().__init__(f"{method_name}.proof_matrix[0].status invalid")
            self.error_code = "invalid_runtime_contract_payload"
            self.status_code = 0
            self.details = {
                "cause": f"{method_name}.proof_matrix[0].status",
                "validation_errors": [
                    {
                        "path": f"{method_name}.proof_matrix[0].status",
                        "message": "Input should be a valid enum value",
                        "type": "enum",
                    }
                ],
            }

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
    assert exc.value.details["source_status_code"] == 0
    assert exc.value.details["source_error_details"] == {
        "cause": f"{method_name}.proof_matrix[0].status",
        "validation_errors": [
            {
                "path": f"{method_name}.proof_matrix[0].status",
                "message": "Input should be a valid enum value",
                "type": "enum",
            }
        ],
    }
    assert exc.value.validation_errors[0]["path"] == f"{method_name}.proof_matrix[0].status"
    assert exc.value.field_errors[0]["path"] == f"{method_name}.proof_matrix[0].status"


def test_runtime_api_mode_get_runtime_manifest_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    manifest_payload = get_runtime_manifest().model_dump(mode="json")

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: manifest_payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    manifest = runtime.get_runtime_manifest()

    assert isinstance(manifest, RuntimeManifestOutput)
    assert manifest.shipping_contract.module_count == 22
    assert manifest.modules[0].name == "bpe_tokenizer"
    assert isinstance(manifest.modules[0].maturity, RuntimeMaturity)
    assert manifest.modules[0].maturity is RuntimeMaturity.channel_covered
    assert manifest.modules[0].public_supported_channels[0] is RuntimeSupportedChannel.python_sdk
    assert (
        manifest.modules[0].validated_auxiliary_channels[0]
        is RuntimeAuxiliaryChannel.bundled_worker
    )
    assert (
        manifest.modules[0].feature_flag_channels[0]
        is RuntimeFeatureFlagChannel.http_api_feature_flag
    )
    assert manifest.system_invariants[0].name is RuntimeInvariantName.manifest_truth
    assert manifest.execution_model.state_fields[0] is RuntimeExecutionStateField.request
    assert manifest.execution_model.validity_rules[0] is RuntimeExecutionValidityRule.schema_valid
    assert (
        manifest.execution_model.allowed_transitions[0]
        is RuntimeExecutionTransition.model_call_started
    )
    assert (
        manifest.external_nondeterminism.sources[0]
        is RuntimeExternalNondeterminismSource.provider_responses
    )
    assert (
        manifest.external_nondeterminism.required_artifacts[0]
        is RuntimeNondeterminismArtifact.provider_response_record
    )
    assert manifest.external_nondeterminism.failure_codes[0] is RuntimeFailureCode.replay_mismatch
    assert manifest.artifact_lineage.artifact_flow[0] is RuntimeArtifactLineageStep.input
    assert manifest.artifact_lineage.required_node_fields[0] is RuntimeLineageNodeField.node_id
    assert manifest.capability_algebra.required_fields[0] is RuntimeCapabilityField.tool_name
    assert (
        manifest.capability_algebra.rules[0]
        is RuntimeCapabilityRule.mcp_tools_are_untrusted_by_default
    )
    assert manifest.modules[0].name is RuntimeModuleId.bpe_tokenizer
    assert manifest.modules[0].promotion_status.value == "shipping"
    assert isinstance(manifest.capability_algebra.enums.side_effect_class[0], RuntimeSideEffectClass)
    assert isinstance(manifest.capability_algebra.enums.risk_level[-1], RuntimeRiskLevel)
    assert manifest.capability_algebra.enums.risk_level[-1] is RuntimeRiskLevel.critical
    assert isinstance(manifest.capability_algebra.enums.replayability[0], RuntimeReplayability)
    assert manifest.modules[0].layer is RuntimeLayer.mojo_llm_runtime_core
    assert manifest.shipping_contract.runtime_core_layer is RuntimeLayer.mojo_llm_runtime_core
    assert (
        manifest.shipping_contract.benchmark_discovery_rule
        is RuntimeBenchmarkDiscoveryRule.shipping_llm_rollout_only
    )
    assert (
        manifest.benchmark_discovery_lane.non_shipping_rule
        is RuntimeNonShippingRule.broader_mojo_inventory_not_advertised
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
    assert manifest.modules[0].proof_obligations[0] is RuntimeProofObligation.numerical_parity
    assert manifest.proof_matrix[0].layer is RuntimeLayer.mojo_llm_runtime_core
    assert isinstance(manifest.proof_matrix[0].status, RuntimeMaturity)
    assert manifest.proof_matrix[0].status is RuntimeMaturity.channel_covered
    assert manifest.proof_matrix[0].obligations[0] is RuntimeProofObligation.numerical_parity
    assert manifest.maturity[RuntimeModuleId.bpe_tokenizer] is RuntimeMaturity.channel_covered
    assert manifest.supported_channels[0] is RuntimeSupportedChannel.python_sdk
    assert manifest.validated_auxiliary_channels[0] is RuntimeAuxiliaryChannel.bundled_worker
    assert (
        manifest.feature_flag_channels[0]
        is RuntimeFeatureFlagChannel.http_api_feature_flag
    )
    assert manifest.deployment_mode is RuntimeDeploymentMode.self_hosted
    assert manifest.deployment_modes.current is RuntimeDeploymentMode.self_hosted
    assert manifest.deployment_modes.supported_modes[0] is RuntimeDeploymentMode.saas
    assert manifest.benchmarking.classes[0].code is RuntimeBenchmarkClassCode.microkernel_latency
    assert any(
        entry.code is RuntimeBenchmarkClassCode.provider_routing_overhead
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
        entry.code is RuntimeBenchmarkClassCode.checkpoint_replay_overhead
        and entry.description == "checkpoint and replay overhead"
        and entry.evidence_paths == []
        for entry in manifest.benchmarking.classes
    )
    assert manifest.benchmarking.required_metrics[0] is RuntimeBenchmarkMetric.p50
    assert manifest.benchmarking.baselines[-1] is RuntimeBenchmarkBaseline.algenta_mojo_native_path
    assert manifest.slo_budgets[0].name is RuntimeSLOBudgetName.runtime_manifest_load
    assert (
        manifest.slo_budgets[0].applies_to
        is RuntimeSLOBudgetAppliesTo.first_party_runtime_manifest_route
    )
    assert manifest.scheduler_model.policies[0] is RuntimeSchedulerPolicy.fifo
    assert manifest.scheduler_model.minimize[0] is RuntimeSchedulerMinimizeObjective.tail_latency
    assert (
        manifest.scheduler_model.maximize[0]
        is RuntimeSchedulerMaximizeObjective.gpu_or_cpu_utilization
    )
    assert (
        manifest.scheduler_model.invariants[0]
        is RuntimeSchedulerInvariant.no_request_starves_indefinitely
    )
    assert manifest.memory_model.regions[0] is RuntimeMemoryRegion.model_weights
    assert manifest.memory_model.rules[0] is RuntimeMemoryRule.kv_pages_are_tenant_scoped
    assert manifest.memory_model.failure_codes[0] is RuntimeFailureCode.kv_cache_exhausted
    assert manifest.evaluation_science.dimensions[0] is RuntimeEvaluationDimension.answer_correctness
    assert manifest.evaluation_science.methods[0] is RuntimeEvaluationMethod.bootstrap_confidence_intervals
    assert (
        manifest.evaluation_science.release_blockers[0]
        is RuntimeReleaseBlocker.replay_success_regression
    )
    assert manifest.typed_failures[0].code is RuntimeFailureCode.provider_timeout
    assert manifest.threat_model.threat_classes[0] is RuntimeThreatClass.prompt_injection
    assert manifest.threat_model.controls[0] is RuntimeThreatControl.tool_allowlists
    assert (
        manifest.threat_model.non_negotiable_rules[0]
        is RuntimeThreatRule.mcp_tools_are_untrusted_by_default
    )
    assert (
        manifest.release_artifact_bundle.required_artifacts[0]
        is RuntimeReleaseArtifact.signed_runtime_manifest
    )
    assert manifest.release_gates[0].gate is RuntimeReleaseGateId.gate_a
    assert manifest.immediate_implementation_sequence[0].pr == "PR 0"
    assert manifest.compiled_artifacts[0].kind is RuntimeArtifactKind.proof_bundle
    assert manifest.signature.algorithm is RuntimeSignatureAlgorithm.hmac_sha256
    assert manifest.signature.scope is RuntimeSignatureScope.control_plane_hmac_v1
    assert manifest.advertised_capabilities.runtime_modules[0] is RuntimeModuleId.bpe_tokenizer
    assert (
        manifest.advertised_capabilities.public_endpoints[0]
        is RuntimePublicEndpoint.meta_contract
    )
    assert (
        manifest.advertised_capabilities.admin_endpoints[0]
        is RuntimeAdminEndpoint.runtime_modules
    )
    assert (
        manifest.advertised_capabilities.feature_flag_endpoints[0]
        is RuntimeFeatureFlagEndpoint.libraries
    )
    assert manifest.to_dict()["supported_channels"][0] == "python_sdk"
    assert manifest.to_dict()["deployment_mode"] == "self_hosted"
    assert manifest.to_dict()["maturity"]["bpe_tokenizer"] == "channel_covered"


def test_runtime_api_mode_get_runtime_modules_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_modules().model_dump(mode="json")

    class _FakeClient:
        def get_runtime_modules(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    modules = runtime.get_runtime_modules()

    assert isinstance(modules, RuntimeAdminModulesOutput)
    assert modules.summary.module_count == 22
    assert modules.modules[0].name == "bpe_tokenizer"
    assert modules.modules[0].layer is RuntimeLayer.mojo_llm_runtime_core
    assert modules.modules[0].maturity is RuntimeMaturity.channel_covered
    assert modules.modules[0].public_supported_channels[0] is RuntimeSupportedChannel.python_sdk
    assert modules.summary.maturity_counts[RuntimeMaturity.channel_covered] == 22
    assert modules.summary.layer_counts[RuntimeLayer.mojo_llm_runtime_core] == 22
    assert modules.proof_matrix[0].layer is RuntimeLayer.mojo_llm_runtime_core
    assert modules.modules[0].proof_obligations[0] is RuntimeProofObligation.numerical_parity
    assert modules.proof_matrix[0].obligations[0] is RuntimeProofObligation.numerical_parity
    assert modules.proof_matrix[0].status is RuntimeMaturity.channel_covered
    assert (
        modules.shipping_contract.benchmark_discovery_rule
        is RuntimeBenchmarkDiscoveryRule.shipping_llm_rollout_only
    )
    assert modules.to_dict()["modules"][0]["maturity"] == "channel_covered"


def test_runtime_api_mode_get_runtime_benchmarks_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    benchmarks = runtime.get_runtime_benchmarks()

    assert isinstance(benchmarks, RuntimeAdminBenchmarksOutput)
    assert benchmarks.module_benchmarks[0].name is RuntimeModuleId.bpe_tokenizer
    assert benchmarks.module_benchmarks[0].function_count > 0
    assert (
        benchmarks.benchmark_discovery_lane.non_shipping_rule
        is RuntimeNonShippingRule.broader_mojo_inventory_not_advertised
    )
    assert len(benchmarks.benchmark_discovery_lane.discovered_source_inventory) == (
        benchmarks.benchmark_discovery_lane.discovered_source_modules
    )
    assert sum(
        entry.public_function_count
        for entry in benchmarks.benchmark_discovery_lane.discovered_source_inventory
    ) == benchmarks.benchmark_discovery_lane.discovered_public_functions
    assert benchmarks.shipping_runtime_modules[0] is RuntimeModuleId.bpe_tokenizer
    assert benchmarks.shipping_runtime_function_counts[0] == benchmarks.module_benchmarks[0].function_count
    assert (
        benchmarks.shipping_runtime_benchmark_artifacts[0]
        == benchmarks.module_benchmarks[0].benchmark_artifact
    )
    assert (
        benchmarks.shipping_runtime_compiled_artifacts[0]
        == benchmarks.module_benchmarks[0].compiled_artifact
    )
    assert benchmarks.compiled_artifacts[0].kind is RuntimeArtifactKind.proof_bundle
    assert benchmarks.module_benchmarks[0].compiled_engine is RuntimeCompiledEngine.mojo
    assert (
        benchmarks.shipping_runtime_compiled_engines[0]
        == benchmarks.module_benchmarks[0].compiled_engine
    )
    assert benchmarks.evaluation_science.dimensions[0] is RuntimeEvaluationDimension.answer_correctness
    assert (
        benchmarks.quality_gate_benchmark_classes[0].code
        is RuntimeBenchmarkClassCode.checkpoint_replay_overhead
    )
    assert any(
        entry.code is RuntimeBenchmarkClassCode.decision_workflow_completion_latency
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
    assert benchmarks.shipping_runtime_max_cold_ms[0] == benchmarks.module_benchmarks[0].max_cold_ms
    assert benchmarks.shipping_runtime_max_warm_ms[0] == benchmarks.module_benchmarks[0].max_warm_ms
    assert benchmarks.shipping_runtime_max_hot_ms[0] == benchmarks.module_benchmarks[0].max_hot_ms
    assert (
        benchmarks.benchmarking.classes[0].code
        is RuntimeBenchmarkClassCode.microkernel_latency
    )
    assert any(
        entry.code is RuntimeBenchmarkClassCode.provider_routing_overhead
        and entry.description == "provider routing overhead"
        and entry.evidence_paths
        == [
            "build/provider_routing_overhead_benchmark.json",
            "benchmarks/provider_routing_overhead_benchmark.py",
            "tests/test_provider_routing_overhead_benchmark.py",
        ]
        for entry in benchmarks.benchmarking.classes
    )
    assert benchmarks.benchmarking.required_metrics[0] is RuntimeBenchmarkMetric.p50
    assert benchmarks.benchmarking.baselines[-1] is RuntimeBenchmarkBaseline.algenta_mojo_native_path
    assert (
        benchmarks.slo_budgets[0].applies_to
        is RuntimeSLOBudgetAppliesTo.first_party_runtime_manifest_route
    )
    assert benchmarks.signature.scope is RuntimeSignatureScope.control_plane_hmac_v1


def test_runtime_api_mode_get_runtime_release_validation_uses_typed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_release_validation().model_dump(mode="json")

    class _FakeClient:
        def get_runtime_release_validation(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    validation = runtime.get_runtime_release_validation()

    assert isinstance(validation, RuntimeReleaseValidationOutput)
    assert validation.valid_release is True
    assert validation.conditions[0].condition is RuntimeReleaseCondition.manifest_listed
    assert validation.deployment_mode is RuntimeDeploymentMode.self_hosted
    assert validation.deployment_mode_raw == "local_dev_daemon"
    assert validation.conditions[0].evidence_paths[0] == "/v1/runtime/manifest"


def test_runtime_api_mode_get_runtime_release_validation_rejects_boolean_coercion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_release_validation

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["valid_release"] = "yes"
    payload["conditions"][0]["satisfied"] = "no"

    class _FakeClient:
        def get_runtime_release_validation(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_release_validation()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.details["cause"] == "conditions.0.satisfied"
    assert exc_info.value.validation_errors[0]["path"] == "conditions.0.satisfied"
    assert exc_info.value.field_errors[0]["message"] == "must be a boolean."


def test_runtime_api_mode_get_runtime_manifest_rejects_tuple_backed_supported_channels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"] = ("python_sdk", "typescript_sdk", "cli", "mcp")

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "supported_channels"
    assert exc_info.value.field_errors[0]["message"] == "must be a list."


def test_runtime_api_mode_get_runtime_manifest_rejects_duplicate_release_conditions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["formal_release_theorem"]["required_conditions"].append("manifest-listed")

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == (
        "formal_release_theorem.required_conditions"
    )
    assert exc_info.value.field_errors[0]["path"] == "formal_release_theorem.required_conditions"


def test_runtime_api_mode_get_runtime_manifest_rejects_duplicate_module_public_channels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["public_supported_channels"].append("python_sdk")

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "modules.0.public_supported_channels"
    assert exc_info.value.field_errors[0]["path"] == "modules.0.public_supported_channels"


def test_runtime_api_mode_get_runtime_manifest_rejects_duplicate_module_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["functions"].append(payload["modules"][0]["functions"][0])

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "modules.0.functions"
    assert exc_info.value.field_errors[0]["path"] == "modules.0.functions"


def test_runtime_api_mode_get_runtime_manifest_rejects_invalid_artifact_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["compiled_artifacts"][0]["kind"] = "ghost_bundle"

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "compiled_artifacts.0.kind"
    assert exc_info.value.field_errors[0]["path"] == "compiled_artifacts.0.kind"


def test_runtime_api_mode_get_runtime_manifest_rejects_invalid_benchmark_discovery_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )
    assert (
        exc_info.value.field_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )


def test_runtime_api_mode_get_runtime_manifest_rejects_benchmark_shipping_function_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_manifest

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["shipping_manifest_functions"] += 1

    class _FakeClient:
        def get_runtime_manifest(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_manifest()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == (
        "benchmark_discovery_lane.shipping_manifest_functions"
    )
    assert exc_info.value.field_errors[0]["path"] == (
        "benchmark_discovery_lane.shipping_manifest_functions"
    )


def test_runtime_api_mode_get_runtime_modules_rejects_duplicate_proof_matrix_layers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"].append(dict(payload["proof_matrix"][0]))

    class _FakeClient:
        def get_runtime_modules(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_modules()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "proof_matrix"
    assert exc_info.value.field_errors[0]["path"] == "proof_matrix"


def test_runtime_api_mode_get_runtime_modules_rejects_invalid_benchmark_discovery_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    class _FakeClient:
        def get_runtime_modules(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_modules()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert (
        exc_info.value.validation_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )
    assert (
        exc_info.value.field_errors[0]["path"]
        == "shipping_contract.benchmark_discovery_rule"
    )


def test_runtime_api_mode_get_runtime_modules_rejects_summary_function_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_modules

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["summary"]["function_count"] += 1

    class _FakeClient:
        def get_runtime_modules(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_modules()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "summary.function_count"
    assert exc_info.value.field_errors[0]["path"] == "summary.function_count"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_duplicate_benchmark_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmarking"]["classes"].append(dict(payload["benchmarking"]["classes"][0]))

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "benchmarking.classes"
    assert exc_info.value.field_errors[0]["path"] == "benchmarking.classes"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_function_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_function_counts"][0] += 1

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_function_counts.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_function_counts.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_shipping_module_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_modules"][0], payload["shipping_runtime_modules"][1] = (
        payload["shipping_runtime_modules"][1],
        payload["shipping_runtime_modules"][0],
    )

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "shipping_runtime_modules.0"
    assert exc_info.value.field_errors[0]["path"] == "shipping_runtime_modules.0"


def test_runtime_api_mode_get_runtime_benchmarks_rejects_quality_gate_summary_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.runtime_manifest import get_runtime_admin_benchmarks

    runtime = Runtime(mode="api", api_key="de_live_test", base_url="https://api.algenta.ai")
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["evaluation_summary"]["benchmark_class_count"] += 1

    class _FakeClient:
        def get_runtime_benchmarks(self) -> object:
            return SimpleNamespace(model_dump=lambda: payload)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="invalid signed payload") as exc_info:
        runtime.get_runtime_benchmarks()

    assert exc_info.value.code == "invalid_runtime_contract_payload"
    assert exc_info.value.validation_errors[0]["path"] == "evaluation_summary.benchmark_class_count"
    assert exc_info.value.field_errors[0]["path"] == "evaluation_summary.benchmark_class_count"


