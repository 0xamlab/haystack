"""Tests for test_runtime_manifest_model_validation: producer_runtime.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-2/tests/test_runtime_manifest_model_validation.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_manifest_model_validation_helpers import *  # noqa: F401,F403


def test_producer_runtime_manifest_model_rejects_invalid_maturity_map_key() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["maturity"]["wormhole_kernel"] = payload["maturity"].pop("bpe_tokenizer")

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "maturity" in str(exc_info.value)
    assert "wormhole_kernel" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_supported_channel() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"][0] = "desktop_magic"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "supported_channels.0" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_module_channel() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["public_supported_channels"][0] = "desktop_magic"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "modules.0.public_supported_channels.0" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_module_id() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["name"] = "wormhole_kernel"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "modules.0.name" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_deployment_mode() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["deployment_mode"] = "shadow_realm"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "deployment_mode" in str(exc_info.value)


def test_producer_runtime_release_validation_model_rejects_invalid_deployment_mode() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["deployment_mode"] = "shadow_realm"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeReleaseValidationResponse.model_validate(payload)

    assert "deployment_mode" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_execution_transition() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["execution_model"]["allowed_transitions"][0] = "wormhole_opened"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "execution_model.allowed_transitions.0" in str(exc_info.value)


def test_producer_runtime_release_validation_model_rejects_invalid_release_condition() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["condition"] = "teleport-validated"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeReleaseValidationResponse.model_validate(payload)

    assert "conditions.0.condition" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_failure_code() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["typed_failures"][0]["code"] = "cosmic_timeout"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "typed_failures.0.code" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_benchmark_class_code() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmarking"]["classes"][0]["code"] = "B42"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "benchmarking.classes.0.code" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_benchmark_metric() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmarking"]["required_metrics"][0] = "p105"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "benchmarking.required_metrics.0" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_scheduler_minimize_objective() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["scheduler_model"]["minimize"][0] = "negative entropy"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "scheduler_model.minimize.0" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_invariant_name() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["system_invariants"][0]["name"] = "Everything Is Fine"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "system_invariants.0.name" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_module_proof_obligation() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["proof_obligations"][0] = "cosmic confidence"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "modules.0.proof_obligations.0" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_execution_validity_rule() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["execution_model"]["validity_rules"][0] = "time-travel-safe"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "execution_model.validity_rules.0" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_evaluation_dimension() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["evaluation_science"]["dimensions"][0] = "oracle correctness"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "evaluation_science.dimensions.0" in str(exc_info.value)


