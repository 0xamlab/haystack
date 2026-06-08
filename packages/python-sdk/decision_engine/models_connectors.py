"""Compatibility wrapper for connector and dataset SDK models."""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "ConnectorInfo": ("decision_engine.models_connector_info", "ConnectorInfo"),
    "ConnectorListResult": (
        "decision_engine.models_connector_list_result",
        "ConnectorListResult",
    ),
    "ConnectorTestInfo": ("decision_engine.models_connector_preview", "ConnectorTestInfo"),
    "ConnectorBrowseResult": ("decision_engine.models_connector_preview", "ConnectorBrowseResult"),
    "DatasetInfo": ("decision_engine.models_dataset", "DatasetInfo"),
    "DatasetListResult": ("decision_engine.models_dataset", "DatasetListResult"),
    "DatasetDetailResult": ("decision_engine.models_dataset", "DatasetDetailResult"),
    "DatasetSummaryResult": ("decision_engine.models_dataset", "DatasetSummaryResult"),
    "DatasetDeleteResult": ("decision_engine.models_dataset", "DatasetDeleteResult"),
    "DatasetConnectResult": ("decision_engine.models_dataset", "DatasetConnectResult"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(
            f"module 'decision_engine.models_connectors' has no attribute '{name}'"
        )
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
