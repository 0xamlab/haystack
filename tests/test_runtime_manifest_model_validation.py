from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.runtime_manifest import (
    get_runtime_admin_benchmarks,
    get_runtime_admin_modules,
    get_runtime_manifest,
    get_runtime_release_validation,
)

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

decision_engine_manifest_models = importlib.import_module("decision_engine.models_runtime_manifest")
algenta_manifest_models = importlib.import_module("algenta.runtime_model_manifest")
producer_runtime_manifest_models = importlib.import_module("apps.runtime_manifest")

RuntimeAdminModulesOutput = algenta_manifest_models.RuntimeAdminModulesOutput
RuntimeAdminBenchmarksOutput = algenta_manifest_models.RuntimeAdminBenchmarksOutput
RuntimeManifestOutput = algenta_manifest_models.RuntimeManifestOutput
RuntimeReleaseValidationOutput = algenta_manifest_models.RuntimeReleaseValidationOutput
RuntimeAdminModulesResult = decision_engine_manifest_models.RuntimeAdminModulesResult
RuntimeAdminBenchmarksResult = decision_engine_manifest_models.RuntimeAdminBenchmarksResult
RuntimeManifestResult = decision_engine_manifest_models.RuntimeManifestResult
ProducerRuntimeAdminBenchmarksResponse = (
    producer_runtime_manifest_models.RuntimeAdminBenchmarksResponse
)
ProducerRuntimeAdminModulesResponse = producer_runtime_manifest_models.RuntimeAdminModulesResponse
ProducerRuntimeReleaseValidationResponse = (
    producer_runtime_manifest_models.RuntimeReleaseValidationResponse
)
ProducerRuntimeManifestResponse = producer_runtime_manifest_models.RuntimeManifestResponse


def test_python_runtime_manifest_model_rejects_invalid_module_maturity() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["maturity"] = "legendary"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "modules.0.maturity" in str(exc_info.value)


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


def test_algenta_runtime_manifest_model_rejects_invalid_compiled_engine() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["compiled_engine"] = "warp_core"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

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


def test_algenta_runtime_manifest_model_rejects_invalid_slo_budget_applies_to() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["slo_budgets"][0]["applies_to"] = "shadow_realm_lane"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

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


def test_algenta_runtime_manifest_model_rejects_invalid_benchmark_discovery_rule() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

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


def test_algenta_runtime_manifest_model_rejects_invalid_non_shipping_rule() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["non_shipping_rule"] = "shadow_inventory_lane"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

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


def test_algenta_runtime_manifest_model_rejects_invalid_artifact_kind() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["compiled_artifacts"][0]["kind"] = "ghost_bundle"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

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


def test_algenta_runtime_manifest_model_rejects_invalid_signature_algorithm() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["signature"]["algorithm"] = "sha1"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

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


def test_algenta_runtime_manifest_model_rejects_invalid_signature_scope() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["signature"]["scope"] = "manifest_scope_v2"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "signature.scope" in str(exc_info.value)
    assert "manifest_scope_v2" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_maturity_map_key() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["maturity"]["wormhole_kernel"] = payload["maturity"].pop("bpe_tokenizer")

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "maturity" in str(exc_info.value)
    assert "wormhole_kernel" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_maturity_map_key() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["maturity"]["wormhole_kernel"] = payload["maturity"].pop("bpe_tokenizer")

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "maturity" in str(exc_info.value)
    assert "wormhole_kernel" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_invalid_maturity_map_key() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["maturity"]["wormhole_kernel"] = payload["maturity"].pop("bpe_tokenizer")

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "maturity.wormhole_kernel.[key]" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_supported_channel() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"][0] = "desktop_magic"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "supported_channels.0" in str(exc_info.value)


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
        ProducerRuntimeReleaseValidationResponse,
        decision_engine_manifest_models.RuntimeReleaseValidationResult,
    ],
)
def test_runtime_release_validation_models_reject_duplicate_conditions(
    model_cls: type[object],
) -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"].append(dict(payload["conditions"][0]))

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "conditions" in str(exc_info.value)
    assert "manifest-listed" in str(exc_info.value)


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
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_duplicate_compiled_artifacts(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["compiled_artifacts"].append(dict(payload["compiled_artifacts"][0]))

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "compiled_artifacts" in str(exc_info.value)
    assert "build/llm_rollout_proof_bundle.json" in str(exc_info.value)
    assert "duplicate entries" in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_duplicate_compiled_artifacts() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["compiled_artifacts"].append(dict(payload["compiled_artifacts"][0]))

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "compiled_artifacts" in str(exc_info.value)
    assert "build/llm_rollout_proof_bundle.json" in str(exc_info.value)
    assert "duplicate entries" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_quality_gate_class_missing_from_benchmarking_classes(
    model_cls: type[object],
) -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmarking"]["classes"] = [
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] != "B6"
    ]

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "quality_gate_benchmark_classes" in str(exc_info.value)
        assert "benchmarking.classes" in str(exc_info.value)
    else:
        assert (
            "runtime evaluation benchmark classes must be declared in benchmarking.classes"
            in str(exc_info.value)
        )


