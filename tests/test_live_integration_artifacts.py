from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration import live_integration_artifacts as artifacts


def test_live_integration_summary_artifacts_cover_root_live_scripts() -> None:
    expected_subset = {
        "algenta_client_live": Path("build/algenta_client_live_summary.json").resolve(),
        "algenta_runtime_live": Path("build/algenta_runtime_live_summary.json").resolve(),
        "cli_integration": Path("build/cli_integration_summary.json").resolve(),
        "go_live_connectivity_local_only": Path(
            "build/go_live_connectivity_local_only_summary.json"
        ).resolve(),
        "go_live_connectivity_real": Path("build/go_live_connectivity_real_summary.json").resolve(),
        "go_live_full_real": Path("build/go_live_full_real_summary.json").resolve(),
        "local_runtime_real": Path("build/local_runtime_real_summary.json").resolve(),
        "mcp_runtime_live": Path("build/mcp_runtime_live_summary.json").resolve(),
        "mcp_server_integration": Path("build/mcp_server_integration_summary.json").resolve(),
        "openapi_integration": Path("build/openapi_integration_summary.json").resolve(),
        "python_sdk_integration": Path("build/python_sdk_integration_summary.json").resolve(),
        "services_integration": Path("build/services_integration_summary.json").resolve(),
        "typescript_sdk_client_live": Path("build/typescript_sdk_client_live_summary.json").resolve(),
    }
    for name, expected_path in expected_subset.items():
        assert artifacts.LIVE_INTEGRATION_SUMMARY_ARTIFACTS[name] == expected_path

    expected_scripts_subset = {
        "algenta_client_live": "tests/integration/test_algenta_client_live.py",
        "cli_integration": "tests/integration/test_cli.py",
        "go_live_connectivity_local_only": "tests/integration/test_go_live_connectivity_real.py",
        "go_live_connectivity_real": "tests/integration/test_go_live_connectivity_real.py",
        "go_live_full_real": "tests/integration/test_go_live_full_real.py",
        "mcp_runtime_live": "tests/integration/test_mcp_runtime_live.py",
        "mcp_server_integration": "tests/integration/test_mcp_server.py",
        "services_integration": "tests/integration/test_services.py",
        "typescript_sdk_client_live": "tests/integration/test_typescript_sdk_client_live.py",
    }
    for name, expected_script in expected_scripts_subset.items():
        assert artifacts.LIVE_INTEGRATION_SUMMARY_SCRIPTS[name] == expected_script


def test_write_live_integration_summary_round_trip(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "mcp_server_integration_summary.json"
    monkeypatch.setattr(
        artifacts,
        "LIVE_INTEGRATION_SUMMARY_ARTIFACTS",
        {"mcp_server_integration": output_path},
    )

    written = artifacts.write_live_integration_summary(
        "mcp_server_integration",
        script="tests/integration/test_mcp_server.py",
        passed=39,
        failed=0,
        skipped=3,
        total=42,
        elapsed_seconds=2.3456,
        details={"runtime_proof_tool_count": 5},
    )

    assert written == output_path
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["artifact"] == "live_integration_summary"
    assert payload["name"] == "mcp_server_integration"
    assert payload["script"] == "tests/integration/test_mcp_server.py"
    assert payload["passed"] == 39
    assert payload["failed"] == 0
    assert payload["skipped"] == 3
    assert payload["total"] == 42
    assert payload["elapsed_seconds"] == 2.346
    assert payload["details"] == {"runtime_proof_tool_count": 5}
    assert payload["generated_at"].endswith("Z")


def test_write_live_integration_summary_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="unknown live integration summary name"):
        artifacts.write_live_integration_summary(
            "unknown_suite",
            script="tests/integration/unknown.py",
            passed=1,
            failed=0,
            total=1,
            elapsed_seconds=1.0,
        )

    with pytest.raises(
        ValueError,
        match="output_path must match registered artifact path: .*mcp_server_integration_summary.json",
    ):
        artifacts._coerce_registered_output_path(
            "mcp_server_integration",
            Path("/tmp/mcp_server_integration_summary.json"),
        )


def test_write_live_integration_summary_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError, match="total must equal passed \\+ failed \\+ skipped"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=3,
            failed=0,
            skipped=1,
            total=3,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="skipped must be >= 0"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=3,
            failed=0,
            skipped=-1,
            total=2,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="passed must be an integer, not boolean"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=True,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="passed must be an integer"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=1.5,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="elapsed_seconds must be a finite number >= 0"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=-0.1,
        )

    with pytest.raises(ValueError, match="elapsed_seconds must be a finite number >= 0"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=False,
        )

    with pytest.raises(ValueError, match="elapsed_seconds must be a finite number >= 0"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds="1.25",
        )


def test_write_live_integration_summary_rejects_invalid_script_path() -> None:
    with pytest.raises(ValueError, match="script must be a tests/integration/\\*\\.py path"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script=123,
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=1.0,
        )

    with pytest.raises(ValueError, match="script must be a tests/integration/\\*\\.py path"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="apps/cli/main.py",
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=1.0,
        )

    with pytest.raises(
        ValueError,
        match="script must match registered suite script: tests/integration/test_mcp_server.py",
    ):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_cli.py",
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=1.0,
        )


