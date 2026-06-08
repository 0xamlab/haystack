from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.astro_analysis_support import (
    ASTRO_SUFFIXES,
    has_astro_path_hints,
    is_probable_astro_source,
    iter_component_references,
    iter_import_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
)
from apps.api_server.services.repository_intelligence_adapters.astro_primitives import (
    normalize_identifier,
    strip_comments,
)

__all__ = [
    "ASTRO_SUFFIXES",
    "has_astro_path_hints",
    "is_probable_astro_source",
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