def test_algenta_runtime_admin_benchmark_model_rejects_quality_gate_class_missing_from_benchmarking_classes() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmarking"]["classes"] = [
        entry for entry in payload["benchmarking"]["classes"] if entry["code"] != "B6"
    ]

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "quality_gate_benchmark_classes must be declared in benchmarking.classes." in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_quality_gate_benchmark_count_mismatch(
    model_cls: type[object],
) -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["evaluation_summary"]["benchmark_class_count"] += 1

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "evaluation_summary.benchmark_class_count" in str(exc_info.value)
    else:
        assert (
            "runtime evaluation benchmark class count does not match quality_gate_benchmark_classes"
            in str(exc_info.value)
        )


def test_algenta_runtime_admin_benchmark_model_rejects_quality_gate_benchmark_count_mismatch() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["evaluation_summary"]["benchmark_class_count"] += 1

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert (
        "evaluation_summary.benchmark_class_count must equal the number of quality gate "
        "benchmark classes." in str(exc_info.value)
    )


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_replay_gate_summary_mismatch(
    model_cls: type[object],
) -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["evaluation_summary"]["replay_gate_enabled"] = False

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "evaluation_summary.replay_gate_enabled" in str(exc_info.value)
    else:
        assert (
            "runtime replay quality gate flag does not match benchmark, budget, and evaluation science coverage"
            in str(exc_info.value)
        )


def test_algenta_runtime_admin_benchmark_model_rejects_replay_gate_summary_mismatch() -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["evaluation_summary"]["replay_gate_enabled"] = False

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert (
        "evaluation_summary.replay_gate_enabled must match the replay benchmark, budget, "
        "and release blocker coverage." in str(exc_info.value)
    )


@pytest.mark.parametrize(
    ("field_name", "producer_message", "result_message"),
    [
        (
            "tool_call_quality_gate_enabled",
            "runtime tool-call quality gate flag does not match benchmark, budget, and evaluation science coverage",
            "evaluation_summary.tool_call_quality_gate_enabled",
        ),
        (
            "rag_quality_gate_enabled",
            "runtime RAG quality gate flag does not match benchmark and evaluation science coverage",
            "evaluation_summary.rag_quality_gate_enabled",
        ),
        (
            "decision_quality_gate_enabled",
            "runtime decision quality gate flag does not match benchmark, budget, and evaluation science coverage",
            "evaluation_summary.decision_quality_gate_enabled",
        ),
    ],
)
@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_non_replay_quality_gate_summary_mismatches(
    model_cls: type[object],
    field_name: str,
    producer_message: str,
    result_message: str,
) -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["evaluation_summary"][field_name] = False

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert result_message in str(exc_info.value)
    else:
        assert producer_message in str(exc_info.value)


