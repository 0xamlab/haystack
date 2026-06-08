from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from tests import go_live_fivetran_verify as verification


def _healthy_connection_payload(*, succeeded_at: str) -> dict[str, object]:
    return {
        "data": {
            "paused": False,
            "succeeded_at": succeeded_at,
            "status": {
                "setup_state": "connected",
                "sync_state": "scheduled",
                "schema_status": "ready",
            },
            "setup_tests": [{"title": "Connection", "status": "PASSED"}],
        }
    }


def _single_connector_selection_lock() -> dict[str, object]:
    return {
        "inventory_version": "inv",
        "selection_version": "sel",
        "selected_connectors": [
            {
                "connector_slug": "salesforce",
                "display_name": "Salesforce",
                "family": "application",
                "docs_path": "/docs/connectors/applications/salesforce",
                "release_class": "ga",
                "plan_class": "standard",
                "classification_confidence": "high",
                "schema_complexity": "high",
                "join_complexity": "high",
                "selection_bucket": "crm_marketing_support",
                "source_type": "api",
                "nested_json": True,
                "wide_table": True,
                "high_churn_rest": False,
                "append_only_event": False,
            }
        ],
    }


def test_manifest_destination_defaults_ratio_and_requires_freshness_budget() -> None:
    destination = verification.FivetranManifestDestination.model_validate(
        {
            "connection_id": "conn",
            "table": "DB.SCHEMA.TABLE",
            "expected_core_tables": ["DB.SCHEMA.TABLE"],
            "max_data_lag_minutes": 60,
        }
    )

    assert destination.minimum_row_count == 1
    assert destination.minimum_expected_ratio == 0.8

    with pytest.raises(ValidationError, match="max_data_lag_minutes"):
        verification.FivetranManifestDestination.model_validate(
            {
                "connection_id": "conn",
                "table": "DB.SCHEMA.TABLE",
                "expected_core_tables": ["DB.SCHEMA.TABLE"],
            }
        )


def test_validate_manifest_against_selection_lock_rejects_version_and_metadata_drift() -> None:
    inventory_lock, selection_lock = (
        verification.ensure_inventory_and_selection_locks_are_consistent()
    )
    payload = verification.build_example_manifest(selection_lock)
    document = verification.FivetranManifestDocument.model_validate(payload)

    verification.validate_manifest_against_selection_lock(
        document,
        inventory_lock=inventory_lock,
        selection_lock=selection_lock,
    )

    tampered_version = json.loads(json.dumps(payload))
    tampered_version["selection_version"] = "tampered"
    with pytest.raises(Exception, match="selection_version"):
        verification.validate_manifest_against_selection_lock(
            verification.FivetranManifestDocument.model_validate(tampered_version),
            inventory_lock=inventory_lock,
            selection_lock=selection_lock,
        )

    tampered_metadata = json.loads(json.dumps(payload))
    tampered_metadata["connectors"][0]["family"] = "tampered"
    with pytest.raises(Exception, match="metadata or ordering drifted"):
        verification.validate_manifest_against_selection_lock(
            verification.FivetranManifestDocument.model_validate(tampered_metadata),
            inventory_lock=inventory_lock,
            selection_lock=selection_lock,
        )


def test_validate_baseline_lock_payload_detects_hash_drift() -> None:
    payload = verification.build_empty_baseline_lock()
    verification.validate_baseline_lock_payload(payload)

    tampered = json.loads(json.dumps(payload))
    tampered["entries"] = [{"connector_slug": "salesforce"}]
    with pytest.raises(Exception, match="Baseline lock hash mismatch"):
        verification.validate_baseline_lock_payload(tampered)


def test_placeholder_reason_lists_exact_destination_fields() -> None:
    destination = verification.FivetranManifestDestination.model_validate(
        {
            "connection_id": "__REPLACE_WITH_CONNECTION_ID__",
            "table": "__REPLACE_WITH_TABLE__",
            "expected_core_tables": ["valid.table", "__REPLACE_WITH_EXPECTED_TABLE__"],
            "max_data_lag_minutes": 60,
        }
    )

    reason, fields = verification._placeholder_reason("snowflake", destination)

    assert fields == (
        "snowflake.connection_id",
        "snowflake.table",
        "snowflake.expected_core_tables[1]",
    )
    assert reason == (
        "snowflake manifest still contains placeholder values in: "
        "snowflake.connection_id, snowflake.table, snowflake.expected_core_tables[1]"
    )


