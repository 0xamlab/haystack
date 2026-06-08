from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

helpers = importlib.import_module("decision_engine.request_helpers")
models = importlib.import_module("decision_engine.models")


def test_request_helpers_wrapper_loads_leaf_modules_lazily() -> None:
    modules = (
        "decision_engine.request_helpers",
        "decision_engine.request_common",
        "decision_engine.request_query_helpers",
        "decision_engine.request_simulation_helpers",
        "decision_engine.request_source_helpers",
        "decision_engine.request_explain_helpers",
    )
    preserved = {name: sys.modules[name] for name in modules if name in sys.modules}
    for module_name in modules:
        sys.modules.pop(module_name, None)

    try:
        wrapper = importlib.import_module("decision_engine.request_helpers")

        assert "decision_engine.request_query_helpers" not in sys.modules
        assert "decision_engine.request_simulation_helpers" not in sys.modules
        assert "decision_engine.request_source_helpers" not in sys.modules
        assert "decision_engine.request_explain_helpers" not in sys.modules

        assert wrapper._merge_request_payload.__name__ == "_merge_request_payload"
        assert "decision_engine.request_query_helpers" in sys.modules
        assert "decision_engine.request_simulation_helpers" not in sys.modules
        assert "decision_engine.request_source_helpers" not in sys.modules

        assert wrapper._normalize_simulation_request.__name__ == "_normalize_simulation_request"
        assert "decision_engine.request_simulation_helpers" in sys.modules

        assert (
            wrapper._normalize_source_registration_request.__name__
            == "_normalize_source_registration_request"
        )
        assert "decision_engine.request_source_helpers" in sys.modules

        assert wrapper._build_explain_result.__name__ == "_build_explain_result"
        assert "decision_engine.request_explain_helpers" in sys.modules
    finally:
        for module_name in modules:
            sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


def test_normalize_query_like_request_enforces_join_path_bounds() -> None:
    normalized = helpers._normalize_query_like_request(
        {"join_path": {"edges": [{"left_source": "Orders", "right_source": "Customers"}]}}
    )

    assert normalized["join_path"]["max_hops"] == helpers.DEFAULT_JOIN_PATH_HOPS

    with pytest.raises(ValueError, match="join_path.edges has 2 entries"):
        helpers._normalize_query_like_request(
            {
                "join_path": {
                    "max_hops": 1,
                    "edges": [
                        {"left_source": "Orders", "right_source": "Customers"},
                        {"left_source": "Customers", "right_source": "Regions"},
                    ],
                }
            }
        )


def test_normalize_source_registration_request_wraps_plain_source_payload() -> None:
    payload = helpers._normalize_source_registration_request(
        {"type": "file", "path": "orders.csv"},
        description="Orders import",
        extra={"name": "Orders"},
    )

    assert payload == {
        "source": {"type": "file", "path": "orders.csv"},
        "name": "Orders",
        "description": "Orders import",
    }


def test_build_explain_result_derives_source_set_and_join_path() -> None:
    query_result = models.QueryResult.model_validate(
        {
            "query_id": "q_123",
            "result": 42,
            "result_type": "scalar",
            "confidence": 0.97,
            "plan": ["Planner selected Orders.amount"],
            "resolved_column": "amount",
            "resolved_role": "derived_measure",
            "resolved_source": "Orders⋈Customers",
            "row_count": 1,
            "candidates": [],
            "source_scores": {"Orders": 0.97},
            "ambiguous": False,
            "exact_spec": False,
            "explanation": ["Deterministic execution"],
            "latency_ms": 9.5,
            "decision_path": "planner_hint",
            "plan_hash": "plan_123",
            "schema_revision": "schema_rev_1",
            "validated": True,
            "deterministic_scope": "planned_execution",
            "confidence_source": "planner_query_confidence",
            "clarification_required": False,
            "rejection_reason": None,
            "request_id": "req_123",
            "intent_signature": "intent_123",
            "source_set": [],
            "join_path": [],
            "planner_mode": None,
        }
    )

    explained = helpers._build_explain_result({}, query_result)

    assert explained.source_set == ["Orders", "Customers"]
    assert explained.join_path == [{"left_source": "Orders", "right_source": "Customers"}]
    assert explained.planner_mode == "planner_hint"
