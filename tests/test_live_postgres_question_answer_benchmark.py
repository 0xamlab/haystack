from benchmarks.live_postgres_question_answer_benchmark import (
    JoinEdge,
    SchemaColumn,
    SchemaTable,
    WorkloadResult,
    build_workload_questions,
    infer_join_edges,
    summarize_workload,
)


def _table(name: str, *columns: tuple[str, str]) -> SchemaTable:
    return SchemaTable(
        name=name,
        approx_rows=100,
        columns=tuple(SchemaColumn(column_name, data_type) for column_name, data_type in columns),
    )


def test_infer_join_edges_detects_suffix_id_relationships() -> None:
    tables = {
        "airports": _table("airports", ("id", "integer"), ("name", "text")),
        "suppliers": _table("suppliers", ("id", "integer"), ("name", "text")),
        "fuel_prices": _table(
            "fuel_prices",
            ("id", "integer"),
            ("airport_id", "integer"),
            ("supplier_id", "integer"),
            ("price_usd_per_l", "numeric"),
        ),
    }

    assert infer_join_edges(tables) == [
        JoinEdge(
            source_table="fuel_prices",
            source_column="airport_id",
            target_table="airports",
            target_column="id",
        ),
        JoinEdge(
            source_table="fuel_prices",
            source_column="supplier_id",
            target_table="suppliers",
            target_column="id",
        ),
    ]


def test_infer_join_edges_skips_type_incompatible_suffix_matches() -> None:
    tables = {
        "customers": _table("customers", ("id", "integer"), ("name", "text")),
        "orders": _table(
            "orders",
            ("id", "integer"),
            ("customer_id", "text"),
            ("amount_usd", "numeric"),
        ),
    }

    assert infer_join_edges(tables) == []


def test_build_workload_questions_generates_multi_table_patterns() -> None:
    tables = {
        "airports": _table("airports", ("id", "integer"), ("name", "text")),
        "routes": _table("routes", ("id", "integer"), ("code", "text")),
        "flights": _table(
            "flights",
            ("id", "integer"),
            ("flight_number", "text"),
            ("route_id", "integer"),
        ),
        "fuel_prices": _table(
            "fuel_prices",
            ("id", "integer"),
            ("airport_id", "integer"),
            ("price_usd_per_l", "numeric"),
        ),
        "fuel_uplifts": _table(
            "fuel_uplifts",
            ("id", "integer"),
            ("flight_id", "integer"),
            ("airport_id", "integer"),
            ("supplier_id", "integer"),
            ("total_cost_usd", "numeric"),
        ),
        "suppliers": _table("suppliers", ("id", "integer"), ("name", "text")),
    }

    questions = build_workload_questions("public", tables)

    assert any(question.complexity == 2 for question in questions)
    assert any(question.complexity == 3 for question in questions)
    assert any(question.complexity == 4 for question in questions)
    assert all("flightss" not in question.question for question in questions)
    assert all(question.dimension_tables for question in questions)
    assert all(question.dimension_columns for question in questions)
    assert all(
        len(question.dimension_tables) == len(question.dimension_columns) for question in questions
    )


def test_summarize_workload_reports_accuracy_and_breakdowns() -> None:
    results = [
        WorkloadResult(
            question_id="q1",
            question="Which airports have the highest total fuel price?",
            primary_table="fuel_prices",
            expected_tables=("fuel_prices", "airports"),
            dimension_tables=("airports",),
            dimension_columns=("name",),
            metric_column="price_usd_per_l",
            complexity=2,
            kind="single_dimension_sum",
            row_count=5,
            answer_rows=({"entity_label": "A", "metric_value": 10},),
            primary_top1=True,
            any_expected_top1=True,
            any_expected_top3=True,
            expected_coverage_top6=1.0,
            top_matches=("fuel_prices", "airports"),
            predicted_metric_column="price_usd_per_l",
            predicted_dimension_columns=("name",),
            dimension_top1=True,
            metric_top1=True,
        ),
        WorkloadResult(
            question_id="q2",
            question="Which airport and route combinations have the highest total cost?",
            primary_table="fuel_uplifts",
            expected_tables=("fuel_uplifts", "airports", "flights", "routes"),
            dimension_tables=("airports", "routes"),
            dimension_columns=("name", "code"),
            metric_column="total_cost_usd",
            complexity=4,
            kind="direct_plus_two_hop_sum",
            row_count=5,
            answer_rows=({"left_entity": "A", "right_entity": "R", "metric_value": 20},),
            primary_top1=False,
            any_expected_top1=False,
            any_expected_top3=True,
            expected_coverage_top6=0.5,
            top_matches=("airports", "fuel_uplifts", "routes"),
            predicted_metric_column="cost_index",
            predicted_dimension_columns=("name", "flight_id"),
            dimension_top1=False,
            metric_top1=False,
        ),
    ]

    summary = summarize_workload(results, generated_questions_count=10, schema="public")

    assert summary["generated_questions"] == 10
    assert summary["executed_questions"] == 2
    assert summary["primary_top1_accuracy"] == 0.5
    assert summary["any_expected_top1_accuracy"] == 0.5
    assert summary["any_expected_top3_accuracy"] == 1.0
    assert summary["mean_expected_coverage_top6"] == 0.75
    assert summary["dimension_question_top1_accuracy"] == 0.5
    assert summary["dimension_slot_top1_accuracy"] == 0.6667
    assert summary["metric_top1_accuracy"] == 0.5
    assert summary["complexity_breakdown"] == {"2": 1, "4": 1}
