from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_errors = importlib.import_module("algenta.runtime_errors")
runtime_local_execution = importlib.import_module("algenta.runtime_local_execution")
RuntimeConfigurationError = runtime_errors.RuntimeConfigurationError
RuntimeValidationError = runtime_errors.RuntimeValidationError
LocalSource = runtime_local_execution.LocalSource
collect_local_plan_errors = runtime_local_execution.collect_local_plan_errors
execute_local_plan = runtime_local_execution.execute_local_plan
infer_numeric_fields = runtime_local_execution.infer_numeric_fields
rank_local_fields = runtime_local_execution.rank_local_fields
select_local_source = runtime_local_execution.select_local_source
validate_local_plan = runtime_local_execution.validate_local_plan


def _source() -> LocalSource:
    records = [
        {"product_line": "Electronics", "revenue": 10, "region": "US"},
        {"product_line": "Apparel", "revenue": 20, "region": "CA"},
        {"product_line": "Electronics", "revenue": 30, "region": "US"},
    ]
    fields = ("product_line", "revenue", "region")
    return LocalSource(
        name="orders",
        records=records,
        fields=fields,
        schema_revision="schema_v1",
        dataset_id="ds_123",
        numeric_fields=infer_numeric_fields(records, fields),
    )


def test_select_local_source_matches_dataset_id() -> None:
    source = _source()

    selected = select_local_source({"orders": source}, {"dataset_id": "ds_123"})

    assert selected is source


def test_select_local_source_requires_explicit_name_for_multiple_sources() -> None:
    source = _source()

    with pytest.raises(RuntimeValidationError) as excinfo:
        select_local_source(
            {
                "orders": source,
                "orders_copy": LocalSource(**{**source.__dict__, "name": "orders_copy"}),
            },
            {},
        )

    assert excinfo.value.code == "source_required"


def test_select_local_source_requires_connected_source() -> None:
    with pytest.raises(RuntimeConfigurationError) as excinfo:
        select_local_source({}, {})

    assert excinfo.value.code == "source_required"


def test_rank_local_fields_prefers_exact_numeric_match() -> None:
    ranked = rank_local_fields(_source(), "revenue", numeric_only=True)

    assert ranked[0].field == "revenue"
    assert ranked[0].score == 1.0
    assert ranked[0].is_numeric is True


def test_infer_numeric_fields_profiles_numeric_columns_once() -> None:
    source = _source()

    assert source.numeric_fields == frozenset({"revenue"})


def test_rank_local_fields_uses_precomputed_numeric_profile(monkeypatch) -> None:
    source = _source()

    def _unexpected_numeric_scan(*args, **kwargs):
        raise AssertionError("_is_numeric_field should not run during rank_local_fields()")

    monkeypatch.setattr(runtime_local_execution, "_is_numeric_field", _unexpected_numeric_scan)

    ranked = rank_local_fields(source, "revenue", numeric_only=True)

    assert ranked[0].field == "revenue"


def test_validate_and_execute_local_plan_return_scalar_and_table_shapes() -> None:
    source = _source()
    local_sources = {source.name: source}

    scalar_plan = SimpleNamespace(
        source_name="orders",
        metric_column="revenue",
        group_column=None,
        aggregation="sum",
        limit=None,
        schema_revision="schema_v1",
    )
    grouped_plan = SimpleNamespace(
        source_name="orders",
        metric_column="revenue",
        group_column="product_line",
        aggregation="sum",
        limit=None,
        schema_revision="schema_v1",
    )

    assert validate_local_plan(local_sources, scalar_plan) is source

    scalar_result = execute_local_plan(source, scalar_plan)
    grouped_result = execute_local_plan(source, grouped_plan)

    assert scalar_result.result_type == "scalar"
    assert scalar_result.value == 60
    assert scalar_result.row_count == 1
    assert grouped_result.result_type == "table"
    assert grouped_result.row_count == 2


