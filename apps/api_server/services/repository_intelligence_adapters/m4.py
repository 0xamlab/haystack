from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.m4_analysis_support import (
    M4_SUFFIXES,
    clean_include_target,
    has_m4_path_hints,
    is_probable_m4_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_include,
    source_symbol_name_for_line,
    strip_comments,
)

__all__ = [
    "M4_SUFFIXES",
    "clean_include_target",
    "has_m4_path_hints",
    "is_probable_m4_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_include",
    "source_symbol_name_for_line",
    "strip_comments",
]
