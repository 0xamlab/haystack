from __future__ import annotations

import json

import pytest

from benchmarks.llm_rollout_parity_benchmark import (
    DEFAULT_OUTPUT_JSON,
    DEFAULT_OUTPUT_TXT,
    expected_library_counts,
    target_bench_libs,
    validate_rollout_summary,
)

SERVING_EXTENSION_LIBRARIES = (
    "kv_cache",
    "paged_kv_cache",
    "continuous_batching",
    "inference_engine",
    "speculative_decoding",
    "generation_loop",
)


def test_llm_rollout_parity_benchmark_targets_expected_library_ids() -> None:
    targets = target_bench_libs()

    assert len(targets) == 22
    assert targets[0] == "bpe_tokenizer"
    assert "text_tokenizer" in targets
    assert "vector_kernels_ranker" in targets
    assert "vector_kernels_table" in targets
    assert "kv_cache" in targets
    assert "paged_kv_cache" in targets
    assert "continuous_batching" in targets
    assert "inference_engine" in targets
    assert "speculative_decoding" in targets
    assert "generation_loop" in targets
    assert DEFAULT_OUTPUT_JSON.name == "llm_rollout_parity_benchmark.json"
    assert DEFAULT_OUTPUT_TXT.name == "llm_rollout_parity_benchmark.txt"


def test_llm_rollout_parity_benchmark_validates_public_function_counts() -> None:
    counts = expected_library_counts()
    summary = {
        "n_libraries": len(counts),
        "total_functions_compared": sum(counts.values()),
        "libraries": [
            {
                "lib": lib,
                "status": "ok",
                "n_functions": count,
                "n_compared": count,
            }
            for lib, count in sorted(counts.items())
        ],
    }

    validate_rollout_summary(summary)

    summary["libraries"][0]["n_compared"] += 1
    with pytest.raises(ValueError, match="n_compared mismatch"):
        validate_rollout_summary(summary)


def test_llm_rollout_parity_benchmark_artifact_covers_serving_extension_modules() -> None:
    payload = json.loads(DEFAULT_OUTPUT_JSON.read_text())
    libraries = {str(item["lib"]): item for item in payload["libraries"]}

    for lib in SERVING_EXTENSION_LIBRARIES:
        module = libraries[lib]
        assert module["status"] == "ok"
        assert module["n_functions"] == 10
        assert module["n_compared"] == 10
        assert float(module["speedup_x"]) > 0.0
        assert float(module["py_total_ns"]) > 0.0
        assert float(module["mojo_total_ns"]) > 0.0
