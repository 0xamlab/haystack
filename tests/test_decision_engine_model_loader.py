from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_model_loader_imports_only_requested_domain_module_and_caches() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine" or module_name.startswith("decision_engine.")
    }
    for module_name in list(sys.modules):
        if module_name == "decision_engine" or module_name.startswith("decision_engine."):
            sys.modules.pop(module_name, None)

    try:
        loader = importlib.import_module("decision_engine.model_loader")
        load_model = loader._load_model
        load_model.cache_clear()

        query_result_cls = load_model("QueryResult")

        assert query_result_cls.__name__ == "QueryResult"
        assert "decision_engine.models_query_result" in sys.modules
        assert "decision_engine.models_connector_info" not in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_decision_envelope" not in sys.modules
        assert load_model("QueryResult") is query_result_cls

        connector_info_cls = load_model("ConnectorInfo")

        assert connector_info_cls.__name__ == "ConnectorInfo"
        assert "decision_engine.models_connector_info" in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_decision_envelope" not in sys.modules

        connector_list_cls = load_model("ConnectorListResult")

        assert connector_list_cls.__name__ == "ConnectorListResult"
        assert "decision_engine.models_connector_list_result" in sys.modules
        assert load_model("ConnectorListResult") is connector_list_cls

        envelope_cls = load_model("DecisionEnvelope")

        assert envelope_cls.__name__ == "DecisionEnvelope"
        assert "decision_engine.models_decision_envelope" in sys.modules
        assert "decision_engine.models_simulation_common" in sys.modules
        assert "decision_engine.models_metrics_summary" not in sys.modules
        assert "decision_engine.models_percentile_summary" not in sys.modules
        assert "decision_engine.models_run_metadata" not in sys.modules
        assert load_model("DecisionEnvelope") is envelope_cls
    finally:
        for module_name in list(sys.modules):
            if module_name == "decision_engine" or module_name.startswith("decision_engine."):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


def test_model_loader_preserves_source_registration_row_count() -> None:
    loader = importlib.import_module("decision_engine.model_loader")
    validate_model = loader.validate_model

    result = validate_model(
        "SourceRegistrationResult",
        {
            "source_id": "src_1",
            "dataset_id": "src_1",
            "name": "orders",
            "status": "already_registered",
            "schema": {"fields": ["order_id"], "row_count": 25},
            "row_count": 25,
        },
    )

    assert result.row_count == 25