@pytest.mark.parametrize(
    ("field_name", "expected_message"),
    [
        (
            "tool_call_quality_gate_enabled",
            "evaluation_summary.tool_call_quality_gate_enabled must match the tool-call benchmark, budget, and release blocker coverage.",
        ),
        (
            "rag_quality_gate_enabled",
            "evaluation_summary.rag_quality_gate_enabled must match the RAG benchmark and release blocker coverage.",
        ),
        (
            "decision_quality_gate_enabled",
            "evaluation_summary.decision_quality_gate_enabled must match the decision benchmark, budget, and release blocker coverage.",
        ),
    ],
)
def test_algenta_runtime_admin_benchmark_model_rejects_non_replay_quality_gate_summary_mismatches(
    field_name: str,
    expected_message: str,
) -> None:
    payload = get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["evaluation_summary"][field_name] = False

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert expected_message in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_shipping_module_count_mismatch(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["shipping_manifest_modules"] += 1

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "benchmark_discovery_lane.shipping_manifest_modules" in str(exc_info.value)
        assert "benchmark modules" in str(exc_info.value)
    else:
        assert "benchmark module inventory" in str(exc_info.value)


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


def test_algenta_runtime_manifest_model_rejects_discovered_source_inventory_count_mismatch() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["discovered_source_inventory"].pop()

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "benchmark_discovery_lane.discovered_source_modules" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_shipping_function_count_mismatch(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_function_counts"][0] += 1

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "shipping_runtime_function_counts.0" in str(exc_info.value)
        assert "module_benchmarks.0.function_count" in str(exc_info.value)
    else:
        assert "shipping function inventory does not match module_benchmarks.0.function_count" in str(
            exc_info.value
        )


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_shipping_speedup_mismatch(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_speedups_x"][0] += 1.0

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "shipping_runtime_benchmark_speedups_x.0" in str(exc_info.value)
        assert "module_benchmarks.0.benchmark_speedup_x" in str(exc_info.value)
    else:
        assert (
            "runtime benchmark shipping speedup inventory does not match "
            "module_benchmarks.0.benchmark_speedup_x" in str(exc_info.value)
        )


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_shipping_module_identity_mismatch(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_modules"][0], payload["shipping_runtime_modules"][1] = (
        payload["shipping_runtime_modules"][1],
        payload["shipping_runtime_modules"][0],
    )

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "shipping_runtime_modules.0" in str(exc_info.value)
    else:
        assert "module_benchmarks.0.name" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_missing_discovered_shipping_module(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    discovery_index = next(
        index
        for index, entry in enumerate(payload["benchmark_discovery_lane"]["discovered_source_inventory"])
        if entry["import_path"] == payload["module_benchmarks"][0]["name"]
    )
    replacement_import_path = f"{payload['module_benchmarks'][0]['name']}_shadow"
    payload["benchmark_discovery_lane"]["discovered_source_inventory"][discovery_index][
        "import_path"
    ] = replacement_import_path

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "module_benchmarks.0.name" in str(exc_info.value)
    assert payload["module_benchmarks"][0]["name"] in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_missing_discovered_shipping_module() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    discovery_index = next(
        index
        for index, entry in enumerate(payload["benchmark_discovery_lane"]["discovered_source_inventory"])
        if entry["import_path"] == payload["module_benchmarks"][0]["name"]
    )
    replacement_import_path = f"{payload['module_benchmarks'][0]['name']}_shadow"
    payload["benchmark_discovery_lane"]["discovered_source_inventory"][discovery_index][
        "import_path"
    ] = replacement_import_path

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "benchmark_discovery_lane.discovered_source_inventory" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_shipping_benchmark_artifact_mismatch(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_artifacts"][0], payload["shipping_runtime_benchmark_artifacts"][1] = (
        payload["shipping_runtime_benchmark_artifacts"][1],
        payload["shipping_runtime_benchmark_artifacts"][0],
    )

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "shipping_runtime_benchmark_artifacts.0" in str(exc_info.value)
        assert "module_benchmarks.0.benchmark_artifact" in str(exc_info.value)
    else:
        assert (
            "runtime benchmark shipping artifact inventory does not match "
            "module_benchmarks.0.benchmark_artifact" in str(exc_info.value)
        )


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_shipping_compiled_artifact_mismatch(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_artifacts"][0] = "build/mismatched-runtime-compiled-artifact.json"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "shipping_runtime_compiled_artifacts.0" in str(exc_info.value)
        assert "module_benchmarks.0.compiled_artifact" in str(exc_info.value)
    else:
        assert (
            "runtime benchmark shipping compiled artifact inventory does not match "
            "module_benchmarks.0.compiled_artifact" in str(exc_info.value)
        )


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_shipping_compiled_engine_mismatch(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_engines"][0] = "python_fallback"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "shipping_runtime_compiled_engines.0" in str(exc_info.value)
        assert "module_benchmarks.0.compiled_engine" in str(exc_info.value)
    else:
        assert (
            "runtime benchmark shipping compiled engine inventory does not match "
            "module_benchmarks.0.compiled_engine" in str(exc_info.value)
        )


@pytest.mark.parametrize(
    ("shipping_field", "benchmark_field"),
    [
        ("shipping_runtime_max_cold_ms", "max_cold_ms"),
        ("shipping_runtime_max_warm_ms", "max_warm_ms"),
        ("shipping_runtime_max_hot_ms", "max_hot_ms"),
    ],
)
@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_shipping_latency_mismatch(
    model_cls: type[object],
    shipping_field: str,
    benchmark_field: str,
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload[shipping_field][0] = payload["module_benchmarks"][0][benchmark_field] + 1.0

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert f"{shipping_field}.0" in str(exc_info.value)
        assert f"module_benchmarks.0.{benchmark_field}" in str(exc_info.value)
    else:
        assert (
            f"runtime benchmark shipping {benchmark_field} inventory does not match "
            f"module_benchmarks.0.{benchmark_field}" in str(exc_info.value)
        )


def test_algenta_runtime_admin_benchmark_model_rejects_shipping_module_identity_mismatch() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_modules"][0], payload["shipping_runtime_modules"][1] = (
        payload["shipping_runtime_modules"][1],
        payload["shipping_runtime_modules"][0],
    )

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "shipping_runtime_modules.0" in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_shipping_benchmark_artifact_mismatch() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_artifacts"][0], payload["shipping_runtime_benchmark_artifacts"][1] = (
        payload["shipping_runtime_benchmark_artifacts"][1],
        payload["shipping_runtime_benchmark_artifacts"][0],
    )

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "shipping_runtime_benchmark_artifacts.0" in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_shipping_compiled_artifact_mismatch() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_artifacts"][0] = "build/mismatched-runtime-compiled-artifact.json"

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "shipping_runtime_compiled_artifacts.0" in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_shipping_compiled_engine_mismatch() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_compiled_engines"][0] = "python_fallback"

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "shipping_runtime_compiled_engines.0" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_invalid_non_shipping_rule(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["non_shipping_rule"] = "shadow_inventory_lane"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "benchmark_discovery_lane.non_shipping_rule" in str(exc_info.value)
    assert "shadow_inventory_lane" in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_invalid_non_shipping_rule() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["non_shipping_rule"] = "shadow_inventory_lane"

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "benchmark_discovery_lane.non_shipping_rule" in str(exc_info.value)
    assert "shadow_inventory_lane" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_invalid_compiled_engine(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["compiled_engine"] = "warp_core"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "module_benchmarks.0.compiled_engine" in str(exc_info.value)
    assert "warp_core" in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_invalid_compiled_engine() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["compiled_engine"] = "warp_core"

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "module_benchmarks.0.compiled_engine" in str(exc_info.value)
    assert "warp_core" in str(exc_info.value)


@pytest.mark.parametrize(
    ("shipping_field", "benchmark_field"),
    [
        ("shipping_runtime_max_cold_ms", "max_cold_ms"),
        ("shipping_runtime_max_warm_ms", "max_warm_ms"),
        ("shipping_runtime_max_hot_ms", "max_hot_ms"),
    ],
)
def test_algenta_runtime_admin_benchmark_model_rejects_shipping_latency_mismatch(
    shipping_field: str,
    benchmark_field: str,
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload[shipping_field][0] = payload["module_benchmarks"][0][benchmark_field] + 1.0

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert f"{shipping_field}.0" in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_shipping_function_count_mismatch() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_function_counts"][0] += 1

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "shipping_runtime_function_counts.0" in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_shipping_speedup_mismatch() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["shipping_runtime_benchmark_speedups_x"][0] += 1.0

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "shipping_runtime_benchmark_speedups_x.0" in str(exc_info.value)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("benchmark_speedup_x", 0.0),
        ("max_cold_ms", 0.0),
        ("max_warm_ms", -1.0),
        ("max_hot_ms", 0.0),
    ],
)
@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_non_positive_benchmark_metrics(
    model_cls: type[object],
    field_name: str,
    bad_value: float,
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0][field_name] = bad_value
    if field_name == "benchmark_speedup_x":
        payload["shipping_runtime_benchmark_speedups_x"][0] = bad_value
    if field_name == "max_cold_ms":
        payload["shipping_runtime_max_cold_ms"][0] = bad_value
    if field_name == "max_warm_ms":
        payload["shipping_runtime_max_warm_ms"][0] = bad_value
    if field_name == "max_hot_ms":
        payload["shipping_runtime_max_hot_ms"][0] = bad_value

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert f"module_benchmarks.0.{field_name}" in str(exc_info.value)
    else:
        assert f"runtime benchmark module {field_name} must be positive" in str(exc_info.value)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("benchmark_speedup_x", 0.0),
        ("max_cold_ms", 0.0),
        ("max_warm_ms", -1.0),
        ("max_hot_ms", 0.0),
    ],
)
def test_algenta_runtime_admin_benchmark_model_rejects_non_positive_benchmark_metrics(
    field_name: str,
    bad_value: float,
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0][field_name] = bad_value
    if field_name == "max_cold_ms":
        payload["shipping_runtime_max_cold_ms"][0] = bad_value
    if field_name == "max_warm_ms":
        payload["shipping_runtime_max_warm_ms"][0] = bad_value
    if field_name == "max_hot_ms":
        payload["shipping_runtime_max_hot_ms"][0] = bad_value

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert f"module_benchmarks.0.{field_name}" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminBenchmarksResponse,
        RuntimeAdminBenchmarksResult,
    ],
)
def test_runtime_admin_benchmark_models_reject_missing_compiled_artifact_references(
    model_cls: type[object],
) -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["compiled_artifact"] = "build/missing-runtime-benchmark.json"
    payload["shipping_runtime_compiled_artifacts"][0] = "build/missing-runtime-benchmark.json"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminBenchmarksResult:
        assert "module_benchmarks.0.compiled_artifact" in str(exc_info.value)
    assert "compiled_artifacts" in str(exc_info.value)


def test_algenta_runtime_admin_benchmark_model_rejects_missing_compiled_artifact_references() -> None:
    payload = producer_runtime_manifest_models.get_runtime_admin_benchmarks().model_dump(mode="json")
    payload["module_benchmarks"][0]["compiled_artifact"] = "build/missing-runtime-benchmark.json"
    payload["shipping_runtime_compiled_artifacts"][0] = "build/missing-runtime-benchmark.json"

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminBenchmarksOutput.from_api(payload)

    assert "module_benchmarks.0.compiled_artifact" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeReleaseValidationResponse,
        decision_engine_manifest_models.RuntimeReleaseValidationResult,
    ],
)
def test_runtime_release_validation_models_reject_duplicate_condition_evidence_paths(
    model_cls: type[object],
) -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["evidence_paths"].append(payload["conditions"][0]["evidence_paths"][0])

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is decision_engine_manifest_models.RuntimeReleaseValidationResult:
        assert "conditions.0.evidence_paths" in str(exc_info.value)
    assert "/v1/runtime/manifest" in str(exc_info.value)
    assert "duplicate entries" in str(exc_info.value)


