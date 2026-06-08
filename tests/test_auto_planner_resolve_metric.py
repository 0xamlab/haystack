"""Tests for test_auto_planner: resolve_metric.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-5/tests/test_auto_planner.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_helpers import *  # noqa: F401,F403


def test_resolve_metric_prefers_unit_cost_over_extended_cost_for_unit_cost_hint(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "POS": {
            "UNIT_COST": ColumnNode(
                name="UNIT_COST",
                role=UNIT_MEASURE,
                is_numeric=True,
                magnitude_class="medium",
                fill_rate=1.0,
            ),
            "EXT_COST": ColumnNode(
                name="EXT_COST",
                role=DERIVED_MEASURE,
                is_numeric=True,
                magnitude_class="large",
                fill_rate=1.0,
            ),
            "OH_COST": ColumnNode(
                name="OH_COST",
                role=DERIVED_MEASURE,
                is_numeric=True,
                magnitude_class="medium",
                fill_rate=1.0,
            ),
        }
    }
    planner.profiles = {
        "POS": {
            "UNIT_COST": {
                "is_numeric": True,
                "numeric": [10.0, 12.0],
                "fill_rate": 1.0,
                "mean": 11.0,
                "std": 1.0,
                "sample_values": [10.0, 12.0],
                "strings": [],
                "unique_count": 2,
                "total_count": 2,
            },
            "EXT_COST": {
                "is_numeric": True,
                "numeric": [100.0, 120.0],
                "fill_rate": 1.0,
                "mean": 110.0,
                "std": 10.0,
                "sample_values": [100.0, 120.0],
                "strings": [],
                "unique_count": 2,
                "total_count": 2,
            },
            "OH_COST": {
                "is_numeric": True,
                "numeric": [80.0, 90.0],
                "fill_rate": 1.0,
                "mean": 85.0,
                "std": 5.0,
                "sample_values": [80.0, 90.0],
                "strings": [],
                "unique_count": 2,
                "total_count": 2,
            },
        }
    }

    src, col, conf, role, steps = planner.resolve_metric("unit cost", "POS", "avg")

    assert (src, col, role) == ("POS", "UNIT_COST", UNIT_MEASURE)
    assert conf > 0.6
    assert any("gap" in step for step in steps)


def test_resolve_metric_prefers_extended_cost_for_total_cost_hint(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "POS": {
            "UNIT_COST": ColumnNode(
                name="UNIT_COST",
                role=UNIT_MEASURE,
                is_numeric=True,
                magnitude_class="medium",
                fill_rate=1.0,
            ),
            "EXT_COST": ColumnNode(
                name="EXT_COST",
                role=DERIVED_MEASURE,
                is_numeric=True,
                magnitude_class="large",
                fill_rate=1.0,
            ),
            "OH_COST": ColumnNode(
                name="OH_COST",
                role=DERIVED_MEASURE,
                is_numeric=True,
                magnitude_class="medium",
                fill_rate=1.0,
            ),
        }
    }
    planner.profiles = {
        "POS": {
            "UNIT_COST": {
                "is_numeric": True,
                "numeric": [10.0, 12.0],
                "fill_rate": 1.0,
                "mean": 11.0,
                "std": 1.0,
                "sample_values": [10.0, 12.0],
                "strings": [],
                "unique_count": 2,
                "total_count": 2,
            },
            "EXT_COST": {
                "is_numeric": True,
                "numeric": [100.0, 120.0],
                "fill_rate": 1.0,
                "mean": 110.0,
                "std": 10.0,
                "sample_values": [100.0, 120.0],
                "strings": [],
                "unique_count": 2,
                "total_count": 2,
            },
            "OH_COST": {
                "is_numeric": True,
                "numeric": [80.0, 90.0],
                "fill_rate": 1.0,
                "mean": 85.0,
                "std": 5.0,
                "sample_values": [80.0, 90.0],
                "strings": [],
                "unique_count": 2,
                "total_count": 2,
            },
        }
    }

    src, col, conf, role, _steps = planner.resolve_metric("total cost", "POS", "sum")

    assert (src, col, role) == ("POS", "EXT_COST", DERIVED_MEASURE)
    assert conf > 0.6


def test_resolve_metric_overhead_cost_selected_for_oh_hint(tmp_path):
    """OH_COST (overhead) beats UNIT_COST when the hint explicitly says 'overhead'."""
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "WH": {
            "UNIT_COST": ColumnNode(
                name="UNIT_COST",
                role=UNIT_MEASURE,
                is_numeric=True,
                magnitude_class="medium",
                fill_rate=1.0,
            ),
            "OH_COST": ColumnNode(
                name="OH_COST",
                role=DERIVED_MEASURE,
                is_numeric=True,
                magnitude_class="medium",
                fill_rate=1.0,
            ),
            "EXT_COST": ColumnNode(
                name="EXT_COST",
                role=DERIVED_MEASURE,
                is_numeric=True,
                magnitude_class="large",
                fill_rate=1.0,
            ),
        }
    }
    planner.profiles = {
        "WH": {
            "UNIT_COST": {
                "is_numeric": True,
                "numeric": [5.0],
                "fill_rate": 1.0,
                "mean": 5.0,
                "std": 1.0,
                "sample_values": [5.0],
                "strings": [],
                "unique_count": 1,
                "total_count": 1,
            },
            "OH_COST": {
                "is_numeric": True,
                "numeric": [20.0],
                "fill_rate": 1.0,
                "mean": 20.0,
                "std": 2.0,
                "sample_values": [20.0],
                "strings": [],
                "unique_count": 1,
                "total_count": 1,
            },
            "EXT_COST": {
                "is_numeric": True,
                "numeric": [80.0],
                "fill_rate": 1.0,
                "mean": 80.0,
                "std": 5.0,
                "sample_values": [80.0],
                "strings": [],
                "unique_count": 1,
                "total_count": 1,
            },
        }
    }

    src, col, conf, role, steps = planner.resolve_metric("overhead cost", "WH", "sum")

    assert col == "OH_COST"
    assert conf > 0.5
    # The planner must note the gap so the caller can surface ambiguity
    assert any("gap" in step for step in steps)


def test_resolve_metric_query_hints_prefers_strong_match_in_preferred_source(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner._query_hints_by_src = {
        "S0": [
            {
                "metric_role": "derived_measure",
                "columns": [
                    {"name": "measure_total", "fill_rate": 1.0, "formula": "quantity * unit_rate"}
                ],
            }
        ],
        "I0": [
            {
                "metric_role": "derived_measure",
                "columns": [{"name": "measure_total", "fill_rate": 1.0}],
            }
        ],
    }

    src, col, conf, role, steps = planner.resolve_metric("total value", "I0", "sum")

    assert (src, col, role) == ("I0", "measure_total", "derived_measure")
    assert conf >= 0.45
    assert any("query_hints/registry" in step for step in steps)


def test_resolve_metric_query_hints_uses_canonical_tokens_for_overhead_cost(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner._query_hints_by_src = {
        "C0": [
            {
                "metric_role": "derived_measure",
                "columns": [
                    {"name": "EXT_COST", "fill_rate": 1.0, "formula": "qty * unit_cost"},
                    {"name": "OH_COST", "fill_rate": 1.0},
                ],
            }
        ],
    }

    src, col, conf, role, _steps = planner.resolve_metric("overhead cost", "C0", "sum")

    assert (src, col, role) == ("C0", "OH_COST", "derived_measure")
    assert conf >= 0.45


def test_resolve_metric_unit_cost_beats_ext_cost_on_source_prior(tmp_path):
    """Source-prior bonus (POS → unit cost) should hold across sources."""
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "POS": {
            "UNIT_COST": ColumnNode(
                name="UNIT_COST",
                role=UNIT_MEASURE,
                is_numeric=True,
                magnitude_class="medium",
                fill_rate=1.0,
            ),
            "EXT_COST": ColumnNode(
                name="EXT_COST",
                role=DERIVED_MEASURE,
                is_numeric=True,
                magnitude_class="large",
                fill_rate=1.0,
            ),
        },
        "Backlog": {
            "UNIT_COST": ColumnNode(
                name="UNIT_COST",
                role=UNIT_MEASURE,
                is_numeric=True,
                magnitude_class="medium",
                fill_rate=1.0,
            ),
            "EXT_PRICE": ColumnNode(
                name="EXT_PRICE",
                role=DERIVED_MEASURE,
                is_numeric=True,
                magnitude_class="large",
                fill_rate=1.0,
            ),
        },
    }
    planner.profiles = {
        "POS": {
            "UNIT_COST": {
                "is_numeric": True,
                "numeric": [10.0],
                "fill_rate": 1.0,
                "mean": 10.0,
                "std": 1.0,
                "sample_values": [10.0],
                "strings": [],
                "unique_count": 1,
                "total_count": 1,
            },
            "EXT_COST": {
                "is_numeric": True,
                "numeric": [100.0],
                "fill_rate": 1.0,
                "mean": 100.0,
                "std": 5.0,
                "sample_values": [100.0],
                "strings": [],
                "unique_count": 1,
                "total_count": 1,
            },
        },
        "Backlog": {
            "UNIT_COST": {
                "is_numeric": True,
                "numeric": [12.0],
                "fill_rate": 1.0,
                "mean": 12.0,
                "std": 1.0,
                "sample_values": [12.0],
                "strings": [],
                "unique_count": 1,
                "total_count": 1,
            },
            "EXT_PRICE": {
                "is_numeric": True,
                "numeric": [120.0],
                "fill_rate": 1.0,
                "mean": 120.0,
                "std": 6.0,
                "sample_values": [120.0],
                "strings": [],
                "unique_count": 1,
                "total_count": 1,
            },
        },
    }

    # Without preferred source: should still pick UNIT_COST for "unit cost" hint
    src, col, conf, role, _steps = planner.resolve_metric("unit cost", None, "avg")
    assert col == "UNIT_COST"
    assert role == UNIT_MEASURE
    assert conf > 0.5

    # Clear cache so second call is fresh
    planner._metric_resolution_cache.clear()

    # With preferred source POS: UNIT_COST from POS
    src2, col2, conf2, role2, _steps2 = planner.resolve_metric("unit cost", "POS", "avg")
    assert (src2, col2) == ("POS", "UNIT_COST")


def test_resolve_metric_gap_note_includes_second_candidate_name(tmp_path):
    """gap note must name both the winner and the runner-up for explainability."""
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "POS": {
            "UNIT_COST": ColumnNode(
                name="UNIT_COST",
                role=UNIT_MEASURE,
                is_numeric=True,
                magnitude_class="medium",
                fill_rate=1.0,
            ),
            "EXT_COST": ColumnNode(
                name="EXT_COST",
                role=DERIVED_MEASURE,
                is_numeric=True,
                magnitude_class="large",
                fill_rate=1.0,
            ),
        }
    }
    planner.profiles = {
        "POS": {
            "UNIT_COST": {
                "is_numeric": True,
                "numeric": [10.0],
                "fill_rate": 1.0,
                "mean": 10.0,
                "std": 1.0,
                "sample_values": [10.0],
                "strings": [],
                "unique_count": 1,
                "total_count": 1,
            },
            "EXT_COST": {
                "is_numeric": True,
                "numeric": [100.0],
                "fill_rate": 1.0,
                "mean": 100.0,
                "std": 5.0,
                "sample_values": [100.0],
                "strings": [],
                "unique_count": 1,
                "total_count": 1,
            },
        }
    }

    _src, col, _conf, _role, steps = planner.resolve_metric("unit cost", "POS", "avg")

    assert col == "UNIT_COST"
    gap_steps = [s for s in steps if "gap" in s]
    assert gap_steps, "Expected at least one gap step for disambiguation"
    # The gap step should mention both candidates
    assert "UNIT_COST" in gap_steps[0]
    assert "EXT_COST" in gap_steps[0]


def test_resolve_metric_query_hints_sales_prefers_measure_over_sales_person_id(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner._query_hints_by_src = {
        "POS": [
            {
                "metric_role": "derived_measure",
                "columns": [{"name": "EXT_PRICE", "fill_rate": 1.0, "formula": "qty * unit_price"}],
            },
            {
                "metric_role": "base_measure",
                "columns": [{"name": "CUST_SALES_PERSON_NO", "fill_rate": 1.0}],
            },
        ],
    }

    src, col, conf, role, _steps = planner.resolve_metric("sales", "POS", "sum")

    assert (src, col, role) == ("POS", "EXT_PRICE", "derived_measure")
    assert conf >= 0.45


def test_resolve_metric_query_hints_sales_prefers_ext_price_over_ext_cost(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner._query_hints_by_src = {
        "POS": [
            {
                "metric_role": "derived_measure",
                "columns": [{"name": "EXT_PRICE", "fill_rate": 1.0, "formula": "qty * unit_price"}],
            },
            {
                "metric_role": "unit_measure",
                "columns": [{"name": "EXT_COST", "fill_rate": 1.0}],
            },
        ],
    }

    src, col, conf, role, _steps = planner.resolve_metric("sales", "POS", "sum")

    assert (src, col, role) == ("POS", "EXT_PRICE", "derived_measure")
    assert conf >= 0.85


def test_resolve_metric_query_hints_revenue_keeps_ext_price_above_accept_threshold(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner._query_hints_by_src = {
        "Quotes": [
            {
                "metric_role": "derived_measure",
                "columns": [{"name": "EXT_PRICE", "fill_rate": 1.0, "formula": "qty * unit_price"}],
            },
            {
                "metric_role": "unit_measure",
                "columns": [{"name": "EXT_COST", "fill_rate": 1.0}],
            },
        ],
    }

    src, col, conf, role, _steps = planner.resolve_metric("revenue", "Quotes", "sum")

    assert (src, col, role) == ("Quotes", "EXT_PRICE", "derived_measure")
    assert conf >= 0.85


def test_resolve_metric_broadens_after_preferred_source_miss(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "Quotes": {
            "EXT_PRICE": ColumnNode(
                name="EXT_PRICE",
                role=DERIVED_MEASURE,
                is_numeric=True,
                fill_rate=1.0,
            ),
        },
        "Bookings": {
            "AAR_MARGIN_%": ColumnNode(
                name="AAR_MARGIN_%",
                role=query_router.RATIO,
                is_numeric=True,
                fill_rate=1.0,
            ),
        },
    }
    planner.profiles = {
        "Quotes": {
            "EXT_PRICE": {
                "is_numeric": True,
                "numeric": [10.0, 12.0],
                "fill_rate": 1.0,
                "mean": 11.0,
                "std": 1.0,
                "sample_values": [10.0, 12.0],
                "strings": [],
                "unique_count": 2,
                "total_count": 2,
            },
        },
        "Bookings": {
            "AAR_MARGIN_%": {
                "is_numeric": True,
                "numeric": [0.25, 0.30],
                "fill_rate": 1.0,
                "mean": 0.275,
                "std": 0.035,
                "sample_values": [0.25, 0.30],
                "strings": [],
                "unique_count": 2,
                "total_count": 2,
            },
        },
    }

    src, col, conf, role, steps = planner.resolve_metric(
        "aar margin percent",
        "Quotes",
        "avg",
    )

    assert (src, col) == ("Bookings", "AAR_MARGIN_%")
    assert role == query_router.RATIO
    assert conf > 0.5
    assert any("preferred_source_miss" in step for step in steps)


