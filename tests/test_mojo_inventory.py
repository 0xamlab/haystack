from __future__ import annotations

import time
from pathlib import Path

from apps.runtime import mojo_inventory


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_discover_source_modules_collects_recursive_modules(tmp_path: Path) -> None:
    engine_root = tmp_path / "mojo" / "engine"
    _write(engine_root / "finance.mojo", "fn npv() -> Float64:\n    return 1.0\n")
    _write(engine_root / "crypto" / "hash.mojo", "fn digest() -> Int:\n    return 1\n")
    _write(engine_root / "crypto" / "__init__.mojo", "")

    modules = mojo_inventory.discover_source_modules(engine_root)

    assert [module.import_path for module in modules] == ["crypto.hash", "finance"]
    assert [module.lib_id for module in modules] == ["crypto_hash", "finance"]
    assert [module.public_functions for module in modules] == [("digest",), ("npv",)]


def test_parse_test_all_import_modules_ignores_std_imports(tmp_path: Path) -> None:
    test_all = tmp_path / "test_all_libraries.mojo"
    test_all.write_text(
        "\n".join(
            [
                "from std.math import is_finite",
                "from finance import npv",
                "from crypto.hash import digest",
            ]
        ),
        encoding="utf-8",
    )

    modules = mojo_inventory.parse_test_all_import_modules(test_all)

    assert modules == ("crypto.hash", "finance")


def test_build_inventory_report_flags_artifact_only_modules(tmp_path: Path) -> None:
    engine_root = tmp_path / "mojo" / "engine"
    test_all = tmp_path / "mojo" / "tests" / "test_all_libraries.mojo"
    benchmark_results = tmp_path / "benchmarks" / "results"
    benchmark_benches = tmp_path / "benchmarks" / "mojo_benchmarks"

    _write(engine_root / "finance.mojo", "fn npv() -> Float64:\n    return 1.0\n")
    _write(engine_root / "crypto" / "hash.mojo", "fn digest() -> Int:\n    return 1\n")
    _write(
        test_all,
        "\n".join(
            [
                "from finance import npv",
                "from accounting import gross_margin",
                "from crypto.hash import digest",
            ]
        ),
    )
    _write(benchmark_results / "finance.json", "{}")
    _write(benchmark_results / "accounting.json", "{}")
    _write(benchmark_benches / "bench_finance.mojo", "from finance import npv\n")
    _write(benchmark_benches / "bench_accounting.mojo", "from accounting import gross_margin\n")

    report = mojo_inventory.build_inventory_report(
        engine_root=engine_root,
        test_all_path=test_all,
        benchmark_results_dir=benchmark_results,
        benchmark_mojo_dir=benchmark_benches,
        threshold_target=3,
    )

    assert report.source_module_count == 2
    assert report.source_modules_with_public_functions_count == 2
    assert report.source_public_function_count == 2
    assert report.test_all_missing_from_source == ("accounting",)
    assert report.benchmark_results_missing_from_source == ("accounting",)
    assert report.benchmark_benches_missing_from_source == ("accounting",)
    assert report.threshold_met is False
    assert report.threshold_gap == 1


