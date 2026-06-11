from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]

LIVE_INTEGRATION_SUMMARY_ARTIFACTS: dict[str, Path] = {
    "algenta_client_live": ROOT / "build" / "algenta_client_live_summary.json",
    "algenta_runtime_live": ROOT / "build" / "algenta_runtime_live_summary.json",
    "all_engines_integration": ROOT / "build" / "all_engines_integration_summary.json",
    "api_live_integration": ROOT / "build" / "api_live_integration_summary.json",
    "auth_security_integration": ROOT / "build" / "auth_security_integration_summary.json",
    "benchmarks_integration": ROOT / "build" / "benchmarks_integration_summary.json",
    "billing_team_integration": ROOT / "build" / "billing_team_integration_summary.json",
    "cli_integration": ROOT / "build" / "cli_integration_summary.json",
    "connectors_integration": ROOT / "build" / "connectors_integration_summary.json",
    "database_integration": ROOT / "build" / "database_integration_summary.json",
    "e2e_complete_integration": ROOT / "build" / "e2e_complete_integration_summary.json",
    "go_live_connectivity_local_only": ROOT / "build" / "go_live_connectivity_local_only_summary.json",
    "go_live_connectivity_real": ROOT / "build" / "go_live_connectivity_real_summary.json",
    "go_live_full_real": ROOT / "build" / "go_live_full_real_summary.json",
    "jobs_integration": ROOT / "build" / "jobs_integration_summary.json",
    "local_runtime_real": ROOT / "build" / "local_runtime_real_summary.json",
    "mcp_runtime_live": ROOT / "build" / "mcp_runtime_live_summary.json",
    "mcp_server_integration": ROOT / "build" / "mcp_server_integration_summary.json",
    "middleware_integration": ROOT / "build" / "middleware_integration_summary.json",
    "mojo_pool_integration": ROOT / "build" / "mojo_pool_integration_summary.json",
    "mojo_engines_realdata_integration": ROOT / "build" / "mojo_engines_realdata_integration_summary.json",
    "openapi_integration": ROOT / "build" / "openapi_integration_summary.json",
    "python_sdk_integration": ROOT / "build" / "python_sdk_integration_summary.json",
    "redis_integration": ROOT / "build" / "redis_integration_summary.json",
    "services_integration": ROOT / "build" / "services_integration_summary.json",
    "templates_integration": ROOT / "build" / "templates_integration_summary.json",
    "typescript_sdk_client_live": ROOT / "build" / "typescript_sdk_client_live_summary.json",
}

LIVE_INTEGRATION_SUMMARY_SCRIPTS: dict[str, str] = {
    "algenta_client_live": "tests/integration/test_algenta_client_live.py",
    "algenta_runtime_live": "tests/integration/test_algenta_runtime_live.py",
    "all_engines_integration": "tests/integration/test_all_engines.py",
    "api_live_integration": "tests/integration/test_api_live.py",
    "auth_security_integration": "tests/integration/test_auth_security.py",
    "benchmarks_integration": "tests/integration/test_benchmarks.py",
    "billing_team_integration": "tests/integration/test_billing_team.py",
    "cli_integration": "tests/integration/test_cli.py",
    "connectors_integration": "tests/integration/test_connectors.py",
    "database_integration": "tests/integration/test_database.py",
    "e2e_complete_integration": "tests/integration/test_e2e_complete.py",
    "go_live_connectivity_local_only": "tests/integration/test_go_live_connectivity_real.py",
    "go_live_connectivity_real": "tests/integration/test_go_live_connectivity_real.py",
    "go_live_full_real": "tests/integration/test_go_live_full_real.py",
    "jobs_integration": "tests/integration/test_jobs.py",
    "local_runtime_real": "tests/integration/test_local_runtime_real.py",
    "mcp_runtime_live": "tests/integration/test_mcp_runtime_live.py",
    "mcp_server_integration": "tests/integration/test_mcp_server.py",
    "middleware_integration": "tests/integration/test_middleware.py",
    "mojo_engines_realdata_integration": "tests/integration/test_mojo_engines_realdata.py",
    "mojo_pool_integration": "tests/integration/test_mojo_pool.py",
    "openapi_integration": "tests/integration/test_openapi.py",
    "python_sdk_integration": "tests/integration/test_python_sdk.py",
    "redis_integration": "tests/integration/test_redis.py",
    "services_integration": "tests/integration/test_services.py",
    "templates_integration": "tests/integration/test_templates.py",
    "typescript_sdk_client_live": "tests/integration/test_typescript_sdk_client_live.py",
}

