from __future__ import annotations

import warnings

import pytest

from apps.api_server.main import app
from apps.runtime_manifest import (
    ExecutionTransition,
    ReleaseCondition,
    RuntimeAuxiliaryChannel,
    RuntimeBenchmarkBaseline,
    RuntimeBenchmarkClassCode,
    RuntimeBenchmarkMetric,
    RuntimeDeploymentMode,
    RuntimeEvaluationDimension,
    RuntimeEvaluationMethod,
    RuntimeExecutionStateField,
    RuntimeExecutionValidityRule,
    RuntimeExternalNondeterminismSource,
    RuntimeFailureCode,
    RuntimeFeatureFlagChannel,
    RuntimeFeatureFlagEndpoint,
    RuntimeInvariantName,
    RuntimeArtifactLineageStep,
    RuntimeAdminEndpoint,
    RuntimeCapabilityField,
    RuntimeCapabilityRule,
    RuntimeLayer,
    RuntimeLineageNodeField,
    RuntimeNondeterminismArtifact,
    RuntimeMemoryRegion,
    RuntimeMemoryRule,
    RuntimeModuleId,
    RuntimeMaturity,
    RuntimeProofObligation,
    RuntimePublicEndpoint,
    RuntimeReleaseArtifact,
    RuntimeReleaseBlocker,
    RuntimeReleaseGateId,
    RuntimeSchedulerInvariant,
    RuntimeSchedulerMaximizeObjective,
    RuntimeSchedulerMinimizeObjective,
    RuntimeSchedulerPolicy,
    RuntimeSLOBudgetName,
    RuntimeSupportedChannel,
    RuntimeThreatClass,
    RuntimeThreatControl,
    RuntimeThreatRule,
    RuntimeManifestBuildError,
    get_runtime_manifest,
    load_runtime_manifest,
    validate_runtime_manifest_payload,
)
from tests._asgi_client import SyncASGIClient
from tests.llm_rollout_matrix import LLM_ROLLOUT_FUNCTION_CASES, LLM_ROLLOUT_MODULE_NAMES


def test_runtime_manifest_route_matches_current_llm_rollout_contract() -> None:
    with SyncASGIClient(app) as client:
        response = client.get("/v1/runtime/manifest")

    assert response.status_code == 200
    payload = response.json()

    assert payload["runtime_version"] == "2026.05.0"
    assert payload["llm_core_manifest"] == "llm-core-v1"
    assert payload["module_manifest_version"] == "runtime-manifest-v1"
    assert payload["shipping_contract"]["module_count"] == len(LLM_ROLLOUT_MODULE_NAMES)
    assert payload["shipping_contract"]["function_count"] == len(LLM_ROLLOUT_FUNCTION_CASES)
    assert payload["supported_channels"] == [
        "python_sdk",
        "typescript_sdk",
        "cli",
        "mcp",
    ]
    assert payload["validated_auxiliary_channels"] == [
        "bundled_worker",
        "runtime_local",
    ]
    assert payload["feature_flag_channels"] == ["http_api_feature_flag"]

    modules = payload["modules"]
    assert [module["name"] for module in modules] == list(LLM_ROLLOUT_MODULE_NAMES)
    assert sum(module["function_count"] for module in modules) == len(LLM_ROLLOUT_FUNCTION_CASES)
    assert payload["advertised_capabilities"]["runtime_modules"] == list(LLM_ROLLOUT_MODULE_NAMES)
    assert set(payload["advertised_capabilities"]["public_endpoints"]) == {
        "/v1/meta/contract",
        "/v1/runtime/manifest",
    }
    assert payload["advertised_capabilities"]["admin_endpoints"] == [
        "/v1/admin/runtime/modules",
        "/v1/admin/runtime/benchmarks",
        "/v1/admin/runtime/validation",
    ]
    assert payload["advertised_capabilities"]["feature_flag_endpoints"] == [
        "/v1/libraries",
        "/v1/libraries/health",
        "/v1/libraries/execute",
    ]
    assert payload["modules"][0]["name"] == "bpe_tokenizer"

    for module in modules:
        assert module["maturity"] == "channel_covered"
        assert module["layer"] == "mojo_llm_runtime_core"
        assert module["capability_id"].startswith("mojo_llm_runtime_core.")
        assert module["owner"] == "algenta-runtime-core"
        assert module["contract_boundary"]
        assert module["public_supported_channels"] == payload["supported_channels"]
        assert module["validated_auxiliary_channels"] == payload["validated_auxiliary_channels"]
        assert module["feature_flag_channels"] == payload["feature_flag_channels"]
        assert module["promotion_status"] == "shipping"
        assert module["rollback_flag"].endswith(".rollback_to_python")
        assert module["benchmark_report_ref"] == module["benchmark_artifact"]
        assert module["parity_report_ref"] == "build/llm_rollout_parity_benchmark.json"
        assert module["schema_compat_report_ref"] == "tests/test_runtime_schema_surface.py"
        assert module["isolation_proof_ref"] == "tests/test_runtime_manifest.py"
        assert module["replay_proof_ref"] == "tests/test_runtime_release_validation.py"
        assert module["benchmark_speedup_x"] > 0
        assert module["max_cold_ms"] > 0
        assert module["max_warm_ms"] > 0
        assert module["max_hot_ms"] > 0
        assert module["proof_artifacts"]


