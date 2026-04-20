#!/usr/bin/env python3
"""
Exact-spec benchmark for the uploaded CSV corpus.

This exercises the production query path users hit after schema discovery:
  register sources -> exact /v1/query spec -> execute

It measures:
  - exact query correctness on real uploaded CSVs
  - cross-table exact query correctness
  - registration latency
  - query latency
"""

# ruff: noqa: E402

from __future__ import annotations

import asyncio
import json
import math
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from apps.api_server.routers.data_map import DataSource
from apps.api_server.routers.query import (
    _CACHE_LOCK,
    _DF_CACHE,
    _PLANNER_CACHE,
    _RESULT_CACHE,
    _SOURCE_CACHE,
    _VERIFY_CACHE,
    JoinEdgeSpec,
    JoinPathSpec,
    QueryRequest,
    query_sources,
)
from apps.api_server.routers.sources import RegisterRequest, register_source
from apps.api_server.services import source_registry as reg
from apps.api_server.services.auto_planner import AutoPlanner

SOURCE_FILES: dict[str, Path] = {
    "BookingsNew": ROOT / "test_files" / "bookings_new.csv",
    "POSNew": ROOT / "test_files" / "pos_new.csv",
    "QuotesNew": ROOT / "test_files" / "quotes_new.csv",
    "Inventory": ROOT / "test_files" / "Available_Inventory.csv",
    "Backlog": ROOT / "test_files" / "Backlog.csv",
}

_API_RESULT_PRECISION = 4


@dataclass(frozen=True)
class ExactQueryCase:
    label: str
    description: str
    source_name: str
    metric_column: str
    group_source: str | None
    group_column: str | None
    edges: tuple[tuple[str, str, str, str], ...]
    aggregation: str = "sum"


def _normalize_result(result: Any) -> Any:
    if isinstance(result, list):
        rows = [
            {
                "group": str(item["group"]),
                "value": round(float(item["value"]), _API_RESULT_PRECISION),
            }
            for item in result
        ]
        rows.sort(key=lambda item: (-item["value"], item["group"]))
        return rows
    if isinstance(result, int | float):
        return round(float(result), _API_RESULT_PRECISION)
    return result


def _group_rows(
    rows: list[dict[str, Any]],
    value_col: str,
    group_col: str,
    agg: str,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[float]] = {}
    for row in rows:
        group = _blankish_value(row.get(group_col))
        value = row.get(value_col)
        if not group or not isinstance(value, int | float) or not math.isfinite(float(value)):
            continue
        buckets.setdefault(group, []).append(float(value))

    out: list[dict[str, Any]] = []
    for group, values in buckets.items():
        if agg == "sum":
            value = sum(values)
        elif agg == "avg":
            value = sum(values) / len(values)
        elif agg == "count":
            value = float(len(values))
        else:
            raise ValueError(f"Unsupported aggregate: {agg}")
        out.append({"group": group, "value": round(value, _API_RESULT_PRECISION)})
    out.sort(key=lambda item: (-item["value"], item["group"]))
    return out


def _stable_group_map(
    rows: list[dict[str, Any]],
    join_key_col: str,
    group_col: str,
) -> tuple[dict[str, str], set[str]]:
    mapping: dict[str, str] = {}
    conflicts: set[str] = set()

    for row in rows:
        join_key = _blankish_value(row.get(join_key_col))
        group = _blankish_value(row.get(group_col))
        if not join_key or not group:
            continue
        existing = mapping.get(join_key)
        if existing is None:
            mapping[join_key] = group
            continue
        if existing != group:
            conflicts.add(join_key)

    for join_key in conflicts:
        mapping.pop(join_key, None)
    return mapping, conflicts


def _join_group_rows(
    metric_rows: list[dict[str, Any]],
    metric_col: str,
    metric_join_col: str,
    group_rows: list[dict[str, Any]],
    group_join_col: str,
    group_col: str,
    agg: str,
) -> tuple[list[dict[str, Any]], int, int]:
    join_map, conflicts = _stable_group_map(group_rows, group_join_col, group_col)
    buckets: dict[str, list[float]] = {}
    matched_rows = 0

    for row in metric_rows:
        join_key = _blankish_value(row.get(metric_join_col))
        if not join_key or join_key in conflicts:
            continue
        group = join_map.get(join_key)
        value = row.get(metric_col)
        if group is None or not isinstance(value, int | float) or not math.isfinite(float(value)):
            continue
        matched_rows += 1
        buckets.setdefault(group, []).append(float(value))

    out: list[dict[str, Any]] = []
    for group, values in buckets.items():
        if agg == "sum":
            value = sum(values)
        elif agg == "avg":
            value = sum(values) / len(values)
        elif agg == "count":
            value = float(len(values))
        else:
            raise ValueError(f"Unsupported aggregate: {agg}")
        out.append({"group": group, "value": round(value, _API_RESULT_PRECISION)})
    out.sort(key=lambda item: (-item["value"], item["group"]))
    return out, matched_rows, len(conflicts)


