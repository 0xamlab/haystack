from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from apps.api_server.models.data_connector import DataConnector
from apps.api_server.schemas.repositories import (
    RepositoryEvidenceItem,
    RepositoryGraphEdge,
    RepositoryGraphImpactItem,
    RepositoryGraphNode,
    RepositoryGraphQueryRequest,
    RepositoryGraphQueryResponse,
    RepositoryTriageRequest,
    RepositoryTriageResponse,
)
from apps.api_server.services import repository_intelligence_graph as repository_graph
from apps.api_server.services import repository_intelligence_storage as repository_storage
from apps.api_server.services import repository_intelligence_telemetry as telemetry
from apps.api_server.services import repository_intelligence_sdk_ranking as sdk_ranking
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _estimate_tokens,
)
from apps.api_server.services.repository_intelligence_runtime import (
    _graph_query_lookup_dir,
    _lookup_response_payload,
    _read_json,
    _triage_dir,
    _triage_lookup_dir,
    _write_json,
)
from apps.api_server.services.repository_intelligence_shared import (
    _stable_identifier,
    _utc_now,
)
from apps.api_server.services.runtime_internal_contracts import (
    WorkspaceEvidenceBundleRecord,
    parquet_bytes_from_records,
)

_RequireRepositoryConnector = Callable[[DataConnector], None]
_LoadSnapshotManifest = Callable[..., dict[str, Any]]
_LoadTriageManifest = Callable[..., dict[str, Any]]
_ReadJson = Callable[[Path], dict[str, Any]]
_MaterializedSnapshot = Callable[[dict[str, Any]], Any]


def _triage_lookup_key(
    *,
    snapshot_id: str,
    signals: dict[str, Any],
    max_evidence_items: int,
    max_snippet_lines: int,
    token_budget: int,
    engine_revision: str,
    ranking_mode: str,
) -> str:
    return _stable_identifier(
        "triage_lookup",
        {
            "engine_revision": engine_revision,
            "snapshot_id": snapshot_id,
            "signals": signals,
            "max_evidence_items": max_evidence_items,
            "max_snippet_lines": max_snippet_lines,
            "token_budget": token_budget,
            # The ranking lane changes the output ordering, so it is part of the
            # cache identity: heuristic and SDK-fused (Mojo RRF) results must not
            # share a key, else toggling ALGENTA_REPOSITORIES_SDK_RANKING serves a
            # stale ordering from the other mode.
            "ranking_mode": ranking_mode,
        },
    )


def _triage_ranking_mode() -> str:
    """Identity of the active triage ranking lane (part of the cache key)."""
    return "sdk_rrf" if sdk_ranking.sdk_ranking_enabled() else "heuristic"


def _graph_query_lookup_key(
    *,
    snapshot_id: str,
    file_path: str | None,
    symbol_name: str | None,
    workspace_evidence_bundle_ref: str | None,
    direction: str,
    max_depth: int,
    max_nodes: int,
    engine_revision: str,
) -> str:
    return _stable_identifier(
        "graph_query_lookup",
        {
            "engine_revision": engine_revision,
            "snapshot_id": snapshot_id,
            "file_path": file_path,
            "symbol_name": symbol_name,
            "workspace_evidence_bundle_ref": workspace_evidence_bundle_ref,
            "direction": direction,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
        },
    )


