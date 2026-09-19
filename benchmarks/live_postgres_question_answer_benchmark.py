from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DSN_ENV = "LIVE_POSTGRES_BENCHMARK_DSN"
DEFAULT_SCHEMA = "public"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "build" / "live_postgres_question_answer_benchmark.json"
NUMERIC_TYPES = frozenset({"integer", "bigint", "numeric", "double precision", "real", "smallint"})
LABEL_COLUMN_PRIORITY = (
    "name",
    "title",
    "label",
    "full_name",
    "registration",
    "flight_number",
    "pnr_locator",
    "member_number",
    "base_code",
    "iata_code",
    "icao_code",
    "event_code",
    "invoice_number",
    "wo_number",
    "reason_code",
    "code",
    "category",
)
STATUS_COLUMN_PRIORITY = ("status", "case_status", "invoice_status")
TEMPORAL_COLUMN_PRIORITY = (
    "created_at_utc",
    "created_at",
    "recorded_at_utc",
    "reported_at_utc",
    "opened_at_utc",
    "assigned_at_utc",
    "price_date",
    "detected_at_utc",
)
METRIC_NAME_TOKENS = (
    "amount",
    "price",
    "cost",
    "count",
    "minutes",
    "hours",
    "score",
    "delay",
    "revenue",
    "fare",
    "value",
    "usd",
    "emission",
    "burn",
    "bags",
    "passengers",
    "qty",
    "quantity",
    "processed",
    "lost",
    "damaged",
    "mishandled",
    "delayed",
)
CLOSED_STATUS_VALUES = (
    "closed",
    "complete",
    "completed",
    "resolved",
    "cancelled",
    "canceled",
    "paid",
)


@dataclass(frozen=True)
class SchemaColumn:
    name: str
    data_type: str


@dataclass(frozen=True)
class SchemaTable:
    name: str
    approx_rows: int
    columns: tuple[SchemaColumn, ...]


@dataclass(frozen=True)
class JoinEdge:
    source_table: str
    source_column: str
    target_table: str
    target_column: str


@dataclass(frozen=True)
class WorkloadQuestion:
    question_id: str
    question: str
    sql: str
    primary_table: str
    expected_tables: tuple[str, ...]
    dimension_tables: tuple[str, ...]
    dimension_columns: tuple[str, ...]
    metric_column: str | None
    complexity: int
    kind: str


@dataclass(frozen=True)
class WorkloadResult:
    question_id: str
    question: str
    primary_table: str
    expected_tables: tuple[str, ...]
    dimension_tables: tuple[str, ...]
    dimension_columns: tuple[str, ...]
    metric_column: str | None
    complexity: int
    kind: str
    row_count: int
    answer_rows: tuple[dict[str, object], ...]
    primary_top1: bool
    any_expected_top1: bool
    any_expected_top3: bool
    expected_coverage_top6: float
    top_matches: tuple[str, ...]
    predicted_metric_column: str | None
    predicted_dimension_columns: tuple[str | None, ...]
    dimension_top1: bool
    metric_top1: bool


def quote_ident(value: str) -> str:
    return f'"{value.replace('"', '""')}"'


def qualified_table(schema: str, table_name: str) -> str:
    return f"{quote_ident(schema)}.{quote_ident(table_name)}"


def humanize_identifier(value: str) -> str:
    text = value.replace("_", " ").strip()
    replacements = {
        "usd": "USD",
        "pnr": "PNR",
        "utc": "UTC",
        "wo": "WO",
        "id": "ID",
        "csat": "CSAT",
        "nps": "NPS",
        "qty": "quantity",
    }
    words = []
    for word in text.split():
        lowered = word.lower()
        words.append(replacements.get(lowered, lowered))
    return " ".join(words)


def infer_dimension_noun(table_name: str) -> str:
    return humanize_identifier(table_name).lower()


def prioritize_questions(questions: list[WorkloadQuestion]) -> list[WorkloadQuestion]:
    buckets: dict[int, list[WorkloadQuestion]] = defaultdict(list)
    for question in questions:
        buckets[question.complexity].append(question)

    ordered: list[WorkloadQuestion] = []
    complexity_order = sorted(buckets, reverse=True)
    while any(buckets.values()):
        for complexity in complexity_order:
            bucket = buckets[complexity]
            if bucket:
                ordered.append(bucket.pop(0))
    return ordered


