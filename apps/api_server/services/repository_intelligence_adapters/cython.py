from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    cython_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cython_primitives as primitives,
)

CYTHON_SUFFIXES = primitives.CYTHON_SUFFIXES
CYTHON_CONFIG_BASENAMES = frozenset()

strip_comments = primitives.strip_comments
has_cython_path_hints = primitives.has_cython_path_hints
is_probable_cython_source = primitives.is_probable_cython_source
include_statements = primitives.include_statements
import_statements = primitives.import_statements
iter_symbol_entries = primitives.iter_symbol_entries
module_name_from_path = primitives.module_name_from_path
module_aliases_for_path = analysis_support.module_aliases_for_path
resolve_import = analysis_support.resolve_import
resolve_include = analysis_support.resolve_include
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file

__all__ = [
    "CYTHON_CONFIG_BASENAMES",
    "CYTHON_SUFFIXES",
    "has_cython_path_hints",
    "import_statements",
    "include_statements",
    "is_probable_cython_source",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "resolve_include",
    "strip_comments",
]
