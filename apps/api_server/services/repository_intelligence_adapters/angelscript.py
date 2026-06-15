from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.angelscript_analysis_support import (
    ANGELSCRIPT_SUFFIXES,
    collect_symbols,
    has_angelscript_path_hints,
    is_probable_angelscript_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    normalize_symbol_name,
    parse_dependencies_only,
    parse_file,
    resolve_include,
    resolve_named_target,
    source_symbol_name_for_line,
    strip_comments,
)

__all__ = [
    "ANGELSCRIPT_SUFFIXES",
    "collect_symbols",
    "has_angelscript_path_hints",
    "is_probable_angelscript_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_symbol_name",
    "parse_dependencies_only",
    "parse_file",
    "resolve_include",
    "resolve_named_target",
    "source_symbol_name_for_line",
    "strip_comments",
]
