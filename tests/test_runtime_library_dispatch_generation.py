from __future__ import annotations

from apps.runtime.mojo_inventory import discover_runtime_library_modules
from scripts.generate_runtime_library_dispatch import TARGET, render_dispatch_source


def test_generated_runtime_library_dispatch_is_in_sync() -> None:
    modules = discover_runtime_library_modules(executable_only=True)
    rendered = render_dispatch_source(modules)
    committed = TARGET.read_text(encoding="utf-8")

    assert committed == rendered
    assert "fn dispatch_runtime_library(raw: String) raises -> String:" in committed
    assert "_dispatch_elevator" in committed
    assert "annual_energy_consumption" in committed


def test_runtime_library_dispatch_excludes_internal_vector_kernel_helpers() -> None:
    import_paths = {
        module.import_path for module in discover_runtime_library_modules(executable_only=True)
    }

    assert "vector_kernels.prefilter" not in import_paths
    assert "vector_kernels.semantic_micro.semantic_expand" not in import_paths
    assert "vector_kernels.semantic_micro.semantic_loader" not in import_paths


def test_runtime_library_dispatch_contains_llm_rollout_handlers() -> None:
    committed = TARGET.read_text(encoding="utf-8")

    assert "_dispatch_text_tokenizer" in committed
    assert "_dispatch_vector_kernels_ranker" in committed
    assert "_dispatch_vector_kernels_table" in committed
    assert "_dispatch_rerank_eval" in committed
    assert "_dispatch_inference_cost_latency" in committed
    assert 'if function_name == "build_query":' in committed
    assert 'if function_name == "build_table_json":' in committed
    assert '\\"query_vec\\":{\\"data\\":' in committed
    assert '\\"entries\\":[' in committed
