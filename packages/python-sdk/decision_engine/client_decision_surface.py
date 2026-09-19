# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "batch": ("decision_engine.client_simulation_surface", "batch"),
    "compare": ("decision_engine.client_simulation_surface", "compare"),
    "explain": ("decision_engine.client_query_surface", "explain"),
    "plan_decision": ("decision_engine.client_decision_plan_surface", "plan_decision"),
    "query": ("decision_engine.client_query_surface", "query"),
    "recommend": ("decision_engine.client_simulation_surface", "recommend"),
    "refresh_source": ("decision_engine.client_source_surface", "refresh_source"),
    "register_source": ("decision_engine.client_source_surface", "register_source"),
    "resolve": ("decision_engine.client_query_surface", "resolve"),
    "score": ("decision_engine.client_simulation_surface", "score"),
    "simulate": ("decision_engine.client_simulation_surface", "simulate"),
    "verify": ("decision_engine.client_query_surface", "verify"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(
            f"module 'decision_engine.client_decision_surface' has no attribute '{name}'"
        )
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
