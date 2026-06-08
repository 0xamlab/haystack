from __future__ import annotations

import uuid

import pytest

from apps.api_server.routers.data_map import DataSource
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.auto_planner_types import JoinHop, QueryPlan
from benchmarks.live_postgres_question_answer_benchmark import (
    SchemaColumn,
    SchemaTable,
    WorkloadQuestion,
)
from benchmarks.live_postgres_registry_planner_benchmark import (
    classify_failure,
    join_path_matches_expected,
    normalize_actual_rows,
    normalize_expected_rows,
    planner_inputs_for_question,
    projection_query_for_table,
    register_workload_tables,
    rows_semantically_match,
    select_supported_questions,
    workload_projection_columns,
)


def _question(
    *,
    question_id: str,
    kind: str,
    complexity: int,
    primary_table: str = "fact_table",
    expected_tables: tuple[str, ...] = ("fact_table", "dim_table"),
    dimension_tables: tuple[str, ...] = ("dim_table",),
    dimension_columns: tuple[str, ...] = ("name",),
    metric_column: str | None = "metric_value",
) -> WorkloadQuestion:
    return WorkloadQuestion(
        question_id=question_id,
        question=f"question {question_id}",
        sql="SELECT 1",
        primary_table=primary_table,
        expected_tables=expected_tables,
        dimension_tables=dimension_tables,
        dimension_columns=dimension_columns,
        metric_column=metric_column,
        complexity=complexity,
        kind=kind,
    )


def test_select_supported_questions_balances_per_kind() -> None:
    questions = [
        _question(question_id=f"sum-{index}", kind="single_dimension_sum", complexity=2)
        for index in range(3)
    ]
    questions.extend(
        _question(question_id=f"avg-{index}", kind="single_dimension_avg", complexity=2)
        for index in range(3)
    )
    questions.extend(
        _question(
            question_id=f"hop-{index}",
            kind="two_hop_sum",
            complexity=3,
            expected_tables=("fact_table", "bridge_table", "dim_table"),
        )
        for index in range(3)
    )
    questions.append(_question(question_id="ignored", kind="double_dimension_sum", complexity=3))

    selected = select_supported_questions(questions, per_kind_limit=2)

    assert [question.question_id for question in selected] == [
        "sum-0",
        "sum-1",
        "avg-0",
        "avg-1",
        "hop-0",
        "hop-1",
    ]


def test_planner_inputs_for_question_derive_metric_and_dimension_hints() -> None:
    question = _question(
        question_id="q1",
        kind="single_dimension_avg",
        complexity=2,
        primary_table="fuel_prices",
        dimension_tables=("airports",),
        metric_column="avg_price_usd",
    )

    inputs = planner_inputs_for_question(question)

    assert inputs.metric_hint == "avg price USD".lower()
    assert inputs.dim_hint == "airports"
    assert inputs.agg == "avg"
    assert inputs.preferred_source == "fuel_prices"


def test_normalize_expected_rows_rounds_to_supported_execution_precision() -> None:
    rows = [{"entity_label": "JFK", "metric_value": 12.3456, "supporting_rows": 9}]

    assert normalize_expected_rows(rows) == ({"group": "JFK", "value": 12.35},)


def test_normalize_actual_rows_ignores_non_tabular_payloads() -> None:
    assert normalize_actual_rows(None) == ()
    assert normalize_actual_rows(123) == ()
    assert normalize_actual_rows([{"group": "LAX", "value": 4.4444}]) == (
        {"group": "LAX", "value": 4.44},
    )


def test_rows_semantically_match_accepts_tied_top_k_variants() -> None:
    expected_rows = (
        {"group": "A", "value": 4.0},
        {"group": "B", "value": 4.0},
        {"group": "C", "value": 4.0},
    )
    actual_rows = (
        {"group": "X", "value": 4.0},
        {"group": "Y", "value": 4.0},
        {"group": "Z", "value": 4.0},
    )

    assert rows_semantically_match(expected_rows, actual_rows)


def test_rows_semantically_match_accepts_penny_level_average_differences() -> None:
    expected_rows = (
        {"group": "contract A", "value": 173086.25},
        {"group": "contract B", "value": 169038.19},
    )
    actual_rows = (
        {"group": "contract A", "value": 173086.24},
        {"group": "contract B", "value": 169038.18},
    )

    assert rows_semantically_match(expected_rows, actual_rows)


def test_rows_semantically_match_rejects_unique_label_mismatch() -> None:
    expected_rows = (
        {"group": "A", "value": 10.0},
        {"group": "B", "value": 8.0},
    )
    actual_rows = (
        {"group": "A", "value": 10.0},
        {"group": "C", "value": 8.0},
    )

    assert not rows_semantically_match(expected_rows, actual_rows)


