from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.freemarker_analysis_support import (
    FREEMARKER_SUFFIXES,
    has_freemarker_path_hints,
    imported_symbol_bindings,
    is_probable_freemarker_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
    source_symbol_name_for_line,
)
from apps.api_server.services.repository_intelligence_adapters.freemarker_primitives import (
    normalize_identifier,
    strip_comments,
)

__all__ = [
    "FREEMARKER_SUFFIXES",
    "has_freemarker_path_hints",
    "imported_symbol_bindings",
    "is_probable_freemarker_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "source_symbol_name_for_line",
    "strip_comments",
]
