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

    assert "_dispatch_text__tokenizer" in committed
    assert "_dispatch_vector_kernels__ranker" in committed
    assert "_dispatch_vector_kernels__table" in committed
    assert "_dispatch_rerank_eval" in committed
    assert "_dispatch_inference_cost_latency" in committed
    assert 'if module_name == "text.tokenizer":' in committed
    assert 'if module_name == "vector_kernels.ranker":' in committed
    assert 'if module_name == "vector_kernels.table":' in committed
    assert 'if function_name == "build_query":' in committed
    assert 'if function_name == "build_table_json":' in committed
    assert "_to_json_rankrequest_vector_kernels_table" in committed
    assert "_to_json_vec64_vector_kernels_table(value.query_vec)" in committed
    assert "_to_json_list_candidateentry_vector_kernels_table(value.entries)" in committed


def test_runtime_library_dispatch_can_render_filtered_module_subset() -> None:
    modules = discover_runtime_library_modules(executable_only=True)
    selected = tuple(
        module
        for module in modules
        if module.import_path in {"image_ops", "vector_kernels.table", "vision_gate"}
    )

    rendered = render_dispatch_source(selected)

    assert "_dispatch_image_ops" in rendered
    assert "_dispatch_vector_kernels__table" in rendered
    assert "_dispatch_vision_gate" in rendered
    assert "_dispatch_elevator" not in rendered
    assert "fn _to_json_uint32(value: UInt32) -> String:" in rendered
