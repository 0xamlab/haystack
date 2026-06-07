from apps.api_server.services.source_registration_responses import (
    build_already_registered_response,
    build_freshness_policy,
    build_registered_source_response,
    build_registration_metadata_updates,
    build_registration_provenance,
)


def test_build_registration_metadata_updates_preserves_source_contract() -> None:
    metadata = build_registration_metadata_updates(
        dataset_name="Orders dataset",
        connector_id="connector-1",
        visibility="private",
        owner_user_id="user-1",
        owner_key_id="key-1",
        description="snapshot",
        selection={"table": "orders"},
        connection_type="postgres",
        provider="postgres",
        refreshable=True,
        source_definition={"table": "orders"},
        discovery_labels={"entity_noun": "table"},
        discovery_metadata={"scope_noun": "catalog", "count_kind": "exact"},
    )

    assert metadata == {
        "dataset_name": "Orders dataset",
        "connector_id": "connector-1",
        "visibility": "private",
        "owner_user_id": "user-1",
        "owner_key_id": "key-1",
        "description": "snapshot",
        "selection": {"table": "orders"},
        "connection_type": "postgres",
        "provider": "postgres",
        "refreshable": True,
        "source_definition": {"table": "orders"},
        "discovery_labels": {"entity_noun": "table"},
        "discovery_metadata": {"scope_noun": "catalog", "count_kind": "exact"},
        "decision_mode": "deterministic_only",
        "workspace_id": None,
    }


def test_build_registration_provenance_and_freshness_policy_are_deterministic() -> None:
    provenance = build_registration_provenance(
        captured_at="2026-04-23T20:00:00+00:00",
        connection_type="s3",
        provider="s3",
        selection={"path": "orders.csv"},
        source_definition={"url": "https://example.com/orders.csv"},
        dataset_name="Orders dataset",
    )
    freshness = build_freshness_policy(refreshable=False)

    assert provenance == {
        "captured_at": "2026-04-23T20:00:00+00:00",
        "connection_type": "s3",
        "provider": "s3",
        "selection": {"path": "orders.csv"},
        "source_definition": {"url": "https://example.com/orders.csv"},
        "dataset_name": "Orders dataset",
    }
    assert freshness == {
        "refreshable": False,
        "mode": "immutable_snapshot",
    }


def test_build_already_registered_response_uses_cache_reuse_defaults() -> None:
    response = build_already_registered_response(
        source_id="src_123",
        source_name="Orders",
        dataset_name="Orders dataset",
        schema={"row_count": 25, "mojo_profiling_status": {"status": "enabled"}},
        planner_cache_hit=True,
        planner_schema_revision="rev-1",
        planner_prewarm_ms=12.5,
        latency_ms=18.4,
    )

    assert response == {
        "source_id": "src_123",
        "dataset_id": "src_123",
        "name": "Orders",
        "dataset_name": "Orders dataset",
        "status": "already_registered",
        "ingest_mode": "cache_reuse",
        "row_count": 25,
        "schema": {"row_count": 25, "mojo_profiling_status": {"status": "enabled"}},
        "mojo_profiling_status": {"status": "enabled"},
        "planner_cache_hit": True,
        "planner_schema_revision": "rev-1",
        "planner_prewarm_ms": 12.5,
        "latency_ms": 18.4,
    }


def test_build_registered_source_response_preserves_join_metrics() -> None:
    response = build_registered_source_response(
        source_id="src_456",
        source_name="Customers",
        dataset_name="Customers dataset",
        ingest_mode="loaded",
        row_count=25,
        schema={"columns": ["customer_id"]},
        mojo_profiling_status={"status": "disabled", "reason": "fallback"},
        connections_found=[{"source": "orders"}],
        join_candidates_considered=4,
        join_existing_total=9,
        join_scan_mode="scored",
        join_candidate_limit=7,
        join_candidate_min_score=0.35,
        planner_cache_hit=False,
        planner_schema_revision="rev-2",
        planner_prewarm_ms=41.0,
        latency_ms=88.2,
    )

    assert response == {
        "source_id": "src_456",
        "dataset_id": "src_456",
        "name": "Customers",
        "dataset_name": "Customers dataset",
        "status": "registered",
        "ingest_mode": "loaded",
        "row_count": 25,
        "schema": {"columns": ["customer_id"]},
        "mojo_profiling_status": {"status": "disabled", "reason": "fallback"},
        "connections_found": [{"source": "orders"}],
        "join_candidates_considered": 4,
        "join_existing_total": 9,
        "join_scan_mode": "scored",
        "join_candidate_limit": 7,
        "join_candidate_min_score": 0.35,
        "planner_cache_hit": False,
        "planner_schema_revision": "rev-2",
        "planner_prewarm_ms": 41.0,
        "latency_ms": 88.2,
    }