def test_algenta_runtime_release_validation_model_rejects_duplicate_condition_evidence_paths() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["evidence_paths"].append(payload["conditions"][0]["evidence_paths"][0])

    with pytest.raises(ValueError) as exc_info:
        RuntimeReleaseValidationOutput.from_api(payload)

    assert "conditions.0.evidence_paths" in str(exc_info.value)
    assert "/v1/runtime/manifest" in str(exc_info.value)
    assert "duplicate entries" in str(exc_info.value)


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


def test_algenta_runtime_manifest_model_rejects_benchmark_shipping_function_count_mismatch() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["benchmark_discovery_lane"]["shipping_manifest_functions"] += 1

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "benchmark_discovery_lane.shipping_manifest_functions" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeAdminModulesResponse,
        RuntimeAdminModulesResult,
    ],
)
def test_runtime_admin_modules_models_reject_invalid_benchmark_discovery_rule(
    model_cls: type[object],
) -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "shipping_contract.benchmark_discovery_rule" in str(exc_info.value)
    assert "shadow_runtime_contract" in str(exc_info.value)


def test_algenta_runtime_admin_modules_model_rejects_invalid_benchmark_discovery_rule() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["shipping_contract"]["benchmark_discovery_rule"] = "shadow_runtime_contract"

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminModulesOutput.from_api(payload)

    assert "shipping_contract.benchmark_discovery_rule" in str(exc_info.value)
    assert "shadow_runtime_contract" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        producer_runtime_manifest_models.RuntimeAdminModulesResponse,
        RuntimeAdminModulesResult,
    ],
)
def test_runtime_admin_modules_models_reject_summary_function_count_mismatch(
    model_cls: type[object],
) -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["summary"]["function_count"] += 1

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is RuntimeAdminModulesResult:
        assert "summary.function_count" in str(exc_info.value)
    else:
        assert "runtime admin function count does not match admin modules inventory" in str(
            exc_info.value
        )


