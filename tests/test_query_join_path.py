from apps.api_server.routers.query import (
    JoinEdgeSpec,
    JoinPathSpec,
    _resolve_join_path,
    execute,
    execute_join_path,
)


def test_resolve_join_path_rejects_fanout_when_requested():
    path = JoinPathSpec(
        base_source="S0",
        group_source="S1",
        reject_on_fanout=True,
        edges=[
            JoinEdgeSpec(
                left_source="S0",
                right_source="S1",
                left_key="entity_key",
                right_key="entity_key",
            )
        ],
    )

    connections = [{
        "source_a_name": "S0",
        "source_b_name": "S1",
        "col_a": "entity_key",
        "col_b": "entity_key",
        "confidence": 0.93,
        "cardinality": "one_to_many",
    }]

    try:
        _resolve_join_path("S0", path, connections)
    except ValueError as exc:
        assert "fanout cardinality 'one_to_many'" in str(exc)
    else:
        raise AssertionError("expected fanout path rejection")


def test_execute_join_path_supports_two_hop_grouping():
    records_by_source = {
        "S0": [
            {"entity_key": "A", "metric_value": 10.0},
            {"entity_key": "B", "metric_value": 5.0},
        ],
        "S1": [
            {"entity_key": "A", "bridge_key": "X"},
            {"entity_key": "B", "bridge_key": "Y"},
        ],
        "S2": [
            {"bridge_key": "X", "group_attr": "G1"},
            {"bridge_key": "Y", "group_attr": "G2"},
        ],
    }

    result, row_count, plan = execute_join_path(
        records_by_source=records_by_source,
        base_source="S0",
        metric_col="metric_value",
        group_source="S2",
        group_col="group_attr",
        ordered_edges=[
            JoinEdgeSpec(
                left_source="S0",
                right_source="S1",
                left_key="entity_key",
                right_key="entity_key",
            ),
            JoinEdgeSpec(
                left_source="S1",
                right_source="S2",
                left_key="bridge_key",
                right_key="bridge_key",
            ),
        ],
        agg="sum",
        limit=None,
        order="desc",
    )

    assert row_count == 2
    assert result == [
        {"group": "G1", "value": 10.0},
        {"group": "G2", "value": 5.0},
    ]
    assert any("Hop 2" in step for step in plan)


def test_execute_join_path_collapses_consistent_terminal_duplicates():
    records_by_source = {
        "S0": [
            {"entity_key": "A", "metric_value": 10.0},
            {"entity_key": "B", "metric_value": 5.0},
        ],
        "S1": [
            {"entity_key": "A", "group_attr": "G1"},
            {"entity_key": "A", "group_attr": "G1"},
            {"entity_key": "B", "group_attr": "G2"},
        ],
    }

    result, row_count, plan = execute_join_path(
        records_by_source=records_by_source,
        base_source="S0",
        metric_col="metric_value",
        group_source="S1",
        group_col="group_attr",
        ordered_edges=[
            JoinEdgeSpec(
                left_source="S0",
                right_source="S1",
                left_key="entity_key",
                right_key="entity_key",
            )
        ],
        agg="sum",
        limit=None,
        order="desc",
    )

    assert row_count == 2
    assert result == [
        {"group": "G1", "value": 10.0},
        {"group": "G2", "value": 5.0},
    ]
    assert any("collapsed 1 duplicate key" in step for step in plan)


def test_execute_join_path_collapses_consistent_intermediate_duplicates():
    records_by_source = {
        "S0": [
            {"entity_key": "A", "metric_value": 10.0},
            {"entity_key": "B", "metric_value": 5.0},
        ],
        "S1": [
            {"entity_key": "A", "bridge_key": "X"},
            {"entity_key": "A", "bridge_key": "X"},
            {"entity_key": "B", "bridge_key": "Y"},
        ],
        "S2": [
            {"bridge_key": "X", "group_attr": "G1"},
            {"bridge_key": "Y", "group_attr": "G2"},
        ],
    }

    result, row_count, plan = execute_join_path(
        records_by_source=records_by_source,
        base_source="S0",
        metric_col="metric_value",
        group_source="S2",
        group_col="group_attr",
        ordered_edges=[
            JoinEdgeSpec(
                left_source="S0",
                right_source="S1",
                left_key="entity_key",
                right_key="entity_key",
            ),
            JoinEdgeSpec(
                left_source="S1",
                right_source="S2",
                left_key="bridge_key",
                right_key="bridge_key",
            ),
        ],
        agg="sum",
        limit=None,
        order="desc",
    )

    assert row_count == 2
    assert result == [
        {"group": "G1", "value": 10.0},
        {"group": "G2", "value": 5.0},
    ]
    assert any("downstream key 'bridge_key'" in step for step in plan)