def test_resolve_fivetran_api_credentials_accepts_keys_txt_system_key(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        verification,
        "load_keys_txt_assignments",
        lambda: {
            "FIVETRAN_SYSTEM_KEY": "ft_example_key",
            "FIVETRAN_SYSTEM_KEY_SECRET": "ft_example_secret",
        },
    )
    monkeypatch.delenv("DE_TEST_FIVETRAN_API_KEY", raising=False)
    monkeypatch.delenv("DE_TEST_FIVETRAN_API_SECRET", raising=False)
    monkeypatch.delenv("FIVETRAN_SYSTEM_KEY", raising=False)
    monkeypatch.delenv("FIVETRAN_SYSTEM_KEY_SECRET", raising=False)

    resolved = verification._resolve_fivetran_api_credentials()

    assert resolved is not None
    assert resolved.api_key == "ft_example_key"
    assert resolved.api_secret == "ft_example_secret"
    assert resolved.key_source == "keys.txt:FIVETRAN_SYSTEM_KEY"
    assert resolved.secret_source == "keys.txt:FIVETRAN_SYSTEM_KEY_SECRET"
    assert verification.required_fivetran_envs_missing() == ()


def test_discover_live_connection_candidates_matches_selected_slug_and_destination() -> None:
    class _ApiClient:
        def list_destinations(self) -> list[dict[str, object]]:
            return [
                {"id": "dest-snow", "group_id": "group-snow", "service": "snowflake"},
                {"id": "dest-bq", "group_id": "group-bq", "service": "google_bigquery"},
            ]

        def list_connections(self) -> list[dict[str, object]]:
            return [
                {"id": "conn-snow", "group_id": "group-snow", "service": "salesforce"},
                {"id": "conn-bq", "group_id": "group-bq", "service": "salesforce"},
                {"id": "conn-other", "group_id": "group-snow", "service": "other_connector"},
            ]

    discovery = verification.discover_live_connection_candidates(
        api_client=_ApiClient(),  # type: ignore[arg-type]
        selected_connector_slugs=["salesforce"],
    )

    assert discovery["summary"] == {
        "matched_pairs": 2,
        "matched_candidates": 2,
        "unmatched_candidates": 1,
    }
    assert discovery["matches"]["salesforce:snowflake"][0]["connection_id"] == "conn-snow"
    assert discovery["matches"]["salesforce:bigquery"][0]["connection_id"] == "conn-bq"
    assert discovery["unmatched_candidates"][0]["connection_id"] == "conn-other"


def test_inspect_live_fivetran_account_returns_destinations_connections_and_matches(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        verification,
        "ensure_inventory_and_selection_locks_are_consistent",
        lambda: (
            {"inventory_version": "inv"},
            {
                "selected_connectors": [
                    {
                        "connector_slug": "salesforce",
                        "display_name": "Salesforce",
                    }
                ]
            },
        ),
    )
    monkeypatch.setattr(
        verification,
        "_resolve_fivetran_api_credentials",
        lambda: verification.FivetranCredentialResolution(
            api_key="key",
            api_secret="secret",
            key_source="env:key",
            secret_source="env:secret",
        ),
    )
    monkeypatch.setattr(verification, "required_fivetran_envs_missing", lambda: ())

    class _ApiClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def list_destinations(self) -> list[dict[str, object]]:
            return [
                {"id": "dest-snow", "group_id": "group-snow", "service": "snowflake"},
                {"id": "dest-bq", "group_id": "group-bq", "service": "google_bigquery"},
            ]

        def list_connections(self) -> list[dict[str, object]]:
            return [
                {"id": "conn-snow", "group_id": "group-snow", "service": "salesforce"},
                {"id": "conn-bq", "group_id": "group-bq", "service": "salesforce"},
                {"id": "conn-other", "group_id": "group-snow", "service": "other_connector"},
            ]

        def close(self) -> None:
            return None

    monkeypatch.setattr(verification, "FivetranApiClient", _ApiClient)

    payload = verification.inspect_live_fivetran_account(connector_slugs=("salesforce",))

    assert payload["connector_filter"] == ["salesforce"]
    assert payload["selected_connectors"] == ["salesforce"]
    assert payload["summary"] == {
        "destinations": 2,
        "connections": 3,
        "matched_pairs": 2,
        "matched_candidates": 2,
        "unmatched_candidates": 1,
    }
    assert payload["destinations"][0]["destination_name"] == "snowflake"
    assert payload["connections"][0]["connector_slug"] == "salesforce"
    assert payload["candidate_matches"]["salesforce:snowflake"][0]["connection_id"] == "conn-snow"