def _resolve_connection_string(args: argparse.Namespace) -> str:
    if args.dsn:
        return args.dsn
    env_value = os.environ.get(args.dsn_env)
    if env_value:
        return env_value
    raise SystemExit(
        f"Missing connection string. Pass --dsn or set the {args.dsn_env} environment variable."
    )


def load_schema_tables(connection_string: str, schema: str) -> dict[str, SchemaTable]:
    connection = psycopg2.connect(connection_string)
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT
              t.table_name,
              COALESCE(
                (
                  SELECT reltuples::bigint
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                  WHERE n.nspname = %s AND c.relname = t.table_name
                ),
                0
              ) AS approx_rows
            FROM information_schema.tables t
            WHERE t.table_schema = %s AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
            """,
            (schema, schema),
        )
        row_counts = {
            str(row["table_name"]): int(row["approx_rows"] or 0) for row in cursor.fetchall()
        }
        cursor.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
            """,
            (schema,),
        )
        columns_by_table: dict[str, list[SchemaColumn]] = defaultdict(list)
        for row in cursor.fetchall():
            columns_by_table[str(row["table_name"])].append(
                SchemaColumn(name=str(row["column_name"]), data_type=str(row["data_type"]))
            )
    finally:
        connection.close()

    return {
        table_name: SchemaTable(
            name=table_name,
            approx_rows=row_counts.get(table_name, 0),
            columns=tuple(columns_by_table.get(table_name, [])),
        )
        for table_name in sorted(row_counts)
    }


def load_ranker_catalog(tables: dict[str, SchemaTable]) -> list[dict[str, object]]:
    return [
        {
            "sourceTable": table.name,
            "importTargetTable": table.name,
            "domain": None,
            "importedRowCount": table.approx_rows,
            "primaryKey": [],
            "columns": [column.name for column in table.columns],
        }
        for table in tables.values()
    ]


def candidate_table_names(base_name: str) -> tuple[str, ...]:
    candidates = [base_name, f"{base_name}s", f"{base_name}es"]
    if base_name.endswith("y") and len(base_name) > 1:
        candidates.append(f"{base_name[:-1]}ies")
    return tuple(dict.fromkeys(candidates))


def column_type(table: SchemaTable, column_name: str) -> str | None:
    for column in table.columns:
        if column.name == column_name:
            return column.data_type
    return None


def normalized_type_group(data_type: str | None) -> str | None:
    if data_type is None:
        return None
    lowered = data_type.lower()
    if lowered in NUMERIC_TYPES or lowered in {"serial", "bigserial"}:
        return "numeric"
    if lowered in {"text", "character varying", "character", "varchar"}:
        return "text"
    if lowered == "uuid":
        return "uuid"
    if any(token in lowered for token in ("date", "time")):
        return "temporal"
    return lowered


def column_types_compatible(source_type: str | None, target_type: str | None) -> bool:
    source_group = normalized_type_group(source_type)
    target_group = normalized_type_group(target_type)
    return source_group is not None and source_group == target_group


def infer_join_edges(tables: dict[str, SchemaTable]) -> list[JoinEdge]:
    edges: list[JoinEdge] = []
    for table in tables.values():
        for column in table.columns:
            if not column.name.endswith("_id") or column.name == "id":
                continue
            base_name = column.name[:-3]
            for target_table in candidate_table_names(base_name):
                target = tables.get(target_table)
                if target is None or target.name == table.name:
                    continue
                if any(target_column.name == "id" for target_column in target.columns) and (
                    column_types_compatible(column.data_type, column_type(target, "id"))
                ):
                    edges.append(
                        JoinEdge(
                            source_table=table.name,
                            source_column=column.name,
                            target_table=target.name,
                            target_column="id",
                        )
                    )
    return sorted(
        {
            (edge.source_table, edge.source_column, edge.target_table, edge.target_column): edge
            for edge in edges
        }.values(),
        key=lambda edge: (edge.source_table, edge.source_column, edge.target_table),
    )