def test_runtime_manifest_declares_formal_runtime_foundation_sections() -> None:
    typed_manifest = get_runtime_manifest()
    manifest = typed_manifest.model_dump(mode="json")

    assert manifest["policy_snapshot"]["snapshot_id"].startswith("execution-policy-default-v1:")
    assert manifest["schema_snapshot"]["snapshot_id"].startswith("platform-contract-v1:")
    assert manifest["benchmark_discovery_lane"]["shipping_manifest_modules"] == 22
    assert manifest["benchmark_discovery_lane"]["shipping_manifest_functions"] == 209
    discovered_source_inventory = manifest["benchmark_discovery_lane"]["discovered_source_inventory"]
    assert len(discovered_source_inventory) == manifest["benchmark_discovery_lane"][
        "discovered_source_modules"
    ]
    assert sum(
        entry["public_function_count"] for entry in discovered_source_inventory
    ) == manifest["benchmark_discovery_lane"]["discovered_public_functions"]
    assert discovered_source_inventory == sorted(
        discovered_source_inventory,
        key=lambda entry: entry["import_path"],
    )
    assert (
        manifest["benchmark_discovery_lane"]["discovered_source_modules"]
        > manifest["benchmark_discovery_lane"]["shipping_manifest_modules"]
    )
    assert {
        module["name"] for module in manifest["modules"]
    }.issubset({entry["import_path"] for entry in discovered_source_inventory})

    invariant_names = [entry["name"] for entry in manifest["system_invariants"]]
    assert invariant_names == [
        "Manifest Truth",
        "Replay Determinism",
        "Policy Monotonicity",
        "No Silent Fallback",
        "Audit Completeness",
        "Tenant Non-Interference",
    ]

    execution_model = manifest["execution_model"]
    assert execution_model["state_fields"] == [
        "request",
        "tenant",
        "workspace",
        "policy_snapshot",
        "schema_snapshot",
        "runtime_manifest",
        "model_backend",
        "tool_manifest",
        "checkpoint_log",
        "event_log",
        "decision_state",
    ]
    assert execution_model["allowed_transitions"] == [
        "model_call_started",
        "model_token_emitted",
        "tool_call_requested",
        "tool_call_approved",
        "tool_call_denied",
        "checkpoint_committed",
        "decision_plan_created",
        "simulation_started",
        "execution_started",
        "replay_started",
        "failure_emitted",
    ]
    assert execution_model["validity_rules"] == [
        "schema-valid",
        "policy-valid",
        "ordered",
        "replayable",
        "audit-visible",
    ]

    external = manifest["external_nondeterminism"]
    assert external["sources"] == [
        "provider responses",
        "MCP tool responses",
        "database snapshots",
        "clock time",
        "random seeds",
        "external API outputs",
    ]
    assert external["required_artifacts"] == [
        "provider response record",
        "tool or MCP response record",
        "data snapshot reference or query result hash",
        "clock snapshot",
        "seed record",
        "backend or version identifier",
    ]
    assert external["failure_codes"] == [
        "replay_mismatch",
        "external_dependency_unavailable",
    ]
    assert typed_manifest.external_nondeterminism.failure_codes[0] is RuntimeFailureCode.replay_mismatch

    lineage = manifest["artifact_lineage"]
    assert lineage["artifact_flow"] == [
        "input",
        "policy snapshot",
        "schema snapshot",
        "runtime manifest",
        "backend or model",
        "tool or MCP calls",
        "checkpoints",
        "decision plan",
        "execution record",
        "outcome",
        "evaluation result",
    ]
    assert lineage["required_node_fields"] == [
        "node_id",
        "artifact_type",
        "content_hash",
        "parent_hashes",
        "tenant_scope",
        "workspace_scope",
        "timestamp",
        "manifest_version",
        "policy_snapshot_id",
        "schema_snapshot_id",
    ]

    capability_algebra = manifest["capability_algebra"]
    assert capability_algebra["required_fields"] == [
        "tool_name",
        "input_schema",
        "output_schema",
        "side_effect_class",
        "risk_level",
        "required_policy",
        "replayability",
        "approval_required",
    ]
    assert capability_algebra["enums"] == {
        "side_effect_class": [
            "read_only",
            "write_scoped",
            "write_external",
            "exec_external",
            "network_external",
        ],
        "risk_level": ["low", "medium", "high", "critical"],
        "replayability": ["deterministic", "artifact_backed", "non_replayable"],
    }
    assert capability_algebra["rules"] == [
        "MCP tools are untrusted by default.",
        "No tool may execute without a capability record.",
        "Approvals and fallbacks derive from capability algebra, not ad hoc code paths.",
    ]
    promotion = manifest["kernel_promotion_criteria"]
    assert promotion["required_manifest_fields"] == [
        "capability_id",
        "owner",
        "contract_boundary",
        "promotion_status",
        "rollback_flag",
    ]
    assert promotion["required_proof_reference_fields"] == [
        "benchmark_report_ref",
        "parity_report_ref",
        "schema_compat_report_ref",
        "isolation_proof_ref",
        "replay_proof_ref",
    ]
    assert promotion["minimum_primary_metric_improvement_pct"] == 15.0
    assert promotion["maximum_adjacent_metric_regression_pct"] == 5.0
    assert "fixed-seed deterministic corpus" in promotion["deterministic_test_corpus_rule"]
    assert "Arrow and Parquet schema compatibility" in promotion["schema_compatibility_rule"]
    assert "rollback flag" in promotion["rollback_scope_rule"]
    assert "replay_mismatch" in promotion["replay_compatibility_rule"]

    proof_matrix = {entry["layer"]: entry for entry in manifest["proof_matrix"]}
    assert set(proof_matrix) == {
        "mojo_llm_runtime_core",
        "python_compatibility_ring",
        "llm_api_provider_layer",
        "agent_runtime",
        "decision_runtime",
        "enterprise_control_plane",
    }
    assert proof_matrix["mojo_llm_runtime_core"]["status"] == "channel_covered"
    assert proof_matrix["python_compatibility_ring"]["status"] == "experimental"
    assert proof_matrix["agent_runtime"]["status"] == "experimental"
    assert typed_manifest.system_invariants[0].name is RuntimeInvariantName.manifest_truth
    assert typed_manifest.execution_model.state_fields[0] is RuntimeExecutionStateField.request
    assert typed_manifest.execution_model.validity_rules[0] is RuntimeExecutionValidityRule.schema_valid
    assert (
        typed_manifest.external_nondeterminism.sources[0]
        is RuntimeExternalNondeterminismSource.provider_responses
    )
    assert (
        typed_manifest.external_nondeterminism.required_artifacts[0]
        is RuntimeNondeterminismArtifact.provider_response_record
    )
    assert typed_manifest.artifact_lineage.artifact_flow[0] is RuntimeArtifactLineageStep.input
    assert typed_manifest.artifact_lineage.required_node_fields[0] is RuntimeLineageNodeField.node_id
    assert typed_manifest.capability_algebra.required_fields[0] is RuntimeCapabilityField.tool_name
    assert (
        typed_manifest.capability_algebra.rules[0]
        is RuntimeCapabilityRule.mcp_tools_are_untrusted_by_default
    )
    assert typed_manifest.modules[0].name is RuntimeModuleId.bpe_tokenizer
    assert typed_manifest.modules[0].promotion_status.value == "shipping"
    assert typed_manifest.maturity[RuntimeModuleId.bpe_tokenizer] is RuntimeMaturity.channel_covered
    assert typed_manifest.modules[0].proof_obligations[0] is RuntimeProofObligation.numerical_parity
    assert typed_manifest.proof_matrix[0].obligations[0] is RuntimeProofObligation.numerical_parity
    assert typed_manifest.benchmarking.classes[0].code is RuntimeBenchmarkClassCode.microkernel_latency
    assert any(
        entry.code is RuntimeBenchmarkClassCode.provider_routing_overhead
        and entry.description == "provider routing overhead"
        and entry.evidence_paths
        == [
            "build/provider_routing_overhead_benchmark.json",
            "benchmarks/provider_routing_overhead_benchmark.py",
            "tests/test_provider_routing_overhead_benchmark.py",
        ]
        for entry in typed_manifest.benchmarking.classes
    )
    assert any(
        entry.code is RuntimeBenchmarkClassCode.checkpoint_replay_overhead
        and entry.description == "checkpoint and replay overhead"
        and entry.evidence_paths == []
        for entry in typed_manifest.benchmarking.classes
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
        for entry in typed_manifest.benchmarking.classes
    )
    assert typed_manifest.benchmarking.required_metrics[0] is RuntimeBenchmarkMetric.p50
    assert typed_manifest.benchmarking.baselines[-1] is RuntimeBenchmarkBaseline.algenta_mojo_native_path
    assert typed_manifest.scheduler_model.policies[0] is RuntimeSchedulerPolicy.fifo
    assert (
        typed_manifest.scheduler_model.minimize[0]
        is RuntimeSchedulerMinimizeObjective.tail_latency
    )
    assert (
        typed_manifest.scheduler_model.maximize[0]
        is RuntimeSchedulerMaximizeObjective.gpu_or_cpu_utilization
    )
    assert (
        typed_manifest.scheduler_model.invariants[0]
        is RuntimeSchedulerInvariant.no_request_starves_indefinitely
    )
    assert typed_manifest.slo_budgets[0].name is RuntimeSLOBudgetName.runtime_manifest_load
    assert typed_manifest.memory_model.regions[0] is RuntimeMemoryRegion.model_weights
    assert typed_manifest.memory_model.rules[0] is RuntimeMemoryRule.kv_pages_are_tenant_scoped
    assert typed_manifest.memory_model.failure_codes[0] is RuntimeFailureCode.kv_cache_exhausted
    assert (
        typed_manifest.evaluation_science.dimensions[0]
        is RuntimeEvaluationDimension.answer_correctness
    )
    assert (
        typed_manifest.evaluation_science.methods[0]
        is RuntimeEvaluationMethod.bootstrap_confidence_intervals
    )
    assert (
        typed_manifest.evaluation_science.release_blockers[0]
        is RuntimeReleaseBlocker.replay_success_regression
    )
    assert typed_manifest.threat_model.threat_classes[0] is RuntimeThreatClass.prompt_injection
    assert typed_manifest.threat_model.controls[0] is RuntimeThreatControl.tool_allowlists
    assert (
        typed_manifest.threat_model.non_negotiable_rules[0]
        is RuntimeThreatRule.mcp_tools_are_untrusted_by_default
    )
    assert (
        typed_manifest.release_artifact_bundle.required_artifacts[0]
        is RuntimeReleaseArtifact.signed_runtime_manifest
    )
    assert typed_manifest.typed_failures[0].code is RuntimeFailureCode.provider_timeout
    assert typed_manifest.release_gates[0].gate is RuntimeReleaseGateId.gate_a
    assert typed_manifest.advertised_capabilities.runtime_modules[0] is RuntimeModuleId.bpe_tokenizer
    assert (
        typed_manifest.advertised_capabilities.public_endpoints[0]
        is RuntimePublicEndpoint.meta_contract
    )
    assert (
        typed_manifest.advertised_capabilities.admin_endpoints[0]
        is RuntimeAdminEndpoint.runtime_modules
    )
    assert (
        typed_manifest.advertised_capabilities.feature_flag_endpoints[0]
        is RuntimeFeatureFlagEndpoint.libraries
    )


