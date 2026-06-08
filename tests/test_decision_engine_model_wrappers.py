from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_models_query_wrapper_loads_leaf_modules_lazily() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine" or module_name.startswith("decision_engine.")
    }
    for module_name in list(sys.modules):
        if module_name == "decision_engine" or module_name.startswith("decision_engine."):
            sys.modules.pop(module_name, None)

    try:
        wrapper = importlib.import_module("decision_engine.models_query")

        assert "decision_engine.models_query_result" not in sys.modules
        assert "decision_engine.models_resolve_result" not in sys.modules

        query_result_cls = wrapper.QueryResult
        resolve_result_cls = wrapper.ResolveResult

        assert query_result_cls.__name__ == "QueryResult"
        assert resolve_result_cls.__name__ == "ResolveResult"
        assert "decision_engine.models_query_result" in sys.modules
        assert "decision_engine.models_resolve_result" in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "decision_engine" or module_name.startswith("decision_engine."):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


def test_models_connectors_wrapper_loads_leaf_modules_lazily() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine" or module_name.startswith("decision_engine.")
    }
    for module_name in list(sys.modules):
        if module_name == "decision_engine" or module_name.startswith("decision_engine."):
            sys.modules.pop(module_name, None)

    try:
        wrapper = importlib.import_module("decision_engine.models_connectors")

        assert "decision_engine.models_connector_info" not in sys.modules
        assert "decision_engine.models_connector_list_result" not in sys.modules
        assert "decision_engine.models_connector_preview" not in sys.modules
        assert "decision_engine.models_dataset" not in sys.modules

        connector_cls = wrapper.ConnectorInfo
        connector_list_cls = wrapper.ConnectorListResult
        browse_cls = wrapper.ConnectorBrowseResult
        dataset_cls = wrapper.DatasetInfo

        assert connector_cls.__name__ == "ConnectorInfo"
        assert connector_list_cls.__name__ == "ConnectorListResult"
        assert browse_cls.__name__ == "ConnectorBrowseResult"
        assert dataset_cls.__name__ == "DatasetInfo"
        assert "decision_engine.models_connector_info" in sys.modules
        assert "decision_engine.models_connector_list_result" in sys.modules
        assert "decision_engine.models_connector_preview" in sys.modules
        assert "decision_engine.models_dataset" in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "decision_engine" or module_name.startswith("decision_engine."):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


def test_models_simulation_wrapper_loads_leaf_modules_lazily() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine" or module_name.startswith("decision_engine.")
    }
    for module_name in list(sys.modules):
        if module_name == "decision_engine" or module_name.startswith("decision_engine."):
            sys.modules.pop(module_name, None)

    try:
        wrapper = importlib.import_module("decision_engine.models_simulation")

        assert "decision_engine.models_metrics_summary" not in sys.modules
        assert "decision_engine.models_percentile_summary" not in sys.modules
        assert "decision_engine.models_run_metadata" not in sys.modules
        assert "decision_engine.models_simulation_common" not in sys.modules
        assert "decision_engine.models_decision_envelope" not in sys.modules
        assert "decision_engine.models_batch_result" not in sys.modules

        envelope_cls = wrapper.DecisionEnvelope
        batch_cls = wrapper.BatchResult

        assert envelope_cls.__name__ == "DecisionEnvelope"
        assert batch_cls.__name__ == "BatchResult"
        assert "decision_engine.models_decision_envelope" in sys.modules
        assert "decision_engine.models_simulation_common" in sys.modules
        assert "decision_engine.models_metrics_summary" not in sys.modules
        assert "decision_engine.models_percentile_summary" not in sys.modules
        assert "decision_engine.models_run_metadata" not in sys.modules
        assert "decision_engine.models_batch_result" in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "decision_engine" or module_name.startswith("decision_engine."):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
