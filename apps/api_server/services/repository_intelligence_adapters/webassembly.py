from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.webassembly_analysis_support import (
    WEBASSEMBLY_SUFFIXES,
    has_webassembly_path_hints,
    is_probable_webassembly_source,
    iter_declared_symbol_entries,
    iter_import_entries,
    iter_reference_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    path_aliases_for_file,
    strip_comments,
)

__all__ = [
    "WEBASSEMBLY_SUFFIXES",
    "has_webassembly_path_hints",
    "is_probable_webassembly_source",
    "iter_declared_symbol_entries",
    "iter_import_entries",
    "iter_reference_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "path_aliases_for_file",
    "strip_comments",
]

