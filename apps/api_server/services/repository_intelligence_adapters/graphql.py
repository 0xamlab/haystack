from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.graphql_analysis_support import (
    GRAPHQL_SUFFIXES,
    has_graphql_path_hints,
    is_probable_graphql_source,
    iter_declared_symbol_entries,
    iter_import_entries,
    iter_reference_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    path_aliases_for_file,
    resolve_import,
    strip_comments,
)

__all__ = [
    "GRAPHQL_SUFFIXES",
    "has_graphql_path_hints",
    "is_probable_graphql_source",
    "iter_declared_symbol_entries",
    "iter_import_entries",
    "iter_reference_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "path_aliases_for_file",
    "resolve_import",
    "strip_comments",
]

