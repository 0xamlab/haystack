from __future__ import annotations

import json

import pytest

from tests.go_live_fivetran_inventory import (
    DIVERSITY_CONSTRAINTS,
    MANIFEST_EXAMPLE_PATH,
    SELECTION_BUCKET_QUOTAS,
    ensure_inventory_and_selection_locks_are_consistent,
    validate_inventory_lock_payload,
    validate_selection_lock_payload,
)


def test_fivetran_lock_files_are_self_consistent() -> None:
    inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()

    assert inventory_lock["inventory_version"]
    assert selection_lock["selection_version"]
    assert len(selection_lock["selected_connectors"]) == 20


def test_wave_one_selection_only_contains_high_confidence_ga_standard_connectors() -> None:
    _inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()

    for entry in selection_lock["selected_connectors"]:
        assert entry["release_class"] == "ga"
        assert entry["plan_class"] == "standard"
        assert entry["classification_confidence"] == "high"


def test_wave_one_selection_satisfies_bucket_quotas_and_diversity_constraints() -> None:
    _inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()
    selected = selection_lock["selected_connectors"]

    for bucket, required_count in SELECTION_BUCKET_QUOTAS.items():
        actual_count = sum(1 for entry in selected if entry["selection_bucket"] == bucket)
        assert actual_count == required_count

    for trait_name, required_count in DIVERSITY_CONSTRAINTS.items():
        actual_count = sum(1 for entry in selected if entry[trait_name] is True)
        assert actual_count >= required_count


def test_example_manifest_matches_frozen_top20_selection() -> None:
    _inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()
    manifest_payload = json.loads(MANIFEST_EXAMPLE_PATH.read_text(encoding="utf-8"))

    assert manifest_payload["inventory_version"] == selection_lock["inventory_version"]
    assert manifest_payload["selection_version"] == selection_lock["selection_version"]
    selected_slugs = [entry["connector_slug"] for entry in selection_lock["selected_connectors"]]
    manifest_slugs = [entry["connector_slug"] for entry in manifest_payload["connectors"]]

    assert manifest_slugs == selected_slugs
    for connector, selected_entry in zip(
        manifest_payload["connectors"],
        selection_lock["selected_connectors"],
        strict=True,
    ):
        assert connector["connector_slug"] == selected_entry["connector_slug"]
        assert connector["display_name"] == selected_entry["display_name"]
        assert connector["family"] == selected_entry["family"]
        assert connector["docs_path"] == selected_entry["docs_path"]
        assert connector["classification_confidence"] == selected_entry["classification_confidence"]
        assert connector["snowflake"]["max_data_lag_minutes"] == 60
        assert connector["bigquery"]["minimum_expected_ratio"] == 0.8


def test_inventory_and_selection_validation_fail_on_hash_drift() -> None:
    inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()

    tampered_inventory = json.loads(json.dumps(inventory_lock))
    tampered_inventory["entries"][0]["display_name"] = "tampered"
    with pytest.raises(Exception, match="Inventory lock hash mismatch"):
        validate_inventory_lock_payload(tampered_inventory)

    tampered_selection = json.loads(json.dumps(selection_lock))
    tampered_selection["selected_connectors"][0]["display_name"] = "tampered"
    with pytest.raises(Exception, match="Selection lock hash mismatch"):
        validate_selection_lock_payload(
            tampered_selection,
            inventory_version=inventory_lock["inventory_version"],
        )
