from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api_server.routers.data_map import DataSource  # noqa: E402
from apps.api_server.routers.query import (  # noqa: E402
    _CACHE_LOCK,
    _DF_CACHE,
    _PLANNER_CACHE,
    _RESOLVE_CACHE,
    _RESULT_CACHE,
    _SOURCE_CACHE,
)
from apps.api_server.routers.sources import RegisterRequest, register_source  # noqa: E402
from apps.api_server.services import source_registry as reg  # noqa: E402
from apps.api_server.services.auth_service import AuthContext  # noqa: E402
from apps.api_server.services.auto_planner import AutoPlanner  # noqa: E402
from benchmarks.live_postgres_question_answer_benchmark import (  # noqa: E402
    DEFAULT_DSN_ENV,
    DEFAULT_SCHEMA,
    JoinEdge,
    SchemaTable,
    WorkloadQuestion,
    build_workload_questions,
    humanize_identifier,
    infer_join_edges,
    label_column,
    load_schema_tables,
)

SUPPORTED_KINDS = ("single_dimension_sum", "single_dimension_avg", "two_hop_sum")
DEFAULT_PER_KIND_LIMIT = 40
DEFAULT_STATEMENT_TIMEOUT_MS = 5000
DEFAULT_OUTPUT_PATH = REPO_ROOT / "build" / "live_postgres_registry_planner_benchmark.json"
RESULT_VALUE_PRECISION = 2
SAMPLE_LIMIT = 5
RESULT_VALUE_TOLERANCE = 0.01
RESULT_VALUE_EPSILON = 1e-9


@dataclass(frozen=True)
class PlannerInputs:
    metric_hint: str
    dim_hint: str
    agg: str
    preferred_source: str


@dataclass(frozen=True)
class PlannerBenchmarkResult:
    question_id: str
    question: str
    kind: str
    complexity: int
    planner_inputs: dict[str, str]
    expected_tables: tuple[str, ...]
    expected_dimension_tables: tuple[str, ...]
    expected_dimension_columns: tuple[str, ...]
    expected_metric_column: str | None
    planned_metric_src: str | None
    planned_metric_col: str | None
    planned_group_src: str | None
    planned_group_col: str | None
    planned_join_sources: tuple[str, ...]
    plan_error: str | None
    ground_truth_error: str | None
    metric_src_top1: bool
    metric_col_top1: bool
    group_src_top1: bool
    group_col_top1: bool
    join_path_exact: bool | None
    answer_exact: bool
    planner_latency_ms: float
    execution_latency_ms: float | None
    failure_class: str | None
    expected_rows: tuple[dict[str, object], ...]
    actual_rows: tuple[dict[str, object], ...]
    planner_trace: tuple[str, ...]


def _resolve_connection_string(args: argparse.Namespace) -> str:
    if args.dsn:
        return args.dsn
    env_value = os.environ.get(args.dsn_env)
    if env_value:
        return env_value
    raise SystemExit(
        f"Missing connection string. Pass --dsn or set the {args.dsn_env} environment variable."
    )


def quote_ident(value: str) -> str:
    return f'"{value.replace('"', '""')}"'


def qualified_table(schema: str, table_name: str) -> str:
    return f"{quote_ident(schema)}.{quote_ident(table_name)}"


def select_supported_questions(
    questions: list[WorkloadQuestion],
    *,
    per_kind_limit: int,
) -> list[WorkloadQuestion]:
    buckets: dict[str, list[WorkloadQuestion]] = defaultdict(list)
    for question in questions:
        if question.kind in SUPPORTED_KINDS:
            buckets[question.kind].append(question)

    selected: list[WorkloadQuestion] = []
    for kind in SUPPORTED_KINDS:
        selected.extend(buckets[kind][:per_kind_limit])
    return selected


def projection_query_for_table(
    *,
    schema: str,
    table_name: str,
    projected_columns: tuple[str, ...] | None,
) -> str:
    if not projected_columns:
        return f"SELECT * FROM {qualified_table(schema, table_name)}"  # noqa: S608
    select_list = ", ".join(quote_ident(column) for column in projected_columns)
    return f"SELECT {select_list} FROM {qualified_table(schema, table_name)}"  # noqa: S608


