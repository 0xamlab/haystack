from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.onec_enterprise_analysis_support import (
    ONEC_ENTERPRISE_SUFFIXES,
    has_onec_enterprise_path_hints,
    import_targets_for_text,
    is_probable_onec_enterprise_source,
    iter_declared_symbol_entries,
    iter_reference_targets,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
    resolve_target,
)

__all__ = [
    "ONEC_ENTERPRISE_SUFFIXES",
    "has_onec_enterprise_path_hints",
    "import_targets_for_text",
    "is_probable_onec_enterprise_source",
    "iter_declared_symbol_entries",
    "iter_reference_targets",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_target",
]

