from __future__ import annotations

from tests.benchmark_mojo_vs_python import (
    get_all_libs,
    get_benchmark_inventory_breakdown,
    get_shipping_runtime_contract_counts,
)
from tests.llm_rollout_matrix import LLM_ROLLOUT_FUNCTIONS_BY_MODULE


def test_benchmark_inventory_breakdown_matches_dynamic_library_scan() -> None:
    libs = get_all_libs()
    breakdown = get_benchmark_inventory_breakdown(libs)

    assert breakdown["kind"] == "benchmark_discovery_inventory"
    assert breakdown["total_libraries"] == len(libs)
    assert (
        breakdown["top_level_library_count"] + breakdown["nested_library_count"]
        == breakdown["total_libraries"]
    )
    assert breakdown["group_counts"]["top_level"] == breakdown["top_level_library_count"]
    assert sum(breakdown["group_counts"].values()) == breakdown["total_libraries"]


def test_shipping_runtime_contract_counts_match_rollout_matrix() -> None:
    counts = get_shipping_runtime_contract_counts()

    assert counts == {
        "kind": "shipping_runtime_contract",
        "module_count": len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE),
        "function_count": sum(
            len(functions) for functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.values()
        ),
    }
