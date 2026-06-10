from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    ml as repository_ml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sml_primitives as repository_sml_primitives,
)

ResolveSuffixMatch = repository_sml_primitives.ResolveSuffixMatch
StableIdentifier = repository_sml_primitives.StableIdentifier

SML_SUFFIXES = repository_sml_primitives.SML_SUFFIXES
collect_symbol_entries = repository_sml_primitives.collect_symbol_entries
declared_module_names = repository_sml_primitives.declared_module_names
has_sml_path_hints = repository_sml_primitives.has_sml_path_hints
is_probable_sml_source = repository_sml_primitives.is_probable_sml_source
normalize_symbol_name = repository_sml_primitives.normalize_symbol_name
normalize_target = repository_sml_primitives.normalize_target
resolve_import = repository_sml_primitives.resolve_import
strip_comments = repository_sml_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    if PurePosixPath(file_path).suffix.lower() not in SML_SUFFIXES:
        return set()
    return repository_ml_adapter.module_aliases_for_path(
        root_path=root_path,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Any,
) -> tuple[dict[str, Any], ...]:
    if not is_probable_sml_source(path=Path(file_path), text=text):
        return ()
    return repository_ml_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Any,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    if not is_probable_sml_source(path=Path(file_path), text=text):
        return (), (), ()
    return repository_ml_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )


__all__ = [
    "ResolveSuffixMatch",
    "SML_SUFFIXES",
    "StableIdentifier",
    "collect_symbol_entries",
    "declared_module_names",
    "has_sml_path_hints",
    "is_probable_sml_source",
    "module_aliases_for_path",
    "normalize_symbol_name",
    "normalize_target",
    "parse_dependencies_only",
    "parse_file",
    "resolve_import",
    "strip_comments",
]
