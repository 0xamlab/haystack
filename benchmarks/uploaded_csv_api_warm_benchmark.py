#!/usr/bin/env python3
# ruff: noqa: E402
"""
Warm-path API benchmark for the uploaded CSV corpus.

This exercises the real registry-backed hint path in /v1/query and separates:
  - cold first query after registration (planner build)
  - warm unique queries on the same org/schema
  - hot repeated queries (result cache)
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path
from statistics import mean
from typing import Any

from fastapi import HTTPException

ROOT = Path(__file__).parent.parent
BENCHMARKS_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BENCHMARKS_DIR))

from uploaded_csv_exact_benchmark import (
    SOURCE_FILES,
    _ensure_case_tables,
    _expected_result,
    _normalize_result,
    _reset_runtime_state,
    _setup_mojo_runtime,
    _teardown_mojo_runtime,
)
from uploaded_csv_spec_reconstruction_benchmark import HintQueryCase, _build_hint_cases

from apps.api_server.routers.data_map import DataSource
from apps.api_server.routers.query import (
    QueryRequest,
    ResolveRequest,
    _resolve_registered_intent,
    query_sources,
)
from apps.api_server.routers.sources import RegisterRequest, register_source
from apps.api_server.services.auto_planner import AutoPlanner


async def _run_case(
    *,
    case: HintQueryCase,
    auth: dict[str, str],
    reference_planner: AutoPlanner,
) -> dict[str, Any]:
    _ensure_case_tables(reference_planner, case.exact_case)
    expected_result, _ = _expected_result(case.exact_case, reference_planner.tables)
    expected_norm = _normalize_result(expected_result)

    payload = QueryRequest(
        metric={"role": "derived_measure", "hint": case.metric_hint},
        group_by=[case.dim_hint] if case.dim_hint else [],
        preferred_source=case.preferred_source,
        aggregation=case.exact_case.aggregation,
    )

    t0 = time.perf_counter()
    try:
        resolve_response = await _resolve_registered_intent(
            ResolveRequest(
                metric=payload.metric,
                group_by=payload.group_by,
                preferred_source=payload.preferred_source,
                aggregation=payload.aggregation,
                allow_org_scope=True,
            ),
            auth=auth,
            request_id=None,
        )
    except HTTPException as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        detail = exc.detail.get("error", {}) if isinstance(exc.detail, dict) else {}
        return {
            "label": case.label,
            "latency_ms": round(elapsed_ms, 3),
            "query_correct": False,
            "planner_cache_hit": False,
            "result_cache_hit": False,
            "resolved_source": "",
            "resolved_column": "",
            "confidence": 0.0,
            "rejection_reason": detail.get("code") or "resolve_error",
        }
    if resolve_response.resolved_plan is None:
        return {
            "label": case.label,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 3),
            "query_correct": False,
            "planner_cache_hit": any("Planner cache HIT" in step for step in resolve_response.plan),
            "result_cache_hit": any("Resolve cache HIT" in step for step in resolve_response.plan),
            "resolved_source": resolve_response.resolved_source,
            "resolved_column": resolve_response.resolved_column,
            "confidence": resolve_response.confidence,
            "rejection_reason": resolve_response.rejection_reason,
        }

    response = await query_sources(
        QueryRequest(resolved_plan=resolve_response.resolved_plan),
        auth=auth,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    actual_norm = _normalize_result(response.result)

    return {
        "label": case.label,
        "latency_ms": round(elapsed_ms, 3),
        "query_correct": actual_norm == expected_norm,
        "planner_cache_hit": any("Planner cache HIT" in step for step in resolve_response.plan),
        "result_cache_hit": any("Result cache HIT" in step for step in response.plan),
        "resolved_source": response.resolved_source,
        "resolved_column": response.resolved_column,
        "confidence": response.confidence,
        "rejection_reason": None,
    }


async def _run() -> dict[str, Any]:
    cases = _build_hint_cases()

    with tempfile.TemporaryDirectory() as tmp_dir:
        registry_dir = Path(tmp_dir) / "registry"
        await _reset_runtime_state(registry_dir)
        mojo_runtime_mode = await _setup_mojo_runtime()

        try:
            org_id = f"uploaded_csv_api_{int(time.time())}"
            auth = {"org_id": org_id, "role": "owner", "key_id": str(uuid.uuid4())}
            register_latencies: list[float] = []
            register_prewarm_latencies: list[float] = []

            for source_name, path in SOURCE_FILES.items():
                payload = RegisterRequest(
                    source=DataSource(
                        name=source_name,
                        csv=path.read_text(encoding="utf-8", errors="replace"),
                    )
                )
                t0 = time.perf_counter()
                response = await register_source(payload, auth=auth)
                register_latencies.append((time.perf_counter() - t0) * 1000)
                if response["status"] not in {"registered", "already_registered"}:
                    raise RuntimeError(f"registration failed for {source_name}: {response}")
                register_prewarm_latencies.append(float(response.get("planner_prewarm_ms", 0.0)))

            reference_planner = AutoPlanner.from_registry(org_id, llm_policy="never")

            cold_first = await _run_case(
                case=cases[0],
                auth=auth,
                reference_planner=reference_planner,
            )
            warm_unique = [
                await _run_case(case=case, auth=auth, reference_planner=reference_planner)
                for case in cases[1:]
            ]
            hot_repeat = [
                await _run_case(case=case, auth=auth, reference_planner=reference_planner)
                for case in cases
            ]

            first_pass = [cold_first] + warm_unique
            return {
                "benchmark": "uploaded_csv_api_warm_benchmark",
                "queries": len(cases),
                "query_accuracy_first_pass": round(
                    sum(1 for item in first_pass if item["query_correct"]) / len(first_pass), 4
                ),
                "avg_register_ms": round(mean(register_latencies), 3),
                "avg_register_prewarm_ms": round(mean(register_prewarm_latencies), 3),
                "cold_first_query_ms": cold_first["latency_ms"],
                "cold_first_planner_cache_hit": cold_first["planner_cache_hit"],
                "warm_unique_avg_ms": round(mean(item["latency_ms"] for item in warm_unique), 3),
                "warm_unique_planner_cache_hits": sum(
                    1 for item in warm_unique if item["planner_cache_hit"]
                ),
                "warm_unique_result_cache_hits": sum(
                    1 for item in warm_unique if item["result_cache_hit"]
                ),
                "hot_repeat_avg_ms": round(mean(item["latency_ms"] for item in hot_repeat), 3),
                "hot_repeat_result_cache_hits": sum(
                    1 for item in hot_repeat if item["result_cache_hit"]
                ),
                "mojo_runtime_mode": mojo_runtime_mode,
                "details": {
                    "cold_first": cold_first,
                    "warm_unique": warm_unique,
                    "hot_repeat": hot_repeat,
                },
            }
        finally:
            await _teardown_mojo_runtime()


def main() -> None:
    started = time.perf_counter()
    summary = asyncio.run(_run())
    elapsed_ms = (time.perf_counter() - started) * 1000
    summary["elapsed_ms"] = round(elapsed_ms, 3)

    print("\nUploaded CSV API Warm Benchmark")
    print("=" * 72)
    print(
        json.dumps(
            {
                "queries": summary["queries"],
                "query_accuracy_first_pass": summary["query_accuracy_first_pass"],
                "avg_register_ms": summary["avg_register_ms"],
                "avg_register_prewarm_ms": summary["avg_register_prewarm_ms"],
                "cold_first_query_ms": summary["cold_first_query_ms"],
                "cold_first_planner_cache_hit": summary["cold_first_planner_cache_hit"],
                "warm_unique_avg_ms": summary["warm_unique_avg_ms"],
                "warm_unique_planner_cache_hits": summary["warm_unique_planner_cache_hits"],
                "warm_unique_result_cache_hits": summary["warm_unique_result_cache_hits"],
                "hot_repeat_avg_ms": summary["hot_repeat_avg_ms"],
                "hot_repeat_result_cache_hits": summary["hot_repeat_result_cache_hits"],
                "mojo_runtime_mode": summary["mojo_runtime_mode"],
                "elapsed_ms": summary["elapsed_ms"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
