from __future__ import annotations

from typing import Any


def build_registration_metadata_updates(
    *,
    dataset_name: str,
    connector_id: str | None,
    visibility: str,
    owner_user_id: str | None,
    owner_key_id: str | None,
    description: str | None,
    selection: dict[str, Any] | None,
    connection_type: str | None,
    provider: str | None,
    refreshable: bool | None,
    source_definition: dict[str, Any] | None,
    discovery_labels: dict[str, Any] | None,
    discovery_metadata: dict[str, Any] | None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    return {
        "dataset_name": dataset_name,
        "connector_id": connector_id,
        "visibility": visibility,
        "owner_user_id": owner_user_id,
        "owner_key_id": owner_key_id,
        # Workspace scope for sub-tenancy. None → key dropped by register_source's
        # not-None filter → entry has no workspace_id → org-wide/legacy (read gate
        # only exposes it to unscoped platform calls).
        "workspace_id": workspace_id,
        "description": description,
        "selection": selection,
        "connection_type": connection_type,
        "provider": provider,
        "refreshable": refreshable,
        "source_definition": source_definition,
        "discovery_labels": discovery_labels,
        "discovery_metadata": discovery_metadata,
        "decision_mode": "deterministic_only",
    }


def build_registration_provenance(
    *,
    captured_at: str,
    connection_type: str | None,
    provider: str | None,
    selection: dict[str, Any] | None,
    source_definition: dict[str, Any] | None,
    dataset_name: str,
) -> dict[str, Any]:
    return {
        "captured_at": captured_at,
        "connection_type": connection_type,
        "provider": provider,
        "selection": selection,
        "source_definition": source_definition,
        "dataset_name": dataset_name,
    }


def build_freshness_policy(refreshable: bool | None) -> dict[str, Any]:
    return {
        "refreshable": bool(refreshable),
        "mode": "manual_refresh" if refreshable else "immutable_snapshot",
    }


def build_already_registered_response(
    *,
    source_id: str,
    source_name: str,
    dataset_name: str,
    schema: dict[str, Any],
    row_count: int | None = None,
    planner_cache_hit: bool,
    planner_schema_revision: str,
    planner_prewarm_ms: float,
    latency_ms: float,
) -> dict[str, Any]:
    resolved_row_count = row_count
    if resolved_row_count is None:
        schema_row_count = schema.get("row_count")
        if isinstance(schema_row_count, int):
            resolved_row_count = schema_row_count
    return {
        "source_id": source_id,
        "dataset_id": source_id,
        "name": source_name,
        "dataset_name": dataset_name,
        "status": "already_registered",
        "ingest_mode": "cache_reuse",
        "row_count": resolved_row_count,
        "schema": schema,
        "mojo_profiling_status": schema.get("mojo_profiling_status") or {},
        "planner_cache_hit": planner_cache_hit,
        "planner_schema_revision": planner_schema_revision,
        "planner_prewarm_ms": planner_prewarm_ms,
        "latency_ms": latency_ms,
    }


def build_registered_source_response(
    *,
    source_id: str,
    source_name: str,
    dataset_name: str,
    ingest_mode: str,
    row_count: int,
    schema: dict[str, Any],
    mojo_profiling_status: dict[str, Any],
    connections_found: list[dict[str, Any]],
    join_candidates_considered: int,
    join_existing_total: int,
    join_scan_mode: str,
    join_candidate_limit: int,
    join_candidate_min_score: float,
    planner_cache_hit: bool,
    planner_schema_revision: str,
    planner_prewarm_ms: float,
    latency_ms: float,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "dataset_id": source_id,
        "name": source_name,
        "dataset_name": dataset_name,
        "status": "registered",
        "ingest_mode": ingest_mode,
        "row_count": row_count,
        "schema": schema,
        "mojo_profiling_status": mojo_profiling_status,
        "connections_found": connections_found,
        "join_candidates_considered": join_candidates_considered,
        "join_existing_total": join_existing_total,
        "join_scan_mode": join_scan_mode,
        "join_candidate_limit": join_candidate_limit,
        "join_candidate_min_score": join_candidate_min_score,
        "planner_cache_hit": planner_cache_hit,
        "planner_schema_revision": planner_schema_revision,
        "planner_prewarm_ms": planner_prewarm_ms,
        "latency_ms": latency_ms,
    }
