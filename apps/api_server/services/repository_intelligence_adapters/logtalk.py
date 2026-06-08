from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.logtalk_analysis_support import (
    extract_import_bindings,
    has_logtalk_markers,
    has_logtalk_path_hints,
    is_probable_logtalk_source,
    module_aliases_for_path,
    module_name_from_path,
    module_name_from_text,
    parse_dependencies_only,
    parse_file,
    parse_load_statements,
    parse_reference_targets,
    parse_relation_statements,
    parse_uses_statements,
    resolve_import,
    resolve_target,
    strip_comments,
)
from apps.api_server.services.repository_intelligence_adapters.logtalk_primitives import (
    iter_symbol_entries,
)

__all__ = [
    "extract_import_bindings",
    "has_logtalk_markers",
    "has_logtalk_path_hints",
    "is_probable_logtalk_source",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "module_name_from_text",
    "parse_dependencies_only",
    "parse_file",
    "parse_load_statements",
    "parse_reference_targets",
    "parse_relation_statements",
    "parse_uses_statements",
    "resolve_import",
    "resolve_target",
    "strip_comments",
]