def label_column(table: SchemaTable) -> str | None:
    by_name = {column.name: column for column in table.columns}
    for preferred in LABEL_COLUMN_PRIORITY:
        if preferred in by_name:
            return preferred
    for column in table.columns:
        if column.data_type in {"text", "character varying"} and not column.name.endswith("_id"):
            if column.name not in {"status", "severity"}:
                return column.name
    return None


def status_column(table: SchemaTable) -> str | None:
    names = {column.name for column in table.columns}
    for preferred in STATUS_COLUMN_PRIORITY:
        if preferred in names:
            return preferred
    return None


def temporal_column(table: SchemaTable) -> str | None:
    by_name = {column.name: column for column in table.columns}
    for preferred in TEMPORAL_COLUMN_PRIORITY:
        column = by_name.get(preferred)
        if column and any(token in column.data_type for token in ("date", "time")):
            return column.name
    for column in table.columns:
        if any(token in column.data_type for token in ("date", "time")):
            return column.name
    return None


def metric_columns(table: SchemaTable) -> list[str]:
    result = [
        column.name
        for column in table.columns
        if column.data_type in NUMERIC_TYPES
        and any(token in column.name for token in METRIC_NAME_TOKENS)
        and not column.name.endswith("_id")
    ]
    return result


def close_filter_sql(table_alias: str, column_name: str) -> str:
    values = ", ".join(f"'{value}'" for value in CLOSED_STATUS_VALUES)
    return f"LOWER(COALESCE({table_alias}.{quote_ident(column_name)}::text, '')) NOT IN ({values})"


def build_single_dimension_question(
    *,
    schema: str,
    source_table: SchemaTable,
    edge: JoinEdge,
    target_table: SchemaTable,
    metric_column: str,
    aggregator: str,
) -> WorkloadQuestion:
    target_label = label_column(target_table)
    if target_label is None:
        raise ValueError(f"Missing label column for {target_table.name}")

    source_alias = "fact"
    target_alias = "dim"
    aggregate_label = "total" if aggregator == "SUM" else "average"
    metric_phrase = humanize_identifier(metric_column).lower()
    sql = f"""
        SELECT
          {target_alias}.{quote_ident(target_label)} AS entity_label,
          ROUND(
            {aggregator}({source_alias}.{quote_ident(metric_column)})::numeric,
            2
          ) AS metric_value,
          COUNT(*) AS supporting_rows
        FROM {qualified_table(schema, source_table.name)} AS {source_alias}
        JOIN {qualified_table(schema, target_table.name)} AS {target_alias}
          ON {source_alias}.{quote_ident(edge.source_column)}
           = {target_alias}.{quote_ident(edge.target_column)}
        WHERE {source_alias}.{quote_ident(metric_column)} IS NOT NULL
          AND {target_alias}.{quote_ident(target_label)} IS NOT NULL
        GROUP BY 1
        HAVING COUNT(*) > 0
        ORDER BY 2 DESC NULLS LAST, 1
        LIMIT 5
    """.strip()  # noqa: S608
    dimension_phrase = infer_dimension_noun(target_table.name)
    question_id = f"{source_table.name}:{target_table.name}:{metric_column}:{aggregator.lower()}"
    question = (
        f"Which {dimension_phrase} have the highest {aggregate_label} "
        f"{metric_phrase} in {humanize_identifier(source_table.name).lower()}?"
    )
    return WorkloadQuestion(
        question_id=question_id,
        question=question,
        sql=sql,
        primary_table=source_table.name,
        expected_tables=(source_table.name, target_table.name),
        dimension_tables=(target_table.name,),
        dimension_columns=(target_label,),
        metric_column=metric_column,
        complexity=2,
        kind=f"single_dimension_{aggregator.lower()}",
    )


