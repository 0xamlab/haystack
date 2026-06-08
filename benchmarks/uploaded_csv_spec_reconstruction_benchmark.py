#!/usr/bin/env python3
# ruff: noqa: E402, E501
"""
Hint-only spec reconstruction benchmark for the uploaded CSV corpus.

This reuses the same real uploaded CSV cases as the exact-spec benchmark, but
degrades each case to:
  - metric_hint
  - dim_hint
  - preferred_source

It scores the planner on spec reconstruction, not just final answers:
  - source accuracy
  - metric accuracy
  - group accuracy
  - join-path accuracy
  - full-spec accuracy
  - end-to-end query accuracy
  - partial score distribution
  - failure taxonomy
  - confidence vs correctness
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
BENCHMARKS_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BENCHMARKS_DIR))

from uploaded_csv_exact_benchmark import (
    SOURCE_FILES,
    ExactQueryCase,
    _build_cases,
    _ensure_case_tables,
    _expected_result,
    _normalize_result,
    _reset_runtime_state,
    _setup_mojo_runtime,
    _teardown_mojo_runtime,
)

from apps.api_server.routers.data_map import DataSource
from apps.api_server.routers.sources import RegisterRequest, register_source
from apps.api_server.services.auto_planner import AutoPlanner, QueryPlan


@dataclass(frozen=True)
class HintQueryCase:
    label: str
    description: str
    metric_hint: str
    dim_hint: str | None
    preferred_source: str
    exact_case: ExactQueryCase


def _build_hint_cases() -> list[HintQueryCase]:
    exact_by_label = {case.label: case for case in _build_cases()}
    hints = {
        "Q1": ("revenue", "ship to state", "BookingsNew"),
        "Q2": ("sales", "ship to country", "POSNew"),
        "Q3": ("revenue", "status", "QuotesNew"),
        "Q4": ("extended cost", "warehouse", "Inventory"),
        "Q5": ("extended price", "sales office", "Backlog"),
        "Q6": ("revenue", "pos inventory type", "BookingsNew"),
        "Q7": ("revenue", "inventory product line", "QuotesNew"),
        "Q8": ("sales", "pos inventory type", "QuotesNew"),
        "Q9": ("extended price", "pos inventory type", "Backlog"),
        "Q10": ("extended price", "pos ohvendname", "Backlog"),
    }
    out: list[HintQueryCase] = []
    for label, (metric_hint, dim_hint, preferred_source) in hints.items():
        exact_case = exact_by_label[label]
        out.append(
            HintQueryCase(
                label=label,
                description=exact_case.description,
                metric_hint=metric_hint,
                dim_hint=dim_hint,
                preferred_source=preferred_source,
                exact_case=exact_case,
            )
        )
    return out


def _plan_edges(plan: QueryPlan) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (hop.left_source, hop.left_key, hop.right_source, hop.right_key) for hop in plan.join_hops
    )


def _plan_confidence(plan: QueryPlan) -> float:
    values = [max(0.0, float(plan.metric_conf))]
    if plan.group_col:
        values.append(max(0.0, float(plan.group_conf)))
    if plan.join_hops:
        values.append(max(0.0, float(plan.path_confidence or plan.join_conf)))
    return min(values) if values else 0.0


def _join_failure_label(
    expected: tuple[tuple[str, str, str, str], ...], actual: tuple[tuple[str, str, str, str], ...]
) -> str:
    if expected == actual:
        return ""
    if not expected and actual:
        return "extra_join"
    if expected and not actual:
        return "missing_join"
    if len(actual) > len(expected):
        return "over_join"
    if len(actual) < len(expected):
        return "under_join"
    return "wrong_join_path"


def _failure_tags(case: HintQueryCase, plan: QueryPlan) -> list[str]:
    tags: list[str] = []
    exact = case.exact_case

    if plan.error:
        tags.append("plan_error")

    if plan.metric_src != exact.source_name:
        tags.append("wrong_source")
    if plan.metric_col != exact.metric_column:
        tags.append("wrong_metric")

    expected_group = (exact.group_source, exact.group_column) if exact.group_column else None
    actual_group = (plan.group_src, plan.group_col) if plan.group_col else None
    if expected_group != actual_group:
        tags.append("wrong_group")

    join_tag = _join_failure_label(exact.edges, _plan_edges(plan))
    if join_tag:
        tags.append(join_tag)

    return tags


async def _run() -> dict[str, Any]:
    cases = _build_hint_cases()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        registry_dir = Path(tmp_dir) / "registry"
        await _reset_runtime_state(registry_dir)
        mojo_runtime_mode = await _setup_mojo_runtime()

        try:
            org_id = f"uploaded_csv_spec_{int(time.time())}"
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

            source_hits = 0
            metric_hits = 0
            group_hits = 0
            join_hits = 0
            full_spec_hits = 0
            query_hits = 0

            plan_latencies: list[float] = []
            exec_latencies: list[float] = []
            correct_confidences: list[float] = []
            wrong_confidences: list[float] = []
            partial_hist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
            taxonomy: dict[str, int] = {}
            details: list[dict[str, Any]] = []

            for case in cases:
                exact = case.exact_case
                _ensure_case_tables(planner, exact)
                expected_result, _ = _expected_result(exact, planner.tables)
                expected_norm = _normalize_result(expected_result)

                t0 = time.perf_counter()
                plan = await asyncio.to_thread(
                    planner.plan,
                    metric_hint=case.metric_hint,
                    dim_hint=case.dim_hint,
                    agg=exact.aggregation,
                    preferred_source=case.preferred_source,
                )
                plan_ms = (time.perf_counter() - t0) * 1000
                plan_latencies.append(plan_ms)

                t0 = time.perf_counter()
                actual_result, row_count, trace = await asyncio.to_thread(
                    planner.execute_plan,
                    plan,
                    limit=None,
                )
                exec_ms = (time.perf_counter() - t0) * 1000
                exec_latencies.append(exec_ms)
                actual_norm = _normalize_result(actual_result)

                source_ok = plan.metric_src == exact.source_name
                metric_ok = plan.metric_col == exact.metric_column
                expected_group = (
                    (exact.group_source, exact.group_column) if exact.group_column else None
                )
                actual_group = (plan.group_src, plan.group_col) if plan.group_col else None
                group_ok = expected_group == actual_group
                join_ok = exact.edges == _plan_edges(plan)
                full_spec_ok = source_ok and metric_ok and group_ok and join_ok and not plan.error
                query_ok = actual_norm == expected_norm and not plan.error

                source_hits += int(source_ok)
                metric_hits += int(metric_ok)
                group_hits += int(group_ok)
                join_hits += int(join_ok)
                full_spec_hits += int(full_spec_ok)
                query_hits += int(query_ok)

                partial_score = int(source_ok) + int(metric_ok) + int(group_ok) + int(join_ok)
                partial_hist[partial_score] += 1

                confidence = _plan_confidence(plan)
                if full_spec_ok:
                    correct_confidences.append(confidence)
                else:
                    wrong_confidences.append(confidence)

                tags = _failure_tags(case, plan)
                for tag in tags:
                    taxonomy[tag] = taxonomy.get(tag, 0) + 1

                details.append(
                    {
                        "label": case.label,
                        "description": case.description,
                        "metric_hint": case.metric_hint,
                        "dim_hint": case.dim_hint,
                        "preferred_source": case.preferred_source,
                        "plan_ms": round(plan_ms, 3),
                        "exec_ms": round(exec_ms, 3),
                        "plan_confidence": round(confidence, 4),
                        "source_correct": source_ok,
                        "metric_correct": metric_ok,
                        "group_correct": group_ok,
                        "join_path_correct": join_ok,
                        "full_spec_correct": full_spec_ok,
                        "query_correct": query_ok,
                        "partial_score": partial_score,
                        "failure_tags": tags,
                        "expected_spec": {
                            "metric_source": exact.source_name,
                            "metric_column": exact.metric_column,
                            "group": [exact.group_source, exact.group_column]
                            if exact.group_column
                            else None,
                            "join_path": list(exact.edges),
                        },
                        "actual_spec": {
                            "metric_source": plan.metric_src,
                            "metric_column": plan.metric_col,
                            "group": [plan.group_src, plan.group_col] if plan.group_col else None,
                            "join_path": list(_plan_edges(plan)),
                        },
                        "expected_result": expected_norm,
                        "actual_result": actual_norm,
                        "row_count": row_count,
                        "plan_error": plan.error,
                        "plan_tail": plan.steps[-6:],
                        "exec_tail": trace[-6:],
                    }
                )

            queries = len(cases)
            return {
                "benchmark": "uploaded_csv_spec_reconstruction_benchmark",
                "sources": list(SOURCE_FILES.keys()),
                "queries": queries,
                "source_accuracy": round(source_hits / queries, 4),
                "metric_accuracy": round(metric_hits / queries, 4),
                "group_accuracy": round(group_hits / queries, 4),
                "join_accuracy": round(join_hits / queries, 4),
                "full_spec_accuracy": round(full_spec_hits / queries, 4),
                "query_accuracy": round(query_hits / queries, 4),
                "avg_partial_score": round(
                    sum(score * count for score, count in partial_hist.items()) / queries, 4
                ),
                "partial_score_histogram": partial_hist,
                "avg_register_ms": round(sum(register_latencies) / len(register_latencies), 3),
                "avg_plan_ms": round(sum(plan_latencies) / len(plan_latencies), 3),
                "avg_exec_ms": round(sum(exec_latencies) / len(exec_latencies), 3),
                "avg_end_to_end_ms": round(
                    (sum(plan_latencies) + sum(exec_latencies)) / len(exec_latencies), 3
                ),
                "avg_confidence_when_correct": round(
                    sum(correct_confidences) / len(correct_confidences), 4
                )
                if correct_confidences
                else None,
                "avg_confidence_when_wrong": round(
                    sum(wrong_confidences) / len(wrong_confidences), 4
                )
                if wrong_confidences
                else None,
                "failure_taxonomy": dict(sorted(taxonomy.items())),
                "mojo_runtime_mode": mojo_runtime_mode,
                "details": details,
            }
        finally:
            await _teardown_mojo_runtime()


def main() -> None:
    started = time.perf_counter()
    summary = asyncio.run(_run())
    elapsed_ms = (time.perf_counter() - started) * 1000
    summary["elapsed_ms"] = round(elapsed_ms, 3)

    print("\nUploaded CSV Spec Reconstruction Benchmark")
    print("=" * 72)
    print(
        json.dumps(
            {
                "queries": summary["queries"],
                "source_accuracy": summary["source_accuracy"],
                "metric_accuracy": summary["metric_accuracy"],
                "group_accuracy": summary["group_accuracy"],
                "join_accuracy": summary["join_accuracy"],
                "full_spec_accuracy": summary["full_spec_accuracy"],
                "query_accuracy": summary["query_accuracy"],
                "avg_partial_score": summary["avg_partial_score"],
                "partial_score_histogram": summary["partial_score_histogram"],
                "avg_register_ms": summary["avg_register_ms"],
                "avg_plan_ms": summary["avg_plan_ms"],
                "avg_exec_ms": summary["avg_exec_ms"],
                "avg_end_to_end_ms": summary["avg_end_to_end_ms"],
                "avg_confidence_when_correct": summary["avg_confidence_when_correct"],
                "avg_confidence_when_wrong": summary["avg_confidence_when_wrong"],
                "failure_taxonomy": summary["failure_taxonomy"],
                "mojo_runtime_mode": summary["mojo_runtime_mode"],
            },
            indent=2,
        )
    )
    print()
    for item in summary["details"]:
        status = "PASS" if item["full_spec_correct"] else "FAIL"
        answer = "answer=ok" if item["query_correct"] else "answer=bad"
        tags = ",".join(item["failure_tags"]) or "-"
        print(
            f"{item['label']:<4} {status:<4} "
            f"score={item['partial_score']}/4  "
            f"conf={item['plan_confidence']:.3f}  "
            f"plan={item['plan_ms']:>7.1f}ms  exec={item['exec_ms']:>7.1f}ms  "
            f"{answer:<10} tags={tags:<30} {item['description']}"
        )
    print(f"\nElapsed: {elapsed_ms:.1f}ms")


if __name__ == "__main__":
    main()