def workload_projection_columns(
    *,
    tables: dict[str, SchemaTable],
    selected_questions: list[WorkloadQuestion],
) -> dict[str, tuple[str, ...]]:
    selected_table_names = sorted(
        {table_name for question in selected_questions for table_name in question.expected_tables}
    )
    selected_tables = {
        table_name: tables[table_name]
        for table_name in selected_table_names
        if table_name in tables
    }
    projected_columns: dict[str, set[str]] = {table_name: set() for table_name in selected_tables}

    def _add_column(table_name: str, column_name: str | None) -> None:
        if not column_name or table_name not in selected_tables:
            return
        available = {column.name for column in selected_tables[table_name].columns}
        if column_name in available:
            projected_columns[table_name].add(column_name)

    for table_name, table in selected_tables.items():
        _add_column(table_name, "id")
        for column in table.columns:
            if column.name.endswith("_id"):
                projected_columns[table_name].add(column.name)
        _add_column(table_name, label_column(table))

    inferred_edges: list[JoinEdge] = infer_join_edges(selected_tables)
    for edge in inferred_edges:
        _add_column(edge.source_table, edge.source_column)
        _add_column(edge.target_table, edge.target_column)

    for question in selected_questions:
        _add_column(question.primary_table, question.metric_column)
        for table_name, column_name in zip(
            question.dimension_tables,
            question.dimension_columns,
            strict=False,
        ):
            _add_column(table_name, column_name)

    ordered_projection: dict[str, tuple[str, ...]] = {}
    for table_name, table in selected_tables.items():
        ordered = tuple(
            column.name for column in table.columns if column.name in projected_columns[table_name]
        )
        ordered_projection[table_name] = ordered or tuple(column.name for column in table.columns)
    return ordered_projection


def planner_inputs_for_question(question: WorkloadQuestion) -> PlannerInputs:
    metric_column = question.metric_column
    if metric_column is None:
        raise ValueError(
            f"Unsupported planner workload question without metric column: {question.kind}"
        )
    agg = "avg" if question.kind.endswith("_avg") else "sum"
    return PlannerInputs(
        metric_hint=humanize_identifier(metric_column).lower(),
        dim_hint=humanize_identifier(question.dimension_tables[0]).lower(),
        agg=agg,
        preferred_source=question.primary_table,
    )


def _normalize_result_value(value: object) -> object:
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float | int):
        return round(float(value), RESULT_VALUE_PRECISION)
    return value


def normalize_expected_rows(rows: list[dict[str, Any]]) -> tuple[dict[str, object], ...]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        label = row.get("entity_label")
        value = row.get("metric_value")
        if label is None or value is None:
            continue
        normalized.append(
            {
                "group": str(label),
                "value": _normalize_result_value(value),
            }
        )
    return tuple(normalized)


def normalize_actual_rows(result: object) -> tuple[dict[str, object], ...]:
    if not isinstance(result, list):
        return ()
    normalized: list[dict[str, object]] = []
    for row in result:
        if not isinstance(row, dict):
            continue
        group = row.get("group")
        value = row.get("value")
        if group is None or value is None:
            continue
        normalized.append(
            {
                "group": str(group),
                "value": _normalize_result_value(value),
            }
        )
    return tuple(normalized)


