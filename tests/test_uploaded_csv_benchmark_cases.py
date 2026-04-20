from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS_DIR = ROOT / "benchmarks"
sys.path.insert(0, str(BENCHMARKS_DIR))

# ruff: noqa: E402
from uploaded_csv_spec_reconstruction_benchmark import _build_hint_cases


def test_uploaded_csv_hint_cases_match_current_cross_source_expectations() -> None:
    cases = {case.label: case for case in _build_hint_cases()}

    assert cases["Q9"].dim_hint == "pos inventory type"
    assert cases["Q9"].exact_case.group_source == "POSNew"
    assert cases["Q9"].exact_case.group_column == "INVENTORY_TYPE"

    assert cases["Q10"].dim_hint == "pos ohvendname"
    assert cases["Q10"].exact_case.group_source == "POSNew"
    assert cases["Q10"].exact_case.group_column == "OHVENDNAME"