def test_algenta_runtime_admin_modules_model_rejects_summary_function_count_mismatch() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["summary"]["function_count"] += 1

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminModulesOutput.from_api(payload)

    assert "summary.function_count" in str(exc_info.value)


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


def test_python_runtime_manifest_model_rejects_invalid_scheduler_invariant() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["scheduler_model"]["invariants"][0] = "Starvation is fine."

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "scheduler_model.invariants.0" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_invalid_memory_region() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["memory_model"]["regions"][0] = "dream buffer"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "memory_model.regions.0" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_invalid_memory_rule() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["memory_model"]["rules"][0] = "Reuse pages however you want."

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "memory_model.rules.0" in str(exc_info.value)


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


def test_python_runtime_manifest_model_rejects_invalid_capability_enum() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["capability_algebra"]["enums"]["risk_level"][0] = "impossible"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "capability_algebra.enums.risk_level.0" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_execution_validity_rule() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["execution_model"]["validity_rules"][0] = "time-travel-safe"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "execution_model.validity_rules.0" in str(exc_info.value)


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


def test_algenta_runtime_manifest_model_rejects_invalid_nondeterminism_artifact() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["external_nondeterminism"]["required_artifacts"][0] = "oracle transcript"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "external_nondeterminism.required_artifacts.0" in str(exc_info.value)
    assert "oracle transcript" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_invalid_admin_endpoint() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["advertised_capabilities"]["admin_endpoints"][0] = "/v1/admin/runtime/wormhole"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "advertised_capabilities.admin_endpoints.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_artifact_lineage_step() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["artifact_lineage"]["artifact_flow"][0] = "wormhole"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "artifact_lineage.artifact_flow.0" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_invalid_capability_field() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["capability_algebra"]["required_fields"][0] = "tool_scope"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "capability_algebra.required_fields.0" in str(exc_info.value)
    assert "tool_scope" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_capability_rule() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["capability_algebra"]["rules"][0] = "Capabilities can bypass policy."

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "capability_algebra.rules.0" in str(exc_info.value)


