from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.apl_analysis_support import (
    APL_SUFFIXES,
    has_apl_path_hints,
    is_probable_apl_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    source_symbol_name_for_line,
    strip_comments,
)

__all__ = [
    "APL_SUFFIXES",
    "has_apl_path_hints",
    "is_probable_apl_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "source_symbol_name_for_line",
    "strip_comments",
]
