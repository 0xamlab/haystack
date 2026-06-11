from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_agent_run_references import (
    collect_agent_run_references,
)
from tests.integration.live_check_filter import LIVE_CHECK_FILTER_ENV

RUN_REPO_PYTHON = ROOT / "scripts" / "run_repo_python.sh"
DEFAULT_OUTPUT_PATH = ROOT / "build" / "repository_intelligence_channel_parity_summary.json"
DEFAULT_LOGS_DIR = ROOT / "build" / "repository_intelligence_channel_parity_logs"
DEFAULT_JOBS = 1


@dataclass(frozen=True)
class ChannelSummaryCounts:
    passed: int
    failed: int
    skipped: int
    total: int | None


@dataclass(frozen=True)
class ChannelSpec:
    name: str
    script: str
    summary_artifact: str
    expected_repository_counts: ChannelSummaryCounts | None = None


CHANNEL_SPECS: tuple[ChannelSpec, ...] = (
    ChannelSpec(
        name="python_sdk",
        script="tests/integration/test_python_sdk.py",
        summary_artifact="build/python_sdk_integration_summary.json",
        expected_repository_counts=ChannelSummaryCounts(passed=2, failed=0, skipped=43, total=45),
    ),
    ChannelSpec(
        name="cli",
        script="tests/integration/test_cli.py",
        summary_artifact="build/cli_integration_summary.json",
        expected_repository_counts=ChannelSummaryCounts(passed=1, failed=0, skipped=42, total=43),
    ),
    ChannelSpec(
        name="mcp",
        script="tests/integration/test_mcp_server.py",
        summary_artifact="build/mcp_server_integration_summary.json",
        expected_repository_counts=ChannelSummaryCounts(passed=1, failed=0, skipped=64, total=65),
    ),
    ChannelSpec(
        name="algenta_client",
        script="tests/integration/test_algenta_client_live.py",
        summary_artifact="build/algenta_client_live_summary.json",
        expected_repository_counts=ChannelSummaryCounts(passed=1, failed=0, skipped=17, total=18),
    ),
    ChannelSpec(
        name="algenta_runtime",
        script="tests/integration/test_algenta_runtime_live.py",
        summary_artifact="build/algenta_runtime_live_summary.json",
        expected_repository_counts=ChannelSummaryCounts(passed=1, failed=0, skipped=16, total=17),
    ),
    ChannelSpec(
        name="typescript_sdk",
        script="tests/integration/test_typescript_sdk_client_live.py",
        summary_artifact="build/typescript_sdk_client_live_summary.json",
        expected_repository_counts=ChannelSummaryCounts(passed=1, failed=0, skipped=14, total=15),
    ),
    ChannelSpec(
        name="typescript_runtime",
        script="tests/integration/test_typescript_runtime_live.py",
        summary_artifact="build/typescript_sdk_local_runtime_live_summary.json",
        expected_repository_counts=ChannelSummaryCounts(passed=1, failed=0, skipped=14, total=15),
    ),
)


@dataclass(frozen=True)
class ChannelRunResult:
    name: str
    script: str
    summary_artifact: str
    log_artifact: str
    return_code: int
    elapsed_seconds: float
    status: str
    summary_counts: ChannelSummaryCounts | None
    error: str | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Repository Intelligence live channel parity across the standalone "
            "CLI, SDK, runtime, and MCP integration scripts."
        )
    )
    parser.add_argument(
        "--filter",
        default="repository",
        help=(
            "Value for ALGENTA_LIVE_CHECK_FILTER. Defaults to 'repository' so only "
            "Repository Intelligence checks execute."
        ),
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path to the consolidated parity summary JSON artifact.",
    )
    parser.add_argument(
        "--logs-dir",
        default=str(DEFAULT_LOGS_DIR),
        help="Directory where per-channel parity logs are written.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help=(
            "Maximum number of channel proofs to run concurrently. Defaults to "
            f"{DEFAULT_JOBS}."
        ),
    )
    return parser.parse_args(argv)


def effective_jobs(*, filter_value: str, requested_jobs: int) -> int:
    if requested_jobs < 1:
        raise ValueError(f"jobs must be >= 1, got {requested_jobs!r}")
    if filter_value == "repository":
        return 1
    return requested_jobs


