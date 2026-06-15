from .thrift_analysis_support import (
    THRIFT_SUFFIXES,
    has_thrift_path_hints,
    is_probable_thrift_source,
    iter_import_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "THRIFT_SUFFIXES",
    "has_thrift_path_hints",
    "is_probable_thrift_source",
    "iter_import_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
