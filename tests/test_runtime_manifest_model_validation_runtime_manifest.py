"""Tests for test_runtime_manifest_model_validation: runtime_manifest.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-2/tests/test_runtime_manifest_model_validation.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_manifest_model_validation_helpers import *  # noqa: F401,F403


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_invalid_compiled_engine(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["compiled_engine"] = "warp_core"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "modules.0.compiled_engine" in str(exc_info.value)
    assert "warp_core" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_invalid_slo_budget_applies_to(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["slo_budgets"][0]["applies_to"] = "shadow_realm_lane"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "slo_budgets.0.applies_to" in str(exc_info.value)
    assert "shadow_realm_lane" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_invalid_benchmark_discovery_rule(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "shipping_contract.benchmark_discovery_rule" in str(exc_info.value)
    assert "shadow_runtime_contract" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_invalid_non_shipping_rule(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["non_shipping_rule"] = "shadow_inventory_lane"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "benchmark_discovery_lane.non_shipping_rule" in str(exc_info.value)
    assert "shadow_inventory_lane" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_invalid_artifact_kind(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["compiled_artifacts"][0]["kind"] = "ghost_bundle"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "compiled_artifacts.0.kind" in str(exc_info.value)
    assert "ghost_bundle" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_invalid_signature_algorithm(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["signature"]["algorithm"] = "sha1"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "signature.algorithm" in str(exc_info.value)
    assert "sha1" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_invalid_signature_scope(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["signature"]["scope"] = "manifest_scope_v2"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "signature.scope" in str(exc_info.value)
    assert "manifest_scope_v2" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_tuple_backed_supported_channels(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"] = ("python_sdk", "typescript_sdk", "cli", "mcp")

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "supported_channels" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_tuple_backed_nested_enum_lists(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["proof_obligations"] = ("numerical parity", "channel proof")

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    error_text = str(exc_info.value)
    assert "modules.0" in error_text
    assert "proof_obligations must be provided as a list" in error_text


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_duplicate_release_conditions(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["formal_release_theorem"]["required_conditions"].append("manifest-listed")

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "manifest-listed" in str(exc_info.value)
    assert "duplicate entries" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_duplicate_proof_matrix_layers(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["proof_matrix"].append(dict(payload["proof_matrix"][0]))

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "duplicate entries" in str(exc_info.value)
    assert "mojo_llm_runtime_core" in str(exc_info.value)


@pytest.mark.parametrize(
    ("mutate", "expected_path", "duplicate_value"),
    [
        (
            lambda payload: payload["modules"][0]["functions"].append(
                payload["modules"][0]["functions"][0]
            ),
            "modules.0.functions",
            "bpe_merge_rank_score",
        ),
        (
            lambda payload: payload["modules"][0]["proof_artifacts"].append(
                payload["modules"][0]["proof_artifacts"][0]
            ),
            "modules.0.proof_artifacts",
            "build/llm_rollout_proof_bundle.json",
        ),
        (
            lambda payload: payload["modules"][0]["public_supported_channels"].append(
                "python_sdk"
            ),
            "modules.0.public_supported_channels",
            "python_sdk",
        ),
        (
            lambda payload: payload["compiled_artifacts"].append(
                dict(payload["compiled_artifacts"][0])
            ),
            "compiled_artifacts",
            "build/llm_rollout_proof_bundle.json",
        ),
        (
            lambda payload: payload["execution_model"]["allowed_transitions"].append(
                "model_call_started"
            ),
            "execution_model.allowed_transitions",
            "model_call_started",
        ),
        (
            lambda payload: payload["proof_matrix"][0]["evidence_paths"].append(
                payload["proof_matrix"][0]["evidence_paths"][0]
            ),
            "proof_matrix.0.evidence_paths",
            "build/llm_rollout_proof_bundle.json",
        ),
        (
            lambda payload: payload["external_nondeterminism"]["sources"].append(
                "provider responses"
            ),
            "external_nondeterminism.sources",
            "provider responses",
        ),
        (
            lambda payload: payload["benchmarking"]["classes"].append(
                dict(payload["benchmarking"]["classes"][0])
            ),
            "benchmarking.classes",
            "B1",
        ),
        (
            lambda payload: payload["scheduler_model"]["policies"].append("FIFO"),
            "scheduler_model.policies",
            "FIFO",
        ),
    ],
)
@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_duplicate_nested_runtime_identifier_lists(
    model_cls: type[object],
    mutate,
    expected_path: str,
    duplicate_value: str,
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    mutate(payload)

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeManifestResult:
        assert expected_path in str(exc_info.value)
    assert duplicate_value in str(exc_info.value)
    assert "duplicate entries" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_discovered_source_inventory_count_mismatch(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["discovered_source_inventory"].pop()

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeManifestResult:
        assert (
            "benchmark_discovery_lane.discovered_source_modules must equal the number of "
            "discovered_source_inventory entries." in str(exc_info.value)
        )
    else:
        assert (
            "runtime benchmark discovery source module count does not match discovered source "
            "inventory" in str(exc_info.value)
        )


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_benchmark_shipping_function_count_mismatch(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["shipping_manifest_functions"] += 1

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeManifestResult:
        assert "benchmark_discovery_lane.shipping_manifest_functions" in str(exc_info.value)
    else:
        assert "benchmark discovery shipping function count does not match manifest modules" in str(
            exc_info.value
        )


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_integer_and_float_coercion(model_cls: type[object]) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["function_count"] = True
    payload["slo_budgets"][0]["p95_objective_ms"] = "800.0"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "modules.0.function_count" in str(exc_info.value)
    assert "slo_budgets.0.p95_objective_ms" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_invalid_kernel_promotion_status(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["promotion_status"] = "graduated"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "modules.0.promotion_status" in str(exc_info.value)
    assert "graduated" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeManifestResponse,
        RuntimeManifestResult,
    ],
)
def test_runtime_manifest_models_reject_shipping_kernel_missing_replay_proof_reference(
    model_cls: type[object],
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["replay_proof_ref"] = ""

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "replay_proof_ref" in str(exc_info.value)
    assert "shipping" in str(exc_info.value)