def test_hydrate_manifest_connection_ids_from_live_account_updates_unambiguous_placeholders(
    monkeypatch,
    tmp_path,
) -> None:
    selection_lock = _single_connector_selection_lock()
    manifest_payload = verification.build_example_manifest(selection_lock)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

    monkeypatch.setenv("DE_TEST_FIVETRAN_MANIFEST_PATH", str(manifest_path))
    monkeypatch.setenv("DE_TEST_FIVETRAN_API_KEY", "key")
    monkeypatch.setenv("DE_TEST_FIVETRAN_API_SECRET", "secret")
    monkeypatch.setattr(
        verification,
        "ensure_inventory_and_selection_locks_are_consistent",
        lambda: (
            {"inventory_version": "inv", "entries": []},
            selection_lock,
        ),
    )

    class _ApiClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def list_destinations(self) -> list[dict[str, object]]:
            return [
                {"id": "dest-snow", "group_id": "group-snow", "service": "snowflake"},
                {"id": "dest-bq", "group_id": "group-bq", "service": "bigquery"},
            ]

        def list_connections(self) -> list[dict[str, object]]:
            return [
                {"id": "conn-snow", "group_id": "group-snow", "service": "salesforce"},
                {"id": "conn-bq", "group_id": "group-bq", "service": "salesforce"},
            ]

        def close(self) -> None:
            return None

    monkeypatch.setattr(verification, "FivetranApiClient", _ApiClient)

    payload = verification.hydrate_manifest_connection_ids_from_live_account()

    assert payload["changed"] is True
    assert payload["hydrated_paths"] == [
        "salesforce.snowflake.connection_id",
        "salesforce.bigquery.connection_id",
    ]
    assert payload["remaining_placeholder_fields"] == [
        "salesforce.snowflake.table",
        "salesforce.snowflake.expected_core_tables[0]",
        "salesforce.bigquery.table",
        "salesforce.bigquery.expected_core_tables[0]",
    ]


