from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_runtime_connector_models_wrapper_loads_leaf_modules_lazily() -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "algenta.runtime_connector_models"
        or module_name.startswith("algenta.runtime_connector_model_")
    }
    for module_name in list(sys.modules):
        if module_name == "algenta.runtime_connector_models" or module_name.startswith(
            "algenta.runtime_connector_model_"
        ):
            sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module("algenta.runtime_connector_models")

        assert "algenta.runtime_connector_model_metadata" not in sys.modules
        assert "algenta.runtime_connector_model_preview" not in sys.modules
        assert "algenta.runtime_connector_model_dataset" not in sys.modules

        connector_metadata_cls = module.ConnectorMetadata

        assert connector_metadata_cls.__name__ == "ConnectorMetadata"
        assert "algenta.runtime_connector_models" in sys.modules
        assert "algenta.runtime_connector_model_common" in sys.modules
        assert "algenta.runtime_connector_model_metadata" in sys.modules
        assert "algenta.runtime_connector_model_preview" not in sys.modules
        assert "algenta.runtime_connector_model_dataset" not in sys.modules

        dataset_summary_cls = module.DatasetSummary

        assert dataset_summary_cls.__name__ == "DatasetSummary"
        assert "algenta.runtime_connector_model_dataset" in sys.modules
        assert "algenta.runtime_connector_model_preview" not in sys.modules
    finally:
        for module_name in list(sys.modules):
            if module_name == "algenta.runtime_connector_models" or module_name.startswith(
                "algenta.runtime_connector_model_"
            ):
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
