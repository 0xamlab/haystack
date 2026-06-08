from __future__ import annotations

import json
from pathlib import Path

from tests.integration import test_mojo_libraries_az as az


def test_is_timeout_failure_only_matches_timeout_outputs() -> None:
    assert az._is_timeout_failure(("procurement", 0, 1, 30.0, "TIMEOUT after 30s"))
    assert not az._is_timeout_failure(("procurement", 12, 0, 3.0, ""))
    assert not az._is_timeout_failure(("procurement", 0, 1, 3.0, "Syntax error"))


def test_rerun_timeout_failures_replaces_only_timeout_results(monkeypatch, tmp_path: Path) -> None:
    timeout_result = ("procurement", 0, 1, 30.0, "TIMEOUT after 30s")
    non_timeout_failure = ("scoring", 0, 1, 2.0, "exit code 1")
    passing_result = ("semiconductors", 12, 0, 3.0, "")
    results = [passing_result, timeout_result, non_timeout_failure]

    calls: list[tuple[str, int]] = []
    test_file = tmp_path / "test_procurement.mojo"
    test_file.write_text("// placeholder")

    monkeypatch.setattr(az, "LIBS_DIR", tmp_path)
    monkeypatch.setattr(az, "RETRY_TIMEOUT", 60)

    def fake_run_library_test(path: Path, *, timeout: int) -> tuple[str, int, int, float, str]:
        calls.append((path.name, timeout))
        return ("procurement", 12, 0, 5.0, "")

    monkeypatch.setattr(az, "_run_library_test", fake_run_library_test)

    updated = az._rerun_timeout_failures(results)

    assert updated == [
        passing_result,
        ("procurement", 12, 0, 5.0, ""),
        non_timeout_failure,
    ]
    assert calls == [("test_procurement.mojo", 60)]


def test_write_summary_artifact_emits_machine_readable_runtime_totals(tmp_path: Path) -> None:
    output_path = tmp_path / "mojo_libraries_az_summary.json"
    results = [
        ("procurement", 12, 0, 1.2, ""),
        ("scoring", 10, 1, 2.3, "exit code 1"),
    ]

    summary = az._write_summary_artifact(
        results,
        suite_duration=3.5,
        output_path=output_path,
    )

    assert json.loads(output_path.read_text(encoding="utf-8")) == summary
    assert summary["library_count"] == 2
    assert summary["passed_library_count"] == 1
    assert summary["failed_library_count"] == 1
    assert summary["function_count"] == 23
    assert summary["passed_function_count"] == 22
    assert summary["failed_function_count"] == 1
    assert summary["suite_duration_s"] == 3.5