def _resolve_repo_relative_path(path_value: str, *, field_name: str) -> Path:
    raw_path = Path(path_value)
    if raw_path.is_absolute():
        raise ValueError(f"{field_name} must be repo-relative: {path_value}")
    resolved_path = (ROOT / raw_path).resolve()
    try:
        resolved_path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"{field_name} escapes repo root: {path_value}") from exc
    return resolved_path


def _resolve_repo_path(path_value: Path | str, *, field_name: str) -> Path:
    raw_path = Path(path_value)
    resolved_path = raw_path.resolve() if raw_path.is_absolute() else (ROOT / raw_path).resolve()
    try:
        resolved_path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"{field_name} escapes repo root: {raw_path}") from exc
    return resolved_path


def _is_safe_channel_name(name: str) -> bool:
    return bool(name) and all(character.islower() or character.isdigit() or character == "_" for character in name)


def validate_runtime_paths(*, output_path: Path, logs_dir: Path) -> tuple[Path, Path]:
    resolved_output_path = _resolve_repo_path(output_path, field_name="output path")
    resolved_logs_dir = _resolve_repo_path(logs_dir, field_name="logs dir")
    try:
        resolved_output_path.relative_to(ROOT / "build")
    except ValueError as exc:
        raise ValueError(f"output path must stay under build/: {output_path}") from exc
    try:
        resolved_logs_dir.relative_to(ROOT / "build")
    except ValueError as exc:
        raise ValueError(f"logs dir must stay under build/: {logs_dir}") from exc
    if resolved_output_path.suffix != ".json":
        raise ValueError(f"output path must be a .json file: {output_path}")
    if resolved_logs_dir == resolved_output_path:
        raise ValueError(
            "logs dir must be distinct from output path: "
            f"{logs_dir}"
        )
    return resolved_output_path, resolved_logs_dir


def validate_runtime_surface_contract(
    *,
    channel_specs: tuple[ChannelSpec, ...],
    output_path: Path,
    logs_dir: Path,
) -> None:
    for spec in channel_specs:
        summary_artifact_path = _resolve_repo_relative_path(
            spec.summary_artifact,
            field_name="channel spec summary artifact",
        )
        if summary_artifact_path == output_path:
            raise ValueError(
                f"output path must stay distinct from channel summary artifacts: {output_path}"
            )
        try:
            summary_artifact_path.relative_to(logs_dir)
        except ValueError:
            continue
        raise ValueError(
            "logs dir must stay outside channel summary artifacts: "
            f"{logs_dir}"
        )
    try:
        output_path.relative_to(logs_dir)
    except ValueError:
        return
    raise ValueError(f"output path must stay outside logs dir: {output_path}")


def resolve_fatal_runtime_paths(*, output_path: Path, logs_dir: Path) -> tuple[Path, Path]:
    try:
        return validate_runtime_paths(output_path=output_path, logs_dir=logs_dir)
    except ValueError:
        return validate_runtime_paths(
            output_path=DEFAULT_OUTPUT_PATH,
            logs_dir=DEFAULT_LOGS_DIR,
        )


def validate_channel_specs(
    *,
    channel_specs: tuple[ChannelSpec, ...],
    filter_value: str,
) -> None:
    seen_names: set[str] = set()
    seen_scripts: set[str] = set()
    seen_summary_artifacts: set[str] = set()
    for spec in channel_specs:
        if not _is_safe_channel_name(spec.name):
            raise ValueError(f"invalid channel spec name: {spec.name}")
        if spec.name in seen_names:
            raise ValueError(f"duplicate channel spec name: {spec.name}")
        if spec.script in seen_scripts:
            raise ValueError(f"duplicate channel spec script: {spec.script}")
        if spec.summary_artifact in seen_summary_artifacts:
            raise ValueError(
                f"duplicate channel spec summary artifact: {spec.summary_artifact}"
            )
        if filter_value == "repository" and spec.expected_repository_counts is None:
            raise ValueError(
                f"repository channel spec missing expected counts: {spec.name}"
            )
        if spec.expected_repository_counts is not None:
            expected_total = (
                spec.expected_repository_counts.passed
                + spec.expected_repository_counts.failed
                + spec.expected_repository_counts.skipped
            )
            if spec.expected_repository_counts.total != expected_total:
                raise ValueError(
                    f"repository channel spec has inconsistent expected total: {spec.name}"
                )
        script_path = _resolve_repo_relative_path(spec.script, field_name="channel spec script")
        if not script_path.is_file():
            raise ValueError(f"missing channel spec script: {spec.script}")
        try:
            script_path.relative_to(ROOT / "tests" / "integration")
        except ValueError as exc:
            raise ValueError(
                f"channel spec script must stay under tests/integration/: {spec.script}"
            ) from exc
        summary_artifact_path = _resolve_repo_relative_path(
            spec.summary_artifact,
            field_name="channel spec summary artifact",
        )
        try:
            summary_artifact_path.relative_to(ROOT / "build")
        except ValueError as exc:
            raise ValueError(
                f"channel spec summary artifact must stay under build/: {spec.summary_artifact}"
            ) from exc
        if summary_artifact_path.suffix != ".json":
            raise ValueError(
                f"channel spec summary artifact must be a .json file: {spec.summary_artifact}"
            )
        seen_names.add(spec.name)
        seen_scripts.add(spec.script)
        seen_summary_artifacts.add(spec.summary_artifact)


