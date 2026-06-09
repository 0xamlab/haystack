"""Tests for test_repository_channel_parity_runner: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-2/tests/test_repository_channel_parity_runner.py during modularization.
"""
from __future__ import annotations

from tests._test_repository_channel_parity_runner_helpers import *  # noqa: F401,F403


def test_parse_args_accepts_jobs_override() -> None:
    args = runner.parse_args(["--jobs", "5"])
    assert args.jobs == 5


def test_effective_jobs_clamps_repository_filter_to_serial() -> None:
    assert runner.effective_jobs(filter_value="repository", requested_jobs=5) == 1
    assert runner.effective_jobs(filter_value="other", requested_jobs=5) == 5


def test_resolve_fatal_runtime_paths_falls_back_to_defaults(monkeypatch, tmp_path: Path) -> None:
    default_output_path = tmp_path / "build" / "parity.json"
    default_logs_dir = tmp_path / "build" / "logs"
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "DEFAULT_OUTPUT_PATH", default_output_path)
    monkeypatch.setattr(runner, "DEFAULT_LOGS_DIR", default_logs_dir)

    output_path, logs_dir = runner.resolve_fatal_runtime_paths(
        output_path=Path("../parity.json"),
        logs_dir=Path("../logs"),
    )

    assert output_path == default_output_path.resolve()
    assert logs_dir == default_logs_dir.resolve()


def test_expected_repository_aggregate_counts_sums_channel_contracts() -> None:
    counts = runner.expected_repository_aggregate_counts(runner.CHANNEL_SPECS)
    assert counts == runner.ChannelSummaryCounts(
        passed=8,
        failed=0,
        skipped=210,
        total=218,
    )


