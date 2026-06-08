from __future__ import annotations

from importlib import import_module

from .sdk_defaults import (
    DEFAULT_JOIN_PATH_HOPS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    MAX_JOIN_PATH_HOPS,
)

_LAZY_EXPORTS = {
    "_build_explain_result": ("decision_engine.request_explain_helpers", "_build_explain_result"),
    "_merge_request_payload": ("decision_engine.request_query_helpers", "_merge_request_payload"),
    "_normalize_compare_request": (
        "decision_engine.request_simulation_helpers",
        "_normalize_compare_request",
    ),
    "_normalize_expert_variable": (
        "decision_engine.request_simulation_helpers",
        "_normalize_expert_variable",
    ),
    "_normalize_query_like_request": (
        "decision_engine.request_query_helpers",
        "_normalize_query_like_request",
    ),
    "_normalize_recommend_request": (
        "decision_engine.request_simulation_helpers",
        "_normalize_recommend_request",
    ),
    "_normalize_simulation_request": (
        "decision_engine.request_simulation_helpers",
        "_normalize_simulation_request",
    ),
    "_normalize_source_registration_request": (
        "decision_engine.request_source_helpers",
        "_normalize_source_registration_request",
    ),
    "_request_source_set": ("decision_engine.request_query_helpers", "_request_source_set"),
    "_split_resolved_sources": ("decision_engine.request_query_helpers", "_split_resolved_sources"),
    "_strip_none": ("decision_engine.request_common", "_strip_none"),
}

__all__ = [
    "DEFAULT_JOIN_PATH_HOPS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT",
    "MAX_JOIN_PATH_HOPS",
] + list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'decision_engine.request_helpers' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
