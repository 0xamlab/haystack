from __future__ import annotations

import json

import pytest

from benchmarks.llm_rollout_live_artifacts import (
    LIVE_SUMMARY_ARTIFACTS,
    LIVE_SUMMARY_SCRIPTS,
    read_live_summary_artifact,
    write_live_summary_artifact,
)


def test_live_summary_artifacts_cover_all_rollout_live_suite_names() -> None:
    assert set(LIVE_SUMMARY_ARTIFACTS) == {
        "python_sdk_local_runtime",
        "typescript_sdk_local_runtime",
        "local_runtime_cli_mcp_matrix",
        "public_http_library_routes_feature_flag_live",
    }
    assert LIVE_SUMMARY_SCRIPTS == {
        "python_sdk_local_runtime": "tests/integration/test_algenta_mojo_library_live.py",
        "typescript_sdk_local_runtime": "tests/integration/test_typescript_runtime_live.py",
        "local_runtime_cli_mcp_matrix": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
        "public_http_library_routes_feature_flag_live": (
            "tests/integration/test_runtime_libraries_http_live.py"
        ),
    }
    assert (
        LIVE_SUMMARY_ARTIFACTS["public_http_library_routes_feature_flag_live"].name
        == "public_http_library_routes_feature_flag_live_live_summary.json"
    )


def test_live_summary_artifact_paths_follow_suite_name_live_suffix() -> None:
    assert {
        name: path.name for name, path in LIVE_SUMMARY_ARTIFACTS.items()
    } == {name: f"{name}_live_summary.json" for name in LIVE_SUMMARY_ARTIFACTS}


def test_write_and_read_live_summary_artifact_round_trip(tmp_path) -> None:
    artifact_path = tmp_path / "local_runtime_cli_mcp_matrix_live_summary.json"
    original_path = LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"]
    LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"] = artifact_path

    try:
        payload = write_live_summary_artifact(
            output_path=artifact_path,
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=11,
            passed=11,
            failed=0,
            skipped=0,
            elapsed_seconds=12.3456,
            extra={"base_url": "http://127.0.0.1:8000"},
        )

        assert payload["artifact"] == "llm_rollout_live_summary"
        assert payload["generated_at"].endswith("Z")
        assert payload["status"] == "passed"
        assert payload["elapsed_seconds"] == 12.346

        raw_text = artifact_path.read_text(encoding="utf-8")
        assert raw_text.endswith("\n")
        assert raw_text.index('"artifact"') < raw_text.index('"base_url"')
        assert raw_text.index('"base_url"') < raw_text.index('"channels"')

        loaded = read_live_summary_artifact(artifact_path)
        assert loaded["name"] == "local_runtime_cli_mcp_matrix"
        assert loaded["channels"] == ["daemon_client", "runtime_local", "cli", "mcp"]
        assert loaded["minimum_passed"] == 11
        assert loaded["base_url"] == "http://127.0.0.1:8000"
    finally:
        LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"] = original_path


def test_write_live_summary_artifact_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError, match="minimum_passed must be <= passed \\+ failed \\+ skipped"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=12,
            passed=11,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="failed must be >= 0"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=-1,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="passed must be an integer, not boolean"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=True,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="passed must be an integer"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1.5,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="elapsed_seconds must be a finite number >= 0"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=float("nan"),
        )

    with pytest.raises(ValueError, match="elapsed_seconds must be a finite number >= 0"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=False,
        )

    with pytest.raises(ValueError, match="elapsed_seconds must be a finite number >= 0"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds="1.25",
        )


def test_write_live_summary_artifact_rejects_invalid_script_and_channels() -> None:
    with pytest.raises(ValueError, match="script must be a tests/integration/\\*\\.py path"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script=123,
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="script must be a tests/integration/\\*\\.py path"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="benchmarks/scorecard_sync.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(
        ValueError,
        match="script must match registered suite script: tests/integration/test_cli_mcp_runtime_libraries_live.py",
    ):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_runtime_libraries_http_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="channels must not be empty"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=(),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(
        ValueError,
        match="channels must be a sequence of channel names, not a single string",
    ):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels="cli",
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="channels must be a list or tuple of channel names"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels={"cli", "mcp"},
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="channels must contain only strings"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("cli", 1),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="channels must not contain blank names"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("cli", "   "),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="channels must be unique"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("cli", "cli"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )


