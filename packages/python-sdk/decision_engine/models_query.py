"""Compatibility wrapper for query/result SDK models."""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "QueryCandidate": ("decision_engine.models_query_result", "QueryCandidate"),
    "QueryBatchResult": ("decision_engine.models_query_metadata", "QueryBatchResult"),
    "QueryExecutionMetadata": ("decision_engine.models_query_metadata", "QueryExecutionMetadata"),
    "QueryResult": ("decision_engine.models_query_result", "QueryResult"),
    "QuerySqlReportResult": ("decision_engine.models_query_metadata", "QuerySqlReportResult"),
    "QueryWithMetadataResult": (
        "decision_engine.models_query_metadata",
        "QueryWithMetadataResult",
    ),
    "ResolvedPlan": ("decision_engine.models_resolve_result", "ResolvedPlan"),
    "ResolveResult": ("decision_engine.models_resolve_result", "ResolveResult"),
    "VerifyResult": ("decision_engine.models_verify_result", "VerifyResult"),
    "SourceRegistrationResult": (
        "decision_engine.models_registration_result",
        "SourceRegistrationResult",
    ),
    "ExplainResult": ("decision_engine.models_explain_result", "ExplainResult"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'decision_engine.models_query' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
