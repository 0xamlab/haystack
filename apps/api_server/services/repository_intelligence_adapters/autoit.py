from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    autoit_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    autoit_primitives as primitives,
)

strip_comments = primitives.strip_comments
has_autoit_path_hints = primitives.has_autoit_path_hints
is_probable_autoit_source = primitives.is_probable_autoit_source
import_statements = primitives.import_statements
iter_symbol_entries = primitives.iter_symbol_entries
module_aliases_for_path = analysis_support.module_aliases_for_path
resolve_include = analysis_support.resolve_include
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file

__all__ = [
    "has_autoit_path_hints",
    "import_statements",
    "is_probable_autoit_source",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_include",
    "strip_comments",
]
