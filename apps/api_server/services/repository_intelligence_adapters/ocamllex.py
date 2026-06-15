from .ocamllex_analysis_support import (
    OCAMLLEX_SUFFIXES,
    has_ocamllex_path_hints,
    is_probable_ocamllex_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_symbol_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "OCAMLLEX_SUFFIXES",
    "has_ocamllex_path_hints",
    "is_probable_ocamllex_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