def rows_semantically_match(
    expected_rows: tuple[dict[str, object], ...],
    actual_rows: tuple[dict[str, object], ...],
    *,
    value_tolerance: float = RESULT_VALUE_TOLERANCE,
) -> bool:
    if len(expected_rows) != len(actual_rows):
        return False
    if not expected_rows and not actual_rows:
        return True

    def _row_value(row: dict[str, object]) -> float:
        return float(row.get("value", 0.0) or 0.0)

    expected_sorted = sorted(
        expected_rows,
        key=lambda row: (-_row_value(row), str(row.get("group", ""))),
    )
    actual_sorted = sorted(
        actual_rows,
        key=lambda row: (-_row_value(row), str(row.get("group", ""))),
    )

    def _cluster_rows(rows: list[dict[str, object]]) -> list[tuple[float, list[dict[str, object]]]]:
        clusters: list[tuple[float, list[dict[str, object]]]] = []
        for row in rows:
            value = _row_value(row)
            if not clusters or abs(clusters[-1][0] - value) > (
                value_tolerance + RESULT_VALUE_EPSILON
            ):
                clusters.append((value, [row]))
                continue
            clusters[-1][1].append(row)
        return clusters

    expected_clusters = _cluster_rows(expected_sorted)
    actual_clusters = _cluster_rows(actual_sorted)
    if len(expected_clusters) != len(actual_clusters):
        return False

    for (expected_value, expected_bucket), (actual_value, actual_bucket) in zip(
        expected_clusters,
        actual_clusters,
        strict=True,
    ):
        if abs(expected_value - actual_value) > value_tolerance + RESULT_VALUE_EPSILON:
            return False
        if len(expected_bucket) != len(actual_bucket):
            return False
        if len(expected_bucket) == 1:
            expected_group = str(expected_bucket[0].get("group", ""))
            actual_group = str(actual_bucket[0].get("group", ""))
            if expected_group != actual_group:
                return False
    return True


def join_sources_for_plan(plan: Any) -> tuple[str, ...]:
    if not getattr(plan, "join_hops", None):
        return ()
    sources = [str(getattr(plan, "metric_src", ""))]
    for hop in getattr(plan, "join_hops", []) or []:
        sources.append(str(getattr(hop, "right_source", "")))
    return tuple(source for source in sources if source)


def join_path_matches_expected(question: WorkloadQuestion, plan: Any) -> bool | None:
    if question.kind != "two_hop_sum":
        return None
    expected_sources = question.expected_tables
    actual_sources = join_sources_for_plan(plan)
    return actual_sources == expected_sources


def classify_failure(
    *,
    question: WorkloadQuestion,
    plan: Any,
    answer_exact: bool,
    join_path_exact: bool | None,
    ground_truth_error: str | None = None,
) -> str | None:
    if getattr(plan, "error", None):
        return "plan_error"
    if getattr(plan, "metric_src", None) != question.primary_table:
        return "metric_source_mismatch"
    if question.metric_column and getattr(plan, "metric_col", None) != question.metric_column:
        return "metric_column_mismatch"
    if getattr(plan, "group_src", None) != question.dimension_tables[0]:
        return "group_source_mismatch"
    if getattr(plan, "group_col", None) != question.dimension_columns[0]:
        return "group_column_mismatch"
    if join_path_exact is False:
        return "join_path_mismatch"
    if ground_truth_error:
        if "QueryCanceled" in ground_truth_error:
            return "ground_truth_timeout"
        return "ground_truth_error"
    if not answer_exact:
        return "answer_mismatch"
    return None


def fetch_ground_truth_rows(
    connection: psycopg2.extensions.connection,
    question: WorkloadQuestion,
) -> tuple[dict[str, object], ...]:
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(question.sql)
        rows = cursor.fetchall()
    finally:
        cursor.close()
    return normalize_expected_rows([dict(row) for row in rows])


async def reset_registry_state(sources_dir: Path) -> None:
    reg._SOURCES_DIR = sources_dir
    reg._SCHEMA_REVISION_CACHE.clear()
    reg._SOURCE_SCHEMA_REVISION_CACHE.clear()
    reg._SOURCE_META_CACHE.clear()
    reg._SOURCE_ENTRY_CACHE.clear()
    reg._SOURCE_ENTRY_BY_NAME_CACHE.clear()
    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
    _PLANNER_CACHE.clear()
    _DF_CACHE.clear()
    _RESULT_CACHE.clear()
    _RESOLVE_CACHE.clear()