def query_repository_graph(
    *,
    connector: DataConnector,
    request: RepositoryGraphQueryRequest,
    engine_revision: str,
    require_repository_connector: _RequireRepositoryConnector,
    load_snapshot_manifest: _LoadSnapshotManifest,
    load_triage_manifest: _LoadTriageManifest,
    read_json: _ReadJson = _read_json,
) -> RepositoryGraphQueryResponse:
    require_repository_connector(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)
    resolved_snapshot_id = request.snapshot_id
    triage_manifest: dict[str, Any] | None = None
    if request.workspace_evidence_bundle_ref:
        triage_manifest = load_triage_manifest(
            org_id=org_id,
            repository_id=repository_id,
            evidence_bundle_ref=request.workspace_evidence_bundle_ref,
        )
        triage_snapshot_id = str(triage_manifest.get("snapshot_id") or "").strip()
        if not triage_snapshot_id:
            raise RepositoryIntelligenceError(
                code="workspace_evidence_bundle_invalid",
                message=(
                    "Workspace evidence bundle is missing a snapshot_id and cannot seed "
                    "a repository graph query."
                ),
                status_code=409,
                details={
                    "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
                },
            )
        if resolved_snapshot_id and triage_snapshot_id != resolved_snapshot_id:
            raise RepositoryIntelligenceError(
                code="repository_graph_query_snapshot_mismatch",
                message=(
                    "Repository graph query workspace_evidence_bundle_ref does not "
                    "belong to the requested snapshot."
                ),
                status_code=409,
                details={
                    "requested_snapshot_id": resolved_snapshot_id,
                    "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
                    "triage_snapshot_id": triage_snapshot_id,
                },
            )
        resolved_snapshot_id = triage_snapshot_id
    if not resolved_snapshot_id:
        raise RepositoryIntelligenceError(
            code="repository_graph_query_requires_snapshot",
            message=(
                "Repository graph query requires snapshot_id or "
                "workspace_evidence_bundle_ref."
            ),
            status_code=422,
        )

    graph_query_lookup_key = _graph_query_lookup_key(
        snapshot_id=resolved_snapshot_id,
        file_path=request.file_path,
        symbol_name=request.symbol_name,
        workspace_evidence_bundle_ref=request.workspace_evidence_bundle_ref,
        direction=request.direction,
        max_depth=request.max_depth,
        max_nodes=request.max_nodes,
        engine_revision=engine_revision,
    )
    graph_query_lookup_path = _graph_query_lookup_dir(org_id, repository_id) / (
        f"{graph_query_lookup_key}.json"
    )
    if graph_query_lookup_path.exists():
        graph_query_lookup = read_json(graph_query_lookup_path)
        cached_response = _lookup_response_payload(graph_query_lookup)
        if cached_response is not None:
            return RepositoryGraphQueryResponse.model_validate(cached_response)

    snapshot_manifest = load_snapshot_manifest(
        org_id=org_id,
        repository_id=repository_id,
        snapshot_id=resolved_snapshot_id,
    )
    files_by_path = {
        str(file_entry["file_path"]): file_entry for file_entry in snapshot_manifest["files"]
    }
    seed_files, seed_symbols = repository_graph._resolve_graph_query_seeds(
        triage_manifest=triage_manifest,
        snapshot_manifest=snapshot_manifest,
        request=request,
    )
    inbound_neighbors, outbound_neighbors = repository_graph._snapshot_file_graph_neighbors(
        snapshot_manifest
    )
    effective_seed_files = repository_graph._effective_graph_query_seed_files(
        seed_files=seed_files,
        files_by_path=files_by_path,
        inbound_neighbors=inbound_neighbors,
        outbound_neighbors=outbound_neighbors,
    )
    visited_depths: dict[str, int] = dict.fromkeys(effective_seed_files, 0)
    frontier = list(effective_seed_files)
    while frontier:
        current_file = frontier.pop(0)
        current_depth = visited_depths[current_file]
        if current_depth >= request.max_depth:
            continue
        neighbor_candidates: set[str] = set()
        if request.direction in {"outbound", "both"}:
            neighbor_candidates.update(outbound_neighbors.get(current_file, ()))
        if request.direction in {"inbound", "both"}:
            neighbor_candidates.update(inbound_neighbors.get(current_file, ()))
        for neighbor in sorted(neighbor_candidates):
            if neighbor in visited_depths:
                continue
            if len(visited_depths) >= request.max_nodes:
                break
            visited_depths[neighbor] = current_depth + 1
            frontier.append(neighbor)
        if len(visited_depths) >= request.max_nodes:
            break

    visited_files = set(visited_depths)
    raw_direct_dependencies = sorted(
        {
            dependency
            for seed_file in effective_seed_files
            for dependency in outbound_neighbors.get(seed_file, ())
            if dependency in files_by_path
        }
    )
    raw_direct_dependents = sorted(
        {
            dependent
            for seed_file in effective_seed_files
            for dependent in inbound_neighbors.get(seed_file, ())
            if dependent in files_by_path
        }
    )
    direct_dependencies = repository_graph._collapse_wrapper_neighbors(
        initial_files=raw_direct_dependencies,
        direction="outbound",
        files_by_path=files_by_path,
        inbound_neighbors=inbound_neighbors,
        outbound_neighbors=outbound_neighbors,
    )
    direct_dependents = repository_graph._collapse_wrapper_neighbors(
        initial_files=raw_direct_dependents,
        direction="inbound",
        files_by_path=files_by_path,
        inbound_neighbors=inbound_neighbors,
        outbound_neighbors=outbound_neighbors,
    )
    graph_edges = [
        RepositoryGraphEdge(
            source_file=source_file,
            target_file=target_file,
            edge_type=edge_type,
        )
        for source_file, target_file, edge_type in repository_graph._snapshot_file_graph_edges(
            snapshot_manifest
        )
        if source_file in visited_files and target_file in visited_files
    ]
    graph_nodes: list[RepositoryGraphNode] = []
    impacted_symbols: set[str] = set()
    for file_path in sorted(visited_files):
        file_entry = files_by_path[file_path]
        contained_symbols = [
            str(symbol.get("symbol_name") or "").strip()
            for symbol in repository_graph._actionable_symbols_for_file(file_entry)
        ]
        impacted_symbols.update(symbol for symbol in contained_symbols if symbol)
        graph_nodes.append(
            RepositoryGraphNode(
                file_path=file_path,
                depth=visited_depths[file_path],
                is_seed=file_path in seed_files,
                inbound_count=len(inbound_neighbors.get(file_path, ())),
                outbound_count=len(outbound_neighbors.get(file_path, ())),
                risk_score=repository_graph._file_query_risk_score(
                    file_entry=file_entry,
                    depth=visited_depths[file_path],
                    inbound_count=len(inbound_neighbors.get(file_path, ())),
                    outbound_count=len(outbound_neighbors.get(file_path, ())),
                    is_seed=file_path in effective_seed_files,
                ),
                contained_symbols=contained_symbols[:16],
                parent_child_symbols=repository_graph._file_parent_child_labels(file_entry),
            )
        )
    graph_nodes.sort(key=lambda node: (node.depth, -node.risk_score, node.file_path))
    top_change_risk_files: list[RepositoryGraphImpactItem] = []
    for node in sorted(
        graph_nodes,
        key=lambda entry: (-entry.risk_score, entry.depth, entry.file_path),
    ):
        if node.file_path in effective_seed_files:
            relationship = "seed"
        elif node.file_path in direct_dependents:
            relationship = "dependent"
        elif node.file_path in direct_dependencies:
            relationship = "dependency"
        else:
            relationship = "connected"
        top_change_risk_files.append(
            RepositoryGraphImpactItem(
                file_path=node.file_path,
                depth=node.depth,
                relationship=relationship,
                risk_score=node.risk_score,
                top_symbol=node.contained_symbols[0] if node.contained_symbols else None,
            )
        )

    response = RepositoryGraphQueryResponse(
        repository_id=repository_id,
        snapshot_id=resolved_snapshot_id,
        created_at=_utc_now(),
        seed_file_paths=effective_seed_files,
        seed_symbols=seed_symbols,
        direct_dependencies=direct_dependencies,
        direct_dependents=direct_dependents,
        impacted_files=[node.file_path for node in graph_nodes],
        impacted_symbols=sorted(impacted_symbols),
        graph_nodes=graph_nodes,
        graph_edges=graph_edges,
        top_change_risk_files=top_change_risk_files[: min(24, len(top_change_risk_files))],
    )
    _write_json(
        graph_query_lookup_path,
        {
            "snapshot_id": resolved_snapshot_id,
            "file_path": request.file_path,
            "symbol_name": request.symbol_name,
            "workspace_evidence_bundle_ref": request.workspace_evidence_bundle_ref,
            "direction": request.direction,
            "max_depth": request.max_depth,
            "max_nodes": request.max_nodes,
            "created_at": response.created_at.isoformat(),
            "response": response.model_dump(mode="json"),
        },
    )
    return response


