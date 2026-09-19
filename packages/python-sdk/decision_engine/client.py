# SPDX-License-Identifier: Apache-2.0

"""
Compatibility wrapper for the synchronous Algenta API client.

This module exposes the Cloud Managed path by default. In `self_hosted` and `air_gapped`,
pass an explicit self-hosted `base_url` and use the API key
provisioned by your self-hosted operator deployment instead. Private profiles
fail closed and do not silently fall back to Algenta cloud.
"""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "AlgentaClient": ("decision_engine.client_facade", "AlgentaClient"),
    "CodnaClient": ("decision_engine.client_facade", "CodnaClient"),
    "DecisionEngineClient": ("decision_engine.client_facade", "DecisionEngineClient"),
    "QueryFilterCondition": (
        "decision_engine.models_resolve_result",
        "QueryFilterCondition",
    ),
    "QueryFilterSpec": ("decision_engine.models_resolve_result", "QueryFilterSpec"),
    "DEFAULT_BASE_URL": ("decision_engine._contract", "DEFAULT_BASE_URL"),
    "CONTRACT_VERSION": ("decision_engine._contract", "CONTRACT_VERSION"),
    "BRAND": ("decision_engine._contract", "BRAND"),
    "MCP_ENDPOINT": ("decision_engine._contract", "MCP_ENDPOINT"),
    "MCP_TOOLS_ENDPOINT": ("decision_engine._contract", "MCP_TOOLS_ENDPOINT"),
    "AUTH_SCHEME": ("decision_engine._contract", "AUTH_SCHEME"),
    "API_KEY_PREFIX_LIVE": ("decision_engine._contract", "API_KEY_PREFIX_LIVE"),
    "API_KEY_PREFIX_TEST": ("decision_engine._contract", "API_KEY_PREFIX_TEST"),
    "LEGACY_HEADERS": ("decision_engine._contract", "LEGACY_HEADERS"),
    "LEGACY_ENV_VARS": ("decision_engine._contract", "LEGACY_ENV_VARS"),
    "LEGACY_DOMAINS": ("decision_engine._contract", "LEGACY_DOMAINS"),
    "VENDOR_TELEMETRY_HOSTS": ("decision_engine._contract", "VENDOR_TELEMETRY_HOSTS"),
    "PRIVATE_HOST_SUFFIXES": ("decision_engine._contract", "PRIVATE_HOST_SUFFIXES"),
    "DEPRECATION_WINDOW_DAYS": ("decision_engine._contract", "DEPRECATION_WINDOW_DAYS"),
    "READ_ONLY_DEFAULT": ("decision_engine._contract", "READ_ONLY_DEFAULT"),
    "WRITE_CONFIRMATION_REQUIRED": (
        "decision_engine._contract",
        "WRITE_CONFIRMATION_REQUIRED",
    ),
    "PLAN_LIMITS": ("decision_engine._contract", "PLAN_LIMITS"),
    "INTEGRATIONS": ("decision_engine._contract", "INTEGRATIONS"),
    "PRIMARY_DATA_QUERY_CONTRACT": (
        "decision_engine._contract",
        "PRIMARY_DATA_QUERY_CONTRACT",
    ),
    "CAPABILITY_PLANE_CONTRACT": (
        "decision_engine._contract",
        "CAPABILITY_PLANE_CONTRACT",
    ),
}

_CONTRACT_EXPORT_NAMES = tuple(
    name for name, export in _LAZY_EXPORTS.items() if export[0] == "decision_engine._contract"
)

__all__ = list(_LAZY_EXPORTS)


def _cache_available_exports(module_name: str, module) -> None:
    for export_name, export in _LAZY_EXPORTS.items():
        if export[0] != module_name:
            continue
        attribute_name = export[1]
        if hasattr(module, attribute_name):
            globals()[export_name] = getattr(module, attribute_name)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'decision_engine.client' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    if module_name == "decision_engine._contract":
        _cache_available_exports(module_name, module)
        value = getattr(module, attribute_name)
        globals()[name] = value
    else:
        _cache_available_exports(module_name, module)
        value = getattr(module, attribute_name)
        globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
