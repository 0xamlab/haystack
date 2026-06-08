from __future__ import annotations

import tarfile
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.schemas.repositories import (
    RepositorySnapshotCreateRequest,
    RepositorySnapshotResponse,
)
from apps.api_server.services import (
    repository_intelligence_cache as repository_cache,
)
from apps.api_server.services import (
    repository_intelligence_indexing as repository_indexing,
)
from apps.api_server.services import (
    repository_intelligence_runtime as repository_runtime,
)
from apps.api_server.services import (
    repository_intelligence_storage as repository_storage,
)
from apps.api_server.services.repository_intelligence_shared import (
    _hash_payload,
    _stable_identifier,
    _utc_now,
)
from apps.api_server.services.runtime_internal_contracts import (
    DependencyGraphRecord,
    RepositoryGraphRecord,
    RepositorySnapshotRecord,
    SymbolGraphRecord,
    parquet_bytes_from_records,
)

_RequireRepositoryConnector = Callable[[DataConnector], None]
_ParseConnectorConfig = Callable[[DataConnector], dict[str, Any]]
_ResolvedRepositorySource = Callable[..., Any]
_CompactRepositoryFocusPaths = Callable[..., tuple[str, ...]]
_IterRepositoryFiles = Callable[..., list[Path]]
_BuildModuleIndex = Callable[..., dict[str, str]]
_BuildWorkspaceIndex = Callable[[Path], dict[str, str]]
_GitTrackedContentHashes = Callable[..., dict[str, str] | None]
_FileAnalysisContextHash = Callable[..., str]
_AnalyzeSnapshotFiles = Callable[..., list[Any]]
_AugmentAnalyses = Callable[..., list[Any]]
_ResolveSymbolReferenceTarget = Callable[..., str | None]
_HashFile = Callable[[Path], str]
_WriteBytesWithHash = Callable[[Path, bytes], str]
_LoadSnapshotManifest = Callable[..., dict[str, Any]]


def _snapshot_lookup_key(
    *,
    repository_id: str,
    ref: str | None,
    resolved_revision: str,
    focus_paths: Sequence[str],
    include_patterns: Sequence[str],
    exclude_patterns: Sequence[str],
    max_files: int,
    max_file_size_bytes: int,
    max_total_bytes: int | None,
    engine_revision: str,
) -> str:
    return _stable_identifier(
        "snapshot_lookup",
        {
            "engine_revision": engine_revision,
            "repository_id": repository_id,
            "ref": ref,
            "resolved_revision": resolved_revision,
            "focus_paths": list(focus_paths),
            "include_patterns": list(include_patterns),
            "exclude_patterns": list(exclude_patterns),
            "max_files": max_files,
            "max_file_size_bytes": max_file_size_bytes,
            "max_total_bytes": max_total_bytes,
        },
    )


def _snapshot_lookup_path(org_id: str, repository_id: str, lookup_key: str) -> Path:
    return repository_runtime._snapshot_lookup_dir(org_id, repository_id) / f"{lookup_key}.json"


def _create_source_archive(
    *,
    root_path: Path,
    files: Sequence[Path],
    destination: Path,
    hash_file: _HashFile = repository_storage._hash_file,
) -> str:
    repository_runtime._ensure_parent(destination)
    with tarfile.open(destination, "w") as handle:
        for path in files:
            handle.add(path, arcname=str(path.relative_to(root_path)), recursive=False)
    return hash_file(destination)


