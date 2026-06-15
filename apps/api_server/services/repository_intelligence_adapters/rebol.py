from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.rebol_analysis_support import (
    REBOL_SUFFIXES,
    UNAMBIGUOUS_REBOL_SUFFIXES,
    candidate_module_keys,
    clean_import_target,
    has_rebol_path_hints,
    is_probable_rebol_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import_module,
    source_symbol_name_for_line,
    strip_comments,
)

__all__ = [
    "REBOL_SUFFIXES",
    "UNAMBIGUOUS_REBOL_SUFFIXES",
    "candidate_module_keys",
    "clean_import_target",
    "has_rebol_path_hints",
    "is_probable_rebol_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import_module",
    "source_symbol_name_for_line",
    "strip_comments",
]
