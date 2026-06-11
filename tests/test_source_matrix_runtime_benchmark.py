from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.api_server.routers.query_contract import ResolvedPlan

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
_active_public_validation_cases = _BENCHMARK._active_public_validation_cases
_discover_local_csv_paths = _BENCHMARK._discover_local_csv_paths
_discover_local_parquet_paths = _BENCHMARK._discover_local_parquet_paths
_discover_local_workbook_paths = _BENCHMARK._discover_local_workbook_paths
_parse_csv_records = _BENCHMARK._parse_csv_records
_percentile = _BENCHMARK._percentile
_prepare_local_csv_cases = _BENCHMARK._prepare_local_csv_cases
_prepare_public_cases = _BENCHMARK._prepare_public_cases
_public_case_source_name = _BENCHMARK._public_case_source_name
_register_case = _BENCHMARK._register_case
_run = _BENCHMARK._run
_summarize_category = _BENCHMARK._summarize_category


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


def test_active_public_validation_cases_excludes_non_benchmark_public_rest_defaults() -> None:
    active_case_ids = {case.case_id for case in _active_public_validation_cases()}

    assert "public_s3_source_registration" in active_case_ids
    assert "public_gcs_source_registration" in active_case_ids
    assert "public_azure_blob_source_registration" in active_case_ids
    assert "fivetran_npi_registry_number" in active_case_ids
    assert "dlt_pokeapi_pokemon" in active_case_ids
    assert "pokeapi_color_pagination" not in active_case_ids
    assert "fivetran_noaa_station_kilg" not in active_case_ids
    assert "dlt_github_issues" not in active_case_ids


def test_active_public_validation_cases_skip_live_only_non_benchmark_defaults() -> None:
    cases = {
        case.case_id: case
        for case in _BENCHMARK.PUBLIC_VALIDATION_CASES
        if case.case_id
        in {
            "fivetran_noaa_station_kilg",
            "pokeapi_color_pagination",
            "dlt_github_issues",
        }
    }

    assert set(cases) == {
        "fivetran_noaa_station_kilg",
        "pokeapi_color_pagination",
        "dlt_github_issues",
    }
    for case in cases.values():
        assert case.enabled_by_default is True
        assert case.benchmark_enabled is False


def test_public_case_source_name_uses_category_prefix() -> None:
    class _Case:
        def __init__(self, connector_type: str) -> None:
            self.connector_type = connector_type

    assert _public_case_source_name(1, _Case("s3")) == "PublicObject01"
    assert _public_case_source_name(2, _Case("rest_api")) == "PublicRest02"


def test_parse_csv_records_can_allow_empty_exports() -> None:
    empty_path = (
        TEST_FILES / "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv"
    )

    csv_text, records = _parse_csv_records(empty_path, allow_empty=True)

    assert "Store,External Store ID" in csv_text
    assert records == []


def test_summarize_category_reports_source_total_metrics() -> None:
    summary = _summarize_category(
        [
            {
                "register_ms": 10.0,
                "prewarm_ms": 20.0,
                "source_total_ms": 30.0,
                "resolve_miss_ms": 15.0,
                "resolve_hit_ms": 0.2,
                "exact_hit_ms": 0.8,
                "resolved_query_hit_ms": 1.5,
                "exact_result_cache_hit": True,
                "resolve_cache_hit": True,
                "resolved_query_cache_hit": True,
            },
            {
                "register_ms": 12.0,
                "prewarm_ms": 22.0,
                "source_total_ms": 34.0,
                "resolve_miss_ms": 18.0,
                "resolve_hit_ms": 0.3,
                "exact_hit_ms": 0.9,
                "resolved_query_hit_ms": 1.8,
                "exact_result_cache_hit": True,
                "resolve_cache_hit": True,
                "resolved_query_cache_hit": True,
            },
        ]
    )

    assert summary["avg_source_total_ms"] == 32.0
    assert summary["p95_source_total_ms"] == 34.0


@pytest.mark.anyio
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


@pytest.mark.anyio
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
        expected_count=None,
    )

    assert case.metric_column == "record_id"
    assert case.metric_role == "identifier"
    assert case.expected_count == 10


@pytest.mark.anyio
async def test_prepare_local_csv_cases_skips_empty_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_path = (
        TEST_FILES / "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv"
    )
    non_empty_path = TEST_FILES / "Backlog.csv"

    monkeypatch.setattr(
        _BENCHMARK,
        "_discover_local_csv_paths",
        lambda include_processed_variants, local_limit=None: [empty_path, non_empty_path],
    )

    async def _fake_register_case(**kwargs):  # type: ignore[no-untyped-def]
        if kwargs["origin"] == str(empty_path.relative_to(Path(__file__).resolve().parents[1])):
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "empty_source", "message": "empty"}},
            )
        return {"origin": kwargs["origin"]}

    monkeypatch.setattr(_BENCHMARK, "_register_case", _fake_register_case)

    prepared, skipped = await _prepare_local_csv_cases(
        auth={"org_id": "bench-org"},
        include_processed_variants=False,
        local_limit=None,
    )

    assert len(prepared) == 1
    assert prepared[0]["origin"] == str(
        non_empty_path.relative_to(Path(__file__).resolve().parents[1])
    )
    assert skipped == [str(empty_path.relative_to(Path(__file__).resolve().parents[1]))]


