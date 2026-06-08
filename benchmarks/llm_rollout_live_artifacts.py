from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = PROJECT_ROOT / "build"

LIVE_SUMMARY_ARTIFACTS: dict[str, Path] = {
    "python_sdk_local_runtime": BUILD_DIR / "python_sdk_local_runtime_live_summary.json",
    "typescript_sdk_local_runtime": BUILD_DIR / "typescript_sdk_local_runtime_live_summary.json",
    "local_runtime_cli_mcp_matrix": BUILD_DIR / "local_runtime_cli_mcp_matrix_live_summary.json",
    "public_http_library_routes_feature_flag_live": BUILD_DIR
    / "public_http_library_routes_feature_flag_live_live_summary.json",
}

LIVE_SUMMARY_SCRIPTS: dict[str, str] = {
    "python_sdk_local_runtime": "tests/integration/test_algenta_mojo_library_live.py",
    "typescript_sdk_local_runtime": "tests/integration/test_typescript_runtime_live.py",
    "local_runtime_cli_mcp_matrix": "tests/integration/test_cli_mcp_runtime_libraries_live.py",
    "public_http_library_routes_feature_flag_live": (
        "tests/integration/test_runtime_libraries_http_live.py"
    ),
}

RESERVED_SUMMARY_KEYS = {
    "artifact",
    "generated_at",
    "name",
    "script",
    "channels",
    "minimum_passed",
    "passed",
    "failed",
    "skipped",
    "elapsed_seconds",
    "status",
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


def _coerce_registered_output_path(suite_name: str, output_path: Path) -> Path:
    try:
        expected = LIVE_SUMMARY_ARTIFACTS[suite_name]
    except KeyError as exc:
        raise ValueError(f"unknown rollout live summary name: {suite_name}") from exc
    if output_path.resolve() != expected.resolve():
        raise ValueError(f"output_path must match registered artifact path: {expected}")
    return output_path


def _coerce_registered_script_path(suite_name: str, script: str) -> str:
    try:
        expected = LIVE_SUMMARY_SCRIPTS[suite_name]
    except KeyError as exc:
        raise ValueError(f"unknown rollout live summary name: {suite_name}") from exc
    normalized = _coerce_script_path(script)
    if normalized != expected:
        raise ValueError(f"script must match registered suite script: {expected}")
    return normalized


def _coerce_channels(channels: Sequence[str]) -> list[str]:
    if isinstance(channels, (str, bytes)):
        raise ValueError("channels must be a sequence of channel names, not a single string")
    if not isinstance(channels, (list, tuple)):
        raise ValueError("channels must be a list or tuple of channel names")
    coerced: list[str] = []
    for channel in channels:
        if not isinstance(channel, str):
            raise ValueError("channels must contain only strings")
        normalized = channel.strip()
        if not normalized:
            raise ValueError("channels must not contain blank names")
        coerced.append(normalized)
    if not coerced:
        raise ValueError("channels must not be empty")
    if len(set(coerced)) != len(coerced):
        raise ValueError("channels must be unique")
    return coerced


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


def _coerce_extra(value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("extra must be a dict")
    _validate_json_metadata_shape(
        value,
        key_error_message="extra must use only string keys",
        tuple_error_message="extra must not contain tuples",
    )
    overlap = sorted(RESERVED_SUMMARY_KEYS.intersection(value))
    if overlap:
        raise ValueError(f"extra must not override reserved keys: {', '.join(overlap)}")
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("extra must be JSON-serializable with finite values") from exc
    return value


def write_live_summary_artifact(
    *,
    output_path: Path,
    suite_name: str,
    script: str,
    channels: Sequence[str],
    minimum_passed: int,
    passed: int,
    failed: int,
    skipped: int,
    elapsed_seconds: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_output_path = _coerce_registered_output_path(suite_name, output_path)
    minimum_passed_count = _coerce_non_negative_int("minimum_passed", minimum_passed)
    passed_count = _coerce_non_negative_int("passed", passed)
    failed_count = _coerce_non_negative_int("failed", failed)
    skipped_count = _coerce_non_negative_int("skipped", skipped)
    if minimum_passed_count > passed_count + failed_count + skipped_count:
        raise ValueError("minimum_passed must be <= passed + failed + skipped")

    payload: dict[str, Any] = {
        "artifact": "llm_rollout_live_summary",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "name": suite_name,
        "script": _coerce_registered_script_path(suite_name, script),
        "channels": _coerce_channels(channels),
        "minimum_passed": minimum_passed_count,
        "passed": passed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "elapsed_seconds": _coerce_elapsed_seconds(elapsed_seconds),
        "status": (
            "passed"
            if failed_count == 0 and passed_count >= minimum_passed_count
            else "failed"
        ),
    }
    payload.update(_coerce_extra(extra))
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return payload


def read_live_summary_artifact(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if payload.get("artifact") != "llm_rollout_live_summary":
        raise ValueError(f"{path} is not an llm rollout live summary artifact")
    if not isinstance(payload.get("name"), str):
        raise ValueError("llm rollout live summary missing string name")

    _coerce_registered_output_path(payload["name"], path)
    payload["script"] = _coerce_registered_script_path(payload["name"], payload.get("script", ""))
    payload["generated_at"] = _coerce_generated_at(payload.get("generated_at"))
    minimum_passed_count = _coerce_non_negative_int("minimum_passed", payload.get("minimum_passed", 0))
    passed_count = _coerce_non_negative_int("passed", payload.get("passed", 0))
    failed_count = _coerce_non_negative_int("failed", payload.get("failed", 0))
    skipped_count = _coerce_non_negative_int("skipped", payload.get("skipped", 0))
    if minimum_passed_count > passed_count + failed_count + skipped_count:
        raise ValueError("llm rollout live summary minimum_passed exceeds total outcomes")

    payload["channels"] = _coerce_channels(payload.get("channels", ()))
    payload["minimum_passed"] = minimum_passed_count
    payload["passed"] = passed_count
    payload["failed"] = failed_count
    payload["skipped"] = skipped_count
    payload["elapsed_seconds"] = _coerce_elapsed_seconds(payload.get("elapsed_seconds", 0.0))
    expected_status = "passed" if failed_count == 0 and passed_count >= minimum_passed_count else "failed"
    if payload.get("status") != expected_status:
        raise ValueError("llm rollout live summary status does not match outcome counts")
    extra = _coerce_extra({key: value for key, value in payload.items() if key not in RESERVED_SUMMARY_KEYS})
    payload.update(extra)
    return payload