def _build_cases() -> list[ExactQueryCase]:
    return [
        ExactQueryCase(
            label="Q1",
            description="Bookings revenue by ship-to state",
            source_name="BookingsNew",
            metric_column="EXT_PRICE",
            group_source="BookingsNew",
            group_column="SHIP_TO_STATE",
            edges=(),
        ),
        ExactQueryCase(
            label="Q2",
            description="POS revenue by ship-to country",
            source_name="POSNew",
            metric_column="EXT_PRICE",
            group_source="POSNew",
            group_column="SHIP_TO_COUNTRY",
            edges=(),
        ),
        ExactQueryCase(
            label="Q3",
            description="Quotes revenue by status",
            source_name="QuotesNew",
            metric_column="EXT_PRICE",
            group_source="QuotesNew",
            group_column="STATUS",
            edges=(),
        ),
        ExactQueryCase(
            label="Q4",
            description="Inventory extended cost by warehouse",
            source_name="Inventory",
            metric_column="EXT_COST",
            group_source="Inventory",
            group_column="Warehouse",
            edges=(),
        ),
        ExactQueryCase(
            label="Q5",
            description="Backlog extended price by sales office",
            source_name="Backlog",
            metric_column="EXT_PRICE",
            group_source="Backlog",
            group_column="Sales Office",
            edges=(),
        ),
        ExactQueryCase(
            label="Q6",
            description="Bookings revenue by POS inventory type",
            source_name="BookingsNew",
            metric_column="EXT_PRICE",
            group_source="POSNew",
            group_column="INVENTORY_TYPE",
            edges=(("BookingsNew", "ORDER_NUMBER", "POSNew", "ORDER_NUMBER"),),
        ),
        ExactQueryCase(
            label="Q7",
            description="Quotes revenue by inventory product line",
            source_name="QuotesNew",
            metric_column="EXT_PRICE",
            group_source="Inventory",
            group_column="Product Line",
            edges=(("QuotesNew", "PART_NUMBER", "Inventory", "PART_NUMBER"),),
        ),
        ExactQueryCase(
            label="Q8",
            description="Quotes revenue by POS inventory type",
            source_name="QuotesNew",
            metric_column="EXT_PRICE",
            group_source="POSNew",
            group_column="INVENTORY_TYPE",
            edges=(("QuotesNew", "PART_NUMBER", "POSNew", "PART_NUMBER"),),
        ),
        ExactQueryCase(
            label="Q9",
            description="Backlog extended price by POS inventory type",
            source_name="Backlog",
            metric_column="EXT_PRICE",
            group_source="POSNew",
            group_column="INVENTORY_TYPE",
            edges=(("Backlog", "PART_NUMBER", "POSNew", "PART_NUMBER"),),
        ),
        ExactQueryCase(
            label="Q10",
            description="Backlog extended price by POS on-hand vendor name",
            source_name="Backlog",
            metric_column="EXT_PRICE",
            group_source="POSNew",
            group_column="OHVENDNAME",
            edges=(("Backlog", "PART_NUMBER", "POSNew", "PART_NUMBER"),),
        ),
    ]


async def _reset_runtime_state(registry_dir: Path) -> None:
    reg._SOURCES_DIR = registry_dir
    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()
    _RESULT_CACHE.clear()
    _VERIFY_CACHE.clear()
    _DF_CACHE.clear()


