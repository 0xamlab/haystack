from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta = importlib.import_module("algenta")
algenta_mojo = importlib.import_module("algenta.mojo")
algenta_mojo_runtime = importlib.import_module("algenta.mojo_runtime")
libraries = algenta.libraries
LibraryCatalog = algenta_mojo_runtime.LibraryCatalog
MojoExecutionError = algenta_mojo.MojoExecutionError
MojoFunctionNotRegisteredError = algenta_mojo.MojoFunctionNotRegisteredError
MojoModuleNotRegisteredError = algenta_mojo.MojoModuleNotRegisteredError
MojoRuntimeConfigurationError = algenta_mojo.MojoRuntimeConfigurationError
MojoRuntime = algenta_mojo_runtime.MojoRuntime


def _clear_runtime_descriptor_cache() -> None:
    algenta_mojo_runtime._cached_runtime_descriptors.cache_clear()


@pytest.fixture(autouse=True)
def _reset_runtime_descriptor_cache() -> None:
    _clear_runtime_descriptor_cache()
    yield
    _clear_runtime_descriptor_cache()


class _FakeRuntimeSDK:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls: list[tuple[str, str, object]] = []

    def execute(self, module: str, function: str, args: object = None) -> dict[str, object]:
        self.calls.append((module, function, args))
        return {"success": True, "result": {"module": module, "function": function, "args": args}}

    def health(self) -> dict[str, object]:
        return {"status": "ok"}


class _FakeFunction:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeModule:
    def __init__(self, import_path: str, function_names: list[str]) -> None:
        self.import_path = import_path
        self.functions = tuple(_FakeFunction(name) for name in function_names)


def test_mojo_runtime_list_modules_uses_runtime_inventory(monkeypatch) -> None:
    _clear_runtime_descriptor_cache()
    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FakeRuntimeSDK)
    monkeypatch.setattr(
        algenta_mojo_runtime,
        "_load_runtime_inventory",
        lambda: (
            lambda: (
                _FakeModule("ab_testing", ["sample_size_proportion"]),
                _FakeModule("vector_search", ["recall_at_k", "ann_distance_bound"]),
            )
        ),
    )

    runtime = MojoRuntime(mode="local")
    modules = runtime.list_modules()

    assert modules == [
        {"name": "ab_testing", "engine": "mojo", "functions": ["sample_size_proportion"]},
        {
            "name": "vector_search",
            "engine": "mojo",
            "functions": ["ann_distance_bound", "recall_at_k"],
        },
    ]
    assert runtime.list_functions("vector_search") == ("ann_distance_bound", "recall_at_k")


def test_libraries_catalog_lists_functions_and_dispatches_calls(monkeypatch) -> None:
    _clear_runtime_descriptor_cache()
    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FakeRuntimeSDK)
    monkeypatch.setattr(
        algenta_mojo_runtime,
        "_load_runtime_inventory",
        lambda: lambda: (_FakeModule("ab_testing", ["sample_size_proportion"]),),
    )

    catalog = libraries(mode="local")

    assert isinstance(catalog, LibraryCatalog)
    assert tuple(descriptor.name for descriptor in catalog.list_modules()) == ("ab_testing",)
    assert catalog.list_functions("ab_testing") == ("sample_size_proportion",)
    assert "ab_testing" in catalog
    assert catalog.module("ab_testing") is catalog["ab_testing"] is catalog.ab_testing
    assert catalog.ab_testing.sample_size_proportion is catalog.ab_testing.sample_size_proportion

    result = catalog.ab_testing.sample_size_proportion(
        p1=0.10,
        p2=0.12,
        alpha=0.05,
        power=0.8,
    )

    assert result == {
        "module": "ab_testing",
        "function": "sample_size_proportion",
        "args": {"p1": 0.10, "p2": 0.12, "alpha": 0.05, "power": 0.8},
    }


