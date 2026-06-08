"""Tests for test_go_live_verify: build_verification.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-1/tests/test_go_live_verify.py during modularization.
"""
from __future__ import annotations

from tests._test_go_live_verify_helpers import *  # noqa: F401,F403


def test_build_verification_steps_passes_tier_filter_only_to_connectivity() -> None:
    steps = build_verification_steps(
        "python-bin",
        parallel_tasks=4,
        mojo_workers=3,
        mojo_timeout=25,
        include_full_real=True,
        include_pytest=True,
        tiers=("credentialed_example",),
        connectors=("clickhouse",),
    )

    assert "--tiers" in steps[0].command
    assert "--connector" in steps[0].command
    assert steps[0].command[-4:] == (
        "--tiers",
        "credentialed_example",
        "--connector",
        "clickhouse",
    )
    assert "--tiers" not in steps[1].command
    assert "--tiers" not in steps[2].command
    assert "--connector" not in steps[1].command
    assert "--connector" not in steps[2].command


def test_build_verification_steps_keeps_serial_go_live_order() -> None:
    steps = build_verification_steps(
        "python-bin",
        parallel_tasks=4,
        mojo_workers=3,
        mojo_timeout=25,
        include_full_real=True,
        include_pytest=True,
        tiers=None,
        connectors=None,
    )
    assert [step.name for step in steps] == ["connectivity", "full_real", "pytest"]
    assert steps[0].command[-2:] == ("--parallel-tasks", "4")
    assert steps[1].command[-4:] == ("--mojo-workers", "3", "--mojo-timeout", "25")
    assert steps[2].command == ("python-bin", "-m", "pytest", "tests", "-q")


def test_build_verification_steps_supports_connectivity_only_runs() -> None:
    steps = build_verification_steps(
        "python-bin",
        parallel_tasks=4,
        mojo_workers=3,
        mojo_timeout=25,
        include_full_real=False,
        include_pytest=False,
        tiers=("credentialed_example",),
        connectors=("clickhouse",),
    )

    assert [step.name for step in steps] == ["connectivity"]
    assert steps[0].command[-4:] == (
        "--tiers",
        "credentialed_example",
        "--connector",
        "clickhouse",
    )


def test_build_verification_metadata_captures_filters_and_options(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "go_live_verify_summary.json"
    monkeypatch.setattr("tests.go_live_verify.time.strftime", lambda fmt, now: "2026-05-22T02:20:00Z")

    metadata = build_verification_metadata(
        python_executable="python-bin",
        output_path=output_path,
        selected_tiers=("credentialed_example",),
        selected_connectors=("clickhouse", "snowflake"),
        include_full_real=False,
        include_pytest=True,
        require_all_configured=True,
        require_all_behavior_ready=False,
        strict=False,
    )

    assert metadata == {
        "generated_at": "2026-05-22T02:20:00Z",
        "python_executable": "python-bin",
        "output_path": str(output_path),
        "filters": {
            "tiers": ["credentialed_example"],
            "connectors": ["clickhouse", "snowflake"],
        },
        "options": {
            "include_full_real": False,
            "include_pytest": True,
            "require_all_configured": True,
            "require_all_behavior_ready": False,
            "strict": False,
        },
    }


