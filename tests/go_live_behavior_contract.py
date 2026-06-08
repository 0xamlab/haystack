from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetricBudget:
    severity: str
    p95: float | None = None
    p99: float | None = None


P0_METRIC_BUDGETS: dict[str, MetricBudget] = {
    "resolve_hit_ms": MetricBudget(severity="P0", p95=3.0, p99=5.0),
    "exact_hit_ms": MetricBudget(severity="P0", p95=5.0, p99=10.0),
    "failure_response_ms": MetricBudget(severity="P0", p95=200.0, p99=400.0),
}

P1_METRIC_BUDGETS: dict[str, MetricBudget] = {
    # total_request_ms covers warmed source registration plus the first exact
    # query on real public connectors, so it must tolerate bounded external
    # object/API variance beyond the isolated fetch and query budgets below.
    "total_request_ms": MetricBudget(severity="P1", p95=450.0, p99=700.0),
    "first_query_total_ms": MetricBudget(severity="P1", p95=200.0, p99=350.0),
    "failure_response_ms.neo4j_connector_test": MetricBudget(severity="P1", p95=600.0, p99=900.0),
    "fetch_ms.rest_single_dataset": MetricBudget(severity="P1", p95=200.0, p99=400.0),
    "fetch_ms.object_single": MetricBudget(severity="P1", p95=300.0, p99=500.0),
    "fetch_ms.warehouse_fixture": MetricBudget(severity="P1", p95=300.0, p99=500.0),
    "fetch_ms.clickhouse_cloud_fixture": MetricBudget(severity="P1", p95=600.0, p99=900.0),
    "fetch_ms.paginated_rest": MetricBudget(severity="P1", p95=500.0, p99=800.0),
}

P2_METRIC_BUDGETS: dict[str, MetricBudget] = {
    "metadata_register_ms": MetricBudget(severity="P2", p95=50.0, p99=100.0),
    "full_register_prewarm_ms.small": MetricBudget(severity="P2", p95=300.0),
    "full_register_prewarm_ms.medium": MetricBudget(severity="P2", p95=500.0),
    "full_register_prewarm_ms.large": MetricBudget(severity="P2", p95=1500.0),
    "source_matrix.avg_source_ms": MetricBudget(severity="P2", p95=150.0),
    "source_matrix.p95_source_total_ms": MetricBudget(severity="P2", p95=500.0),
}


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil((pct / 100.0) * len(ordered)) - 1)
    return float(ordered[min(rank, len(ordered) - 1)])


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and math.isnan(value):
            return "NaN"
        return value
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in sorted(value.items())}
    return str(value)