def build_double_dimension_question(
    *,
    schema: str,
    source_table: SchemaTable,
    left_edge: JoinEdge,
    right_edge: JoinEdge,
    left_table: SchemaTable,
    right_table: SchemaTable,
    metric_column: str,
) -> WorkloadQuestion:
    left_label = label_column(left_table)
    right_label = label_column(right_table)
    if left_label is None or right_label is None:
        raise ValueError("Missing label column for joined dimension table")

    source_alias = "fact"
    left_alias = "left_dim"
    right_alias = "right_dim"
    metric_phrase = humanize_identifier(metric_column).lower()
    sql = f"""
        SELECT
          {left_alias}.{quote_ident(left_label)} AS left_entity,
          {right_alias}.{quote_ident(right_label)} AS right_entity,
          ROUND(SUM({source_alias}.{quote_ident(metric_column)})::numeric, 2) AS metric_value,
          COUNT(*) AS supporting_rows
        FROM {qualified_table(schema, source_table.name)} AS {source_alias}
        JOIN {qualified_table(schema, left_table.name)} AS {left_alias}
          ON {source_alias}.{quote_ident(left_edge.source_column)}
           = {left_alias}.{quote_ident(left_edge.target_column)}
        JOIN {qualified_table(schema, right_table.name)} AS {right_alias}
          ON {source_alias}.{quote_ident(right_edge.source_column)}
           = {right_alias}.{quote_ident(right_edge.target_column)}
        WHERE {source_alias}.{quote_ident(metric_column)} IS NOT NULL
          AND {left_alias}.{quote_ident(left_label)} IS NOT NULL
          AND {right_alias}.{quote_ident(right_label)} IS NOT NULL
        GROUP BY 1, 2
        HAVING COUNT(*) > 0
        ORDER BY 3 DESC NULLS LAST, 1, 2
        LIMIT 5
    """.strip()  # noqa: S608
    left_noun = infer_dimension_noun(left_table.name)
    right_noun = infer_dimension_noun(right_table.name)
    question_id = f"{source_table.name}:{left_table.name}:{right_table.name}:{metric_column}:sum"
    question = (
        f"Which {left_noun} and {right_noun} combinations have the highest total "
        f"{metric_phrase} in {humanize_identifier(source_table.name).lower()}?"
    )
    return WorkloadQuestion(
        question_id=question_id,
        question=question,
        sql=sql,
        primary_table=source_table.name,
        expected_tables=(source_table.name, left_table.name, right_table.name),
        dimension_tables=(left_table.name, right_table.name),
        dimension_columns=(left_label, right_label),
        metric_column=metric_column,
        complexity=3,
        kind="double_dimension_sum",
    )


def build_status_backlog_question(
    *,
    schema: str,
    source_table: SchemaTable,
    edge: JoinEdge,
    target_table: SchemaTable,
) -> WorkloadQuestion:
    target_label = label_column(target_table)
    source_status = status_column(source_table)
    if target_label is None or source_status is None:
        raise ValueError("Missing status or label column for backlog question")

    source_alias = "fact"
    target_alias = "dim"
    sql = f"""
        SELECT
          {target_alias}.{quote_ident(target_label)} AS entity_label,
          COUNT(*) AS open_count
        FROM {qualified_table(schema, source_table.name)} AS {source_alias}
        JOIN {qualified_table(schema, target_table.name)} AS {target_alias}
          ON {source_alias}.{quote_ident(edge.source_column)}
           = {target_alias}.{quote_ident(edge.target_column)}
        WHERE {close_filter_sql(source_alias, source_status)}
          AND {target_alias}.{quote_ident(target_label)} IS NOT NULL
        GROUP BY 1
        HAVING COUNT(*) > 0
        ORDER BY 2 DESC, 1
        LIMIT 5
    """.strip()  # noqa: S608
    dimension_phrase = infer_dimension_noun(target_table.name)
    question_id = f"{source_table.name}:{target_table.name}:backlog"
    question = (
        f"Which {dimension_phrase} have the largest open "
        f"{humanize_identifier(source_table.name).lower()} backlog?"
    )
    return WorkloadQuestion(
        question_id=question_id,
        question=question,
        sql=sql,
        primary_table=source_table.name,
        expected_tables=(source_table.name, target_table.name),
        dimension_tables=(target_table.name,),
        dimension_columns=(target_label,),
        metric_column=None,
        complexity=2,
        kind="status_backlog_count",
    )


