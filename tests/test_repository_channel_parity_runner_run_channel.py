"""Tests for test_repository_channel_parity_runner: run_channel.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-2/tests/test_repository_channel_parity_runner.py during modularization.
"""
from __future__ import annotations

from tests._test_repository_channel_parity_runner_helpers import *  # noqa: F401,F403


def test_run_channel_specs_converts_unexpected_channel_exception_to_failed_result(
    monkeypatch, tmp_path: Path
) -> None:
    fake_root = tmp_path
    logs_dir = fake_root / "logs"
    spec = runner.ChannelSpec(name="python_sdk", script="a.py", summary_artifact="a.json")

    def _boom(spec, *, filter_value, logs_dir):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(runner, "ROOT", fake_root)
    monkeypatch.setattr(runner, "run_channel_spec", _boom)

    results = runner.run_channel_specs(
        channel_specs=(spec,),
        filter_value="repository",
        logs_dir=logs_dir,
        jobs=1,
    )

    assert len(results) == 1
    result = results[0]
    assert result.status == "failed"
    assert result.summary_counts is None
    assert result.return_code == 1
    assert result.error == "unexpected runner exception: boom"
    assert (logs_dir / "python_sdk.log").read_text(encoding="utf-8") == (
        "unexpected runner exception: boom\n"
    )


def test_run_channel_spec_writes_log_and_loads_summary(monkeypatch, tmp_path: Path) -> None:
    fake_root = tmp_path
    logs_dir = fake_root / "logs"
    summary_path = fake_root / "build" / "python_sdk_integration_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    def _fake_run(command, cwd, env, capture_output, text):  # noqa: ANN001
        assert command == [str(fake_root / "scripts" / "run_repo_python.sh"), "tests/integration/test_python_sdk.py"]
        assert cwd == str(fake_root)
        assert env["ALGENTA_LIVE_CHECK_FILTER"] == "repository"
        assert capture_output is True
        assert text is True
        summary_path.write_text(
            json.dumps(
                {
                    "passed": 2,
                    "failed": 0,
                    "skipped": 43,
                    "total": 45,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="python-sdk-ok\n", stderr="")

    monkeypatch.setattr(runner, "ROOT", fake_root)
    monkeypatch.setattr(runner, "RUN_REPO_PYTHON", fake_root / "scripts" / "run_repo_python.sh")
    monkeypatch.setattr(runner.subprocess, "run", _fake_run)

    result = runner.run_channel_spec(
        runner.ChannelSpec(
            name="python_sdk",
            script="tests/integration/test_python_sdk.py",
            summary_artifact="build/python_sdk_integration_summary.json",
        ),
        filter_value="repository",
        logs_dir=logs_dir,
    )

    assert result.status == "passed"
    assert result.summary_counts == runner.ChannelSummaryCounts(
        passed=2,
        failed=0,
        skipped=43,
        total=45,
    )
    assert result.log_artifact == "logs/python_sdk.log"
    assert (logs_dir / "python_sdk.log").read_text(encoding="utf-8") == "python-sdk-ok\n"


def test_run_channel_spec_rejects_stale_summary_artifact(monkeypatch, tmp_path: Path) -> None:
    fake_root = tmp_path
    logs_dir = fake_root / "logs"
    summary_path = fake_root / "build" / "python_sdk_integration_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "passed": 99,
                "failed": 0,
                "skipped": 0,
                "total": 99,
                "status": "passed",
            }
        ),
        encoding="utf-8",
    )

    def _fake_run(command, cwd, env, capture_output, text):  # noqa: ANN001
        assert command == [str(fake_root / "scripts" / "run_repo_python.sh"), "tests/integration/test_python_sdk.py"]
        assert cwd == str(fake_root)
        assert env["ALGENTA_LIVE_CHECK_FILTER"] == "repository"
        assert capture_output is True
        assert text is True
        assert not summary_path.exists()
        return SimpleNamespace(returncode=0, stdout="python-sdk-ok\n", stderr="")

    monkeypatch.setattr(runner, "ROOT", fake_root)
    monkeypatch.setattr(runner, "RUN_REPO_PYTHON", fake_root / "scripts" / "run_repo_python.sh")
    monkeypatch.setattr(runner.subprocess, "run", _fake_run)

    result = runner.run_channel_spec(
        runner.ChannelSpec(
            name="python_sdk",
            script="tests/integration/test_python_sdk.py",
            summary_artifact="build/python_sdk_integration_summary.json",
        ),
        filter_value="repository",
        logs_dir=logs_dir,
    )

    assert result.status == "failed"
    assert result.summary_counts is None
    assert result.error == f"missing summary artifact: {summary_path}"


