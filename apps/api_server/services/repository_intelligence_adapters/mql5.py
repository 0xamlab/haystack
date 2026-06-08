from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.mql5_analysis_support import (
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
)
from apps.api_server.services.repository_intelligence_adapters.mql5_primitives import (
    collect_symbol_entries,
    has_mql5_path_hints,
    import_targets_for_text,
    is_probable_mql5_source,
    module_symbol_name,
    normalize_identifier,
    normalize_import_target,
    project_file_entries,
    strip_comments,
)

__all__ = [
    "strip_comments",
    "has_mql5_path_hints",
    "is_probable_mql5_source",
    "normalize_identifier",
    "normalize_import_target",
    "module_symbol_name",
    "import_targets_for_text",
    "project_file_entries",
    "collect_symbol_entries",
    "module_aliases_for_path",
    "resolve_import",
    "parse_dependencies_only",
    "parse_file",
]
