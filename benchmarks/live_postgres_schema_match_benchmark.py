from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType

import psycopg2
from psycopg2.extras import RealDictCursor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DSN_ENV = "LIVE_POSTGRES_BENCHMARK_DSN"
DEFAULT_SCHEMA = "public"


@dataclass(frozen=True)
class BenchmarkQuery:
    query: str
    expected_tables: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkResult:
    query: str
    expected_tables: tuple[str, ...]
    top_matches: tuple[str, ...]
    hit_top_1: bool
    hit_top_3: bool
    hit_top_6: bool


BENCHMARK_QUERIES: tuple[BenchmarkQuery, ...] = (
    BenchmarkQuery(
        query="what are the top 5 airports by fuel price",
        expected_tables=("fuel_prices", "airports"),
    ),
    BenchmarkQuery(
        query="which suppliers have the most overdue invoices",
        expected_tables=("supplier_invoices", "suppliers"),
    ),
    BenchmarkQuery(
        query="what is the maintenance backlog right now",
        expected_tables=("maintenance_work_orders",),
    ),
    BenchmarkQuery(
        query="which crew bases have the highest fatigue scores",
        expected_tables=("crew_fatigue_scores", "crew_bases"),
    ),
    BenchmarkQuery(
        query="Which gates, crews, or turnaround decisions need action first today?",
        expected_tables=("gate_assignments", "crew_assignments"),
    ),
    BenchmarkQuery(
        query="Where are the highest-risk disruptions across the airport network right now?",
        expected_tables=("disruption_event_flights", "disruption_events"),
    ),
    BenchmarkQuery(
        query="How should I rebalance stands, gates, and crews for the next wave?",
        expected_tables=("stand_allocations", "gate_assignments", "crew_assignments"),
    ),
)


def _default_aerogenie_root() -> Path:
    return Path(__file__).resolve().parents[1].parent / "aerogenie-chatbot"


def _load_schema_match_module(aerogenie_root: Path) -> ModuleType:
    script_path = aerogenie_root / "scripts" / "algenta_schema_match.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Schema match script not found at {script_path}")
    spec = importlib.util.spec_from_file_location("algenta_schema_match", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module spec for {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_catalog(connection_string: str, schema: str) -> tuple[list[dict[str, object]], int]:
    connection = psycopg2.connect(connection_string)
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
              table_name,
              COALESCE(
                (
                  SELECT reltuples::bigint
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                  WHERE n.nspname = %s AND c.relname = t.table_name
                ),
                0
              ) AS imported_row_count
            FROM information_schema.tables t
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            (schema, schema),
        )
        tables = cursor.fetchall()
        cursor.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
            """,
            (schema,),
        )
        columns_by_table: dict[str, list[str]] = {}
        for row in cursor.fetchall():
            columns_by_table.setdefault(str(row["table_name"]), []).append(str(row["column_name"]))
    finally:
        connection.close()

    catalog = [
        {
            "sourceTable": str(row["table_name"]),
            "importTargetTable": str(row["table_name"]),
            "domain": None,
            "importedRowCount": int(row["imported_row_count"] or 0),
            "primaryKey": [],
            "columns": columns_by_table.get(str(row["table_name"]), []),
        }
        for row in tables
    ]
    return catalog, len(catalog)


def run_benchmark(
    *,
    schema_match_module: ModuleType,
    catalog: list[dict[str, object]],
    scorer: str = "aerogenie_compat",
    queries: tuple[BenchmarkQuery, ...] = BENCHMARK_QUERIES,
) -> list[BenchmarkResult]:
    from apps.api_server.services.data_map_matching import (
        _semantic_similarity,
        rank_schema_table_matches,
    )

    results: list[BenchmarkResult] = []
    for benchmark_query in queries:
        if scorer == "decision_engine_generic":
            ranked = rank_schema_table_matches(benchmark_query.query, catalog)
        elif scorer == "aerogenie_compat":
            query_terms = schema_match_module._build_query_term_entries(benchmark_query.query)
            ranked = [
                schema_match_module._score_table(query_terms, table, _semantic_similarity)
                for table in catalog
            ]
        else:
            raise ValueError(f"Unsupported scorer: {scorer}")
        ranked = [entry for entry in ranked if float(entry["score"]) >= 0.12]
        top_matches = tuple(str(entry["sourceTable"]) for entry in ranked[:6])
        expected_tables = set(benchmark_query.expected_tables)
        results.append(
            BenchmarkResult(
                query=benchmark_query.query,
                expected_tables=benchmark_query.expected_tables,
                top_matches=top_matches,
                hit_top_1=any(candidate in expected_tables for candidate in top_matches[:1]),
                hit_top_3=any(candidate in expected_tables for candidate in top_matches[:3]),
                hit_top_6=any(candidate in expected_tables for candidate in top_matches[:6]),
            )
        )
    return results


def summarize_results(
    results: list[BenchmarkResult], *, schema: str, table_count: int, scorer: str
) -> dict[str, object]:
    sample_count = len(results)
    if sample_count == 0:
        raise ValueError("At least one benchmark result is required.")
    return {
        "scorer": scorer,
        "schema": schema,
        "table_count": table_count,
        "samples": sample_count,
        "top1_accuracy": round(sum(result.hit_top_1 for result in results) / sample_count, 4),
        "top3_accuracy": round(sum(result.hit_top_3 for result in results) / sample_count, 4),
        "top6_accuracy": round(sum(result.hit_top_6 for result in results) / sample_count, 4),
        "results": [asdict(result) for result in results],
    }


def _resolve_connection_string(args: argparse.Namespace) -> str:
    if args.dsn:
        return args.dsn
    env_value = os.environ.get(args.dsn_env)
    if env_value:
        return env_value
    raise SystemExit(
        f"Missing connection string. Pass --dsn or set the {args.dsn_env} environment variable."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark schema table ranking against live Postgres using Aerogenie prompts."
    )
    parser.add_argument("--dsn", default=None, help="Postgres connection string.")
    parser.add_argument(
        "--dsn-env",
        default=DEFAULT_DSN_ENV,
        help=(
            "Environment variable that contains the connection string "
            f"(default: {DEFAULT_DSN_ENV})."
        ),
    )
    parser.add_argument(
        "--schema",
        default=DEFAULT_SCHEMA,
        help=f"Schema to inspect (default: {DEFAULT_SCHEMA}).",
    )
    parser.add_argument(
        "--aerogenie-root",
        default=str(_default_aerogenie_root()),
        help="Path to the aerogenie-chatbot repository.",
    )
    parser.add_argument(
        "--scorer",
        choices=("aerogenie_compat", "decision_engine_generic"),
        default="aerogenie_compat",
        help="Scoring implementation to benchmark.",
    )
    args = parser.parse_args()

    connection_string = _resolve_connection_string(args)
    schema_match_module = _load_schema_match_module(
        Path(args.aerogenie_root).expanduser().resolve()
    )
    catalog, table_count = _build_catalog(connection_string, args.schema)
    results = run_benchmark(
        schema_match_module=schema_match_module,
        catalog=catalog,
        scorer=args.scorer,
    )
    summary = summarize_results(
        results,
        schema=args.schema,
        table_count=table_count,
        scorer=args.scorer,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
