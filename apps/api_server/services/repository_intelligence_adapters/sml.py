from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.sml_analysis_support import (
    SML_SUFFIXES,
    collect_symbol_entries,
    declared_module_names,
    has_sml_path_hints,
    is_probable_sml_source,
    module_aliases_for_path,
    normalize_symbol_name,
    normalize_target,
    parse_dependencies_only,
    parse_file,
    resolve_import,
    strip_comments,
)

__all__ = [
    "SML_SUFFIXES",
    "collect_symbol_entries",
    "declared_module_names",
    "has_sml_path_hints",
    "is_probable_sml_source",
    "module_aliases_for_path",
    "normalize_symbol_name",
    "normalize_target",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "strip_comments",
]
