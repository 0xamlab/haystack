from __future__ import annotations

import importlib
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_errors = importlib.import_module("algenta.runtime_errors")
runtime_local_execution = importlib.import_module("algenta.runtime_local_execution")
runtime_local_query = importlib.import_module("algenta.runtime_local_query")
CodnaRuntimeError = runtime_errors.CodnaRuntimeError
LocalSource = runtime_local_execution.LocalSource
infer_numeric_fields = runtime_local_execution.infer_numeric_fields
query_local_request = runtime_local_query.query_local_request
verify_local_request = runtime_local_query.verify_local_request


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


def _plan(metric_column: str = "revenue", group_column: str | None = "product_line"):
    return SimpleNamespace(
        source_name="orders",
        metric_column=metric_column,
        aggregation="sum",
        group_column=group_column,
        filter=None,
        limit=None,
        order="desc",
        constraints={},
        schema_revision="schema_v1",
    )


def test_query_local_request_executes_and_enforces_entitlement() -> None:
    source = _source()
    events: list[str] = []

    result = query_local_request(
        {source.name: source},
        request={"metric": "revenue"},
        kwargs={},
        coerce_plan=lambda request, kwargs: _plan(),
        ensure_local_execution_entitlement=lambda: events.append("entitlement"),
        consume_local_credit=lambda: events.append("credits"),
        plan_hash=lambda plan: "plan_hash_123456",
    )

    assert events == ["entitlement", "credits"]
    assert result.result_type == "table"
    assert result.row_count == 2
    assert result.plan_hash == "plan_hash_123456"
    assert result.request_id == "local_query_plan_hash_12"


def test_query_local_request_includes_filter_steps_in_plan() -> None:
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
        ],
        fields=("product_line", "revenue", "region", "status", "booked_on"),
        schema_revision="schema_v1",
        dataset_id="ds_123",
        numeric_fields=frozenset({"revenue"}),
    )

    result = query_local_request(
        {source.name: source},
        request={"metric": "revenue"},
        kwargs={},
        coerce_plan=lambda request, kwargs: SimpleNamespace(
            source_name="orders",
            metric_column="revenue",
            aggregation="sum",
            group_column=None,
            filter={
                "time_filter": "this_year",
                "conditions": [
                    {"dimension_hint": "status", "op": "eq", "value": "closed"},
                ],
            },
            limit=None,
            order="desc",
            schema_revision="schema_v1",
        ),
        ensure_local_execution_entitlement=lambda: None,
        consume_local_credit=lambda: None,
        plan_hash=lambda plan: "plan_hash_filter_1",
    )

    assert result.result == 10
    assert any("Time filter 'this_year'" in step for step in result.plan)
    assert any("Filter 'status eq 'closed''" in step for step in result.plan)


def test_verify_local_request_returns_structured_error_for_invalid_plan() -> None:
    source = _source()

    result = verify_local_request(
        {source.name: source},
        request={"metric": "revenue"},
        kwargs={},
        coerce_plan=lambda request, kwargs: (_ for _ in ()).throw(
            CodnaRuntimeError("bad_plan", "plan is invalid")
        ),
        plan_hash=lambda plan: "unused",
    )

    assert result.valid is False
    assert result.errors == ["plan is invalid"]
    assert result.rejection_reason == "bad_plan"
    assert result.verification_mode == "local"


def test_verify_local_request_reports_missing_fields() -> None:
    source = _source()

    result = verify_local_request(
        {source.name: source},
        request={"metric": "profit"},
        kwargs={},
        coerce_plan=lambda request, kwargs: _plan(metric_column="profit", group_column="country"),
        plan_hash=lambda plan: "verify_hash_123456",
    )

    assert result.valid is False
    assert result.errors == [
        "Metric column 'profit' is missing.",
        "Group column 'country' is missing.",
    ]
    assert result.plan_hash == "verify_hash_123456"
    assert result.request_id == "local_verify_verify_hash_"


def test_verify_local_request_accepts_valid_plan() -> None:
    source = _source()

    result = verify_local_request(
        {source.name: source},
        request={"metric": "revenue"},
        kwargs={},
        coerce_plan=lambda request, kwargs: _plan(),
        plan_hash=lambda plan: "verify_hash_987654",
    )

    assert result.valid is True
    assert result.errors == []
    assert result.valid_measures == ["revenue"]
    assert result.valid_dimensions == ["product_line"]