def build_two_hop_dimension_question(
    *,
    schema: str,
    source_table: SchemaTable,
    bridge_edge: JoinEdge,
    bridge_table: SchemaTable,
    target_edge: JoinEdge,
    target_table: SchemaTable,
    metric_column: str,
) -> WorkloadQuestion:
    target_label = label_column(target_table)
    if target_label is None:
        raise ValueError("Missing label column for two-hop target table")

    source_alias = "fact"
    bridge_alias = "bridge"
    target_alias = "dim"
    metric_phrase = humanize_identifier(metric_column).lower()
    sql = f"""
        SELECT
          {target_alias}.{quote_ident(target_label)} AS entity_label,
          ROUND(SUM({source_alias}.{quote_ident(metric_column)})::numeric, 2) AS metric_value,
          COUNT(*) AS supporting_rows
        FROM {qualified_table(schema, source_table.name)} AS {source_alias}
        JOIN {qualified_table(schema, bridge_table.name)} AS {bridge_alias}
          ON {source_alias}.{quote_ident(bridge_edge.source_column)}
           = {bridge_alias}.{quote_ident(bridge_edge.target_column)}
        JOIN {qualified_table(schema, target_table.name)} AS {target_alias}
          ON {bridge_alias}.{quote_ident(target_edge.source_column)}
           = {target_alias}.{quote_ident(target_edge.target_column)}
        WHERE {source_alias}.{quote_ident(metric_column)} IS NOT NULL
          AND {target_alias}.{quote_ident(target_label)} IS NOT NULL
        GROUP BY 1
        HAVING COUNT(*) > 0
        ORDER BY 2 DESC NULLS LAST, 1
        LIMIT 5
    """.strip()  # noqa: S608
    dimension_phrase = infer_dimension_noun(target_table.name)
    question_id = (
        f"{source_table.name}:{bridge_table.name}:{target_table.name}:{metric_column}:two_hop"
    )
    question = (
        f"Which {dimension_phrase} have the highest total {metric_phrase} in "
        f"{humanize_identifier(source_table.name).lower()} when linked through "
        f"{humanize_identifier(bridge_table.name).lower()}?"
    )
    return WorkloadQuestion(
        question_id=question_id,
        question=question,
        sql=sql,
        primary_table=source_table.name,
        expected_tables=(source_table.name, bridge_table.name, target_table.name),
        dimension_tables=(target_table.name,),
        dimension_columns=(target_label,),
        metric_column=metric_column,
        complexity=3,
        kind="two_hop_sum",
    )


def build_direct_plus_two_hop_question(
    *,
    schema: str,
    source_table: SchemaTable,
    direct_edge: JoinEdge,
    direct_table: SchemaTable,
    bridge_edge: JoinEdge,
    bridge_table: SchemaTable,
    target_edge: JoinEdge,
    target_table: SchemaTable,
    metric_column: str,
) -> WorkloadQuestion:
    direct_label = label_column(direct_table)
    target_label = label_column(target_table)
    if direct_label is None or target_label is None:
        raise ValueError("Missing label columns for multi-hop question")

    source_alias = "fact"
    direct_alias = "direct_dim"
    bridge_alias = "bridge"
    target_alias = "target_dim"
    metric_phrase = humanize_identifier(metric_column).lower()
    sql = f"""
        SELECT
          {direct_alias}.{quote_ident(direct_label)} AS left_entity,
          {target_alias}.{quote_ident(target_label)} AS right_entity,
          ROUND(SUM({source_alias}.{quote_ident(metric_column)})::numeric, 2) AS metric_value,
          COUNT(*) AS supporting_rows
        FROM {qualified_table(schema, source_table.name)} AS {source_alias}
        JOIN {qualified_table(schema, direct_table.name)} AS {direct_alias}
          ON {source_alias}.{quote_ident(direct_edge.source_column)}
           = {direct_alias}.{quote_ident(direct_edge.target_column)}
        JOIN {qualified_table(schema, bridge_table.name)} AS {bridge_alias}
          ON {source_alias}.{quote_ident(bridge_edge.source_column)}
           = {bridge_alias}.{quote_ident(bridge_edge.target_column)}
        JOIN {qualified_table(schema, target_table.name)} AS {target_alias}
          ON {bridge_alias}.{quote_ident(target_edge.source_column)}
           = {target_alias}.{quote_ident(target_edge.target_column)}
        WHERE {source_alias}.{quote_ident(metric_column)} IS NOT NULL
          AND {direct_alias}.{quote_ident(direct_label)} IS NOT NULL
          AND {target_alias}.{quote_ident(target_label)} IS NOT NULL
        GROUP BY 1, 2
        HAVING COUNT(*) > 0
        ORDER BY 3 DESC NULLS LAST, 1, 2
        LIMIT 5
    """.strip()  # noqa: S608
    direct_noun = infer_dimension_noun(direct_table.name)
    target_noun = infer_dimension_noun(target_table.name)
    question_id = ":".join(
        [
            source_table.name,
            direct_table.name,
            bridge_table.name,
            target_table.name,
            metric_column,
        ]
    )
    question = (
        f"Which {direct_noun} and {target_noun} combinations have the highest total "
        f"{metric_phrase} in {humanize_identifier(source_table.name).lower()}?"
    )
    return WorkloadQuestion(
        question_id=question_id,
        question=question,
        sql=sql,
        primary_table=source_table.name,
        expected_tables=(
            source_table.name,
            direct_table.name,
            bridge_table.name,
            target_table.name,
        ),
        dimension_tables=(direct_table.name, target_table.name),
        dimension_columns=(direct_label, target_label),
        metric_column=metric_column,
        complexity=4,
        kind="direct_plus_two_hop_sum",
    )