@pytest.mark.anyio
async def test_prepare_public_cases_warms_active_cases_before_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class _Case:
        case_id = "pokeapi_color_pagination"
        label = "PokeAPI color pagination source registration"
        connector_type = "rest_api"
        docs_url = "https://pokeapi.co/docs/v2"

        def build_connection(self) -> dict[str, str]:
            return {
                "type": "rest_api",
                "url": "https://pokeapi.co/api/v2/pokemon-color?limit=5",
            }

        def load_runtime_records_for_connection(
            self,
            connection: dict[str, str],
        ) -> list[dict[str, int]]:
            assert "pokemon-color" in connection["url"]
            events.append("warm")
            return [{"name": "black"}]

    async def _fake_register_case(*args, **kwargs):  # type: ignore[no-untyped-def]
        events.append("register")
        return "prepared"

    monkeypatch.setattr(_BENCHMARK, "_active_public_validation_cases", lambda: (_Case(),))
    monkeypatch.setattr(_BENCHMARK, "_register_case", _fake_register_case)

    prepared = await _prepare_public_cases(auth={"org_id": "bench-org"})

    assert prepared == ["prepared"]
    assert events == ["warm", "register"]


@pytest.mark.anyio
async def test_run_csv_only_skips_local_non_csv_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    runtime_events: list[str] = []

    async def _fake_prepare_local_csv_cases(**kwargs):  # type: ignore[no-untyped-def]
        return (["csv_case"], [])

    async def _fake_prepare_local_non_csv_cases(**kwargs):  # type: ignore[no-untyped-def]
        events.append("local_non_csv")
        return ["non_csv_case"]

    async def _fake_measure_cases(**kwargs):  # type: ignore[no-untyped-def]
        prepared_cases = kwargs["prepared_cases"]
        return [
            {
                "label": f"case_{index}",
                "category": "local_csv",
                "origin": f"fixture_{index}.csv",
                "source_name": f"LocalCsv{index:03d}",
                "metric_column": "record_id",
                "metric_role": "identifier",
                "expected_count": 1,
                "schema_columns": 2,
                "register_ms": 1.0,
                "prewarm_ms": 1.0,
                "exact_first_ms": 1.0,
                "exact_hit_ms": 1.0,
                "resolve_miss_ms": 1.0,
                "resolve_hit_ms": 0.1,
                "resolved_query_first_ms": 1.0,
                "resolved_query_hit_ms": 1.0,
                "source_total_ms": 2.0,
                "exact_result_cache_hit": True,
                "resolve_cache_hit": True,
                "resolved_query_cache_hit": True,
            }
            for index, _ in enumerate(prepared_cases, start=1)
        ]

    monkeypatch.setattr(_BENCHMARK, "_prepare_local_csv_cases", _fake_prepare_local_csv_cases)
    monkeypatch.setattr(
        _BENCHMARK, "_prepare_local_non_csv_cases", _fake_prepare_local_non_csv_cases
    )
    monkeypatch.setattr(_BENCHMARK, "_measure_cases", _fake_measure_cases)
    monkeypatch.setattr(_BENCHMARK, "_validate_measurements", lambda measurements: None)
    monkeypatch.setattr(
        _BENCHMARK,
        "_setup_mojo_runtime",
        lambda: _record_async(runtime_events, "setup", return_value="pool"),
    )
    monkeypatch.setattr(
        _BENCHMARK,
        "_teardown_mojo_runtime",
        lambda: _record_async(runtime_events, "teardown"),
    )

    summary = await _run(
        include_processed_variants=False,
        skip_public=True,
        skip_db=True,
        local_limit=None,
        csv_only=True,
    )

    assert events == []
    assert runtime_events == ["setup", "teardown"]
    assert summary["csv_only"] is True
    assert summary["mojo_runtime_mode"] == "pool"
    assert summary["totals"]["mojo_runtime_mode"] == "pool"
    assert summary["local_csv_files"] == 1
    assert summary["local_non_csv_sources"] == 0


async def _record_async(
    events: list[str],
    name: str,
    *,
    return_value: str | None = None,
) -> str | None:
    events.append(name)
    return return_value


@pytest.mark.anyio
async def test_run_resolve_query_preserves_dataset_scope_for_resolved_plan_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _BENCHMARK.PreparedSourceCase(
        label="Scoped resolve fixture",
        category="local_csv",
        origin="fixture.csv",
        source_name="ScopedSource",
        dataset_id="scoped-dataset-id",
        metric_column="record_id",
        metric_role="identifier",
        expected_count=7,
        register_ms=1.0,
        prewarm_ms=1.0,
        schema_columns=2,
    )
    recorded_requests: list[object] = []
    resolved_plan = ResolvedPlan(
        source_name=case.source_name,
        metric_column=case.metric_column,
        aggregation="count",
        schema_revision="rev-1",
    )

    async def _fake_resolve(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(resolved_plan=resolved_plan, rejection_reason=None, plan=[])

    async def _fake_query(request, *, auth):  # type: ignore[no-untyped-def]
        recorded_requests.append(request)
        return SimpleNamespace(result=case.expected_count, plan=[])

    monkeypatch.setattr(_BENCHMARK, "_resolve_registered_intent", _fake_resolve)
    monkeypatch.setattr(_BENCHMARK, "query_sources", _fake_query)

    await _BENCHMARK._run_resolve_query(auth={"org_id": "bench-org"}, case=case)

    assert [request.dataset_id for request in recorded_requests] == [
        case.dataset_id,
        case.dataset_id,
    ]
