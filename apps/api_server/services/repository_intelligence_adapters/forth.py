from .forth_analysis_support import (
    FORTH_SUFFIXES,
    has_forth_path_hints,
    is_probable_forth_source,
    iter_dependency_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "FORTH_SUFFIXES",
    "has_forth_path_hints",
    "is_probable_forth_source",
    "iter_dependency_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
