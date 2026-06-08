from __future__ import annotations

import math
from typing import Any

from apps.api_server.compute.mojo_errors import build_mojo_engine_status


def _mojo_profiling_enabled_status(
    engine_type: str,
    *,
    engine_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "enabled",
        "engine_type": engine_type,
        "reason": None,
        "message": None,
        "engine_status": engine_status
        or build_mojo_engine_status(
            engine_type=engine_type,
            status="enabled",
            reason=None,
        ),
    }


def _mojo_profiling_disabled_status(
    engine_type: str,
    reason: str,
    *,
    message: str | None = None,
    engine_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "disabled",
        "engine_type": engine_type,
        "reason": reason,
        "message": message,
        "engine_status": engine_status
        or build_mojo_engine_status(
            engine_type=engine_type,
            status="disabled",
            reason=reason,
            message=message,
        ),
    }


def _mojo_profiling_status_from_result(
    result: dict[str, Any] | None,
    *,
    engine_type: str = "column_profile",
) -> dict[str, Any]:
    if not result:
        return _mojo_profiling_disabled_status(engine_type, "no_result")
    status = result.get("_profiling_status")
    if isinstance(status, dict):
        return {
            "status": str(status.get("status") or "disabled"),
            "engine_type": str(status.get("engine_type") or engine_type),
            "reason": status.get("reason"),
            "message": status.get("message"),
        }
    return _mojo_profiling_enabled_status(engine_type)


def _finite_numeric_samples(values: list[Any] | None, *, limit: int) -> list[float]:
    """Return up to ``limit`` finite numeric samples in stable input order."""
    samples: list[float] = []
    for value in values or []:
        if isinstance(value, bool):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric):
            continue
        samples.append(numeric)
        if len(samples) >= limit:
            break
    return samples


def _string_samples(values: list[Any] | None, *, limit: int) -> list[str]:
    """Return up to ``limit`` string samples in stable input order."""
    samples: list[str] = []
    for value in values or []:
        samples.append(str(value))
        if len(samples) >= limit:
            break
    return samples


def _build_mojo_column_profile_columns(
    profile: dict[str, dict[str, Any]],
    *,
    value_limit: int,
    string_limit: int,
    include_fill_rate: bool = False,
) -> dict[str, dict[str, Any]]:
    """
    Build a deterministic Mojo column-profile payload from profiled source metadata.

    ``values`` is restricted to finite numeric samples only. Mixed ``sample_values``
    can contain identifier-like strings that begin with digits, which the Mojo
    numeric parser can interpret as numbers and turn into invalid JSON stats.
    """
    payload: dict[str, dict[str, Any]] = {}
    for field, info in profile.items():
        fill_rate = float(info.get("fill_rate", 1.0) or 0.0)
        if fill_rate <= 0.0:
            continue

        entry: dict[str, Any] = {
            "values": _finite_numeric_samples(info.get("numeric"), limit=value_limit),
            "strings": _string_samples(info.get("strings"), limit=string_limit),
            "sample_size": int(info.get("total_count", 0) or 0),
        }
        if include_fill_rate:
            entry["fill_rate"] = fill_rate
        payload[field] = entry
    return payload


def _mojo_column_profile_sample_limits(column_count: int) -> tuple[int, int]:
    """
    Bound Mojo profiling payload size deterministically for wide schemas.

    Wide sources do not need the same per-column sample budget as narrow ones.
    Keeping the budget proportional to schema width reduces registration latency
    without changing the set of profiled columns.
    """
    if column_count >= 192:
        return 12, 12
    if column_count >= 96:
        return 16, 12
    if column_count >= 48:
        return 24, 16
    return 50, 50


def _mojo_column_profile_preflight_skip_reason(
    columns: dict[str, dict[str, Any]],
) -> str | None:
    """
    Return a deterministic skip reason when Mojo profiling is not worthwhile.

    Very small sources provide too little signal for Mojo profiling while still
    paying the full engine startup / IPC boundary cost. Skipping these payloads
    keeps first-touch behavior stable and relies on the existing Python path for
    equivalent profiling semantics.
    """
    sample_sizes = [max(int(column.get("sample_size", 0) or 0), 0) for column in columns.values()]
    if not sample_sizes:
        return "preflight_no_samples"

    max_sample_size = max(sample_sizes)
    total_sample_size = sum(sample_sizes)
    minimum_total = max(8, len(sample_sizes) * 2)
    if max_sample_size < 4 or total_sample_size < minimum_total:
        return "preflight_insufficient_samples"
    return None
