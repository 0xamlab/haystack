"""
algenta.map — compatibility wrapper for local mapping and query helpers.
"""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "FieldMapping": ("algenta.map_models", "FieldMapping"),
    "MapResult": ("algenta.map_models", "MapResult"),
    "map_data": ("algenta.map_matching", "map_data"),
    "query_data": ("algenta.map_query", "query_data"),
    "_normalize": ("algenta.map_matching", "_normalize"),
    "_semantic_similarity": ("algenta.map_matching", "_semantic_similarity"),
    "_profile_field": ("algenta.map_matching", "_profile_field"),
    "_stat_similarity": ("algenta.map_matching", "_stat_similarity"),
    "_parse_source": ("algenta.map_parsing", "_parse_source"),
    "_source_name": ("algenta.map_parsing", "_source_name"),
    "_AGG_KEYWORDS": ("algenta.map_query", "_AGG_KEYWORDS"),
    "_METRIC_SYNONYMS": ("algenta.map_query", "_METRIC_SYNONYMS"),
    "_is_numeric_field": ("algenta.map_query", "_is_numeric_field"),
    "_execute": ("algenta.map_query", "_execute"),
    "_agg": ("algenta.map_query", "_agg"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'algenta.map' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
