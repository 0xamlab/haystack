from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _FileAnalysis,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_runtime import (
    _dependency_analysis_cache_dir,
    _file_analysis_cache_dir,
    _read_json,
    _repository_file_selection_cache_dir,
)
from apps.api_server.services.repository_intelligence_shared import (
    _hash_payload,
    _stable_identifier,
)

_FILE_ANALYSIS_CACHE_SCHEMA_VERSION = "repository-file-analysis-v1"
_DEPENDENCY_ANALYSIS_CACHE_SCHEMA_VERSION = "repository-dependency-analysis-v1"


def _file_analysis_context_hash(
    *,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
    workspace_go_module_index: dict[str, tuple[str, ...]] | None,
    max_file_size_bytes: int,
    engine_revision: str,
) -> str:
    return _hash_payload(
        {
            "engine_revision": engine_revision,
            "module_index": module_index,
            "workspace_package_index": workspace_package_index,
            "workspace_go_module_index": workspace_go_module_index or {},
            "max_file_size_bytes": max_file_size_bytes,
        }
    )


def _file_analysis_cache_key(
    *,
    relative_path: str,
    content_hash: str,
    analysis_context_hash: str,
    engine_revision: str,
) -> str:
    return _stable_identifier(
        "file_analysis",
        {
            "engine_revision": engine_revision,
            "relative_path": relative_path,
            "content_hash": content_hash,
            "analysis_context_hash": analysis_context_hash,
        },
    )


def _file_analysis_cache_path(cache_key: str) -> Path:
    return _file_analysis_cache_dir() / cache_key[:2] / f"{cache_key}.json"


def _serialize_file_analysis(
    analysis: _FileAnalysis,
    *,
    engine_revision: str,
) -> dict[str, Any]:
    return {
        "schema_version": _FILE_ANALYSIS_CACHE_SCHEMA_VERSION,
        "engine_revision": engine_revision,
        "analysis": {
            "file_path": analysis.file_path,
            "language": analysis.language,
            "content_hash": analysis.content_hash,
            "line_count": analysis.line_count,
            "byte_size": analysis.byte_size,
            "token_estimate": analysis.token_estimate,
            "symbols": [asdict(symbol) for symbol in analysis.symbols],
            "dependencies": [asdict(dependency) for dependency in analysis.dependencies],
            "symbol_references": [
                asdict(reference) for reference in analysis.symbol_references
            ],
        },
    }


def _deserialize_symbol(payload: dict[str, Any]) -> _Symbol:
    return _Symbol(
        symbol_id=str(payload["symbol_id"]),
        symbol_name=str(payload["symbol_name"]),
        symbol_kind=str(payload["symbol_kind"]),
        start_line=int(payload["start_line"]),
        end_line=int(payload["end_line"]),
        parent_symbol_id=(
            None
            if payload.get("parent_symbol_id") is None
            else str(payload.get("parent_symbol_id"))
        ),
        signature=None if payload.get("signature") is None else str(payload.get("signature")),
    )


def _deserialize_dependency(payload: dict[str, Any]) -> _Dependency:
    return _Dependency(
        dependency_edge_id=str(payload["dependency_edge_id"]),
        source_file=str(payload["source_file"]),
        target_file=None if payload.get("target_file") is None else str(payload.get("target_file")),
        target_symbol=(
            None if payload.get("target_symbol") is None else str(payload.get("target_symbol"))
        ),
        dependency_type=str(payload["dependency_type"]),
    )


def _deserialize_symbol_reference(
    payload: dict[str, Any],
) -> _SymbolReferenceCandidate:
    return _SymbolReferenceCandidate(
        reference_edge_id=str(payload["reference_edge_id"]),
        source_symbol_id=str(payload["source_symbol_id"]),
        source_file=str(payload["source_file"]),
        target_symbol_id=(
            None
            if payload.get("target_symbol_id") is None
            else str(payload.get("target_symbol_id"))
        ),
        target_file=None if payload.get("target_file") is None else str(payload.get("target_file")),
        target_names=tuple(str(name) for name in payload.get("target_names", [])),
        reference_type=str(payload["reference_type"]),
    )


