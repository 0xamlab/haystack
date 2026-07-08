from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "ConnectorMetadata": (
        "algenta.runtime_connector_model_metadata",
        "ConnectorMetadata",
    ),
    "ConnectorTestOutput": (
        "algenta.runtime_connector_model_preview",
        "ConnectorTestOutput",
    ),
    "ConnectorBrowseOutput": (
        "algenta.runtime_connector_model_preview",
        "ConnectorBrowseOutput",
    ),
    "DatasetSummary": ("algenta.runtime_connector_model_dataset", "DatasetSummary"),
    "DatasetDetail": ("algenta.runtime_connector_model_dataset", "DatasetDetail"),
    "DatasetDeleteOutput": (
        "algenta.runtime_connector_model_dataset",
        "DatasetDeleteOutput",
    ),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'algenta.runtime_connector_models' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