async def register_workload_tables(
    *,
    auth: AuthContext,
    connection_string: str,
    schema: str,
    table_names: list[str],
    projected_columns_by_table: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, object]:
    registration_latencies: list[float] = []
    connections_total = 0
    for index, table_name in enumerate(table_names, start=1):
        projected_columns = (
            projected_columns_by_table.get(table_name)
            if projected_columns_by_table is not None
            else None
        )
        query = projection_query_for_table(
            schema=schema,
            table_name=table_name,
            projected_columns=projected_columns,
        )
        payload = RegisterRequest(
            source=DataSource(
                name=table_name,
                connection={
                    "type": "sql",
                    "connection_string": connection_string,
                    "query": query,
                },
            )
        )
        started = time.perf_counter()
        response = await register_source(payload, auth=auth)
        registration_latencies.append((time.perf_counter() - started) * 1000.0)
        connections_total += len(
            response.get("connections_found") or response.get("connections") or []
        )
        if index % 5 == 0 or index == len(table_names):
            print(
                f"registration progress sources={index}/{len(table_names)} "
                f"connections={connections_total} "
                f"projected_columns={len(projected_columns or ()) or '*'}",
                file=sys.stderr,
            )
    registration_latencies.sort()
    p90_index = min(
        len(registration_latencies) - 1,
        int(len(registration_latencies) * 0.9),
    )
    return {
        "registered_sources": len(table_names),
        "connections_found": connections_total,
        "projection_mode": "workload" if projected_columns_by_table is not None else "full",
        "projected_column_counts": {
            table_name: len(projected_columns_by_table.get(table_name, ()))
            for table_name in table_names
        }
        if projected_columns_by_table is not None
        else None,
        "latency_ms": {
            "mean": round(sum(registration_latencies) / max(len(registration_latencies), 1), 3),
            "p90": round(
                registration_latencies[p90_index],
                3,
            )
            if registration_latencies
            else None,
            "max": round(max(registration_latencies), 3) if registration_latencies else None,
        },
    }


def _percentile_ms(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * fraction))
    return round(ordered[index], 3)


def summarize_results(
    *,
    schema: str,
    generated_questions: int,
    selected_questions: list[WorkloadQuestion],
    registration_summary: dict[str, object],
    results: list[PlannerBenchmarkResult],
    sources_dir: Path,
) -> dict[str, object]:
    if not results:
        raise RuntimeError("Planner benchmark produced no results.")

    failure_breakdown = Counter(result.failure_class for result in results if result.failure_class)
    kind_breakdown = Counter(result.kind for result in results)
    complexity_breakdown = Counter(result.complexity for result in results)
    planner_latencies = [result.planner_latency_ms for result in results]
    execution_latencies = [
        result.execution_latency_ms for result in results if result.execution_latency_ms is not None
    ]
    two_hop_results = [result for result in results if result.kind == "two_hop_sum"]
    selected_kind_breakdown = Counter(question.kind for question in selected_questions)
    selected_complexity_breakdown = {
        str(key): value for key, value in sorted(complexity_breakdown.items())
    }
    plan_success_rate = round(
        sum(result.plan_error is None for result in results) / len(results),
        4,
    )
    metric_source_top1_accuracy = round(
        sum(result.metric_src_top1 for result in results) / len(results),
        4,
    )
    metric_column_top1_accuracy = round(
        sum(result.metric_col_top1 for result in results) / len(results),
        4,
    )
    group_source_top1_accuracy = round(
        sum(result.group_src_top1 for result in results) / len(results),
        4,
    )
    group_column_top1_accuracy = round(
        sum(result.group_col_top1 for result in results) / len(results),
        4,
    )
    answer_exact_accuracy = round(
        sum(result.answer_exact for result in results) / len(results),
        4,
    )

    return {
        "schema": schema,
        "generated_questions": generated_questions,
        "selected_questions": len(selected_questions),
        "selected_kind_breakdown": dict(sorted(selected_kind_breakdown.items())),
        "selected_complexity_breakdown": selected_complexity_breakdown,
        "sources_dir": str(sources_dir),
        "registration": registration_summary,
        "planner_metrics": {
            "plan_success_rate": plan_success_rate,
            "metric_source_top1_accuracy": metric_source_top1_accuracy,
            "metric_column_top1_accuracy": metric_column_top1_accuracy,
            "group_source_top1_accuracy": group_source_top1_accuracy,
            "group_column_top1_accuracy": group_column_top1_accuracy,
            "join_path_exact_accuracy": round(
                sum(result.join_path_exact is True for result in two_hop_results)
                / len(two_hop_results),
                4,
            )
            if two_hop_results
            else None,
            "answer_exact_accuracy": answer_exact_accuracy,
        },
        "latency_ms": {
            "planner_mean": round(sum(planner_latencies) / len(planner_latencies), 3),
            "planner_p90": _percentile_ms(planner_latencies, 0.9),
            "planner_p95": _percentile_ms(planner_latencies, 0.95),
            "planner_max": round(max(planner_latencies), 3),
            "execution_mean": round(sum(execution_latencies) / len(execution_latencies), 3)
            if execution_latencies
            else None,
            "execution_p90": _percentile_ms(execution_latencies, 0.9),
            "execution_p95": _percentile_ms(execution_latencies, 0.95),
            "execution_max": round(max(execution_latencies), 3) if execution_latencies else None,
        },
        "failure_breakdown": dict(sorted(failure_breakdown.items())),
        "kind_breakdown": dict(sorted(kind_breakdown.items())),
        "sample_failures": [asdict(result) for result in results if result.failure_class][:10],
        "results": [asdict(result) for result in results],
    }


