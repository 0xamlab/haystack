from pathlib import Path
from types import SimpleNamespace

from apps.api_server.routers import query as query_router
from apps.api_server.routers.query import DERIVED_MEASURE, UNIT_MEASURE, ColumnNode
from apps.api_server.services import auto_planner as auto_planner_module
from apps.api_server.services import source_registry as reg
from apps.api_server.services.auto_planner import AutoPlanner, JoinHop, QueryPlan, _profile_records


def _planner_node(role: str, *, is_numeric: bool = True, fill_rate: float = 1.0):
    node = SimpleNamespace()
    node.role = role
    node.is_numeric = is_numeric
    node.fill_rate = fill_rate
    node.formula = None
    node.magnitude_class = None
    return node


def test_plan_skips_llm_for_confident_same_source_resolution(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="auto")
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0", "MEASURE_TOTAL", 1.15, "derived_measure", ["metric"]
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S0", "GROUP_DIM", 1.20, ["dimension"]
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
        "S0", "RATE_VALUE", 1.10, "unit_measure", ["metric"]
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S0", "DIM_CANDIDATE_A", 0.62, ["dimension"]
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
        "S0", "MEASURE_TOTAL", 1.05, "derived_measure", ["metric"]
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S1", "DIM_EXTERNAL", 1.00, ["dimension"]
    )
    planner.find_join_keys = lambda src_a, src_b: [{
        "field_a": "KEY_LEFT",
        "source_a": "S0",
        "field_b": "KEY_RIGHT",
        "source_b": "S1",
        "confidence": 0.439,
        "cardinality": "many_to_many",
    }]

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
        "S0", "RATE_VALUE", 1.10, "unit_measure", ["metric"]
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S0", "DIM_CANDIDATE_A", 0.62, ["dimension"]
    )

    def _unexpected_llm(**_kwargs):
        raise AssertionError("LLM policy 'never' must suppress all LLM calls")

    planner._llm_confirm_plan = _unexpected_llm

    plan = planner.plan("rate", "dimension", "avg", "S0")

    assert plan.group_col == "DIM_CANDIDATE_A"
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
        "S0": [{
            "metric_role": "derived_measure",
            "columns": [{"name": "MEASURE_TOTAL", "fill_rate": 1.0}],
        }]
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


def test_refresh_registry_source_reuses_incremental_vector_resolver_for_new_source(
    tmp_path,
    monkeypatch,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "POS": {
            "UNIT_PRICE": _planner_node("unit_measure"),
            "EXT_PRICE": _planner_node("derived_measure"),
        }
    }
    planner.profiles = {"POS": {}}
    planner._connections = []
    planner._build_vector_resolver()

    rebuild_calls = {"count": 0}

    def _count_rebuild():
        rebuild_calls["count"] += 1

    monkeypatch.setattr(planner, "_build_vector_resolver", _count_rebuild)
    monkeypatch.setattr(
        auto_planner_module,
        "_registry_source_artifacts_from_meta",
        lambda **_kwargs: auto_planner_module._CachedRegistrySourceArtifacts(
            nodes={
                "UNIT_COST": _planner_node("unit_measure"),
                "EXT_COST": _planner_node("derived_measure"),
            },
            profile={},
            query_hints=[],
        ),
    )

    planner.refresh_registry_source(
        org_id="org-1",
        source_id="src-backlog",
        source_name="BACKLOG",
        schema_meta={},
        source_schema_revision="schema-rev-backlog",
        parquet_path=None,
        new_connections=[],
    )

    assert rebuild_calls["count"] == 0
    result = planner._vector_resolver.resolve(
        "extended cost",
        preferred_source="BACKLOG",
        role_hint="derived_measure",
    )
    assert result is not None
    assert result.source == "BACKLOG"
    assert result.column == "EXT_COST"


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


