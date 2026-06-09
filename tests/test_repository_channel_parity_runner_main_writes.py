"""Tests for test_repository_channel_parity_runner: main_writes.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-2/tests/test_repository_channel_parity_runner.py during modularization.
"""
from __future__ import annotations

from tests._test_repository_channel_parity_runner_helpers import *  # noqa: F401,F403


def test_main_writes_failed_summary_on_unexpected_runner_exception(
    monkeypatch, tmp_path: Path
) -> None:
    output_path = tmp_path / "parity.json"
    logs_dir = tmp_path / "logs"

    monkeypatch.setattr(
        runner,
        "parse_args",
        lambda argv=None: SimpleNamespace(
            filter="repository",
            output=str(output_path),
            logs_dir=str(logs_dir),
            jobs=1,
        ),
    )
    monkeypatch.setattr(runner, "validate_runtime_paths", lambda **kwargs: (output_path, logs_dir))
    monkeypatch.setattr(
        runner,
        "run_channel_specs",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("fatal boom")),
    )

    exit_code = runner.main([])
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["fatal_error"] == "fatal boom"


def test_main_writes_failed_summary_on_invalid_jobs_and_replaces_stale_output(
    monkeypatch, tmp_path: Path
) -> None:
    output_path = tmp_path / "parity.json"
    output_path.write_text("stale", encoding="utf-8")
    logs_dir = tmp_path / "logs"

    monkeypatch.setattr(
        runner,
        "parse_args",
        lambda argv=None: SimpleNamespace(
            filter="repository",
            output=str(output_path),
            logs_dir=str(logs_dir),
            jobs=0,
        ),
    )
    monkeypatch.setattr(runner, "validate_runtime_paths", lambda **kwargs: (output_path, logs_dir))

    exit_code = runner.main([])
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["fatal_error"] == "jobs must be >= 1, got 0"


def test_main_writes_failed_summary_on_invalid_runtime_paths(
    monkeypatch, tmp_path: Path
) -> None:
    output_path = tmp_path / "outside" / "parity.json"
    logs_dir = tmp_path / "outside" / "logs"
    default_output_path = tmp_path / "build" / "repository_intelligence_channel_parity_summary.json"
    default_logs_dir = tmp_path / "build" / "repository_intelligence_channel_parity_logs"

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        runner,
        "parse_args",
        lambda argv=None: SimpleNamespace(
            filter="repository",
            output=str(output_path),
            logs_dir=str(logs_dir),
            jobs=1,
        ),
    )
    monkeypatch.setattr(runner, "DEFAULT_OUTPUT_PATH", default_output_path)
    monkeypatch.setattr(runner, "DEFAULT_LOGS_DIR", default_logs_dir)

    exit_code = runner.main([])
    payload = json.loads(default_output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["fatal_error"] == f"output path must stay under build/: {output_path}"
    assert payload["output_path"] == str(default_output_path.resolve())
    assert payload["logs_dir"] == str(default_logs_dir.resolve())
    assert not output_path.exists()


