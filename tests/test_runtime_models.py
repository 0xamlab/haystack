from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

runtime_models = importlib.import_module("algenta.runtime_models")
QueryOutput = runtime_models.QueryOutput
ResolveOutput = runtime_models.ResolveOutput
ResolvedPlan = runtime_models.ResolvedPlan
SourceRegistration = runtime_models.SourceRegistration


class _JsonableValue:
    def __init__(self, payload: dict[str, str]) -> None:
        self._payload = payload

    def to_dict(self) -> dict[str, str]:
        return dict(self._payload)


def test_runtime_models_wrapper_loads_leaf_modules_lazily() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "algenta.runtime_models"
        or module_name.startswith("algenta.runtime_model_")
    }
    for module_name in list(sys.modules):
        if module_name == "algenta.runtime_models" or module_name.startswith(
            "algenta.runtime_model_"
        ):
            sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module("algenta.runtime_models")

        assert "algenta.runtime_model_query_output" not in sys.modules
        assert "algenta.runtime_model_source_registration" not in sys.modules

        query_output_cls = module.QueryOutput

        assert query_output_cls.__name__ == "QueryOutput"
        assert "algenta.runtime_models" in sys.modules
        assert "algenta.runtime_model_query_output" in sys.modules
        assert "algenta.runtime_model_source_registration" not in sys.modules

        registration_cls = module.SourceRegistration

        assert registration_cls.__name__ == "SourceRegistration"
        assert "algenta.runtime_model_source_registration" in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "algenta.runtime_models" or module_name.startswith(
                "algenta.runtime_model_"
            ):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


def test_source_registration_from_api_uses_dataset_name_and_schema_alias() -> None:
    registration = SourceRegistration.from_api(
        {
            "source_id": "src_123",
            "dataset_id": "ds_123",
            "dataset_name": "orders",
            "status": "ready",
            "schema": {"fields": ["revenue", "region"]},
            "row_count": 42,
        }
    )

    assert registration.name == "orders"
    assert registration.dataset_name == "orders"
    assert registration.source_schema == {"fields": ["revenue", "region"]}
    assert registration.row_count == 42


def test_resolve_output_to_dict_serializes_nested_plan() -> None:
    output = ResolveOutput(
        resolved_plan=ResolvedPlan(
            source_name="orders",
            metric_column="revenue",
            aggregation="sum",
            group_column="region",
            schema_revision="schema_v1",
        ),
        confidence=1.0,
        plan=["Use source 'orders'."],
        explanation=["Resolved metric 'revenue' to 'revenue'."],
        latency_ms=12.5,
        decision_path="exact_spec",
        schema_revision="schema_v1",
        validated=True,
        deterministic_scope="local_registered_source",
        confidence_source="local_schema_match",
    )

    payload = output.to_dict()

    assert payload["resolved_plan"]["source_name"] == "orders"
    assert payload["resolved_plan"]["metric_column"] == "revenue"
    assert payload["confidence"] == 1.0


def test_query_output_to_dict_jsonifies_nested_values() -> None:
    output = QueryOutput(
        result={
            "summary": _JsonableValue({"label": "north"}),
            "rows": [_JsonableValue({"label": "south"})],
        },
        result_type="table",
        confidence=1.0,
        plan=["Aggregate 'revenue' with 'sum'."],
        resolved_column="revenue",
        resolved_role="measure",
        resolved_source="orders",
        row_count=2,
        ambiguous=False,
        exact_spec=True,
        explanation=["Executed deterministic local plan."],
        latency_ms=3.1,
        decision_path="exact_spec",
        plan_hash="hash_123",
        validated=True,
        deterministic_scope="local_registered_source",
        confidence_source="local_exact_execution",
    )

    payload = output.to_dict()

    assert payload["result"]["summary"] == {"label": "north"}
    assert payload["result"]["rows"] == [{"label": "south"}]
