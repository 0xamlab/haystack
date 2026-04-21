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
_parse_csv_records = _BENCHMARK._parse_csv_records
_percentile = _BENCHMARK._percentile
_prepare_local_csv_cases = _BENCHMARK._prepare_local_csv_cases
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


def test_parse_csv_records_can_allow_empty_exports() -> None:
    empty_path = (
        TEST_FILES
        / "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv"
    )

    csv_text, records = _parse_csv_records(empty_path, allow_empty=True)

    assert "Store,External Store ID" in csv_text
    assert records == []


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
                ],
                "planner_profile": {
                    "record_id": {
                        "total_count": 1,
                    }
                },
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
    assert case.expected_count == 1


@pytest.mark.asyncio
async def test_register_case_prefers_runtime_count_anchor_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_register_source(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "status": "registered",
            "dataset_id": "count-anchor-id",
            "schema": {
                "row_count": 10,
                "columns": [
                    {"name": "nullable_metric", "role": "derived_measure", "fill_rate": 0.7},
                    {"name": "record_id", "role": "identifier", "fill_rate": 1.0},
                ],
                "planner_profile": {
                    "nullable_metric": {"total_count": 7},
                    "record_id": {"total_count": 10},
                },
            },
            "latency_ms": 2.0,
            "planner_prewarm_ms": 1.0,
        }

    monkeypatch.setattr(_BENCHMARK, "register_source", _fake_register_source)
    monkeypatch.setattr(
        _BENCHMARK.reg,
        "get_source_entry",
        lambda org_id, source_id: {"id": source_id, "name": "AnchorSource"},
    )

    case = await _register_case(
        auth={"org_id": "bench-org"},
        label="Count anchor fixture",
        category="local_csv",
        origin="fixture.csv",
        source=_BENCHMARK.DataSource(
            name="AnchorSource",
            csv="record_id,nullable_metric\n1,10\n",
        ),
        expected_count=10,
    )

    assert case.metric_column == "record_id"
    assert case.metric_role == "identifier"
    assert case.expected_count == 10


@pytest.mark.asyncio
async def test_prepare_local_csv_cases_skips_empty_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_path = (
        TEST_FILES
        / "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv"
    )
    non_empty_path = TEST_FILES / "Backlog.csv"

    monkeypatch.setattr(
        _BENCHMARK,
        "_discover_local_csv_paths",
        lambda include_processed_variants, local_limit=None: [empty_path, non_empty_path],
    )

    async def _fake_register_case(**kwargs):  # type: ignore[no-untyped-def]
        return {"origin": kwargs["origin"]}

    monkeypatch.setattr(_BENCHMARK, "_register_case", _fake_register_case)

    prepared, skipped = await _prepare_local_csv_cases(
        auth={"org_id": "bench-org"},
        include_processed_variants=False,
        local_limit=None,
    )

    assert len(prepared) == 1
    assert prepared[0]["origin"] == str(non_empty_path.relative_to(Path(__file__).resolve().parents[1]))
    assert skipped == [str(empty_path.relative_to(Path(__file__).resolve().parents[1]))]