def load_channel_summary_counts(path: Path) -> ChannelSummaryCounts:
    payload = json.loads(path.read_text(encoding="utf-8"))
    passed = payload.get("passed")
    failed = payload.get("failed")
    skipped = payload.get("skipped")
    total = payload.get("total")
    for name, value in (("passed", passed), ("failed", failed), ("skipped", skipped)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{path} has invalid {name}: {value!r}")
    if total is None:
        total = passed + failed + skipped
    elif not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise ValueError(f"{path} has invalid total: {total!r}")
    elif total != passed + failed + skipped:
        raise ValueError(
            f"{path} has inconsistent total: {total!r} != {passed + failed + skipped!r}"
        )
    status = payload.get("status")
    if status is not None and status != "passed":
        raise ValueError(f"{path} reported non-passing status: {status!r}")
    return ChannelSummaryCounts(
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=total,
    )


def validate_channel_summary_counts(
    *,
    spec: ChannelSpec,
    filter_value: str,
    counts: ChannelSummaryCounts,
) -> None:
    if filter_value != "repository":
        return
    expected_repository_counts = spec.expected_repository_counts
    if expected_repository_counts is None:
        return
    if counts != expected_repository_counts:
        raise ValueError(
            f"{spec.name} expected repository counts "
            f"{expected_repository_counts!r}, got {counts!r}"
        )


def expected_repository_aggregate_counts(
    channel_specs: tuple[ChannelSpec, ...],
) -> ChannelSummaryCounts | None:
    aggregate_passed = 0
    aggregate_failed = 0
    aggregate_skipped = 0
    aggregate_total = 0
    saw_expected_counts = False
    for spec in channel_specs:
        counts = spec.expected_repository_counts
        if counts is None:
            continue
        saw_expected_counts = True
        aggregate_passed += counts.passed
        aggregate_failed += counts.failed
        aggregate_skipped += counts.skipped
        aggregate_total += counts.total or 0
    if not saw_expected_counts:
        return None
    return ChannelSummaryCounts(
        passed=aggregate_passed,
        failed=aggregate_failed,
        skipped=aggregate_skipped,
        total=aggregate_total,
    )


def repository_contract_snapshot(
    *,
    filter_value: str,
    channel_specs: tuple[ChannelSpec, ...],
    actual_counts: ChannelSummaryCounts,
) -> dict[str, Any] | None:
    if filter_value != "repository":
        return None
    expected_aggregate_counts = expected_repository_aggregate_counts(channel_specs)
    if expected_aggregate_counts is None:
        return None
    return {
        "mode": "repository",
        "expected_aggregate_counts": asdict(expected_aggregate_counts),
        "actual_aggregate_counts": asdict(actual_counts),
        "per_channel_expected_counts": {
            spec.name: (
                asdict(spec.expected_repository_counts)
                if spec.expected_repository_counts is not None
                else None
            )
            for spec in channel_specs
        },
        "status": "passed" if actual_counts == expected_aggregate_counts else "failed",
    }


def run_channel_spec(
    spec: ChannelSpec,
    *,
    filter_value: str,
    logs_dir: Path,
) -> ChannelRunResult:
    started_at = time.monotonic()
    env = dict(os.environ)
    env[LIVE_CHECK_FILTER_ENV] = filter_value
    command = [str(RUN_REPO_PYTHON), spec.script]
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{spec.name}.log"
    artifact_path = ROOT / spec.summary_artifact
    if artifact_path.exists():
        artifact_path.unlink()
    process = subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    log_output = (process.stdout or "") + ("\n" if process.stdout and process.stderr else "") + (process.stderr or "")
    log_path.write_text(log_output, encoding="utf-8")
    elapsed_seconds = round(time.monotonic() - started_at, 3)
    if process.returncode != 0:
        error = process.stderr.strip() or process.stdout.strip() or "channel proof failed"
        return ChannelRunResult(
            name=spec.name,
            script=spec.script,
            summary_artifact=spec.summary_artifact,
            log_artifact=str(log_path.relative_to(ROOT)),
            return_code=process.returncode,
            elapsed_seconds=elapsed_seconds,
            status="failed",
            summary_counts=None,
            error=error,
        )
    if not artifact_path.exists():
        return ChannelRunResult(
            name=spec.name,
            script=spec.script,
            summary_artifact=spec.summary_artifact,
            log_artifact=str(log_path.relative_to(ROOT)),
            return_code=process.returncode,
            elapsed_seconds=elapsed_seconds,
            status="failed",
            summary_counts=None,
            error=f"missing summary artifact: {artifact_path}",
        )
    try:
        counts = load_channel_summary_counts(artifact_path)
        validate_channel_summary_counts(
            spec=spec,
            filter_value=filter_value,
            counts=counts,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return ChannelRunResult(
            name=spec.name,
            script=spec.script,
            summary_artifact=spec.summary_artifact,
            log_artifact=str(log_path.relative_to(ROOT)),
            return_code=process.returncode,
            elapsed_seconds=elapsed_seconds,
            status="failed",
            summary_counts=None,
            error=str(exc),
        )
    return ChannelRunResult(
        name=spec.name,
        script=spec.script,
        summary_artifact=spec.summary_artifact,
        log_artifact=str(log_path.relative_to(ROOT)),
        return_code=process.returncode,
        elapsed_seconds=elapsed_seconds,
        status="passed",
        summary_counts=counts,
    )


def run_channel_specs(
    *,
    channel_specs: tuple[ChannelSpec, ...],
    filter_value: str,
    logs_dir: Path,
    jobs: int,
) -> list[ChannelRunResult]:
    if jobs < 1:
        raise ValueError(f"jobs must be >= 1, got {jobs!r}")
    max_workers = min(jobs, len(channel_specs))
    if max_workers == 1:
        results = [
            _run_channel_spec_safe(
                spec,
                filter_value=filter_value,
                logs_dir=logs_dir,
            )
            for spec in channel_specs
        ]
        for result in results:
            _print_channel_result(result)
        return results

    results_by_name: dict[str, ChannelRunResult] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_spec = {
            executor.submit(
                _run_channel_spec_safe,
                spec,
                filter_value=filter_value,
                logs_dir=logs_dir,
            ): spec
            for spec in channel_specs
        }
        for future in as_completed(future_to_spec):
            result = future.result()
            results_by_name[result.name] = result
            _print_channel_result(result)
    return [results_by_name[spec.name] for spec in channel_specs]


def _channel_log_artifact_path(spec: ChannelSpec, *, logs_dir: Path) -> str:
    log_path = logs_dir / f"{spec.name}.log"
    try:
        return str(log_path.relative_to(ROOT))
    except ValueError:
        return str(log_path)


def _write_channel_log(*, spec: ChannelSpec, logs_dir: Path, content: str) -> str:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{spec.name}.log"
    log_path.write_text(content, encoding="utf-8")
    return _channel_log_artifact_path(spec, logs_dir=logs_dir)


def _run_channel_spec_safe(
    spec: ChannelSpec,
    *,
    filter_value: str,
    logs_dir: Path,
) -> ChannelRunResult:
    started_at = time.monotonic()
    try:
        return run_channel_spec(
            spec,
            filter_value=filter_value,
            logs_dir=logs_dir,
        )
    except Exception as exc:  # noqa: BLE001
        log_artifact = _write_channel_log(
            spec=spec,
            logs_dir=logs_dir,
            content=f"unexpected runner exception: {exc}\n",
        )
        return ChannelRunResult(
            name=spec.name,
            script=spec.script,
            summary_artifact=spec.summary_artifact,
            log_artifact=log_artifact,
            return_code=1,
            elapsed_seconds=round(time.monotonic() - started_at, 3),
            status="failed",
            summary_counts=None,
            error=f"unexpected runner exception: {exc}",
        )


def _print_channel_result(result: ChannelRunResult) -> None:
    if result.status == "passed":
        counts = result.summary_counts
        counts_text = ""
        if counts is not None:
            counts_text = (
                f" passed={counts.passed} failed={counts.failed} "
                f"skipped={counts.skipped}"
            )
        print(
            f"  ✅ {result.name} ({result.elapsed_seconds:.2f}s){counts_text}",
            flush=True,
        )
        return
    print(
        f"  ❌ {result.name} ({result.elapsed_seconds:.2f}s): {result.error}",
        flush=True,
    )


def prepare_logs_dir(*, channel_specs: tuple[ChannelSpec, ...], logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    for spec in channel_specs:
        log_path = logs_dir / f"{spec.name}.log"
        if log_path.exists():
            log_path.unlink()


def prepare_output_path(*, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()


def build_parity_summary(
    *,
    filter_value: str,
    channel_specs: tuple[ChannelSpec, ...],
    results: list[ChannelRunResult],
    elapsed_seconds: float,
    output_path: Path,
    logs_dir: Path,
) -> dict[str, Any]:
    validate_channel_results(
        channel_specs=channel_specs,
        results=results,
        logs_dir=logs_dir,
    )
    passed_channels = sum(1 for result in results if result.status == "passed")
    failed_channels = sum(1 for result in results if result.status == "failed")
    aggregate_passed_checks = sum(
        result.summary_counts.passed for result in results if result.summary_counts is not None
    )
    aggregate_failed_checks = sum(
        result.summary_counts.failed for result in results if result.summary_counts is not None
    )
    aggregate_skipped_checks = sum(
        result.summary_counts.skipped for result in results if result.summary_counts is not None
    )
    aggregate_total_checks = sum(
        result.summary_counts.total or 0 for result in results if result.summary_counts is not None
    )
    actual_counts = ChannelSummaryCounts(
        passed=aggregate_passed_checks,
        failed=aggregate_failed_checks,
        skipped=aggregate_skipped_checks,
        total=aggregate_total_checks,
    )
    agent_run_references = collect_agent_run_references(
        root=ROOT,
        summary_artifacts=(
            result.summary_artifact for result in results if result.status == "passed"
        ),
    )
    return {
        "artifact": "repository_intelligence_channel_parity_summary",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "filter": filter_value,
        "status": "passed" if failed_channels == 0 else "failed",
        "passed_channels": passed_channels,
        "failed_channels": failed_channels,
        "total_channels": len(results),
        "aggregate_passed_checks": aggregate_passed_checks,
        "aggregate_failed_checks": aggregate_failed_checks,
        "aggregate_skipped_checks": aggregate_skipped_checks,
        "aggregate_total_checks": aggregate_total_checks,
        "contract": repository_contract_snapshot(
            filter_value=filter_value,
            channel_specs=channel_specs,
            actual_counts=actual_counts,
        ),
        "agent_run_references": agent_run_references,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "output_path": str(output_path),
        "logs_dir": str(logs_dir),
        "channels": [
            {
                **asdict(result),
                "summary_counts": (
                    asdict(result.summary_counts) if result.summary_counts is not None else None
                ),
            }
            for result in results
        ],
    }


def _serialize_channel_results(results: list[ChannelRunResult]) -> list[dict[str, Any]]:
    return [
        {
            **asdict(result),
            "summary_counts": asdict(result.summary_counts) if result.summary_counts is not None else None,
        }
        for result in results
    ]


def _aggregate_channel_results(results: list[ChannelRunResult]) -> tuple[int, int, ChannelSummaryCounts]:
    passed_channels = sum(1 for result in results if result.status == "passed")
    failed_channels = sum(1 for result in results if result.status == "failed")
    return (
        passed_channels,
        failed_channels,
        ChannelSummaryCounts(
            passed=sum(
                result.summary_counts.passed
                for result in results
                if result.summary_counts is not None
            ),
            failed=sum(
                result.summary_counts.failed
                for result in results
                if result.summary_counts is not None
            ),
            skipped=sum(
                result.summary_counts.skipped
                for result in results
                if result.summary_counts is not None
            ),
            total=sum(
                result.summary_counts.total or 0
                for result in results
                if result.summary_counts is not None
            ),
        ),
    )


def validate_channel_results(
    *,
    channel_specs: tuple[ChannelSpec, ...],
    results: list[ChannelRunResult],
    logs_dir: Path,
) -> None:
    expected_specs_by_name = {spec.name: spec for spec in channel_specs}
    expected_names = [spec.name for spec in channel_specs]
    expected_name_set = set(expected_names)
    seen_result_names: set[str] = set()
    for result in results:
        if result.name not in expected_name_set:
            raise ValueError(f"unexpected channel result: {result.name}")
        if result.name in seen_result_names:
            raise ValueError(f"duplicate channel result: {result.name}")
        spec = expected_specs_by_name[result.name]
        if result.script != spec.script:
            raise ValueError(
                f"channel result script drifted for {result.name}: {result.script}"
            )
        if result.summary_artifact != spec.summary_artifact:
            raise ValueError(
                "channel result summary artifact drifted for "
                f"{result.name}: {result.summary_artifact}"
            )
        expected_log_artifact = _channel_log_artifact_path(spec, logs_dir=logs_dir)
        if result.log_artifact != expected_log_artifact:
            raise ValueError(
                "channel result log artifact drifted for "
                f"{result.name}: {result.log_artifact}"
            )
        if not math.isfinite(result.elapsed_seconds) or result.elapsed_seconds < 0:
            raise ValueError(
                "channel result elapsed seconds invalid for "
                f"{result.name}: {result.elapsed_seconds}"
            )
        if result.status not in {"passed", "failed"}:
            raise ValueError(
                f"channel result status invalid for {result.name}: {result.status}"
            )
        if result.status == "passed":
            if result.return_code != 0:
                raise ValueError(
                    "channel result return code drifted for passed "
                    f"{result.name}: {result.return_code}"
                )
            if result.summary_counts is None:
                raise ValueError(
                    f"channel result missing summary counts for passed {result.name}"
                )
            if result.error is not None:
                raise ValueError(
                    "channel result error drifted for passed "
                    f"{result.name}: {result.error}"
                )
        else:
            if result.return_code == 0:
                raise ValueError(
                    "channel result return code drifted for failed "
                    f"{result.name}: {result.return_code}"
                )
            if result.summary_counts is not None:
                raise ValueError(
                    f"channel result summary counts drifted for failed {result.name}"
                )
            if not result.error:
                raise ValueError(
                    f"channel result missing error for failed {result.name}"
                )
        seen_result_names.add(result.name)
    actual_names = [result.name for result in results]
    if actual_names != expected_names[: len(actual_names)]:
        raise ValueError(
            "channel result order drifted: "
            f"expected prefix {expected_names[: len(actual_names)]}, got {actual_names}"
        )
    missing_names = [name for name in expected_names if name not in seen_result_names]
    if missing_names:
        raise ValueError("missing channel results: " + ", ".join(missing_names))


def validate_parity_summary_contract(
    *,
    filter_value: str,
    channel_specs: tuple[ChannelSpec, ...],
    payload: dict[str, Any],
) -> None:
    if filter_value != "repository":
        return
    expected_counts = expected_repository_aggregate_counts(channel_specs)
    if expected_counts is None:
        return
    actual_counts = ChannelSummaryCounts(
        passed=int(payload["aggregate_passed_checks"]),
        failed=int(payload["aggregate_failed_checks"]),
        skipped=int(payload["aggregate_skipped_checks"]),
        total=int(payload["aggregate_total_checks"]),
    )
    if actual_counts != expected_counts:
        raise ValueError(
            "aggregate repository parity counts drifted: "
            f"expected {expected_counts!r}, got {actual_counts!r}"
        )


def finalize_parity_summary_contract(
    *,
    filter_value: str,
    channel_specs: tuple[ChannelSpec, ...],
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        validate_parity_summary_contract(
            filter_value=filter_value,
            channel_specs=channel_specs,
            payload=payload,
        )
    except ValueError as exc:
        failed_payload = dict(payload)
        failed_payload["status"] = "failed"
        failed_payload["contract_error"] = str(exc)
        contract = failed_payload.get("contract")
        if isinstance(contract, dict):
            contract["status"] = "failed"
            contract["error"] = str(exc)
        return failed_payload
    return payload


def write_summary(output_path: Path, payload: dict[str, Any]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def build_fatal_summary(
    *,
    filter_value: str,
    channel_specs: tuple[ChannelSpec, ...],
    output_path: Path,
    logs_dir: Path,
    elapsed_seconds: float,
    fatal_error: str,
    results: list[ChannelRunResult] | None = None,
) -> dict[str, Any]:
    completed_results = list(results or [])
    passed_channels, failed_channels, aggregate_counts = _aggregate_channel_results(completed_results)
    contract = repository_contract_snapshot(
        filter_value=filter_value,
        channel_specs=channel_specs,
        actual_counts=aggregate_counts,
    )
    if isinstance(contract, dict):
        contract["status"] = "failed"
        contract["error"] = fatal_error
    agent_run_references = collect_agent_run_references(
        root=ROOT,
        summary_artifacts=(
            result.summary_artifact
            for result in completed_results
            if result.status == "passed"
        ),
    )
    return {
        "artifact": "repository_intelligence_channel_parity_summary",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "filter": filter_value,
        "status": "failed",
        "passed_channels": passed_channels,
        "failed_channels": failed_channels,
        "total_channels": len(channel_specs),
        "aggregate_passed_checks": aggregate_counts.passed,
        "aggregate_failed_checks": aggregate_counts.failed,
        "aggregate_skipped_checks": aggregate_counts.skipped,
        "aggregate_total_checks": aggregate_counts.total or 0,
        "contract": contract,
        "agent_run_references": agent_run_references,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "output_path": str(output_path),
        "logs_dir": str(logs_dir),
        "channels": _serialize_channel_results(completed_results),
        "fatal_error": fatal_error,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = Path(args.output)
    logs_dir = Path(args.logs_dir)
    started_at = time.monotonic()
    results: list[ChannelRunResult] = []
    try:
        output_path, logs_dir = validate_runtime_paths(
            output_path=output_path,
            logs_dir=logs_dir,
        )
        jobs = effective_jobs(filter_value=args.filter, requested_jobs=args.jobs)
        validate_channel_specs(channel_specs=CHANNEL_SPECS, filter_value=args.filter)
        validate_runtime_surface_contract(
            channel_specs=CHANNEL_SPECS,
            output_path=output_path,
            logs_dir=logs_dir,
        )

        print(
            "Running Repository Intelligence channel parity "
            f"with {LIVE_CHECK_FILTER_ENV}={args.filter} "
            f"(jobs={min(jobs, len(CHANNEL_SPECS))})",
            flush=True,
        )
        if jobs != args.jobs:
            print(
                "  note: repository live checks share write-scoped POST routes, "
                "so jobs were clamped to 1 to avoid resource_write_conflict.",
                flush=True,
            )
        prepare_output_path(output_path=output_path)
        prepare_logs_dir(channel_specs=CHANNEL_SPECS, logs_dir=logs_dir)
        for spec in CHANNEL_SPECS:
            print(f"  ... {spec.name}: {spec.script}", flush=True)
        results = run_channel_specs(
            channel_specs=CHANNEL_SPECS,
            filter_value=args.filter,
            logs_dir=logs_dir,
            jobs=jobs,
        )

        payload = build_parity_summary(
            filter_value=args.filter,
            channel_specs=CHANNEL_SPECS,
            results=results,
            elapsed_seconds=time.monotonic() - started_at,
            output_path=output_path,
            logs_dir=logs_dir,
        )
        payload = finalize_parity_summary_contract(
            filter_value=args.filter,
            channel_specs=CHANNEL_SPECS,
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001
        output_path, logs_dir = resolve_fatal_runtime_paths(
            output_path=output_path,
            logs_dir=logs_dir,
        )
        payload = build_fatal_summary(
            filter_value=args.filter,
            channel_specs=CHANNEL_SPECS,
            output_path=output_path,
            logs_dir=logs_dir,
            elapsed_seconds=time.monotonic() - started_at,
            fatal_error=str(exc),
            results=results,
        )
    write_summary(output_path, payload)
    print(f"Summary artifact: {output_path}", flush=True)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