def _blankish_value(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            return None
        if v.is_integer():
            return str(int(v))
        return str(v)
    text = str(v).strip()
    if not text or text.lower() in {"?", "none", "null", "nan"}:
        return None
    return text


def _expected_result(
    case: ExactQueryCase,
    tables: dict[str, list[dict[str, Any]]],
) -> tuple[Any, dict[str, Any]]:
    metric_rows = tables[case.source_name]
    if not case.group_source or not case.group_column:
        values = [
            float(row[case.metric_column])
            for row in metric_rows
            if isinstance(row.get(case.metric_column), int | float)
        ]
        if case.aggregation == "sum":
            return round(sum(values), _API_RESULT_PRECISION), {
                "matched_rows": len(values),
                "conflicts": 0,
            }
        raise ValueError(f"Unsupported scalar aggregate: {case.aggregation}")

    if not case.edges:
        return _group_rows(metric_rows, case.metric_column, case.group_column, case.aggregation), {
            "matched_rows": sum(
                1
                for row in metric_rows
                if isinstance(row.get(case.metric_column), int | float)
                and str(row.get(case.group_column, "")).strip()
            ),
            "conflicts": 0,
        }

    if len(case.edges) != 1:
        raise ValueError("uploaded_csv_exact_benchmark currently supports one-hop exact cases only")

    _, metric_join_col, _, group_join_col = case.edges[0]
    result, matched_rows, conflicts = _join_group_rows(
        metric_rows=metric_rows,
        metric_col=case.metric_column,
        metric_join_col=metric_join_col,
        group_rows=tables[case.group_source],
        group_join_col=group_join_col,
        group_col=case.group_column,
        agg=case.aggregation,
    )
    return result, {"matched_rows": matched_rows, "conflicts": conflicts}


def _ensure_case_tables(planner: AutoPlanner, case: ExactQueryCase) -> None:
    planner._ensure_records(case.source_name)
    if case.group_source:
        planner._ensure_records(case.group_source)


async def _run() -> dict[str, Any]:
    cases = _build_cases()

    with tempfile.TemporaryDirectory() as tmp_dir:
        workdir = Path(tmp_dir)
        registry_dir = workdir / "registry"
        await _reset_runtime_state(registry_dir)

        org_id = f"uploaded_csv_exact_{int(time.time())}"
        auth = {"org_id": org_id, "role": "owner", "key_id": str(uuid.uuid4())}
        register_latencies: list[float] = []

        for source_name, path in SOURCE_FILES.items():
            payload = RegisterRequest(
                source=DataSource(
                    name=source_name,
                    csv=path.read_text(encoding="utf-8", errors="replace"),
                )
            )
            t0 = time.perf_counter()
            resp = await register_source(payload, auth=auth)
            register_latencies.append((time.perf_counter() - t0) * 1000)
            if resp["status"] not in {"registered", "already_registered"}:
                raise RuntimeError(f"registration failed for {source_name}: {resp}")

        planner = AutoPlanner.from_registry(org_id, llm_policy="never")
        query_latencies: list[float] = []
        cross_latencies: list[float] = []
        passed = 0
        cross_passed = 0
        cross_total = 0
        details: list[dict[str, Any]] = []

        for case in cases:
            _ensure_case_tables(planner, case)
            expected, expected_meta = _expected_result(case, planner.tables)
            join_path = None
            if case.edges:
                join_path = JoinPathSpec(
                    base_source=case.source_name,
                    group_source=case.group_source,
                    edges=[
                        JoinEdgeSpec(
                            left_source=left_source,
                            left_key=left_key,
                            right_source=right_source,
                            right_key=right_key,
                            allow_many_to_many=True,
                        )
                        for left_source, left_key, right_source, right_key in case.edges
                    ],
                    reject_on_fanout=False,
                    reject_on_ambiguity=True,
                )

            request = QueryRequest(
                source_name=case.source_name,
                metric_column=case.metric_column,
                group_column=case.group_column,
                join_path=join_path,
                aggregation=case.aggregation,
                limit=None,
                order="desc",
            )

            t0 = time.perf_counter()
            response = await query_sources(request, auth=auth)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            query_latencies.append(elapsed_ms)
            if case.edges:
                cross_latencies.append(elapsed_ms)
                cross_total += 1

            actual = _normalize_result(response.result)
            expected_norm = _normalize_result(expected)
            ok = actual == expected_norm
            passed += int(ok)
            cross_passed += int(ok and bool(case.edges))

            details.append({
                "label": case.label,
                "description": case.description,
                "cross_source": bool(case.edges),
                "ok": ok,
                "latency_ms": round(elapsed_ms, 3),
                "row_count": response.row_count,
                "matched_rows_expected": expected_meta["matched_rows"],
                "conflicting_group_keys": expected_meta["conflicts"],
                "actual_result": actual,
                "expected_result": expected_norm,
                "plan_tail": response.plan[-5:],
            })

        return {
            "benchmark": "uploaded_csv_exact_query_benchmark",
            "sources": list(SOURCE_FILES.keys()),
            "queries": len(cases),
            "cross_source_queries": cross_total,
            "query_accuracy": round(passed / len(cases), 4),
            "cross_source_accuracy": round(cross_passed / max(cross_total, 1), 4),
            "avg_register_ms": round(sum(register_latencies) / len(register_latencies), 3),
            "avg_query_ms": round(sum(query_latencies) / len(query_latencies), 3),
            "avg_cross_query_ms": round(sum(cross_latencies) / max(len(cross_latencies), 1), 3),
            "max_query_ms": round(max(query_latencies), 3),
            "details": details,
        }


def main() -> None:
    started = time.perf_counter()
    summary = asyncio.run(_run())
    elapsed_ms = (time.perf_counter() - started) * 1000
    summary["elapsed_ms"] = round(elapsed_ms, 3)

    print("\nUploaded CSV Exact Query Benchmark")
    print("=" * 72)
    print(json.dumps({
        "queries": summary["queries"],
        "cross_source_queries": summary["cross_source_queries"],
        "query_accuracy": summary["query_accuracy"],
        "cross_source_accuracy": summary["cross_source_accuracy"],
        "avg_register_ms": summary["avg_register_ms"],
        "avg_query_ms": summary["avg_query_ms"],
        "avg_cross_query_ms": summary["avg_cross_query_ms"],
        "max_query_ms": summary["max_query_ms"],
    }, indent=2))
    print()
    for item in summary["details"]:
        status = "PASS" if item["ok"] else "FAIL"
        scope = "cross" if item["cross_source"] else "single"
        print(
            f"{item['label']:<4} {status:<4} {scope:<6} "
            f"{item['latency_ms']:>7.1f}ms  rows={item['row_count']:<6}  "
            f"{item['description']}"
        )
    print(f"\nElapsed: {elapsed_ms:.1f}ms")


if __name__ == "__main__":
    main()
