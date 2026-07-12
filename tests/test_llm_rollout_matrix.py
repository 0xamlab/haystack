from __future__ import annotations

import json
from pathlib import Path

from tests.llm_rollout_matrix import (
    LLM_ROLLOUT_CASES_JSON,
    LLM_ROLLOUT_FUNCTION_CASES,
    LLM_ROLLOUT_FUNCTIONS_BY_MODULE,
    LLM_ROLLOUT_MODULE_NAMES,
)


def test_llm_rollout_matrix_covers_all_target_modules() -> None:
    assert LLM_ROLLOUT_MODULE_NAMES == (
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


def test_llm_rollout_matrix_contains_every_benchmarked_function() -> None:
    assert len(LLM_ROLLOUT_FUNCTION_CASES) == 209
    assert len(LLM_ROLLOUT_CASES_JSON) == 209
    assert len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE["vector_kernels.ranker"]) == 1
    assert len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE["vector_kernels.table"]) == 4
    assert "precision_at_k" in LLM_ROLLOUT_FUNCTIONS_BY_MODULE["rerank_eval"]
    assert "prompt_token_estimate" in LLM_ROLLOUT_FUNCTIONS_BY_MODULE["inference_cost_latency"]
    assert len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE["kv_cache"]) == 10
    assert len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE["paged_kv_cache"]) == 10
    assert len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE["continuous_batching"]) == 10
    assert len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE["inference_engine"]) == 10
    assert len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE["speculative_decoding"]) == 10
    assert len(LLM_ROLLOUT_FUNCTIONS_BY_MODULE["generation_loop"]) == 10


def test_llm_rollout_benchmark_artifacts_match_public_runtime_surface() -> None:
    root = Path(__file__).resolve().parents[1]
    benchmarks_dir = root / "benchmarks" / "results"
    name_map = {
        "text.tokenizer": "text_tokenizer",
        "vector_kernels.ranker": "vector_kernels_ranker",
        "vector_kernels.table": "vector_kernels_table",
    }

    for module_name, expected_functions in LLM_ROLLOUT_FUNCTIONS_BY_MODULE.items():
        benchmark_name = name_map.get(module_name, module_name)
        payload = json.loads((benchmarks_dir / f"{benchmark_name}.json").read_text())
        actual_functions = {item["function"] for item in payload["functions"]}

        assert actual_functions == set(expected_functions)
        assert payload["n_compared"] == len(expected_functions)


