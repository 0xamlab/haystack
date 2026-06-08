from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RepositoryIntelligenceError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


@dataclass(frozen=True)
class _ModuleIndexLookup:
    values: tuple[str, ...]
    exact_paths: dict[str, str]
    suffix_paths: dict[str, str]
    directory_suffix_paths: dict[str, str]


@dataclass(frozen=True)
class _Symbol:
    symbol_id: str
    symbol_name: str
    symbol_kind: str
    start_line: int
    end_line: int
    parent_symbol_id: str | None
    signature: str | None


@dataclass(frozen=True)
class _Dependency:
    dependency_edge_id: str
    source_file: str
    target_file: str | None
    target_symbol: str | None
    dependency_type: str


@dataclass(frozen=True)
class _JSImportBinding:
    alias: str
    target_file: str | None
    target_names: tuple[str, ...]


@dataclass(frozen=True)
class _SymbolReferenceCandidate:
    reference_edge_id: str
    source_symbol_id: str
    source_file: str
    target_symbol_id: str | None
    target_file: str | None
    target_names: tuple[str, ...]
    reference_type: str


@dataclass(frozen=True)
class _ImportedSymbolBinding:
    alias: str
    target_file: str | None
    target_names: tuple[str, ...]


@dataclass(frozen=True)
class _FileAnalysis:
    file_path: str
    language: str
    content_hash: str
    line_count: int
    byte_size: int
    token_estimate: int
    symbols: tuple[_Symbol, ...]
    dependencies: tuple[_Dependency, ...]
    symbol_references: tuple[_SymbolReferenceCandidate, ...]


@dataclass(frozen=True)
class _ResolvedRepositorySource:
    root_path: Path
    connector_type: str
    repository_url: str | None
    ref: str | None
    resolved_revision: str
    is_git: bool
    cleanup_path: Path | None = None


@dataclass(frozen=True)
class _InlineConnectorType:
    value: str


@dataclass(frozen=True)
class _InlineConnector:
    id: uuid.UUID
    org_id: uuid.UUID
    connector_type: _InlineConnectorType


@dataclass(frozen=True)
class _DeterministicLiteralPatch:
    file_path: str
    symbol_name: str | None
    diagnostic_line: int | None
    current_literal: str
    expected_literal: str
    patch_diff: str


@dataclass(frozen=True)
class _DeterministicConfigPatch:
    file_path: str
    old_root_dir: str | None
    new_root_dir: str
    diagnostic_count: int
    patch_diff: str


@dataclass
class _JsLikeLexState:
    in_block_comment: bool = False
    string_delim: str | None = None
    escape: bool = False
    template_expression_depth: int = 0


@dataclass(frozen=True)
class _TsconfigPathAliasMapping:
    alias_pattern: str
    target_pattern: str
