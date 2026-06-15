from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.jsonnet_analysis_support import (
    JSONNET_SUFFIXES,
    clean_import_target,
    has_jsonnet_path_hints,
    is_probable_jsonnet_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
    source_symbol_name_for_line,
    strip_comments,
)

__all__ = [
    "JSONNET_SUFFIXES",
    "clean_import_target",
    "has_jsonnet_path_hints",
    "is_probable_jsonnet_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "source_symbol_name_for_line",
    "strip_comments",
]
