from __future__ import annotations

import json
import sys

import benchmarks.llm_rollout_proof_bundle as proof_bundle
from benchmarks.llm_rollout_proof_bundle import (
    HTTP_FLAG_CONTRACT_SUITES,
    HTTP_FLAG_LIVE_SUITES,
    PUBLIC_HTTP_LIBRARY_ROUTES_ENABLE_ENV,
    PUBLIC_SUPPORTED_CHANNELS,
    SDK_CONTRACT_SUITES,
    SERVING_EXTENSION_CHANNEL_SUITES,
    SERVING_EXTENSION_MODULES,
    UNDERLYING_VALIDATED_LANES,
    _parse_live_suite_summary,
    _parse_test_runner_summary,
    _validate_compiled_runtime_artifact,
)


def test_parse_live_suite_summary_extracts_pass_fail_skip_counts() -> None:
    output = """
Passed: 11
Skipped: 2
Failed: 0
"""

    assert _parse_live_suite_summary(output) == {"passed": 11, "failed": 0, "skipped": 2}


def test_parse_test_runner_summary_extracts_vitest_counts() -> None:
    output = """
Tests  1 passed | 8 skipped (9)
"""

    assert _parse_test_runner_summary(output) == {"passed": 1, "failed": 0, "skipped": 8}


def test_rollout_proof_bundle_channel_sets_match_supported_surfaces() -> None:
    assert PUBLIC_SUPPORTED_CHANNELS == ("python_sdk", "typescript_sdk", "cli", "mcp")
    assert UNDERLYING_VALIDATED_LANES == ("daemon_client", "runtime_local")
    assert PUBLIC_HTTP_LIBRARY_ROUTES_ENABLE_ENV == "ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED"
    assert tuple(suite["name"] for suite in SDK_CONTRACT_SUITES) == (
        "python_sdk_package_contract",
        "typescript_sdk_package_contract",
    )
    assert tuple(suite["name"] for suite in HTTP_FLAG_CONTRACT_SUITES) == (
        "public_http_library_routes_feature_flag",
    )
    assert tuple(suite["name"] for suite in HTTP_FLAG_LIVE_SUITES) == (
        "public_http_library_routes_feature_flag_live",
    )
    assert SDK_CONTRACT_SUITES[0]["command"][1:] == (
        "-m",
        "pytest",
        "-q",
        "tests/test_algenta_mojo_sdk.py",
        "-k",
        "keeps_rollout_modules_on_canonical_names_and_alias_dispatch",
    )
    assert SDK_CONTRACT_SUITES[1]["command"] == (
        "pnpm",
        "--dir",
        "packages/ts-sdk",
        "exec",
        "vitest",
        "run",
        "src/libraries.test.ts",
        "-t",
        "keeps the 22-library rollout inventory on canonical module names and alias dispatch",
    )
    assert HTTP_FLAG_CONTRACT_SUITES[0]["command"][1:] == (
        "-m",
        "pytest",
        "-q",
        "tests/test_runtime_libraries_api.py",
    )
    assert HTTP_FLAG_LIVE_SUITES[0]["script"] == "tests/integration/test_runtime_libraries_http_live.py"
    assert HTTP_FLAG_LIVE_SUITES[0]["channels"] == ("http_api_feature_flag",)
    assert HTTP_FLAG_LIVE_SUITES[0]["minimum_passed"] == 4
    assert tuple(item["channel"] for item in SERVING_EXTENSION_CHANNEL_SUITES) == (
        "python_sdk",
        "typescript_sdk",
        "daemon_client",
        "runtime_local",
        "cli",
        "mcp",
        "http_api_feature_flag",
    )
    assert SERVING_EXTENSION_MODULES == (
        "kv_cache",
        "paged_kv_cache",
        "continuous_batching",
        "inference_engine",
        "speculative_decoding",
        "generation_loop",
    )


def test_validate_compiled_runtime_artifact_rejects_non_mojo_function() -> None:
    payload = {
        "module_count": 1,
        "function_count": 1,
        "failed_function_count": 0,
        "modules": {
            "bpe_tokenizer": {
                "functions": {
                    "bpe_merge_score": {
                        "engine_used": "python",
                    }
                }
            }
        },
    }

    try:
        _validate_compiled_runtime_artifact(payload)
    except ValueError as exc:
        assert "expected 22" in str(exc) or "did not use mojo" in str(exc)
    else:
        raise AssertionError("compiled runtime validator should reject non-rollout payloads")


