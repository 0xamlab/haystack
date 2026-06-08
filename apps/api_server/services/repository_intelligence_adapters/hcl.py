from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.hcl_analysis_support import (
    extract_import_bindings,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
    resolve_module_source,
)
from apps.api_server.services.repository_intelligence_adapters.hcl_primitives import (
    has_hcl_path_hints,
    is_probable_hcl_source,
    iter_block_entries,
    iter_local_assignments,
    iter_module_source_statements,
    module_name_from_path,
    strip_comments,
)

__all__ = [
    "extract_import_bindings",
    "has_hcl_path_hints",
    "is_probable_hcl_source",
    "iter_block_entries",
    "iter_local_assignments",
    "iter_module_source_statements",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_module_source",
    "strip_comments",
]
