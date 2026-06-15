from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    rescript_primitives as repository_rescript_primitives,
)

StableIdentifier = repository_rescript_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_rescript_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_rescript_primitives.ResolveSuffixMatch

REASONML_SUFFIXES = frozenset({".re", ".rei"})
REASONML_CONFIG_BASENAMES = frozenset()
_CollectedSymbol = repository_rescript_primitives._CollectedSymbol
_EXTERNAL_RE = repository_rescript_primitives._EXTERNAL_RE
_LET_RE = repository_rescript_primitives._LET_RE
_MODULE_ALIAS_RE = repository_rescript_primitives._MODULE_ALIAS_RE
_MODULE_DECL_RE = repository_rescript_primitives._MODULE_DECL_RE
_OPEN_RE = repository_rescript_primitives._OPEN_RE
_QUALIFIED_REFERENCE_RE = repository_rescript_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_rescript_primitives._RESERVED_SYMBOL_NAMES
_TYPE_RE = repository_rescript_primitives._TYPE_RE
_TYPE_REFERENCE_RE = repository_rescript_primitives._TYPE_REFERENCE_RE
_VALUE_REFERENCE_RE = repository_rescript_primitives._VALUE_REFERENCE_RE
_CALL_RE = repository_rescript_primitives._CALL_RE
_line_count = repository_rescript_primitives._line_count
_line_number = repository_rescript_primitives._line_number
_looks_binaryish = repository_rescript_primitives._looks_binaryish
iter_symbol_entries = repository_rescript_primitives.iter_symbol_entries
module_name_from_path = repository_rescript_primitives.module_name_from_path
strip_comments = repository_rescript_primitives.strip_comments


def has_reasonml_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in REASONML_SUFFIXES


def is_probable_reasonml_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in REASONML_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    return bool(
        _OPEN_RE.search(stripped_text)
        or _MODULE_ALIAS_RE.search(stripped_text)
        or _MODULE_DECL_RE.search(stripped_text)
        or _TYPE_RE.search(stripped_text)
        or _LET_RE.search(stripped_text)
        or _EXTERNAL_RE.search(stripped_text)
    )


def is_probable_reasonml_config(*, path: Path | PurePosixPath, text: str) -> bool:
    return False