def test_producer_runtime_manifest_model_rejects_invalid_evaluation_dimension() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["evaluation_science"]["dimensions"][0] = "oracle correctness"

    with pytest.raises(ValidationError) as exc_info:
        ProducerRuntimeManifestResponse.model_validate(payload)

    assert "evaluation_science.dimensions.0" in str(exc_info.value)


def test_python_runtime_manifest_model_rejects_invalid_threat_class() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["threat_model"]["threat_classes"][0] = "friendly ghost"

    with pytest.raises(ValidationError) as exc_info:
        RuntimeManifestResult.model_validate(payload)

    assert "threat_model.threat_classes.0" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_invalid_threat_control() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["threat_model"]["controls"][0] = "trust everyone"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "threat_model.controls.0" in str(exc_info.value)
    assert "trust everyone" in str(exc_info.value)


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


def test_algenta_runtime_manifest_model_rejects_invalid_release_artifact() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["release_artifact_bundle"]["required_artifacts"][0] = "victory lap"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "release_artifact_bundle.required_artifacts.0" in str(exc_info.value)
    assert "victory lap" in str(exc_info.value)


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


def test_algenta_runtime_admin_modules_model_rejects_invalid_summary_layer_key() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["summary"]["layer_counts"]["moonbase_runtime"] = payload["summary"]["layer_counts"].pop(
        "mojo_llm_runtime_core"
    )

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminModulesOutput.from_api(payload)

    assert "summary.layer_counts.moonbase_runtime.[key]" in str(exc_info.value)


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