def test_execute_join_path_rejects_conflicting_terminal_duplicates():
    records_by_source = {
        "S0": [
            {"entity_key": "A", "metric_value": 10.0},
        ],
        "S1": [
            {"entity_key": "A", "group_attr": "G1"},
            {"entity_key": "A", "group_attr": "G9"},
        ],
    }

    result, row_count, plan = execute_join_path(
        records_by_source=records_by_source,
        base_source="S0",
        metric_col="metric_value",
        group_source="S1",
        group_col="group_attr",
        ordered_edges=[
            JoinEdgeSpec(
                left_source="S0",
                right_source="S1",
                left_key="entity_key",
                right_key="entity_key",
            )
        ],
        agg="sum",
        limit=None,
        order="desc",
    )

    assert result is None
    assert row_count == 0
    assert any("conflicting group value 'group_attr' values" in step for step in plan)


def test_execute_join_path_ignores_blank_like_duplicate_group_values():
    records_by_source = {
        "S0": [
            {"entity_key": "A", "metric_value": 10.0},
        ],
        "S1": [
            {"entity_key": "A", "group_attr": "G1"},
            {"entity_key": "A", "group_attr": float("nan")},
        ],
    }

    result, row_count, plan = execute_join_path(
        records_by_source=records_by_source,
        base_source="S0",
        metric_col="metric_value",
        group_source="S1",
        group_col="group_attr",
        ordered_edges=[
            JoinEdgeSpec(
                left_source="S0",
                right_source="S1",
                left_key="entity_key",
                right_key="entity_key",
            )
        ],
        agg="sum",
        limit=None,
        order="desc",
    )

    assert row_count == 1
    assert result == [{"group": "G1", "value": 10.0}]
    assert any("collapsed 1 duplicate key" in step for step in plan)


def test_execute_ignores_nan_metric_values_when_grouping():
    result, row_count, plan = execute(
        records=[
            {"group_attr": "US", "metric_value": 10.0},
            {"group_attr": "US", "metric_value": float("nan")},
            {"group_attr": "CA", "metric_value": 5.0},
        ],
        metric_col="metric_value",
        agg="sum",
        group_col="group_attr",
        date_col=None,
        tr=None,
        limit=None,
        order="desc",
    )

    assert row_count == 3
    assert result == [
        {"group": "US", "value": 10.0},
        {"group": "CA", "value": 5.0},
    ]
    assert any("SUM(`metric_value`) BY `group_attr`" in step for step in plan)


def test_execute_normalizes_numeric_group_keys_and_excludes_blank_like_values():
    result, row_count, plan = execute(
        records=[
            {"group_attr": 1.0, "metric_value": 10.0},
            {"group_attr": 1, "metric_value": 5.0},
            {"group_attr": "None", "metric_value": 7.0},
        ],
        metric_col="metric_value",
        agg="sum",
        group_col="group_attr",
        date_col=None,
        tr=None,
        limit=None,
        order="desc",
    )

    assert row_count == 3
    assert result == [{"group": "1", "value": 15.0}]
    assert any("excluded from results" in step for step in plan)


def test_execute_count_handles_array_valued_metric_column():
    result, row_count, plan = execute(
        records=[
            {"addresses": [{"city": "Denver"}], "number": "1"},
            {"addresses": [{"city": "Aurora"}], "number": "2"},
        ],
        metric_col="addresses",
        agg="count",
        group_col=None,
        date_col=None,
        tr=None,
        limit=None,
        order="desc",
    )

    assert row_count == 2
    assert result == 2
    assert any("COUNT" in step for step in plan)
