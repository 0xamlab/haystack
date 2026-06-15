from .lex_analysis_support import (
    LEX_SUFFIXES,
    has_lex_path_hints,
    is_probable_lex_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "LEX_SUFFIXES",
    "has_lex_path_hints",
    "is_probable_lex_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
