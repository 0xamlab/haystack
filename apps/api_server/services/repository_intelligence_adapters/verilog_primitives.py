from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog_primitives as repository_systemverilog_primitives,
)

StableIdentifier = repository_systemverilog_primitives.StableIdentifier
NormalizeRepositoryRelativePath = (
    repository_systemverilog_primitives.NormalizeRepositoryRelativePath
)
ResolveSuffixMatch = repository_systemverilog_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = frozenset({".v", ".vh"})
_DIRECT_VERILOG_SUFFIXES = _KNOWN_SUFFIXES
_PATH_HINT_PARTS = frozenset({"dv", "hdl", "rtl", "sim", "tb", "testbench", "verilog"})
_PATH_HINT_BASENAMES = frozenset({"bender.yml", "bender.yaml", "fusesoc.conf"})
_PRIMARY_TOKEN_RE = repository_systemverilog_primitives._PRIMARY_TOKEN_RE
_ROUTINE_DECL_RE = repository_systemverilog_primitives._ROUTINE_DECL_RE
_INCLUDE_RE = repository_systemverilog_primitives._INCLUDE_RE
_IMPORT_RE = repository_systemverilog_primitives._IMPORT_RE
_IMPORT_ITEM_RE = repository_systemverilog_primitives._IMPORT_ITEM_RE
_QUALIFIED_REFERENCE_RE = repository_systemverilog_primitives._QUALIFIED_REFERENCE_RE
_INSTANTIATION_RE = repository_systemverilog_primitives._INSTANTIATION_RE
_RESERVED_REFERENCE_NAMES = repository_systemverilog_primitives._RESERVED_REFERENCE_NAMES
_END_TOKEN_TO_KIND = repository_systemverilog_primitives._END_TOKEN_TO_KIND
_PRIMARY_SYMBOL_KINDS = repository_systemverilog_primitives._PRIMARY_SYMBOL_KINDS
_ROUTINE_MODIFIERS = repository_systemverilog_primitives._ROUTINE_MODIFIERS

_PROBABLE_VERILOG_RE = re.compile(
    r"(?im)^\s*(?:"
    r"`(?:include|define|ifdef|ifndef|elsif|else|endif|timescale)\b|"
    r"module\s+[A-Za-z_][A-Za-z0-9_$]*\b|"
    r"endmodule\b|"
    r"(?:input|output|inout|wire|reg|assign|always|initial|parameter|localparam)\b"
    r")"
)
_SYSTEMVERILOG_ONLY_RE = re.compile(
    r"(?im)\b(?:"
    r"always_(?:comb|ff|latch)|"
    r"assert|bit|byte|class|clocking|covergroup|endclass|endinterface|endpackage|"
    r"endprogram|enum|final|int|interface|logic|package|program|property|"
    r"rand|randc|sequence|string|struct|typedef|union|unique|virtual"
    r")\b|::"
)

_normalize_repository_relative_path = (
    repository_systemverilog_primitives._normalize_repository_relative_path
)
strip_comments = repository_systemverilog_primitives.strip_comments
_line_number = repository_systemverilog_primitives._line_number
_normalized_path_aliases = repository_systemverilog_primitives._normalized_path_aliases
_collect_primary_symbols = repository_systemverilog_primitives._collect_primary_symbols
_routine_name_from_header = repository_systemverilog_primitives._routine_name_from_header
_containing_primary_symbol_id = (
    repository_systemverilog_primitives._containing_primary_symbol_id
)
_collect_routine_symbols = repository_systemverilog_primitives._collect_routine_symbols
_ordered_symbols = repository_systemverilog_primitives._ordered_symbols


def has_verilog_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    parts = {part.lower() for part in normalized_path.parts}
    if parts & _PATH_HINT_PARTS:
        return True
    return normalized_path.name.lower() in _PATH_HINT_BASENAMES


def is_probable_verilog_source(*, path: Path | PurePosixPath, text: str) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix not in _KNOWN_SUFFIXES:
        return False
    stripped_text = strip_comments(text)
    if _SYSTEMVERILOG_ONLY_RE.search(stripped_text):
        return False
    if _PROBABLE_VERILOG_RE.search(stripped_text):
        return True
    return has_verilog_path_hints(path)
