from .nsis_analysis_support import (
    NSIS_SUFFIXES,
    has_nsis_path_hints,
    is_probable_nsis_source,
    iter_dependency_entries,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)

__all__ = [
    "NSIS_SUFFIXES",
    "has_nsis_path_hints",
    "is_probable_nsis_source",
    "iter_dependency_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]
