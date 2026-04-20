from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "source_matrix_runtime_benchmark.py"
)
_SPEC = importlib.util.spec_from_file_location("source_matrix_runtime_benchmark", _BENCHMARK_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load benchmark module from {_BENCHMARK_PATH}")
_BENCHMARK = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _BENCHMARK
_SPEC.loader.exec_module(_BENCHMARK)

TEST_FILES = _BENCHMARK.TEST_FILES
_as_scalar_count = _BENCHMARK._as_scalar_count
_discover_local_csv_paths = _BENCHMARK._discover_local_csv_paths
_discover_local_parquet_paths = _BENCHMARK._discover_local_parquet_paths
_discover_local_workbook_paths = _BENCHMARK._discover_local_workbook_paths
_percentile = _BENCHMARK._percentile
_register_case = _BENCHMARK._register_case


def test_discover_local_csv_paths_excludes_processed_variants_by_default() -> None:
    paths = _discover_local_csv_paths(include_processed_variants=False)
    names = {path.name for path in paths}

    assert TEST_FILES / "Backlog.csv" in paths
    assert TEST_FILES / "Bookings.csv" in paths
    assert "Renamed_df_aar_electronics_master_sheet_1.csv" not in names


def test_discover_local_csv_paths_includes_processed_variants_when_requested() -> None:
    paths = _discover_local_csv_paths(include_processed_variants=True)

    assert TEST_FILES / "Processed" / "Renamed_df_aar_electronics_master_sheet_1.csv" in paths
    assert len(paths) > len(_discover_local_csv_paths(include_processed_variants=False))


def test_discover_local_workbook_paths_returns_expected_repo_workbooks() -> None:
    paths = _discover_local_workbook_paths()

    assert TEST_FILES / "Grayhill - Full Price Book - 01-01-24.xlsx" in paths
    assert TEST_FILES / "QPL Price List_AAR_Expires 20241230.xlsx" in paths


def test_discover_local_parquet_paths_returns_expected_cache_files() -> None:
    paths = _discover_local_parquet_paths()

    assert TEST_FILES / ".algenta_cache" / "Backlog.parquet" in paths
    assert TEST_FILES / ".algenta_cache" / "Inventory.parquet" in paths


def test_scalar_count_normalization_handles_scalar_and_dict() -> None:
    assert _as_scalar_count(7) == 7.0
    assert _as_scalar_count({"value": 11}) == 11.0


def test_percentile_uses_nearest_rank() -> None:
    values = [5.0, 10.0, 15.0, 20.0]

    assert _percentile(values, 50) == 10.0
    assert _percentile(values, 95) == 20.0


@pytest.mark.asyncio
async def test_register_case_uses_canonical_registered_source_name_for_reused_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_register_source(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "status": "already_registered",
            "dataset_id": "shared-source-id",
            "schema": {
                "columns": [
                    {"name": "record_id", "role": "identifier"},
                ]
            },
            "latency_ms": 3.5,
            "planner_prewarm_ms": 1.2,
        }

    monkeypatch.setattr(_BENCHMARK, "register_source", _fake_register_source)
    monkeypatch.setattr(
        _BENCHMARK.reg,
        "get_source_entry",
        lambda org_id, source_id: {"id": source_id, "name": "LocalCsv053"},
    )

    case = await _register_case(
        auth={"org_id": "bench-org"},
        label="Local CSV duplicate-content fixture",
        category="local_csv",
        origin="test_files/distribution_price_list_aar_with_cleaned_part_number.csv",
        source=_BENCHMARK.DataSource(
            name="LocalCsv054",
            csv="record_id,value\n1,2\n",
        ),
        expected_count=1,
    )

    assert case.dataset_id == "shared-source-id"
    assert case.source_name == "LocalCsv053"
    assert case.metric_column == "record_id"
