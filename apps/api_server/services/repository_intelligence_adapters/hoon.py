from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.hoon_analysis_support import (
    HOON_SUFFIXES,
    has_hoon_path_hints,
    is_probable_hoon_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    normalize_identifier,
    parse_dependencies_only,
    parse_file,
    resolve_import_module,
    source_symbol_name_for_line,
    strip_comments,
)

__all__ = [
    "HOON_SUFFIXES",
    "has_hoon_path_hints",
    "is_probable_hoon_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import_module",
    "source_symbol_name_for_line",
    "strip_comments",
]