def test_libraries_catalog_keeps_rollout_modules_on_canonical_names_and_alias_dispatch(
    monkeypatch,
) -> None:
    _clear_runtime_descriptor_cache()
    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FakeRuntimeSDK)
    monkeypatch.setattr(
        algenta_mojo_runtime,
        "_load_runtime_inventory",
        lambda: (
            lambda: (
                _FakeModule("bpe_tokenizer", ["bpe_merge_score"]),
                _FakeModule("text.tokenizer", ["word_tokenize", "pad_sequence"]),
                _FakeModule("embeddings", ["cosine_similarity"]),
                _FakeModule("flash_attention", ["flash_block_output"]),
                _FakeModule("sparse_attention", ["block_sparse_mask_density"]),
                _FakeModule(
                    "transformer_attention",
                    ["scaled_dot_product_attention"],
                ),
                _FakeModule("transformer_blocks", ["feedforward_layer1"]),
                _FakeModule("llm_sampling", ["top_k_threshold"]),
                _FakeModule("vector_similarity", ["cosine_similarity"]),
                _FakeModule("vector_search", ["recall_at_k"]),
                _FakeModule("vector_kernels.ranker", ["run_column_rank_v2"]),
                _FakeModule(
                    "vector_kernels.table",
                    ["build_query", "source_id_of", "role_id_of", "build_table_json"],
                ),
                _FakeModule("sparse_vector", ["nnz_ratio"]),
                _FakeModule("rlhf_dpo", ["dpo_reward_margin"]),
                _FakeModule("rerank_eval", ["precision_at_k", "hit_rate_at_k"]),
                _FakeModule(
                    "inference_cost_latency",
                    ["prompt_token_estimate", "queue_delay_estimate"],
                ),
                _FakeModule(
                    "kv_cache",
                    ["kv_cache_total_memory", "kv_cache_utilization"],
                ),
                _FakeModule(
                    "paged_kv_cache",
                    ["page_table_lookup", "context_extension_factor"],
                ),
                _FakeModule(
                    "continuous_batching",
                    ["iteration_level_batch_size", "batching_efficiency"],
                ),
                _FakeModule(
                    "inference_engine",
                    ["kv_cache_hit_ratio", "decode_time_per_token"],
                ),
                _FakeModule(
                    "speculative_decoding",
                    ["speculative_accept_prob", "draft_model_speedup"],
                ),
                _FakeModule(
                    "generation_loop",
                    ["top_k_accept", "typical_sampling_accept"],
                ),
            )
        ),
    )

    catalog = libraries(mode="local")
    rollout_modules = (
        "bpe_tokenizer",
        "text.tokenizer",
        "embeddings",
        "flash_attention",
        "sparse_attention",
        "transformer_attention",
        "transformer_blocks",
        "llm_sampling",
        "vector_similarity",
        "vector_search",
        "vector_kernels.ranker",
        "vector_kernels.table",
        "sparse_vector",
        "rlhf_dpo",
        "rerank_eval",
        "inference_cost_latency",
        "kv_cache",
        "paged_kv_cache",
        "continuous_batching",
        "inference_engine",
        "speculative_decoding",
        "generation_loop",
    )

    assert catalog.names() == tuple(sorted(rollout_modules))
    assert tuple(descriptor.name for descriptor in catalog.list_modules()) == tuple(
        sorted(rollout_modules)
    )
    assert catalog.list_functions("text.tokenizer") == ("pad_sequence", "word_tokenize")
    assert catalog.list_functions("vector_kernels.ranker") == ("run_column_rank_v2",)
    assert catalog.list_functions("vector_kernels.table") == (
        "build_query",
        "build_table_json",
        "role_id_of",
        "source_id_of",
    )
    assert catalog.list_functions("rerank_eval") == ("hit_rate_at_k", "precision_at_k")
    assert catalog.list_functions("inference_cost_latency") == (
        "prompt_token_estimate",
        "queue_delay_estimate",
    )
    assert catalog.list_functions("kv_cache") == (
        "kv_cache_total_memory",
        "kv_cache_utilization",
    )
    assert catalog.list_functions("generation_loop") == (
        "top_k_accept",
        "typical_sampling_accept",
    )

    assert catalog.module("text.tokenizer") is catalog["text.tokenizer"] is catalog.text_tokenizer
    assert (
        catalog.module("vector_kernels.ranker")
        is catalog["vector_kernels.ranker"]
        is catalog.vector_kernels_ranker
    )
    assert (
        catalog.module("vector_kernels.table")
        is catalog["vector_kernels.table"]
        is catalog.vector_kernels_table
    )

    text_result = catalog.text_tokenizer.word_tokenize("alpha beta")
    ranker_result = catalog.vector_kernels_ranker.run_column_rank_v2(
        {"query": {"name": "unit_price"}}
    )
    table_result = catalog.vector_kernels_table.build_query("unit_price", 1, 1, 2)
    rerank_result = catalog.rerank_eval.precision_at_k(relevance=[1, 0, 1], k=3)
    cost_result = catalog.inference_cost_latency.prompt_token_estimate(
        char_count=120,
        chars_per_token=4.0,
    )
    kv_cache_result = catalog.kv_cache.kv_cache_total_memory(4096.0, 32.0)
    generation_result = catalog.generation_loop.top_k_accept(rank=1.0, k=10.0)

    assert text_result == {
        "module": "text.tokenizer",
        "function": "word_tokenize",
        "args": "alpha beta",
    }
    assert ranker_result == {
        "module": "vector_kernels.ranker",
        "function": "run_column_rank_v2",
        "args": {"query": {"name": "unit_price"}},
    }
    assert table_result == {
        "module": "vector_kernels.table",
        "function": "build_query",
        "args": ["unit_price", 1, 1, 2],
    }
    assert rerank_result == {
        "module": "rerank_eval",
        "function": "precision_at_k",
        "args": {"relevance": [1, 0, 1], "k": 3},
    }
    assert cost_result == {
        "module": "inference_cost_latency",
        "function": "prompt_token_estimate",
        "args": {"char_count": 120, "chars_per_token": 4.0},
    }
    assert kv_cache_result == {
        "module": "kv_cache",
        "function": "kv_cache_total_memory",
        "args": [4096.0, 32.0],
    }
    assert generation_result == {
        "module": "generation_loop",
        "function": "top_k_accept",
        "args": {"rank": 1.0, "k": 10.0},
    }

    assert catalog._runtime._runtime.calls == [
        ("text.tokenizer", "word_tokenize", "alpha beta"),
        ("vector_kernels.ranker", "run_column_rank_v2", {"query": {"name": "unit_price"}}),
        ("vector_kernels.table", "build_query", ["unit_price", 1, 1, 2]),
        ("rerank_eval", "precision_at_k", {"relevance": [1, 0, 1], "k": 3}),
        (
            "inference_cost_latency",
            "prompt_token_estimate",
            {"char_count": 120, "chars_per_token": 4.0},
        ),
        ("kv_cache", "kv_cache_total_memory", [4096.0, 32.0]),
        ("generation_loop", "top_k_accept", {"rank": 1.0, "k": 10.0}),
    ]


