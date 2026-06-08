"""Tests for test_auto_planner: execute_plan.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-5/tests/test_auto_planner.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_helpers import *  # noqa: F401,F403


def test_execute_plan_uses_join_hops_for_multi_hop_execution(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.tables = {
        "S0": [
            {"CUSTOMER_ID": "C1", "MEASURE_TOTAL": 100.0},
            {"CUSTOMER_ID": "C2", "MEASURE_TOTAL": 50.0},
            {"CUSTOMER_ID": "C3", "MEASURE_TOTAL": 75.0},
        ],
        "S1": [
            {"CUSTOMER_ID": "C1", "GEO_KEY": "G1"},
            {"CUSTOMER_ID": "C2", "GEO_KEY": "G1"},
            {"CUSTOMER_ID": "C3", "GEO_KEY": "G2"},
        ],
        "S2": [
            {"GEO_KEY": "G1", "REGION_LABEL": "east"},
            {"GEO_KEY": "G2", "REGION_LABEL": "west"},
        ],
    }
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
        join_conf=0.931,
        join_cardinality="many_to_one",
        join_hops=[
            JoinHop(
                "S0", "S1", "CUSTOMER_ID", "CUSTOMER_ID", confidence=0.97, cardinality="many_to_one"
            ),
            JoinHop("S1", "S2", "GEO_KEY", "GEO_KEY", confidence=0.96, cardinality="many_to_one"),
        ],
        path_confidence=0.931,
        intermediate_sources=["S1"],
        validation_notes=[],
    )

    result, row_count, trace = planner.execute_plan(qplan, limit=10)

    assert row_count == 3
    assert result == [
        {"group": "east", "value": 150.0},
        {"group": "west", "value": 75.0},
    ]
    assert any("Join-path execution" in step for step in trace)


def test_execute_plan_uses_four_hop_join_execution(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.tables = {
        "S0": [
            {"CUSTOMER_ID": "C1", "MEASURE_TOTAL": 100.0},
            {"CUSTOMER_ID": "C2", "MEASURE_TOTAL": 50.0},
            {"CUSTOMER_ID": "C3", "MEASURE_TOTAL": 75.0},
        ],
        "S1": [
            {"CUSTOMER_ID": "C1", "ACCOUNT_KEY": "A1"},
            {"CUSTOMER_ID": "C2", "ACCOUNT_KEY": "A1"},
            {"CUSTOMER_ID": "C3", "ACCOUNT_KEY": "A2"},
        ],
        "S2": [
            {"ACCOUNT_KEY": "A1", "GEO_KEY": "G1"},
            {"ACCOUNT_KEY": "A2", "GEO_KEY": "G2"},
        ],
        "S3": [
            {"GEO_KEY": "G1", "REGION_KEY": "R1"},
            {"GEO_KEY": "G2", "REGION_KEY": "R2"},
        ],
        "S4": [
            {"REGION_KEY": "R1", "REGION_LABEL": "east"},
            {"REGION_KEY": "R2", "REGION_LABEL": "west"},
        ],
    }
    qplan = QueryPlan(
        metric_src="S0",
        metric_col="MEASURE_TOTAL",
        metric_conf=1.0,
        metric_role="derived_measure",
        agg="sum",
        group_col="REGION_LABEL",
        group_src="S4",
        group_conf=1.0,
        join_key_metric="CUSTOMER_ID",
        join_key_group="REGION_KEY",
        join_conf=0.822,
        join_cardinality="many_to_one",
        join_hops=[
            JoinHop(
                "S0", "S1", "CUSTOMER_ID", "CUSTOMER_ID", confidence=0.97, cardinality="many_to_one"
            ),
            JoinHop(
                "S1", "S2", "ACCOUNT_KEY", "ACCOUNT_KEY", confidence=0.96, cardinality="many_to_one"
            ),
            JoinHop("S2", "S3", "GEO_KEY", "GEO_KEY", confidence=0.95, cardinality="many_to_one"),
            JoinHop(
                "S3", "S4", "REGION_KEY", "REGION_KEY", confidence=0.94, cardinality="many_to_one"
            ),
        ],
        path_confidence=0.822,
        intermediate_sources=["S1", "S2", "S3"],
        validation_notes=[],
    )

    result, row_count, trace = planner.execute_plan(qplan, limit=10)

    assert row_count == 3
    assert result == [
        {"group": "east", "value": 150.0},
        {"group": "west", "value": 75.0},
    ]
    assert any("Join-path execution" in step for step in trace)


def test_execute_plan_uses_six_hop_join_execution(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.tables = {
        "S0": [
            {"CUSTOMER_ID": "C1", "MEASURE_TOTAL": 100.0},
            {"CUSTOMER_ID": "C2", "MEASURE_TOTAL": 50.0},
            {"CUSTOMER_ID": "C3", "MEASURE_TOTAL": 75.0},
        ],
        "S1": [
            {"CUSTOMER_ID": "C1", "ACCOUNT_KEY": "A1"},
            {"CUSTOMER_ID": "C2", "ACCOUNT_KEY": "A1"},
            {"CUSTOMER_ID": "C3", "ACCOUNT_KEY": "A2"},
        ],
        "S2": [
            {"ACCOUNT_KEY": "A1", "GEO_KEY": "G1"},
            {"ACCOUNT_KEY": "A2", "GEO_KEY": "G2"},
        ],
        "S3": [
            {"GEO_KEY": "G1", "REGION_KEY": "R1"},
            {"GEO_KEY": "G2", "REGION_KEY": "R2"},
        ],
        "S4": [
            {"REGION_KEY": "R1", "SEGMENT_KEY": "SG1"},
            {"REGION_KEY": "R2", "SEGMENT_KEY": "SG2"},
        ],
        "S5": [
            {"SEGMENT_KEY": "SG1", "LABEL_KEY": "L1"},
            {"SEGMENT_KEY": "SG2", "LABEL_KEY": "L2"},
        ],
        "S6": [
            {"LABEL_KEY": "L1", "REGION_LABEL": "east"},
            {"LABEL_KEY": "L2", "REGION_LABEL": "west"},
        ],
    }
    qplan = QueryPlan(
        metric_src="S0",
        metric_col="MEASURE_TOTAL",
        metric_conf=1.0,
        metric_role="derived_measure",
        agg="sum",
        group_col="REGION_LABEL",
        group_src="S6",
        group_conf=1.0,
        join_key_metric="CUSTOMER_ID",
        join_key_group="LABEL_KEY",
        join_conf=0.698,
        join_cardinality="many_to_one",
        join_hops=[
            JoinHop(
                "S0", "S1", "CUSTOMER_ID", "CUSTOMER_ID", confidence=0.97, cardinality="many_to_one"
            ),
            JoinHop(
                "S1", "S2", "ACCOUNT_KEY", "ACCOUNT_KEY", confidence=0.96, cardinality="many_to_one"
            ),
            JoinHop("S2", "S3", "GEO_KEY", "GEO_KEY", confidence=0.95, cardinality="many_to_one"),
            JoinHop(
                "S3", "S4", "REGION_KEY", "REGION_KEY", confidence=0.94, cardinality="many_to_one"
            ),
            JoinHop(
                "S4", "S5", "SEGMENT_KEY", "SEGMENT_KEY", confidence=0.93, cardinality="many_to_one"
            ),
            JoinHop(
                "S5", "S6", "LABEL_KEY", "LABEL_KEY", confidence=0.92, cardinality="many_to_one"
            ),
        ],
        path_confidence=0.698,
        intermediate_sources=["S1", "S2", "S3", "S4", "S5"],
        validation_notes=[],
    )

    result, row_count, trace = planner.execute_plan(qplan, limit=10)

    assert row_count == 3
    assert result == [
        {"group": "east", "value": 150.0},
        {"group": "west", "value": 75.0},
    ]
    assert any("Join-path execution" in step for step in trace)


