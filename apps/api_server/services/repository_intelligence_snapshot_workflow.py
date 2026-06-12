from __future__ import annotations

import tarfile
import time
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
from apps.api_server.services import (
    repository_intelligence_telemetry as telemetry,
)
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.repository_intelligence_lookup_store import (
    mirror_lookup,
    read_lookup_shared,
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
    SymbolReferenceRecord,
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


def _mirror_source_archive_to_object_store(
    *,
    org_id: str,
    repository_id: str,
    snapshot_id: str,
    archive_path: Path,
) -> str | None:
    """B8 durability: when the object store is enabled (``ALGENTA_RI_OBJECT_STORE=s3``), mirror the
    source archive to the durable, tenant-scoped object store so the snapshot survives the loss of
    the node that created it and is materializable from any replica. The node-local copy stays the
    fast path; the returned key is recorded in the manifest for ``materialized_snapshot``'s
    cross-replica fallback.

    Returns ``None`` in local mode (the current behavior — no mirror). Fails closed: when s3 is
    required and the durable write fails, the snapshot must not silently report success."""
    from apps.api_server.services.repository_intelligence_object_store import (
        artifact_key,
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return None
    key = artifact_key(
        org_id=org_id,
        repository_id=repository_id,
        kind="archives",
        artifact_id=snapshot_id,
    )
    try:
        get_object_store().put_bytes(
            key,
            Path(archive_path).read_bytes(),
            content_type="application/x-tar",
        )
    except Exception as exc:  # noqa: BLE001 — surface as a fail-closed snapshot error
        raise RepositoryIntelligenceError(
            code="snapshot_source_archive_persist_failed",
            message=f"failed to persist the source archive to the object store: {exc}",
            status_code=502,
        ) from exc
    return key


def _mirror_snapshot_manifest_to_object_store(
    *,
    org_id: str,
    repository_id: str,
    snapshot_id: str,
    manifest: dict[str, Any],
) -> str | None:
    """B8 durability: mirror the snapshot MANIFEST (the slim v2 JSON) to the durable, tenant-scoped
    object store when it's enabled (``ALGENTA_RI_OBJECT_STORE=s3``), so the manifest is recoverable
    from any replica even if the node that created it is lost. The node-local copy stays the fast
    path. Returns ``None`` in local mode (no-op, fully backward compatible). Fails closed (502) when
    the durable write fails — the API must not report a snapshot created while its durable manifest
    silently failed.

    Uses the ``snapshots`` kind, distinct from the source archive's ``archives`` kind for the same
    ``snapshot_id``, so the manifest object never collides with ``source.tar``. The key is NOT
    self-recorded in the manifest: the read path re-derives it from identity, which keeps the
    on-disk file and the durable object byte-identical (both ``json.dumps(indent=2, sort_keys=True)``)."""
    from apps.api_server.services.repository_intelligence_object_store import (
        artifact_key,
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return None
    key = artifact_key(
        org_id=org_id,
        repository_id=repository_id,
        kind="snapshots",
        artifact_id=snapshot_id,
    )
    try:
        get_object_store().put_json(key, manifest)
    except Exception as exc:  # noqa: BLE001 — surface as a fail-closed snapshot error
        raise RepositoryIntelligenceError(
            code="snapshot_manifest_persist_failed",
            message=f"failed to persist the snapshot manifest to the object store: {exc}",
            status_code=502,
        ) from exc
    return key


def _mirror_snapshot_parquet_to_object_store(
    *,
    org_id: str,
    repository_id: str,
    snapshot_id: str,
    parquet_by_kind: dict[str, bytes],
) -> None:
    """B8 durability: mirror the snapshot's Parquet artifacts to the durable, tenant-scoped object
    store when it's enabled (``ALGENTA_RI_OBJECT_STORE=s3``), so a v2 (slim) snapshot can be
    hydrated from any replica — the manifest only carries lightweight per-file metadata; the
    symbols/dependencies/symbol_references arrays live in these Parquet blobs. The node-local copies
    stay the fast path. No-op (returns) in local mode (backward compatible). Fails closed (502) when
    any durable write fails.

    Each kind is stored under its own ``artifact_key`` (the five ``snapshot_paths`` Parquet keys, all
    distinct from the ``snapshots`` manifest kind and the ``archives`` source-tar kind for the same
    ``snapshot_id``), keyed by ``snapshot_id``. The caller passes the EXACT in-memory bytes that
    were hashed into the manifest ``content_hash`` (never a disk re-read), so the recovery-side
    sha256 integrity check matches by construction.

    DURABILITY GUARANTEE: only snapshots created on the cold-create path with the object store
    enabled get their Parquet mirrored. Snapshots whose manifest was already on this node (the
    lookup-cache / manifest-exists early-return paths) and pre-existing v2 snapshots created before
    this slice require a one-time operational backfill; until then a cross-replica read of such a
    snapshot fails closed with ``snapshot_hydration_unavailable`` (503)."""
    from apps.api_server.services.repository_intelligence_object_store import (
        artifact_key,
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return
    store = get_object_store()
    try:
        for kind, data in parquet_by_kind.items():
            store.put_bytes(
                artifact_key(
                    org_id=org_id,
                    repository_id=repository_id,
                    kind=kind,
                    artifact_id=snapshot_id,
                ),
                data,
                content_type="application/vnd.apache.parquet",
            )
    except Exception as exc:  # noqa: BLE001 — surface as a fail-closed snapshot error
        raise RepositoryIntelligenceError(
            code="snapshot_parquet_persist_failed",
            message=f"failed to persist a snapshot Parquet artifact to the object store: {exc}",
            status_code=502,
        ) from exc


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
                # B8: this fast path is gated on the LOCAL manifest existing, so it serves a
                # snapshot already materialized on this node; it does NOT re-mirror Parquet (a fresh
                # replica has no local manifest and falls through to the cold-create path, which
                # mirrors). Pre-existing v2 snapshots need a one-time operational backfill.
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

        # Cross-replica perf-dedup (s3 mode only; no-op locally): a sibling may have already created
        # this exact snapshot, so we can skip the expensive re-clone + re-archive. Snapshots are
        # content-addressed and deterministic — a miss/fault just falls through to the cold-create
        # path (which itself mirrors). The embedded response is self-contained; downstream reads
        # recover the manifest/Parquet via B8. The lookup_key already pins resolved_revision, but we
        # re-check it on the embedded response for parity with the node-local fast path above.
        shared_snapshot_lookup = read_lookup_shared(
            org_id=org_id,
            repository_id=repository_id,
            kind="snapshot_lookup",
            lookup_key=lookup_key,
        )
        if shared_snapshot_lookup is not None:
            shared_response = repository_runtime._lookup_response_payload(shared_snapshot_lookup)
            if (
                shared_response is not None
                and str(shared_response.get("resolved_revision") or "")
                == source.resolved_revision
            ):
                return RepositorySnapshotResponse.model_validate(
                    shared_response | {"status": "existing"}
                )

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
        # B8: gated on the LOCAL manifest existing — serves an already-materialized snapshot and
        # does NOT re-mirror Parquet (a fresh replica has no local manifest and reaches cold-create
        # below, which mirrors). Pre-existing v2 snapshots need a one-time operational backfill.
        if paths["manifest"].exists():
            existing = repository_runtime._read_json(paths["manifest"])
            response = RepositorySnapshotResponse.model_validate(existing | {"status": "existing"})
            snapshot_lookup_payload = {
                "snapshot_id": snapshot_id,
                "engine_revision": engine_revision,
                "resolved_revision": source.resolved_revision,
                "created_at": existing.get("created_at") or _utc_now().isoformat(),
                "response": response.model_dump(mode="json"),
            }
            repository_runtime._write_json(lookup_path, snapshot_lookup_payload)
            # Lazily backfill the shared index from a locally-materialized snapshot (s3 only; no-op
            # locally). Best-effort — lets sibling replicas dedup without a re-clone.
            mirror_lookup(
                org_id=org_id,
                repository_id=repository_id,
                kind="snapshot_lookup",
                lookup_key=lookup_key,
                payload=snapshot_lookup_payload,
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
        # AR-OPT-2: persist per-file symbol references to Parquet so the slim (v2)
        # manifest can hydrate them on load instead of inlining them in the JSON.
        symbol_reference_records = [
            SymbolReferenceRecord(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                reference_edge_id=reference.reference_edge_id,
                source_file=reference.source_file,
                source_symbol_id=reference.source_symbol_id,
                target_symbol_id=reference.target_symbol_id,
                target_file=reference.target_file,
                reference_type=reference.reference_type,
                created_at=created_at,
            )
            for item in analyses
            for reference in item.symbol_references
        ]
        # AR-OPT-0: time the dependency/reference graph construction (edge resolution
        # + record assembly) into the telemetry span the CI presence gate requires.
        _graph_build_start = time.perf_counter()
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
        telemetry.record_span_ms(
            "graph_build_ms", (time.perf_counter() - _graph_build_start) * 1000.0
        )

        # AR-OPT-0/2: time artifact IO so the slim-manifest (v2) work can prove its
        # reduction against these baselines.
        _parquet_write_start = time.perf_counter()
        paths["dir"].mkdir(parents=True, exist_ok=True)
        # B8: capture the exact in-memory Parquet payloads so the object-store mirror below stores
        # the SAME bytes that write_bytes_with_hash hashes into the manifest content_hash — the
        # recovery-side sha256 integrity check then matches by construction (no re-read / TOCTOU).
        snapshot_parquet_bytes = parquet_bytes_from_records(
            snapshot_records, record_type=RepositorySnapshotRecord
        )
        symbol_graph_parquet_bytes = (
            parquet_bytes_from_records(symbol_records, record_type=SymbolGraphRecord)
            if symbol_records
            else parquet_bytes_from_records([], record_type=SymbolGraphRecord)
        )
        dependency_graph_parquet_bytes = (
            parquet_bytes_from_records(dependency_records, record_type=DependencyGraphRecord)
            if dependency_records
            else parquet_bytes_from_records([], record_type=DependencyGraphRecord)
        )
        repository_graph_parquet_bytes = (
            parquet_bytes_from_records(repository_graph_records, record_type=RepositoryGraphRecord)
            if repository_graph_records
            else parquet_bytes_from_records([], record_type=RepositoryGraphRecord)
        )
        symbol_reference_parquet_bytes = (
            parquet_bytes_from_records(symbol_reference_records, record_type=SymbolReferenceRecord)
            if symbol_reference_records
            else parquet_bytes_from_records([], record_type=SymbolReferenceRecord)
        )
        snapshot_parquet_hash = write_bytes_with_hash(
            paths["snapshot_parquet"], snapshot_parquet_bytes
        )
        symbol_graph_parquet_hash = write_bytes_with_hash(
            paths["symbol_graph_parquet"], symbol_graph_parquet_bytes
        )
        dependency_graph_parquet_hash = write_bytes_with_hash(
            paths["dependency_graph_parquet"], dependency_graph_parquet_bytes
        )
        repository_graph_parquet_hash = write_bytes_with_hash(
            paths["repository_graph_parquet"], repository_graph_parquet_bytes
        )
        symbol_reference_parquet_hash = write_bytes_with_hash(
            paths["symbol_reference_parquet"], symbol_reference_parquet_bytes
        )
        # B8: mirror the snapshot Parquet to the durable object store BEFORE the manifest (below),
        # so a crash between the two never leaves a recoverable manifest pointing at absent Parquet.
        # No-op in local mode; fails closed (502) in s3.
        _mirror_snapshot_parquet_to_object_store(
            org_id=org_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            parquet_by_kind={
                "snapshot_parquet": snapshot_parquet_bytes,
                "symbol_graph_parquet": symbol_graph_parquet_bytes,
                "dependency_graph_parquet": dependency_graph_parquet_bytes,
                "repository_graph_parquet": repository_graph_parquet_bytes,
                "symbol_reference_parquet": symbol_reference_parquet_bytes,
            },
        )
        telemetry.record_span_ms(
            "parquet_write_ms", (time.perf_counter() - _parquet_write_start) * 1000.0
        )
        _tar_write_start = time.perf_counter()
        source_archive_hash = _create_source_archive(
            root_path=source.root_path,
            files=files,
            destination=paths["source_archive"],
            hash_file=hash_file,
        )
        telemetry.record_span_ms(
            "tar_write_ms", (time.perf_counter() - _tar_write_start) * 1000.0
        )
        # B8: mirror the source archive to the durable object store (opt-in; no-op in local mode)
        # so the snapshot is recoverable from any replica even if this node's volume is lost.
        source_archive_object_key = _mirror_source_archive_to_object_store(
            org_id=org_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            archive_path=paths["source_archive"],
        )
        language_counts = dict(sorted(Counter(item.language for item in analyses).items()))
        raw_repo_token_estimate = sum(item.token_estimate for item in analyses)
        manifest = {
            # AR-OPT-2: slim manifest v2 — files[] carries only lightweight metadata;
            # per-file symbols/dependencies/symbol_references are NOT inlined and are
            # hydrated on load from the Parquet artifacts (see manifest_reader). Legacy
            # v1 (inline) snapshots remain readable via their inline arrays.
            "manifest_version": 2,
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
            "symbol_reference_artifact": repository_storage._artifact_ref(
                artifact_id=_stable_identifier(
                    "artifact", {"kind": "symbol_reference", "snapshot_id": snapshot_id}
                ),
                artifact_kind="SymbolReference",
                content_hash=symbol_reference_parquet_hash,
                storage_path=paths["symbol_reference_parquet"],
                schema_revision="runtime-internal-contracts-v1",
                created_at=created_at,
            ).model_dump(mode="json"),
            "source_archive_path": str(paths["source_archive"]),
            "source_archive_hash": source_archive_hash,
            # B8: durable object-store key for the source archive (None in local mode). Read by
            # materialized_snapshot to recover the archive when it isn't on the local node.
            "source_archive_object_key": source_archive_object_key,
            # AR-OPT-2 v2: lightweight per-file metadata only. The heavy
            # symbols/dependencies/symbol_references arrays live in the Parquet
            # artifacts above and are hydrated on load by manifest_reader.
            "files": [
                {
                    "file_path": item.file_path,
                    "language": item.language,
                    "content_hash": item.content_hash,
                    "line_count": item.line_count,
                    "byte_size": item.byte_size,
                    "token_estimate": item.token_estimate,
                }
                for item in analyses
            ],
        }
        # AR-OPT-2: time the manifest JSON write — the v1 inline payload dominates
        # this for large repos and is exactly what the v2 slim manifest will cut.
        _manifest_write_start = time.perf_counter()
        repository_runtime._write_json(paths["manifest"], manifest)
        # B8: mirror the snapshot manifest to the durable object store (opt-in; no-op in local mode)
        # so it's recoverable from any replica. The lookup index below stays node-local.
        _mirror_snapshot_manifest_to_object_store(
            org_id=org_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            manifest=manifest,
        )
        cold_snapshot_lookup_payload = {
            "snapshot_id": snapshot_id,
            "engine_revision": engine_revision,
            "resolved_revision": source.resolved_revision,
            "created_at": created_at.isoformat(),
            "response": RepositorySnapshotResponse.model_validate(manifest).model_dump(mode="json"),
        }
        repository_runtime._write_json(lookup_path, cold_snapshot_lookup_payload)
        # Publish the freshly-created snapshot to the durable shared index so sibling replicas dedup
        # the re-clone (s3 only; no-op locally). Best-effort — a failed mirror just lets one recompute.
        mirror_lookup(
            org_id=org_id,
            repository_id=repository_id,
            kind="snapshot_lookup",
            lookup_key=lookup_key,
            payload=cold_snapshot_lookup_payload,
        )
        telemetry.record_span_ms(
            "manifest_write_ms", (time.perf_counter() - _manifest_write_start) * 1000.0
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
