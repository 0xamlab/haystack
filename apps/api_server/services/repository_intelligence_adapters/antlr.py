from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.antlr_analysis_support import (
    ANTLR_INDEX_BASENAMES,
    ANTLR_SUFFIXES,
    collect_symbols,
    grammar_name_from_text,
    has_antlr_path_hints,
    is_probable_antlr_source,
    iter_dependency_entries,
    iter_reference_entries,
    iter_rule_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    resolve_import,
)

__all__ = [
    "ANTLR_INDEX_BASENAMES",
    "ANTLR_SUFFIXES",
    "collect_symbols",
    "grammar_name_from_text",
    "has_antlr_path_hints",
    "is_probable_antlr_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_rule_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
]