async def run_registry_planner_workload(
    *,
    connection_string: str,
    schema: str,
    per_kind_limit: int,
    statement_timeout_ms: int,
    keep_sources_dir: bool,
    full_table_registration: bool,
) -> dict[str, object]:
    tables = load_schema_tables(connection_string, schema)
    generated_questions = build_workload_questions(schema, tables)
    selected_questions = select_supported_questions(
        generated_questions,
        per_kind_limit=per_kind_limit,
    )
    if not selected_questions:
        raise RuntimeError("No supported planner questions were selected.")

    selected_table_names = sorted(
        {table for question in selected_questions for table in question.expected_tables}
    )
    projected_columns_by_table = (
        None
        if full_table_registration
        else workload_projection_columns(
            tables=tables,
            selected_questions=selected_questions,
        )
    )
    temp_root = Path(
        tempfile.mkdtemp(
            prefix="algenta_live_registry_planner_",
            dir=str(REPO_ROOT / "build"),
        )
    )
    sources_dir = temp_root / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    await reset_registry_state(sources_dir)

    auth: AuthContext = {
        "org_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
        "user_id": None,
        "plan": "enterprise",
        "role": "owner",
        "email": "benchmark@algenta.local",
    }

    registration_summary = await register_workload_tables(
        auth=auth,
        connection_string=connection_string,
        schema=schema,
        table_names=selected_table_names,
        projected_columns_by_table=projected_columns_by_table,
    )

    planner = AutoPlanner.from_registry(str(auth["org_id"]), data_dir=temp_root, llm_policy="never")
    connection = psycopg2.connect(connection_string)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SET statement_timeout = {int(statement_timeout_ms)}")
        results: list[PlannerBenchmarkResult] = []
        for index, question in enumerate(selected_questions, start=1):
            expected_rows: tuple[dict[str, object], ...] = ()
            ground_truth_error: str | None = None
            try:
                expected_rows = fetch_ground_truth_rows(connection, question)
            except psycopg2.Error as exc:
                connection.rollback()
                ground_truth_error = f"{type(exc).__name__}: {exc}".strip()
            inputs = planner_inputs_for_question(question)

            plan_started = time.perf_counter()
            plan = planner.plan(
                inputs.metric_hint,
                inputs.dim_hint,
                inputs.agg,
                inputs.preferred_source,
            )
            planner_latency_ms = round((time.perf_counter() - plan_started) * 1000.0, 3)

            execution_latency_ms: float | None = None
            actual_rows: tuple[dict[str, object], ...] = ()
            planner_trace: tuple[str, ...] = ()
            if not plan.error:
                execution_started = time.perf_counter()
                execution_result, _, trace = planner.execute_plan(
                    plan,
                    limit=SAMPLE_LIMIT,
                    order="desc",
                )
                execution_latency_ms = round((time.perf_counter() - execution_started) * 1000.0, 3)
                actual_rows = normalize_actual_rows(execution_result)
                planner_trace = tuple(trace)

            join_path_exact = join_path_matches_expected(question, plan)
            answer_exact = (
                ground_truth_error is None
                and rows_semantically_match(expected_rows, actual_rows)
                and not plan.error
            )
            failure_class = classify_failure(
                question=question,
                plan=plan,
                answer_exact=answer_exact,
                join_path_exact=join_path_exact,
                ground_truth_error=ground_truth_error,
            )
            results.append(
                PlannerBenchmarkResult(
                    question_id=question.question_id,
                    question=question.question,
                    kind=question.kind,
                    complexity=question.complexity,
                    planner_inputs=asdict(inputs),
                    expected_tables=question.expected_tables,
                    expected_dimension_tables=question.dimension_tables,
                    expected_dimension_columns=question.dimension_columns,
                    expected_metric_column=question.metric_column,
                    planned_metric_src=getattr(plan, "metric_src", None) or None,
                    planned_metric_col=getattr(plan, "metric_col", None) or None,
                    planned_group_src=getattr(plan, "group_src", None) or None,
                    planned_group_col=getattr(plan, "group_col", None) or None,
                    planned_join_sources=join_sources_for_plan(plan),
                    plan_error=getattr(plan, "error", None),
                    ground_truth_error=ground_truth_error,
                    metric_src_top1=getattr(plan, "metric_src", None) == question.primary_table,
                    metric_col_top1=question.metric_column is not None
                    and getattr(plan, "metric_col", None) == question.metric_column,
                    group_src_top1=(
                        getattr(plan, "group_src", None) == question.dimension_tables[0]
                    ),
                    group_col_top1=(
                        getattr(plan, "group_col", None) == question.dimension_columns[0]
                    ),
                    join_path_exact=join_path_exact,
                    answer_exact=answer_exact,
                    planner_latency_ms=planner_latency_ms,
                    execution_latency_ms=execution_latency_ms,
                    failure_class=failure_class,
                    expected_rows=expected_rows,
                    actual_rows=actual_rows,
                    planner_trace=planner_trace,
                )
            )
            if index % 10 == 0 or index == len(selected_questions):
                print(
                    f"planner progress questions={index}/{len(selected_questions)} "
                    f"answer_exact={sum(result.answer_exact for result in results)}",
                    file=sys.stderr,
                )
    finally:
        connection.close()
        if not keep_sources_dir:
            # The parent temp dir is safe to remove at the end of the run.
            import shutil

            shutil.rmtree(temp_root, ignore_errors=True)

    return summarize_results(
        schema=schema,
        generated_questions=len(generated_questions),
        selected_questions=selected_questions,
        registration_summary=registration_summary,
        results=results,
        sources_dir=sources_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Register a live Postgres workload into the local source registry and "
            "benchmark AutoPlanner plan plus execute against SQL ground truth."
        )
    )
    parser.add_argument("--dsn", default=None, help="Postgres connection string.")
    parser.add_argument(
        "--dsn-env",
        default=DEFAULT_DSN_ENV,
        help=f"Environment variable holding the Postgres DSN (default: {DEFAULT_DSN_ENV}).",
    )
    parser.add_argument(
        "--schema",
        default=DEFAULT_SCHEMA,
        help=f"Schema to inspect (default: {DEFAULT_SCHEMA}).",
    )
    parser.add_argument(
        "--per-kind-limit",
        type=int,
        default=DEFAULT_PER_KIND_LIMIT,
        help="Number of questions to execute per supported workload kind.",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=DEFAULT_STATEMENT_TIMEOUT_MS,
        help="Per-statement timeout in milliseconds for ground-truth SQL.",
    )
    parser.add_argument(
        "--keep-sources-dir",
        action="store_true",
        help="Keep the temporary source-registry directory after the run for inspection.",
    )
    parser.add_argument(
        "--full-table-registration",
        action="store_true",
        help=(
            "Register each workload table with SELECT * instead of the workload-driven "
            "projection used by default."
        ),
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Where to write the JSON results (default: {DEFAULT_OUTPUT_PATH}).",
    )
    args = parser.parse_args()

    summary = asyncio.run(
        run_registry_planner_workload(
            connection_string=_resolve_connection_string(args),
            schema=args.schema,
            per_kind_limit=args.per_kind_limit,
            statement_timeout_ms=args.statement_timeout_ms,
            keep_sources_dir=args.keep_sources_dir,
            full_table_registration=args.full_table_registration,
        )
    )

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_without_results = {
        key: value for key, value in summary.items() if key not in {"results", "sample_failures"}
    }
    print(json.dumps(summary_without_results, indent=2))
    print(f"wrote_results={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
