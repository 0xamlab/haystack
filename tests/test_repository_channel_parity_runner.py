from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from tests import repository_channel_parity_runner as runner


def _expected_log_artifact(*, spec: runner.ChannelSpec, logs_dir: Path) -> str:
    return runner._channel_log_artifact_path(spec, logs_dir=logs_dir)


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


def test_parse_args_accepts_jobs_override() -> None:
    args = runner.parse_args(["--jobs", "5"])
    assert args.jobs == 5


def test_effective_jobs_clamps_repository_filter_to_serial() -> None:
    assert runner.effective_jobs(filter_value="repository", requested_jobs=5) == 1
    assert runner.effective_jobs(filter_value="other", requested_jobs=5) == 5


def test_validate_runtime_paths_accepts_default_build_paths() -> None:
    output_path, logs_dir = runner.validate_runtime_paths(
        output_path=runner.DEFAULT_OUTPUT_PATH,
        logs_dir=runner.DEFAULT_LOGS_DIR,
    )
    assert output_path == runner.DEFAULT_OUTPUT_PATH.resolve()
    assert logs_dir == runner.DEFAULT_LOGS_DIR.resolve()


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


def test_validate_channel_specs_accepts_current_registry() -> None:
    runner.validate_channel_specs(
        channel_specs=runner.CHANNEL_SPECS,
        filter_value="repository",
    )