def test_runtime_manifest_signature_release_theorem_and_openapi_route_are_stable() -> None:
    manifest_a = get_runtime_manifest()
    manifest_b = get_runtime_manifest()

    assert manifest_a.manifest_digest == manifest_b.manifest_digest
    assert manifest_a.signature.signature_hex == manifest_b.signature.signature_hex
    assert manifest_a.signature.algorithm == "hmac-sha256"
    assert manifest_a.signature.key_id == "runtime-manifest-signing-v1"
    assert manifest_a.deployment_mode is RuntimeDeploymentMode.local_dev_daemon
    assert manifest_a.deployment_modes.current is RuntimeDeploymentMode.local_dev_daemon
    assert manifest_a.deployment_modes.supported_modes[0] is RuntimeDeploymentMode.saas
    assert manifest_a.supported_channels[0] is RuntimeSupportedChannel.python_sdk
    assert manifest_a.validated_auxiliary_channels[0] is RuntimeAuxiliaryChannel.bundled_worker
    assert (
        manifest_a.feature_flag_channels[0]
        is RuntimeFeatureFlagChannel.http_api_feature_flag
    )
    assert manifest_a.modules[0].layer is RuntimeLayer.mojo_llm_runtime_core
    assert manifest_a.shipping_contract.runtime_core_layer is RuntimeLayer.mojo_llm_runtime_core
    assert manifest_a.execution_model.allowed_transitions[0] is ExecutionTransition.model_call_started
    assert (
        manifest_a.formal_release_theorem.required_conditions[0]
        is ReleaseCondition.manifest_listed
    )

    theorem = manifest_a.formal_release_theorem.model_dump(mode="json")
    assert theorem["statement"] == (
        "A release is valid iff every advertised capability is manifest-listed, proof-backed, "
        "policy-covered, replay-tested, and deployment-mode validated."
    )
    assert theorem["required_conditions"] == [
        "manifest-listed",
        "proof-backed",
        "policy-covered",
        "replay-tested",
        "deployment-mode validated",
    ]

    compiled_artifact_paths = {artifact.path for artifact in manifest_a.compiled_artifacts}
    assert {
        "build/llm_rollout_proof_bundle.json",
        "build/llm_rollout_parity_benchmark.json",
        "build/llm_compiled_runtime_benchmark.json",
    }.issubset(compiled_artifact_paths)

    openapi = app.openapi()
    assert "/v1/runtime/manifest" in openapi["paths"]