def test_plan_builds_multi_hop_join_path_from_registry_connections(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {"S0": {}, "S1": {}, "S2": {}}
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0", "MEASURE_TOTAL", 1.12, "derived_measure", ["metric"]
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S2", "REGION_LABEL", 1.01, ["dimension"]
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
    assert [(hop.left_source, hop.right_source) for hop in plan.join_hops] == [("S0", "S1"), ("S1", "S2")]
    assert plan.intermediate_sources == ["S1"]
    assert plan.group_src == "S2"
    assert plan.path_confidence > 0.6
    assert plan.join_key_metric == "CUSTOMER_ID"
    assert plan.join_key_group == "GEO_KEY"
    assert any("multi-hop path" in note for note in plan.validation_notes)


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
            JoinHop("S0", "S1", "CUSTOMER_ID", "CUSTOMER_ID", confidence=0.97, cardinality="many_to_one"),
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


def test_plan_returns_explicit_error_when_cross_source_dimension_has_no_join_path(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {"S0": {}, "S2": {}}
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0", "MEASURE_TOTAL", 1.05, "derived_measure", ["metric"]
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S2", "REGION_LABEL", 0.98, ["dimension"]
    )
    planner.find_join_keys = lambda src_a, src_b: []

    plan = planner.plan("total value", "region", "sum", "S0")

    assert plan.error == "No join path from 'S0' to 'S2' for dimension 'REGION_LABEL'"
    assert any("No join path from 'S0' to 'S2'" in note for note in plan.validation_notes)


def test_plan_returns_explicit_error_when_dimension_hint_cannot_be_resolved(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {"S0": {}}
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0", "MEASURE_TOTAL", 1.03, "derived_measure", ["metric"]
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "", None, 0.0, ["dimension"]
    )

    plan = planner.plan("total value", "unsupported dimension", "sum", "S0")

    assert plan.error == "No supported dimension found for hint 'unsupported dimension'"
    assert "No supported dimension found for hint 'unsupported dimension'" in plan.validation_notes


def test_resolve_metric_prefers_unit_cost_over_extended_cost_for_unit_cost_hint(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "POS": {
            "UNIT_COST": ColumnNode(name="UNIT_COST", role=UNIT_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
            "EXT_COST": ColumnNode(name="EXT_COST", role=DERIVED_MEASURE, is_numeric=True, magnitude_class="large", fill_rate=1.0),
            "OH_COST": ColumnNode(name="OH_COST", role=DERIVED_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
        }
    }
    planner.profiles = {
        "POS": {
            "UNIT_COST": {"is_numeric": True, "numeric": [10.0, 12.0], "fill_rate": 1.0, "mean": 11.0, "std": 1.0, "sample_values": [10.0, 12.0], "strings": [], "unique_count": 2, "total_count": 2},
            "EXT_COST": {"is_numeric": True, "numeric": [100.0, 120.0], "fill_rate": 1.0, "mean": 110.0, "std": 10.0, "sample_values": [100.0, 120.0], "strings": [], "unique_count": 2, "total_count": 2},
            "OH_COST": {"is_numeric": True, "numeric": [80.0, 90.0], "fill_rate": 1.0, "mean": 85.0, "std": 5.0, "sample_values": [80.0, 90.0], "strings": [], "unique_count": 2, "total_count": 2},
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
            "UNIT_COST": ColumnNode(name="UNIT_COST", role=UNIT_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
            "EXT_COST": ColumnNode(name="EXT_COST", role=DERIVED_MEASURE, is_numeric=True, magnitude_class="large", fill_rate=1.0),
            "OH_COST": ColumnNode(name="OH_COST", role=DERIVED_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
        }
    }
    planner.profiles = {
        "POS": {
            "UNIT_COST": {"is_numeric": True, "numeric": [10.0, 12.0], "fill_rate": 1.0, "mean": 11.0, "std": 1.0, "sample_values": [10.0, 12.0], "strings": [], "unique_count": 2, "total_count": 2},
            "EXT_COST": {"is_numeric": True, "numeric": [100.0, 120.0], "fill_rate": 1.0, "mean": 110.0, "std": 10.0, "sample_values": [100.0, 120.0], "strings": [], "unique_count": 2, "total_count": 2},
            "OH_COST": {"is_numeric": True, "numeric": [80.0, 90.0], "fill_rate": 1.0, "mean": 85.0, "std": 5.0, "sample_values": [80.0, 90.0], "strings": [], "unique_count": 2, "total_count": 2},
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
            "UNIT_COST": ColumnNode(name="UNIT_COST", role=UNIT_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
            "OH_COST": ColumnNode(name="OH_COST", role=DERIVED_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
            "EXT_COST": ColumnNode(name="EXT_COST", role=DERIVED_MEASURE, is_numeric=True, magnitude_class="large", fill_rate=1.0),
        }
    }
    planner.profiles = {
        "WH": {
            "UNIT_COST": {"is_numeric": True, "numeric": [5.0], "fill_rate": 1.0, "mean": 5.0, "std": 1.0, "sample_values": [5.0], "strings": [], "unique_count": 1, "total_count": 1},
            "OH_COST":   {"is_numeric": True, "numeric": [20.0], "fill_rate": 1.0, "mean": 20.0, "std": 2.0, "sample_values": [20.0], "strings": [], "unique_count": 1, "total_count": 1},
            "EXT_COST":  {"is_numeric": True, "numeric": [80.0], "fill_rate": 1.0, "mean": 80.0, "std": 5.0, "sample_values": [80.0], "strings": [], "unique_count": 1, "total_count": 1},
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
        "S0": [{
            "metric_role": "derived_measure",
            "columns": [{"name": "measure_total", "fill_rate": 1.0, "formula": "quantity * unit_rate"}],
        }],
        "I0": [{
            "metric_role": "derived_measure",
            "columns": [{"name": "measure_total", "fill_rate": 1.0}],
        }],
    }

    src, col, conf, role, steps = planner.resolve_metric("total value", "I0", "sum")

    assert (src, col, role) == ("I0", "measure_total", "derived_measure")
    assert conf >= 0.45
    assert any("query_hints/registry" in step for step in steps)


def test_resolve_metric_query_hints_uses_canonical_tokens_for_overhead_cost(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner._query_hints_by_src = {
        "C0": [{
            "metric_role": "derived_measure",
            "columns": [
                {"name": "EXT_COST", "fill_rate": 1.0, "formula": "qty * unit_cost"},
                {"name": "OH_COST", "fill_rate": 1.0},
            ],
        }],
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
            "UNIT_COST": ColumnNode(name="UNIT_COST", role=UNIT_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
            "EXT_COST":  ColumnNode(name="EXT_COST",  role=DERIVED_MEASURE, is_numeric=True, magnitude_class="large",  fill_rate=1.0),
        },
        "Backlog": {
            "UNIT_COST": ColumnNode(name="UNIT_COST", role=UNIT_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
            "EXT_PRICE": ColumnNode(name="EXT_PRICE", role=DERIVED_MEASURE, is_numeric=True, magnitude_class="large",  fill_rate=1.0),
        },
    }
    planner.profiles = {
        "POS": {
            "UNIT_COST": {"is_numeric": True, "numeric": [10.0], "fill_rate": 1.0, "mean": 10.0, "std": 1.0, "sample_values": [10.0], "strings": [], "unique_count": 1, "total_count": 1},
            "EXT_COST":  {"is_numeric": True, "numeric": [100.0], "fill_rate": 1.0, "mean": 100.0, "std": 5.0, "sample_values": [100.0], "strings": [], "unique_count": 1, "total_count": 1},
        },
        "Backlog": {
            "UNIT_COST": {"is_numeric": True, "numeric": [12.0], "fill_rate": 1.0, "mean": 12.0, "std": 1.0, "sample_values": [12.0], "strings": [], "unique_count": 1, "total_count": 1},
            "EXT_PRICE": {"is_numeric": True, "numeric": [120.0], "fill_rate": 1.0, "mean": 120.0, "std": 6.0, "sample_values": [120.0], "strings": [], "unique_count": 1, "total_count": 1},
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
            "UNIT_COST": ColumnNode(name="UNIT_COST", role=UNIT_MEASURE, is_numeric=True, magnitude_class="medium", fill_rate=1.0),
            "EXT_COST":  ColumnNode(name="EXT_COST",  role=DERIVED_MEASURE, is_numeric=True, magnitude_class="large",  fill_rate=1.0),
        }
    }
    planner.profiles = {
        "POS": {
            "UNIT_COST": {"is_numeric": True, "numeric": [10.0], "fill_rate": 1.0, "mean": 10.0, "std": 1.0, "sample_values": [10.0], "strings": [], "unique_count": 1, "total_count": 1},
            "EXT_COST":  {"is_numeric": True, "numeric": [100.0], "fill_rate": 1.0, "mean": 100.0, "std": 5.0, "sample_values": [100.0], "strings": [], "unique_count": 1, "total_count": 1},
        }
    }

    _src, col, _conf, _role, steps = planner.resolve_metric("unit cost", "POS", "avg")

    assert col == "UNIT_COST"
    gap_steps = [s for s in steps if "gap" in s]
    assert gap_steps, "Expected at least one gap step for disambiguation"
    # The gap step should mention both candidates
    assert "UNIT_COST" in gap_steps[0]
    assert "EXT_COST" in gap_steps[0]


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
            "local_group": {"fill_rate": 1.0, "unique_count": 4, "total_count": 240, "strings": ["g_a", "g_b"]},
        },
        "L0": {
            "local_group": {"fill_rate": 1.0, "unique_count": 4, "total_count": 12, "strings": ["g_a", "g_b"]},
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
            "INVENTORY_TYPE": ColumnNode(name="INVENTORY_TYPE", role="metric", is_numeric=True, fill_rate=0.41),
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
            "SHIP_TO_STATE": {"fill_rate": 0.43, "unique_count": 42, "total_count": 1000, "strings": ["CA", "NY"]},
        },
        "S1": {
            "SHIP_TO_STATE": {"fill_rate": 0.96, "unique_count": 50, "total_count": 1000, "strings": ["CA", "TX"]},
        },
    }
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0", "EXT_PRICE", 1.0, "derived_measure", ["metric"]
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S1", "SHIP_TO_STATE", 1.33, ["dimension"]
    )

    plan = planner.plan("revenue", "ship to state", "sum", "S0")

    assert (plan.group_src, plan.group_col) == ("S0", "SHIP_TO_STATE")
    assert any("self_correct_same_source" in step for step in plan.steps)


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

    clean = planner._join_candidate_effective_conf({
        "source_a": "S0",
        "field_a": "ORDER_NUMBER",
        "source_b": "S1",
        "field_b": "ORDER_NUMBER",
        "confidence": 0.75,
        "cardinality": "many_to_many",
    })
    noisy = planner._join_candidate_effective_conf({
        "source_a": "S0",
        "field_a": "PRODUCT_LINE",
        "source_b": "S1",
        "field_b": "PRODUCT_LINE",
        "confidence": 0.80,
        "cardinality": "many_to_many",
    })

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

    stable = planner._join_candidate_effective_conf({
        "source_a": "S0",
        "field_a": "ORDER_NUMBER",
        "source_b": "S1",
        "field_b": "ORDER_NUMBER",
        "confidence": 0.74,
        "cardinality": "many_to_many",
    }, group_col="INVENTORY_TYPE")
    conflicted = planner._join_candidate_effective_conf({
        "source_a": "S0",
        "field_a": "PRODUCT_LINE",
        "source_b": "S1",
        "field_b": "PRODUCT_LINE",
        "confidence": 0.82,
        "cardinality": "many_to_many",
    }, group_col="INVENTORY_TYPE")

    assert stable > conflicted


def test_join_candidate_effective_conf_penalizes_low_distinct_join_keys(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.tables = {
        "S0": [{"ORDER_NUMBER": "O1"}, {"ORDER_NUMBER": "O2"}, {"ORDER_NUMBER": "O3"}],
        "S1": [{"ORDER_NUMBER": "O1"}, {"ORDER_NUMBER": "O2"}, {"ORDER_NUMBER": "O3"}],
    }
    planner.profiles = {
        "S0": {
            "ORDER_NUMBER": {"fill_rate": 1.0, "unique_count": 3, "total_count": 3, "strings": ["O1", "O2", "O3"]},
            "MESSAGE_CODE": {"fill_rate": 1.0, "unique_count": 3, "total_count": 300, "strings": ["A", "B", "C"]},
        },
        "S1": {
            "ORDER_NUMBER": {"fill_rate": 1.0, "unique_count": 3, "total_count": 3, "strings": ["O1", "O2", "O3"]},
            "MESSAGE_CODE": {"fill_rate": 1.0, "unique_count": 3, "total_count": 500, "strings": ["A", "B", "C"]},
        },
    }

    strong = planner._join_candidate_effective_conf({
        "source_a": "S0",
        "field_a": "ORDER_NUMBER",
        "source_b": "S1",
        "field_b": "ORDER_NUMBER",
        "confidence": 0.70,
        "cardinality": "many_to_many",
    })
    weak = planner._join_candidate_effective_conf({
        "source_a": "S0",
        "field_a": "MESSAGE_CODE",
        "source_b": "S1",
        "field_b": "MESSAGE_CODE",
        "confidence": 0.78,
        "cardinality": "many_to_many",
    })

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


def test_join_candidate_effective_conf_registry_inventory_dimension_prefers_part_number_key(tmp_path):
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


def test_plan_prefers_group_stable_join_for_cross_source_dimension(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "S0": {
            "EXT_PRICE": ColumnNode(name="EXT_PRICE", role="derived_measure", is_numeric=True, fill_rate=1.0),
        },
        "S1": {
            "INVENTORY_TYPE": ColumnNode(name="INVENTORY_TYPE", role="metric", is_numeric=True, fill_rate=0.5),
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
            "ORDER_NUMBER": {"fill_rate": 1.0, "unique_count": 3, "total_count": 3, "strings": ["O1", "O2", "O3"]},
            "PART_NUMBER": {"fill_rate": 1.0, "unique_count": 3, "total_count": 3, "strings": ["P1", "P2", "P3"]},
            "EXT_PRICE": {"fill_rate": 1.0, "unique_count": 3, "total_count": 3, "is_numeric": True, "sample_values": [100.0, 80.0, 50.0], "strings": []},
        },
        "S1": {
            "ORDER_NUMBER": {"fill_rate": 1.0, "unique_count": 3, "total_count": 5, "strings": ["O1", "O2", "OX"]},
            "PART_NUMBER": {"fill_rate": 1.0, "unique_count": 2, "total_count": 5, "strings": ["P1", "P2"]},
            "INVENTORY_TYPE": {"fill_rate": 0.5, "unique_count": 3, "total_count": 5, "strings": [], "sample_values": [1, 2, 3]},
        },
    }
    planner.resolve_metric = lambda hint, preferred_source=None, agg="sum": (
        "S0", "EXT_PRICE", 1.0, "derived_measure", ["metric"]
    )
    planner.resolve_dimension = lambda hint, preferred_source=None: (
        "S1", "INVENTORY_TYPE", 0.9, ["dimension"]
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
    assert (plan.join_hops[0].left_key, plan.join_hops[0].right_key) == ("ORDER_NUMBER", "ORDER_NUMBER")


def test_search_join_path_short_circuits_safe_direct_path(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "S0": {"EXT_PRICE": ColumnNode(name="EXT_PRICE", role="derived_measure", is_numeric=True, fill_rate=1.0)},
        "S1": {"INVENTORY_TYPE": ColumnNode(name="INVENTORY_TYPE", role="category", is_numeric=False, fill_rate=1.0)},
        "S2": {"PRODUCT_LINE": ColumnNode(name="PRODUCT_LINE", role="category", is_numeric=False, fill_rate=1.0)},
    }
    planner.profiles = {
        "S0": {
            "ORDER_NUMBER": {"fill_rate": 1.0, "unique_count": 700, "total_count": 1000, "strings": ["O1", "O2"]},
        },
        "S1": {
            "ORDER_NUMBER": {"fill_rate": 1.0, "unique_count": 900, "total_count": 1200, "strings": ["O1", "O2"]},
            "INVENTORY_TYPE": {"fill_rate": 1.0, "unique_count": 12, "total_count": 1200, "strings": [], "sample_values": [1, 2, 3]},
        },
        "S2": {
            "PRODUCT_LINE": {"fill_rate": 1.0, "unique_count": 20, "total_count": 1200, "strings": ["A", "B"]},
        },
    }

    calls: list[tuple[str, str]] = []

    def _fake_direct_join_candidates(left_source: str, right_source: str) -> list[dict[str, object]]:
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


def test_resolve_metric_query_hints_sales_prefers_measure_over_sales_person_id(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner._query_hints_by_src = {
        "POS": [{
            "metric_role": "derived_measure",
            "columns": [{"name": "EXT_PRICE", "fill_rate": 1.0, "formula": "qty * unit_price"}],
        }, {
            "metric_role": "base_measure",
            "columns": [{"name": "CUST_SALES_PERSON_NO", "fill_rate": 1.0}],
        }],
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


def test_discover_sources_includes_local_parquet(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(
        pa.Table.from_pylist([{"entity_id": "A1", "measure_total": 10.0}]),
        tmp_path / "S0.parquet",
    )
    (tmp_path / "S1.csv").write_text("entity_id,measure_total\nB1,20\n", encoding="utf-8")

    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")

    assert planner.discover_sources() == ["S0", "S1"]


def test_build_knowledge_loads_local_parquet_sources(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = [
        {"entity_id": "A1", "local_group": "g_a", "measure_total": 10.0},
        {"entity_id": "A2", "local_group": "g_b", "measure_total": 20.0},
        {"entity_id": "A3", "local_group": "g_a", "measure_total": 30.0},
    ]
    pq.write_table(pa.Table.from_pylist(rows), tmp_path / "S0.parquet")

    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.build_knowledge()

    assert "S0" in planner.tables
    assert len(planner.tables["S0"]) == 3
    assert planner.profiles["S0"]["measure_total"]["is_numeric"] is True
    assert planner.profiles["S0"]["local_group"]["strings"] == ["g_a", "g_b", "g_a"]


def test_from_registry_uses_persisted_profiles_and_lazy_loads_records(tmp_path, monkeypatch):
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    rows = [
        {"entity_id": "A1", "local_group": "g_a", "measure_total": 10.0},
        {"entity_id": "A2", "local_group": "g_b", "measure_total": 20.0},
    ]
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), buf)

    reg.register_source(
        "org_registry",
        "src_a",
        "S0",
        buf.getvalue(),
        {
            "source": "S0",
            "row_count": 2,
            "columns": [
                {"name": "entity_id", "role": "identifier", "is_numeric": False, "fill_rate": 1.0, "samples": ["A1", "A2"]},
                {"name": "local_group", "role": "category", "is_numeric": False, "fill_rate": 1.0, "samples": ["g_a", "g_b"], "cardinality": 2},
                {"name": "measure_total", "role": "derived_measure", "is_numeric": True, "fill_rate": 1.0, "mean": 15.0, "magnitude": "large"},
            ],
            "query_hints": [{
                "metric_role": "derived_measure",
                "columns": [{"name": "measure_total", "fill_rate": 1.0, "samples": ["10.0", "20.0"], "mean": 15.0}],
            }],
            "planner_profile": {
                "entity_id": {
                    "is_numeric": False,
                    "strings": ["A1", "A2"],
                    "sample_values": ["A1", "A2"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                },
                "local_group": {
                    "is_numeric": False,
                    "strings": ["g_a", "g_b"],
                    "sample_values": ["g_a", "g_b"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                },
                "measure_total": {
                    "is_numeric": True,
                    "sample_values": ["10.0", "20.0"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                    "mean": 15.0,
                    "std": 5.0,
                },
            },
            "roles_summary": {"identifier": 1, "category": 1, "derived_measure": 1},
            "formulas": [],
        },
        graph_nodes={},
        profile={},
    )

    planner = AutoPlanner.from_registry("org_registry", data_dir=Path(tmp_path), llm_policy="never")

    assert "S0" not in planner.tables
    assert planner.profiles["S0"]["measure_total"]["mean"] == 15.0
    assert planner.profiles["S0"]["local_group"]["strings"] == ["g_a", "g_b"]
    assert planner._parquet_paths["S0"].exists()

    planner._ensure_records("S0")

    assert "S0" in planner.tables
    assert len(planner.tables["S0"]) == 2


def test_from_registry_reuses_cached_graph_nodes_across_rebuilds(tmp_path, monkeypatch):
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    query_router._GRAPH_NODE_CACHE.clear()
    AutoPlanner.from_registry.__globals__["_REGISTRY_SOURCE_ARTIFACT_CACHE"].clear()

    rows = [
        {"entity_id": "A1", "measure_total": 10.0},
        {"entity_id": "A2", "measure_total": 20.0},
    ]
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), buf)

    reg.register_source(
        "org_registry",
        "src_a",
        "S0",
        buf.getvalue(),
        {
            "source": "S0",
            "row_count": 2,
            "columns": [
                {"name": "entity_id", "role": "identifier", "is_numeric": False, "fill_rate": 1.0},
                {
                    "name": "measure_total",
                    "role": "derived_measure",
                    "is_numeric": True,
                    "fill_rate": 1.0,
                    "mean": 15.0,
                    "magnitude": "medium",
                },
            ],
            "planner_profile": {
                "entity_id": {
                    "is_numeric": False,
                    "strings": ["A1", "A2"],
                    "sample_values": ["A1", "A2"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                },
                "measure_total": {
                    "is_numeric": True,
                    "sample_values": ["10.0", "20.0"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                    "mean": 15.0,
                    "std": 5.0,
                },
            },
            "roles_summary": {"identifier": 1, "derived_measure": 1},
            "formulas": [],
        },
        graph_nodes={},
        profile={},
    )

    calls = {"graph": 0, "profile": 0}
    original_graph = query_router._graph_nodes_from_meta
    original_profiles = AutoPlanner.from_registry.__globals__["_profiles_from_registry_meta"]

    def _counting_graph_nodes(meta: dict) -> dict[str, ColumnNode]:
        calls["graph"] += 1
        return original_graph(meta)

    def _counting_profiles(meta: dict) -> dict[str, dict]:
        calls["profile"] += 1
        return original_profiles(meta)

    monkeypatch.setattr(query_router, "_graph_nodes_from_meta", _counting_graph_nodes)
    monkeypatch.setitem(
        AutoPlanner.from_registry.__globals__,
        "_profiles_from_registry_meta",
        _counting_profiles,
    )

    first = AutoPlanner.from_registry("org_registry", data_dir=Path(tmp_path), llm_policy="never")
    second = AutoPlanner.from_registry("org_registry", data_dir=Path(tmp_path), llm_policy="never")

    assert "S0" in first.graph
    assert "S0" in second.graph
    assert calls["graph"] == 1
    assert calls["profile"] == 1


def test_python_field_map_prefers_percentage_when_hint_mentions_percent():
    analysis = AutoPlanner._python_field_map("aar margin percent")

    assert analysis["unit"] == "percentage"
    assert analysis["semantic_type"] == "percentage"


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