def test_run_channel_spec_rejects_repository_count_drift(
    monkeypatch, tmp_path: Path
) -> None:
    fake_root = tmp_path
    logs_dir = fake_root / "logs"
    summary_path = fake_root / "build" / "python_sdk_integration_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    def _fake_run(command, cwd, env, capture_output, text):  # noqa: ANN001
        assert command == [str(fake_root / "scripts" / "run_repo_python.sh"), "tests/integration/test_python_sdk.py"]
        assert cwd == str(fake_root)
        assert env["ALGENTA_LIVE_CHECK_FILTER"] == "repository"
        assert capture_output is True
        assert text is True
        summary_path.write_text(
            json.dumps(
                {
                    "passed": 1,
                    "failed": 0,
                    "skipped": 44,
                    "total": 45,
                    "status": "passed",
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="python-sdk-ok\n", stderr="")

    monkeypatch.setattr(runner, "ROOT", fake_root)
    monkeypatch.setattr(runner, "RUN_REPO_PYTHON", fake_root / "scripts" / "run_repo_python.sh")
    monkeypatch.setattr(runner.subprocess, "run", _fake_run)

    result = runner.run_channel_spec(
        runner.ChannelSpec(
            name="python_sdk",
            script="tests/integration/test_python_sdk.py",
            summary_artifact="build/python_sdk_integration_summary.json",
            expected_repository_counts=runner.ChannelSummaryCounts(
                passed=2,
                failed=0,
                skipped=43,
                total=45,
            ),
        ),
        filter_value="repository",
        logs_dir=logs_dir,
    )

    assert result.status == "failed"
    assert result.summary_counts is None
    assert "python_sdk expected repository counts" in result.error


def test_run_channel_specs_preserves_channel_order(monkeypatch, tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    specs = (
        runner.ChannelSpec(name="first", script="a.py", summary_artifact="a.json"),
        runner.ChannelSpec(name="second", script="b.py", summary_artifact="b.json"),
    )
    run_order: list[str] = []

    class FakeFuture:
        def __init__(self, value: runner.ChannelRunResult) -> None:
            self._value = value

        def result(self) -> runner.ChannelRunResult:
            return self._value

    class FakeExecutor:
        def __init__(self, *, max_workers: int) -> None:
            assert max_workers == 2

        def __enter__(self) -> FakeExecutor:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        def submit(self, fn, spec, *, filter_value, logs_dir):  # noqa: ANN001
            result = fn(spec, filter_value=filter_value, logs_dir=logs_dir)
            return FakeFuture(result)

    def _fake_run_channel_spec(spec, *, filter_value, logs_dir):  # noqa: ANN001
        assert filter_value == "repository"
        assert logs_dir == logs_dir_arg
        run_order.append(spec.name)
        return runner.ChannelRunResult(
            name=spec.name,
            script=spec.script,
            summary_artifact=spec.summary_artifact,
            log_artifact=f"logs/{spec.name}.log",
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        )

    def _fake_as_completed(futures):  # noqa: ANN001
        return list(reversed(list(futures)))

    logs_dir_arg = logs_dir
    monkeypatch.setattr(runner, "ThreadPoolExecutor", FakeExecutor)
    monkeypatch.setattr(runner, "as_completed", _fake_as_completed)
    monkeypatch.setattr(runner, "run_channel_spec", _fake_run_channel_spec)

    results = runner.run_channel_specs(
        channel_specs=specs,
        filter_value="repository",
        logs_dir=logs_dir_arg,
        jobs=2,
    )

    assert run_order == ["first", "second"]
    assert [result.name for result in results] == ["first", "second"]


def test_run_channel_specs_serial_path_skips_executor(monkeypatch, tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    specs = (
        runner.ChannelSpec(name="first", script="a.py", summary_artifact="a.json"),
        runner.ChannelSpec(name="second", script="b.py", summary_artifact="b.json"),
    )
    run_order: list[str] = []

    def _unexpected_executor(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("ThreadPoolExecutor should not be used for serial parity runs")

    def _fake_run_channel_spec_safe(spec, *, filter_value, logs_dir):  # noqa: ANN001
        assert filter_value == "repository"
        assert logs_dir == logs_dir_arg
        run_order.append(spec.name)
        return runner.ChannelRunResult(
            name=spec.name,
            script=spec.script,
            summary_artifact=spec.summary_artifact,
            log_artifact=f"logs/{spec.name}.log",
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        )

    logs_dir_arg = logs_dir
    monkeypatch.setattr(runner, "ThreadPoolExecutor", _unexpected_executor)
    monkeypatch.setattr(runner, "_run_channel_spec_safe", _fake_run_channel_spec_safe)

    results = runner.run_channel_specs(
        channel_specs=specs,
        filter_value="repository",
        logs_dir=logs_dir_arg,
        jobs=1,
    )

    assert run_order == ["first", "second"]
    assert [result.name for result in results] == ["first", "second"]