def test_algenta_runtime_manifest_model_rejects_invalid_module_maturity() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["maturity"] = "legendary"

    with pytest.raises(ValueError, match="legendary"):
        RuntimeManifestOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_capability_enum() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["capability_algebra"]["enums"]["side_effect_class"][0] = "teleport"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "capability_algebra.enums.side_effect_class.0" in str(exc_info.value)
    assert "teleport" in str(exc_info.value)


def test_algenta_runtime_admin_modules_model_rejects_invalid_proof_status() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["status"] = "unknown_status"

    with pytest.raises(ValueError, match="unknown_status"):
        RuntimeAdminModulesOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_supported_channel() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"][0] = "desktop_magic"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "supported_channels.0" in str(exc_info.value)
    assert "desktop_magic" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_tuple_backed_supported_channels() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["supported_channels"] = ("python_sdk", "typescript_sdk", "cli", "mcp")

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "supported_channels must be a list." in str(exc_info.value)


def test_algenta_runtime_admin_modules_model_rejects_tuple_backed_summary_counts() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["summary"]["maturity_counts"] = (("channel_covered", 22),)

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminModulesOutput.from_api(payload)

    assert "summary.maturity_counts must be a mapping." in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_duplicate_release_conditions() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["formal_release_theorem"]["required_conditions"].append("manifest-listed")

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "formal_release_theorem.required_conditions must be unique;" in str(exc_info.value)


def test_algenta_runtime_admin_modules_model_rejects_duplicate_proof_matrix_layers() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"].append(dict(payload["proof_matrix"][0]))

    with pytest.raises(ValueError) as exc_info:
        RuntimeAdminModulesOutput.from_api(payload)

    assert "proof_matrix must be unique;" in str(exc_info.value)


def test_algenta_runtime_release_validation_model_rejects_duplicate_conditions() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"].append(dict(payload["conditions"][0]))

    with pytest.raises(ValueError) as exc_info:
        RuntimeReleaseValidationOutput.from_api(payload)

    assert "conditions must be unique;" in str(exc_info.value)


