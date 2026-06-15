from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.abapcds_analysis_support import (
    ABAPCDS_DECL_RE,
    ABAPCDS_SUFFIXES,
    ASSOCIATION_TO_RE,
    PROJECTION_ON_RE,
    SELECT_FROM_RE,
    has_abapcds_path_hints,
    is_probable_abapcds_source,
    iter_declared_type_entries,
    iter_reference_targets,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
    resolve_target,
)

__all__ = [
    "ABAPCDS_DECL_RE",
    "ABAPCDS_SUFFIXES",
    "ASSOCIATION_TO_RE",
    "PROJECTION_ON_RE",
    "SELECT_FROM_RE",
    "has_abapcds_path_hints",
    "is_probable_abapcds_source",
    "iter_declared_type_entries",
    "iter_reference_targets",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_target",
]
