from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.vue_analysis_support import (
    VUE_SUFFIXES,
    collect_symbols,
    has_vue_path_hints,
    is_probable_vue_source,
    iter_import_entries,
    iter_template_component_references,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
)

__all__ = [
    "VUE_SUFFIXES",
    "collect_symbols",
    "has_vue_path_hints",
    "is_probable_vue_source",
    "iter_import_entries",
    "iter_template_component_references",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
]
