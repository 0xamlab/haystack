from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_decision_engine_models_module_uses_lazy_domain_exports() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine" or module_name.startswith("decision_engine.")
    }
    for module_name in list(sys.modules):
        if module_name == "decision_engine" or module_name.startswith("decision_engine."):
            sys.modules.pop(module_name, None)

    try:
        models = importlib.import_module("decision_engine.models")

        assert "decision_engine.models_query_result" not in sys.modules
        assert "decision_engine.models_resolve_result" not in sys.modules
        assert "decision_engine.models_connector_info" not in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_decision_envelope" not in sys.modules
        assert "decision_engine.models_metrics_summary" not in sys.modules
        assert "decision_engine.models_percentile_summary" not in sys.modules
        assert "decision_engine.models_run_metadata" not in sys.modules
        assert "decision_engine.models_simulation_common" not in sys.modules
        assert "decision_engine.models_simulation" not in sys.modules
        assert "decision_engine.models_account" not in sys.modules

        query_result_cls = models.QueryResult

        assert query_result_cls.__name__ == "QueryResult"
        assert "decision_engine.models_query_result" in sys.modules
        assert "decision_engine.models_connector_info" not in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_decision_envelope" not in sys.modules
        assert "decision_engine.models_simulation" not in sys.modules
        assert "decision_engine.models_account" not in sys.modules

        connector_info_cls = models.ConnectorInfo
        envelope_cls = models.DecisionEnvelope

        assert connector_info_cls.__name__ == "ConnectorInfo"
        assert envelope_cls.__name__ == "DecisionEnvelope"
        assert "decision_engine.models_connector_info" in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_decision_envelope" in sys.modules
        assert "decision_engine.models_simulation_common" in sys.modules
        assert "decision_engine.models_metrics_summary" not in sys.modules
        assert "decision_engine.models_percentile_summary" not in sys.modules
        assert "decision_engine.models_run_metadata" not in sys.modules
        assert "decision_engine.models_simulation" not in sys.modules
        assert "decision_engine.models_account" not in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "decision_engine" or module_name.startswith("decision_engine."):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
