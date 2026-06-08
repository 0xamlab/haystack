"""Tests for test_runtime_manifest_model_validation: runtime_admin.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-2/tests/test_runtime_manifest_model_validation.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_manifest_model_validation_helpers import *  # noqa: F401,F403


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


