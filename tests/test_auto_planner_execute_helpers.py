from types import SimpleNamespace

from apps.api_server.routers import query as query_router
from apps.api_server.services.auto_planner import JoinHop, QueryPlan
from apps.api_server.services.auto_planner_execute import execute_query_plan


def _unexpected_call(name: str):
    def _raise(**_kwargs):
        raise AssertionError(f"{name} should not be called")

    return _raise


def test_execute_query_plan_returns_error_without_loading_records():
    planner = SimpleNamespace(
        tables={},
        graph={},
        _ensure_records=lambda *_args: (_ for _ in ()).throw(
            AssertionError("_ensure_records should not run for error plans")
        ),
    )
    qplan = QueryPlan(
        metric_src="S0",
        metric_col="VALUE",
        metric_conf=1.0,
        metric_role="derived_measure",
        agg="sum",
        error="bad plan",
    )

    result, row_count, trace = execute_query_plan(
        planner,
        qplan=qplan,
        limit=None,
        order="desc",
        time_filter=None,
    )

    assert result is None
    assert row_count == 0
    assert trace == ["ERROR: bad plan"]


def test_execute_query_plan_dispatches_join_path_and_loads_intermediates(monkeypatch):
    ensure_calls: list[str] = []
    planner = SimpleNamespace(
        tables={
            "S0": [{"CUSTOMER_ID": "C1", "MEASURE_TOTAL": 10.0}],
            "S1": [{"CUSTOMER_ID": "C1", "GEO_KEY": "G1"}],
            "S2": [{"GEO_KEY": "G1", "REGION_LABEL": "east"}],
        },
        graph={},
        _ensure_records=lambda source_name: ensure_calls.append(source_name),
    )
    seen: dict[str, object] = {}

    def _fake_execute_join_path(**kwargs):
        seen.update(kwargs)
        return ([{"group": "east", "value": 10.0}], 1, ["Join-path execution"])

    monkeypatch.setattr(query_router, "execute_join_path", _fake_execute_join_path)
    monkeypatch.setattr(
        query_router, "execute_cross_source", _unexpected_call("execute_cross_source")
    )
    monkeypatch.setattr(query_router, "execute", _unexpected_call("execute"))

    qplan = QueryPlan(
        metric_src="S0",
        metric_col="MEASURE_TOTAL",
        metric_conf=1.0,
        metric_role="derived_measure",
        agg="sum",
        group_col="REGION_LABEL",
        group_src="S2",
        group_conf=1.0,
        join_key_metric="CUSTOMER_ID",
        join_key_group="GEO_KEY",
        join_conf=0.93,
        join_cardinality="many_to_one",
        join_hops=[
            JoinHop("S0", "S1", "CUSTOMER_ID", "CUSTOMER_ID", confidence=0.97),
            JoinHop("S1", "S2", "GEO_KEY", "GEO_KEY", confidence=0.96),
        ],
        path_confidence=0.93,
        intermediate_sources=["S1"],
    )

    result, row_count, trace = execute_query_plan(
        planner,
        qplan=qplan,
        limit=10,
        order="desc",
        time_filter=None,
    )

    assert result == [{"group": "east", "value": 10.0}]
    assert row_count == 1
    assert trace == ["Join-path execution"]
    assert ensure_calls == ["S0", "S2", "S1"]
    assert list(seen["records_by_source"]) == ["S0", "S1", "S2"]
    assert len(seen["ordered_edges"]) == 2
    first_edge = seen["ordered_edges"][0]
    assert first_edge.left_source == "S0"
    assert first_edge.right_source == "S1"
    assert first_edge.left_key == "CUSTOMER_ID"
    assert first_edge.right_key == "CUSTOMER_ID"
    assert first_edge.min_confidence == 0.97
    assert first_edge.allow_many_to_many is False


