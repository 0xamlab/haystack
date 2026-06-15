from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.ats_analysis_support import (
    ATS_SUFFIXES,
    has_ats_path_hints,
    is_probable_ats_source,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_target,
)
from apps.api_server.services.repository_intelligence_adapters.ats_primitives import (
    iter_declared_symbol_entries,
    iter_dependency_entries,
    iter_reference_entries,
    path_aliases_for_file,
    strip_comments,
)

__all__ = [
    "ATS_SUFFIXES",
    "has_ats_path_hints",
    "is_probable_ats_source",
    "iter_declared_symbol_entries",
    "iter_dependency_entries",
    "iter_reference_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "path_aliases_for_file",
    "resolve_target",
    "strip_comments",
]
