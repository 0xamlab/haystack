from __future__ import annotations

import json

from benchmarks import scorecard_suite_summaries


def test_parse_pytest_summary_extracts_counts() -> None:
    output = """
======================== 14 passed, 2 skipped in 0.38s ========================
"""

    summary = scorecard_suite_summaries._parse_pytest_summary(output)

    assert summary.passed == 14
    assert summary.failed == 0
    assert summary.skipped == 2
    assert summary.total == 16


def test_build_suite_summaries_uses_machine_readable_counts(monkeypatch) -> None:
    monkeypatch.setattr(
        scorecard_suite_summaries,
        "_run_pytest_suite",
        lambda paths: scorecard_suite_summaries.PytestSummary(
            passed=len(paths),
            failed=0,
            skipped=0,
            total=len(paths),
        ),
    )
    monkeypatch.setattr(
        scorecard_suite_summaries,
        "_compute_hospitality_accuracy",
        lambda: {"correct": 12, "total": 12, "percentage": 100.0},
    )

    payload = scorecard_suite_summaries.build_suite_summaries()

    assert payload["narrow_resolver_regression"]["accuracy"] == {
        "correct": 12,
        "total": 12,
        "percentage": 100.0,
    }
    assert payload["narrow_resolver_regression"]["regression_suite"] == {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "total": 1,
    }
    assert payload["join_path_correctness"] == {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "total": 1,
    }
    assert payload["import_planner_regression_suite"] == {
        "passed": 4,
        "failed": 0,
        "skipped": 0,
        "total": 4,
    }
    assert "generated_at" in payload


def test_main_writes_summary_artifact(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(scorecard_suite_summaries, "OUTPUT_PATH", tmp_path / "summary.json")
    monkeypatch.setattr(
        scorecard_suite_summaries,
        "build_suite_summaries",
        lambda: {"generated_at": "2026-05-23T20:00:00+00:00", "ok": True},
    )

    assert scorecard_suite_summaries.main() == 0
    assert json.loads((tmp_path / "summary.json").read_text()) == {
        "generated_at": "2026-05-23T20:00:00+00:00",
        "ok": True,
    }