def test_hydrate_manifest_connection_ids_from_live_account_can_filter_to_one_connector(
    monkeypatch,
    tmp_path,
) -> None:
    selection_lock = {
        "inventory_version": "inv",
        "selection_version": "sel",
        "selected_connectors": [
            {
                "connector_slug": "salesforce",
                "display_name": "Salesforce",
                "family": "application",
                "docs_path": "/docs/connectors/applications/salesforce",
                "release_class": "ga",
                "plan_class": "standard",
                "classification_confidence": "high",
                "schema_complexity": "high",
                "join_complexity": "high",
                "selection_bucket": "crm_marketing_support",
                "source_type": "api",
                "nested_json": True,
                "wide_table": True,
                "high_churn_rest": False,
                "append_only_event": False,
            },
            {
                "connector_slug": "hubspot",
                "display_name": "HubSpot",
                "family": "application",
                "docs_path": "/docs/connectors/applications/hubspot",
                "release_class": "ga",
                "plan_class": "standard",
                "classification_confidence": "high",
                "schema_complexity": "high",
                "join_complexity": "high",
                "selection_bucket": "crm_marketing_support",
                "source_type": "api",
                "nested_json": True,
                "wide_table": True,
                "high_churn_rest": False,
                "append_only_event": False,
            },
        ],
    }
    manifest_payload = verification.build_example_manifest(selection_lock)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

    monkeypatch.setenv("DE_TEST_FIVETRAN_MANIFEST_PATH", str(manifest_path))
    monkeypatch.setenv("DE_TEST_FIVETRAN_API_KEY", "key")
    monkeypatch.setenv("DE_TEST_FIVETRAN_API_SECRET", "secret")
    monkeypatch.setattr(
        verification,
        "ensure_inventory_and_selection_locks_are_consistent",
        lambda: (
            {"inventory_version": "inv", "entries": []},
            selection_lock,
        ),
    )
    monkeypatch.setattr(
        verification,
        "discover_live_connection_candidates",
        lambda **kwargs: {
            "matches": {
                "salesforce:snowflake": [{"connection_id": "snow-conn"}],
                "salesforce:bigquery": [{"connection_id": "bq-conn"}],
            },
            "matched_candidates": [],
            "unmatched_candidates": [],
            "summary": {"matched_pairs": 2, "matched_candidates": 2, "unmatched_candidates": 0},
        },
    )

    class _ApiClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def close(self) -> None:
            return None

    monkeypatch.setattr(verification, "FivetranApiClient", _ApiClient)

    payload = verification.hydrate_manifest_connection_ids_from_live_account(
        connector_slugs=("salesforce",),
    )

    updated_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    connectors_by_slug = {
        entry["connector_slug"]: entry for entry in updated_manifest["connectors"]
    }
    assert payload["connector_filter"] == ["salesforce"]
    assert payload["hydrated_paths"] == [
        "salesforce.snowflake.connection_id",
        "salesforce.bigquery.connection_id",
    ]
    assert connectors_by_slug["salesforce"]["snowflake"]["connection_id"] == "snow-conn"
    assert connectors_by_slug["salesforce"]["bigquery"]["connection_id"] == "bq-conn"
    assert (
        connectors_by_slug["hubspot"]["snowflake"]["connection_id"]
        == "__REPLACE_WITH_SNOWFLAKE_CONNECTION_ID__"
    )
    assert (
        connectors_by_slug["hubspot"]["bigquery"]["connection_id"]
        == "__REPLACE_WITH_BIGQUERY_CONNECTION_ID__"
    )
    assert all(path.startswith("salesforce.") for path in payload["remaining_placeholder_fields"])


def test_build_connector_manifest_view_returns_entry_and_placeholder_fields(
    monkeypatch,
    tmp_path,
) -> None:
    selection_lock = _single_connector_selection_lock()
    manifest_payload = verification.build_example_manifest(selection_lock)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    monkeypatch.setenv("DE_TEST_FIVETRAN_MANIFEST_PATH", str(manifest_path))

    payload = verification.build_connector_manifest_view(connector_slug="salesforce")

    assert payload["manifest_path"] == str(manifest_path)
    assert payload["connector_slug"] == "salesforce"
    assert payload["manifest_entry"]["connector_slug"] == "salesforce"
    assert payload["remaining_placeholder_fields"] == [
        "snowflake.connection_id",
        "snowflake.table",
        "snowflake.expected_core_tables[0]",
        "bigquery.connection_id",
        "bigquery.table",
        "bigquery.expected_core_tables[0]",
    ]
    assert payload["next_commands"] == [
        "make go-live-hydrate-fivetran-manifest CONNECTOR=salesforce",
        "make go-live-verify-fivetran-prebaseline CONNECTOR=salesforce",
        "make go-live-refresh-fivetran-baseline CONNECTOR=salesforce",
        "make go-live-verify-fivetran CONNECTOR=salesforce",
    ]


def test_evaluate_preflight_fails_when_sync_is_stale(monkeypatch) -> None:
    now = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(verification, "_utc_now", lambda: now)

    state, reasons, lag = verification._evaluate_preflight(
        payload=_healthy_connection_payload(
            succeeded_at=(now - timedelta(minutes=90)).isoformat().replace("+00:00", "Z")
        ),
        destination=verification.FivetranManifestDestination.model_validate(
            {
                "connection_id": "conn",
                "table": "DB.SCHEMA.TABLE",
                "expected_core_tables": ["DB.SCHEMA.TABLE"],
                "max_data_lag_minutes": 60,
            }
        ),
    )

    assert state == "fail"
    assert lag is not None and lag > 60
    assert "max_data_lag_minutes" in reasons[0]


def test_evaluate_preflight_blocks_without_sync_timestamp() -> None:
    state, reasons, lag = verification._evaluate_preflight(
        payload={
            "data": {
                "paused": False,
                "status": {"setup_state": "connected", "sync_state": "scheduled"},
            }
        },
        destination=verification.FivetranManifestDestination.model_validate(
            {
                "connection_id": "conn",
                "table": "DB.SCHEMA.TABLE",
                "expected_core_tables": ["DB.SCHEMA.TABLE"],
                "max_data_lag_minutes": 60,
            }
        ),
    )

    assert state == "blocked"
    assert lag is None
    assert "last successful sync timestamp" in reasons[0]


