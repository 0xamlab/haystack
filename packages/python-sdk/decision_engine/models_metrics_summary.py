# SPDX-License-Identifier: Apache-2.0

"""Compatibility wrapper for metrics summary SDK model."""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "MetricsSummary": ("decision_engine.models_simulation_common", "MetricsSummary"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(
            f"module 'decision_engine.models_metrics_summary' has no attribute '{name}'"
        )
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