def build_workload_questions(schema: str, tables: dict[str, SchemaTable]) -> list[WorkloadQuestion]:
    edges = infer_join_edges(tables)
    edges_by_source: dict[str, list[JoinEdge]] = defaultdict(list)
    for edge in edges:
        edges_by_source[edge.source_table].append(edge)

    questions: dict[str, WorkloadQuestion] = {}

    def register(question: WorkloadQuestion) -> None:
        questions.setdefault(question.question_id, question)

    for source_table in tables.values():
        source_edges = [
            edge
            for edge in edges_by_source.get(source_table.name, [])
            if label_column(tables[edge.target_table])
        ]
        metrics = metric_columns(source_table)
        if not metrics:
            continue

        for metric_column in metrics[:3]:
            for edge in source_edges[:4]:
                register(
                    build_single_dimension_question(
                        schema=schema,
                        source_table=source_table,
                        edge=edge,
                        target_table=tables[edge.target_table],
                        metric_column=metric_column,
                        aggregator="SUM",
                    )
                )
                register(
                    build_single_dimension_question(
                        schema=schema,
                        source_table=source_table,
                        edge=edge,
                        target_table=tables[edge.target_table],
                        metric_column=metric_column,
                        aggregator="AVG",
                    )
                )

            if len(source_edges) >= 2:
                for left_index in range(min(len(source_edges), 3)):
                    for right_index in range(left_index + 1, min(len(source_edges), 4)):
                        register(
                            build_double_dimension_question(
                                schema=schema,
                                source_table=source_table,
                                left_edge=source_edges[left_index],
                                right_edge=source_edges[right_index],
                                left_table=tables[source_edges[left_index].target_table],
                                right_table=tables[source_edges[right_index].target_table],
                                metric_column=metric_column,
                            )
                        )

        source_status = status_column(source_table)
        if source_status:
            for edge in source_edges[:3]:
                register(
                    build_status_backlog_question(
                        schema=schema,
                        source_table=source_table,
                        edge=edge,
                        target_table=tables[edge.target_table],
                    )
                )

        for bridge_edge in source_edges[:3]:
            bridge_table = tables[bridge_edge.target_table]
            bridge_edges = [
                edge
                for edge in edges_by_source.get(bridge_table.name, [])
                if edge.target_table != source_table.name
                and label_column(tables[edge.target_table])
            ]
            if not bridge_edges:
                continue
            for metric_column in metrics[:2]:
                for target_edge in bridge_edges[:3]:
                    register(
                        build_two_hop_dimension_question(
                            schema=schema,
                            source_table=source_table,
                            bridge_edge=bridge_edge,
                            bridge_table=bridge_table,
                            target_edge=target_edge,
                            target_table=tables[target_edge.target_table],
                            metric_column=metric_column,
                        )
                    )
                    for direct_edge in source_edges[:3]:
                        if direct_edge.target_table in {
                            bridge_table.name,
                            target_edge.target_table,
                        }:
                            continue
                        if not label_column(tables[direct_edge.target_table]):
                            continue
                        register(
                            build_direct_plus_two_hop_question(
                                schema=schema,
                                source_table=source_table,
                                direct_edge=direct_edge,
                                direct_table=tables[direct_edge.target_table],
                                bridge_edge=bridge_edge,
                                bridge_table=bridge_table,
                                target_edge=target_edge,
                                target_table=tables[target_edge.target_table],
                                metric_column=metric_column,
                            )
                        )

    ordered = sorted(
        questions.values(),
        key=lambda item: (item.complexity, item.kind, item.primary_table, item.question),
    )
    return prioritize_questions(ordered)