def test_runtime_library_manifest_cache_reuses_cached_inventory(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine_root = tmp_path / "mojo" / "engine"
    cache_path = tmp_path / ".cache" / "runtime_library_inventory.json"
    _write(
        engine_root / "finance.mojo",
        "fn npv(rate: Float64) -> Float64:\n    return rate\n",
    )

    first = mojo_inventory.discover_runtime_library_modules(
        engine_root=engine_root,
        executable_only=True,
        cache_path=cache_path,
    )

    assert first[0].import_path == "finance"
    assert cache_path.exists()

    def _unexpected_parse(_: Path) -> tuple[mojo_inventory.RuntimeFunctionSpec, ...]:
        raise AssertionError("runtime inventory should load from manifest cache")

    monkeypatch.setattr(mojo_inventory, "_parse_runtime_function_specs", _unexpected_parse)

    second = mojo_inventory.discover_runtime_library_modules(
        engine_root=engine_root,
        executable_only=True,
        cache_path=cache_path,
    )

    assert second == first


def test_runtime_library_manifest_cache_invalidates_when_source_changes(tmp_path: Path) -> None:
    engine_root = tmp_path / "mojo" / "engine"
    cache_path = tmp_path / ".cache" / "runtime_library_inventory.json"
    finance_module = engine_root / "finance.mojo"
    _write(
        finance_module,
        "fn npv(rate: Float64) -> Float64:\n    return rate\n",
    )

    first = mojo_inventory.discover_runtime_library_modules(
        engine_root=engine_root,
        executable_only=True,
        cache_path=cache_path,
    )

    time.sleep(0.01)
    _write(
        finance_module,
        (
            "fn npv(rate: Float64) -> Float64:\n    return rate\n\n"
            "fn irr(rate: Float64) -> Float64:\n    return rate\n"
        ),
    )

    refreshed = mojo_inventory.discover_runtime_library_modules(
        engine_root=engine_root,
        executable_only=True,
        cache_path=cache_path,
    )

    assert first[0].functions == (
        mojo_inventory.RuntimeFunctionSpec(
            name="npv",
            params=(
                mojo_inventory.RuntimeParamSpec(
                    name="rate",
                    typ="Float64",
                    has_default=False,
                    is_mut=False,
                ),
            ),
            return_type="Float64",
        ),
    )
    assert tuple(spec.name for spec in refreshed[0].functions) == ("npv", "irr")


def test_current_repo_inventory_report_detects_stale_artifact_gap() -> None:
    report = mojo_inventory.build_inventory_report()
    executable_modules = mojo_inventory.discover_runtime_library_modules(executable_only=True)

    assert report.source_module_count > 0
    assert report.source_modules_with_public_functions_count > 0
    assert report.source_public_function_count > 0
    assert report.test_all_missing_from_source == ()
    assert report.threshold_met is True
    assert len(executable_modules) >= 400


def test_llm_rollout_modules_are_runtime_executable() -> None:
    modules = {
        module.import_path: tuple(spec.name for spec in module.functions)
        for module in mojo_inventory.discover_runtime_library_modules(executable_only=True)
    }

    assert modules["text.tokenizer"] == (
        "is_stopword",
        "word_tokenize",
        "sentence_tokenize",
        "char_ngrams",
        "word_ngrams",
        "remove_stopwords",
        "stem_simple",
        "vocabulary_size",
        "token_frequency",
        "pad_sequence",
    )
    assert modules["vector_kernels.ranker"] == ("run_column_rank_v2",)
    assert modules["vector_kernels.table"] == (
        "build_query",
        "source_id_of",
        "role_id_of",
        "build_table_json",
    )
    assert modules["column_rank"] == ("run_column_rank",)
    assert modules["crypto.base64"] == (
        "b64_encode",
        "b64_decode",
        "b64_url_encode",
        "b64_url_decode",
    )
    assert modules["crypto.uuid"] == ("uuid4", "uuid4_hex")
    assert modules["json.writer"] == (
        "json_escape_string",
        "json_object_start",
        "json_object_end",
        "json_add_string",
        "json_add_int",
        "json_add_float",
        "json_add_bool",
        "json_add_null",
        "json_add_array_float",
        "json_add_array_string",
        "json_add_raw",
        "json_build_object",
    )
    assert modules["runtime_library_dispatch_generated"] == ("dispatch_runtime_library",)
    assert modules["rerank_eval"] == (
        "precision_at_k",
        "recall_at_k",
        "hit_rate_at_k",
        "mrr_at_k",
        "map_at_k",
        "ndcg_at_k",
        "pairwise_margin_accuracy",
        "score_separation",
        "latency_weighted_quality",
    )
    assert modules["inference_cost_latency"] == (
        "prompt_token_estimate",
        "completion_token_estimate",
        "kv_cache_bytes",
        "attention_flops",
        "prefill_latency_estimate",
        "decode_latency_estimate",
        "request_cost_estimate",
        "cost_latency_frontier_score",
        "batch_efficiency_estimate",
        "queue_delay_estimate",
        "speculative_decode_gain_estimate",
    )


def test_runtime_executable_function_supports_struct_transport(tmp_path: Path) -> None:
    module_path = tmp_path / "cache.mojo"
    _write(
        module_path,
        "\n".join(
            [
                "struct CacheEntry(Copyable, Movable):",
                "    var key: Int",
                "    var value: Float64",
                "",
                "struct Cache(Copyable, Movable):",
                "    var entries: List[CacheEntry]",
                "    var hits: Int",
                "",
                "fn cache_put(mut cache: Cache, key: Int, value: Float64) -> Cache:",
                "    return cache",
            ]
        ),
    )
    functions = mojo_inventory._parse_runtime_function_specs(module_path)
    struct_specs = mojo_inventory.parse_runtime_struct_specs(module_path)

    assert len(functions) == 1
    assert mojo_inventory.is_runtime_executable_function(
        functions[0],
        import_path="cache",
        struct_specs=struct_specs,
    )


def test_current_repo_non_executable_benchmark_gap_does_not_regress() -> None:
    report = mojo_inventory.build_inventory_report()
    runtime_all = {
        module.lib_id: module
        for module in mojo_inventory.discover_runtime_library_modules(executable_only=False)
    }
    runtime_exec_ids = {
        module.lib_id for module in mojo_inventory.discover_runtime_library_modules(executable_only=True)
    }

    benchmark_ids = set(report.artifact_benchmark_result_libs) | set(report.artifact_benchmark_bench_libs)
    non_executable_gap = sorted(
        lib_id
        for lib_id in benchmark_ids
        if lib_id not in runtime_exec_ids and lib_id in runtime_all
    )

    assert len(non_executable_gap) <= 19
