from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    classic_visual_basic_support as repository_classic_visual_basic_support,
)

StableIdentifier = repository_classic_visual_basic_support.StableIdentifier
ResolveSuffixMatch = repository_classic_visual_basic_support.ResolveSuffixMatch
ResolveDirectoryPrefixMatch = (
    repository_classic_visual_basic_support.ResolveDirectoryPrefixMatch
)

_KNOWN_CLASSIC_VISUAL_BASIC_SUFFIXES = (
    repository_classic_visual_basic_support._KNOWN_CLASSIC_VISUAL_BASIC_SUFFIXES
)
CLASSIC_VISUAL_BASIC_SUFFIXES = frozenset(_KNOWN_CLASSIC_VISUAL_BASIC_SUFFIXES)
CLASSIC_VISUAL_BASIC_CONFIG_BASENAMES = frozenset()
RESERVED_SYMBOL_NAMES = repository_classic_visual_basic_support.RESERVED_SYMBOL_NAMES
BUILTIN_TYPE_NAMES = repository_classic_visual_basic_support.BUILTIN_TYPE_NAMES

strip_comments = repository_classic_visual_basic_support.strip_comments
normalize_target = repository_classic_visual_basic_support.normalize_target
normalize_symbol_name = repository_classic_visual_basic_support.normalize_symbol_name
component_name = repository_classic_visual_basic_support.component_name
project_name = repository_classic_visual_basic_support.project_name
project_startup_name = repository_classic_visual_basic_support.project_startup_name
is_probable_classic_visual_basic_source = (
    repository_classic_visual_basic_support.is_probable_classic_visual_basic_source
)
project_component_entries = (
    repository_classic_visual_basic_support.project_component_entries
)
collect_symbol_entries = repository_classic_visual_basic_support.collect_symbol_entries
module_aliases_for_path = repository_classic_visual_basic_support.module_aliases_for_path
resolve_target = repository_classic_visual_basic_support.resolve_target
parse_dependencies_only = (
    repository_classic_visual_basic_support.parse_dependencies_only
)
parse_file = repository_classic_visual_basic_support.parse_file


def has_classic_visual_basic_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in CLASSIC_VISUAL_BASIC_SUFFIXES


def has_vb6_path_hints(path: Path | PurePosixPath) -> bool:
    return has_classic_visual_basic_path_hints(path)