def test_aggregate_connector_state_prefers_fail_then_blocked() -> None:
    passed = verification.DestinationEvaluation("snowflake", "id", "pass", ())
    blocked = verification.DestinationEvaluation("bigquery", "id", "blocked", ("missing baseline",))
    failed = verification.DestinationEvaluation("snowflake", "id", "fail", ("schema mismatch",))

    assert verification._aggregate_connector_state((passed, blocked)) == "blocked"
    assert verification._aggregate_connector_state((failed, blocked)) == "fail"


def test_filter_selected_connectors_returns_requested_subset() -> None:
    selection_entries = [
        {"connector_slug": "github", "display_name": "GitHub"},
        {"connector_slug": "salesforce", "display_name": "Salesforce"},
    ]

    filtered = verification._filter_selected_connectors(
        selection_entries,
        ("salesforce",),
    )

    assert filtered == [{"connector_slug": "salesforce", "display_name": "Salesforce"}]


def test_filter_selected_connectors_rejects_unknown_connector() -> None:
    selection_entries = [
        {"connector_slug": "github", "display_name": "GitHub"},
    ]

    with pytest.raises(
        verification.FivetranVerificationError,
        match="Requested connectors are not part of the frozen top-20 selection: stripe",
    ):
        verification._filter_selected_connectors(selection_entries, ("stripe",))


def test_evaluate_destination_blocks_without_baseline(monkeypatch) -> None:
    destination = verification.FivetranManifestDestination.model_validate(
        {
            "connection_id": "conn",
            "table": "DB.SCHEMA.TABLE",
            "expected_core_tables": ["DB.SCHEMA.TABLE"],
            "identity_columns": ["id"],
            "max_data_lag_minutes": 60,
        }
    )

    class _ApiClient:
        def connection_details(self, _connection_id: str) -> dict[str, object]:
            return _healthy_connection_payload(succeeded_at="2026-04-24T11:30:00Z")

    monkeypatch.setattr(verification, "_utc_now", lambda: datetime(2026, 4, 24, 12, 0, tzinfo=UTC))
    monkeypatch.setattr(verification, "_check_expected_core_tables", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        verification,
        "_sample_records_for_destination",
        lambda *_args, **_kwargs: ([{"id": 1}], [{"name": "id", "physical_type": "int64"}]),
    )
    monkeypatch.setattr(verification, "_count_rows_for_destination", lambda *_args, **_kwargs: 10)

    evaluation, case = verification._evaluate_destination_without_behavior(
        connector_slug="salesforce",
        destination_name="snowflake",
        display_name="Salesforce",
        destination=destination,
        baseline_lock={"entries": []},
        api_client=_ApiClient(),
    )

    assert evaluation.state == "blocked"
    assert "baseline entry is missing" in evaluation.reasons[0]
    assert case is None


def test_evaluate_destination_blocks_on_placeholders_before_api_calls() -> None:
    destination = verification.FivetranManifestDestination.model_validate(
        {
            "connection_id": "__REPLACE_WITH_CONNECTION_ID__",
            "table": "__REPLACE_WITH_TABLE__",
            "expected_core_tables": ["valid.table", "__REPLACE_WITH_EXPECTED_TABLE__"],
            "max_data_lag_minutes": 60,
        }
    )

    class _ApiClient:
        def connection_details(self, _connection_id: str) -> dict[str, object]:
            raise AssertionError(
                "connection_details() should not be called for placeholder-blocked destinations"
            )

    evaluation, case = verification._evaluate_destination_without_behavior(
        connector_slug="salesforce",
        destination_name="snowflake",
        display_name="Salesforce",
        destination=destination,
        baseline_lock={"entries": []},
        api_client=_ApiClient(),
    )

    assert evaluation.state == "blocked"
    assert evaluation.placeholder_fields == (
        "snowflake.connection_id",
        "snowflake.table",
        "snowflake.expected_core_tables[1]",
    )
    assert "snowflake manifest still contains placeholder values" in evaluation.reasons[0]
    assert case is None


