from __future__ import annotations

import re
from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    classic_visual_basic_support as repository_classic_visual_basic_support,
)

StableIdentifier = repository_classic_visual_basic_support.StableIdentifier
ResolveSuffixMatch = repository_classic_visual_basic_support.ResolveSuffixMatch
ResolveDirectoryPrefixMatch = (
    repository_classic_visual_basic_support.ResolveDirectoryPrefixMatch
)

RESERVED_SYMBOL_NAMES = repository_classic_visual_basic_support.RESERVED_SYMBOL_NAMES
BUILTIN_TYPE_NAMES = repository_classic_visual_basic_support.BUILTIN_TYPE_NAMES

strip_comments = repository_classic_visual_basic_support.strip_comments
normalize_target = repository_classic_visual_basic_support.normalize_target
normalize_symbol_name = repository_classic_visual_basic_support.normalize_symbol_name
component_name = repository_classic_visual_basic_support.component_name
collect_symbol_entries = repository_classic_visual_basic_support.collect_symbol_entries
module_aliases_for_path = repository_classic_visual_basic_support.module_aliases_for_path
resolve_target = repository_classic_visual_basic_support.resolve_target
parse_dependencies_only = repository_classic_visual_basic_support.parse_dependencies_only
parse_file = repository_classic_visual_basic_support.parse_file

_KNOWN_VBA_SUFFIXES = frozenset({".bas", ".cls", ".frm"})
_VBA_USERFORM_RE = re.compile(
    r"^\s*(?:VERSION\s+\d+\.\d+\s+)?Begin\s+\{[0-9A-Fa-f\-]{8,}\}\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)


def is_probable_vba_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_VBA_SUFFIXES:
        return False
    if not repository_classic_visual_basic_support.is_probable_classic_visual_basic_source(
        path=path,
        text=text,
    ):
        return False
    stripped_text = strip_comments(text)
    if suffix == ".frm":
        return _VBA_USERFORM_RE.search(text) is not None
    if repository_classic_visual_basic_support.BEGIN_COMPONENT_RE.search(stripped_text):
        return False
    return (
        repository_classic_visual_basic_support.ATTRIBUTE_VB_NAME_RE.search(stripped_text)
        is not None
    )
