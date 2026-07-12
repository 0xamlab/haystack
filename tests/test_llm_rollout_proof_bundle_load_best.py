"""Tests for test_llm_rollout_proof_bundle: load_best.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-2/tests/test_llm_rollout_proof_bundle.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_rollout_proof_bundle_helpers import *  # noqa: F401,F403


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
                "channels": ["bundled_worker", "runtime_local", "cli", "mcp"],
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
                "channels": ["bundled_worker", "runtime_local", "cli", "mcp"],
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

