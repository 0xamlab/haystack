from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.handlebars_analysis_support import (
    HANDLEBARS_SUFFIXES,
    collect_symbols,
    has_handlebars_path_hints,
    is_probable_handlebars_source,
    iter_dependency_entries,
    iter_reference_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
    source_symbol_name_for_line,
)
from apps.api_server.services.repository_intelligence_adapters.handlebars_primitives import (
    normalize_identifier,
    strip_comments,
)

__all__ = [
    "HANDLEBARS_SUFFIXES",
    "collect_symbols",
    "has_handlebars_path_hints",
    "is_probable_handlebars_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "source_symbol_name_for_line",
    "strip_comments",
]
