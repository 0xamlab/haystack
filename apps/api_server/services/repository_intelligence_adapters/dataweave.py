from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.dataweave_analysis_support import (
    DATAWEAVE_SUFFIXES,
    clean_import_target,
    has_dataweave_path_hints,
    is_probable_dataweave_source,
    iter_dependency_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
    strip_comments,
)

__all__ = [
    "DATAWEAVE_SUFFIXES",
    "clean_import_target",
    "has_dataweave_path_hints",
    "is_probable_dataweave_source",
    "iter_dependency_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "strip_comments",
]