def test_execute_local_plan_applies_time_and_generic_filter_conditions() -> None:
    current_year = date.today().year
    source = LocalSource(
        name="orders",
        records=[
            {
                "product_line": "Electronics",
                "revenue": 10,
                "region": "US",
                "status": "closed",
                "booked_on": f"{current_year}-01-15",
            },
            {
                "product_line": "Electronics",
                "revenue": 20,
                "region": "US",
                "status": "open",
                "booked_on": f"{current_year}-02-15",
            },
            {
                "product_line": "Apparel",
                "revenue": 30,
                "region": "CA",
                "status": "closed",
                "booked_on": f"{current_year - 1}-03-10",
            },
        ],
        fields=("product_line", "revenue", "region", "status", "booked_on"),
        schema_revision="schema_v1",
        dataset_id="ds_123",
        numeric_fields=frozenset({"revenue"}),
    )

    filtered_plan = SimpleNamespace(
        source_name="orders",
        metric_column="revenue",
        group_column=None,
        aggregation="sum",
        limit=None,
        schema_revision="schema_v1",
        filter={
            "time_filter": "this_year",
            "conditions": [
                {"dimension_hint": "status", "op": "eq", "value": "closed"},
            ],
        },
    )

    filtered_result = execute_local_plan(source, filtered_plan)

    assert filtered_result.result_type == "scalar"
    assert filtered_result.value == 10
    assert any("Time filter 'this_year'" in step for step in filtered_result.plan_steps)
    assert any("Filter 'status eq 'closed''" in step for step in filtered_result.plan_steps)


def test_collect_local_plan_errors_reports_missing_source_and_columns() -> None:
    source = _source()

    missing_source_errors = collect_local_plan_errors(
        {},
        SimpleNamespace(
            source_name="orders",
            metric_column="revenue",
            group_column=None,
            schema_revision="schema_v1",
        ),
    )
    invalid_plan_errors = collect_local_plan_errors(
        {source.name: source},
        SimpleNamespace(
            source_name="orders",
            metric_column="profit",
            group_column="country",
            schema_revision="schema_v2",
        ),
    )

    assert missing_source_errors == ["Source 'orders' is not connected."]
    assert invalid_plan_errors == [
        "schema_revision mismatch",
        "Metric column 'profit' is missing.",
        "Group column 'country' is missing.",
    ]


def test_collect_local_plan_errors_reports_invalid_filter_condition() -> None:
    source = _source()

    errors = collect_local_plan_errors(
        {source.name: source},
        SimpleNamespace(
            source_name="orders",
            metric_column="revenue",
            group_column=None,
            schema_revision="schema_v1",
            filter={
                "conditions": [
                    {"dimension_hint": "priority", "op": "eq", "value": "high"},
                ]
            },
        ),
    )

    assert errors == ["Filter dimension_hint 'priority' did not resolve on source 'orders'."]


def test_collect_local_plan_errors_rejects_unsupported_filter_operator() -> None:
    source = _source()

    errors = collect_local_plan_errors(
        {source.name: source},
        SimpleNamespace(
            source_name="orders",
            metric_column="revenue",
            group_column=None,
            schema_revision="schema_v1",
            filter={
                "conditions": [
                    {"dimension_hint": "region", "op": "contains", "value": "US"},
                ]
            },
        ),
    )

    assert errors == ["Unsupported filter operator 'contains'."]


def test_collect_local_plan_errors_rejects_invalid_scalar_list_filter_shape() -> None:
    source = _source()

    errors = collect_local_plan_errors(
        {source.name: source},
        SimpleNamespace(
            source_name="orders",
            metric_column="revenue",
            group_column=None,
            schema_revision="schema_v1",
            filter={
                "conditions": [
                    {"dimension_hint": "region", "op": "in", "value": "US"},
                ]
            },
        ),
    )

    assert errors == ["filter condition op='in' does not accept value"]
