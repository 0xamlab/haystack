from types import SimpleNamespace

import apps.api_server.services.auto_planner_plan as auto_planner_plan
from apps.api_server.services.auto_planner_plan import (
    JoinState,
    PlanSelection,
    apply_llm_review,
    build_join_state,
    build_query_plan,
    llm_review_decision,
    prefer_same_source_metric_selection,
    resolve_dimension_state,
)


def test_build_join_state_returns_dimension_error_when_unresolved():
    planner = SimpleNamespace(mojo_engines=[], _search_join_path=lambda *_args, **_kwargs: None)
    mojo_ops: list[str] = []

    join_state = build_join_state(
        planner,
        current_metric_src="S0",
        current_group_src="",
        current_group_col=None,
        dim_hint="region",
        mojo_ops=mojo_ops,
    )

    assert join_state.plan_error == "No supported dimension found for hint 'region'"
    assert join_state.validation_notes == ["No supported dimension found for hint 'region'"]
    assert mojo_ops == []


def test_build_join_state_records_join_path_and_join_detect_op():
    hop = SimpleNamespace(
        left_source="S0",
        right_source="S1",
        left_key="CUSTOMER_ID",
        right_key="CUSTOMER_ID",
        confidence=0.97,
        cardinality="many_to_one",
    )
    planner = SimpleNamespace(
        mojo_engines=["join_detect"],
        _search_join_path=lambda *_args, **_kwargs: (
            [hop],
            0.97,
            ["multi-hop path via registry connections"],
            None,
        ),
    )
    mojo_ops: list[str] = []

    join_state = build_join_state(
        planner,
        current_metric_src="S0",
        current_group_src="S1",
        current_group_col="REGION",
        dim_hint="region",
        mojo_ops=mojo_ops,
    )

    assert join_state.join_key_metric == "CUSTOMER_ID"
    assert join_state.join_key_group == "CUSTOMER_ID"
    assert join_state.join_conf == 0.97
    assert join_state.join_cardinality == "many_to_one"
    assert join_state.join_hops == [hop]
    assert any(step.startswith("[join_detect]") for step in join_state.join_steps)
    assert any("SELECTED 1 hop path" in step for step in join_state.join_steps)
    assert mojo_ops == ["join_detect"]


def test_resolve_dimension_state_keeps_source_hint_match_without_same_source_override():
    def _same_source_dimension_candidate(*_args):
        raise AssertionError("same-source fallback should not run for explicit source hints")

    planner = SimpleNamespace(
        graph={"Inventory": {}, "POS": {}},
        resolve_dimension=lambda *_args: (
            "Inventory",
            "Product Line",
            0.91,
            ["[dimension] source_hint_exact"],
        ),
        _same_source_dimension_candidate=_same_source_dimension_candidate,
    )

    dimension_state = resolve_dimension_state(
        planner,
        dim_hint="inventory product line",
        metric_src="POS",
        preferred_source="POS",
    )

    assert dimension_state.group_src == "Inventory"
    assert dimension_state.group_col == "Product Line"
    assert dimension_state.group_conf == 0.91
    assert dimension_state.steps == ["[dimension] source_hint_exact"]


def test_resolve_dimension_state_self_corrects_same_named_dimension_back_to_metric_source():
    planner = SimpleNamespace(
        graph={"S0": {}, "S1": {}},
        resolve_dimension=lambda *_args: (
            "S1",
            "SHIP_TO_STATE",
            1.33,
            ["[dimension] resolved_cross_source"],
        ),
        _same_source_dimension_candidate=lambda *_args: (
            "S0",
            "SHIP_TO_STATE",
            0.43,
            ["[dimension] self_correct_same_source"],
        ),
    )

    dimension_state = resolve_dimension_state(
        planner,
        dim_hint="ship to state",
        metric_src="S0",
        preferred_source="S0",
    )

    assert dimension_state.group_src == "S0"
    assert dimension_state.group_col == "SHIP_TO_STATE"
    assert dimension_state.group_conf == 0.43
    assert dimension_state.steps == [
        "[dimension] resolved_cross_source",
        "[dimension] self_correct_same_source",
    ]


