"""Tests for test_repository_channel_parity_runner: validate_channel.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_b79cfb1f-957-2/tests/test_repository_channel_parity_runner.py during modularization.
"""
from __future__ import annotations

from tests._test_repository_channel_parity_runner_helpers import *  # noqa: F401,F403


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


