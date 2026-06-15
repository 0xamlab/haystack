from .xquery_analysis_support import (
    XQUERY_SUFFIXES,
    has_xquery_path_hints,
    is_probable_xquery_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "XQUERY_SUFFIXES",
    "has_xquery_path_hints",
    "is_probable_xquery_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
