from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.groovy_analysis_support import (
    GROOVY_CONFIG_BASENAMES,
    GROOVY_SUFFIXES,
    IMPORT_RE,
    PACKAGE_RE,
    TYPE_DECL_RE,
    TYPE_REFERENCE_RE,
    extract_import_bindings,
    has_groovy_path_hints,
    is_probable_groovy_source,
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
)

__all__ = [
    "GROOVY_CONFIG_BASENAMES",
    "GROOVY_SUFFIXES",
    "IMPORT_RE",
    "PACKAGE_RE",
    "TYPE_DECL_RE",
    "TYPE_REFERENCE_RE",
    "extract_import_bindings",
    "has_groovy_path_hints",
    "is_probable_groovy_source",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
]