def test_load_runtime_manifest_fails_closed_for_invalid_internal_signature_payload(
    monkeypatch,
) -> None:
    # _build_signature is defined in _builders. _public_api imported it
    # explicitly so it holds a local reference — patch BOTH binding sites so
    # the test's fault injection reaches the call site in load_runtime_manifest.
    import apps.runtime_manifest as runtime_manifest_module
    import apps.runtime_manifest._builders as runtime_manifest_builders
    import apps.runtime_manifest._public_api as runtime_manifest_public

    original_build_signature = runtime_manifest_builders._build_signature

    def _invalid_build_signature(payload: dict[str, object]):
        digest_hex, signature = original_build_signature(payload)
        return digest_hex, signature.model_copy(update={"signature_hex": ""})

    load_runtime_manifest.cache_clear()
    monkeypatch.setattr(runtime_manifest_builders, "_build_signature", _invalid_build_signature)
    monkeypatch.setattr(runtime_manifest_public, "_build_signature", _invalid_build_signature)

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        runtime_manifest_module.load_runtime_manifest(
            "test-invalid-manifest",
            True,
            "local_dev_daemon",
        )

    assert exc_info.value.code == "invalid_runtime_manifest_payload"
    assert exc_info.value.details["cause"] == "signature.signature_hex"
    assert exc_info.value.details["validation_errors"][0]["path"] == "signature.signature_hex"
    load_runtime_manifest.cache_clear()


