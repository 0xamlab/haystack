from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.metal_analysis_support import (
    METAL_SUFFIXES,
    candidate_module_keys,
    has_metal_path_hints,
    is_probable_metal_source,
    module_aliases_for_path,
    module_name_from_path,
    normalize_symbol_name,
    parse_dependencies_only,
    parse_file,
    resolve_include,
    strip_comments,
)

__all__ = [
    "METAL_SUFFIXES",
    "candidate_module_keys",
    "has_metal_path_hints",
    "is_probable_metal_source",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_symbol_name",
    "parse_dependencies_only",
    "parse_file",
    "resolve_include",
    "strip_comments",
]
