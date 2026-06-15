from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.plpgsql_analysis_support import (
    PLPGSQL_SUFFIXES,
    has_plpgsql_path_hints,
    is_probable_plpgsql_source,
    module_aliases_for_path,
    normalize_identifier,
    parse_dependencies_only,
    parse_file,
    resolve_import,
    resolve_target,
    strip_comments,
    symbol_name_parts,
)

__all__ = [
    "PLPGSQL_SUFFIXES",
    "has_plpgsql_path_hints",
    "is_probable_plpgsql_source",
    "module_aliases_for_path",
    "normalize_identifier",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "resolve_target",
    "strip_comments",
    "symbol_name_parts",
]
