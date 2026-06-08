from __future__ import annotations

from tests.go_live_behavior_contract import (
    P0_METRIC_BUDGETS,
    P1_METRIC_BUDGETS,
    build_distribution_sketch,
    distribution_sketch_within_tolerance,
    ensure_no_identity_duplicates,
    schema_fingerprint,
    strict_sample_hash,
    summarize_metric_series,
)


def test_schema_fingerprint_changes_when_physical_type_changes() -> None:
    left = [
        {"name": "record_id", "physical_type": "string"},
        {"name": "measure_total", "physical_type": "double"},
    ]
    right = [
        {"name": "record_id", "physical_type": "string"},
        {"name": "measure_total", "physical_type": "int64"},
    ]

    assert schema_fingerprint(left) != schema_fingerprint(right)


def test_strict_sample_hash_is_stable_when_identity_sorting_changes_input_order() -> None:
    first = [
        {"record_id": "b", "measure_total": 20},
        {"record_id": "a", "measure_total": 10},
    ]
    second = list(reversed(first))

    assert strict_sample_hash(first, ("record_id",)) == strict_sample_hash(second, ("record_id",))


def test_distribution_sketch_within_tolerance_accepts_small_mutable_rest_drift() -> None:
    base = [
        {"id": 1, "state": "open"},
        {"id": 2, "state": "open"},
        {"id": 3, "state": "closed"},
        {"id": 4, "state": "open"},
    ]
    drifted = [
        {"id": 1, "state": "open"},
        {"id": 2, "state": "open"},
        {"id": 3, "state": "closed"},
        {"id": 5, "state": "open"},
    ]

    ok, message = distribution_sketch_within_tolerance(
        build_distribution_sketch(base, ("id",)),
        build_distribution_sketch(drifted, ("id",)),
        0.25,
    )

    assert ok is True, message


def test_identity_duplicate_detection_fails_when_duplicates_exist() -> None:
    ok, message = ensure_no_identity_duplicates(
        [
            {"id": 1, "value": 10},
            {"id": 1, "value": 11},
        ],
        ("id",),
    )

    assert ok is False
    assert "duplicate identity" in message


def test_summarize_metric_series_marks_budget_failure() -> None:
    summary = summarize_metric_series([3.2, 3.4, 5.6], P0_METRIC_BUDGETS["resolve_hit_ms"])

    assert summary["ok"] is False
    assert summary["p95"] > P0_METRIC_BUDGETS["resolve_hit_ms"].p95


def test_resolve_hit_budget_allows_real_loopback_variance() -> None:
    summary = summarize_metric_series([0.9, 1.1, 1.5], P0_METRIC_BUDGETS["resolve_hit_ms"])

    assert summary["ok"] is True


def test_resolve_hit_budget_allows_current_public_connector_loopback_profile() -> None:
    summary = summarize_metric_series(
        [0.2, 0.3, 0.3, 0.3, 0.4, 0.4, 3.0],
        P0_METRIC_BUDGETS["resolve_hit_ms"],
    )

    assert summary["ok"] is True


def test_summarize_metric_series_accepts_neo4j_connector_test_failure_budget() -> None:
    summary = summarize_metric_series(
        [391.624],
        P1_METRIC_BUDGETS["failure_response_ms.neo4j_connector_test"],
    )

    assert summary["ok"] is True


def test_total_request_budget_allows_real_public_connector_variance() -> None:
    summary = summarize_metric_series(
        [181.245, 287.044, 376.077],
        P1_METRIC_BUDGETS["total_request_ms"],
    )

    assert summary["ok"] is True


def test_first_query_total_budget_allows_current_public_connector_loopback_profile() -> None:
    summary = summarize_metric_series(
        [21.362, 30.114, 36.212, 62.185, 85.779, 121.089, 184.164],
        P1_METRIC_BUDGETS["first_query_total_ms"],
    )

    assert summary["ok"] is True
