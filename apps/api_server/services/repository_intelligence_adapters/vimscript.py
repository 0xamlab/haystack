from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.vimscript_analysis_support import (
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
)
from apps.api_server.services.repository_intelligence_adapters.vimscript_primitives import (
    autoload_target_for_name,
    has_vimscript_path_hints,
    is_probable_vimscript_source,
    iter_reference_names,
    iter_source_statements,
    iter_symbol_entries,
    module_name_from_path,
    normalize_identifier,
    strip_comments,
)

__all__ = [
    "autoload_target_for_name",
    "has_vimscript_path_hints",
    "is_probable_vimscript_source",
    "iter_reference_names",
    "iter_source_statements",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "strip_comments",
]
