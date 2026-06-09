"""Tests for test_auto_planner_join_path_scoring: search_join_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-1/tests/test_auto_planner_join_path_scoring.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_join_path_scoring_helpers import *  # noqa: F401,F403


def test_search_join_path_prefers_plain_bridge_over_qualified_shortcut(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "aircraft_lease_agreements": {
            "contract_id": _planner_node("identifier"),
            "lessor_supplier_id": _planner_node("identifier"),
            "maintenance_reserve_usd": _planner_node("base_measure", is_numeric=True),
        },
        "contracts": {
            "id": _planner_node("identifier"),
            "supplier_id": _planner_node("identifier"),
        },
        "suppliers": {
            "id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft_lease_agreements": {
            "contract_id": {
                "fill_rate": 1.0,
                "unique_count": 182,
                "total_count": 182,
                "strings": ["1", "2"],
            },
            "lessor_supplier_id": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 182,
                "strings": ["10", "20"],
            },
            "maintenance_reserve_usd": {
                "fill_rate": 1.0,
                "unique_count": 182,
                "total_count": 182,
                "strings": ["100", "200"],
            },
        },
        "contracts": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 1763,
                "total_count": 1763,
                "strings": ["1", "2"],
            },
            "supplier_id": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 1763,
                "strings": ["10", "20"],
            },
        },
        "suppliers": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 600,
                "strings": ["10", "20"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 600,
                "strings": ["Supplier A", "Supplier B"],
            },
        },
    }
    planner._connections = [
        {
            "source_a_name": "aircraft_lease_agreements",
            "source_b_name": "suppliers",
            "col_a": "lessor_supplier_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 0.055,
        },
        {
            "source_a_name": "aircraft_lease_agreements",
            "source_b_name": "contracts",
            "col_a": "contract_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 0.0508,
        },
        {
            "source_a_name": "contracts",
            "source_b_name": "suppliers",
            "col_a": "supplier_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
    ]

    hops, conf, _notes, error = planner._search_join_path(
        "aircraft_lease_agreements",
        "suppliers",
        group_col="name",
    )

    assert error is None
    assert conf >= 0.14
    assert [(hop.left_source, hop.left_key, hop.right_source, hop.right_key) for hop in hops] == [
        ("aircraft_lease_agreements", "contract_id", "contracts", "id"),
        ("contracts", "supplier_id", "suppliers", "id"),
    ]


def test_search_join_path_prefers_plain_location_hierarchy_over_headquarters_shortcut(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "bag_handling_metrics": {
            "airport_id": _planner_node("identifier"),
            "supplier_id": _planner_node("identifier"),
            "bags_processed": _planner_node("base_measure", is_numeric=True),
        },
        "airports": {
            "id": _planner_node("identifier"),
            "city_id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
        "suppliers": {
            "id": _planner_node("identifier"),
            "hq_city_id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
        "cities": {
            "id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
    }
    planner.profiles = {
        "bag_handling_metrics": {
            "airport_id": {
                "fill_rate": 1.0,
                "unique_count": 3557,
                "total_count": 2350784,
                "strings": ["1", "2"],
            },
            "supplier_id": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 2350784,
                "strings": ["10", "20"],
            },
            "bags_processed": {
                "fill_rate": 1.0,
                "unique_count": 2500,
                "total_count": 2350784,
                "strings": ["100", "200"],
            },
        },
        "airports": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 3557,
                "total_count": 3557,
                "strings": ["1", "2"],
            },
            "city_id": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 3557,
                "strings": ["100", "200"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 3557,
                "total_count": 3557,
                "strings": ["Airport A", "Airport B"],
            },
        },
        "suppliers": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 600,
                "strings": ["10", "20"],
            },
            "hq_city_id": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 600,
                "strings": ["100", "200"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 600,
                "strings": ["Supplier A", "Supplier B"],
            },
        },
        "cities": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 143,
                "strings": ["100", "200"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 143,
                "strings": ["Paris", "Tokyo"],
            },
        },
    }
    planner._connections = [
        {
            "source_a_name": "bag_handling_metrics",
            "source_b_name": "airports",
            "col_a": "airport_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 0.1478,
        },
        {
            "source_a_name": "airports",
            "source_b_name": "cities",
            "col_a": "city_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
        {
            "source_a_name": "bag_handling_metrics",
            "source_b_name": "suppliers",
            "col_a": "supplier_id",
            "col_b": "id",
            "confidence": 0.839,
            "cardinality": "many_to_one",
            "overlap": 0.147,
        },
        {
            "source_a_name": "suppliers",
            "source_b_name": "cities",
            "col_a": "hq_city_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 0.951,
        },
    ]

    hops, conf, _notes, error = planner._search_join_path(
        "bag_handling_metrics",
        "cities",
        group_col="name",
    )

    assert error is None
    assert conf >= 0.14
    assert [(hop.left_source, hop.left_key, hop.right_source, hop.right_key) for hop in hops] == [
        ("bag_handling_metrics", "airport_id", "airports", "id"),
        ("airports", "city_id", "cities", "id"),
    ]


