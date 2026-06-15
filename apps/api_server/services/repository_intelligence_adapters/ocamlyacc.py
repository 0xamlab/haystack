from .ocamlyacc_analysis_support import (
    OCAMLYACC_SUFFIXES,
    has_ocamlyacc_path_hints,
    is_probable_ocamlyacc_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "OCAMLYACC_SUFFIXES",
    "has_ocamlyacc_path_hints",
    "is_probable_ocamlyacc_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