def test_build_parity_summary_reports_channel_statuses(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    python_spec = runner.ChannelSpec(
        name="python_sdk",
        script="tests/integration/test_python_sdk.py",
        summary_artifact="build/python_sdk_integration_summary.json",
        expected_repository_counts=runner.ChannelSummaryCounts(
            passed=2,
            failed=0,
            skipped=43,
            total=45,
        ),
    )
    cli_spec = runner.ChannelSpec(
        name="cli",
        script="tests/integration/test_cli.py",
        summary_artifact="build/cli_integration_summary.json",
        expected_repository_counts=runner.ChannelSummaryCounts(
            passed=1,
            failed=0,
            skipped=42,
            total=43,
        ),
    )
    results = [
        runner.ChannelRunResult(
            name=python_spec.name,
            script=python_spec.script,
            summary_artifact=python_spec.summary_artifact,
            log_artifact=_expected_log_artifact(spec=python_spec, logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.2,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(
                passed=2,
                failed=0,
                skipped=43,
                total=45,
            ),
        ),
        runner.ChannelRunResult(
            name=cli_spec.name,
            script=cli_spec.script,
            summary_artifact=cli_spec.summary_artifact,
            log_artifact=_expected_log_artifact(spec=cli_spec, logs_dir=logs_dir),
            return_code=1,
            elapsed_seconds=0.8,
            status="failed",
            summary_counts=None,
            error="channel proof failed",
        ),
    ]
    payload = runner.build_parity_summary(
        filter_value="repository",
        channel_specs=(python_spec, cli_spec),
        results=results,
        elapsed_seconds=3.4,
        output_path=tmp_path / "parity.json",
        logs_dir=logs_dir,
    )
    assert payload["artifact"] == "repository_intelligence_channel_parity_summary"
    assert payload["filter"] == "repository"
    assert payload["status"] == "failed"
    assert payload["passed_channels"] == 1
    assert payload["failed_channels"] == 1
    assert payload["total_channels"] == 2
    assert payload["aggregate_passed_checks"] == 2
    assert payload["aggregate_failed_checks"] == 0
    assert payload["aggregate_skipped_checks"] == 43
    assert payload["aggregate_total_checks"] == 45
    assert payload["contract"]["status"] == "failed"
    assert payload["contract"]["actual_aggregate_counts"] == {
        "passed": 2,
        "failed": 0,
        "skipped": 43,
        "total": 45,
    }
    assert payload["channels"][0]["summary_counts"]["passed"] == 2
    assert payload["channels"][0]["log_artifact"].endswith("python_sdk.log")
    assert payload["channels"][1]["error"] == "channel proof failed"


def test_validate_parity_summary_contract_rejects_aggregate_drift(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    python_spec = runner.ChannelSpec(
        name="python_sdk",
        script="tests/integration/test_python_sdk.py",
        summary_artifact="build/python_sdk_integration_summary.json",
        expected_repository_counts=runner.ChannelSummaryCounts(
            passed=2,
            failed=0,
            skipped=43,
            total=45,
        ),
    )
    results = [
        runner.ChannelRunResult(
            name=python_spec.name,
            script=python_spec.script,
            summary_artifact=python_spec.summary_artifact,
            log_artifact=_expected_log_artifact(spec=python_spec, logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.2,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(
                passed=2,
                failed=0,
                skipped=42,
                total=44,
            ),
        )
    ]
    payload = runner.build_parity_summary(
        filter_value="repository",
        channel_specs=(python_spec,),
        results=results,
        elapsed_seconds=3.4,
        output_path=tmp_path / "parity.json",
        logs_dir=logs_dir,
    )
    try:
        runner.validate_parity_summary_contract(
            filter_value="repository",
            channel_specs=(python_spec,),
            payload=payload,
        )
    except ValueError as exc:
        assert "aggregate repository parity counts drifted" in str(exc)
    else:
        raise AssertionError("expected ValueError for aggregate parity drift")


def test_finalize_parity_summary_contract_writes_failed_payload_on_drift(
    tmp_path: Path,
) -> None:
    logs_dir = tmp_path / "logs"
    python_spec = runner.ChannelSpec(
        name="python_sdk",
        script="tests/integration/test_python_sdk.py",
        summary_artifact="build/python_sdk_integration_summary.json",
        expected_repository_counts=runner.ChannelSummaryCounts(
            passed=2,
            failed=0,
            skipped=43,
            total=45,
        ),
    )
    payload = runner.build_parity_summary(
        filter_value="repository",
        channel_specs=(python_spec,),
        results=[
            runner.ChannelRunResult(
                name=python_spec.name,
                script=python_spec.script,
                summary_artifact=python_spec.summary_artifact,
                log_artifact=_expected_log_artifact(spec=python_spec, logs_dir=logs_dir),
                return_code=0,
                elapsed_seconds=1.2,
                status="passed",
                summary_counts=runner.ChannelSummaryCounts(
                    passed=2,
                    failed=0,
                    skipped=42,
                    total=44,
                ),
            )
        ],
        elapsed_seconds=3.4,
        output_path=tmp_path / "parity.json",
        logs_dir=logs_dir,
    )
    finalized = runner.finalize_parity_summary_contract(
        filter_value="repository",
        channel_specs=(python_spec,),
        payload=payload,
    )
    assert finalized["status"] == "failed"
    assert "contract_error" in finalized
    assert "aggregate repository parity counts drifted" in finalized["contract_error"]
    assert finalized["contract"]["status"] == "failed"
    assert "aggregate repository parity counts drifted" in finalized["contract"]["error"]


def test_build_fatal_summary_marks_run_failed(tmp_path: Path) -> None:
    payload = runner.build_fatal_summary(
        filter_value="repository",
        channel_specs=runner.CHANNEL_SPECS,
        output_path=tmp_path / "parity.json",
        logs_dir=tmp_path / "logs",
        elapsed_seconds=1.25,
        fatal_error="boom",
    )
    assert payload["status"] == "failed"
    assert payload["fatal_error"] == "boom"
    assert payload["channels"] == []
    assert payload["aggregate_total_checks"] == 0
    assert payload["contract"]["status"] == "failed"
    assert payload["contract"]["error"] == "boom"


def test_build_fatal_summary_preserves_partial_results(tmp_path: Path) -> None:
    payload = runner.build_fatal_summary(
        filter_value="repository",
        channel_specs=runner.CHANNEL_SPECS,
        output_path=tmp_path / "parity.json",
        logs_dir=tmp_path / "logs",
        elapsed_seconds=1.25,
        fatal_error="late boom",
        results=[
            runner.ChannelRunResult(
                name="python_sdk",
                script="tests/integration/test_python_sdk.py",
                summary_artifact="build/python_sdk_integration_summary.json",
                log_artifact="build/repository_intelligence_channel_parity_logs/python_sdk.log",
                return_code=0,
                elapsed_seconds=1.2,
                status="passed",
                summary_counts=runner.ChannelSummaryCounts(
                    passed=2,
                    failed=0,
                    skipped=43,
                    total=45,
                ),
            )
        ],
    )

    assert payload["status"] == "failed"
    assert payload["fatal_error"] == "late boom"
    assert payload["passed_channels"] == 1
    assert payload["failed_channels"] == 0
    assert payload["total_channels"] == len(runner.CHANNEL_SPECS)
    assert payload["aggregate_passed_checks"] == 2
    assert payload["aggregate_failed_checks"] == 0
    assert payload["aggregate_skipped_checks"] == 43
    assert payload["aggregate_total_checks"] == 45
    assert len(payload["channels"]) == 1
    assert payload["channels"][0]["name"] == "python_sdk"
    assert payload["channels"][0]["summary_counts"] == {
        "passed": 2,
        "failed": 0,
        "skipped": 43,
        "total": 45,
    }
    assert payload["contract"]["status"] == "failed"
    assert payload["contract"]["error"] == "late boom"
    assert payload["contract"]["actual_aggregate_counts"] == {
        "passed": 2,
        "failed": 0,
        "skipped": 43,
        "total": 45,
    }


def test_prepare_logs_dir_removes_stale_channel_logs(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stale_log = logs_dir / "python_sdk.log"
    stale_log.write_text("stale", encoding="utf-8")
    untouched_log = logs_dir / "unrelated.log"
    untouched_log.write_text("keep", encoding="utf-8")

    runner.prepare_logs_dir(
        channel_specs=(
            runner.ChannelSpec(
                name="python_sdk",
                script="tests/integration/test_python_sdk.py",
                summary_artifact="build/python_sdk_integration_summary.json",
            ),
        ),
        logs_dir=logs_dir,
    )

    assert not stale_log.exists()
    assert untouched_log.read_text(encoding="utf-8") == "keep"


def test_prepare_output_path_removes_stale_summary_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "build" / "parity.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("stale", encoding="utf-8")

    runner.prepare_output_path(output_path=output_path)

    assert not output_path.exists()
    assert output_path.parent.exists()


def test_main_preserves_partial_results_on_late_summary_failure(
    monkeypatch, tmp_path: Path
) -> None:
    output_path = tmp_path / "parity.json"
    logs_dir = tmp_path / "logs"
    partial_results = [
        runner.ChannelRunResult(
            name="python_sdk",
            script="tests/integration/test_python_sdk.py",
            summary_artifact="build/python_sdk_integration_summary.json",
            log_artifact="build/repository_intelligence_channel_parity_logs/python_sdk.log",
            return_code=0,
            elapsed_seconds=1.2,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(
                passed=2,
                failed=0,
                skipped=43,
                total=45,
            ),
        )
    ]

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
    monkeypatch.setattr(runner, "run_channel_specs", lambda **kwargs: partial_results)
    monkeypatch.setattr(
        runner,
        "build_parity_summary",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("late boom")),
    )

    exit_code = runner.main([])
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["fatal_error"] == "late boom"
    assert payload["passed_channels"] == 1
    assert payload["failed_channels"] == 0
    assert payload["aggregate_passed_checks"] == 2
    assert payload["aggregate_total_checks"] == 45
    assert len(payload["channels"]) == 1
    assert payload["channels"][0]["name"] == "python_sdk"