def test_evaluate_destination_fails_when_row_count_ratio_drops(monkeypatch) -> None:
    destination = verification.FivetranManifestDestination.model_validate(
        {
            "connection_id": "conn",
            "table": "DB.SCHEMA.TABLE",
            "expected_core_tables": ["DB.SCHEMA.TABLE"],
            "max_data_lag_minutes": 60,
            "minimum_expected_ratio": 0.8,
        }
    )

    class _ApiClient:
        def connection_details(self, _connection_id: str) -> dict[str, object]:
            return _healthy_connection_payload(succeeded_at="2026-04-24T11:30:00Z")

    monkeypatch.setattr(verification, "_utc_now", lambda: datetime(2026, 4, 24, 12, 0, tzinfo=UTC))
    monkeypatch.setattr(verification, "_check_expected_core_tables", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        verification,
        "_sample_records_for_destination",
        lambda *_args, **_kwargs: ([{"id": 1}], [{"name": "id", "physical_type": "int64"}]),
    )
    monkeypatch.setattr(verification, "_count_rows_for_destination", lambda *_args, **_kwargs: 50)

    evaluation, case = verification._evaluate_destination_without_behavior(
        connector_slug="salesforce",
        destination_name="snowflake",
        display_name="Salesforce",
        destination=destination,
        baseline_lock={
            "entries": [
                {
                    "connector_slug": "salesforce",
                    "destination_name": "snowflake",
                    "row_count": 100,
                }
            ]
        },
        api_client=_ApiClient(),
    )

    assert evaluation.state == "fail"
    assert evaluation.observed_ratio == 0.5
    assert "minimum_expected_ratio" in evaluation.reasons[0]
    assert case is None