def test_validate_runtime_manifest_payload_fails_closed_for_duplicate_release_conditions() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["formal_release_theorem"]["required_conditions"].append("manifest-listed")

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_manifest_payload(payload)

    assert exc_info.value.code == "invalid_runtime_manifest_payload"
    assert exc_info.value.details["cause"] == "formal_release_theorem.required_conditions"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "formal_release_theorem.required_conditions"
    )


def test_validate_runtime_manifest_payload_fails_closed_for_duplicate_module_public_channels() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["public_supported_channels"].append("python_sdk")

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_manifest_payload(payload)

    assert exc_info.value.code == "invalid_runtime_manifest_payload"
    assert exc_info.value.details["cause"] == "modules.0.public_supported_channels"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "modules.0.public_supported_channels"
    )


def test_validate_runtime_manifest_payload_fails_closed_for_duplicate_module_functions() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["functions"].append(payload["modules"][0]["functions"][0])

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_manifest_payload(payload)

    assert exc_info.value.code == "invalid_runtime_manifest_payload"
    assert exc_info.value.details["cause"] == "modules.0.functions"
    assert exc_info.value.details["validation_errors"][0]["path"] == "modules.0.functions"


def test_validate_runtime_manifest_payload_fails_closed_for_benchmark_shipping_function_mismatch() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["shipping_manifest_functions"] += 1

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_manifest_payload(payload)

    assert exc_info.value.code == "invalid_runtime_manifest_payload"
    assert exc_info.value.details["cause"] == (
        "benchmark_discovery_lane.shipping_manifest_functions"
    )
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "benchmark_discovery_lane.shipping_manifest_functions"
    )