def test_llm_rollout_proof_bundle_artifact_matches_rollout_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "build" / "llm_rollout_proof_bundle.json").read_text())

    assert payload["bundle"] == "llm_rollout_proof_bundle"
    assert payload["expected_modules"] == len(LLM_ROLLOUT_MODULE_NAMES)
    assert payload["expected_functions"] == len(LLM_ROLLOUT_FUNCTION_CASES)
    assert payload["public_supported_channels"] == [
        "python_sdk",
        "typescript_sdk",
        "cli",
        "mcp",
    ]
    assert payload["underlying_validated_lanes"] == [
        "bundled_worker",
        "runtime_local",
    ]
    assert payload["public_http_library_routes_supported"] is True
    assert payload["public_http_library_routes_feature_flag_ready"] is True
    assert payload["public_http_library_routes_enable_env"] == (
        "ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED"
    )

    parity = payload["parity_artifact"]
    assert parity["path"] == "build/llm_rollout_parity_benchmark.json"
    assert parity["library_count"] == len(LLM_ROLLOUT_MODULE_NAMES)
    assert parity["function_count"] == len(LLM_ROLLOUT_FUNCTION_CASES)
    assert parity["median_speedup_x"] > 0
    assert parity["mean_speedup_x"] > 0
    assert parity["max_speedup_x"] > 0
    assert isinstance(parity["timestamp"], str) and parity["timestamp"]

    compiled = payload["compiled_runtime_artifact"]
    assert compiled["path"] == "build/llm_compiled_runtime_benchmark.json"
    assert compiled["module_count"] == len(LLM_ROLLOUT_MODULE_NAMES)
    assert compiled["function_count"] == len(LLM_ROLLOUT_FUNCTION_CASES)
    assert compiled["failed_function_count"] == 0
    assert compiled["transport"] == "compiled_worker"
    for key in ("max_cold_ms", "max_warm_ms", "max_hot_ms"):
        entry = compiled[key]
        assert entry["value"] > 0
        assert isinstance(entry["module"], str) and entry["module"]
        assert isinstance(entry["function"], str) and entry["function"]

    sdk_contract_suites = payload["sdk_contract_suites"]
    assert [item["name"] for item in sdk_contract_suites] == [
        "python_sdk_package_contract",
        "typescript_sdk_package_contract",
    ]
    assert [item["status"] for item in sdk_contract_suites] == ["passed", "passed"]
    assert [item["channels"] for item in sdk_contract_suites] == [
        ["python_sdk"],
        ["typescript_sdk"],
    ]
    assert sdk_contract_suites[0]["minimum_passed"] == 1
    assert sdk_contract_suites[1]["minimum_passed"] == 1
    assert sdk_contract_suites[0]["passed"] == 1
    assert sdk_contract_suites[1]["passed"] == 1
    assert sdk_contract_suites[0]["failed"] == 0
    assert sdk_contract_suites[1]["failed"] == 0
    assert sdk_contract_suites[0]["skipped"] == 0
    assert sdk_contract_suites[1]["skipped"] == 8
    assert "tests/test_algenta_mojo_sdk.py" in sdk_contract_suites[0]["evidence_paths"]
    assert (
        "packages/ts-sdk/src/libraries.test.ts"
        in sdk_contract_suites[1]["evidence_paths"]
    )
    assert sdk_contract_suites[0]["command"][1:] == [
        "-m",
        "pytest",
        "-q",
        "tests/test_algenta_mojo_sdk.py",
        "-k",
        "keeps_rollout_modules_on_canonical_names_and_alias_dispatch",
    ]
    assert sdk_contract_suites[1]["command"] == [
        "pnpm",
        "--dir",
        "packages/ts-sdk",
        "exec",
        "vitest",
        "run",
        "src/libraries.test.ts",
        "-t",
        "keeps the 22-library rollout inventory on canonical module names and alias dispatch",
    ]

    http_flag_contract_suites = payload["http_flag_contract_suites"]
    assert [item["name"] for item in http_flag_contract_suites] == [
        "public_http_library_routes_feature_flag"
    ]
    assert [item["status"] for item in http_flag_contract_suites] == ["passed"]
    assert http_flag_contract_suites[0]["minimum_passed"] == 2
    assert http_flag_contract_suites[0]["passed"] == 2
    assert http_flag_contract_suites[0]["failed"] == 0
    assert http_flag_contract_suites[0]["skipped"] == 0
    assert "tests/test_runtime_libraries_api.py" in http_flag_contract_suites[0]["evidence_paths"]
    assert "apps/api_server/main.py" in http_flag_contract_suites[0]["evidence_paths"]
    assert "apps/api_server/config.py" in http_flag_contract_suites[0]["evidence_paths"]
    assert http_flag_contract_suites[0]["command"][1:] == [
        "-m",
        "pytest",
        "-q",
        "tests/test_runtime_libraries_api.py",
    ]

    http_flag_live_suites = payload["http_flag_live_suites"]
    assert [item["name"] for item in http_flag_live_suites] == [
        "public_http_library_routes_feature_flag_live"
    ]
    assert [item["status"] for item in http_flag_live_suites] == ["passed"]
    assert http_flag_live_suites[0]["minimum_passed"] == 4
    assert http_flag_live_suites[0]["passed"] == 4
    assert http_flag_live_suites[0]["failed"] == 0
    assert http_flag_live_suites[0]["skipped"] == 0
    assert http_flag_live_suites[0]["channels"] == ["http_api_feature_flag"]
    assert (
        "tests/integration/test_runtime_libraries_http_live.py"
        in http_flag_live_suites[0]["evidence_paths"]
    )
    assert "tests/_asgi_client.py" in http_flag_live_suites[0]["evidence_paths"]
    assert "apps/api_server/main.py" in http_flag_live_suites[0]["evidence_paths"]
    assert "apps/api_server/config.py" in http_flag_live_suites[0]["evidence_paths"]
    assert http_flag_live_suites[0]["script"] == "tests/integration/test_runtime_libraries_http_live.py"

    serving_extension_subset = payload["serving_extension_subset"]
    assert serving_extension_subset["module_count"] == 6
    assert serving_extension_subset["function_count"] == 60
    assert serving_extension_subset["functions_compared"] == 60
    assert serving_extension_subset["all_modules_fully_compared"] is True
    assert serving_extension_subset["all_compiled_engine_used_mojo"] is True
    assert serving_extension_subset["min_speedup_x"] > 0
    assert serving_extension_subset["max_speedup_x"] >= serving_extension_subset["min_speedup_x"]
    assert serving_extension_subset["max_cold_ms"]["value"] > 0
    assert serving_extension_subset["max_warm_ms"]["value"] > 0
    assert serving_extension_subset["max_hot_ms"]["value"] > 0
    subset_by_name = {item["name"]: item for item in serving_extension_subset["modules"]}
    assert set(subset_by_name) == {
        "kv_cache",
        "paged_kv_cache",
        "continuous_batching",
        "inference_engine",
        "speculative_decoding",
        "generation_loop",
    }
    for item in subset_by_name.values():
        assert item["parity_function_count"] == 10
        assert item["parity_compared_count"] == 10
        assert item["compiled_function_count"] == 10
        assert item["compiled_all_engine_used_mojo"] is True
        assert item["parity_speedup_x"] > 0

    serving_extension_channel_coverage = payload["serving_extension_channel_coverage"]
    assert serving_extension_channel_coverage["module_count"] == 6
    assert serving_extension_channel_coverage["function_count"] == 60
    assert serving_extension_channel_coverage["source_rollout_function_count"] == 209
    assert serving_extension_channel_coverage["public_supported_channels_complete"] is True
    assert serving_extension_channel_coverage["validated_auxiliary_channels_complete"] is True
    assert serving_extension_channel_coverage["http_feature_flag_channel_complete"] is True
    assert (
        "Each referenced live suite executes all LLM_ROLLOUT_FUNCTION_CASES"
        in serving_extension_channel_coverage["coverage_basis"]
    )
    channel_entries = {
        item["channel"]: item for item in serving_extension_channel_coverage["channels"]
    }
    assert list(channel_entries) == [
        "python_sdk",
        "typescript_sdk",
        "bundled_worker",
        "runtime_local",
        "cli",
        "mcp",
        "http_api_feature_flag",
    ]
    for channel_name, item in channel_entries.items():
        assert item["status"] == "passed"
        assert item["module_count"] == 6
        assert item["function_count"] == 60
        assert item["covers_all_serving_extension_modules"] is True
        assert item["covers_all_serving_extension_functions"] is True
        if channel_name == "http_api_feature_flag":
            assert item["feature_flag"] is True
            assert item["script"] == "tests/integration/test_runtime_libraries_http_live.py"
            assert item["passed"] == 4
        elif channel_name == "python_sdk":
            assert item["feature_flag"] is False
            assert item["script"] == "tests/integration/test_algenta_mojo_library_live.py"
            assert item["passed"] == 7
        elif channel_name == "typescript_sdk":
            assert item["feature_flag"] is False
            assert item["script"] == "tests/integration/test_typescript_runtime_live.py"
            assert item["passed"] == 15
            assert item["skipped"] == 0
        else:
            assert item["feature_flag"] is False
            assert item["script"] == "tests/integration/test_cli_mcp_runtime_libraries_live.py"
            assert item["passed"] == 11

    live_suites = payload["live_suites"]
    assert [item["name"] for item in live_suites] == [
        "python_sdk_local_runtime",
        "typescript_sdk_local_runtime",
        "local_runtime_cli_mcp_matrix",
    ]
    assert [item["status"] for item in live_suites] == ["passed", "passed", "passed"]
    assert [item["passed"] for item in live_suites] == [7, 15, 11]
    assert [item["failed"] for item in live_suites] == [0, 0, 0]
    assert [item["skipped"] for item in live_suites] == [0, 0, 0]
    for item in live_suites:
        assert item["elapsed_seconds"] >= 0
