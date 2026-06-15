from .templ_analysis_support import (
    TEMPL_SUFFIXES,
    has_templ_path_hints,
    is_probable_templ_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "TEMPL_SUFFIXES",
    "has_templ_path_hints",
    "is_probable_templ_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
