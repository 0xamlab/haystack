from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    stan_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    stan_primitives as primitives,
)

STAN_SUFFIXES = primitives.STAN_SUFFIXES
STAN_CONFIG_BASENAMES = frozenset()

strip_comments = primitives.strip_comments
has_stan_path_hints = primitives.has_stan_path_hints
is_probable_stan_source = primitives.is_probable_stan_source
include_statements = primitives.include_statements
iter_symbol_entries = primitives.iter_symbol_entries
module_name_from_path = primitives.module_name_from_path
module_aliases_for_path = analysis_support.module_aliases_for_path
resolve_include = analysis_support.resolve_include
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file

__all__ = [
    "STAN_CONFIG_BASENAMES",
    "STAN_SUFFIXES",
    "has_stan_path_hints",
    "include_statements",
    "is_probable_stan_source",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_include",
    "strip_comments",
]
