"""Tests for test_go_live_verify: build_verification.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-1/tests/test_go_live_verify.py during modularization.
"""
from __future__ import annotations

from pathlib import Path

from tests._test_go_live_verify_helpers import (
    ROOT,
    VerificationStep,
    build_go_live_runtime_worker_env,
    build_verification_metadata,
    build_verification_steps,
    run_verification_steps,
)


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




def test_build_go_live_runtime_worker_env_skips_connectivity_only() -> None:
    assert build_go_live_runtime_worker_env(
        include_full_real=False,
        include_pytest=False,
    ) == {}


def test_build_go_live_runtime_worker_env_preflights_shared_worker(monkeypatch) -> None:
    sentinel_worker = Path("/tmp/algenta-worker")

    monkeypatch.setattr(
        "tests.integration.test_go_live_full_real._ensure_go_live_runtime_worker",
        lambda: sentinel_worker,
    )
    monkeypatch.setattr(
        "tests.integration.test_go_live_full_real._runtime_worker_env",
        lambda worker_path: {"ALGENTA_NATIVE_WORKER": str(worker_path)},
    )

    assert build_go_live_runtime_worker_env(
        include_full_real=False,
        include_pytest=True,
    ) == {"ALGENTA_NATIVE_WORKER": str(sentinel_worker)}


def test_run_verification_steps_passes_env_overrides(monkeypatch) -> None:
    captured_env: dict[str, str] = {}

    class FakeStdout:
        def __iter__(self):
            return iter(("child output\n",))

        def close(self) -> None:
            return None

    class FakeProcess:
        stdout = FakeStdout()

        def wait(self) -> int:
            return 0

    def fake_popen(command, *, cwd, env, stdout, stderr, text, bufsize):
        del command, cwd, stdout, stderr, text, bufsize
        captured_env.update(env)
        return FakeProcess()

    monkeypatch.setattr("tests.go_live_verify.subprocess.Popen", fake_popen)

    result = run_verification_steps(
        [VerificationStep(name="probe", command=("python-bin", "probe.py"))],
        env_overrides={"ALGENTA_NATIVE_WORKER": "/tmp/worker"},
    )

    assert result[0].name == "probe"
    assert result[0].returncode == 0
    assert result[0].output == "child output\n"
    assert captured_env["PYTHONPATH"] == str(ROOT)
    assert captured_env["ALGENTA_NATIVE_WORKER"] == "/tmp/worker"