def test_load_best_cached_live_suite_results_prefers_passed_bundle(monkeypatch, tmp_path) -> None:
    skipped_output = tmp_path / "bundle_out.json"
    default_output = tmp_path / "checked_in_bundle.json"
    missing_artifact_paths = {
        "python_sdk_local_runtime": tmp_path / "missing_python_sdk_local_runtime.json",
        "typescript_sdk_local_runtime": tmp_path / "missing_typescript_sdk_local_runtime.json",
        "local_runtime_cli_mcp_matrix": tmp_path / "missing_local_runtime_cli_mcp_matrix.json",
        "public_http_library_routes_feature_flag_live": tmp_path
        / "missing_public_http_library_routes_feature_flag_live.json",
    }

    skipped_output.write_text(
        json.dumps(
            {
                "live_suites": [
                    {"name": "python_sdk_local_runtime", "status": "skipped"},
                    {"name": "typescript_sdk_local_runtime", "status": "skipped"},
                    {"name": "local_runtime_cli_mcp_matrix", "status": "skipped"},
                ],
                "http_flag_live_suites": [
                    {
                        "name": "public_http_library_routes_feature_flag_live",
                        "status": "skipped",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    default_output.write_text(
        json.dumps(
            {
                "live_suites": [
                    {
                        "name": "python_sdk_local_runtime",
                        "status": "passed",
                        "elapsed_seconds": 8.699,
                        "passed": 7,
                        "failed": 0,
                        "skipped": 0,
                    },
                    {
                        "name": "typescript_sdk_local_runtime",
                        "status": "passed",
                        "elapsed_seconds": 16.467,
                        "passed": 2,
                        "failed": 0,
                        "skipped": 2,
                    },
                    {
                        "name": "local_runtime_cli_mcp_matrix",
                        "status": "passed",
                        "elapsed_seconds": 73.083,
                        "passed": 11,
                        "failed": 0,
                        "skipped": 0,
                    },
                ],
                "http_flag_live_suites": [
                    {
                        "name": "public_http_library_routes_feature_flag_live",
                        "status": "passed",
                        "elapsed_seconds": 22.418,
                        "passed": 4,
                        "failed": 0,
                        "skipped": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(proof_bundle, "LIVE_SUMMARY_ARTIFACTS", missing_artifact_paths)
    monkeypatch.setattr(proof_bundle, "DEFAULT_OUTPUT", default_output)

    live_suites, http_flag_live_suites = proof_bundle._load_best_cached_live_suite_results(
        skipped_output
    )

    assert live_suites is not None
    assert http_flag_live_suites is not None
    assert [item["status"] for item in live_suites] == ["passed", "passed", "passed"]
    assert [item["passed"] for item in live_suites] == [7, 2, 11]
    assert [item["status"] for item in http_flag_live_suites] == ["passed"]
    assert http_flag_live_suites[0]["passed"] == 4


def test_normalize_live_suite_results_accepts_lower_reported_minimum_when_skipped() -> None:
    normalized = proof_bundle._normalize_live_suite_results(
        [
            {
                "name": "python_sdk_local_runtime",
                "status": "passed",
                "minimum_passed": 7,
                "passed": 7,
                "failed": 0,
                "skipped": 0,
                "elapsed_seconds": 8.699,
            },
            {
                "name": "typescript_sdk_local_runtime",
                "status": "passed",
                "minimum_passed": 1,
                "passed": 1,
                "failed": 0,
                "skipped": 9,
                "elapsed_seconds": 16.467,
            },
            {
                "name": "local_runtime_cli_mcp_matrix",
                "status": "passed",
                "minimum_passed": 11,
                "passed": 11,
                "failed": 0,
                "skipped": 0,
                "elapsed_seconds": 73.083,
            },
        ]
    )

    by_name = {item["name"]: item for item in normalized}
    assert by_name["typescript_sdk_local_runtime"]["minimum_passed"] == 1
    assert by_name["typescript_sdk_local_runtime"]["passed"] == 1
    assert by_name["typescript_sdk_local_runtime"]["skipped"] == 9


def test_load_best_cached_live_suite_results_uses_standalone_live_artifacts(
    monkeypatch, tmp_path
) -> None:
    skipped_output = tmp_path / "bundle_out.json"
    skipped_output.write_text(
        json.dumps(
            {
                "live_suites": [
                    {"name": "python_sdk_local_runtime", "status": "skipped"},
                    {"name": "typescript_sdk_local_runtime", "status": "skipped"},
                    {"name": "local_runtime_cli_mcp_matrix", "status": "skipped"},
                ],
                "http_flag_live_suites": [
                    {
                        "name": "public_http_library_routes_feature_flag_live",
                        "status": "skipped",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    artifact_paths = {
        "python_sdk_local_runtime": tmp_path / "python_sdk_local_runtime_live_summary.json",
        "typescript_sdk_local_runtime": tmp_path
        / "typescript_sdk_local_runtime_live_summary.json",
        "local_runtime_cli_mcp_matrix": tmp_path / "local_runtime_cli_mcp_matrix_live_summary.json",
        "public_http_library_routes_feature_flag_live": tmp_path
        / "public_http_library_routes_feature_flag_live_live_summary.json",
    }
    artifact_paths["python_sdk_local_runtime"].write_text(
        json.dumps(
            {
                "artifact": "llm_rollout_live_summary",
                "name": "python_sdk_local_runtime",
                "status": "passed",
                "script": "tests/integration/test_algenta_mojo_library_live.py",
                "channels": ["python_sdk"],
                "minimum_passed": 7,
                "passed": 7,
                "failed": 0,
                "skipped": 0,
                "elapsed_seconds": 8.699,
            }
        ),
        encoding="utf-8",
    )
    artifact_paths["typescript_sdk_local_runtime"].write_text(
        json.dumps(
            {
                "artifact": "llm_rollout_live_summary",
                "name": "typescript_sdk_local_runtime",
                "status": "passed",
                "script": "tests/integration/test_typescript_runtime_live.py",
                "channels": ["typescript_sdk"],
                "minimum_passed": 2,
                "passed": 2,
                "failed": 0,
                "skipped": 2,
                "elapsed_seconds": 16.467,
            }
        ),
        encoding="utf-8",
    )
    artifact_paths["local_runtime_cli_mcp_matrix"].write_text(
        json.dumps(
            {
                "artifact": "llm_rollout_live_summary",
                "name": "local_runtime_cli_mcp_matrix",
                "status": "passed",
                "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                "minimum_passed": 11,
                "passed": 11,
                "failed": 0,
                "skipped": 0,
                "elapsed_seconds": 73.083,
            }
        ),
        encoding="utf-8",
    )
    artifact_paths["public_http_library_routes_feature_flag_live"].write_text(
        json.dumps(
            {
                "artifact": "llm_rollout_live_summary",
                "name": "public_http_library_routes_feature_flag_live",
                "status": "passed",
                "script": "tests/integration/test_runtime_libraries_http_live.py",
                "channels": ["http_api_feature_flag"],
                "minimum_passed": 4,
                "passed": 4,
                "failed": 0,
                "skipped": 0,
                "elapsed_seconds": 22.418,
                "evidence_paths": ["tests/integration/test_runtime_libraries_http_live.py"],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(proof_bundle, "LIVE_SUMMARY_ARTIFACTS", artifact_paths)
    monkeypatch.setattr(proof_bundle, "DEFAULT_OUTPUT", tmp_path / "missing_default.json")

    live_suites, http_flag_live_suites = proof_bundle._load_best_cached_live_suite_results(
        skipped_output
    )

    assert live_suites is not None
    assert http_flag_live_suites is not None
    assert [item["status"] for item in live_suites] == ["passed", "passed", "passed"]
    assert [item["passed"] for item in live_suites] == [7, 2, 11]
    assert [item["status"] for item in http_flag_live_suites] == ["passed"]
    assert http_flag_live_suites[0]["passed"] == 4


def test_load_best_cached_live_suite_results_prefers_artifacts_on_equal_score(
    monkeypatch, tmp_path
) -> None:
    bundle_output = tmp_path / "bundle_out.json"
    bundle_output.write_text(
        json.dumps(
            {
                "live_suites": [
                    {
                        "name": "python_sdk_local_runtime",
                        "status": "passed",
                        "elapsed_seconds": 8.699,
                        "passed": 7,
                        "failed": 0,
                        "skipped": 0,
                    },
                    {
                        "name": "typescript_sdk_local_runtime",
                        "status": "passed",
                        "elapsed_seconds": 16.467,
                        "passed": 4,
                        "failed": 0,
                        "skipped": 0,
                    },
                    {
                        "name": "local_runtime_cli_mcp_matrix",
                        "status": "passed",
                        "elapsed_seconds": 73.083,
                        "passed": 11,
                        "failed": 0,
                        "skipped": 0,
                    },
                ],
                "http_flag_live_suites": [
                    {
                        "name": "public_http_library_routes_feature_flag_live",
                        "status": "passed",
                        "elapsed_seconds": 22.418,
                        "passed": 4,
                        "failed": 0,
                        "skipped": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    artifact_paths = {
        "python_sdk_local_runtime": tmp_path / "python_sdk_local_runtime_live_summary.json",
        "typescript_sdk_local_runtime": tmp_path
        / "typescript_sdk_local_runtime_live_summary.json",
        "local_runtime_cli_mcp_matrix": tmp_path / "local_runtime_cli_mcp_matrix_live_summary.json",
        "public_http_library_routes_feature_flag_live": tmp_path
        / "public_http_library_routes_feature_flag_live_live_summary.json",
    }
    artifact_paths["python_sdk_local_runtime"].write_text(
        json.dumps(
            {
                "artifact": "llm_rollout_live_summary",
                "name": "python_sdk_local_runtime",
                "status": "passed",
                "script": "tests/integration/test_algenta_mojo_library_live.py",
                "channels": ["python_sdk"],
                "minimum_passed": 7,
                "passed": 7,
                "failed": 0,
                "skipped": 0,
                "elapsed_seconds": 8.699,
            }
        ),
        encoding="utf-8",
    )
    artifact_paths["typescript_sdk_local_runtime"].write_text(
        json.dumps(
            {
                "artifact": "llm_rollout_live_summary",
                "name": "typescript_sdk_local_runtime",
                "status": "passed",
                "script": "tests/integration/test_typescript_runtime_live.py",
                "channels": ["typescript_sdk"],
                "minimum_passed": 2,
                "passed": 2,
                "failed": 0,
                "skipped": 2,
                "elapsed_seconds": 16.467,
            }
        ),
        encoding="utf-8",
    )
    artifact_paths["local_runtime_cli_mcp_matrix"].write_text(
        json.dumps(
            {
                "artifact": "llm_rollout_live_summary",
                "name": "local_runtime_cli_mcp_matrix",
                "status": "passed",
                "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                "minimum_passed": 11,
                "passed": 11,
                "failed": 0,
                "skipped": 0,
                "elapsed_seconds": 73.083,
            }
        ),
        encoding="utf-8",
    )
    artifact_paths["public_http_library_routes_feature_flag_live"].write_text(
        json.dumps(
            {
                "artifact": "llm_rollout_live_summary",
                "name": "public_http_library_routes_feature_flag_live",
                "status": "passed",
                "script": "tests/integration/test_runtime_libraries_http_live.py",
                "channels": ["http_api_feature_flag"],
                "minimum_passed": 4,
                "passed": 4,
                "failed": 0,
                "skipped": 0,
                "elapsed_seconds": 22.418,
                "evidence_paths": ["tests/integration/test_runtime_libraries_http_live.py"],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(proof_bundle, "LIVE_SUMMARY_ARTIFACTS", artifact_paths)
    monkeypatch.setattr(proof_bundle, "DEFAULT_OUTPUT", tmp_path / "missing_default.json")

    live_suites, http_flag_live_suites = proof_bundle._load_best_cached_live_suite_results(
        bundle_output
    )

    assert live_suites is not None
    assert http_flag_live_suites is not None
    assert live_suites[1]["passed"] == 2
    assert live_suites[1]["skipped"] == 2
    assert http_flag_live_suites[0]["passed"] == 4


def test_main_skip_live_reuses_cached_live_suite_results(monkeypatch, tmp_path, capsys) -> None:
    output_path = tmp_path / "bundle_out.json"
    synced: dict[str, object] = {}
    cached_live_suites = [
        {
            "name": "python_sdk_local_runtime",
            "status": "passed",
            "elapsed_seconds": 8.699,
            "passed": 7,
            "failed": 0,
            "skipped": 0,
            "channels": ["python_sdk"],
            "minimum_passed": 7,
        }
    ]
    cached_http_flag_live_suites = [
        {
            "name": "public_http_library_routes_feature_flag_live",
            "status": "passed",
            "elapsed_seconds": 22.418,
            "passed": 4,
            "failed": 0,
            "skipped": 0,
            "channels": ["http_api_feature_flag"],
            "minimum_passed": 4,
            "evidence_paths": ["tests/integration/test_runtime_libraries_http_live.py"],
        }
    ]
    forwarded: dict[str, object] = {}

    monkeypatch.setattr(
        proof_bundle,
        "_load_best_cached_live_suite_results",
        lambda path: (cached_live_suites, cached_http_flag_live_suites),
    )

    def fake_build_proof_bundle(
        *,
        run_live,
        refresh_artifacts,
        live_suite_results,
        http_flag_live_suite_results,
    ):
        forwarded["run_live"] = run_live
        forwarded["refresh_artifacts"] = refresh_artifacts
        forwarded["live_suite_results"] = live_suite_results
        forwarded["http_flag_live_suite_results"] = http_flag_live_suite_results
        return {
            "bundle": "llm_rollout_proof_bundle",
            "parity_artifact": {"path": "build/llm_rollout_parity_benchmark.json"},
            "compiled_runtime_artifact": {"path": "build/llm_compiled_runtime_benchmark.json"},
        }

    monkeypatch.setattr(proof_bundle, "build_proof_bundle", fake_build_proof_bundle)
    monkeypatch.setattr(
        proof_bundle,
        "sync_rollout_scorecard",
        lambda bundle, *, scorecard_path=proof_bundle.SCORECARD_PATH: synced.setdefault(
            "bundle", bundle
        ),
    )
    monkeypatch.setattr(sys, "argv", ["llm_rollout_proof_bundle.py", "--skip-live", "--output", str(output_path)])

    assert proof_bundle.main() == 0
    assert forwarded["run_live"] is False
    assert forwarded["refresh_artifacts"] is False
    assert forwarded["live_suite_results"] == cached_live_suites
    assert forwarded["http_flag_live_suite_results"] == cached_http_flag_live_suites
    assert json.loads(output_path.read_text()) == {
        "bundle": "llm_rollout_proof_bundle",
        "parity_artifact": {"path": "build/llm_rollout_parity_benchmark.json"},
        "compiled_runtime_artifact": {"path": "build/llm_compiled_runtime_benchmark.json"},
    }
    assert synced["bundle"] == {
        "bundle": "llm_rollout_proof_bundle",
        "parity_artifact": {"path": "build/llm_rollout_parity_benchmark.json"},
        "compiled_runtime_artifact": {"path": "build/llm_compiled_runtime_benchmark.json"},
    }
    captured = capsys.readouterr().out
    assert str(output_path) in captured
    assert str(proof_bundle.SCORECARD_PATH) in captured


def test_sync_rollout_scorecard_rewrites_rollout_section(tmp_path) -> None:
    scorecard_path = tmp_path / "scorecard.md"
    scorecard_path.write_text(
        "# Decision Engine Scorecard\n\n"
        "Updated: 2026-05-22\n\n"
        "## Current measured state\n\n"
        "placeholder\n\n"
        "## LLM rollout proof (2026-05-21)\n\n"
        "old rollout text\n\n"
        "## Non-negotiable product requirement\n\n"
        "rest of scorecard\n",
        encoding="utf-8",
    )
    bundle = {
        "generated_at": "2026-05-22T01:55:42Z",
        "parity_artifact": {
            "library_count": 22,
            "function_count": 209,
            "median_speedup_x": 106.72,
            "mean_speedup_x": 156.85,
            "max_speedup_x": 677.97,
        },
        "compiled_runtime_artifact": {
            "module_count": 22,
            "function_count": 209,
            "failed_function_count": 0,
            "max_cold_ms": {"value": 50.88025},
            "max_warm_ms": {"value": 0.456917},
            "max_hot_ms": {"value": 0.363354},
        },
        "serving_extension_subset": {
            "module_count": 6,
            "function_count": 60,
            "min_speedup_x": 106.72,
            "max_speedup_x": 286.81,
            "max_cold_ms": {"value": 3.926125},
            "max_warm_ms": {"value": 2.572084},
            "max_hot_ms": {"value": 1.473583},
        },
        "serving_extension_channel_coverage": {
            "module_count": 6,
            "function_count": 60,
        },
        "live_suites": [
            {
                "name": "python_sdk_local_runtime",
                "passed": 7,
                "minimum_passed": 7,
                "skipped": 0,
            },
            {
                "name": "typescript_sdk_local_runtime",
                "passed": 4,
                "minimum_passed": 2,
                "skipped": 0,
            },
            {
                "name": "local_runtime_cli_mcp_matrix",
                "passed": 11,
                "minimum_passed": 11,
                "skipped": 0,
            },
        ],
        "sdk_contract_suites": [
            {"name": "python_sdk_package_contract", "passed": 1},
            {"name": "typescript_sdk_package_contract", "passed": 1, "skipped": 8},
        ],
        "http_flag_contract_suites": [
            {"name": "public_http_library_routes_feature_flag", "passed": 2, "failed": 0}
        ],
        "http_flag_live_suites": [
            {
                "name": "public_http_library_routes_feature_flag_live",
                "passed": 4,
                "minimum_passed": 4,
                "failed": 0,
            }
        ],
    }

    original_sync_shared = proof_bundle.sync_shared_benchmark_scorecard
    proof_bundle.sync_shared_benchmark_scorecard = lambda *, scorecard_path=proof_bundle.SCORECARD_PATH: None
    try:
        proof_bundle.sync_rollout_scorecard(bundle, scorecard_path=scorecard_path)
    finally:
        proof_bundle.sync_shared_benchmark_scorecard = original_sync_shared

    text = scorecard_path.read_text(encoding="utf-8")
    assert "## LLM rollout proof (2026-05-22)" in text
    assert "22 libraries, 209 public runtime functions, 106.72x median, 156.85x mean, 677.97x max" in text
    assert "22 modules, 209 functions, 0 failures, all `engine_used=\"mojo\"`, worst cold 50.88 ms, warm 0.457 ms, hot 0.363 ms" in text
    assert "TypeScript SDK 4 passed and 0 API-backed skips when `DE_API_KEY` is unset" in text
    assert "## Non-negotiable product requirement" in text


def test_build_proof_bundle_skip_live_uses_validated_artifact_payloads(monkeypatch) -> None:
    parity_payload = {
        "n_libraries": 22,
        "total_functions_compared": 209,
        "median_speedup_x": 89.61,
        "mean_speedup_x": 99.99,
        "max_speedup_x": 487.08,
        "timestamp": "2026-05-21T21:46:12",
    }
    compiled_payload = {
        "module_count": 22,
        "function_count": 209,
        "failed_function_count": 0,
        "transport": "compiled_worker",
        "modules": {},
    }

    monkeypatch.setattr(
        proof_bundle,
        "_read_json",
        lambda path: parity_payload if path == proof_bundle.PARITY_ARTIFACT else compiled_payload,
    )
    monkeypatch.setattr(proof_bundle, "_ensure_benchmark_artifacts", lambda refresh_artifacts: None)
    monkeypatch.setattr(proof_bundle, "validate_rollout_summary", lambda payload: None)
    monkeypatch.setattr(proof_bundle, "_validate_compiled_runtime_artifact", lambda payload: None)
    monkeypatch.setattr(
        proof_bundle,
        "_max_latency",
        lambda payload, key: (1.0, "module_name", f"{key}_function"),
    )
    monkeypatch.setattr(
        proof_bundle,
        "_collect_live_suite_results",
        lambda run_live: [
            {"name": "python_sdk_local_runtime", "status": "skipped"},
            {"name": "typescript_sdk_local_runtime", "status": "skipped"},
            {"name": "local_runtime_cli_mcp_matrix", "status": "skipped"},
        ],
    )
    monkeypatch.setattr(
        proof_bundle,
        "_collect_sdk_contract_suite_results",
        lambda: [
            {
                "name": "python_sdk_package_contract",
                "status": "passed",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
            },
            {
                "name": "typescript_sdk_package_contract",
                "status": "passed",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
            },
        ],
    )
    monkeypatch.setattr(
        proof_bundle,
        "_collect_http_flag_contract_suite_results",
        lambda: [
            {
                "name": "public_http_library_routes_feature_flag",
                "status": "passed",
                "passed": 2,
                "failed": 0,
                "skipped": 0,
            }
        ],
    )
    monkeypatch.setattr(
        proof_bundle,
        "_collect_http_flag_live_suite_results",
        lambda run_live: [
            {
                "name": "public_http_library_routes_feature_flag_live",
                "status": "skipped",
            }
        ],
    )
    monkeypatch.setattr(
        proof_bundle,
        "_build_serving_extension_subset_summary",
        lambda parity_payload, compiled_payload: {
            "module_count": 6,
            "function_count": 60,
            "functions_compared": 60,
            "all_modules_fully_compared": True,
            "all_compiled_engine_used_mojo": True,
            "min_speedup_x": 77.67,
            "max_speedup_x": 314.75,
            "modules": [],
        },
    )
    monkeypatch.setattr(
        proof_bundle,
        "_build_serving_extension_channel_coverage",
        lambda live_suites, http_flag_live_suites: {
            "module_count": 6,
            "function_count": 60,
            "source_rollout_function_count": 209,
            "coverage_basis": "Each referenced live suite executes all LLM_ROLLOUT_FUNCTION_CASES, which includes the six serving extension modules.",
            "public_supported_channels_complete": False,
            "validated_auxiliary_channels_complete": False,
            "http_feature_flag_channel_complete": False,
            "channels": [
                {
                    "channel": "python_sdk",
                    "suite_name": "python_sdk_local_runtime",
                    "script": "tests/integration/test_algenta_mojo_library_live.py",
                    "status": "skipped",
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "feature_flag": False,
                    "module_count": 6,
                    "function_count": 60,
                    "covers_all_serving_extension_modules": False,
                    "covers_all_serving_extension_functions": False,
                }
            ],
        },
    )

    bundle = proof_bundle.build_proof_bundle(run_live=False)

    assert bundle["bundle"] == "llm_rollout_proof_bundle"
    assert bundle["expected_modules"] == 22
    assert bundle["expected_functions"] == 209
    assert bundle["public_supported_channels"] == list(PUBLIC_SUPPORTED_CHANNELS)
    assert bundle["underlying_validated_lanes"] == list(UNDERLYING_VALIDATED_LANES)
    assert bundle["public_http_library_routes_supported"] is False
    assert bundle["public_http_library_routes_feature_flag_ready"] is True
    assert bundle["public_http_library_routes_enable_env"] == PUBLIC_HTTP_LIBRARY_ROUTES_ENABLE_ENV

    parity = bundle["parity_artifact"]
    assert parity["path"] == "build/llm_rollout_parity_benchmark.json"
    assert parity["library_count"] == 22
    assert parity["function_count"] == 209

    compiled = bundle["compiled_runtime_artifact"]
    assert compiled["path"] == "build/llm_compiled_runtime_benchmark.json"
    assert compiled["module_count"] == 22
    assert compiled["function_count"] == 209
    assert compiled["failed_function_count"] == 0
    assert compiled["transport"] == "compiled_worker"

    sdk_contract_suites = bundle["sdk_contract_suites"]
    assert [item["name"] for item in sdk_contract_suites] == [
        "python_sdk_package_contract",
        "typescript_sdk_package_contract",
    ]
    assert [item["status"] for item in sdk_contract_suites] == ["passed", "passed"]
    http_flag_contract_suites = bundle["http_flag_contract_suites"]
    assert [item["name"] for item in http_flag_contract_suites] == [
        "public_http_library_routes_feature_flag"
    ]
    assert [item["status"] for item in http_flag_contract_suites] == ["passed"]
    assert http_flag_contract_suites[0]["passed"] == 2
    assert http_flag_contract_suites[0]["failed"] == 0
    http_flag_live_suites = bundle["http_flag_live_suites"]
    assert [item["name"] for item in http_flag_live_suites] == [
        "public_http_library_routes_feature_flag_live"
    ]
    assert [item["status"] for item in http_flag_live_suites] == ["skipped"]
    serving_extension_subset = bundle["serving_extension_subset"]
    assert serving_extension_subset["module_count"] == 6
    assert serving_extension_subset["function_count"] == 60
    assert serving_extension_subset["functions_compared"] == 60
    assert serving_extension_subset["all_modules_fully_compared"] is True
    assert serving_extension_subset["all_compiled_engine_used_mojo"] is True
    serving_extension_channel_coverage = bundle["serving_extension_channel_coverage"]
    assert serving_extension_channel_coverage["module_count"] == 6
    assert serving_extension_channel_coverage["function_count"] == 60
    assert serving_extension_channel_coverage["source_rollout_function_count"] == 209
    assert serving_extension_channel_coverage["public_supported_channels_complete"] is False
    assert serving_extension_channel_coverage["validated_auxiliary_channels_complete"] is False
    assert serving_extension_channel_coverage["http_feature_flag_channel_complete"] is False
    assert serving_extension_channel_coverage["channels"][0]["channel"] == "python_sdk"
    assert serving_extension_channel_coverage["channels"][0]["status"] == "skipped"

    live_suites = bundle["live_suites"]
    assert [item["status"] for item in live_suites] == ["skipped", "skipped", "skipped"]


def test_build_proof_bundle_accepts_explicit_live_suite_results(monkeypatch) -> None:
    parity_payload = {
        "n_libraries": 22,
        "total_functions_compared": 209,
        "median_speedup_x": 89.61,
        "mean_speedup_x": 99.99,
        "max_speedup_x": 487.08,
        "timestamp": "2026-05-21T21:46:12",
    }
    compiled_payload = {
        "module_count": 22,
        "function_count": 209,
        "failed_function_count": 0,
        "transport": "compiled_worker",
        "modules": {},
    }
    live_suite_results = [
        {
            "name": "python_sdk_local_runtime",
            "status": "passed",
            "elapsed_seconds": 8.699,
            "passed": 7,
            "failed": 0,
            "skipped": 0,
        },
        {
            "name": "typescript_sdk_local_runtime",
            "status": "passed",
            "elapsed_seconds": 16.467,
            "passed": 2,
            "failed": 0,
            "skipped": 2,
        },
        {
            "name": "local_runtime_cli_mcp_matrix",
            "status": "passed",
            "elapsed_seconds": 73.083,
            "passed": 11,
            "failed": 0,
            "skipped": 0,
        },
    ]

    monkeypatch.setattr(
        proof_bundle,
        "_read_json",
        lambda path: parity_payload if path == proof_bundle.PARITY_ARTIFACT else compiled_payload,
    )
    monkeypatch.setattr(proof_bundle, "_ensure_benchmark_artifacts", lambda refresh_artifacts: None)
    monkeypatch.setattr(proof_bundle, "validate_rollout_summary", lambda payload: None)
    monkeypatch.setattr(proof_bundle, "_validate_compiled_runtime_artifact", lambda payload: None)
    monkeypatch.setattr(
        proof_bundle,
        "_max_latency",
        lambda payload, key: (1.0, "module_name", f"{key}_function"),
    )
    monkeypatch.setattr(
        proof_bundle,
        "_collect_live_suite_results",
        lambda run_live: (_ for _ in ()).throw(AssertionError("should not collect live suites")),
    )
    monkeypatch.setattr(
        proof_bundle,
        "_collect_http_flag_live_suite_results",
        lambda run_live: (_ for _ in ()).throw(
            AssertionError("should not collect http flag live suites")
        ),
    )
    monkeypatch.setattr(
        proof_bundle,
        "_build_serving_extension_subset_summary",
        lambda parity_payload, compiled_payload: {
            "module_count": 6,
            "function_count": 60,
            "functions_compared": 60,
            "all_modules_fully_compared": True,
            "all_compiled_engine_used_mojo": True,
            "min_speedup_x": 77.67,
            "max_speedup_x": 314.75,
            "modules": [
                {
                    "name": "kv_cache",
                    "parity_function_count": 10,
                    "parity_compared_count": 10,
                    "parity_speedup_x": 106.28,
                    "compiled_function_count": 10,
                    "compiled_all_engine_used_mojo": True,
                }
            ],
        },
    )
    monkeypatch.setattr(
        proof_bundle,
        "_build_serving_extension_channel_coverage",
        lambda live_suites, http_flag_live_suites: {
            "module_count": 6,
            "function_count": 60,
            "source_rollout_function_count": 209,
            "coverage_basis": "Each referenced live suite executes all LLM_ROLLOUT_FUNCTION_CASES, which includes the six serving extension modules.",
            "public_supported_channels_complete": True,
            "validated_auxiliary_channels_complete": True,
            "http_feature_flag_channel_complete": True,
            "channels": [
                {
                    "channel": "python_sdk",
                    "suite_name": "python_sdk_local_runtime",
                    "script": "tests/integration/test_algenta_mojo_library_live.py",
                    "status": "passed",
                    "passed": 7,
                    "failed": 0,
                    "skipped": 0,
                    "feature_flag": False,
                    "module_count": 6,
                    "function_count": 60,
                    "covers_all_serving_extension_modules": True,
                    "covers_all_serving_extension_functions": True,
                },
                {
                    "channel": "http_api_feature_flag",
                    "suite_name": "public_http_library_routes_feature_flag_live",
                    "script": "tests/integration/test_runtime_libraries_http_live.py",
                    "status": "passed",
                    "passed": 4,
                    "failed": 0,
                    "skipped": 0,
                    "feature_flag": True,
                    "module_count": 6,
                    "function_count": 60,
                    "covers_all_serving_extension_modules": True,
                    "covers_all_serving_extension_functions": True,
                },
            ],
        },
    )
    monkeypatch.setattr(
        proof_bundle,
        "_collect_sdk_contract_suite_results",
        lambda: [
            {
                "name": "python_sdk_package_contract",
                "status": "passed",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
            },
            {
                "name": "typescript_sdk_package_contract",
                "status": "passed",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
            },
        ],
    )
    monkeypatch.setattr(
        proof_bundle,
        "_collect_http_flag_contract_suite_results",
        lambda: [
            {
                "name": "public_http_library_routes_feature_flag",
                "status": "passed",
                "passed": 2,
                "failed": 0,
                "skipped": 0,
            }
        ],
    )

    bundle = proof_bundle.build_proof_bundle(
        run_live=False,
        live_suite_results=live_suite_results,
        http_flag_live_suite_results=[
            {
                "name": "public_http_library_routes_feature_flag_live",
                "status": "passed",
                "elapsed_seconds": 22.418,
                "passed": 4,
                "failed": 0,
                "skipped": 0,
            }
        ],
    )

    sdk_contract_suites = bundle["sdk_contract_suites"]
    assert [item["name"] for item in sdk_contract_suites] == [
        "python_sdk_package_contract",
        "typescript_sdk_package_contract",
    ]
    http_flag_contract_suites = bundle["http_flag_contract_suites"]
    assert [item["name"] for item in http_flag_contract_suites] == [
        "public_http_library_routes_feature_flag"
    ]
    assert [item["status"] for item in http_flag_contract_suites] == ["passed"]
    assert http_flag_contract_suites[0]["passed"] == 2
    assert http_flag_contract_suites[0]["failed"] == 0
    http_flag_live_suites = bundle["http_flag_live_suites"]
    assert [item["name"] for item in http_flag_live_suites] == [
        "public_http_library_routes_feature_flag_live"
    ]
    assert [item["status"] for item in http_flag_live_suites] == ["passed"]
    assert http_flag_live_suites[0]["passed"] == 4
    assert http_flag_live_suites[0]["failed"] == 0
    assert http_flag_live_suites[0]["channels"] == ["http_api_feature_flag"]
    serving_extension_subset = bundle["serving_extension_subset"]
    assert serving_extension_subset["module_count"] == 6
    assert serving_extension_subset["function_count"] == 60
    assert serving_extension_subset["functions_compared"] == 60
    assert serving_extension_subset["modules"][0]["name"] == "kv_cache"
    serving_extension_channel_coverage = bundle["serving_extension_channel_coverage"]
    assert serving_extension_channel_coverage["module_count"] == 6
    assert serving_extension_channel_coverage["function_count"] == 60
    assert serving_extension_channel_coverage["source_rollout_function_count"] == 209
    assert serving_extension_channel_coverage["public_supported_channels_complete"] is True
    assert serving_extension_channel_coverage["validated_auxiliary_channels_complete"] is True
    assert serving_extension_channel_coverage["http_feature_flag_channel_complete"] is True
    assert serving_extension_channel_coverage["channels"][0]["channel"] == "python_sdk"
    assert serving_extension_channel_coverage["channels"][1]["channel"] == "http_api_feature_flag"
    live_suites = bundle["live_suites"]
    assert [item["name"] for item in live_suites] == [
        "python_sdk_local_runtime",
        "typescript_sdk_local_runtime",
        "local_runtime_cli_mcp_matrix",
    ]
    assert [item["status"] for item in live_suites] == ["passed", "passed", "passed"]
    assert live_suites[1]["skipped"] == 2
