"""Tests for test_repository_channel_parity_runner: load_channel.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-2/tests/test_repository_channel_parity_runner.py during modularization.
"""
from __future__ import annotations

from tests._test_repository_channel_parity_runner_helpers import *  # noqa: F401,F403


def test_load_channel_summary_counts_accepts_valid_payload(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_text(
        json.dumps(
            {
                "passed": 1,
                "failed": 0,
                "skipped": 3,
                "total": 4,
            }
        ),
        encoding="utf-8",
    )
    counts = runner.load_channel_summary_counts(path)
    assert counts == runner.ChannelSummaryCounts(passed=1, failed=0, skipped=3, total=4)


def test_load_channel_summary_counts_rejects_invalid_shape(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_text(
        json.dumps(
            {
                "passed": True,
                "failed": 0,
                "skipped": 0,
                "total": 1,
            }
        ),
        encoding="utf-8",
    )
    try:
        runner.load_channel_summary_counts(path)
    except ValueError as exc:
        assert "invalid passed" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid summary counts")


def test_load_channel_summary_counts_infers_total_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_text(
        json.dumps(
            {
                "passed": 1,
                "failed": 0,
                "skipped": 14,
            }
        ),
        encoding="utf-8",
    )
    counts = runner.load_channel_summary_counts(path)
    assert counts == runner.ChannelSummaryCounts(passed=1, failed=0, skipped=14, total=15)


def test_load_channel_summary_counts_rejects_inconsistent_total(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_text(
        json.dumps(
            {
                "passed": 1,
                "failed": 0,
                "skipped": 14,
                "total": 99,
            }
        ),
        encoding="utf-8",
    )
    try:
        runner.load_channel_summary_counts(path)
    except ValueError as exc:
        assert "inconsistent total" in str(exc)
    else:
        raise AssertionError("expected ValueError for inconsistent summary total")


def test_load_channel_summary_counts_rejects_non_passing_status(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_text(
        json.dumps(
            {
                "passed": 1,
                "failed": 0,
                "skipped": 14,
                "status": "failed",
            }
        ),
        encoding="utf-8",
    )
    try:
        runner.load_channel_summary_counts(path)
    except ValueError as exc:
        assert "non-passing status" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-passing source status")


