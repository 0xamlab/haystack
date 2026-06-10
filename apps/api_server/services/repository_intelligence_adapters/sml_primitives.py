from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    ml as repository_ml_adapter,
)

StableIdentifier = repository_ml_adapter.StableIdentifier
ResolveSuffixMatch = repository_ml_adapter.ResolveSuffixMatch

SML_SUFFIXES = frozenset({".sml", ".sig", ".fun"})

collect_symbol_entries = repository_ml_adapter.collect_symbol_entries
declared_module_names = repository_ml_adapter.declared_module_names
module_aliases_for_path = repository_ml_adapter.module_aliases_for_path
normalize_symbol_name = repository_ml_adapter.normalize_symbol_name
normalize_target = repository_ml_adapter.normalize_target
resolve_import = repository_ml_adapter.resolve_import
strip_comments = repository_ml_adapter.strip_comments


def has_sml_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in SML_SUFFIXES


def is_probable_sml_source(*, path: Path | PurePosixPath, text: str) -> bool:
    return has_sml_path_hints(path) and bool(strip_comments(text).strip())


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
    "resolve_import",
    "strip_comments",
]