def _stable_json(value: Any) -> str:
    return json.dumps(_json_ready(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ordered_rows(
    records: list[dict[str, Any]],
    identity_columns: tuple[str, ...] = (),
    *,
    sample_size: int = 256,
) -> list[dict[str, Any]]:
    canonical_rows = [
        {str(key): _json_ready(value) for key, value in sorted(row.items())}
        for row in records
        if isinstance(row, dict)
    ]
    if identity_columns and all(
        all(column in row for column in identity_columns) for row in canonical_rows
    ):
        ordered = sorted(
            canonical_rows,
            key=lambda row: tuple(_stable_json(row.get(column)) for column in identity_columns),
        )
    else:
        ordered = sorted(canonical_rows, key=_stable_json)
    return ordered[:sample_size]


def schema_fingerprint(columns: list[dict[str, Any]]) -> str:
    fingerprint_payload = [
        {
            "name": str(column.get("name", "")),
            "physical_type": str(column.get("physical_type", "")),
        }
        for column in columns
    ]
    return _hash_text(_stable_json(fingerprint_payload))


def strict_sample_hash(
    records: list[dict[str, Any]],
    identity_columns: tuple[str, ...] = (),
    *,
    sample_size: int = 256,
) -> str:
    ordered_rows = _ordered_rows(records, identity_columns, sample_size=sample_size)
    return _hash_text(_stable_json(ordered_rows))


def build_distribution_sketch(
    records: list[dict[str, Any]],
    identity_columns: tuple[str, ...] = (),
    *,
    sample_size: int = 256,
    sample_values_per_column: int = 32,
) -> dict[str, Any]:
    ordered_rows = _ordered_rows(records, identity_columns, sample_size=sample_size)
    columns = sorted({key for row in ordered_rows for key in row})
    column_stats: dict[str, dict[str, Any]] = {}
    for column in columns:
        values = [row.get(column) for row in ordered_rows]
        non_null = [value for value in values if value is not None and value != ""]
        distinct_hashes = sorted({_hash_text(_stable_json(value)) for value in non_null})
        column_stats[column] = {
            "non_null_count": len(non_null),
            "distinct_count": len(distinct_hashes),
            "sample_hashes": distinct_hashes[:sample_values_per_column],
        }
    identity_hashes: list[str] = []
    if identity_columns and all(
        all(column in row for column in identity_columns) for row in ordered_rows
    ):
        identity_hashes = [
            _hash_text("|".join(_stable_json(row.get(column)) for column in identity_columns))
            for row in ordered_rows[:sample_values_per_column]
        ]
    return {
        "row_count": len(records),
        "sample_count": len(ordered_rows),
        "columns": column_stats,
        "identity_hashes": identity_hashes,
    }


def row_count_delta_ratio(left_count: int, right_count: int) -> float:
    baseline = max(left_count, right_count, 1)
    return abs(left_count - right_count) / baseline


def within_row_count_tolerance(
    left_count: int, right_count: int, tolerance: float
) -> tuple[bool, str]:
    delta_ratio = row_count_delta_ratio(left_count, right_count)
    if delta_ratio <= tolerance:
        return True, ""
    return (
        False,
        f"row_count drift {left_count} vs {right_count} exceeded tolerance {tolerance:.3f}",
    )


def ensure_no_identity_duplicates(
    records: list[dict[str, Any]],
    identity_columns: tuple[str, ...],
) -> tuple[bool, str]:
    if not identity_columns:
        return True, ""
    seen: set[tuple[str, ...]] = set()
    for row in records:
        if not all(column in row for column in identity_columns):
            return False, f"identity columns missing from records: {identity_columns}"
        key = tuple(_stable_json(row.get(column)) for column in identity_columns)
        if key in seen:
            return False, f"duplicate identity encountered for columns {identity_columns}: {key}"
        seen.add(key)
    return True, ""


def _hash_overlap(left_hashes: list[str], right_hashes: list[str]) -> float:
    left_set = set(left_hashes)
    right_set = set(right_hashes)
    if not left_set and not right_set:
        return 1.0
    union = left_set | right_set
    if not union:
        return 1.0
    return len(left_set & right_set) / len(union)


def distribution_sketch_within_tolerance(
    left: dict[str, Any],
    right: dict[str, Any],
    tolerance: float,
) -> tuple[bool, str]:
    if set(left.get("columns", {})) != set(right.get("columns", {})):
        return False, "distribution sketch columns changed between runs"
    row_count_ok, message = within_row_count_tolerance(
        int(left.get("row_count", 0) or 0),
        int(right.get("row_count", 0) or 0),
        tolerance,
    )
    if not row_count_ok:
        return False, message
    sample_count = max(
        int(left.get("sample_count", 0) or 0),
        int(right.get("sample_count", 0) or 0),
        1,
    )
    overlap_floor = max(0.5, 1.0 - max(tolerance * 2.0, 0.10))
    for column in sorted(left.get("columns", {})):
        left_stats = left["columns"][column]
        right_stats = right["columns"][column]
        non_null_delta = abs(
            (int(left_stats.get("non_null_count", 0) or 0) / sample_count)
            - (int(right_stats.get("non_null_count", 0) or 0) / sample_count)
        )
        if non_null_delta > tolerance:
            return False, f"non-null drift for column '{column}' exceeded tolerance {tolerance:.3f}"
        distinct_delta = abs(
            (int(left_stats.get("distinct_count", 0) or 0) / sample_count)
            - (int(right_stats.get("distinct_count", 0) or 0) / sample_count)
        )
        if distinct_delta > tolerance:
            return (
                False,
                f"distinct-count drift for column '{column}' exceeded tolerance {tolerance:.3f}",
            )
        sample_overlap = _hash_overlap(
            list(left_stats.get("sample_hashes", []) or []),
            list(right_stats.get("sample_hashes", []) or []),
        )
        if sample_overlap < overlap_floor:
            return (
                False,
                f"sample-value drift for column '{column}' exceeded overlap floor {overlap_floor:.2f}",
            )
    identity_overlap = _hash_overlap(
        list(left.get("identity_hashes", []) or []),
        list(right.get("identity_hashes", []) or []),
    )
    if identity_overlap < overlap_floor:
        return False, f"identity drift exceeded overlap floor {overlap_floor:.2f}"
    return True, ""


def summarize_metric_series(values: list[float], budget: MetricBudget) -> dict[str, Any]:
    p95 = round(percentile(values, 95), 3) if values else 0.0
    p99 = round(percentile(values, 99), 3) if values else 0.0
    ok = True
    if budget.p95 is not None and p95 > budget.p95:
        ok = False
    if budget.p99 is not None and p99 > budget.p99:
        ok = False
    return {
        "severity": budget.severity,
        "count": len(values),
        "p95": p95,
        "p99": p99,
        "budget_p95": budget.p95,
        "budget_p99": budget.p99,
        "ok": ok,
    }
