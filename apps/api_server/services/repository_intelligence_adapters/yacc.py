from .yacc_analysis_support import (
    YACC_SUFFIXES,
    has_yacc_path_hints,
    is_probable_yacc_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "YACC_SUFFIXES",
    "has_yacc_path_hints",
    "is_probable_yacc_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
