from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.alloy_analysis_support import (
    ALLOY_SUFFIXES,
    has_alloy_path_hints,
    is_probable_alloy_source,
    iter_declared_symbol_entries,
    iter_reference_targets,
    module_aliases_for_path,
    module_declaration,
    normalize_module_name,
    open_statements,
    parse_dependencies_only,
    parse_file,
    path_aliases_for_file,
    resolve_target,
)

from apps.api_server.services.repository_intelligence_adapters.alloy_primitives import (
    _line_count,
    normalize_identifier,
    strip_comments,
)

__all__ = [
    "ALLOY_SUFFIXES",
    "_line_count",
    "has_alloy_path_hints",
    "is_probable_alloy_source",
    "iter_declared_symbol_entries",
    "iter_reference_targets",
    "module_aliases_for_path",
    "module_declaration",
    "normalize_identifier",
    "normalize_module_name",
    "open_statements",
    "parse_dependencies_only",
    "parse_file",
    "path_aliases_for_file",
    "resolve_target",
    "strip_comments",
]

