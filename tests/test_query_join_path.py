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

    connections = [
        {
            "source_a_name": "S0",
            "source_b_name": "S1",
            "col_a": "entity_key",
            "col_b": "entity_key",
            "confidence": 0.93,
            "cardinality": "one_to_many",
        }
    ]

    try:
        _resolve_join_path("S0", path, connections)
    except ValueError as exc:
        assert "fanout cardinality 'one_to_many'" in str(exc)
    else:
        raise AssertionError("expected fanout path rejection")


def test_resolve_join_path_rejects_more_than_six_hops():
    path = JoinPathSpec(
        base_source="S0",
        group_source="S7",
        max_hops=6,
        edges=[
            JoinEdgeSpec(left_source="S0", right_source="S1", left_key="k01", right_key="k01"),
            JoinEdgeSpec(left_source="S1", right_source="S2", left_key="k12", right_key="k12"),
            JoinEdgeSpec(left_source="S2", right_source="S3", left_key="k23", right_key="k23"),
            JoinEdgeSpec(left_source="S3", right_source="S4", left_key="k34", right_key="k34"),
            JoinEdgeSpec(left_source="S4", right_source="S5", left_key="k45", right_key="k45"),
            JoinEdgeSpec(left_source="S5", right_source="S6", left_key="k56", right_key="k56"),
            JoinEdgeSpec(left_source="S6", right_source="S7", left_key="k67", right_key="k67"),
        ],
    )

    try:
        _resolve_join_path("S0", path, [])
    except ValueError as exc:
        assert "join_path has 7 edges but max_hops=6" in str(exc)
    else:
        raise AssertionError("expected max_hops rejection")


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


def test_execute_join_path_supports_four_hop_grouping():
    records_by_source = {
        "S0": [
            {"entity_key": "A", "metric_value": 10.0},
            {"entity_key": "B", "metric_value": 5.0},
            {"entity_key": "C", "metric_value": 7.5},
        ],
        "S1": [
            {"entity_key": "A", "bridge_key_1": "X1"},
            {"entity_key": "B", "bridge_key_1": "X2"},
            {"entity_key": "C", "bridge_key_1": "X3"},
        ],
        "S2": [
            {"bridge_key_1": "X1", "bridge_key_2": "Y1"},
            {"bridge_key_1": "X2", "bridge_key_2": "Y1"},
            {"bridge_key_1": "X3", "bridge_key_2": "Y2"},
        ],
        "S3": [
            {"bridge_key_2": "Y1", "bridge_key_3": "Z1"},
            {"bridge_key_2": "Y2", "bridge_key_3": "Z2"},
        ],
        "S4": [
            {"bridge_key_3": "Z1", "group_attr": "G1"},
            {"bridge_key_3": "Z2", "group_attr": "G2"},
        ],
    }

    result, row_count, plan = execute_join_path(
        records_by_source=records_by_source,
        base_source="S0",
        metric_col="metric_value",
        group_source="S4",
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
                left_key="bridge_key_1",
                right_key="bridge_key_1",
            ),
            JoinEdgeSpec(
                left_source="S2",
                right_source="S3",
                left_key="bridge_key_2",
                right_key="bridge_key_2",
            ),
            JoinEdgeSpec(
                left_source="S3",
                right_source="S4",
                left_key="bridge_key_3",
                right_key="bridge_key_3",
            ),
        ],
        agg="sum",
        limit=None,
        order="desc",
    )

    assert row_count == 3
    assert result == [
        {"group": "G1", "value": 15.0},
        {"group": "G2", "value": 7.5},
    ]
    assert any("Hop 4" in step for step in plan)


def test_execute_join_path_supports_six_hop_grouping():
    records_by_source = {
        "S0": [
            {"entity_key": "A", "metric_value": 10.0},
            {"entity_key": "B", "metric_value": 5.0},
            {"entity_key": "C", "metric_value": 7.5},
        ],
        "S1": [
            {"entity_key": "A", "bridge_key_1": "X1"},
            {"entity_key": "B", "bridge_key_1": "X2"},
            {"entity_key": "C", "bridge_key_1": "X3"},
        ],
        "S2": [
            {"bridge_key_1": "X1", "bridge_key_2": "Y1"},
            {"bridge_key_1": "X2", "bridge_key_2": "Y1"},
            {"bridge_key_1": "X3", "bridge_key_2": "Y2"},
        ],
        "S3": [
            {"bridge_key_2": "Y1", "bridge_key_3": "Z1"},
            {"bridge_key_2": "Y2", "bridge_key_3": "Z2"},
        ],
        "S4": [
            {"bridge_key_3": "Z1", "bridge_key_4": "Q1"},
            {"bridge_key_3": "Z2", "bridge_key_4": "Q2"},
        ],
        "S5": [
            {"bridge_key_4": "Q1", "bridge_key_5": "R1"},
            {"bridge_key_4": "Q2", "bridge_key_5": "R2"},
        ],
        "S6": [
            {"bridge_key_5": "R1", "group_attr": "G1"},
            {"bridge_key_5": "R2", "group_attr": "G2"},
        ],
    }

    result, row_count, plan = execute_join_path(
        records_by_source=records_by_source,
        base_source="S0",
        metric_col="metric_value",
        group_source="S6",
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
                left_key="bridge_key_1",
                right_key="bridge_key_1",
            ),
            JoinEdgeSpec(
                left_source="S2",
                right_source="S3",
                left_key="bridge_key_2",
                right_key="bridge_key_2",
            ),
            JoinEdgeSpec(
                left_source="S3",
                right_source="S4",
                left_key="bridge_key_3",
                right_key="bridge_key_3",
            ),
            JoinEdgeSpec(
                left_source="S4",
                right_source="S5",
                left_key="bridge_key_4",
                right_key="bridge_key_4",
            ),
            JoinEdgeSpec(
                left_source="S5",
                right_source="S6",
                left_key="bridge_key_5",
                right_key="bridge_key_5",
            ),
        ],
        agg="sum",
        limit=None,
        order="desc",
    )

    assert row_count == 3
    assert result == [
        {"group": "G1", "value": 15.0},
        {"group": "G2", "value": 7.5},
    ]
    assert any("Hop 6" in step for step in plan)


def test_execute_join_path_count_counts_rows_not_metric_values():
    records_by_source = {
        "S0": [
            {"entity_key": "A", "doc_no": 100.0},
            {"entity_key": "B", "doc_no": 200.0},
            {"entity_key": "C", "doc_no": 300.0},
        ],
        "S1": [
            {"entity_key": "A", "group_attr": "G1"},
            {"entity_key": "B", "group_attr": "G1"},
            {"entity_key": "C", "group_attr": "G2"},
        ],
    }

    result, row_count, plan = execute_join_path(
        records_by_source=records_by_source,
        base_source="S0",
        metric_col="doc_no",
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
        agg="count",
        limit=None,
        order="desc",
    )

    assert row_count == 3
    assert result == [
        {"group": "G1", "value": 2.0},
        {"group": "G2", "value": 1.0},
    ]
    assert any("COUNT(*) BY `group_attr` (join-path)" in step for step in plan)


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


def test_execute_join_path_matches_numeric_equivalent_join_keys():
    records_by_source = {
        "S0": [
            {"entity_key": 1.0, "metric_value": 10.0},
            {"entity_key": 2.0, "metric_value": 5.0},
        ],
        "S1": [
            {"entity_key": 1, "group_attr": "G1"},
            {"entity_key": 2, "group_attr": "G2"},
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
    assert any("matched 2 projected rows" in step for step in plan)


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
