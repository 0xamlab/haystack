from .vcl_analysis_support import (
    VCL_SUFFIXES,
    has_vcl_path_hints,
    is_probable_vcl_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    strip_comments,
)

__all__ = [
    "VCL_SUFFIXES",
    "has_vcl_path_hints",
    "is_probable_vcl_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "strip_comments",
]