def json_safe_value(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    return value


def execute_question(
    connection: psycopg2.extensions.connection,
    question: WorkloadQuestion,
    catalog: object,
    tables: dict[str, SchemaTable],
) -> WorkloadResult | None:
    from apps.api_server.services.data_map_matching import (
        rank_schema_dimension_columns,
        rank_schema_metric_columns,
        rank_schema_table_matches,
    )

    cursor = connection.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(question.sql)
        rows = cursor.fetchall()
    except psycopg2.Error:
        connection.rollback()
        return None
    if not rows:
        return None

    ranked = rank_schema_table_matches(question.question, catalog)
    top_matches = tuple(str(entry["sourceTable"]) for entry in ranked[:6])
    expected_set = set(question.expected_tables)
    coverage = len(expected_set & set(top_matches)) / max(len(expected_set), 1)
    predicted_metric_column: str | None = None
    predicted_dimension_columns: list[str | None] = []
    dimension_top1 = True
    for dimension_table_name, expected_dimension_column in zip(
        question.dimension_tables,
        question.dimension_columns,
        strict=True,
    ):
        dimension_table = tables.get(dimension_table_name)
        if dimension_table is None:
            predicted_dimension_columns.append(None)
            dimension_top1 = False
            continue
        dimension_ranked = rank_schema_dimension_columns(
            question.question,
            [column.name for column in dimension_table.columns],
            table_name=dimension_table.name,
        )
        predicted_dimension_column = (
            str(dimension_ranked[0]["column"]) if dimension_ranked else None
        )
        predicted_dimension_columns.append(predicted_dimension_column)
        if predicted_dimension_column != expected_dimension_column:
            dimension_top1 = False
    metric_top1 = question.metric_column is None
    primary_table = tables.get(question.primary_table)
    if question.metric_column and primary_table is not None:
        metric_ranked = rank_schema_metric_columns(
            question.question,
            [column.name for column in primary_table.columns],
        )
        predicted_metric_column = str(metric_ranked[0]["column"]) if metric_ranked else None
        metric_top1 = predicted_metric_column == question.metric_column

    normalized_rows = tuple(
        {str(key): json_safe_value(value) for key, value in row.items()} for row in rows
    )
    return WorkloadResult(
        question_id=question.question_id,
        question=question.question,
        primary_table=question.primary_table,
        expected_tables=question.expected_tables,
        dimension_tables=question.dimension_tables,
        dimension_columns=question.dimension_columns,
        metric_column=question.metric_column,
        complexity=question.complexity,
        kind=question.kind,
        row_count=len(rows),
        answer_rows=normalized_rows,
        primary_top1=bool(top_matches[:1]) and top_matches[0] == question.primary_table,
        any_expected_top1=bool(top_matches[:1]) and top_matches[0] in expected_set,
        any_expected_top3=any(table in expected_set for table in top_matches[:3]),
        expected_coverage_top6=round(coverage, 4),
        top_matches=top_matches,
        predicted_metric_column=predicted_metric_column,
        predicted_dimension_columns=tuple(predicted_dimension_columns),
        dimension_top1=dimension_top1,
        metric_top1=metric_top1,
    )


def run_workload(
    *,
    connection_string: str,
    schema: str,
    limit_questions: int | None = None,
    statement_timeout_ms: int = 5000,
) -> dict[str, object]:
    tables = load_schema_tables(connection_string, schema)
    from apps.api_server.services.data_map_matching import prepare_schema_catalog

    catalog = prepare_schema_catalog(load_ranker_catalog(tables))
    generated_questions = build_workload_questions(schema, tables)

    connection = psycopg2.connect(connection_string)
    try:
        with connection.cursor() as setup_cursor:
            # Bound parameter, not an f-string: psycopg2 quotes/interpolates the value itself.
            setup_cursor.execute("SET statement_timeout = %s", (int(statement_timeout_ms),))
        results: list[WorkloadResult] = []
        for index, question in enumerate(generated_questions, start=1):
            if limit_questions is not None and len(results) >= limit_questions:
                break
            result = execute_question(connection, question, catalog, tables)
            if result is not None:
                results.append(result)
            if index % 25 == 0:
                progress_message = (
                    f"progress considered={index} kept={len(results)} "
                    f"timeout_ms={statement_timeout_ms}"
                )
                print(
                    progress_message,
                    file=sys.stderr,
                )
    finally:
        connection.close()

    if not results:
        raise RuntimeError("No benchmark questions produced answer rows.")
    return summarize_workload(
        results,
        generated_questions_count=len(generated_questions),
        schema=schema,
    )


def summarize_workload(
    results: list[WorkloadResult],
    *,
    generated_questions_count: int,
    schema: str,
) -> dict[str, object]:
    complexity_breakdown: dict[str, int] = defaultdict(int)
    kind_breakdown: dict[str, int] = defaultdict(int)
    for result in results:
        complexity_breakdown[str(result.complexity)] += 1
        kind_breakdown[result.kind] += 1

    sample_count = len(results)
    dimension_slot_results = [
        predicted_column == expected_column
        for result in results
        for expected_column, predicted_column in zip(
            result.dimension_columns,
            result.predicted_dimension_columns,
            strict=True,
        )
    ]
    dimension_slot_count = len(dimension_slot_results)
    metric_results = [result for result in results if result.metric_column is not None]
    metric_sample_count = len(metric_results)
    return {
        "schema": schema,
        "generated_questions": generated_questions_count,
        "executed_questions": sample_count,
        "primary_top1_accuracy": round(
            sum(result.primary_top1 for result in results) / sample_count,
            4,
        ),
        "any_expected_top1_accuracy": round(
            sum(result.any_expected_top1 for result in results) / sample_count,
            4,
        ),
        "any_expected_top3_accuracy": round(
            sum(result.any_expected_top3 for result in results) / sample_count,
            4,
        ),
        "mean_expected_coverage_top6": round(
            sum(result.expected_coverage_top6 for result in results) / sample_count,
            4,
        ),
        "dimension_question_top1_accuracy": round(
            sum(result.dimension_top1 for result in results) / sample_count,
            4,
        ),
        "dimension_slot_top1_accuracy": round(
            sum(dimension_slot_results) / dimension_slot_count,
            4,
        )
        if dimension_slot_count
        else None,
        "metric_top1_accuracy": round(
            sum(result.metric_top1 for result in metric_results) / metric_sample_count,
            4,
        )
        if metric_sample_count
        else None,
        "complexity_breakdown": dict(
            sorted(complexity_breakdown.items(), key=lambda item: int(item[0]))
        ),
        "kind_breakdown": dict(sorted(kind_breakdown.items())),
        "sample_questions": [asdict(result) for result in results[:10]],
        "results": [asdict(result) for result in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and execute a 100+ question live Postgres benchmark with real SQL answers."
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
        "--limit-questions",
        type=int,
        default=None,
        help="Optional cap on executed questions after non-empty answer filtering.",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=5000,
        help="Per-statement timeout in milliseconds for workload SQL.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Where to write the JSON results (default: {DEFAULT_OUTPUT_PATH}).",
    )
    args = parser.parse_args()

    summary = run_workload(
        connection_string=_resolve_connection_string(args),
        schema=args.schema,
        limit_questions=args.limit_questions,
        statement_timeout_ms=args.statement_timeout_ms,
    )
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_without_rows = {
        key: value for key, value in summary.items() if key not in {"results", "sample_questions"}
    }
    print(json.dumps(summary_without_rows, indent=2))
    print(f"wrote_results={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