def test_apply_llm_review_updates_selection_and_rebuilds_join_state():
    planner = SimpleNamespace(
        graph={"S1": {"NET_REVENUE": SimpleNamespace(role="derived_measure")}},
        _query_hints_by_src={"S1": ["net revenue"]},
        _llm_confirm_plan=lambda **_kwargs: {
            "metric_src": "S1",
            "metric_col": "NET_REVENUE",
            "group_src": "S1",
            "group_col": "REGION",
            "reasoning": "prefer reviewed revenue mapping",
        },
        mojo_engines=[],
        _search_join_path=lambda *_args, **_kwargs: None,
    )
    selection = PlanSelection(
        metric_src="S0",
        metric_col="AMOUNT",
        metric_conf=0.84,
        metric_role="measure",
        group_src="S0",
        group_col="STATE",
        group_conf=0.72,
    )
    join_state = JoinState(path_confidence=1.0)

    updated_selection, rebuilt_join_state, review_steps = apply_llm_review(
        planner,
        metric_hint="revenue",
        dim_hint="region",
        agg="sum",
        preferred_source="S0",
        selection=selection,
        join_state=join_state,
        review_reason="low_dimension_confidence",
        mojo_ops=[],
    )

    assert updated_selection.metric_src == "S1"
    assert updated_selection.metric_col == "NET_REVENUE"
    assert updated_selection.metric_role == "derived_measure"
    assert updated_selection.group_src == "S1"
    assert updated_selection.group_col == "REGION"
    assert updated_selection.group_conf == 1.0
    assert rebuilt_join_state.path_confidence == 1.0
    assert review_steps == ["[llm] prefer reviewed revenue mapping"]


def test_apply_llm_review_preserves_explicit_join_budget_on_rebuild():
    observed_max_hops: list[int] = []

    def _search_join_path(*_args, **kwargs):
        observed_max_hops.append(kwargs["max_hops"])
        return ([], 0.0, [], None)

    planner = SimpleNamespace(
        graph={"S1": {"NET_REVENUE": SimpleNamespace(role="derived_measure")}},
        _query_hints_by_src={"S1": ["net revenue"]},
        _llm_confirm_plan=lambda **_kwargs: {
            "metric_src": "S1",
            "metric_col": "NET_REVENUE",
            "group_src": "S2",
            "group_col": "REGION",
            "reasoning": "prefer reviewed revenue mapping",
        },
        mojo_engines=[],
        _search_join_path=_search_join_path,
    )
    selection = PlanSelection(
        metric_src="S0",
        metric_col="AMOUNT",
        metric_conf=0.84,
        metric_role="measure",
        group_src="S0",
        group_col="STATE",
        group_conf=0.72,
    )

    apply_llm_review(
        planner,
        metric_hint="revenue",
        dim_hint="region",
        agg="sum",
        preferred_source="S0",
        selection=selection,
        join_state=JoinState(path_confidence=1.0),
        review_reason="low_dimension_confidence",
        mojo_ops=[],
        max_join_hops=6,
    )

    assert observed_max_hops == [6]


def test_prefer_same_source_metric_selection_rewrites_weak_many_to_many_join():
    planner = SimpleNamespace(
        _join_min_conf=0.4,
        graph={
            "BookingsNew": {},
            "Inventory": {
                "EXT_COST": SimpleNamespace(
                    role="component",
                    is_numeric=True,
                    fill_rate=1.0,
                ),
                "Warehouse": SimpleNamespace(
                    role="category",
                    is_numeric=False,
                    fill_rate=1.0,
                ),
            },
        },
        mojo_engines=[],
        _search_join_path=lambda *_args, **_kwargs: None,
    )
    selection = PlanSelection(
        metric_src="BookingsNew",
        metric_col="EXT_COST",
        metric_conf=1.015,
        metric_role="derived_measure",
        group_src="Inventory",
        group_col="Warehouse",
        group_conf=1.85,
    )
    join_state = JoinState(
        join_hops=[object()],
        join_cardinality="many_to_many",
        path_confidence=0.298,
    )

    updated_selection, rebuilt_join_state, correction_steps = prefer_same_source_metric_selection(
        planner,
        selection=selection,
        join_state=join_state,
        dim_hint="warehouse",
        preferred_source="Inventory",
        mojo_ops=[],
    )

    assert updated_selection.metric_src == "Inventory"
    assert updated_selection.metric_col == "EXT_COST"
    assert updated_selection.metric_role == "component"
    assert rebuilt_join_state.path_confidence == 1.0
    assert correction_steps == [
        "[metric/self_correct_same_source] "
        "BookingsNew.EXT_COST → Inventory.EXT_COST  "
        "reason=many_to_many_join,low_join_conf=0.298"
    ]


