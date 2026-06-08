from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.haxe_analysis_support import (
    has_haxe_path_hints,
    import_statements,
    imported_symbol_bindings,
    is_probable_haxe_source,
    module_aliases_for_path,
    module_name_for_file,
    parse_dependencies_only,
    parse_file,
    resolve_import,
)
from apps.api_server.services.repository_intelligence_adapters.haxe_primitives import (
    collect_symbols,
    iter_symbol_entries,
    package_name_from_text,
    strip_comments,
)

__all__ = [
    "collect_symbols",
    "has_haxe_path_hints",
    "import_statements",
    "imported_symbol_bindings",
    "is_probable_haxe_source",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_for_file",
    "package_name_from_text",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "strip_comments",
]
