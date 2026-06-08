from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.modelica_analysis_support import (
    MODELICA_SUFFIXES,
    clean_import_target,
    declared_module_name_from_text,
    has_modelica_path_hints,
    imported_symbol_bindings,
    is_probable_modelica_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
    strip_comments,
)

__all__ = [
    "MODELICA_SUFFIXES",
    "clean_import_target",
    "declared_module_name_from_text",
    "has_modelica_path_hints",
    "imported_symbol_bindings",
    "is_probable_modelica_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "strip_comments",
]