def test_refresh_baseline_lock_refuses_schema_drift(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(verification, "_utc_now", lambda: datetime(2026, 4, 24, 12, 0, tzinfo=UTC))
    selection_lock = {
        "inventory_version": "inv",
        "selection_version": "sel",
        "selected_connectors": [
            {
                "connector_slug": "salesforce",
                "display_name": "Salesforce",
                "family": "application",
                "docs_path": "/docs/connectors/applications/salesforce",
                "release_class": "ga",
                "plan_class": "standard",
                "classification_confidence": "high",
                "schema_complexity": "high",
                "join_complexity": "high",
                "selection_bucket": "crm_marketing_support",
                "source_type": "api",
                "nested_json": True,
                "wide_table": True,
                "high_churn_rest": False,
                "append_only_event": False,
            }
        ],
    }
    manifest_payload = verification.build_example_manifest(selection_lock)
    manifest_payload["connectors"][0]["snowflake"]["connection_id"] = "snow-conn"
    manifest_payload["connectors"][0]["snowflake"]["table"] = "DB.SCHEMA.TABLE"
    manifest_payload["connectors"][0]["snowflake"]["expected_core_tables"] = ["DB.SCHEMA.TABLE"]
    manifest_payload["connectors"][0]["bigquery"]["connection_id"] = "bq-conn"
    manifest_payload["connectors"][0]["bigquery"]["table"] = "`project.dataset.table`"
    manifest_payload["connectors"][0]["bigquery"]["expected_core_tables"] = [
        "`project.dataset.table`"
    ]

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

    monkeypatch.setenv("DE_TEST_FIVETRAN_MANIFEST_PATH", str(manifest_path))
    monkeypatch.setenv("DE_TEST_FIVETRAN_API_KEY", "key")
    monkeypatch.setenv("DE_TEST_FIVETRAN_API_SECRET", "secret")
    monkeypatch.setattr(
        verification,
        "ensure_inventory_and_selection_locks_are_consistent",
        lambda: (
            {"inventory_version": "inv", "entries": []},
            selection_lock,
        ),
    )

    class _ApiClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def connection_details(self, _connection_id: str) -> dict[str, object]:
            return _healthy_connection_payload(succeeded_at="2026-04-24T11:30:00Z")

        def close(self) -> None:
            return None

    monkeypatch.setattr(verification, "FivetranApiClient", _ApiClient)
    monkeypatch.setattr(verification, "_check_expected_core_tables", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(verification, "_count_rows_for_destination", lambda *_args, **_kwargs: 100)
    schema_sequence = iter(
        [
            ([{"id": 1}], [{"name": "id", "physical_type": "int64"}]),
            ([{"id": "1"}], [{"name": "id", "physical_type": "string"}]),
        ]
    )
    monkeypatch.setattr(
        verification,
        "_sample_records_for_destination",
        lambda *_args, **_kwargs: next(schema_sequence),
    )

    with pytest.raises(Exception, match="schema fingerprint changed"):
        verification.refresh_baseline_lock(sleep_seconds=0, sleep_fn=lambda _seconds: None)


def test_render_fivetran_markdown_report_includes_versions_and_connector_details() -> None:
    payload = {
        "inventory_version": "inv",
        "selection_version": "sel",
        "baseline_version": "base",
        "manifest_version": "manifest",
        "manifest_path": "/tmp/manifest.json",
        "selected_count": 1,
        "missing_api_envs": ["DE_TEST_FIVETRAN_API_KEY"],
        "api_credential_source": {
            "key": "keys.txt:FIVETRAN_SYSTEM_KEY",
            "secret": "keys.txt:FIVETRAN_SYSTEM_KEY_SECRET",
        },
        "account_summary": {"groups": 1, "destinations": 0, "connections": 0},
        "account_summary_error": None,
        "account_blockers": [
            "Fivetran account has no destinations.",
            "Fivetran account has no connections.",
        ],
        "manifest_error": "placeholder manifest",
        "summary": {"pass": 0, "fail": 0, "blocked": 1},
        "next_actions": [
            {
                "code": "create_fivetran_destinations",
                "message": "Create one Snowflake destination and one BigQuery destination in Fivetran.",
                "details": {"required_destinations": ["snowflake", "bigquery"]},
            }
        ],
        "connector_results": [
            {
                "connector_slug": "salesforce",
                "display_name": "Salesforce",
                "state": "blocked",
                "destinations": [
                    {
                        "destination_name": "snowflake",
                        "state": "blocked",
                        "placeholder_fields": ["snowflake.connection_id", "snowflake.table"],
                        "freshness_lag_minutes": None,
                        "observed_ratio": None,
                        "reasons": ["missing baseline"],
                    },
                    {
                        "destination_name": "bigquery",
                        "state": "blocked",
                        "freshness_lag_minutes": 12.0,
                        "observed_ratio": 0.9,
                        "reasons": [],
                    },
                ],
            }
        ],
        "suite_failures": ["selection drift"],
    }
    selection_lock = {
        "selected_connectors": [
            {
                "connector_slug": "salesforce",
                "selection_bucket": "crm_marketing_support",
                "docs_path": "/docs/connectors/applications/salesforce",
                "nested_json": True,
                "wide_table": True,
                "high_churn_rest": False,
                "append_only_event": False,
            }
        ]
    }

    report = verification.render_fivetran_markdown_report(payload, selection_lock=selection_lock)

    assert "# Fivetran Wave-1 Validation Report" in report
    assert "- Inventory version: `inv`" in report
    assert (
        "- API credential source: `keys.txt:FIVETRAN_SYSTEM_KEY` / `keys.txt:FIVETRAN_SYSTEM_KEY_SECRET`"
        in report
    )
    assert "- Account summary: `groups=1` `destinations=0` `connections=0`" in report
    assert "- Account blockers:" in report
    assert "  - Fivetran account has no destinations." in report
    assert (
        "| salesforce | crm_marketing_support | `/docs/connectors/applications/salesforce` | nested_json, wide_table | blocked | blocked | blocked |"
        in report
    )
    assert "### salesforce" in report
    assert "placeholder_fields: snowflake.connection_id, snowflake.table" in report
    assert "missing baseline" in report
    assert "## Next Actions" in report
    assert "`create_fivetran_destinations`" in report
    assert "## Suite Failures" in report


def test_render_fivetran_status_includes_account_summary_and_credential_source() -> None:
    payload = {
        "inventory_version": "inv",
        "selection_version": "sel",
        "baseline_version": "base",
        "manifest_path": "/tmp/manifest.json",
        "selected_count": 1,
        "missing_api_envs": [],
        "api_credential_source": {
            "key": "keys.txt:FIVETRAN_SYSTEM_KEY",
            "secret": "keys.txt:FIVETRAN_SYSTEM_KEY_SECRET",
        },
        "account_summary": {"groups": 1, "destinations": 0, "connections": 0},
        "account_summary_error": None,
        "account_blockers": [
            "Fivetran account has no destinations.",
            "Fivetran account has no connections.",
        ],
        "manifest_error": None,
        "summary": {"pass": 0, "fail": 0, "blocked": 1},
        "next_actions": [
            {
                "code": "create_fivetran_destinations",
                "message": "Create one Snowflake destination and one BigQuery destination in Fivetran.",
                "details": {"required_destinations": ["snowflake", "bigquery"]},
            }
        ],
        "connector_results": [],
        "suite_failures": [],
    }

    rendered = verification.render_fivetran_status(payload)

    assert (
        "API credential source: key=keys.txt:FIVETRAN_SYSTEM_KEY secret=keys.txt:FIVETRAN_SYSTEM_KEY_SECRET"
        in rendered
    )
    assert "Account summary: groups=1 | destinations=0 | connections=0" in rendered
    assert "Account blockers:" in rendered
    assert "  - Fivetran account has no destinations." in rendered
    assert "Next actions:" in rendered
    assert "create_fivetran_destinations" in rendered


def test_build_fivetran_next_actions_for_empty_account_and_manifest_placeholders() -> None:
    payload = {
        "connector_filter": ["github"],
        "missing_api_envs": [],
        "account_summary": {"groups": 1, "destinations": 0, "connections": 0},
        "account_blockers": [
            "Fivetran account has no destinations.",
            "Fivetran account has no connections.",
        ],
        "summary": {"pass": 0, "fail": 0, "blocked": 1},
        "connector_results": [
            {
                "connector_slug": "github",
                "destinations": [
                    {
                        "destination_name": "snowflake",
                        "state": "blocked",
                        "placeholder_fields": [
                            "snowflake.connection_id",
                            "snowflake.table",
                        ],
                        "reasons": [
                            "snowflake manifest still contains placeholder values in: snowflake.connection_id, snowflake.table"
                        ],
                    },
                    {
                        "destination_name": "bigquery",
                        "state": "blocked",
                        "placeholder_fields": [
                            "bigquery.connection_id",
                            "bigquery.table",
                        ],
                        "reasons": [
                            "bigquery manifest still contains placeholder values in: bigquery.connection_id, bigquery.table"
                        ],
                    },
                ],
            }
        ],
    }

    actions = verification.build_fivetran_next_actions(payload)

    assert [action["code"] for action in actions] == [
        "create_fivetran_destinations",
        "create_fivetran_connections",
        "hydrate_manifest_connection_ids",
        "fill_manifest_selectors",
    ]
    assert actions[2]["command"] == "make go-live-hydrate-fivetran-manifest CONNECTOR=github"
    assert actions[3]["details"]["connectors"] == [
        {
            "connector_slug": "github",
            "destinations": {
                "snowflake": ["snowflake.connection_id", "snowflake.table"],
                "bigquery": ["bigquery.connection_id", "bigquery.table"],
            },
        }
    ]


def test_build_fivetran_next_actions_for_missing_baseline_only() -> None:
    payload = {
        "connector_filter": ["github"],
        "missing_api_envs": [],
        "account_summary": {"groups": 1, "destinations": 2, "connections": 2},
        "account_blockers": [],
        "summary": {"pass": 0, "fail": 0, "blocked": 1},
        "connector_results": [
            {
                "connector_slug": "github",
                "destinations": [
                    {
                        "destination_name": "snowflake",
                        "state": "blocked",
                        "placeholder_fields": [],
                        "reasons": ["snowflake baseline entry is missing."],
                    },
                    {
                        "destination_name": "bigquery",
                        "state": "blocked",
                        "placeholder_fields": [],
                        "reasons": ["bigquery baseline entry is missing."],
                    },
                ],
            }
        ],
    }

    actions = verification.build_fivetran_next_actions(payload)

    assert [action["code"] for action in actions] == [
        "refresh_fivetran_baseline",
        "run_fivetran_strict_verify",
    ]
    assert actions[0]["command"] == "make go-live-refresh-fivetran-baseline CONNECTOR=github"
    assert actions[1]["command"] == "make go-live-verify-fivetran CONNECTOR=github"