def test_mojo_runtime_reuses_cached_inventory_until_refresh(monkeypatch) -> None:
    _clear_runtime_descriptor_cache()
    calls = {"inventory": 0}

    def _inventory_loader():
        calls["inventory"] += 1
        return (
            _FakeModule("ab_testing", ["sample_size_proportion"]),
            _FakeModule("vector_search", ["recall_at_k"]),
        )

    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FakeRuntimeSDK)
    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_inventory", lambda: _inventory_loader)

    runtime = MojoRuntime(mode="local")

    first_modules = runtime.list_modules()
    second_modules = runtime.list_modules()
    runtime.libraries().refresh()
    refreshed_modules = runtime.list_modules()

    assert first_modules == second_modules == refreshed_modules
    assert calls["inventory"] == 2


def test_public_libraries_surface_exposes_real_executable_inventory_gate() -> None:
    _clear_runtime_descriptor_cache()
    catalog = libraries(mode="local", auto_start_daemon=False)
    modules = catalog.list_modules()

    assert len(modules) >= 400
    first_module = modules[0]
    assert first_module.functions
    assert catalog.list_functions(first_module.name) == first_module.functions


def test_mojo_runtime_rejects_non_local_modes_but_accepts_local_entitlement_config(
    monkeypatch,
) -> None:
    _clear_runtime_descriptor_cache()
    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FakeRuntimeSDK)
    monkeypatch.setattr(
        algenta_mojo_runtime,
        "_load_runtime_inventory",
        lambda: lambda: (_FakeModule("ab_testing", ["sample_size_proportion"]),),
    )

    with pytest.raises(MojoRuntimeConfigurationError) as invalid_mode:
        libraries(mode="api")
    assert invalid_mode.value.code == "compute_runtime_unavailable"

    runtime = MojoRuntime(
        mode="local",
        api_key="de_live_test",
        base_url="http://localhost:8000",
    )
    assert runtime.health() == {"status": "ok"}
    assert runtime._runtime.kwargs["api_key"] == "de_live_test"
    assert runtime._runtime.kwargs["base_url"] == "http://localhost:8000"

    catalog = libraries(
        mode="local",
        api_key="de_live_test",
        base_url="http://localhost:8000",
    )
    assert catalog.list_functions("ab_testing") == ("sample_size_proportion",)


