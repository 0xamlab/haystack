"""Tests for test_runtime_manifest_model_validation: python_runtime.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-2/tests/test_runtime_manifest_model_validation.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_manifest_model_validation_helpers import *  # noqa: F401,F403


def test_python_runtime_manifest_model_rejects_invalid_module_maturity() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["maturity"] = "legendary"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "modules.0.maturity" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_maturity_map_key() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["maturity"]["wormhole_kernel"] = payload["maturity"].pop("bpe_tokenizer")

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "maturity" in str(exc_info.value)
    assert "wormhole_kernel" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_scheduler_invariant() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["scheduler_model"]["invariants"][0] = "Starvation is fine."

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "scheduler_model.invariants.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_capability_enum() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["capability_algebra"]["enums"]["risk_level"][0] = "impossible"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "capability_algebra.enums.risk_level.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_external_nondeterminism_source() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["external_nondeterminism"]["sources"][0] = "oracle responses"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "external_nondeterminism.sources.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_public_endpoint() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["advertised_capabilities"]["public_endpoints"][0] = "/v1/not-real"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "advertised_capabilities.public_endpoints.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_artifact_lineage_step() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["artifact_lineage"]["artifact_flow"][0] = "wormhole"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "artifact_lineage.artifact_flow.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_capability_rule() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["capability_algebra"]["rules"][0] = "Capabilities can bypass policy."

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "capability_algebra.rules.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_threat_class() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["threat_model"]["threat_classes"][0] = "friendly ghost"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "threat_model.threat_classes.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_threat_rule() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["threat_model"]["non_negotiable_rules"][0] = "MCP tools are trusted by default."

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "threat_model.non_negotiable_rules.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_feature_flag_endpoint() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["advertised_capabilities"]["feature_flag_endpoints"][0] = "/v1/libraries/debug"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "advertised_capabilities.feature_flag_endpoints.0" in str(exc_info.value)


def test_python_runtime_admin_modules_model_rejects_invalid_proof_status() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["status"] = "unknown_status"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeAdminModulesResult.model_validate(payload)

    assert "proof_matrix.0.status" in str(exc_info.value)


def test_python_runtime_admin_modules_model_rejects_invalid_summary_maturity_key() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["summary"]["maturity_counts"]["legendary"] = payload["summary"]["maturity_counts"].pop(
        "channel_covered"
    )

    with pytest.raises(ValidationError) as exc_info:
        RuntimeAdminModulesResult.model_validate(payload)

    assert "summary.maturity_counts" in str(exc_info.value)
    assert "legendary" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_supported_channel() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"][0] = "desktop_magic"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "supported_channels.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_module_channel() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["public_supported_channels"][0] = "desktop_magic"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "modules.0.public_supported_channels.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_module_layer() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["layer"] = "moonbase_runtime"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "modules.0.layer" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_shipping_contract_layer() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["shipping_contract"]["runtime_core_layer"] = "moonbase_runtime"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "shipping_contract.runtime_core_layer" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_deployment_mode() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["deployment_mode"] = "shadow_realm"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "deployment_mode" in str(exc_info.value)


def test_python_runtime_admin_modules_model_rejects_invalid_proof_layer() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["layer"] = "moonbase_runtime"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeAdminModulesResult.model_validate(payload)

    assert "proof_matrix.0.layer" in str(exc_info.value)


def test_python_runtime_admin_modules_model_rejects_invalid_proof_obligation() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["obligations"][0] = "cosmic confidence"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeAdminModulesResult.model_validate(payload)

    assert "proof_matrix.0.obligations.0" in str(exc_info.value)


def test_python_runtime_release_validation_model_rejects_invalid_deployment_mode() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["deployment_mode"] = "shadow_realm"

    with pytest.raises(ValidationError) as exc_info:
        decision_engine_manifest_models.RuntimeReleaseValidationResult.model_validate(payload)

    assert "deployment_mode" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_execution_transition() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["execution_model"]["allowed_transitions"][0] = "wormhole_opened"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "execution_model.allowed_transitions.0" in str(exc_info.value)


def test_python_runtime_release_validation_model_rejects_invalid_release_condition() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["condition"] = "teleport-validated"

    with pytest.raises(ValidationError) as exc_info:
        decision_engine_manifest_models.RuntimeReleaseValidationResult.model_validate(payload)

    assert "conditions.0.condition" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_failure_code() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["memory_model"]["failure_codes"][0] = "cosmic_timeout"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "memory_model.failure_codes.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_scheduler_policy() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["scheduler_model"]["policies"][0] = "round_robin_quantum"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "scheduler_model.policies.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_benchmark_baseline() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmarking"]["baselines"][0] = "Quantum oracle"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "benchmarking.baselines.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_execution_state_field() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["execution_model"]["state_fields"][0] = "quantum_request"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "execution_model.state_fields.0" in str(exc_info.value)


