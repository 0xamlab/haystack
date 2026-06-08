"""Tests for test_auto_planner: misc_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-5/tests/test_auto_planner.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_helpers import *  # noqa: F401,F403


def test_plan_skips_llm_for_confident_same_source_resolution(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="auto")
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "MEASURE_TOTAL",
        1.15,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S0",
        "GROUP_DIM",
        1.20,
        ["dimension"],
    )

    def _unexpected_llm(**_kwargs):
        raise AssertionError("LLM should not be called for confident same-source plans")

    planner._llm_confirm_plan = _unexpected_llm

    plan = planner.plan("total value", "group", "sum", "S0")

    assert plan.metric_src == "S0"
    assert plan.group_src == "S0"
    assert all("[llm]" not in step for step in plan.steps)
    assert any(step.startswith("[llm/skipped]") for step in plan.steps)


def test_plan_uses_llm_when_dimension_resolution_is_ambiguous(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="auto")
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "RATE_VALUE",
        1.10,
        "unit_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S0",
        "DIM_CANDIDATE_A",
        0.62,
        ["dimension"],
    )

    calls = {"count": 0}

    def _llm(**_kwargs):
        calls["count"] += 1
        return {
            "metric_src": "S0",
            "metric_col": "RATE_VALUE",
            "group_src": "S0",
            "group_col": "DIM_CANDIDATE_B",
            "reasoning": "corrected ambiguous manufacturer dimension",
        }

    planner._llm_confirm_plan = _llm

    plan = planner.plan("rate", "dimension", "avg", "S0")

    assert calls["count"] == 1
    assert plan.group_col == "DIM_CANDIDATE_B"
    assert any(step.startswith("[llm]") for step in plan.steps)


def test_plan_cache_prevents_repeat_llm_calls_for_same_request(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="auto")
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "MEASURE_TOTAL",
        1.05,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S1",
        "DIM_EXTERNAL",
        1.00,
        ["dimension"],
    )
    planner.find_join_keys = lambda src_a, src_b: [
        {
            "field_a": "KEY_LEFT",
            "source_a": "S0",
            "field_b": "KEY_RIGHT",
            "source_b": "S1",
            "confidence": 0.439,
            "cardinality": "many_to_many",
        }
    ]

    calls = {"count": 0}

    def _llm(**_kwargs):
        calls["count"] += 1
        return {
            "metric_src": "S0",
            "metric_col": "MEASURE_TOTAL",
            "group_src": "S0",
            "group_col": "DIM_LOCAL",
            "reasoning": "preferred-source dimension retained",
        }

    planner._llm_confirm_plan = _llm

    first = planner.plan("total", "group", "sum", "S0")
    second = planner.plan("total", "group", "sum", "S0")

    assert calls["count"] == 1
    assert first.group_col == second.group_col == "DIM_LOCAL"
    assert first is not second


def test_plan_never_policy_disables_llm_even_for_ambiguous_cases(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "RATE_VALUE",
        1.10,
        "unit_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S0",
        "DIM_CANDIDATE_A",
        0.62,
        ["dimension"],
    )

    def _unexpected_llm(**_kwargs):
        raise AssertionError("LLM policy 'never' must suppress all LLM calls")

    planner._llm_confirm_plan = _unexpected_llm

    plan = planner.plan("rate", "dimension", "avg", "S0")

    assert plan.group_col == "DIM_CANDIDATE_A"
    assert any(step == "[llm/skipped] policy=never" for step in plan.steps)


def test_plan_prefers_same_source_metric_when_weak_join_only_adds_dimension(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "BookingsNew": {
            "EXT_COST": _planner_node("derived_measure"),
        },
        "Inventory": {
            "EXT_COST": _planner_node("component"),
            "Warehouse": _planner_node("category", is_numeric=False),
        },
    }
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "BookingsNew",
        "EXT_COST",
        1.015,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "Inventory",
        "Warehouse",
        1.85,
        ["dimension"],
    )
    weak_hop = SimpleNamespace(
        left_source="BookingsNew",
        right_source="Inventory",
        left_key="PART_NUMBER",
        right_key="PART_NUMBER",
        confidence=0.624,
        cardinality="many_to_many",
    )
    planner._search_join_path = lambda *_args, **_kwargs: (
        [weak_hop],
        0.298,
        [],
        None,
    )

    plan = planner.plan("extended cost", "warehouse", "sum", "Inventory")

    assert plan.metric_src == "Inventory"
    assert plan.metric_col == "EXT_COST"
    assert plan.group_src == "Inventory"
    assert plan.group_col == "Warehouse"
    assert plan.join_hops == []
    assert plan.path_confidence == 1.0
    assert any("metric/self_correct_same_source" in step for step in plan.steps)
    assert any(step == "[llm/skipped] policy=never" for step in plan.steps)


def test_join_candidates_for_source_are_cached_per_source(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.profiles = {
        "S0": {
            "DIMENSION_KEY": {
                "is_numeric": False,
                "strings": ["A", "B", "C"],
                "sample_values": ["A", "B", "C"],
                "unique_count": 3,
                "total_count": 3,
                "fill_rate": 1.0,
            },
            "MEASURE_TOTAL": {
                "is_numeric": True,
                "strings": [],
                "sample_values": [1, 2, 3],
                "unique_count": 2,
                "total_count": 3,
                "fill_rate": 1.0,
            },
        }
    }

    first = planner._join_candidates_for_source("S0")
    second = planner._join_candidates_for_source("S0")

    assert first is second
    assert list(first.keys()) == ["S0.DIMENSION_KEY"]


def test_metric_and_dimension_resolution_are_cached(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {"S0": {}, "S1": {}}
    planner._query_hints_by_src = {
        "S0": [
            {
                "metric_role": "derived_measure",
                "columns": [{"name": "MEASURE_TOTAL", "fill_rate": 1.0}],
            }
        ]
    }
    planner.resolve_dimension = AutoPlanner.resolve_dimension.__get__(planner, AutoPlanner)
    planner.profiles = {
        "S0": {
            "DIMENSION_KEY": {
                "strings": ["A", "B"],
                "sample_values": ["A", "B"],
                "total_count": 2,
                "unique_count": 2,
                "fill_rate": 1.0,
            }
        }
    }

    metric_first = planner.resolve_metric("measure", "S0", "sum")
    metric_second = planner.resolve_metric("measure", "S0", "sum")

    assert metric_first == metric_second


def test_rebuild_adaptive_context_uses_current_source_profiles(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.profiles = {
        "Alpha": {
            "ORDER_ID": {
                "fill_rate": 1.0,
                "unique_count": 100,
                "total_count": 100,
                "strings": [f"O{i}" for i in range(5)],
            },
            "STATUS": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 100,
                "strings": ["open", "closed", "hold"],
            },
        },
        "Beta": {
            "PART_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 40,
                "total_count": 200,
                "strings": [f"P{i}" for i in range(5)],
            },
            "MESSAGE_CODE": {
                "fill_rate": 1.0,
                "unique_count": 4,
                "total_count": 200,
                "strings": ["a", "b", "c", "d"],
            },
        },
    }

    planner._rebuild_adaptive_context()

    assert set(planner._adaptive_source_context) == {"Alpha", "Beta"}
    assert planner._adaptive_source_context["Alpha"].join_distinctiveness
    assert planner._adaptive_source_context["Beta"].join_distinctiveness
    assert planner._adaptive_source_context["Alpha"] != planner._adaptive_source_context["Beta"]


def test_resolve_fields_batch_rebuilds_deferred_vector_resolver(
    tmp_path,
    monkeypatch,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner._vector_resolver = None
    planner._vector_resolver_dirty = True

    calls = {"count": 0}

    class _Resolver:
        def resolve_plan_fields(self, **kwargs):  # type: ignore[no-untyped-def]
            return {"metric": kwargs.get("metric"), "group_by": None, "date": None, "filter": None}

    def _fake_rebuild() -> None:
        calls["count"] += 1
        planner._vector_resolver = _Resolver()
        planner._vector_resolver_dirty = False

    monkeypatch.setattr(planner, "_build_vector_resolver", _fake_rebuild)

    results = planner.resolve_fields_batch(metric=("extended cost", "BACKLOG", "derived_measure"))

    assert calls["count"] == 1
    assert planner._vector_resolver_dirty is False
    assert results["metric"] == ("extended cost", "BACKLOG", "derived_measure")


def test_profile_records_scans_full_loaded_rows_for_sparse_late_columns():
    records = [
        {"sparse_dim": "", "measure_x": 1.0},
        {"sparse_dim": "", "measure_x": 2.0},
        {"sparse_dim": "alpha", "measure_x": 3.0},
        {"sparse_dim": "beta", "measure_x": 4.0},
    ]

    profile = _profile_records(records)

    assert profile["sparse_dim"]["fill_rate"] == 0.5
    assert profile["sparse_dim"]["unique_count"] == 2
    assert profile["sparse_dim"]["strings"] == ["alpha", "beta"]


def test_plan_defaults_to_four_hop_budget_without_opt_in(tmp_path):
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

    plan = planner.plan("total value", "region", "sum", "S0")

    assert plan.error is not None
    assert len(plan.join_hops) == 0
    assert "No join path" in plan.error


def test_plan_returns_explicit_error_when_cross_source_dimension_has_no_join_path(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {"S0": {}, "S2": {}}
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "MEASURE_TOTAL",
        1.05,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S2",
        "REGION_LABEL",
        0.98,
        ["dimension"],
    )
    planner.find_join_keys = lambda src_a, src_b: []

    plan = planner.plan("total value", "region", "sum", "S0")

    assert plan.error == "No join path from 'S0' to 'S2' for dimension 'REGION_LABEL'"
    assert any("No join path from 'S0' to 'S2'" in note for note in plan.validation_notes)


def test_plan_returns_explicit_error_when_dimension_hint_cannot_be_resolved(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {"S0": {}}
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "MEASURE_TOTAL",
        1.03,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: ("", None, 0.0, ["dimension"])

    plan = planner.plan("total value", "unsupported dimension", "sum", "S0")

    assert plan.error == "No supported dimension found for hint 'unsupported dimension'"
    assert "No supported dimension found for hint 'unsupported dimension'" in plan.validation_notes


def test_plan_self_corrects_same_named_dimension_back_to_metric_source(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "S0": {
            "SHIP_TO_STATE": ColumnNode(name="SHIP_TO_STATE", role="category", fill_rate=0.43),
        },
        "S1": {
            "SHIP_TO_STATE": ColumnNode(name="SHIP_TO_STATE", role="category", fill_rate=0.96),
        },
    }
    planner.profiles = {
        "S0": {
            "SHIP_TO_STATE": {
                "fill_rate": 0.43,
                "unique_count": 42,
                "total_count": 1000,
                "strings": ["CA", "NY"],
            },
        },
        "S1": {
            "SHIP_TO_STATE": {
                "fill_rate": 0.96,
                "unique_count": 50,
                "total_count": 1000,
                "strings": ["CA", "TX"],
            },
        },
    }
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "EXT_PRICE",
        1.0,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S1",
        "SHIP_TO_STATE",
        1.33,
        ["dimension"],
    )

    plan = planner.plan("revenue", "ship to state", "sum", "S0")

    assert (plan.group_src, plan.group_col) == ("S0", "SHIP_TO_STATE")
    assert any("self_correct_same_source" in step for step in plan.steps)


def test_plan_prefers_group_stable_join_for_cross_source_dimension(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "S0": {
            "EXT_PRICE": ColumnNode(
                name="EXT_PRICE", role="derived_measure", is_numeric=True, fill_rate=1.0
            ),
        },
        "S1": {
            "INVENTORY_TYPE": ColumnNode(
                name="INVENTORY_TYPE", role="metric", is_numeric=True, fill_rate=0.5
            ),
        },
    }
    planner.tables = {
        "S0": [
            {"ORDER_NUMBER": "O1", "PART_NUMBER": "P1", "EXT_PRICE": 100.0},
            {"ORDER_NUMBER": "O2", "PART_NUMBER": "P2", "EXT_PRICE": 80.0},
            {"ORDER_NUMBER": "O3", "PART_NUMBER": "P3", "EXT_PRICE": 50.0},
        ],
        "S1": [
            {"ORDER_NUMBER": "O1", "PART_NUMBER": "P1", "INVENTORY_TYPE": 1},
            {"ORDER_NUMBER": "O1", "PART_NUMBER": "P1", "INVENTORY_TYPE": 1},
            {"ORDER_NUMBER": "O2", "PART_NUMBER": "P2", "INVENTORY_TYPE": 2},
            {"ORDER_NUMBER": "O2", "PART_NUMBER": "P2", "INVENTORY_TYPE": 2},
            {"ORDER_NUMBER": "OX", "PART_NUMBER": "P1", "INVENTORY_TYPE": 3},
        ],
    }
    planner.profiles = {
        "S0": {
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["O1", "O2", "O3"],
            },
            "PART_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["P1", "P2", "P3"],
            },
            "EXT_PRICE": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "is_numeric": True,
                "sample_values": [100.0, 80.0, 50.0],
                "strings": [],
            },
        },
        "S1": {
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 5,
                "strings": ["O1", "O2", "OX"],
            },
            "PART_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 2,
                "total_count": 5,
                "strings": ["P1", "P2"],
            },
            "INVENTORY_TYPE": {
                "fill_rate": 0.5,
                "unique_count": 3,
                "total_count": 5,
                "strings": [],
                "sample_values": [1, 2, 3],
            },
        },
    }
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0",
        "EXT_PRICE",
        1.0,
        "derived_measure",
        ["metric"],
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S1",
        "INVENTORY_TYPE",
        0.9,
        ["dimension"],
    )
    planner.find_join_keys = lambda src_a, src_b: [
        {
            "field_a": "PART_NUMBER",
            "source_a": src_a,
            "field_b": "PART_NUMBER",
            "source_b": src_b,
            "confidence": 0.83,
            "cardinality": "many_to_many",
        },
        {
            "field_a": "ORDER_NUMBER",
            "source_a": src_a,
            "field_b": "ORDER_NUMBER",
            "source_b": src_b,
            "confidence": 0.74,
            "cardinality": "many_to_many",
        },
    ]

    plan = planner.plan("sales", "inventory type", "sum", "S0")

    assert plan.error is None
    assert len(plan.join_hops) == 1
    assert (plan.join_hops[0].left_key, plan.join_hops[0].right_key) == (
        "ORDER_NUMBER",
        "ORDER_NUMBER",
    )


def test_search_join_path_short_circuits_safe_direct_path(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "S0": {
            "EXT_PRICE": ColumnNode(
                name="EXT_PRICE", role="derived_measure", is_numeric=True, fill_rate=1.0
            )
        },
        "S1": {
            "INVENTORY_TYPE": ColumnNode(
                name="INVENTORY_TYPE", role="category", is_numeric=False, fill_rate=1.0
            )
        },
        "S2": {
            "PRODUCT_LINE": ColumnNode(
                name="PRODUCT_LINE", role="category", is_numeric=False, fill_rate=1.0
            )
        },
    }
    planner.profiles = {
        "S0": {
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 700,
                "total_count": 1000,
                "strings": ["O1", "O2"],
            },
        },
        "S1": {
            "ORDER_NUMBER": {
                "fill_rate": 1.0,
                "unique_count": 900,
                "total_count": 1200,
                "strings": ["O1", "O2"],
            },
            "INVENTORY_TYPE": {
                "fill_rate": 1.0,
                "unique_count": 12,
                "total_count": 1200,
                "strings": [],
                "sample_values": [1, 2, 3],
            },
        },
        "S2": {
            "PRODUCT_LINE": {
                "fill_rate": 1.0,
                "unique_count": 20,
                "total_count": 1200,
                "strings": ["A", "B"],
            },
        },
    }

    calls: list[tuple[str, str]] = []

    def _fake_direct_join_candidates(
        left_source: str, right_source: str
    ) -> list[dict[str, object]]:
        calls.append((left_source, right_source))
        if (left_source, right_source) == ("S0", "S1"):
            return [
                {
                    "field_a": "ORDER_NUMBER",
                    "source_a": "S0",
                    "field_b": "ORDER_NUMBER",
                    "source_b": "S1",
                    "confidence": 0.78,
                    "cardinality": "many_to_many",
                    "overlap": 0.42,
                    "evidence_source": "registry",
                }
            ]
        raise AssertionError("safe direct path should prevent deeper candidate exploration")

    planner._direct_join_candidates = _fake_direct_join_candidates  # type: ignore[method-assign]

    hops, conf, notes, err = planner._search_join_path("S0", "S1", "INVENTORY_TYPE")

    assert err is None
    assert len(hops) == 1
    assert (hops[0].left_key, hops[0].right_key) == ("ORDER_NUMBER", "ORDER_NUMBER")
    assert conf >= 0.22
    assert notes == []
    assert calls == [("S0", "S1")]


