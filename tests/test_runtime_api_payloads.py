from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from algenta.runtime_api_payloads import (  # noqa: E402
    _RUNTIME_DATASET_SCOPE_KEY,
    coerce_api_query_payload,
    coerce_api_resolve_payload,
    coerce_plan,
)
from algenta.runtime_errors import RuntimeValidationError  # noqa: E402
from algenta.runtime_models import QueryOutput, ResolvedPlan, ResolveOutput  # noqa: E402


def _resolved_plan() -> ResolvedPlan:
    return ResolvedPlan(
        source_name="orders",
        metric_column="amount",
        aggregation="sum",
        group_column="customer",
        schema_revision="schema_123",
    )


def test_coerce_api_resolve_payload_normalizes_source_metric_and_group() -> None:
    payload = coerce_api_resolve_payload(
        {
            "source_name": "orders",
            "metric": "gross_revenue",
            "group_by": "customer",
            "metric_column": "amount",
            "resolved_plan": {"ignored": True},
        }
    )

    assert payload == {
        "preferred_source": "orders",
        "allow_org_scope": True,
        "metric": {"role": "metric", "hint": "gross_revenue"},
        "group_by": ["customer"],
    }


def test_coerce_plan_accepts_resolve_output() -> None:
    output = ResolveOutput(
        resolved_plan=_resolved_plan(),
        confidence=1.0,
        plan=[],
        explanation=[],
        latency_ms=1.0,
        decision_path="exact_spec",
        schema_revision="schema_123",
        validated=True,
        deterministic_scope="api_registered_source",
        confidence_source="runtime_exact_spec",
    )

    assert coerce_plan(output, {}) == _resolved_plan()


def test_coerce_plan_rejects_non_executable_resolve_output() -> None:
    output = ResolveOutput(
        resolved_plan=None,
        confidence=0.4,
        plan=[],
        explanation=[],
        latency_ms=1.0,
        decision_path="clarify",
        schema_revision="",
        validated=False,
        deterministic_scope="api_registered_source",
        confidence_source="runtime_exact_spec",
        clarification_required=True,
    )

    with pytest.raises(RuntimeValidationError, match="executable plan"):
        coerce_plan(output, {})


def test_coerce_api_query_payload_wraps_exact_plan_mapping() -> None:
    payload = coerce_api_query_payload(
        {
            "source_name": "orders",
            "metric_column": "amount",
            "aggregation": "sum",
            "schema_revision": "schema_123",
        },
        {},
    )

    assert payload == {
        "resolved_plan": {
            "source_name": "orders",
            "metric_column": "amount",
            "aggregation": "sum",
            "schema_revision": "schema_123",
        }
    }


def test_coerce_api_query_payload_lifts_runtime_dataset_scope() -> None:
    payload = coerce_api_query_payload(
        ResolveOutput(
            resolved_plan=ResolvedPlan(
                source_name="orders",
                metric_column="amount",
                aggregation="sum",
                schema_revision="schema_123",
                constraints={_RUNTIME_DATASET_SCOPE_KEY: "ds_123", "stable": True},
            ),
            confidence=1.0,
            plan=[],
            explanation=[],
            latency_ms=1.0,
            decision_path="exact_spec",
            schema_revision="schema_123",
            validated=True,
            deterministic_scope="api_registered_source",
            confidence_source="runtime_exact_spec",
        ),
        {},
    )

    assert payload["dataset_id"] == "ds_123"
    assert payload["resolved_plan"]["constraints"] == {"stable": True}


def test_coerce_api_query_payload_serializes_query_output() -> None:
    payload = coerce_api_query_payload(
        QueryOutput(
            result={"value": 3},
            result_type="scalar",
            confidence=1.0,
            plan=[],
            resolved_column="amount",
            resolved_role="measure",
            resolved_source="orders",
            row_count=1,
            ambiguous=False,
            exact_spec=True,
            explanation=[],
            latency_ms=1.0,
            decision_path="exact_spec",
            plan_hash="plan_123",
            validated=True,
            deterministic_scope="api_registered_source",
            confidence_source="runtime_exact_spec",
        ),
        {},
    )

    assert payload["result"] == {"value": 3}
    assert payload["resolved_source"] == "orders"
