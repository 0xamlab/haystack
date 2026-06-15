from .xslt_analysis_support import (
    XSLT_SUFFIXES,
    has_xslt_path_hints,
    is_probable_xslt_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "XSLT_SUFFIXES",
    "has_xslt_path_hints",
    "is_probable_xslt_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
