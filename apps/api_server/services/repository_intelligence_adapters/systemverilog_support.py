from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog_analysis_support as repository_systemverilog_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog_primitives as repository_systemverilog_primitives,
)

StableIdentifier = repository_systemverilog_primitives.StableIdentifier
NormalizeRepositoryRelativePath = (
    repository_systemverilog_primitives.NormalizeRepositoryRelativePath
)
ResolveSuffixMatch = repository_systemverilog_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_systemverilog_primitives._KNOWN_SUFFIXES
_DIRECT_SYSTEMVERILOG_SUFFIXES = (
    repository_systemverilog_primitives._DIRECT_SYSTEMVERILOG_SUFFIXES
)
_AMBIGUOUS_SYSTEMVERILOG_SUFFIXES = (
    repository_systemverilog_primitives._AMBIGUOUS_SYSTEMVERILOG_SUFFIXES
)
_PATH_HINT_PARTS = repository_systemverilog_primitives._PATH_HINT_PARTS
_PATH_HINT_BASENAMES = repository_systemverilog_primitives._PATH_HINT_BASENAMES
_PRIMARY_TOKEN_RE = repository_systemverilog_primitives._PRIMARY_TOKEN_RE
_ROUTINE_DECL_RE = repository_systemverilog_primitives._ROUTINE_DECL_RE
_INCLUDE_RE = repository_systemverilog_primitives._INCLUDE_RE
_IMPORT_RE = repository_systemverilog_primitives._IMPORT_RE
_IMPORT_ITEM_RE = repository_systemverilog_primitives._IMPORT_ITEM_RE
_QUALIFIED_REFERENCE_RE = repository_systemverilog_primitives._QUALIFIED_REFERENCE_RE
_INSTANTIATION_RE = repository_systemverilog_primitives._INSTANTIATION_RE
_PROBABLE_SYSTEMVERILOG_RE = (
    repository_systemverilog_primitives._PROBABLE_SYSTEMVERILOG_RE
)
_RESERVED_REFERENCE_NAMES = (
    repository_systemverilog_primitives._RESERVED_REFERENCE_NAMES
)
_END_TOKEN_TO_KIND = repository_systemverilog_primitives._END_TOKEN_TO_KIND
_PRIMARY_SYMBOL_KINDS = repository_systemverilog_primitives._PRIMARY_SYMBOL_KINDS
_ROUTINE_MODIFIERS = repository_systemverilog_primitives._ROUTINE_MODIFIERS

_normalize_repository_relative_path = (
    repository_systemverilog_primitives._normalize_repository_relative_path
)
strip_comments = repository_systemverilog_primitives.strip_comments
has_systemverilog_path_hints = (
    repository_systemverilog_primitives.has_systemverilog_path_hints
)
is_probable_systemverilog_source = (
    repository_systemverilog_primitives.is_probable_systemverilog_source
)
_line_number = repository_systemverilog_primitives._line_number
_normalized_path_aliases = (
    repository_systemverilog_primitives._normalized_path_aliases
)
_collect_primary_symbols = (
    repository_systemverilog_primitives._collect_primary_symbols
)
_routine_name_from_header = (
    repository_systemverilog_primitives._routine_name_from_header
)
_containing_primary_symbol_id = (
    repository_systemverilog_primitives._containing_primary_symbol_id
)
_collect_routine_symbols = (
    repository_systemverilog_primitives._collect_routine_symbols
)
_ordered_symbols = repository_systemverilog_primitives._ordered_symbols

module_aliases_for_path = (
    repository_systemverilog_analysis_support.module_aliases_for_path
)
_resolve_symbol_target = (
    repository_systemverilog_analysis_support._resolve_symbol_target
)
_resolve_include_target = (
    repository_systemverilog_analysis_support._resolve_include_target
)
_iter_import_targets = repository_systemverilog_analysis_support._iter_import_targets
_dependency_key = repository_systemverilog_analysis_support._dependency_key
parse_dependencies_only = (
    repository_systemverilog_analysis_support.parse_dependencies_only
)
_reference_candidates_for_symbol = (
    repository_systemverilog_analysis_support._reference_candidates_for_symbol
)
parse_file = repository_systemverilog_analysis_support.parse_file
