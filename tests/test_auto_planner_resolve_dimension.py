"""Tests for test_auto_planner: resolve_dimension.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-5/tests/test_auto_planner.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_helpers import *  # noqa: F401,F403


def test_resolve_dimension_prefers_exact_preferred_source_anchor(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "S0": {
            "local_group": ColumnNode(name="local_group", role="category", fill_rate=1.0),
        },
        "L0": {
            "local_group": ColumnNode(name="local_group", role="text", fill_rate=1.0),
        },
    }
    planner.profiles = {
        "S0": {
            "local_group": {
                "fill_rate": 1.0,
                "unique_count": 4,
                "total_count": 240,
                "strings": ["g_a", "g_b"],
            },
        },
        "L0": {
            "local_group": {
                "fill_rate": 1.0,
                "unique_count": 4,
                "total_count": 12,
                "strings": ["g_a", "g_b"],
            },
        },
    }

    src, col, score, steps = planner.resolve_dimension("local group", "L0")

    assert (src, col) == ("L0", "local_group")
    assert score > 0.0
    assert any("preferred_exact" in step for step in steps)


def test_resolve_dimension_keeps_exact_two_value_dimension(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "Inventory": {
            "Warehouse": ColumnNode(name="Warehouse", role="category", fill_rate=1.0),
            "User Created": ColumnNode(name="User Created", role="category", fill_rate=1.0),
        }
    }
    planner.profiles = {
        "Inventory": {
            "Warehouse": {
                "fill_rate": 1.0,
                "unique_count": 2,
                "total_count": 120,
                "strings": ["OEP", "WDL", "OEP", "WDL"],
            },
            "User Created": {
                "fill_rate": 1.0,
                "unique_count": 15,
                "total_count": 120,
                "strings": ["alice", "bob", "carol"],
            },
        }
    }

    src, col, score, _steps = planner.resolve_dimension("warehouse", "Inventory")

    assert (src, col) == ("Inventory", "Warehouse")
    assert score > 0.0


def test_resolve_dimension_source_hint_anchors_named_source(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "POSNew": {
            "INVENTORY_TYPE": ColumnNode(
                name="INVENTORY_TYPE", role="metric", is_numeric=True, fill_rate=0.41
            ),
        },
        "Inventory": {
            "PART_TYPE": ColumnNode(name="PART_TYPE", role="category", fill_rate=1.0),
        },
    }
    planner.profiles = {
        "POSNew": {
            "INVENTORY_TYPE": {
                "fill_rate": 0.41,
                "unique_count": 1,
                "total_count": 100,
                "strings": [],
                "sample_values": [1],
            }
        },
        "Inventory": {
            "PART_TYPE": {
                "fill_rate": 1.0,
                "unique_count": 4,
                "total_count": 100,
                "strings": ["consumable", "rotable", "kit"],
                "sample_values": ["consumable", "rotable", "kit"],
            }
        },
    }

    src, col, score, steps = planner.resolve_dimension("pos inventory type", "BookingsNew")

    assert (src, col) == ("POSNew", "INVENTORY_TYPE")
    assert score > 0.0
    assert any("source_hint" in step for step in steps)


def test_resolve_dimension_source_hint_prefers_exact_column_over_variants(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "Inventory": {
            "Product Line": ColumnNode(name="Product Line", role="category", fill_rate=1.0),
            "OS Product Line": ColumnNode(name="OS Product Line", role="category", fill_rate=0.18),
        },
        "Quotes": {
            "STATUS": ColumnNode(name="STATUS", role="category", fill_rate=1.0),
        },
    }
    planner.profiles = {
        "Inventory": {
            "Product Line": {
                "fill_rate": 1.0,
                "unique_count": 1,
                "total_count": 500,
                "strings": ["aamd pl dst"],
                "sample_values": ["aamd pl dst"],
            },
            "OS Product Line": {
                "fill_rate": 0.18,
                "unique_count": 20,
                "total_count": 500,
                "strings": ["leach", "otto", "mil-spec"],
                "sample_values": ["leach", "otto", "mil-spec"],
            },
        },
        "Quotes": {
            "STATUS": {
                "fill_rate": 1.0,
                "unique_count": 4,
                "total_count": 100,
                "strings": ["open", "closed"],
                "sample_values": ["open", "closed"],
            }
        },
    }

    src, col, score, steps = planner.resolve_dimension("inventory product line", "Quotes")

    assert (src, col) == ("Inventory", "Product Line")
    assert score > 0.0
    assert any("source_hint_exact" in step for step in steps)


def test_resolve_dimension_prefers_business_unit_alias_over_acronym_false_positive(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "Bookings": {
            "LEACH_BU": ColumnNode(
                name="LEACH_BU",
                role=query_router.CATEGORY,
                is_numeric=False,
                fill_rate=1.0,
            ),
        },
        "Inventory": {
            "BUY_INIT": ColumnNode(
                name="BUY_INIT",
                role=query_router.CATEGORY,
                is_numeric=False,
                fill_rate=1.0,
            ),
        },
    }
    planner.profiles = {
        "Bookings": {
            "LEACH_BU": {
                "strings": ["Contactors", "Relays"],
                "sample_values": ["Contactors", "Relays"],
                "unique_count": 2,
                "total_count": 10,
                "fill_rate": 1.0,
            },
        },
        "Inventory": {
            "BUY_INIT": {
                "strings": ["AC", "CS"],
                "sample_values": ["AC", "CS"],
                "unique_count": 2,
                "total_count": 10,
                "fill_rate": 1.0,
            },
        },
    }

    src, col, score, _steps = planner.resolve_dimension("business unit", "Bookings")

    assert (src, col) == ("Bookings", "LEACH_BU")
    assert score > 0.8


def test_resolve_dimension_matches_manufacturer_alias_to_mfg_name(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "Bookings": {
            "MFG_NAME": ColumnNode(
                name="MFG_NAME",
                role=query_router.CATEGORY,
                is_numeric=False,
                fill_rate=1.0,
            ),
            "TYPE": ColumnNode(
                name="TYPE",
                role=query_router.CATEGORY,
                is_numeric=False,
                fill_rate=1.0,
            ),
        },
    }
    planner.profiles = {
        "Bookings": {
            "MFG_NAME": {
                "strings": ["Leach International", "Grayhill Inc."],
                "sample_values": ["Leach International", "Grayhill Inc."],
                "unique_count": 2,
                "total_count": 10,
                "fill_rate": 1.0,
            },
            "TYPE": {
                "strings": ["COMMERCIAL", "DEFENSE"],
                "sample_values": ["COMMERCIAL", "DEFENSE"],
                "unique_count": 2,
                "total_count": 10,
                "fill_rate": 1.0,
            },
        },
    }

    src, col, score, _steps = planner.resolve_dimension("manufacturer", "Bookings")

    assert (src, col) == ("Bookings", "MFG_NAME")
    assert score > 0.7


