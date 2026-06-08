from __future__ import annotations

from typing import Any

from apps.api_server.routers.query_contract import JoinEdgeSpec


def ensure_query_plan_records(planner: Any, *, qplan: Any) -> None:
    planner._ensure_records(qplan.metric_src)
    if qplan.group_src and qplan.group_src != qplan.metric_src:
        planner._ensure_records(qplan.group_src)
    for intermediate_source in qplan.intermediate_sources:
        planner._ensure_records(intermediate_source)


def execute_join_path_plan(
    planner: Any,
    *,
    qplan: Any,
    metric_records: list[dict[str, Any]],
    join_edge_spec_cls: Any,
    execute_join_path_fn: Any,
    limit: int | None,
    order: str,
) -> tuple[Any, int, list[str]]:
    ordered_edges = [
        join_edge_spec_cls(
            left_source=hop.left_source,
            right_source=hop.right_source,
            left_key=hop.left_key,
            right_key=hop.right_key,
            join_type=hop.join_type,
            min_confidence=max(hop.confidence, 0.0),
            expected_cardinality=hop.cardinality or None,
            allow_many_to_many=hop.cardinality == "many_to_many",
        )
        for hop in qplan.join_hops
    ]
    records_by_source = {qplan.metric_src: metric_records}
    for hop in qplan.join_hops:
        if hop.right_source not in records_by_source:
            records_by_source[hop.right_source] = planner.tables.get(hop.right_source, [])
    result = execute_join_path_fn(
        records_by_source=records_by_source,
        base_source=qplan.metric_src,
        metric_col=qplan.metric_col,
        group_source=qplan.group_src,
        group_col=qplan.group_col,
        ordered_edges=ordered_edges,
        agg=qplan.agg,
        limit=limit,
        order=order,
        reject_on_ambiguity=True,
    )
    result_tuple: tuple[Any, int, list[str]] = result
    return result_tuple


def execute_cross_source_plan(
    planner: Any,
    *,
    qplan: Any,
    metric_records: list[dict[str, Any]],
    execute_cross_source_fn: Any,
    limit: int | None,
    order: str,
) -> tuple[Any, int, list[str]]:
    group_records = planner.tables.get(qplan.group_src, [])
    result = execute_cross_source_fn(
        metric_records=metric_records,
        metric_col=qplan.metric_col,
        group_records=group_records,
        group_col=qplan.group_col,
        join_metric_col=qplan.join_key_metric or qplan.metric_col,
        join_group_col=qplan.join_key_group or qplan.group_col,
        agg=qplan.agg,
        limit=limit,
        order=order,
        join_cardinality=qplan.join_cardinality,
    )
    result_tuple: tuple[Any, int, list[str]] = result
    return result_tuple


def execute_single_source_plan(
    planner: Any,
    *,
    qplan: Any,
    metric_records: list[dict[str, Any]],
    execute_fn: Any,
    find_time_column_fn: Any,
    time_range_fn: Any,
    limit: int | None,
    order: str,
    time_filter: str | None,
) -> tuple[Any, int, list[str]]:
    date_col = find_time_column_fn(qplan.metric_src, planner.graph) if time_filter else None
    tr = time_range_fn(time_filter) if time_filter else None
    result = execute_fn(
        records=metric_records,
        metric_col=qplan.metric_col,
        agg=qplan.agg,
        group_col=qplan.group_col,
        date_col=date_col,
        tr=tr,
        limit=limit,
        order=order,
    )
    result_tuple: tuple[Any, int, list[str]] = result
    return result_tuple


def execute_query_plan(
    planner: Any,
    *,
    qplan: Any,
    limit: int | None,
    order: str,
    time_filter: str | None,
    filter_spec: Any | None = None,
) -> tuple[Any, int, list[str]]:
    from apps.api_server.routers.query import (
        _apply_filter_conditions,
        _resolve_filter_conditions,
        execute,
        execute_cross_source,
        execute_join_path,
        find_time_column,
        time_range,
    )

    if qplan.error:
        return None, 0, [f"ERROR: {qplan.error}"]

    ensure_query_plan_records(planner, qplan=qplan)
    metric_records = planner.tables.get(qplan.metric_src, [])
    resolved_filter_conditions = _resolve_filter_conditions(
        source_name=qplan.metric_src,
        filter_spec=filter_spec,
        graph_nodes=planner.graph.get(qplan.metric_src, {}),
        records=metric_records,
    )
    metric_records, filter_plan = _apply_filter_conditions(
        metric_records,
        resolved_filter_conditions,
    )

    if qplan.group_col and qplan.group_src and qplan.join_hops:
        result, row_count, plan = execute_join_path_plan(
            planner,
            qplan=qplan,
            metric_records=metric_records,
            join_edge_spec_cls=JoinEdgeSpec,
            execute_join_path_fn=execute_join_path,
            limit=limit,
            order=order,
        )
        return result, row_count, [*filter_plan, *plan]
    if qplan.group_col and qplan.group_src and qplan.group_src != qplan.metric_src:
        result, row_count, plan = execute_cross_source_plan(
            planner,
            qplan=qplan,
            metric_records=metric_records,
            execute_cross_source_fn=execute_cross_source,
            limit=limit,
            order=order,
        )
        return result, row_count, [*filter_plan, *plan]
    result, row_count, plan = execute_single_source_plan(
        planner,
        qplan=qplan,
        metric_records=metric_records,
        execute_fn=execute,
        find_time_column_fn=find_time_column,
        time_range_fn=time_range,
        limit=limit,
        order=order,
        time_filter=time_filter,
    )
    return result, row_count, [*filter_plan, *plan]
