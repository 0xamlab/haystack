"""Tests for test_repository_channel_parity_runner: validate_runtime.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-2/tests/test_repository_channel_parity_runner.py during modularization.
"""
from __future__ import annotations

from tests._test_repository_channel_parity_runner_helpers import *  # noqa: F401,F403


def test_validate_runtime_paths_accepts_default_build_paths() -> None:
    output_path, logs_dir = runner.validate_runtime_paths(
        output_path=runner.DEFAULT_OUTPUT_PATH,
        logs_dir=runner.DEFAULT_LOGS_DIR,
    )
    assert output_path == runner.DEFAULT_OUTPUT_PATH.resolve()
    assert logs_dir == runner.DEFAULT_LOGS_DIR.resolve()


def test_validate_runtime_paths_rejects_output_outside_build() -> None:
    try:
        runner.validate_runtime_paths(
            output_path=runner.ROOT / "tmp" / "parity.json",
            logs_dir=runner.DEFAULT_LOGS_DIR,
        )
    except ValueError as exc:
        assert str(exc) == f"output path must stay under build/: {runner.ROOT / 'tmp' / 'parity.json'}"
    else:
        raise AssertionError("expected output path outside build to fail")


def test_validate_runtime_paths_rejects_logs_dir_outside_build() -> None:
    try:
        runner.validate_runtime_paths(
            output_path=runner.DEFAULT_OUTPUT_PATH,
            logs_dir=runner.ROOT / "tmp" / "parity-logs",
        )
    except ValueError as exc:
        assert str(exc) == f"logs dir must stay under build/: {runner.ROOT / 'tmp' / 'parity-logs'}"
    else:
        raise AssertionError("expected logs dir outside build to fail")


def test_validate_runtime_paths_rejects_non_json_output() -> None:
    try:
        runner.validate_runtime_paths(
            output_path=runner.ROOT / "build" / "parity.txt",
            logs_dir=runner.DEFAULT_LOGS_DIR,
        )
    except ValueError as exc:
        assert str(exc) == f"output path must be a .json file: {runner.ROOT / 'build' / 'parity.txt'}"
    else:
        raise AssertionError("expected non-json output path to fail")


def test_validate_runtime_paths_rejects_logs_dir_equal_to_output_path() -> None:
    output_path = runner.ROOT / "build" / "parity.json"
    try:
        runner.validate_runtime_paths(
            output_path=output_path,
            logs_dir=output_path,
        )
    except ValueError as exc:
        assert str(exc) == f"logs dir must be distinct from output path: {output_path}"
    else:
        raise AssertionError("expected logs dir equal to output path to fail")


def test_validate_runtime_paths_rejects_repo_escape() -> None:
    try:
        runner.validate_runtime_paths(
            output_path=Path("../parity.json"),
            logs_dir=runner.DEFAULT_LOGS_DIR,
        )
    except ValueError as exc:
        assert str(exc) == "output path escapes repo root: ../parity.json"
    else:
        raise AssertionError("expected output path repo escape to fail")


def test_validate_runtime_surface_contract_accepts_current_defaults() -> None:
    runner.validate_runtime_surface_contract(
        channel_specs=runner.CHANNEL_SPECS,
        output_path=runner.DEFAULT_OUTPUT_PATH.resolve(),
        logs_dir=runner.DEFAULT_LOGS_DIR.resolve(),
    )


def test_validate_runtime_surface_contract_rejects_output_inside_logs_dir() -> None:
    logs_dir = runner.ROOT / "build" / "logs"
    try:
        runner.validate_runtime_surface_contract(
            channel_specs=runner.CHANNEL_SPECS,
            output_path=logs_dir / "parity.json",
            logs_dir=logs_dir,
        )
    except ValueError as exc:
        assert str(exc) == f"output path must stay outside logs dir: {logs_dir / 'parity.json'}"
    else:
        raise AssertionError("expected output inside logs dir to fail")


def test_validate_runtime_surface_contract_rejects_logs_dir_covering_summary_artifacts() -> None:
    logs_dir = runner.ROOT / "build"
    try:
        runner.validate_runtime_surface_contract(
            channel_specs=runner.CHANNEL_SPECS,
            output_path=runner.DEFAULT_OUTPUT_PATH.resolve(),
            logs_dir=logs_dir,
        )
    except ValueError as exc:
        assert str(exc) == f"logs dir must stay outside channel summary artifacts: {logs_dir}"
    else:
        raise AssertionError("expected logs dir covering summary artifacts to fail")


def test_validate_runtime_surface_contract_rejects_output_colliding_with_summary_artifact() -> None:
    summary_artifact_path = runner.ROOT / runner.CHANNEL_SPECS[0].summary_artifact
    try:
        runner.validate_runtime_surface_contract(
            channel_specs=runner.CHANNEL_SPECS,
            output_path=summary_artifact_path,
            logs_dir=runner.DEFAULT_LOGS_DIR.resolve(),
        )
    except ValueError as exc:
        assert (
            str(exc)
            == f"output path must stay distinct from channel summary artifacts: {summary_artifact_path}"
        )
    else:
        raise AssertionError("expected output path colliding with summary artifact to fail")


