from __future__ import annotations

import json

from benchmarks.llm_compiled_runtime_benchmark import (
    DEFAULT_OUTPUT,
    TARGET_MODULES,
    _build_args,
    collect_target_modules,
)
from tests.llm_rollout_matrix import LLM_ROLLOUT_FUNCTIONS_BY_MODULE

SERVING_EXTENSION_MODULES = (
    "kv_cache",
    "paged_kv_cache",
    "continuous_batching",
    "inference_engine",
    "speculative_decoding",
    "generation_loop",
)


def test_llm_compiled_runtime_benchmark_collects_all_target_modules() -> None:
    modules = collect_target_modules()

    assert tuple(modules) == TARGET_MODULES
    assert len(TARGET_MODULES) == 22
    assert "word_tokenize" in {fn.name for fn in modules["text.tokenizer"]}
    assert "run_column_rank_v2" in {fn.name for fn in modules["vector_kernels.ranker"]}
    assert "build_query" in {fn.name for fn in modules["vector_kernels.table"]}
    assert "precision_at_k" in {fn.name for fn in modules["rerank_eval"]}
    assert "prompt_token_estimate" in {fn.name for fn in modules["inference_cost_latency"]}
    assert "kv_cache_total_memory" in {fn.name for fn in modules["kv_cache"]}
    assert "page_table_lookup" in {fn.name for fn in modules["paged_kv_cache"]}
    assert "iteration_level_batch_size" in {fn.name for fn in modules["continuous_batching"]}
    assert "decode_time_per_token" in {fn.name for fn in modules["inference_engine"]}
    assert "speculative_accept_prob" in {fn.name for fn in modules["speculative_decoding"]}
    assert "typical_sampling_accept" in {fn.name for fn in modules["generation_loop"]}


def test_llm_compiled_runtime_benchmark_build_args_handles_target_overrides() -> None:
    modules = collect_target_modules()

    text_word_ngrams = next(
        function for function in modules["text.tokenizer"] if function.name == "word_ngrams"
    )
    vector_rank = next(
        function
        for function in modules["vector_kernels.ranker"]
        if function.name == "run_column_rank_v2"
    )
    table_build = next(
        function for function in modules["vector_kernels.table"] if function.name == "build_query"
    )
    rerank_precision = next(
        function for function in modules["rerank_eval"] if function.name == "precision_at_k"
    )
    kv_cache_total = next(
        function for function in modules["kv_cache"] if function.name == "kv_cache_total_memory"
    )
    speculative_accept = next(
        function
        for function in modules["speculative_decoding"]
        if function.name == "speculative_accept_prob"
    )

    assert _build_args("text.tokenizer", text_word_ngrams) == [["alpha", "beta", "gamma"], 2]
    assert '"matches"' not in _build_args("vector_kernels.ranker", vector_rank)[0]
    assert _build_args("vector_kernels.table", table_build) == ["unit_price", 1, 1, 2]
    assert _build_args("rerank_eval", rerank_precision) == [[1, 0, 1, 1, 0], 5]
    assert _build_args("kv_cache", kv_cache_total) == [5.0, 5.0]
    assert _build_args("speculative_decoding", speculative_accept) == [5.0, 5.0]


def test_llm_compiled_runtime_benchmark_artifact_covers_serving_extension_modules() -> None:
    payload = json.loads(DEFAULT_OUTPUT.read_text())
    assert payload["failed_function_count"] == 0

    modules = payload["modules"]
    for module_name in SERVING_EXTENSION_MODULES:
        module = modules[module_name]
        assert module["function_count"] == 10
        assert set(module["functions"]) == set(LLM_ROLLOUT_FUNCTIONS_BY_MODULE[module_name])
        for function_payload in module["functions"].values():
            assert function_payload["engine_used"] == "mojo"
            assert float(function_payload["cold_ms"]) >= 0.0
            assert float(function_payload["warm_ms"]) >= 0.0
            assert float(function_payload["hot_ms"]) >= 0.0