def create_repository_snapshot(
    *,
    connector: DataConnector,
    request: RepositorySnapshotCreateRequest,
    engine_revision: str,
    require_repository_connector: _RequireRepositoryConnector,
    parse_connector_config: _ParseConnectorConfig,
    resolved_repository_source: _ResolvedRepositorySource,
    compact_repository_focus_paths: _CompactRepositoryFocusPaths,
    iter_repository_files: _IterRepositoryFiles,
    build_module_index: _BuildModuleIndex,
    build_workspace_package_index: _BuildWorkspaceIndex,
    build_workspace_go_module_index: _BuildWorkspaceIndex,
    git_tracked_content_hashes: _GitTrackedContentHashes,
    file_analysis_context_hash: _FileAnalysisContextHash,
    analyze_snapshot_files: _AnalyzeSnapshotFiles,
    augment_r_package_symbol_references: _AugmentAnalyses,
    augment_julia_package_symbol_references: _AugmentAnalyses,
    resolve_symbol_reference_target: _ResolveSymbolReferenceTarget,
    hash_file: _HashFile,
    write_bytes_with_hash: _WriteBytesWithHash,
) -> RepositorySnapshotResponse:
    require_repository_connector(connector)
    config = parse_connector_config(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)

    with resolved_repository_source(connector=connector, config=config, ref=request.ref) as source:
        normalized_focus_paths = tuple(
            repository_indexing._normalize_repository_relative_path(value)
            for value in request.focus_paths
            if str(value).strip()
        )
        normalized_include_patterns = tuple(
            repository_indexing._normalize_repository_relative_path(value)
            for value in request.include_patterns
            if str(value).strip()
        )
        normalized_exclude_patterns = tuple(
            repository_indexing._normalize_repository_relative_path(value)
            for value in request.exclude_patterns
            if str(value).strip()
        )
        effective_focus_paths = compact_repository_focus_paths(
            source.root_path,
            focus_paths=normalized_focus_paths,
            include_patterns=normalized_include_patterns,
            exclude_patterns=normalized_exclude_patterns,
            max_files=request.max_files,
            max_total_bytes=request.max_total_bytes,
            prefer_concrete_focus_paths=bool(request.prefer_concrete_focus_paths),
        )
        lookup_key = _snapshot_lookup_key(
            repository_id=repository_id,
            ref=request.ref,
            resolved_revision=source.resolved_revision,
            focus_paths=effective_focus_paths,
            include_patterns=normalized_include_patterns,
            exclude_patterns=normalized_exclude_patterns,
            max_files=request.max_files,
            max_file_size_bytes=request.max_file_size_bytes,
            max_total_bytes=request.max_total_bytes,
            engine_revision=engine_revision,
        )
        lookup_path = _snapshot_lookup_path(org_id, repository_id, lookup_key)
        if lookup_path.exists():
            lookup_payload = repository_runtime._read_json(lookup_path)
            snapshot_id = str(lookup_payload.get("snapshot_id") or "").strip()
            if snapshot_id:
                manifest_path = repository_storage._snapshot_paths(
                    org_id,
                    repository_id,
                    snapshot_id,
                )["manifest"]
                if manifest_path.exists():
                    cached_response = repository_runtime._lookup_response_payload(lookup_payload)
                    if (
                        cached_response is not None
                        and str(cached_response.get("resolved_revision") or "")
                        == source.resolved_revision
                    ):
                        return RepositorySnapshotResponse.model_validate(
                            cached_response | {"status": "existing"}
                        )
                    existing = repository_runtime._read_json(manifest_path)
                    if str(existing.get("resolved_revision") or "") == source.resolved_revision:
                        response = RepositorySnapshotResponse.model_validate(
                            existing | {"status": "existing"}
                        )
                        repository_runtime._write_json(
                            lookup_path,
                            {
                                "snapshot_id": snapshot_id,
                                "engine_revision": engine_revision,
                                "resolved_revision": source.resolved_revision,
                                "created_at": existing.get("created_at")
                                or _utc_now().isoformat(),
                                "response": response.model_dump(mode="json"),
                            },
                        )
                        return response

        selection_cache_key = repository_cache._repository_file_selection_cache_key(
            resolved_revision=source.resolved_revision,
            focus_paths=effective_focus_paths,
            include_patterns=normalized_include_patterns,
            exclude_patterns=normalized_exclude_patterns,
            max_files=request.max_files,
            max_total_bytes=request.max_total_bytes,
            engine_revision=engine_revision,
        )
        selection_cache_path = repository_cache._repository_file_selection_cache_path(
            selection_cache_key
        )
        cached_selection = (
            repository_runtime._read_json(selection_cache_path)
            if selection_cache_path.exists()
            else None
        )
        files: list[Path]
        if (
            isinstance(cached_selection, dict)
            and str(cached_selection.get("resolved_revision") or "") == source.resolved_revision
        ):
            cached_relative_paths = cached_selection.get("file_paths")
            if isinstance(cached_relative_paths, list):
                resolved_files = [
                    source.root_path / str(relative_path)
                    for relative_path in cached_relative_paths
                ]
                if all(path.exists() and path.is_file() for path in resolved_files):
                    files = resolved_files
                else:
                    files = iter_repository_files(
                        source.root_path,
                        focus_paths=effective_focus_paths,
                        include_patterns=normalized_include_patterns,
                        exclude_patterns=normalized_exclude_patterns,
                        max_files=request.max_files,
                        max_total_bytes=request.max_total_bytes,
                    )
            else:
                files = iter_repository_files(
                    source.root_path,
                    focus_paths=effective_focus_paths,
                    include_patterns=normalized_include_patterns,
                    exclude_patterns=normalized_exclude_patterns,
                    max_files=request.max_files,
                    max_total_bytes=request.max_total_bytes,
                )
        else:
            files = iter_repository_files(
                source.root_path,
                focus_paths=effective_focus_paths,
                include_patterns=normalized_include_patterns,
                exclude_patterns=normalized_exclude_patterns,
                max_files=request.max_files,
                max_total_bytes=request.max_total_bytes,
            )
        if not (
            isinstance(cached_selection, dict)
            and str(cached_selection.get("resolved_revision") or "") == source.resolved_revision
        ):
            repository_runtime._write_json_atomic(
                selection_cache_path,
                {
                    "resolved_revision": source.resolved_revision,
                    "file_paths": [str(path.relative_to(source.root_path)) for path in files],
                },
            )
        file_paths = [str(path.relative_to(source.root_path)) for path in files]
        module_index = build_module_index(
            file_paths,
            root_path=source.root_path,
        )
        workspace_package_index = build_workspace_package_index(source.root_path)
        workspace_go_module_index = build_workspace_go_module_index(source.root_path)
        tracked_content_hashes = (
            git_tracked_content_hashes(source.root_path, candidate_paths=file_paths)
            if source.is_git
            else None
        )
        analysis_context_hash = file_analysis_context_hash(
            module_index=module_index,
            workspace_package_index=workspace_package_index,
            workspace_go_module_index=workspace_go_module_index,
            max_file_size_bytes=request.max_file_size_bytes,
            engine_revision=engine_revision,
        )
        analyses = analyze_snapshot_files(
            root_path=source.root_path,
            files=files,
            module_index=module_index,
            workspace_package_index=workspace_package_index,
            workspace_go_module_index=workspace_go_module_index,
            max_file_size_bytes=request.max_file_size_bytes,
            analysis_context_hash=analysis_context_hash,
            git_content_hashes=tracked_content_hashes,
        )
        analyses = augment_r_package_symbol_references(
            root_path=source.root_path,
            analyses=analyses,
        )
        analyses = augment_julia_package_symbol_references(
            root_path=source.root_path,
            analyses=analyses,
            module_index=module_index,
        )
        created_at = _utc_now()
        content_hash = _hash_payload(
            [
                {
                    "file_path": item.file_path,
                    "content_hash": item.content_hash,
                    "line_count": item.line_count,
                    "byte_size": item.byte_size,
                }
                for item in analyses
            ]
        )
        snapshot_id = _stable_identifier(
            "snapshot",
            {
                "engine_revision": engine_revision,
                "repository_id": repository_id,
                "ref": request.ref,
                "resolved_revision": source.resolved_revision,
                "content_hash": content_hash,
                "focus_paths": list(effective_focus_paths),
                "include_patterns": list(normalized_include_patterns),
                "exclude_patterns": list(normalized_exclude_patterns),
                "max_total_bytes": request.max_total_bytes,
            },
        )
        paths = repository_storage._snapshot_paths(org_id, repository_id, snapshot_id)
        if paths["manifest"].exists():
            existing = repository_runtime._read_json(paths["manifest"])
            response = RepositorySnapshotResponse.model_validate(existing | {"status": "existing"})
            repository_runtime._write_json(
                lookup_path,
                {
                    "snapshot_id": snapshot_id,
                    "engine_revision": engine_revision,
                    "resolved_revision": source.resolved_revision,
                    "created_at": existing.get("created_at") or _utc_now().isoformat(),
                    "response": response.model_dump(mode="json"),
                },
            )
            return response

        snapshot_records = [
            RepositorySnapshotRecord(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                connector_type=source.connector_type,
                repository_url=source.repository_url,
                resolved_revision=source.resolved_revision,
                file_path=item.file_path,
                language=item.language,
                content_hash=item.content_hash,
                line_count=item.line_count,
                byte_size=item.byte_size,
                token_estimate=item.token_estimate,
                created_at=created_at,
            )
            for item in analyses
        ]
        symbol_records = [
            SymbolGraphRecord(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                symbol_id=symbol.symbol_id,
                file_path=item.file_path,
                symbol_name=symbol.symbol_name,
                language=item.language,
                symbol_kind=symbol.symbol_kind,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                parent_symbol_id=symbol.parent_symbol_id,
                signature=symbol.signature,
                created_at=created_at,
            )
            for item in analyses
            for symbol in item.symbols
        ]
        dependency_records = [
            DependencyGraphRecord(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                dependency_edge_id=dependency.dependency_edge_id,
                source_file=dependency.source_file,
                target_file=dependency.target_file,
                target_symbol=dependency.target_symbol,
                dependency_type=dependency.dependency_type,
                created_at=created_at,
            )
            for item in analyses
            for dependency in item.dependencies
        ]
        symbols_by_file_and_name: dict[tuple[str, str], list[Any]] = defaultdict(list)
        for item in analyses:
            for symbol in item.symbols:
                symbols_by_file_and_name[(item.file_path, symbol.symbol_name)].append(symbol)
        reference_graph_records_by_id: dict[str, RepositoryGraphRecord] = {}
        for item in analyses:
            for candidate in item.symbol_references:
                target_symbol_id = resolve_symbol_reference_target(
                    candidate=candidate,
                    symbols_by_file_and_name=symbols_by_file_and_name,
                )
                if target_symbol_id is None or target_symbol_id == candidate.source_symbol_id:
                    continue
                edge_id = _stable_identifier(
                    "edge",
                    {
                        "source": candidate.source_symbol_id,
                        "target": target_symbol_id,
                        "type": candidate.reference_type,
                    },
                )
                reference_graph_records_by_id.setdefault(
                    edge_id,
                    RepositoryGraphRecord(
                        repository_id=repository_id,
                        snapshot_id=snapshot_id,
                        edge_id=edge_id,
                        source_node=f"symbol:{candidate.source_symbol_id}",
                        target_node=f"symbol:{target_symbol_id}",
                        edge_type=candidate.reference_type,
                        weight=1.0,
                        created_at=created_at,
                    ),
                )
        reference_graph_records = list(reference_graph_records_by_id.values())
        repository_graph_records = [
            RepositoryGraphRecord(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                edge_id=_stable_identifier(
                    "edge",
                    {"source": item.file_path, "target": symbol.symbol_id, "type": "contains"},
                ),
                source_node=f"file:{item.file_path}",
                target_node=f"symbol:{symbol.symbol_id}",
                edge_type="contains",
                weight=1.0,
                created_at=created_at,
            )
            for item in analyses
            for symbol in item.symbols
        ] + [
            RepositoryGraphRecord(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                edge_id=_stable_identifier(
                    "edge",
                    {
                        "source": symbol.parent_symbol_id,
                        "target": symbol.symbol_id,
                        "type": "contains_symbol",
                    },
                ),
                source_node=f"symbol:{symbol.parent_symbol_id}",
                target_node=f"symbol:{symbol.symbol_id}",
                edge_type="contains_symbol",
                weight=1.0,
                created_at=created_at,
            )
            for item in analyses
            for symbol in item.symbols
            if symbol.parent_symbol_id
        ] + reference_graph_records + [
            RepositoryGraphRecord(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                edge_id=_stable_identifier(
                    "edge",
                    {
                        "source": dependency.source_file,
                        "target": dependency.target_file or dependency.target_symbol,
                        "type": dependency.dependency_type,
                    },
                ),
                source_node=f"file:{dependency.source_file}",
                target_node=f"file:{dependency.target_file}"
                if dependency.target_file
                else f"module:{dependency.target_symbol}",
                edge_type=dependency.dependency_type,
                weight=1.0,
                created_at=created_at,
            )
            for dependency in dependency_records
        ]

        paths["dir"].mkdir(parents=True, exist_ok=True)
        snapshot_parquet_hash = write_bytes_with_hash(
            paths["snapshot_parquet"],
            parquet_bytes_from_records(snapshot_records, record_type=RepositorySnapshotRecord),
        )
        symbol_graph_parquet_hash = write_bytes_with_hash(
            paths["symbol_graph_parquet"],
            parquet_bytes_from_records(symbol_records, record_type=SymbolGraphRecord)
            if symbol_records
            else parquet_bytes_from_records([], record_type=SymbolGraphRecord),
        )
        dependency_graph_parquet_hash = write_bytes_with_hash(
            paths["dependency_graph_parquet"],
            parquet_bytes_from_records(dependency_records, record_type=DependencyGraphRecord)
            if dependency_records
            else parquet_bytes_from_records([], record_type=DependencyGraphRecord),
        )
        repository_graph_parquet_hash = write_bytes_with_hash(
            paths["repository_graph_parquet"],
            parquet_bytes_from_records(repository_graph_records, record_type=RepositoryGraphRecord)
            if repository_graph_records
            else parquet_bytes_from_records([], record_type=RepositoryGraphRecord),
        )
        source_archive_hash = _create_source_archive(
            root_path=source.root_path,
            files=files,
            destination=paths["source_archive"],
            hash_file=hash_file,
        )
        language_counts = dict(sorted(Counter(item.language for item in analyses).items()))
        raw_repo_token_estimate = sum(item.token_estimate for item in analyses)
        manifest = {
            "engine_revision": engine_revision,
            "repository_id": repository_id,
            "snapshot_id": snapshot_id,
            "connector_type": source.connector_type,
            "ref": request.ref,
            "resolved_revision": source.resolved_revision,
            "focus_paths": list(effective_focus_paths),
            "requested_focus_paths": list(request.focus_paths),
            "effective_focus_paths": list(effective_focus_paths),
            "prefer_concrete_focus_paths": bool(request.prefer_concrete_focus_paths),
            "content_hash": content_hash,
            "status": "created",
            "created_at": created_at.isoformat(),
            "file_count": len(analyses),
            "language_counts": language_counts,
            "raw_repo_token_estimate": raw_repo_token_estimate,
            "repository_snapshot_artifact": repository_storage._artifact_ref(
                artifact_id=_stable_identifier(
                    "artifact", {"kind": "repository_snapshot", "snapshot_id": snapshot_id}
                ),
                artifact_kind="RepositorySnapshot",
                content_hash=snapshot_parquet_hash,
                storage_path=paths["snapshot_parquet"],
                schema_revision="runtime-internal-contracts-v1",
                created_at=created_at,
            ).model_dump(mode="json"),
            "repository_graph_artifact": repository_storage._artifact_ref(
                artifact_id=_stable_identifier(
                    "artifact", {"kind": "repository_graph", "snapshot_id": snapshot_id}
                ),
                artifact_kind="RepositoryGraph",
                content_hash=repository_graph_parquet_hash,
                storage_path=paths["repository_graph_parquet"],
                schema_revision="runtime-internal-contracts-v1",
                created_at=created_at,
            ).model_dump(mode="json"),
            "symbol_graph_artifact": repository_storage._artifact_ref(
                artifact_id=_stable_identifier(
                    "artifact", {"kind": "symbol_graph", "snapshot_id": snapshot_id}
                ),
                artifact_kind="SymbolGraph",
                content_hash=symbol_graph_parquet_hash,
                storage_path=paths["symbol_graph_parquet"],
                schema_revision="runtime-internal-contracts-v1",
                created_at=created_at,
            ).model_dump(mode="json"),
            "dependency_graph_artifact": repository_storage._artifact_ref(
                artifact_id=_stable_identifier(
                    "artifact", {"kind": "dependency_graph", "snapshot_id": snapshot_id}
                ),
                artifact_kind="DependencyGraph",
                content_hash=dependency_graph_parquet_hash,
                storage_path=paths["dependency_graph_parquet"],
                schema_revision="runtime-internal-contracts-v1",
                created_at=created_at,
            ).model_dump(mode="json"),
            "source_archive_path": str(paths["source_archive"]),
            "source_archive_hash": source_archive_hash,
            "files": [
                {
                    "file_path": item.file_path,
                    "language": item.language,
                    "content_hash": item.content_hash,
                    "line_count": item.line_count,
                    "byte_size": item.byte_size,
                    "token_estimate": item.token_estimate,
                    "symbols": [symbol.__dict__ for symbol in item.symbols],
                    "dependencies": [dependency.__dict__ for dependency in item.dependencies],
                    "symbol_references": [
                        {
                            "source_symbol_id": reference.source_symbol_id,
                            "target_symbol_id": reference.target_symbol_id,
                            "target_file": reference.target_file,
                            "target_names": list(reference.target_names),
                            "reference_type": reference.reference_type,
                        }
                        for reference in item.symbol_references
                    ],
                }
                for item in analyses
            ],
        }
        repository_runtime._write_json(paths["manifest"], manifest)
        repository_runtime._write_json(
            lookup_path,
            {
                "snapshot_id": snapshot_id,
                "engine_revision": engine_revision,
                "resolved_revision": source.resolved_revision,
                "created_at": created_at.isoformat(),
                "response": RepositorySnapshotResponse.model_validate(manifest).model_dump(
                    mode="json"
                ),
            },
        )
        return RepositorySnapshotResponse.model_validate(manifest)


def get_repository_snapshot(
    *,
    connector: DataConnector,
    snapshot_id: str,
    require_repository_connector: _RequireRepositoryConnector,
    load_snapshot_manifest: _LoadSnapshotManifest,
) -> RepositorySnapshotResponse:
    require_repository_connector(connector)
    manifest = load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot_id,
    )
    return RepositorySnapshotResponse.model_validate(manifest)
