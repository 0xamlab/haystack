"""Tests for test_auto_planner: plan_builds.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-5/tests/test_auto_planner.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_helpers import *  # noqa: F401,F403


def test_plan_builds_multi_hop_join_path_from_registry_connections(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {"S0": {}, "S1": {}, "S2": {}}
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "MEASURE_TOTAL",
        1.12,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S2",
        "REGION_LABEL",
        1.01,
        ["dimension"],
    )
    planner._connections = [
        {
            "source_a_name": "S0",
            "source_b_name": "S1",
            "col_a": "CUSTOMER_ID",
            "col_b": "CUSTOMER_ID",
            "confidence": 0.97,
            "cardinality": "many_to_one",
        },
        {
            "source_a_name": "S1",
            "source_b_name": "S2",
            "col_a": "GEO_KEY",
            "col_b": "GEO_KEY",
            "confidence": 0.96,
            "cardinality": "many_to_one",
        },
    ]

    plan = planner.plan("total value", "region", "sum", "S0")

    assert plan.error is None
    assert len(plan.join_hops) == 2
    assert [(hop.left_source, hop.right_source) for hop in plan.join_hops] == [
        ("S0", "S1"),
        ("S1", "S2"),
    ]
    assert plan.intermediate_sources == ["S1"]
    assert plan.group_src == "S2"
    assert plan.path_confidence > 0.6
    assert plan.join_key_metric == "CUSTOMER_ID"
    assert plan.join_key_group == "GEO_KEY"
    assert any("multi-hop path" in note for note in plan.validation_notes)


def test_plan_builds_four_hop_join_path_from_registry_connections(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {"S0": {}, "S1": {}, "S2": {}, "S3": {}, "S4": {}}
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "MEASURE_TOTAL",
        1.12,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S4",
        "REGION_LABEL",
        1.01,
        ["dimension"],
    )
    planner._connections = [
        {
            "source_a_name": "S0",
            "source_b_name": "S1",
            "col_a": "CUSTOMER_ID",
            "col_b": "CUSTOMER_ID",
            "confidence": 0.97,
            "cardinality": "many_to_one",
        },
        {
            "source_a_name": "S1",
            "source_b_name": "S2",
            "col_a": "ACCOUNT_KEY",
            "col_b": "ACCOUNT_KEY",
            "confidence": 0.96,
            "cardinality": "many_to_one",
        },
        {
            "source_a_name": "S2",
            "source_b_name": "S3",
            "col_a": "GEO_KEY",
            "col_b": "GEO_KEY",
            "confidence": 0.95,
            "cardinality": "many_to_one",
        },
        {
            "source_a_name": "S3",
            "source_b_name": "S4",
            "col_a": "REGION_KEY",
            "col_b": "REGION_KEY",
            "confidence": 0.94,
            "cardinality": "many_to_one",
        },
    ]

    plan = planner.plan("total value", "region", "sum", "S0")

    assert plan.error is None
    assert len(plan.join_hops) == 4
    assert [(hop.left_source, hop.right_source) for hop in plan.join_hops] == [
        ("S0", "S1"),
        ("S1", "S2"),
        ("S2", "S3"),
        ("S3", "S4"),
    ]
    assert plan.intermediate_sources == ["S1", "S2", "S3"]
    assert plan.group_src == "S4"
    assert plan.path_confidence > 0.7
    assert plan.join_key_metric == "CUSTOMER_ID"
    assert plan.join_key_group == "REGION_KEY"
    assert any("multi-hop path" in note for note in plan.validation_notes)


def test_plan_builds_six_hop_join_path_from_registry_connections(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {"S0": {}, "S1": {}, "S2": {}, "S3": {}, "S4": {}, "S5": {}, "S6": {}}
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "MEASURE_TOTAL",
        1.12,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S6",
        "REGION_LABEL",
        1.01,
        ["dimension"],
    )
    planner._connections = [
        {
            "source_a_name": "S0",
            "source_b_name": "S1",
            "col_a": "CUSTOMER_ID",
            "col_b": "CUSTOMER_ID",
            "confidence": 0.97,
            "cardinality": "many_to_one",
        },
        {
            "source_a_name": "S1",
            "source_b_name": "S2",
            "col_a": "ACCOUNT_KEY",
            "col_b": "ACCOUNT_KEY",
            "confidence": 0.96,
            "cardinality": "many_to_one",
        },
        {
            "source_a_name": "S2",
            "source_b_name": "S3",
            "col_a": "GEO_KEY",
            "col_b": "GEO_KEY",
            "confidence": 0.95,
            "cardinality": "many_to_one",
        },
        {
            "source_a_name": "S3",
            "source_b_name": "S4",
            "col_a": "REGION_KEY",
            "col_b": "REGION_KEY",
            "confidence": 0.94,
            "cardinality": "many_to_one",
        },
        {
            "source_a_name": "S4",
            "source_b_name": "S5",
            "col_a": "SEGMENT_KEY",
            "col_b": "SEGMENT_KEY",
            "confidence": 0.93,
            "cardinality": "many_to_one",
        },
        {
            "source_a_name": "S5",
            "source_b_name": "S6",
            "col_a": "LABEL_KEY",
            "col_b": "LABEL_KEY",
            "confidence": 0.92,
            "cardinality": "many_to_one",
        },
    ]

    plan = planner.plan("total value", "region", "sum", "S0", max_join_hops=6)

    assert plan.error is None
    assert len(plan.join_hops) == 6
    assert [(hop.left_source, hop.right_source) for hop in plan.join_hops] == [
        ("S0", "S1"),
        ("S1", "S2"),
        ("S2", "S3"),
        ("S3", "S4"),
        ("S4", "S5"),
        ("S5", "S6"),
    ]
    assert plan.intermediate_sources == ["S1", "S2", "S3", "S4", "S5"]
    assert plan.group_src == "S6"
    assert plan.path_confidence > 0.5
    assert plan.join_key_metric == "CUSTOMER_ID"
    assert plan.join_key_group == "LABEL_KEY"
    assert any("multi-hop path" in note for note in plan.validation_notes)