def triage_repository(
    *,
    connector: DataConnector,
    request: RepositoryTriageRequest,
    engine_revision: str,
    require_repository_connector: _RequireRepositoryConnector,
    load_snapshot_manifest: _LoadSnapshotManifest,
    read_json: _ReadJson = _read_json,
    materialized_snapshot: _MaterializedSnapshot = repository_storage.materialized_snapshot,
) -> RepositoryTriageResponse:
    require_repository_connector(connector)
    org_id = str(connector.org_id)
    repository_id = str(connector.id)
    signals_payload = request.signals.model_dump(mode="json")
    triage_lookup_key = _triage_lookup_key(
        snapshot_id=request.snapshot_id,
        signals=signals_payload,
        max_evidence_items=request.max_evidence_items,
        max_snippet_lines=request.max_snippet_lines,
        token_budget=request.token_budget,
        engine_revision=engine_revision,
        ranking_mode=_triage_ranking_mode(),
    )
    triage_lookup_path = _triage_lookup_dir(org_id, repository_id) / f"{triage_lookup_key}.json"
    if triage_lookup_path.exists():
        triage_lookup = read_json(triage_lookup_path)
        evidence_bundle_ref = str(triage_lookup.get("workspace_evidence_bundle_ref") or "").strip()
        if evidence_bundle_ref:
            triage_path = _triage_dir(org_id, repository_id) / f"{evidence_bundle_ref}.json"
            if triage_path.exists():
                cached_response = _lookup_response_payload(triage_lookup)
                if cached_response is not None:
                    return RepositoryTriageResponse.model_validate(cached_response)
                response = RepositoryTriageResponse.model_validate(read_json(triage_path))
                _write_json(
                    triage_lookup_path,
                    {
                        "workspace_evidence_bundle_ref": evidence_bundle_ref,
                        "snapshot_id": request.snapshot_id,
                        "created_at": triage_lookup.get("created_at") or _utc_now().isoformat(),
                        "response": response.model_dump(mode="json"),
                    },
                )
                return response

    snapshot_manifest = load_snapshot_manifest(
        org_id=org_id,
        repository_id=repository_id,
        snapshot_id=request.snapshot_id,
    )
    # AR-OPT-0: time triage ranking into the span the CI presence gate requires.
    with telemetry.span("triage_rank_ms"):
        scores = repository_graph._score_snapshot_files(snapshot_manifest, request.signals)
    if sdk_ranking.sdk_ranking_enabled():
        # AR-OPT-6/7 + SDK "DNA": fuse the keyword/diagnostic heuristic, graph
        # proximity, and (when the Algenta Mojo runtime is available) a batched
        # Mojo ranking lane via Reciprocal Rank Fusion. Falls back to the pure
        # heuristic ordering when the Mojo lane is unavailable.
        heuristic_rank = repository_graph._ranked_paths_by_score(scores)
        graph_rank = repository_graph._ranked_paths_by_score(
            repository_graph._graph_proximity_scores(snapshot_manifest, request.signals)
        )
        rankings = [heuristic_rank, graph_rank]
        # Mojo-rank the heuristic-ordered candidates (the lane bounds internally);
        # if the heuristic found nothing, fall back to the first files.
        ranked_candidates = heuristic_rank or [
            str(file_entry["file_path"]) for file_entry in snapshot_manifest["files"]
        ]
        mojo_scores = sdk_ranking.mojo_repo_rank_scores(
            query_terms=sorted(repository_graph._keywords_from_signals(request.signals)),
            candidates=[{"path": path} for path in ranked_candidates],
        )
        if mojo_scores:
            rankings.append(repository_graph._ranked_paths_by_score(mojo_scores))
        fused = sdk_ranking.reciprocal_rank_fusion(rankings)
        # Restrict to real snapshot files: the signal/graph lanes seed on
        # changed_files / failing_tests, which can be test node-ids (file::test),
        # not paths — matching the flag-off path which only ranks actual files.
        known_paths = {str(file_entry["file_path"]) for file_entry in snapshot_manifest["files"]}
        ordered_files = [
            path
            for path, _ in sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
            if path in known_paths
        ]
    else:
        ordered_entries = sorted(
            snapshot_manifest["files"],
            key=lambda item: (scores.get(item["file_path"], 0.0), item["token_estimate"]),
            reverse=True,
        )
        ordered_files = [
            file_entry["file_path"]
            for file_entry in ordered_entries
            if scores.get(file_entry["file_path"], 0.0) > 0
        ]
    suspect_files = ordered_files[: request.max_evidence_items]
    if not suspect_files and snapshot_manifest["files"]:
        suspect_files = [
            entry["file_path"]
            for entry in snapshot_manifest["files"][: min(3, len(snapshot_manifest["files"]))]
        ]

    diagnostics_by_path = repository_graph._group_diagnostics_by_snapshot_path(
        snapshot_manifest, request.signals.diagnostics
    )

    created_at = _utc_now()
    evidence_items: list[RepositoryEvidenceItem] = []
    suspect_symbols: list[str] = []
    files_by_path = {
        str(file_entry["file_path"]): file_entry for file_entry in snapshot_manifest["files"]
    }
    with materialized_snapshot(snapshot_manifest) as root_path:
        for rank, file_path in enumerate(suspect_files, start=1):
            file_entry = files_by_path[file_path]
            snippet, symbol_name = repository_graph._snippet_for_file(
                root_path=root_path,
                file_entry=file_entry,
                file_path=file_path,
                diagnostics=diagnostics_by_path.get(file_path, ()),
                max_snippet_lines=request.max_snippet_lines,
            )
            if symbol_name:
                suspect_symbols.append(symbol_name)
            summary_parts = []
            if diagnostics_by_path.get(file_path):
                summary_parts.append(diagnostics_by_path[file_path][0].message)
            if file_path in request.signals.changed_files:
                summary_parts.append("recently changed")
            if file_path in request.signals.failing_tests:
                summary_parts.append("currently failing test")
            summary = "; ".join(summary_parts) or f"Suspicious file ranked #{rank}."
            evidence_items.append(
                RepositoryEvidenceItem(
                    evidence_id=_stable_identifier(
                        "evidence",
                        {"file_path": file_path, "rank": rank, "snapshot_id": request.snapshot_id},
                    ),
                    rank=rank,
                    source_type="repository_file",
                    source_ref=file_path,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    summary=summary,
                    snippet=snippet,
                    token_count=min(request.token_budget, _estimate_tokens(snippet)),
                    score=float(scores.get(file_path, 1.0)),
                )
            )

    bounded_items: list[RepositoryEvidenceItem] = []
    running_tokens = 0
    for item in evidence_items:
        if bounded_items and running_tokens + item.token_count > request.token_budget:
            break
        bounded_items.append(item)
        running_tokens += item.token_count
    evidence_items = bounded_items
    suspect_files = [item.file_path for item in evidence_items if item.file_path]
    evidence_bundle_token_count = sum(item.token_count for item in evidence_items)
    raw_repo_token_estimate = int(snapshot_manifest["raw_repo_token_estimate"])
    reduction_ratio = (
        max(raw_repo_token_estimate / max(evidence_bundle_token_count, 1), 1.0)
        if raw_repo_token_estimate
        else 1.0
    )
    evidence_bundle_ref = _stable_identifier(
        "evidence_bundle",
        {
            "snapshot_id": request.snapshot_id,
            "signals": request.signals.model_dump(mode="json"),
            "items": [item.model_dump(mode="json") for item in evidence_items],
        },
    )
    triage_path = _triage_dir(org_id, repository_id) / f"{evidence_bundle_ref}.json"
    parquet_path = _triage_dir(org_id, repository_id) / f"{evidence_bundle_ref}.parquet"
    if not triage_path.exists():
        triage_path.parent.mkdir(parents=True, exist_ok=True)
        records = [
            WorkspaceEvidenceBundleRecord(
                repository_id=repository_id,
                snapshot_id=request.snapshot_id,
                evidence_bundle_id=evidence_bundle_ref,
                evidence_id=item.evidence_id,
                source_type=item.source_type,
                source_ref=item.source_ref,
                file_path=item.file_path,
                symbol_name=item.symbol_name,
                summary=item.summary,
                token_count=item.token_count,
                rank=item.rank,
                created_at=created_at,
            )
            for item in evidence_items
        ]
        parquet_path.write_bytes(
            parquet_bytes_from_records(records, record_type=WorkspaceEvidenceBundleRecord)
            if records
            else parquet_bytes_from_records([], record_type=WorkspaceEvidenceBundleRecord)
        )
        manifest = {
            "repository_id": repository_id,
            "snapshot_id": request.snapshot_id,
            "workspace_evidence_bundle_ref": evidence_bundle_ref,
            "created_at": created_at.isoformat(),
            "suspect_files": suspect_files,
            "suspect_symbols": sorted(set(suspect_symbols)),
            "raw_repo_token_estimate": raw_repo_token_estimate,
            "evidence_bundle_token_count": evidence_bundle_token_count,
            "reduction_ratio": reduction_ratio,
            "evidence_items": [item.model_dump(mode="json") for item in evidence_items],
            "signals": signals_payload,
            "workspace_evidence_bundle_artifact": repository_storage._artifact_ref(
                artifact_id=_stable_identifier(
                    "artifact", {"kind": "workspace_evidence_bundle", "id": evidence_bundle_ref}
                ),
                artifact_kind="WorkspaceEvidenceBundle",
                content_hash=repository_storage._hash_file(parquet_path),
                storage_path=parquet_path,
                schema_revision="runtime-internal-contracts-v1",
                created_at=created_at,
            ).model_dump(mode="json"),
        }
        _write_json(triage_path, manifest)
    response = RepositoryTriageResponse.model_validate(read_json(triage_path))
    _write_json(
        triage_lookup_path,
        {
            "workspace_evidence_bundle_ref": evidence_bundle_ref,
            "snapshot_id": request.snapshot_id,
            "created_at": created_at.isoformat(),
            "response": response.model_dump(mode="json"),
        },
    )
    return response