@pytest.mark.parametrize(
    ("mutate", "expected_path", "duplicate_value"),
    [
        (
            lambda payload: payload["modules"][0]["public_supported_channels"].append(
                "python_sdk"
            ),
            "modules.0.public_supported_channels",
            "python_sdk",
        ),
        (
            lambda payload: payload["execution_model"]["allowed_transitions"].append(
                "model_call_started"
            ),
            "execution_model.allowed_transitions",
            "model_call_started",
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
def test_algenta_runtime_manifest_model_rejects_duplicate_nested_runtime_identifier_lists(
    mutate,
    expected_path: str,
    duplicate_value: str,
) -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    mutate(payload)

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert expected_path in str(exc_info.value)
    assert duplicate_value in str(exc_info.value)
    assert "duplicate entries" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_invalid_module_channel() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["public_supported_channels"][0] = "desktop_magic"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "modules.0.public_supported_channels.0" in str(exc_info.value)
    assert "desktop_magic" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_invalid_module_layer() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["layer"] = "moonbase_runtime"

    with pytest.raises(ValueError, match="moonbase_runtime"):
        RuntimeManifestOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_shipping_contract_layer() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["shipping_contract"]["runtime_core_layer"] = "moonbase_runtime"

    with pytest.raises(ValueError, match="moonbase_runtime"):
        RuntimeManifestOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_deployment_mode() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["deployment_mode"] = "shadow_realm"

    with pytest.raises(ValueError, match="shadow_realm"):
        RuntimeManifestOutput.from_api(payload)


def test_algenta_runtime_admin_modules_model_rejects_invalid_proof_layer() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["layer"] = "moonbase_runtime"

    with pytest.raises(ValueError, match="moonbase_runtime"):
        RuntimeAdminModulesOutput.from_api(payload)


def test_algenta_runtime_admin_modules_model_rejects_invalid_proof_obligation() -> None:
    payload = get_runtime_admin_modules().model_dump(mode="json")
    payload["proof_matrix"][0]["obligations"][0] = "cosmic confidence"

    with pytest.raises(ValueError, match="cosmic confidence"):
        RuntimeAdminModulesOutput.from_api(payload)


def test_algenta_runtime_release_validation_model_rejects_invalid_deployment_mode() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["deployment_mode"] = "shadow_realm"

    with pytest.raises(ValueError, match="shadow_realm"):
        algenta_manifest_models.RuntimeReleaseValidationOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_execution_transition() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["execution_model"]["allowed_transitions"][0] = "wormhole_opened"

    with pytest.raises(ValueError, match="wormhole_opened"):
        RuntimeManifestOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_evaluation_method() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["evaluation_science"]["methods"][0] = "oracle tuning"

    with pytest.raises(ValueError, match="oracle tuning"):
        RuntimeManifestOutput.from_api(payload)


def test_algenta_runtime_release_validation_model_rejects_invalid_release_condition() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["condition"] = "teleport-validated"

    with pytest.raises(ValueError, match="teleport-validated"):
        algenta_manifest_models.RuntimeReleaseValidationOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_failure_code() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["external_nondeterminism"]["failure_codes"][0] = "cosmic_timeout"

    with pytest.raises(ValueError, match="cosmic_timeout"):
        RuntimeManifestOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_release_gate_id() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["release_gates"][0]["gate"] = "Z"

    with pytest.raises(ValueError, match="Z"):
        RuntimeManifestOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_lineage_node_field() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["artifact_lineage"]["required_node_fields"][0] = "lineage_portal"

    with pytest.raises(ValueError, match="lineage_portal"):
        RuntimeManifestOutput.from_api(payload)


def test_algenta_runtime_manifest_model_rejects_invalid_release_blocker() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["evaluation_science"]["release_blockers"][0] = "cosmic drift"

    with pytest.raises(ValueError, match="cosmic drift"):
        RuntimeManifestOutput.from_api(payload)


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
        ProducerRuntimeReleaseValidationResponse,
        decision_engine_manifest_models.RuntimeReleaseValidationResult,
    ],
)
def test_runtime_release_validation_models_reject_boolean_coercion(
    model_cls: type[object],
) -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["valid_release"] = "yes"
    payload["conditions"][0]["satisfied"] = "no"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "valid_release" in str(exc_info.value)
    assert "conditions.0.satisfied" in str(exc_info.value)


def test_algenta_runtime_manifest_model_rejects_invalid_scalar_types() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["function_count"] = True
    payload["modules"][0]["functions"][0] = 7
    payload["slo_budgets"][0]["p95_objective_ms"] = "800.0"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    message = str(exc_info.value)
    assert "modules.0.function_count must be an integer." in message

    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["functions"][0] = 7

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "modules.0.functions.0 must be a string." in str(exc_info.value)

    payload = get_runtime_manifest().model_dump(mode="json")
    payload["slo_budgets"][0]["p95_objective_ms"] = "800.0"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "slo_budgets.0.p95_objective_ms must be a float." in str(exc_info.value)


def test_algenta_runtime_release_validation_model_rejects_invalid_boolean_types() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["valid_release"] = "yes"

    with pytest.raises(ValueError) as exc_info:
        algenta_manifest_models.RuntimeReleaseValidationOutput.from_api(payload)

    assert "release_validation.valid_release must be a boolean." in str(exc_info.value)

    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["satisfied"] = "no"

    with pytest.raises(ValueError) as exc_info:
        algenta_manifest_models.RuntimeReleaseValidationOutput.from_api(payload)

    assert "conditions.0.satisfied must be a boolean." in str(exc_info.value)


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


def test_algenta_runtime_manifest_model_rejects_invalid_kernel_promotion_status() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["promotion_status"] = "graduated"

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

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


def test_algenta_runtime_manifest_model_rejects_shipping_kernel_missing_replay_proof_reference() -> None:
    payload = get_runtime_manifest().model_dump(mode="json")
    payload["modules"][0]["replay_proof_ref"] = ""

    with pytest.raises(ValueError) as exc_info:
        RuntimeManifestOutput.from_api(payload)

    assert "modules.0.replay_proof_ref" in str(exc_info.value)