def test_write_live_integration_summary_rejects_invalid_details_payload() -> None:
    with pytest.raises(ValueError, match="details must use only string keys"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=1.0,
            details={1: "bad"},
        )

    with pytest.raises(ValueError, match="details must use only string keys"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=1.0,
            details={"nested": [{1: "bad"}]},
        )

    with pytest.raises(ValueError, match="details must not contain tuples"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=1.0,
            details={"nested": ("bad", "tuple")},
        )

    with pytest.raises(ValueError, match="details must be JSON-serializable with finite values"):
        artifacts.write_live_integration_summary(
            "mcp_server_integration",
            script="tests/integration/test_mcp_server.py",
            passed=1,
            failed=0,
            skipped=0,
            total=1,
            elapsed_seconds=1.0,
            details={"bad": float("nan")},
        )


def test_read_live_integration_summary_round_trip(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "mcp_server_integration_summary.json"
    monkeypatch.setattr(
        artifacts,
        "LIVE_INTEGRATION_SUMMARY_ARTIFACTS",
        {"mcp_server_integration": output_path},
    )
    artifacts.write_live_integration_summary(
        "mcp_server_integration",
        script="tests/integration/test_mcp_server.py",
        passed=2,
        failed=0,
        skipped=1,
        total=3,
        elapsed_seconds=1.25,
        details={"runtime_proof_tool_count": 5},
    )

    loaded = artifacts.read_live_integration_summary(output_path)
    assert loaded["name"] == "mcp_server_integration"
    assert loaded["script"] == "tests/integration/test_mcp_server.py"
    assert loaded["generated_at"].endswith("Z")
    assert loaded["passed"] == 2
    assert loaded["failed"] == 0
    assert loaded["skipped"] == 1
    assert loaded["total"] == 3
    assert loaded["elapsed_seconds"] == 1.25


def test_read_live_integration_summary_rejects_malformed_payload(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "mcp_server_integration_summary.json"
    monkeypatch.setattr(
        artifacts,
        "LIVE_INTEGRATION_SUMMARY_ARTIFACTS",
        {"mcp_server_integration": output_path},
    )
    output_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        artifacts.read_live_integration_summary(output_path)

    output_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "name": "mcp_server_integration",
                "script": "tests/integration/test_mcp_server.py",
                "passed": 1,
                "failed": 0,
                "skipped": 1,
                "total": 1,
                "elapsed_seconds": 1.0,
                "details": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="live integration summary total must equal passed \\+ failed \\+ skipped"):
        artifacts.read_live_integration_summary(output_path)

    output_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "name": "mcp_server_integration",
                "script": "tests/integration/test_cli.py",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "elapsed_seconds": 1.0,
                "details": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="script must match registered suite script: tests/integration/test_mcp_server.py",
    ):
        artifacts.read_live_integration_summary(output_path)

    output_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "generated_at": "2026-05-25T00:00:00Z",
                "name": "mcp_server_integration",
                "script": 123,
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "elapsed_seconds": 1.0,
                "details": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="script must be a tests/integration/\\*\\.py path"):
        artifacts.read_live_integration_summary(output_path)

    wrong_dir_path = tmp_path / "nested" / "mcp_server_integration_summary.json"
    wrong_dir_path.parent.mkdir(parents=True, exist_ok=True)
    wrong_dir_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "name": "mcp_server_integration",
                "script": "tests/integration/test_mcp_server.py",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "elapsed_seconds": 1.0,
                "details": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="output_path must match registered artifact path: .*mcp_server_integration_summary.json",
    ):
        artifacts.read_live_integration_summary(wrong_dir_path)

    output_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "generated_at": "not-a-timestamp",
                "name": "mcp_server_integration",
                "script": "tests/integration/test_mcp_server.py",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "elapsed_seconds": 1.0,
                "details": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="generated_at must be a UTC ISO-8601 string ending with Z"):
        artifacts.read_live_integration_summary(output_path)

    output_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "generated_at": "2026-05-25T00:00:00Z",
                "name": "mcp_server_integration",
                "script": "tests/integration/test_mcp_server.py",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "elapsed_seconds": 1.0,
                "details": {},
                "forged": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="live integration summary contains unexpected top-level keys: forged",
    ):
        artifacts.read_live_integration_summary(output_path)

    output_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "generated_at": "2026-05-25T00:00:00Z",
                "name": "mcp_server_integration",
                "script": "tests/integration/test_mcp_server.py",
                "passed": True,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "elapsed_seconds": 1.0,
                "details": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="passed must be an integer, not boolean"):
        artifacts.read_live_integration_summary(output_path)

    output_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "generated_at": "2026-05-25T00:00:00Z",
                "name": "mcp_server_integration",
                "script": "tests/integration/test_mcp_server.py",
                "passed": 1.5,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "elapsed_seconds": 1.0,
                "details": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="passed must be an integer"):
        artifacts.read_live_integration_summary(output_path)

    output_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "generated_at": "2026-05-25T00:00:00Z",
                "name": "mcp_server_integration",
                "script": "tests/integration/test_mcp_server.py",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "elapsed_seconds": "1.25",
                "details": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="elapsed_seconds must be a finite number >= 0"):
        artifacts.read_live_integration_summary(output_path)


    output_path.write_text(
        json.dumps(
            {
                "artifact": "live_integration_summary",
                "generated_at": "2026-05-25T00:00:00+00:00",
                "name": "mcp_server_integration",
                "script": "tests/integration/test_mcp_server.py",
                "passed": 1,
                "failed": 0,
                "skipped": 0,
                "total": 1,
                "elapsed_seconds": 1.0,
                "details": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="generated_at must be a UTC ISO-8601 string ending with Z"):
        artifacts.read_live_integration_summary(output_path)
