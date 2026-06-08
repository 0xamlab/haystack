from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    squirrel_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    squirrel_primitives as primitives,
)

SQUIRREL_SUFFIXES = primitives.SQUIRREL_SUFFIXES

strip_comments = primitives.strip_comments
has_squirrel_path_hints = primitives.has_squirrel_path_hints
is_probable_squirrel_source = primitives.is_probable_squirrel_source
import_statements = primitives.import_statements
iter_symbol_entries = primitives.iter_symbol_entries
module_name_from_path = primitives.module_name_from_path
module_aliases_for_path = analysis_support.module_aliases_for_path
resolve_include = analysis_support.resolve_include
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file

__all__ = [
    "SQUIRREL_SUFFIXES",
    "has_squirrel_path_hints",
    "import_statements",
    "is_probable_squirrel_source",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_include",
    "strip_comments",
]
