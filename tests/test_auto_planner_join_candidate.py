"""Tests for test_auto_planner: join_candidate.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-5/tests/test_auto_planner.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_helpers import *  # noqa: F401,F403


def test_join_candidate_effective_conf_prefers_clean_sampled_join(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.tables = {
        "S0": [
            {"ORDER_NUMBER": "O1", "PRODUCT_LINE": "A"},
            {"ORDER_NUMBER": "O2", "PRODUCT_LINE": "B"},
            {"ORDER_NUMBER": "O3", "PRODUCT_LINE": "C"},
        ],
        "S1": [
            {"ORDER_NUMBER": "O1", "PRODUCT_LINE": "A"},
            {"ORDER_NUMBER": "O2", "PRODUCT_LINE": "B"},
            {"ORDER_NUMBER": "O3", "PRODUCT_LINE": "C"},
            {"ORDER_NUMBER": "OX", "PRODUCT_LINE": "A"},
            {"ORDER_NUMBER": "OY", "PRODUCT_LINE": "B"},
        ],
    }

    clean = planner._join_candidate_effective_conf(
        {
            "source_a": "S0",
            "field_a": "ORDER_NUMBER",
            "source_b": "S1",
            "field_b": "ORDER_NUMBER",
            "confidence": 0.75,
            "cardinality": "many_to_many",
        }
    )
    noisy = planner._join_candidate_effective_conf(
        {
            "source_a": "S0",
            "field_a": "PRODUCT_LINE",
            "source_b": "S1",
            "field_b": "PRODUCT_LINE",
            "confidence": 0.80,
            "cardinality": "many_to_many",
        }
    )

    assert clean > noisy


def test_join_candidate_effective_conf_uses_group_stability_to_tolerate_duplicate_keys(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.tables = {
        "S0": [
            {"ORDER_NUMBER": "O1", "PRODUCT_LINE": "A"},
            {"ORDER_NUMBER": "O2", "PRODUCT_LINE": "B"},
            {"ORDER_NUMBER": "O3", "PRODUCT_LINE": "C"},
        ],
        "S1": [
            {"ORDER_NUMBER": "O1", "INVENTORY_TYPE": 1, "PRODUCT_LINE": "A"},
            {"ORDER_NUMBER": "O1", "INVENTORY_TYPE": 1, "PRODUCT_LINE": "A"},
            {"ORDER_NUMBER": "O2", "INVENTORY_TYPE": 2, "PRODUCT_LINE": "B"},
            {"ORDER_NUMBER": "O2", "INVENTORY_TYPE": 2, "PRODUCT_LINE": "B"},
            {"ORDER_NUMBER": "O3", "INVENTORY_TYPE": 3, "PRODUCT_LINE": "A"},
        ],
    }

    stable = planner._join_candidate_effective_conf(
        {
            "source_a": "S0",
            "field_a": "ORDER_NUMBER",
            "source_b": "S1",
            "field_b": "ORDER_NUMBER",
            "confidence": 0.74,
            "cardinality": "many_to_many",
        },
        group_col="INVENTORY_TYPE",
    )
    conflicted = planner._join_candidate_effective_conf(
        {
            "source_a": "S0",
            "field_a": "PRODUCT_LINE",
            "source_b": "S1",
            "field_b": "PRODUCT_LINE",
            "confidence": 0.82,
            "cardinality": "many_to_many",
        },
        group_col="INVENTORY_TYPE",
    )

    assert stable > conflicted


def test_join_candidate_effective_conf_penalizes_low_distinct_join_keys(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.tables = {
        "S0": [{"ORDER_NUMBER": "O1"}, {"ORDER_NUMBER": "O2"}, {"ORDER_NUMBER": "O3"}],
        "S1": [{"ORDER_NUMBER": "O1"}, {"ORDER_NUMBER": "O2"}, {"ORDER_NUMBER": "O3"}],
    }
    planner.profiles = {
        "S0": {
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["O1", "O2", "O3"],
            },
            "MESSAGE_CODE": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 300,
                "strings": ["A", "B", "C"],
            },
        },
        "S1": {
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["O1", "O2", "O3"],
            },
            "MESSAGE_CODE": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 500,
                "strings": ["A", "B", "C"],
            },
        },
    }

    strong = planner._join_candidate_effective_conf(
        {
            "source_a": "S0",
            "field_a": "ORDER_NUMBER",
            "source_b": "S1",
            "field_b": "ORDER_NUMBER",
            "confidence": 0.70,
            "cardinality": "many_to_many",
        }
    )
    weak = planner._join_candidate_effective_conf(
        {
            "source_a": "S0",
            "field_a": "MESSAGE_CODE",
            "source_b": "S1",
            "field_b": "MESSAGE_CODE",
            "confidence": 0.78,
            "cardinality": "many_to_many",
        }
    )

    assert strong > weak


def test_join_candidate_effective_conf_registry_candidate_skips_record_sampling(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.profiles = {
        "Bookings": {
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 500,
                "total_count": 500,
                "strings": ["O1", "O2", "O3"],
            }
        },
        "POS": {
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 700,
                "total_count": 900,
                "strings": ["O1", "O2", "O3"],
            },
            "INVENTORY_TYPE": {
                "fill_rate": 0.82,
                "unique_count": 12,
                "total_count": 900,
                "strings": [],
                "sample_values": [1, 2, 3],
            },
        },
    }

    planner._ensure_records = lambda name: (_ for _ in ()).throw(  # type: ignore[method-assign]
        AssertionError("registry-backed join scoring must stay metadata-only on the hot path")
    )

    confidence = planner._join_candidate_effective_conf(
        {
            "source_a": "Bookings",
            "field_a": "ORDER_NUMBER",
            "source_b": "POS",
            "field_b": "ORDER_NUMBER",
            "confidence": 0.88,
            "cardinality": "many_to_one",
            "overlap": 0.76,
            "evidence_source": "registry",
        },
        group_col="INVENTORY_TYPE",
    )

    assert confidence > 0.5


def test_join_candidate_effective_conf_registry_inventory_dimension_prefers_part_number_key(
    tmp_path,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.profiles = {
        "Backlog": {
            "PART_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 420,
                "total_count": 1535,
                "strings": ["P1", "P2", "P3"],
            },
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 690,
                "total_count": 1535,
                "strings": ["O1", "O2", "O3"],
            },
        },
        "POSNew": {
            "PART_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 380,
                "total_count": 16730,
                "strings": ["P1", "P2", "P3"],
            },
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 710,
                "total_count": 16730,
                "strings": ["O1", "O2", "O3"],
            },
            "INVENTORY_TYPE": {
                "fill_rate": 1.0,
                "unique_count": 14,
                "total_count": 16730,
                "strings": [],
                "sample_values": [1, 2, 3],
            },
        },
    }

    part_conf = planner._join_candidate_effective_conf(
        {
            "source_a": "Backlog",
            "field_a": "PART_NUMBER",
            "source_b": "POSNew",
            "field_b": "PART_NUMBER",
            "confidence": 0.638,
            "cardinality": "many_to_many",
            "overlap": 0.209,
            "evidence_source": "registry",
        },
        group_col="INVENTORY_TYPE",
    )
    order_conf = planner._join_candidate_effective_conf(
        {
            "source_a": "Backlog",
            "field_a": "ORDER_NUMBER",
            "source_b": "POSNew",
            "field_b": "ORDER_NUMBER",
            "confidence": 0.616,
            "cardinality": "many_to_many",
            "overlap": 0.091,
            "evidence_source": "registry",
        },
        group_col="INVENTORY_TYPE",
    )

    assert part_conf > order_conf


def test_join_candidate_effective_conf_registry_bookings_inventory_dimension_keeps_order_key(
    tmp_path,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.profiles = {
        "BookingsNew": {
            "PART_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 540,
                "total_count": 17719,
                "strings": ["P1", "P2", "P3"],
            },
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 710,
                "total_count": 17719,
                "strings": ["O1", "O2", "O3"],
            },
        },
        "POSNew": {
            "PART_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 380,
                "total_count": 16730,
                "strings": ["P1", "P2", "P3"],
            },
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 690,
                "total_count": 16730,
                "strings": ["O1", "O2", "O3"],
            },
            "INVENTORY_TYPE": {
                "fill_rate": 1.0,
                "unique_count": 14,
                "total_count": 16730,
                "strings": [],
                "sample_values": [1, 2, 3],
            },
        },
    }

    part_conf = planner._join_candidate_effective_conf(
        {
            "source_a": "BookingsNew",
            "field_a": "PART_NUMBER",
            "source_b": "POSNew",
            "field_b": "PART_NUMBER",
            "confidence": 0.738,
            "cardinality": "many_to_many",
            "overlap": 0.25,
            "evidence_source": "registry",
        },
        group_col="INVENTORY_TYPE",
    )
    order_conf = planner._join_candidate_effective_conf(
        {
            "source_a": "BookingsNew",
            "field_a": "ORDER_NUMBER",
            "source_b": "POSNew",
            "field_b": "ORDER_NUMBER",
            "confidence": 0.727,
            "cardinality": "many_to_many",
            "overlap": 0.10,
            "evidence_source": "registry",
        },
        group_col="INVENTORY_TYPE",
    )

    assert order_conf > part_conf


def test_join_candidate_effective_conf_penalizes_measure_on_measure_join_keys(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "Bookings": {
            "EXT_PRICE": ColumnNode(
                name="EXT_PRICE",
                role=DERIVED_MEASURE,
                is_numeric=True,
                fill_rate=1.0,
            ),
            "ORDER_NUMBER": ColumnNode(
                name="ORDER_NUMBER",
                role=query_router.IDENTIFIER,
                is_numeric=False,
                fill_rate=1.0,
            ),
        },
        "Quotes": {
            "EXT_PRICE": ColumnNode(
                name="EXT_PRICE",
                role=DERIVED_MEASURE,
                is_numeric=True,
                fill_rate=1.0,
            ),
            "ORDER_NUMBER": ColumnNode(
                name="ORDER_NUMBER",
                role=query_router.IDENTIFIER,
                is_numeric=False,
                fill_rate=1.0,
            ),
            "CUST_TYPE": ColumnNode(
                name="CUST_TYPE",
                role=query_router.CATEGORY,
                is_numeric=False,
                fill_rate=1.0,
            ),
        },
    }
    planner.profiles = {
        "Bookings": {
            "EXT_PRICE": {
                "unique_count": 2500,
                "total_count": 3000,
                "fill_rate": 1.0,
                "is_numeric": True,
            },
            "ORDER_NUMBER": {
                "unique_count": 1800,
                "total_count": 3000,
                "fill_rate": 1.0,
                "strings": ["A1", "A2", "A3"],
            },
        },
        "Quotes": {
            "EXT_PRICE": {
                "unique_count": 2200,
                "total_count": 2600,
                "fill_rate": 0.88,
                "is_numeric": True,
            },
            "ORDER_NUMBER": {
                "unique_count": 450,
                "total_count": 500,
                "fill_rate": 0.9,
                "strings": ["A1", "A2", "A3"],
            },
            "CUST_TYPE": {
                "unique_count": 10,
                "total_count": 500,
                "fill_rate": 0.9,
                "strings": ["OEM", "DIST"],
            },
        },
    }

    measure_join = {
        "field_a": "EXT_PRICE",
        "source_a": "Bookings",
        "field_b": "EXT_PRICE",
        "source_b": "Quotes",
        "confidence": 0.49,
        "cardinality": "one_to_one",
        "overlap": 0.0,
        "evidence_source": "registry",
    }
    identifier_join = {
        "field_a": "ORDER_NUMBER",
        "source_a": "Bookings",
        "field_b": "ORDER_NUMBER",
        "source_b": "Quotes",
        "confidence": 0.47,
        "cardinality": "many_to_one",
        "overlap": 0.0,
        "evidence_source": "registry",
    }

    measure_effective = planner._join_candidate_effective_conf(
        measure_join,
        group_col="CUST_TYPE",
    )
    identifier_effective = planner._join_candidate_effective_conf(
        identifier_join,
        group_col="CUST_TYPE",
    )

    assert identifier_effective > measure_effective


def test_join_candidate_effective_conf_rejects_zero_coverage_join_candidate(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "Bookings": {
            "ORDER_NUMBER": ColumnNode(
                name="ORDER_NUMBER",
                role=query_router.IDENTIFIER,
                is_numeric=False,
                fill_rate=1.0,
            ),
        },
        "Quotes": {
            "ORDER_NUMBER": ColumnNode(
                name="ORDER_NUMBER",
                role=query_router.IDENTIFIER,
                is_numeric=False,
                fill_rate=1.0,
            ),
            "CUST_TYPE": ColumnNode(
                name="CUST_TYPE",
                role=query_router.CATEGORY,
                is_numeric=False,
                fill_rate=1.0,
            ),
        },
    }
    planner.tables = {
        "Bookings": [{"ORDER_NUMBER": "B-1"}, {"ORDER_NUMBER": "B-2"}],
        "Quotes": [
            {"ORDER_NUMBER": "Q-1", "CUST_TYPE": "OEM"},
            {"ORDER_NUMBER": "Q-2", "CUST_TYPE": "DIST"},
        ],
    }
    planner.profiles = {
        "Bookings": {
            "ORDER_NUMBER": {
                "unique_count": 2,
                "total_count": 2,
                "fill_rate": 1.0,
                "strings": ["B-1", "B-2"],
            },
        },
        "Quotes": {
            "ORDER_NUMBER": {
                "unique_count": 2,
                "total_count": 2,
                "fill_rate": 1.0,
                "strings": ["Q-1", "Q-2"],
            },
            "CUST_TYPE": {
                "unique_count": 2,
                "total_count": 2,
                "fill_rate": 1.0,
                "strings": ["OEM", "DIST"],
            },
        },
    }

    effective = planner._join_candidate_effective_conf(
        {
            "field_a": "ORDER_NUMBER",
            "source_a": "Bookings",
            "field_b": "ORDER_NUMBER",
            "source_b": "Quotes",
            "confidence": 0.48,
            "cardinality": "many_to_one",
        },
        group_col="CUST_TYPE",
    )

    assert effective == 0.0