def test_join_path_matches_expected_for_two_hop_questions() -> None:
    question = _question(
        question_id="hop",
        kind="two_hop_sum",
        complexity=3,
        expected_tables=("flights", "flight_plans", "airports"),
        dimension_tables=("airports",),
    )
    plan = QueryPlan(
        metric_src="flights",
        metric_col="delay_minutes",
        metric_conf=1.0,
        metric_role="derived_measure",
        agg="sum",
        group_src="airports",
        group_col="name",
        join_hops=[
            JoinHop(
                left_source="flights",
                right_source="flight_plans",
                left_key="flight_plan_id",
                right_key="id",
            ),
            JoinHop(
                left_source="flight_plans",
                right_source="airports",
                left_key="airport_id",
                right_key="id",
            ),
        ],
    )

    assert join_path_matches_expected(question, plan) is True


def test_classify_failure_prioritizes_plan_and_column_mismatches() -> None:
    question = _question(question_id="q1", kind="single_dimension_sum", complexity=2)
    plan = QueryPlan(
        metric_src="other_table",
        metric_col="wrong_metric",
        metric_conf=0.5,
        metric_role="derived_measure",
        agg="sum",
        group_src="fact_table",
        group_col="wrong_group",
    )

    assert (
        classify_failure(
            question=question,
            plan=plan,
            answer_exact=False,
            join_path_exact=None,
            ground_truth_error=None,
        )
        == "metric_source_mismatch"
    )

    plan.metric_src = "fact_table"
    assert (
        classify_failure(
            question=question,
            plan=plan,
            answer_exact=False,
            join_path_exact=None,
            ground_truth_error="QueryCanceled: canceling statement due to statement timeout",
        )
        == "metric_column_mismatch"
    )


def test_classify_failure_marks_ground_truth_timeout_when_plan_shape_is_correct() -> None:
    question = _question(question_id="q-timeout", kind="single_dimension_sum", complexity=2)
    plan = QueryPlan(
        metric_src="fact_table",
        metric_col="metric_value",
        metric_conf=1.0,
        metric_role="derived_measure",
        agg="sum",
        group_src="dim_table",
        group_col="name",
    )

    assert (
        classify_failure(
            question=question,
            plan=plan,
            answer_exact=False,
            join_path_exact=None,
            ground_truth_error="QueryCanceled: canceling statement due to statement timeout",
        )
        == "ground_truth_timeout"
    )


@pytest.mark.anyio
async def test_register_workload_tables_counts_connections_found_from_register_response(
    monkeypatch,
) -> None:
    captured_payloads: list[tuple[str, str]] = []

    async def _fake_register_source(payload, auth):  # type: ignore[no-untyped-def]
        assert isinstance(payload.source, DataSource)
        captured_payloads.append((payload.source.name, payload.source.connection["query"]))
        return {
            "connections_found": [
                {"col_a": "customer_id", "col_b": "id"},
                {"col_a": "airport_id", "col_b": "id"},
            ]
        }

    monkeypatch.setattr(
        "benchmarks.live_postgres_registry_planner_benchmark.register_source",
        _fake_register_source,
    )

    auth: AuthContext = {
        "org_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
        "user_id": None,
        "plan": "enterprise",
        "role": "owner",
        "email": "benchmark@algenta.local",
    }

    summary = await register_workload_tables(
        auth=auth,
        connection_string="postgresql://benchmark",
        schema="public",
        table_names=["orders", "customers"],
        projected_columns_by_table={
            "orders": ("id", "customer_id"),
            "customers": ("id", "name"),
        },
    )

    assert [name for name, _query in captured_payloads] == ["orders", "customers"]
    assert summary["connections_found"] == 4


def test_projection_query_for_table_uses_projected_columns_when_present() -> None:
    query = projection_query_for_table(
        schema="public",
        table_name="flights",
        projected_columns=("id", "airport_id", "delay_minutes"),
    )

    assert query == 'SELECT "id", "airport_id", "delay_minutes" FROM "public"."flights"'


def test_workload_projection_columns_include_metrics_dimensions_and_join_keys() -> None:
    tables = {
        "flights": SchemaTable(
            name="flights",
            approx_rows=100,
            columns=(
                SchemaColumn(name="id", data_type="bigint"),
                SchemaColumn(name="airport_id", data_type="bigint"),
                SchemaColumn(name="delay_minutes", data_type="integer"),
                SchemaColumn(name="status", data_type="text"),
            ),
        ),
        "airports": SchemaTable(
            name="airports",
            approx_rows=10,
            columns=(
                SchemaColumn(name="id", data_type="bigint"),
                SchemaColumn(name="name", data_type="text"),
                SchemaColumn(name="iata_code", data_type="text"),
            ),
        ),
    }
    question = _question(
        question_id="q-projection",
        kind="single_dimension_sum",
        complexity=2,
        primary_table="flights",
        expected_tables=("flights", "airports"),
        dimension_tables=("airports",),
        dimension_columns=("name",),
        metric_column="delay_minutes",
    )

    projected = workload_projection_columns(tables=tables, selected_questions=[question])

    assert projected["flights"] == ("id", "airport_id", "delay_minutes")
    assert projected["airports"] == ("id", "name")