def test_mojo_catalog_missing_module_and_function_raise_structured_errors(monkeypatch) -> None:
    _clear_runtime_descriptor_cache()
    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FakeRuntimeSDK)
    monkeypatch.setattr(
        algenta_mojo_runtime,
        "_load_runtime_inventory",
        lambda: lambda: (_FakeModule("ab_testing", ["sample_size_proportion"]),),
    )

    catalog = libraries(mode="local")

    with pytest.raises(MojoModuleNotRegisteredError) as missing_module:
        catalog["does_not_exist"]
    assert missing_module.value.code == "module_not_registered"

    with pytest.raises(MojoFunctionNotRegisteredError) as missing_function:
        _ = catalog.ab_testing.not_a_function
    assert missing_function.value.code == "function_not_registered"


def test_mojo_runtime_execution_failure_maps_to_fail_closed_codes(monkeypatch) -> None:
    _clear_runtime_descriptor_cache()

    class _FailingRuntimeSDK(_FakeRuntimeSDK):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._result = kwargs.pop("result", None)

        def execute(self, module: str, function: str, args: object = None) -> dict[str, object]:
            return self._result or {
                "success": False,
                "error": "local runtime unavailable",
                "engine_used": "none",
            }

    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FailingRuntimeSDK)
    monkeypatch.setattr(
        algenta_mojo_runtime,
        "_load_runtime_inventory",
        lambda: lambda: (_FakeModule("ab_testing", ["sample_size_proportion"]),),
    )

    runtime = MojoRuntime(mode="local")
    catalog = runtime.libraries()

    with pytest.raises(MojoExecutionError) as unavailable:
        catalog.ab_testing.sample_size_proportion({"p1": 0.10, "p2": 0.12})
    assert unavailable.value.code == "compute_runtime_unavailable"

    class _PythonFallbackRuntimeSDK(_FakeRuntimeSDK):
        def execute(self, module: str, function: str, args: object = None) -> dict[str, object]:
            return {
                "success": False,
                "error": "python fallback is disabled",
                "engine_used": "python-fallback",
            }

    _clear_runtime_descriptor_cache()
    monkeypatch.setattr(
        algenta_mojo_runtime, "_load_runtime_class", lambda: _PythonFallbackRuntimeSDK
    )
    fallback_catalog = libraries(mode="local")

    with pytest.raises(MojoExecutionError) as fallback_error:
        fallback_catalog.ab_testing.sample_size_proportion({"p1": 0.10, "p2": 0.12})
    assert fallback_error.value.code == "python_fallback_disabled"


def test_mojo_runtime_inventory_rejects_duplicate_modules(monkeypatch) -> None:
    _clear_runtime_descriptor_cache()
    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FakeRuntimeSDK)
    monkeypatch.setattr(
        algenta_mojo_runtime,
        "_load_runtime_inventory",
        lambda: (
            lambda: (
                _FakeModule("ab_testing", ["sample_size_proportion"]),
                _FakeModule("ab_testing", ["power"]),
            )
        ),
    )

    with pytest.raises(MojoRuntimeConfigurationError) as duplicate_error:
        libraries(mode="local")

    assert duplicate_error.value.code == "compute_runtime_unavailable"


def test_mojo_runtime_inventory_rejects_malformed_function_descriptors(monkeypatch) -> None:
    _clear_runtime_descriptor_cache()
    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FakeRuntimeSDK)

    class _MalformedModule:
        import_path = "ab_testing"
        engine = "mojo"
        functions = (_FakeFunction(""),)

    monkeypatch.setattr(
        algenta_mojo_runtime,
        "_load_runtime_inventory",
        lambda: lambda: (_MalformedModule(),),
    )

    with pytest.raises(MojoRuntimeConfigurationError) as malformed_error:
        libraries(mode="local")

    assert malformed_error.value.code == "compute_runtime_unavailable"


def test_mojo_runtime_inventory_tolerates_public_attribute_alias_collisions(monkeypatch) -> None:
    """Modules with dotted paths whose flat alias collides with another module
    are still listed in the catalog; only the first-seen alias is exposed via
    attribute access.
    """
    _clear_runtime_descriptor_cache()
    monkeypatch.setattr(algenta_mojo_runtime, "_load_runtime_class", lambda: _FakeRuntimeSDK)
    monkeypatch.setattr(
        algenta_mojo_runtime,
        "_load_runtime_inventory",
        lambda: (
            lambda: (
                _FakeModule("ab.testing", ["sample_size_proportion"]),
                _FakeModule("ab_testing", ["power"]),
            )
        ),
    )

    catalog = libraries(mode="local", auto_start_daemon=False)
    module_names = {module.name for module in catalog.list_modules()}
    assert "ab.testing" in module_names
    assert "ab_testing" in module_names