LIVE_INTEGRATION_SUMMARY_KEYS = {
    "artifact",
    "generated_at",
    "name",
    "script",
    "passed",
    "failed",
    "skipped",
    "total",
    "elapsed_seconds",
    "details",
}


def _coerce_non_negative_int(name: str, value: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer, not boolean")
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    coerced = int(value)
    if coerced < 0:
        raise ValueError(f"{name} must be >= 0")
    return coerced


def _coerce_elapsed_seconds(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("elapsed_seconds must be a finite number >= 0")
    if not isinstance(value, (int, float)):
        raise ValueError("elapsed_seconds must be a finite number >= 0")
    coerced = float(value)
    if not math.isfinite(coerced) or coerced < 0:
        raise ValueError("elapsed_seconds must be a finite number >= 0")
    return round(coerced, 3)


def _coerce_generated_at(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("generated_at must be a UTC ISO-8601 string")
    if not value.endswith("Z"):
        raise ValueError("generated_at must be a UTC ISO-8601 string ending with Z")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated_at must be a UTC ISO-8601 string ending with Z") from exc
    if parsed.tzinfo != UTC:
        raise ValueError("generated_at must be a UTC ISO-8601 string ending with Z")
    return value


def _coerce_script_path(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("script must be a tests/integration/*.py path")
    if not value.startswith("tests/integration/") or not value.endswith(".py"):
        raise ValueError("script must be a tests/integration/*.py path")
    return value


def _validate_json_metadata_shape(
    value: Any,
    *,
    key_error_message: str,
    tuple_error_message: str,
) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError(key_error_message)
            _validate_json_metadata_shape(
                nested,
                key_error_message=key_error_message,
                tuple_error_message=tuple_error_message,
            )
        return
    if isinstance(value, tuple):
        raise ValueError(tuple_error_message)
    if isinstance(value, list):
        for item in value:
            _validate_json_metadata_shape(
                item,
                key_error_message=key_error_message,
                tuple_error_message=tuple_error_message,
            )


def _coerce_details(value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("details must be a dict")
    _validate_json_metadata_shape(
        value,
        key_error_message="details must use only string keys",
        tuple_error_message="details must not contain tuples",
    )
    try:
        json.dumps(value, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("details must be JSON-serializable with finite values") from exc
    return value


def _coerce_registered_output_path(name: str, output_path: Path) -> Path:
    try:
        expected = LIVE_INTEGRATION_SUMMARY_ARTIFACTS[name]
    except KeyError as exc:
        raise ValueError(f"unknown live integration summary name: {name}") from exc
    if output_path.resolve() != expected.resolve():
        raise ValueError(f"output_path must match registered artifact path: {expected}")
    return output_path


def _coerce_registered_script_path(name: str, script: str) -> str:
    normalized = _coerce_script_path(script)
    try:
        expected = LIVE_INTEGRATION_SUMMARY_SCRIPTS[name]
    except KeyError as exc:
        raise ValueError(f"unknown live integration summary name: {name}") from exc
    if normalized != expected:
        raise ValueError(f"script must match registered suite script: {expected}")
    return normalized


def _coerce_monotonic_started_at(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("started_at must be a finite monotonic timestamp")
    if not isinstance(value, (int, float)):
        raise ValueError("started_at must be a finite monotonic timestamp")
    coerced = float(value)
    if not math.isfinite(coerced):
        raise ValueError("started_at must be a finite monotonic timestamp")
    return coerced


def summarize_live_integration_results(
    results: Sequence[Sequence[Any]],
    *,
    pass_status: str,
    fail_status: str,
    skip_status: str,
) -> dict[str, Any]:
    if isinstance(results, (str, bytes)):
        raise ValueError("results must be a sequence of result tuples")
    if not isinstance(results, Sequence):
        raise ValueError("results must be a sequence of result tuples")

    known_statuses = {pass_status, fail_status, skip_status}
    passed = 0
    failed = 0
    skipped = 0
    failed_checks: list[str] = []
    skipped_checks: list[str] = []

    for entry in results:
        if not isinstance(entry, Sequence) or isinstance(entry, (str, bytes)):
            raise ValueError("results entries must be tuples or lists")
        if len(entry) < 2:
            raise ValueError("results entries must include at least status and name")

        status = entry[0]
        name = entry[1]
        if not isinstance(status, str):
            raise ValueError("results status must be a string")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("results name must be a non-empty string")
        if status not in known_statuses:
            raise ValueError(
                "results status must match one of the configured pass/fail/skip markers"
            )

        if status == pass_status:
            passed += 1
        elif status == fail_status:
            failed += 1
            failed_checks.append(name)
        else:
            skipped += 1
            skipped_checks.append(name)

    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": len(results),
        "failed_checks": failed_checks,
        "skipped_checks": skipped_checks,
    }


def write_live_integration_summary(
    name: str,
    *,
    script: str,
    passed: int,
    failed: int,
    skipped: int = 0,
    total: int,
    elapsed_seconds: float,
    details: dict[str, Any] | None = None,
) -> Path:
    output_path = _coerce_registered_output_path(name, LIVE_INTEGRATION_SUMMARY_ARTIFACTS.get(name, Path()))

    passed_count = _coerce_non_negative_int("passed", passed)
    failed_count = _coerce_non_negative_int("failed", failed)
    skipped_count = _coerce_non_negative_int("skipped", skipped)
    total_count = _coerce_non_negative_int("total", total)
    if passed_count + failed_count + skipped_count != total_count:
        raise ValueError("total must equal passed + failed + skipped")

    payload = {
        "artifact": "live_integration_summary",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "name": name,
        "script": _coerce_registered_script_path(name, script),
        "passed": passed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "total": total_count,
        "elapsed_seconds": _coerce_elapsed_seconds(elapsed_seconds),
        "details": _coerce_details(details),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_live_integration_summary_from_results(
    name: str,
    *,
    script: str,
    results: Sequence[Sequence[Any]],
    started_at: float,
    pass_status: str,
    fail_status: str,
    skip_status: str,
    details: dict[str, Any] | None = None,
) -> Path:
    started_at_value = _coerce_monotonic_started_at(started_at)
    summary = summarize_live_integration_results(
        results,
        pass_status=pass_status,
        fail_status=fail_status,
        skip_status=skip_status,
    )
    merged_details = dict(details or {})
    merged_details.setdefault("failed_checks", summary["failed_checks"])
    merged_details.setdefault("skipped_checks", summary["skipped_checks"])
    return write_live_integration_summary(
        name,
        script=script,
        passed=summary["passed"],
        failed=summary["failed"],
        skipped=summary["skipped"],
        total=summary["total"],
        elapsed_seconds=time.perf_counter() - started_at_value,
        details=merged_details,
    )


def read_live_integration_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if payload.get("artifact") != "live_integration_summary":
        raise ValueError(f"{path} is not a live integration summary artifact")
    if not isinstance(payload.get("name"), str):
        raise ValueError("live integration summary missing string name")
    unexpected_keys = sorted(set(payload) - LIVE_INTEGRATION_SUMMARY_KEYS)
    if unexpected_keys:
        raise ValueError(
            f"live integration summary contains unexpected top-level keys: {', '.join(unexpected_keys)}"
        )

    resolved_path = _coerce_registered_output_path(payload["name"], path)
    passed_count = _coerce_non_negative_int("passed", payload.get("passed", 0))
    failed_count = _coerce_non_negative_int("failed", payload.get("failed", 0))
    skipped_count = _coerce_non_negative_int("skipped", payload.get("skipped", 0))
    total_count = _coerce_non_negative_int("total", payload.get("total", 0))
    if passed_count + failed_count + skipped_count != total_count:
        raise ValueError("live integration summary total must equal passed + failed + skipped")

    payload["name"] = payload["name"]
    payload["script"] = _coerce_registered_script_path(payload["name"], payload.get("script", ""))
    payload["generated_at"] = _coerce_generated_at(payload.get("generated_at"))
    payload["passed"] = passed_count
    payload["failed"] = failed_count
    payload["skipped"] = skipped_count
    payload["total"] = total_count
    payload["elapsed_seconds"] = _coerce_elapsed_seconds(payload.get("elapsed_seconds", 0.0))
    payload["details"] = _coerce_details(payload.get("details"))
    return payload