def test_validate_channel_specs_rejects_invalid_name_characters() -> None:
    specs = (
        runner.ChannelSpec(
            name="bad-name",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="other")
    except ValueError as exc:
        assert str(exc) == "invalid channel spec name: bad-name"
    else:
        raise AssertionError("expected invalid channel spec name to fail")


def test_validate_channel_specs_rejects_empty_name() -> None:
    specs = (
        runner.ChannelSpec(
            name="",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="other")
    except ValueError as exc:
        assert str(exc) == "invalid channel spec name: "
    else:
        raise AssertionError("expected empty channel spec name to fail")


def test_validate_channel_specs_rejects_duplicate_name() -> None:
    specs = (
        runner.ChannelSpec(
            name="dup",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
        ),
        runner.ChannelSpec(
            name="dup",
            script="tests/integration/test_mcp_server.py",
            summary_artifact="build/b.json",
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="other")
    except ValueError as exc:
        assert str(exc) == "duplicate channel spec name: dup"
    else:
        raise AssertionError("expected duplicate channel spec name to fail")


def test_validate_channel_specs_rejects_duplicate_script() -> None:
    specs = (
        runner.ChannelSpec(
            name="a",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
        ),
        runner.ChannelSpec(
            name="b",
            script="tests/integration/test_cli.py",
            summary_artifact="build/b.json",
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="other")
    except ValueError as exc:
        assert str(exc) == "duplicate channel spec script: tests/integration/test_cli.py"
    else:
        raise AssertionError("expected duplicate channel spec script to fail")


def test_validate_channel_specs_rejects_duplicate_summary_artifact() -> None:
    specs = (
        runner.ChannelSpec(
            name="a",
            script="tests/integration/test_cli.py",
            summary_artifact="build/dup.json",
        ),
        runner.ChannelSpec(
            name="b",
            script="tests/integration/test_mcp_server.py",
            summary_artifact="build/dup.json",
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="other")
    except ValueError as exc:
        assert str(exc) == "duplicate channel spec summary artifact: build/dup.json"
    else:
        raise AssertionError("expected duplicate channel spec summary artifact to fail")


def test_validate_channel_specs_requires_repository_expected_counts() -> None:
    specs = (
        runner.ChannelSpec(name="a", script="a.py", summary_artifact="a.json"),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="repository")
    except ValueError as exc:
        assert str(exc) == "repository channel spec missing expected counts: a"
    else:
        raise AssertionError("expected repository channel spec without expected counts to fail")


def test_validate_channel_specs_rejects_inconsistent_expected_total() -> None:
    specs = (
        runner.ChannelSpec(
            name="a",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            expected_repository_counts=runner.ChannelSummaryCounts(
                passed=1,
                failed=0,
                skipped=0,
                total=2,
            ),
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="repository")
    except ValueError as exc:
        assert str(exc) == "repository channel spec has inconsistent expected total: a"
    else:
        raise AssertionError("expected inconsistent expected total to fail")


def test_validate_channel_specs_rejects_missing_script() -> None:
    specs = (
        runner.ChannelSpec(
            name="a",
            script="tests/integration/does_not_exist.py",
            summary_artifact="build/a.json",
            expected_repository_counts=runner.ChannelSummaryCounts(
                passed=1,
                failed=0,
                skipped=0,
                total=1,
            ),
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="repository")
    except ValueError as exc:
        assert str(exc) == "missing channel spec script: tests/integration/does_not_exist.py"
    else:
        raise AssertionError("expected missing channel spec script to fail")


def test_validate_channel_specs_rejects_absolute_script_path() -> None:
    specs = (
        runner.ChannelSpec(
            name="a",
            script="/tmp/a.py",
            summary_artifact="build/a.json",
            expected_repository_counts=runner.ChannelSummaryCounts(
                passed=1,
                failed=0,
                skipped=0,
                total=1,
            ),
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="repository")
    except ValueError as exc:
        assert str(exc) == "channel spec script must be repo-relative: /tmp/a.py"
    else:
        raise AssertionError("expected absolute channel spec script to fail")


def test_validate_channel_specs_rejects_script_outside_tests_integration() -> None:
    specs = (
        runner.ChannelSpec(
            name="a",
            script="tests/test_repository_channel_parity_runner.py",
            summary_artifact="build/a.json",
            expected_repository_counts=runner.ChannelSummaryCounts(
                passed=1,
                failed=0,
                skipped=0,
                total=1,
            ),
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="repository")
    except ValueError as exc:
        assert (
            str(exc)
            == "channel spec script must stay under tests/integration/: tests/test_repository_channel_parity_runner.py"
        )
    else:
        raise AssertionError("expected script outside tests/integration to fail")


def test_validate_channel_specs_rejects_summary_artifact_outside_build() -> None:
    specs = (
        runner.ChannelSpec(
            name="a",
            script="tests/integration/test_cli.py",
            summary_artifact="tmp/a.json",
            expected_repository_counts=runner.ChannelSummaryCounts(
                passed=1,
                failed=0,
                skipped=0,
                total=1,
            ),
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="repository")
    except ValueError as exc:
        assert str(exc) == "channel spec summary artifact must stay under build/: tmp/a.json"
    else:
        raise AssertionError("expected summary artifact outside build to fail")


def test_validate_channel_specs_rejects_non_json_summary_artifact() -> None:
    specs = (
        runner.ChannelSpec(
            name="a",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.txt",
            expected_repository_counts=runner.ChannelSummaryCounts(
                passed=1,
                failed=0,
                skipped=0,
                total=1,
            ),
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="repository")
    except ValueError as exc:
        assert str(exc) == "channel spec summary artifact must be a .json file: build/a.txt"
    else:
        raise AssertionError("expected non-json summary artifact to fail")


def test_validate_channel_specs_rejects_summary_artifact_repo_escape() -> None:
    specs = (
        runner.ChannelSpec(
            name="a",
            script="tests/integration/test_cli.py",
            summary_artifact="../a.json",
            expected_repository_counts=runner.ChannelSummaryCounts(
                passed=1,
                failed=0,
                skipped=0,
                total=1,
            ),
        ),
    )
    try:
        runner.validate_channel_specs(channel_specs=specs, filter_value="repository")
    except ValueError as exc:
        assert str(exc) == "channel spec summary artifact escapes repo root: ../a.json"
    else:
        raise AssertionError("expected summary artifact repo escape to fail")


def test_validate_channel_summary_counts_rejects_repository_count_mismatch() -> None:
    spec = runner.ChannelSpec(
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
    try:
        runner.validate_channel_summary_counts(
            spec=spec,
            filter_value="repository",
            counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=44, total=45),
        )
    except ValueError as exc:
        assert "expected repository counts" in str(exc)
    else:
        raise AssertionError("expected ValueError for repository count mismatch")


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


def test_validate_channel_results_rejects_missing_result(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
        runner.ChannelSpec(name="second", script="tests/integration/test_mcp_server.py", summary_artifact="build/b.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "missing channel results: second"
    else:
        raise AssertionError("expected missing channel result to fail")


def test_validate_channel_results_rejects_duplicate_result(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    result = runner.ChannelRunResult(
        name="first",
        script="tests/integration/test_cli.py",
        summary_artifact="build/a.json",
        log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
        return_code=0,
        elapsed_seconds=1.0,
        status="passed",
        summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
    )
    try:
        runner.validate_channel_results(
            channel_specs=specs,
            results=[result, result],
            logs_dir=logs_dir,
        )
    except ValueError as exc:
        assert str(exc) == "duplicate channel result: first"
    else:
        raise AssertionError("expected duplicate channel result to fail")


def test_validate_channel_results_rejects_order_drift(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
        runner.ChannelSpec(name="second", script="tests/integration/test_mcp_server.py", summary_artifact="build/b.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="second",
            script="tests/integration/test_mcp_server.py",
            summary_artifact="build/b.json",
            log_artifact=_expected_log_artifact(spec=specs[1], logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        ),
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        ),
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert (
            str(exc)
            == "channel result order drifted: expected prefix ['first', 'second'], got ['second', 'first']"
        )
    else:
        raise AssertionError("expected channel result order drift to fail")


def test_validate_channel_results_rejects_unexpected_result(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="unexpected",
            script="tests/integration/test_mcp_server.py",
            summary_artifact="build/b.json",
            log_artifact=str(logs_dir / "unexpected.log"),
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "unexpected channel result: unexpected"
    else:
        raise AssertionError("expected unexpected channel result to fail")


def test_validate_channel_results_rejects_script_drift(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_mcp_server.py",
            summary_artifact="build/a.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "channel result script drifted for first: tests/integration/test_mcp_server.py"
    else:
        raise AssertionError("expected channel result script drift to fail")


def test_validate_channel_results_rejects_summary_artifact_drift(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/b.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "channel result summary artifact drifted for first: build/b.json"
    else:
        raise AssertionError("expected channel result summary artifact drift to fail")


def test_validate_channel_results_rejects_log_artifact_drift(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            log_artifact="build/logs/wrong.log",
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "channel result log artifact drifted for first: build/logs/wrong.log"
    else:
        raise AssertionError("expected channel result log artifact drift to fail")


def test_validate_channel_results_rejects_invalid_elapsed_seconds(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=-1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "channel result elapsed seconds invalid for first: -1.0"
    else:
        raise AssertionError("expected invalid elapsed seconds to fail")


def test_validate_channel_results_rejects_missing_summary_counts_for_passed(
    tmp_path: Path,
) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=None,
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "channel result missing summary counts for passed first"
    else:
        raise AssertionError("expected missing summary counts for passed result to fail")


def test_validate_channel_results_rejects_error_for_passed_result(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.0,
            status="passed",
            summary_counts=runner.ChannelSummaryCounts(passed=1, failed=0, skipped=0, total=1),
            error="unexpected",
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "channel result error drifted for passed first: unexpected"
    else:
        raise AssertionError("expected passed-result error drift to fail")


def test_validate_channel_results_rejects_failed_result_with_summary_counts(
    tmp_path: Path,
) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=1,
            elapsed_seconds=1.0,
            status="failed",
            summary_counts=runner.ChannelSummaryCounts(passed=0, failed=1, skipped=0, total=1),
            error="channel proof failed",
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "channel result summary counts drifted for failed first"
    else:
        raise AssertionError("expected failed-result summary counts drift to fail")


def test_validate_channel_results_rejects_failed_result_with_zero_return_code(
    tmp_path: Path,
) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=0,
            elapsed_seconds=1.0,
            status="failed",
            summary_counts=None,
            error="channel proof failed",
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "channel result return code drifted for failed first: 0"
    else:
        raise AssertionError("expected failed result with zero return code to fail")


def test_validate_channel_results_rejects_failed_result_without_error(tmp_path: Path) -> None:
    specs = (
        runner.ChannelSpec(name="first", script="tests/integration/test_cli.py", summary_artifact="build/a.json"),
    )
    logs_dir = tmp_path / "logs"
    results = [
        runner.ChannelRunResult(
            name="first",
            script="tests/integration/test_cli.py",
            summary_artifact="build/a.json",
            log_artifact=_expected_log_artifact(spec=specs[0], logs_dir=logs_dir),
            return_code=1,
            elapsed_seconds=1.0,
            status="failed",
            summary_counts=None,
            error=None,
        )
    ]
    try:
        runner.validate_channel_results(channel_specs=specs, results=results, logs_dir=logs_dir)
    except ValueError as exc:
        assert str(exc) == "channel result missing error for failed first"
    else:
        raise AssertionError("expected failed result without error to fail")


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
