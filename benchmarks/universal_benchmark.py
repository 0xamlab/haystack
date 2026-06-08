#!/usr/bin/env python3
"""
Universal synthetic benchmark for enterprise-grade schema generalization.

Goals:
- avoid industry-specific fixtures
- exercise the registry path users hit in local / API / MCP flows
- score the same corpus across CSV, Parquet, and SQLite backends
- report import integrity, resolver correctness, join correctness, query correctness, and latency
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import random
import re
import sqlite3
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class QueryCase:
    label: str
    metric_hint: str
    dim_hint: str | None
    agg: str
    preferred_source: str
    expected_metric: tuple[str, str]
    expected_group: tuple[str, str] | None
    expected_hops: tuple[tuple[str, str, str, str], ...]
    expected_result: Any


@dataclass(frozen=True)
class IngestCheck:
    label: str
    source: str
    row_index: int
    field: str
    expected_type: str
    expected_value: Any


_API_RESULT_PRECISION = 4
_SQLITE_TABLE_NAME_RE = re.compile(r"^[a-z0-9_]+$")


@lru_cache(maxsize=1)
def _runtime_modules() -> dict[str, Any]:
    from apps.api_server.routers.data_map import DataSource
    from apps.api_server.routers.query import (
        _CACHE_LOCK,
        _DF_CACHE,
        _RESULT_CACHE,
        _SOURCE_CACHE,
        _VERIFY_CACHE,
    )
    from apps.api_server.routers.sources import RegisterRequest, register_source
    from apps.api_server.services import source_registry as reg
    from apps.api_server.services.auto_planner import AutoPlanner

    return {
        "DataSource": DataSource,
        "RegisterRequest": RegisterRequest,
        "register_source": register_source,
        "source_registry": reg,
        "AutoPlanner": AutoPlanner,
        "cache_lock": _CACHE_LOCK,
        "df_cache": _DF_CACHE,
        "result_cache": _RESULT_CACHE,
        "source_cache": _SOURCE_CACHE,
        "verify_cache": _VERIFY_CACHE,
    }


def _sqlite_table_name(name: str) -> str:
    table_name = f"t_{name.lower()}"
    if not _SQLITE_TABLE_NAME_RE.fullmatch(table_name):
        raise ValueError(f"Invalid sqlite table name derived from source {name!r}")
    return table_name


def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _rows_to_parquet_b64(rows: list[dict[str, Any]]) -> str:
    arrays: dict[str, pa.Array] = {}
    for key in rows[0].keys():
        values = [row.get(key) for row in rows]
        try:
            arrays[key] = pa.array(values)
        except Exception:
            arrays[key] = pa.array(
                [str(value) if value is not None else None for value in values],
                type=pa.string(),
            )
    table = pa.table(arrays)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return base64.b64encode(buf.getvalue()).decode()


def _normalize_result(result: Any) -> Any:
    if isinstance(result, list):
        return [
            {
                "group": str(item["group"]),
                "value": round(float(item["value"]), _API_RESULT_PRECISION),
            }
            for item in result
        ]
    if isinstance(result, int | float):
        return round(float(result), _API_RESULT_PRECISION)
    return result


def _ingest_value_matches(actual: Any, expected_type: str, expected_value: Any) -> bool:
    if expected_type == "str":
        return isinstance(actual, str) and actual == expected_value
    if expected_type == "float":
        return (
            isinstance(actual, int | float)
            and not isinstance(actual, bool)
            and abs(float(actual) - float(expected_value)) <= 1e-9
        )
    if expected_type == "int":
        return isinstance(actual, int) and not isinstance(actual, bool) and actual == expected_value
    return type(actual).__name__ == expected_type and actual == expected_value


def _group_rows(
    rows: list[dict[str, Any]],
    value_col: str,
    group_col: str,
    agg: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        group = str(row[group_col])
        grouped.setdefault(group, []).append(float(row[value_col]))

    out: list[dict[str, Any]] = []
    for group, values in grouped.items():
        if agg == "sum":
            value = sum(values)
        elif agg == "avg":
            value = sum(values) / len(values)
        elif agg == "count":
            value = float(len(values))
        else:
            raise ValueError(f"Unsupported aggregate: {agg}")
        out.append({"group": group, "value": round(value, 6)})
    out.sort(key=lambda item: (-item["value"], item["group"]))
    return out


def _scalar_value(rows: list[dict[str, Any]], value_col: str, agg: str) -> float:
    values = [float(row[value_col]) for row in rows]
    if agg == "sum":
        return round(sum(values), 6)
    if agg == "avg":
        return round(sum(values) / len(values), 6)
    if agg == "count":
        return round(float(len(values)), 6)
    raise ValueError(f"Unsupported aggregate: {agg}")


def _generate_sources() -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(7)
    s0: list[dict[str, Any]] = []
    s1: list[dict[str, Any]] = []
    s2: list[dict[str, Any]] = []
    s3: list[dict[str, Any]] = []

    entity_map: dict[str, tuple[str, str]] = {}
    bridge_map: dict[str, tuple[str, str]] = {}
    region_map: dict[str, tuple[str, str]] = {}

    groups = ["g_a", "g_b", "g_c", "g_d"]
    segments = ["seg_1", "seg_2", "seg_3"]
    regions = [
        ("region_east", "country_us"),
        ("region_west", "country_ca"),
        ("region_south", "country_mx"),
    ]

    for i in range(240):
        entity_key = f"e_{i:04d}"
        bridge_key = f"bridge_{i % 12:03d}"
        local_group = groups[i % len(groups)]
        quantity = float((i % 9) + 1)
        unit_rate = round(10 + (i % 17) * 1.75, 2)
        measure_total = round(quantity * unit_rate, 2)

        segment = segments[i % len(segments)]
        geo_key = f"geo_{i % 24:03d}"
        region, country = regions[i % len(regions)]
        entity_map[entity_key] = (segment, bridge_key)
        bridge_map.setdefault(bridge_key, (geo_key, f"label_{rng.randint(1, 4)}"))
        region_map[geo_key] = (region, country)

        s0.append(
            {
                "entity_key": entity_key,
                "local_group": local_group,
                "quantity": quantity,
                "unit_rate": unit_rate,
                "measure_total": measure_total,
            }
        )

    for entity_key, (segment, bridge_key) in entity_map.items():
        s1.append(
            {
                "entity_key": entity_key,
                "segment_label": segment,
                "bridge_key": bridge_key,
            }
        )

    for geo_key, (region, country) in region_map.items():
        s2.append(
            {
                "geo_key": geo_key,
                "region_label": region,
                "country_code": country,
            }
        )

    for bridge_key, (geo_key, bridge_label) in bridge_map.items():
        s3.append(
            {
                "bridge_key": bridge_key,
                "geo_key": geo_key,
                "bridge_label": bridge_label,
            }
        )

    c0: list[dict[str, Any]] = []
    cats = ["Alpha", "Beta", "Gamma", "Delta"]
    for i in range(200):
        qty_i = float((i % 8) + 1)
        unit_cost = round(5.0 + (i % 20) * 0.75, 2)
        oh_rate = round(0.12 + (i % 5) * 0.02, 4)
        oh_cost = round(unit_cost * oh_rate, 2)
        ext_cost = round(unit_cost * qty_i, 2)
        c0.append(
            {
                "item_id": f"item_{i:04d}",
                "category": cats[i % len(cats)],
                "qty": qty_i,
                "UNIT_COST": unit_cost,
                "OH_COST": oh_cost,
                "EXT_COST": ext_cost,
            }
        )

    i0 = [
        {
            "account_code": "00123",
            "serial_number": "00004567",
            "zip_code": "02139",
            "local_group": "g_a",
            "measure_total": 10.0,
        },
        {
            "account_code": "00124",
            "serial_number": "00004568",
            "zip_code": "60601",
            "local_group": "g_b",
            "measure_total": 15.0,
        },
        {
            "account_code": "00125",
            "serial_number": "00004569",
            "zip_code": "02139",
            "local_group": "g_a",
            "measure_total": 20.0,
        },
    ]

    l0: list[dict[str, Any]] = []
    for i in range(12):
        l0.append(
            {
                "row_key": f"row_{i:02d}",
                "local_group": groups[i % len(groups)],
                "late_value": None if i < 4 else round(100 + i * 2.5, 2),
                "baseline_value": float(i + 1),
            }
        )

    return {
        "S0": s0,
        "S1": s1,
        "S2": s2,
        "S3": s3,
        "C0": c0,
        "I0": i0,
        "L0": l0,
    }


def _build_query_cases(sources: dict[str, list[dict[str, Any]]]) -> list[QueryCase]:
    s0 = sources["S0"]
    s1 = sources["S1"]
    s2 = sources["S2"]
    s3 = sources["S3"]
    c0 = sources["C0"]
    i0 = sources["I0"]
    l0 = [row for row in sources["L0"] if isinstance(row["late_value"], int | float)]

    entity_to_segment = {row["entity_key"]: row["segment_label"] for row in s1}
    entity_to_bridge = {row["entity_key"]: row["bridge_key"] for row in s1}
    bridge_to_label = {row["bridge_key"]: row["bridge_label"] for row in s3}
    bridge_to_geo = {row["bridge_key"]: row["geo_key"] for row in s3}
    geo_to_region = {row["geo_key"]: row["region_label"] for row in s2}
    geo_to_country = {row["geo_key"]: row["country_code"] for row in s2}

    def joined_rows(group_name: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in s0:
            bridge_key = entity_to_bridge[row["entity_key"]]
            geo_key = bridge_to_geo[bridge_key]
            out.append(
                {
                    **row,
                    "segment": entity_to_segment[row["entity_key"]],
                    "bridge_label": bridge_to_label[bridge_key],
                    "region": geo_to_region[geo_key],
                    "country": geo_to_country[geo_key],
                }
            )
        return [
            {
                "group": item[group_name],
                "value": item["measure_total"],
            }
            for item in out
        ]

    def grouped_joined(group_name: str) -> list[dict[str, Any]]:
        rows = joined_rows(group_name)
        buckets: dict[str, float] = {}
        for row in rows:
            buckets[row["group"]] = buckets.get(row["group"], 0.0) + float(row["value"])
        out = [{"group": k, "value": round(v, 6)} for k, v in buckets.items()]
        out.sort(key=lambda item: (-item["value"], item["group"]))
        return out

    return [
        QueryCase(
            label="Q1",
            metric_hint="total value",
            dim_hint="local group",
            agg="sum",
            preferred_source="S0",
            expected_metric=("S0", "measure_total"),
            expected_group=("S0", "local_group"),
            expected_hops=(),
            expected_result=_group_rows(s0, "measure_total", "local_group", "sum"),
        ),
        QueryCase(
            label="Q2",
            metric_hint="total value",
            dim_hint="segment",
            agg="sum",
            preferred_source="S0",
            expected_metric=("S0", "measure_total"),
            expected_group=("S1", "segment_label"),
            expected_hops=(("S0", "entity_key", "S1", "entity_key"),),
            expected_result=grouped_joined("segment"),
        ),
        QueryCase(
            label="Q3",
            metric_hint="total value",
            dim_hint="bridge label",
            agg="sum",
            preferred_source="S0",
            expected_metric=("S0", "measure_total"),
            expected_group=("S3", "bridge_label"),
            expected_hops=(
                ("S0", "entity_key", "S1", "entity_key"),
                ("S1", "bridge_key", "S3", "bridge_key"),
            ),
            expected_result=grouped_joined("bridge_label"),
        ),
        QueryCase(
            label="Q4",
            metric_hint="total value",
            dim_hint="region",
            agg="sum",
            preferred_source="S0",
            expected_metric=("S0", "measure_total"),
            expected_group=("S2", "region_label"),
            expected_hops=(
                ("S0", "entity_key", "S1", "entity_key"),
                ("S1", "bridge_key", "S3", "bridge_key"),
                ("S3", "geo_key", "S2", "geo_key"),
            ),
            expected_result=grouped_joined("region"),
        ),
        QueryCase(
            label="Q5",
            metric_hint="total value",
            dim_hint="country",
            agg="sum",
            preferred_source="S0",
            expected_metric=("S0", "measure_total"),
            expected_group=("S2", "country_code"),
            expected_hops=(
                ("S0", "entity_key", "S1", "entity_key"),
                ("S1", "bridge_key", "S3", "bridge_key"),
                ("S3", "geo_key", "S2", "geo_key"),
            ),
            expected_result=grouped_joined("country"),
        ),
        QueryCase(
            label="Q6",
            metric_hint="unit rate",
            dim_hint="local group",
            agg="avg",
            preferred_source="S0",
            expected_metric=("S0", "unit_rate"),
            expected_group=("S0", "local_group"),
            expected_hops=(),
            expected_result=_group_rows(s0, "unit_rate", "local_group", "avg"),
        ),
        QueryCase(
            label="Q7",
            metric_hint="scalar total value",
            dim_hint=None,
            agg="sum",
            preferred_source="S0",
            expected_metric=("S0", "measure_total"),
            expected_group=None,
            expected_hops=(),
            expected_result=_scalar_value(s0, "measure_total", "sum"),
        ),
        QueryCase(
            label="Q8",
            metric_hint="unit cost",
            dim_hint="category",
            agg="avg",
            preferred_source="C0",
            expected_metric=("C0", "UNIT_COST"),
            expected_group=("C0", "category"),
            expected_hops=(),
            expected_result=_group_rows(c0, "UNIT_COST", "category", "avg"),
        ),
        QueryCase(
            label="Q9",
            metric_hint="extended cost",
            dim_hint="category",
            agg="sum",
            preferred_source="C0",
            expected_metric=("C0", "EXT_COST"),
            expected_group=("C0", "category"),
            expected_hops=(),
            expected_result=_group_rows(c0, "EXT_COST", "category", "sum"),
        ),
        QueryCase(
            label="Q10",
            metric_hint="overhead cost",
            dim_hint="category",
            agg="sum",
            preferred_source="C0",
            expected_metric=("C0", "OH_COST"),
            expected_group=("C0", "category"),
            expected_hops=(),
            expected_result=_group_rows(c0, "OH_COST", "category", "sum"),
        ),
        QueryCase(
            label="Q11",
            metric_hint="total cost",
            dim_hint=None,
            agg="sum",
            preferred_source="C0",
            expected_metric=("C0", "EXT_COST"),
            expected_group=None,
            expected_hops=(),
            expected_result=_scalar_value(c0, "EXT_COST", "sum"),
        ),
        QueryCase(
            label="Q12",
            metric_hint="total value",
            dim_hint="local group",
            agg="sum",
            preferred_source="I0",
            expected_metric=("I0", "measure_total"),
            expected_group=("I0", "local_group"),
            expected_hops=(),
            expected_result=_group_rows(i0, "measure_total", "local_group", "sum"),
        ),
        QueryCase(
            label="Q13",
            metric_hint="late value",
            dim_hint="local group",
            agg="sum",
            preferred_source="L0",
            expected_metric=("L0", "late_value"),
            expected_group=("L0", "local_group"),
            expected_hops=(),
            expected_result=_group_rows(l0, "late_value", "local_group", "sum"),
        ),
    ]


def _build_ingest_checks() -> list[IngestCheck]:
    return [
        IngestCheck("I0 account code preserved", "I0", 0, "account_code", "str", "00123"),
        IngestCheck("I0 serial preserved", "I0", 0, "serial_number", "str", "00004567"),
        IngestCheck("I0 zip preserved", "I0", 0, "zip_code", "str", "02139"),
        IngestCheck(
            "L0 late sparse field remains numeric when populated",
            "L0",
            4,
            "late_value",
            "float",
            110.0,
        ),
    ]


def _materialize_source(
    *,
    backend: str,
    workdir: Path,
    name: str,
    rows: list[dict[str, Any]],
    sqlite_path: Path | None,
) -> Any:
    runtime_modules = _runtime_modules()
    data_source_cls = runtime_modules["DataSource"]
    if backend == "csv":
        return data_source_cls(name=name, csv=_rows_to_csv(rows))
    if backend == "parquet":
        return data_source_cls(name=name, parquet_b64=_rows_to_parquet_b64(rows))
    if backend == "sqlite":
        if sqlite_path is None:
            raise ValueError("sqlite_path is required for sqlite backend")
        table_name = _sqlite_table_name(name)
        with sqlite3.connect(sqlite_path) as conn:
            pd.DataFrame(rows).to_sql(table_name, conn, index=False, if_exists="replace")
        return data_source_cls(
            name=name,
            connection={
                "type": "sql",
                "connection_string": f"sqlite+pysqlite:///{sqlite_path}",
                "query": f'SELECT * FROM "{table_name}"',  # noqa: S608
            },
        )
    raise ValueError(f"Unsupported backend: {backend}")


async def _reset_runtime_state(registry_dir: Path) -> None:
    runtime_modules = _runtime_modules()
    source_registry = runtime_modules["source_registry"]
    cache_lock = runtime_modules["cache_lock"]
    source_cache = runtime_modules["source_cache"]
    result_cache = runtime_modules["result_cache"]
    verify_cache = runtime_modules["verify_cache"]
    df_cache = runtime_modules["df_cache"]

    source_registry._SOURCES_DIR = registry_dir
    async with cache_lock:
        source_cache.clear()
    result_cache.clear()
    verify_cache.clear()
    df_cache.clear()


async def _run_backend(backend: str, workdir: Path) -> dict[str, Any]:
    runtime_modules = _runtime_modules()
    register_request_cls = runtime_modules["RegisterRequest"]
    register_source = runtime_modules["register_source"]
    auto_planner_cls = runtime_modules["AutoPlanner"]

    sources = _generate_sources()
    query_cases = _build_query_cases(sources)
    ingest_checks = _build_ingest_checks()

    registry_dir = workdir / "registry" / backend
    sqlite_path = workdir / f"{backend}.db" if backend == "sqlite" else None
    await _reset_runtime_state(registry_dir)

    org_id = f"bench_{backend}_{uuid.uuid4().hex[:8]}"
    register_latencies: list[float] = []

    for name, rows in sources.items():
        data_source = _materialize_source(
            backend=backend,
            workdir=workdir,
            name=name,
            rows=rows,
            sqlite_path=sqlite_path,
        )
        t0 = time.perf_counter()
        resp = await register_source(
            register_request_cls(source=data_source),
            auth={"org_id": org_id},
        )
        register_latencies.append((time.perf_counter() - t0) * 1000)
        if resp["status"] not in {"registered", "already_registered"}:
            raise RuntimeError(f"{backend}: registration failed for {name}: {resp}")

    planner = auto_planner_cls.from_registry(org_id, llm_policy="never")

    ingest_passed = 0
    ingest_details: list[dict[str, Any]] = []
    for check in ingest_checks:
        planner._ensure_records(check.source)
        row = planner.tables.get(check.source, [])[check.row_index]
        actual = row[check.field]
        ok = _ingest_value_matches(actual, check.expected_type, check.expected_value)
        if ok:
            ingest_passed += 1
        ingest_details.append(
            {
                "label": check.label,
                "ok": ok,
                "actual_type": type(actual).__name__,
                "actual_value": actual,
                "expected_type": check.expected_type,
                "expected_value": check.expected_value,
            }
        )

    metric_passed = 0
    group_passed = 0
    join_passed = 0
    query_passed = 0
    query_latencies: list[float] = []
    query_details: list[dict[str, Any]] = []

    for case in query_cases:
        t0 = time.perf_counter()
        plan = planner.plan(
            metric_hint=case.metric_hint,
            dim_hint=case.dim_hint,
            agg=case.agg,
            preferred_source=case.preferred_source,
        )
        result, row_count, _trace = planner.execute_plan(plan, limit=10)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        query_latencies.append(elapsed_ms)

        metric_ok = (plan.metric_src, plan.metric_col) == case.expected_metric
        group_ok = (case.expected_group is None and plan.group_col is None) or (
            case.expected_group is not None
            and (plan.group_src, plan.group_col) == case.expected_group
        )
        actual_hops = tuple(
            (hop.left_source, hop.left_key, hop.right_source, hop.right_key)
            for hop in plan.join_hops
        )
        join_ok = actual_hops == case.expected_hops
        normalized_result = _normalize_result(result)
        expected_result = _normalize_result(case.expected_result)
        query_ok = plan.error is None and normalized_result == expected_result

        metric_passed += int(metric_ok)
        group_passed += int(group_ok)
        join_passed += int(join_ok)
        query_passed += int(query_ok)

        query_details.append(
            {
                "label": case.label,
                "metric_ok": metric_ok,
                "group_ok": group_ok,
                "join_ok": join_ok,
                "query_ok": query_ok,
                "metric": [plan.metric_src, plan.metric_col],
                "group": [plan.group_src, plan.group_col] if plan.group_col else None,
                "expected_metric": list(case.expected_metric),
                "expected_group": list(case.expected_group) if case.expected_group else None,
                "actual_hops": [list(h) for h in actual_hops],
                "expected_hops": [list(h) for h in case.expected_hops],
                "row_count": row_count,
                "latency_ms": round(elapsed_ms, 3),
            }
        )

    return {
        "backend": backend,
        "sources": len(sources),
        "queries": len(query_cases),
        "ingest_checks": len(ingest_checks),
        "ingest_passed": ingest_passed,
        "metric_passed": metric_passed,
        "group_passed": group_passed,
        "join_passed": join_passed,
        "query_passed": query_passed,
        "avg_register_ms": round(sum(register_latencies) / len(register_latencies), 3),
        "avg_query_ms": round(sum(query_latencies) / len(query_latencies), 3),
        "max_query_ms": round(max(query_latencies), 3),
        "ingest_details": ingest_details,
        "query_details": query_details,
    }


async def _run_all() -> dict[str, Any]:
    backends = ["csv", "parquet", "sqlite"]
    with tempfile.TemporaryDirectory() as tmp_dir:
        workdir = Path(tmp_dir)
        results = [await _run_backend(backend, workdir) for backend in backends]

    total_queries = sum(item["queries"] for item in results)
    total_ingest = sum(item["ingest_checks"] for item in results)
    return {
        "benchmark": "universal_synthetic_registry_matrix",
        "backends": backends,
        "totals": {
            "queries": total_queries,
            "ingest_checks": total_ingest,
            "metric_accuracy": round(
                sum(item["metric_passed"] for item in results) / total_queries,
                4,
            ),
            "group_accuracy": round(
                sum(item["group_passed"] for item in results) / total_queries,
                4,
            ),
            "join_accuracy": round(
                sum(item["join_passed"] for item in results) / total_queries,
                4,
            ),
            "query_accuracy": round(
                sum(item["query_passed"] for item in results) / total_queries,
                4,
            ),
            "ingest_accuracy": round(
                sum(item["ingest_passed"] for item in results) / total_ingest,
                4,
            ),
        },
        "results": results,
    }


def main() -> None:
    started = time.perf_counter()
    summary = asyncio.run(_run_all())
    elapsed_ms = (time.perf_counter() - started) * 1000
    summary["elapsed_ms"] = round(elapsed_ms, 3)

    print("\nUniversal Synthetic Registry Benchmark")
    print("=" * 72)
    print(json.dumps(summary["totals"], indent=2))
    print()
    for item in summary["results"]:
        print(
            f"{item['backend']:<8} "
            f"ingest={item['ingest_passed']}/{item['ingest_checks']} "
            f"metric={item['metric_passed']}/{item['queries']} "
            f"group={item['group_passed']}/{item['queries']} "
            f"join={item['join_passed']}/{item['queries']} "
            f"query={item['query_passed']}/{item['queries']} "
            f"avg_register_ms={item['avg_register_ms']:.1f} "
            f"avg_query_ms={item['avg_query_ms']:.1f}"
        )
    print(f"\nElapsed: {elapsed_ms:.1f}ms")


if __name__ == "__main__":
    main()