def _deserialize_file_analysis(payload: dict[str, Any]) -> _FileAnalysis | None:
    if payload.get("schema_version") != _FILE_ANALYSIS_CACHE_SCHEMA_VERSION:
        return None
    analysis_payload = payload.get("analysis")
    if not isinstance(analysis_payload, dict):
        return None
    try:
        return _FileAnalysis(
            file_path=str(analysis_payload["file_path"]),
            language=str(analysis_payload["language"]),
            content_hash=str(analysis_payload["content_hash"]),
            line_count=int(analysis_payload["line_count"]),
            byte_size=int(analysis_payload["byte_size"]),
            token_estimate=int(analysis_payload["token_estimate"]),
            symbols=tuple(
                _deserialize_symbol(item)
                for item in analysis_payload.get("symbols", [])
                if isinstance(item, dict)
            ),
            dependencies=tuple(
                _deserialize_dependency(item)
                for item in analysis_payload.get("dependencies", [])
                if isinstance(item, dict)
            ),
            symbol_references=tuple(
                _deserialize_symbol_reference(item)
                for item in analysis_payload.get("symbol_references", [])
                if isinstance(item, dict)
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _load_file_analysis_cache(cache_path: Path) -> _FileAnalysis | None:
    if not cache_path.exists():
        return None
    try:
        payload = _read_json(cache_path)
    except json.JSONDecodeError:
        return None
    return _deserialize_file_analysis(payload)


def _dependency_analysis_cache_key(
    *,
    relative_path: str,
    content_hash: str,
    analysis_context_hash: str,
    engine_revision: str,
) -> str:
    return _stable_identifier(
        "dependency_analysis",
        {
            "engine_revision": engine_revision,
            "relative_path": relative_path,
            "content_hash": content_hash,
            "analysis_context_hash": analysis_context_hash,
        },
    )


def _dependency_analysis_cache_path(cache_key: str) -> Path:
    return _dependency_analysis_cache_dir() / cache_key[:2] / f"{cache_key}.json"


def _serialize_dependency_analysis(
    dependencies: tuple[_Dependency, ...],
    *,
    engine_revision: str,
) -> dict[str, Any]:
    return {
        "schema_version": _DEPENDENCY_ANALYSIS_CACHE_SCHEMA_VERSION,
        "engine_revision": engine_revision,
        "dependencies": [asdict(dependency) for dependency in dependencies],
    }


def _deserialize_dependency_analysis(
    payload: dict[str, Any],
) -> tuple[_Dependency, ...] | None:
    if payload.get("schema_version") != _DEPENDENCY_ANALYSIS_CACHE_SCHEMA_VERSION:
        return None
    dependency_payload = payload.get("dependencies")
    if not isinstance(dependency_payload, list):
        return None
    try:
        return tuple(
            _deserialize_dependency(item)
            for item in dependency_payload
            if isinstance(item, dict)
        )
    except (KeyError, TypeError, ValueError):
        return None


def _load_dependency_analysis_cache(
    cache_path: Path,
) -> tuple[_Dependency, ...] | None:
    if not cache_path.exists():
        return None
    try:
        payload = _read_json(cache_path)
    except json.JSONDecodeError:
        return None
    return _deserialize_dependency_analysis(payload)


def _repository_file_selection_cache_key(
    *,
    resolved_revision: str,
    focus_paths: Sequence[str],
    include_patterns: Sequence[str],
    exclude_patterns: Sequence[str],
    max_files: int,
    max_total_bytes: int | None,
    engine_revision: str,
) -> str:
    return _stable_identifier(
        "file_selection",
        {
            "engine_revision": engine_revision,
            "resolved_revision": resolved_revision,
            "focus_paths": list(focus_paths),
            "include_patterns": list(include_patterns),
            "exclude_patterns": list(exclude_patterns),
            "max_files": max_files,
            "max_total_bytes": max_total_bytes,
        },
    )


def _repository_file_selection_cache_path(cache_key: str) -> Path:
    return _repository_file_selection_cache_dir() / cache_key[:2] / f"{cache_key}.json"
