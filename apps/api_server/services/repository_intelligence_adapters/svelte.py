from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.svelte_analysis_support import (
    SVELTE_ROUTE_BASENAMES,
    SVELTE_SUFFIXES,
    has_svelte_path_hints,
    is_probable_svelte_source,
    iter_component_references,
    iter_import_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
)
from apps.api_server.services.repository_intelligence_adapters.svelte_primitives import (
    normalize_identifier,
    strip_comments,
)

__all__ = [
    "SVELTE_ROUTE_BASENAMES",
    "SVELTE_SUFFIXES",
    "has_svelte_path_hints",
    "is_probable_svelte_source",
    "iter_component_references",
    "iter_import_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "strip_comments",
]