def test_prefer_same_source_metric_selection_preserves_explicit_join_budget_on_rebuild(
    monkeypatch,
):
    observed_max_hops: list[int] = []

    def _build_join_state(*_args, **kwargs):
        observed_max_hops.append(kwargs["max_join_hops"])
        return JoinState(path_confidence=1.0)

    planner = SimpleNamespace(
        _join_min_conf=0.4,
        graph={
            "BookingsNew": {},
            "Inventory": {
                "EXT_COST": SimpleNamespace(
                    role="component",
                    is_numeric=True,
                    fill_rate=1.0,
                ),
                "Warehouse": SimpleNamespace(
                    role="category",
                    is_numeric=False,
                    fill_rate=1.0,
                ),
            },
        },
        mojo_engines=[],
        _search_join_path=lambda *_args, **_kwargs: None,
    )
    selection = PlanSelection(
        metric_src="BookingsNew",
        metric_col="EXT_COST",
        metric_conf=1.015,
        metric_role="derived_measure",
        group_src="Inventory",
        group_col="Warehouse",
        group_conf=1.85,
    )
    join_state = JoinState(
        join_hops=[object()],
        join_cardinality="many_to_many",
        path_confidence=0.298,
    )

    monkeypatch.setattr(auto_planner_plan, "build_join_state", _build_join_state)

    prefer_same_source_metric_selection(
        planner,
        selection=selection,
        join_state=join_state,
        dim_hint="warehouse",
        preferred_source="Inventory",
        mojo_ops=[],
        max_join_hops=6,
    )

    assert observed_max_hops == [6]


def test_prefer_same_source_metric_selection_keeps_original_source_when_group_source_is_not_preferred():
    planner = SimpleNamespace(
        _join_min_conf=0.4,
        graph={
            "Inventory": {
                "EXT_COST": SimpleNamespace(
                    role="component",
                    is_numeric=True,
                    fill_rate=1.0,
                ),
            },
        },
    )
    selection = PlanSelection(
        metric_src="BookingsNew",
        metric_col="EXT_COST",
        metric_conf=1.015,
        metric_role="derived_measure",
        group_src="Inventory",
        group_col="Warehouse",
        group_conf=1.85,
    )
    join_state = JoinState(
        join_hops=[object()],
        join_cardinality="many_to_many",
        path_confidence=0.298,
    )

    updated_selection, rebuilt_join_state, correction_steps = prefer_same_source_metric_selection(
        planner,
        selection=selection,
        join_state=join_state,
        dim_hint="warehouse",
        preferred_source="BookingsNew",
        mojo_ops=[],
    )

    assert updated_selection == selection
    assert rebuilt_join_state == join_state
    assert correction_steps == []


def test_build_query_plan_appends_validation_notes_and_deduplicates_mojo_ops():
    class QueryPlanStub:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    selection = PlanSelection(
        metric_src="S0",
        metric_col="NET_REVENUE",
        metric_conf=0.97,
        metric_role="derived_measure",
        group_src="S1",
        group_col="REGION",
        group_conf=0.88,
    )
    join_state = JoinState(
        join_key_metric="CUSTOMER_ID",
        join_key_group="CUSTOMER_ID",
        join_conf=0.92,
        join_cardinality="many_to_one",
        join_hops=[object()],
        path_confidence=0.92,
        intermediate_sources=["Customers"],
        validation_notes=["ambiguous candidate rejected"],
        plan_error=None,
    )

    plan = build_query_plan(
        query_plan_cls=QueryPlanStub,
        selection=selection,
        agg="sum",
        join_state=join_state,
        mojo_ops=["field_map", "join_detect", "field_map"],
        steps=["metric", "dimension"],
    )

    assert plan.metric_src == "S0"
    assert plan.group_src == "S1"
    assert plan.validation_notes == ["ambiguous candidate rejected"]
    assert plan.mojo_ops == ["field_map", "join_detect"]
    assert plan.steps == [
        "metric",
        "dimension",
        "[validation] ambiguous candidate rejected",
    ]


def test_llm_review_decision_skips_confident_same_source():
    join_state = JoinState()

    should_review, reason = llm_review_decision(
        llm_policy="auto",
        dim_hint="group",
        group_col="GROUP_DIM",
        group_src="S0",
        metric_src="S0",
        metric_conf=1.0,
        group_conf=0.95,
        join_state=join_state,
        join_min_confidence=0.4,
    )

    assert should_review is False
    assert reason == "confident_same_source"


def test_llm_review_decision_flags_many_to_many_join():
    join_state = JoinState(
        join_hops=[object()],
        join_cardinality="many_to_many",
        path_confidence=0.91,
    )

    should_review, reason = llm_review_decision(
        llm_policy="auto",
        dim_hint="region",
        group_col="REGION",
        group_src="S1",
        metric_src="S0",
        metric_conf=1.1,
        group_conf=0.95,
        join_state=join_state,
        join_min_confidence=0.4,
    )

    assert should_review is True
    assert reason == "many_to_many_join"