def test_write_live_summary_artifact_rejects_reserved_or_invalid_extra() -> None:
    with pytest.raises(ValueError, match="extra must use only string keys"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
            extra={1: "bad"},
        )

    with pytest.raises(ValueError, match="extra must use only string keys"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
            extra={"nested": [{1: "bad"}]},
        )

    with pytest.raises(ValueError, match="extra must not contain tuples"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
            extra={"nested": ("bad", "tuple")},
        )

    with pytest.raises(ValueError, match="extra must not override reserved keys: status"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
            extra={"status": "forged"},
        )

    with pytest.raises(ValueError, match="extra must be JSON-serializable with finite values"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
            extra={"bad": float("nan")},
        )


def test_write_live_summary_artifact_rejects_unknown_suite_name_and_mismatched_output_path() -> None:
    with pytest.raises(ValueError, match="unknown rollout live summary name"):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"],
            suite_name="unknown_suite",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    with pytest.raises(
        ValueError,
        match="output_path must match registered artifact path: .*local_runtime_cli_mcp_matrix_live_summary.json",
    ):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"].with_name(
                "local_runtime_cli_mcp_matrix_live_summary.json"
            ).parent
            / "nested"
            / "local_runtime_cli_mcp_matrix_live_summary.json",
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )


def test_read_live_summary_artifact_rejects_malformed_payload(tmp_path, monkeypatch) -> None:
    artifact_path = tmp_path / "local_runtime_cli_mcp_matrix_live_summary.json"
    original_path = LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"]
    LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"] = artifact_path
    try:
        artifact_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
        with pytest.raises(ValueError, match="must contain a JSON object"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", "daemon_client"],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="channels must be unique"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", 1],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="channels must contain only strings"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": 123,
                    "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="script must be a tests/integration/\\*\\.py path"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", "   "],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="channels must not contain blank names"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": {"cli": True},
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="channels must be a list or tuple of channel names"):
            read_live_summary_artifact(artifact_path)
    finally:
        LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"] = original_path

    original_path = LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"]
    original_script = LIVE_SUMMARY_SCRIPTS["local_runtime_cli_mcp_matrix"]
    LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"] = artifact_path
    LIVE_SUMMARY_SCRIPTS["local_runtime_cli_mcp_matrix"] = "tests/integration/test_cli_mcp_runtime_libraries_live.py"
    try:
        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_runtime_libraries_http_live.py",
                    "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(
            ValueError,
            match="script must match registered suite script: tests/integration/test_cli_mcp_runtime_libraries_live.py",
        ):
            read_live_summary_artifact(artifact_path)
    finally:
        LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"] = original_path
        LIVE_SUMMARY_SCRIPTS["local_runtime_cli_mcp_matrix"] = original_script

    with pytest.raises(
        ValueError,
        match="output_path must match registered artifact path: .*local_runtime_cli_mcp_matrix_live_summary.json",
    ):
        write_live_summary_artifact(
            output_path=LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"].with_name(
                "wrong_live_summary.json"
            ),
            suite_name="local_runtime_cli_mcp_matrix",
            script="tests/integration/test_cli_mcp_runtime_libraries_live.py",
            channels=("daemon_client", "runtime_local", "cli", "mcp"),
            minimum_passed=1,
            passed=1,
            failed=0,
            skipped=0,
            elapsed_seconds=1.0,
        )

    nested_artifact_path = artifact_path.parent / "nested" / artifact_path.name
    nested_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    original_path = LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"]
    LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"] = artifact_path
    try:
        nested_artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(
            ValueError,
            match="output_path must match registered artifact path: .*local_runtime_cli_mcp_matrix_live_summary.json",
        ):
            read_live_summary_artifact(nested_artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "not-a-timestamp",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="generated_at must be a UTC ISO-8601 string ending with Z"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00+00:00",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="generated_at must be a UTC ISO-8601 string ending with Z"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                    "bad": float("nan"),
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="extra must be JSON-serializable with finite values"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                    "minimum_passed": 1,
                    "passed": True,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="passed must be an integer, not boolean"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                    "minimum_passed": 1,
                    "passed": 1.5,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": 1.0,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="passed must be an integer"):
            read_live_summary_artifact(artifact_path)

        artifact_path.write_text(
            json.dumps(
                {
                    "artifact": "llm_rollout_live_summary",
                    "generated_at": "2026-05-25T00:00:00Z",
                    "name": "local_runtime_cli_mcp_matrix",
                    "script": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
                    "channels": ["daemon_client", "runtime_local", "cli", "mcp"],
                    "minimum_passed": 1,
                    "passed": 1,
                    "failed": 0,
                    "skipped": 0,
                    "elapsed_seconds": "1.25",
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="elapsed_seconds must be a finite number >= 0"):
            read_live_summary_artifact(artifact_path)
    finally:
        LIVE_SUMMARY_ARTIFACTS["local_runtime_cli_mcp_matrix"] = original_path
