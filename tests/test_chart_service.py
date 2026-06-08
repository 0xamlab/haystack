from __future__ import annotations

import random

from apps.api_server.services.chart_service import build_histogram


def test_build_histogram_preserves_total_count_for_seeded_boundary_case() -> None:
    rng = random.Random(8)
    outcomes = [rng.gauss(100, 20) for _ in range(1000)]

    result = build_histogram(outcomes=outcomes, n_bins=30, unit="USD", title="Test")

    assert result["source"] == "python_computed"
    assert result["stats"]["n"] == 1000
    assert sum(bin_record["count"] for bin_record in result["bins"]) == 1000


def test_build_histogram_preserves_total_count_for_large_seeded_boundary_case() -> None:
    rng = random.Random(6)
    outcomes = [rng.gauss(0, 1) for _ in range(100000)]

    result = build_histogram(outcomes=outcomes, n_bins=50)

    assert result["stats"]["n"] == 100000
    assert len(result["bins"]) == 50
    assert sum(bin_record["count"] for bin_record in result["bins"]) == 100000
