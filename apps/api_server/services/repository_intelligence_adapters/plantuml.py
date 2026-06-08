from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.plantuml_analysis_support import (
    PLANTUML_SUFFIXES,
    clean_import_target,
    collect_symbols,
    has_plantuml_path_hints,
    is_probable_plantuml_source,
    iter_arrow_entries,
    iter_dependency_entries,
    iter_macro_reference_entries,
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
    "PLANTUML_SUFFIXES",
    "clean_import_target",
    "collect_symbols",
    "has_plantuml_path_hints",
    "is_probable_plantuml_source",
    "iter_arrow_entries",
    "iter_dependency_entries",
    "iter_macro_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "source_symbol_name_for_line",
    "strip_comments",
]
