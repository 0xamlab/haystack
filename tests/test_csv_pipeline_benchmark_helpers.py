from __future__ import annotations

import pytest

from tests.integration import test_csv_pipeline


def test_validate_mapping_benchmark_accepts_small_fixture_latency_budget() -> None:
    test_csv_pipeline._validate_mapping_benchmark("PART_NUMBER_Anomalies.csv", 47, 0.2)


def test_validate_mapping_benchmark_accepts_large_fixture_throughput_budget() -> None:
    test_csv_pipeline._validate_mapping_benchmark("bookings_new.csv", 17_719, 7.5)


def test_validate_mapping_benchmark_rejects_slow_large_fixture_throughput() -> None:
    with pytest.raises(AssertionError, match="throughput"):
        test_csv_pipeline._validate_mapping_benchmark("bookings_new.csv", 17_719, 25.0)


def test_validate_mapping_benchmark_rejects_small_fixture_latency_regression() -> None:
    with pytest.raises(AssertionError, match="expected < 1000ms"):
        test_csv_pipeline._validate_mapping_benchmark("PART_NUMBER_Anomalies.csv", 47, 1.5)