def test_load_runtime_manifest_fails_closed_for_invalid_internal_module_payload(
    monkeypatch,
) -> None:
    # Same pattern as the signature-payload test: patch both binding sites
    # (_builders defines it, _public_api imported it).
    import apps.runtime_manifest as runtime_manifest_module
    import apps.runtime_manifest._builders as runtime_manifest_builders
    import apps.runtime_manifest._public_api as runtime_manifest_public

    original_build_module_entries = runtime_manifest_builders._build_module_entries

    def _invalid_build_module_entries(*args, **kwargs):
        modules = original_build_module_entries(*args, **kwargs)
        modules[0].name = "wormhole_kernel"
        return modules

    load_runtime_manifest.cache_clear()
    monkeypatch.setattr(
        runtime_manifest_builders,
        "_build_module_entries",
        _invalid_build_module_entries,
    )
    monkeypatch.setattr(
        runtime_manifest_public,
        "_build_module_entries",
        _invalid_build_module_entries,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeManifestBuildError) as exc_info:
            runtime_manifest_module.load_runtime_manifest(
                "test-invalid-manifest",
                True,
                "local_dev_daemon",
            )

    assert exc_info.value.code == "invalid_runtime_manifest_payload"
    assert exc_info.value.details["cause"] == "modules.0.name"
    assert exc_info.value.details["validation_errors"][0]["path"] == "modules.0.name"
    assert caught == []
    load_runtime_manifest.cache_clear()
