import pytest
from pydantic import ValidationError

from apps.api_server.routers.query import (
    CandidateColumn,
    JoinEdgeSpec,
    JoinPathSpec,
    QueryRequest,
    QueryResponse,
    _decision_contract_flags,
    _planner_load_bearing_validation_notes,
    _planner_query_confidence,
)


def test_query_request_accepts_explicit_multi_hop_join_path():
    req = QueryRequest(
        source_name="S0",
        metric_column="metric_value",
        group_column="group_attr",
        aggregation="sum",
        join_path=JoinPathSpec(
            base_source="S0",
            group_source="S2",
            edges=[
                JoinEdgeSpec(
                    left_source="S0",
                    right_source="S1",
                    left_key="k01_left",
                    right_key="k01_right",
                    min_confidence=0.8,
                ),
                JoinEdgeSpec(
                    left_source="S1",
                    right_source="S2",
                    left_key="k12_left",
                    right_key="k12_right",
                    min_confidence=0.8,
                ),
            ],
            max_hops=4,
            min_path_confidence=0.7,
        ),
    )

    assert req.join_path is not None
    assert req.join_path.base_source == "S0"
    assert len(req.join_path.edges) == 2


def test_join_path_spec_defaults_to_safe_constraints():
    path = JoinPathSpec(base_source="S0")

    assert path.max_hops == 4
    assert path.reject_on_ambiguity is True
    assert path.reject_on_fanout is True


def test_query_request_rejects_legacy_single_hop_fields():
    with pytest.raises(ValidationError):
        QueryRequest(
            source_name="S0",
            metric_column="metric_value",
            aggregation="sum",
            join_source_name="S1",
        )


def test_query_request_rejects_unknown_extra_fields_inside_join_path():
    with pytest.raises(ValidationError):
        QueryRequest(
            source_name="S0",
            metric_column="metric_value",
            group_column="group_attr",
            aggregation="sum",
            join_path=JoinPathSpec.model_validate({
                "base_source": "S0",
                "group_source": "S1",
                "edges": [{
                    "left_source": "S0",
                    "right_source": "S1",
                    "left_key": "k01_left",
                    "right_key": "k01_right",
                    "legacy": True,
                }],
            }),
        )


def test_candidate_column_accepts_explainability_fields():
    cand = CandidateColumn(
        source="POS",
        column="UNIT_COST",
        role="unit_measure",
        magnitude="medium",
        formula=None,
        confidence=0.712,
        score_components={"typed_intent": 0.18, "source_prior": 0.07},
        notes=["typed-intent-match", "source-prior:unit"],
    )

    assert cand.score_components["typed_intent"] == 0.18
    assert "source-prior:unit" in cand.notes


def test_query_response_preserves_ranked_candidate_explanations():
    resp = QueryResponse(
        query_id="q1",
        result=None,
        result_type="none",
        confidence=0.641,
        plan=["Metric ambiguity: top=UNIT_COST second=EXT_COST gap=0.021"],
        resolved_column="UNIT_COST",
        resolved_role="unit_measure",
        resolved_source="POS",
        row_count=0,
        candidates=[
            CandidateColumn(
                source="POS",
                column="UNIT_COST",
                role="unit_measure",
                magnitude="medium",
                formula=None,
                confidence=0.641,
                score_components={"typed_intent": 0.18},
                notes=["ambiguous-top2-gap:0.021"],
            )
        ],
        source_scores={"POS": 0.88},
        ambiguous=True,
        exact_spec=False,
        explanation=[],
        latency_ms=12.3,
        decision_path="planner_hint",
        plan_hash="plan_123",
        schema_revision="schema_rev_1",
        validated=False,
        deterministic_scope="planning_only",
        confidence_source="planner_resolver",
        clarification_required=True,
        rejection_reason=None,
        request_id="req_123",
    )

    assert resp.candidates[0].score_components == {"typed_intent": 0.18}
    assert resp.candidates[0].notes == ["ambiguous-top2-gap:0.021"]


def test_decision_contract_flags_require_clarification_for_mid_confidence():
    validated, clarification_required, rejection_reason = _decision_contract_flags(
        0.81,
        [
            {"source": "POS", "column": "UNIT_COST", "role": "unit_measure", "magnitude": "medium", "formula": None, "confidence": 0.81},
            {"source": "POS", "column": "EXT_COST", "role": "unit_measure", "magnitude": "medium", "formula": None, "confidence": 0.76},
        ],
    )

    assert validated is False
    assert clarification_required is True
    assert rejection_reason is None


def test_decision_contract_flags_reject_low_confidence():
    validated, clarification_required, rejection_reason = _decision_contract_flags(
        0.69,
        [
            {"source": "POS", "column": "UNIT_COST", "role": "unit_measure", "magnitude": "medium", "formula": None, "confidence": 0.69},
        ],
    )

    assert validated is False
    assert clarification_required is False
    assert rejection_reason == "schema_unresolved"


def test_planner_query_confidence_does_not_penalize_safe_selected_join_path():
    class Plan:
        metric_conf = 0.963
        group_col = "INVENTORY_TYPE"
        group_conf = 1.732
        join_hops = [object()]
        path_confidence = 0.259
        join_conf = 0.259
        error = None
        validation_notes = ["ambiguous join candidates between QuotesNew and POSNew"]

    assert _planner_query_confidence(Plan()) == 0.963


def test_planner_load_bearing_validation_notes_ignore_informational_join_candidate_warning():
    class Plan:
        join_hops = [object()]
        validation_notes = [
            "ambiguous join candidates between Backlog and POSNew",
            "ambiguous multi-hop path candidates from Backlog to POSNew",
        ]

    assert _planner_load_bearing_validation_notes(Plan()) == [
        "ambiguous multi-hop path candidates from Backlog to POSNew"
    ]