def test_execute_query_plan_dispatches_cross_source_join(monkeypatch):
    ensure_calls: list[str] = []
    planner = SimpleNamespace(
        tables={
            "Orders": [{"CUSTOMER_ID": "C1", "MEASURE_TOTAL": 100.0}],
            "Customers": [{"GEO_KEY": "G1", "REGION_LABEL": "east"}],
        },
        graph={},
        _ensure_records=lambda source_name: ensure_calls.append(source_name),
    )
    seen: dict[str, object] = {}

    def _fake_execute_cross_source(**kwargs):
        seen.update(kwargs)
        return ([{"group": "east", "value": 100.0}], 1, ["Cross-source execution"])

    monkeypatch.setattr(query_router, "execute_join_path", _unexpected_call("execute_join_path"))
    monkeypatch.setattr(query_router, "execute_cross_source", _fake_execute_cross_source)
    monkeypatch.setattr(query_router, "execute", _unexpected_call("execute"))

    qplan = QueryPlan(
        metric_src="Orders",
        metric_col="MEASURE_TOTAL",
        metric_conf=1.0,
        metric_role="derived_measure",
        agg="sum",
        group_col="REGION_LABEL",
        group_src="Customers",
        group_conf=0.88,
        join_key_metric="CUSTOMER_ID",
        join_key_group="GEO_KEY",
        join_cardinality="many_to_one",
    )

    result, row_count, trace = execute_query_plan(
        planner,
        qplan=qplan,
        limit=5,
        order="asc",
        time_filter=None,
    )

    assert result == [{"group": "east", "value": 100.0}]
    assert row_count == 1
    assert trace == ["Cross-source execution"]
    assert ensure_calls == ["Orders", "Customers"]
    assert seen["join_metric_col"] == "CUSTOMER_ID"
    assert seen["join_group_col"] == "GEO_KEY"
    assert seen["join_cardinality"] == "many_to_one"
    assert seen["limit"] == 5
    assert seen["order"] == "asc"


def test_execute_query_plan_dispatches_single_source_with_time_filter(monkeypatch):
    ensure_calls: list[str] = []
    planner = SimpleNamespace(
        tables={"S0": [{"ORDER_DATE": "2026-04-01", "NET_REVENUE": 100.0}]},
        graph={"S0": {"ORDER_DATE": object()}},
        _ensure_records=lambda source_name: ensure_calls.append(source_name),
    )
    seen: dict[str, object] = {}

    def _fake_find_time_column(source_name, graph):
        seen["find_time_column"] = (source_name, graph)
        return "ORDER_DATE"

    def _fake_time_range(time_filter):
        seen["time_range"] = time_filter
        return ("start", "end")

    def _fake_execute(**kwargs):
        seen["execute"] = kwargs
        return (100.0, 1, ["Single-source execution"])

    monkeypatch.setattr(query_router, "execute_join_path", _unexpected_call("execute_join_path"))
    monkeypatch.setattr(
        query_router, "execute_cross_source", _unexpected_call("execute_cross_source")
    )
    monkeypatch.setattr(query_router, "find_time_column", _fake_find_time_column)
    monkeypatch.setattr(query_router, "time_range", _fake_time_range)
    monkeypatch.setattr(query_router, "execute", _fake_execute)

    qplan = QueryPlan(
        metric_src="S0",
        metric_col="NET_REVENUE",
        metric_conf=1.0,
        metric_role="derived_measure",
        agg="sum",
        group_col="REGION_LABEL",
    )

    result, row_count, trace = execute_query_plan(
        planner,
        qplan=qplan,
        limit=25,
        order="desc",
        time_filter="last_30_days",
    )

    assert result == 100.0
    assert row_count == 1
    assert trace == ["Single-source execution"]
    assert ensure_calls == ["S0"]
    assert seen["find_time_column"] == ("S0", planner.graph)
    assert seen["time_range"] == "last_30_days"
    assert seen["execute"]["date_col"] == "ORDER_DATE"
    assert seen["execute"]["tr"] == ("start", "end")
    assert seen["execute"]["limit"] == 25
