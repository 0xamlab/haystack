import base64
import io
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import HTTPException

from apps.api_server.routers.data_map import DataSource, MojoInstrumentationError
from apps.api_server.routers.query import _CACHE_LOCK, _PLANNER_CACHE, _SOURCE_CACHE
from apps.api_server.routers.sources import (
    _JOIN_NAME_STATS_CACHE,
    _JOIN_PROJECTION_CACHE,
    _JOIN_VALUE_CANDIDATE_CACHE,
    RegisterRequest,
    _bounded_fast_join_connections,
    _build_join_name_stats,
    _build_join_value_candidates,
    _deep_join_projection_columns,
    _detect_joins_between,
    _has_sufficient_fast_join_evidence,
    _infer_shared_column_cardinality_from_stats,
    _join_candidate_limit,
    _join_candidate_min_score,
    _load_join_name_stats_cached,
    _load_join_projection,
    _load_join_projection_cached,
    _load_join_value_candidates_cached,
    register_source,
)
from apps.api_server.services import source_registry as reg


@pytest.mark.anyio
async def test_register_source_persists_cached_content_for_each_org(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()

    payload = RegisterRequest(
        source=DataSource(
            name="S0",
            csv="account_code,local_group,measure_total\n00123,g_a,10\n00456,g_b,20\n",
        )
    )

    first = await register_source(payload, auth={"org_id": "org_a"})
    second = await register_source(payload, auth={"org_id": "org_b"})

    assert first["status"] == "registered"
    assert second["status"] == "registered"
    assert first["source_id"] == second["source_id"]

    org_a_sources = reg.list_sources("org_a")
    org_b_sources = reg.list_sources("org_b")

    assert [s["id"] for s in org_a_sources] == [first["source_id"]]
    assert [s["id"] for s in org_b_sources] == [second["source_id"]]

    meta_b = reg.get_source_meta("org_b", second["source_id"])
    assert meta_b is not None
    assert meta_b["row_count"] == 2


@pytest.mark.anyio
async def test_register_source_includes_physical_types_in_schema_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()

    response = await register_source(
        RegisterRequest(
            source=DataSource(
                name="PhysicalTypes",
                csv="record_id,measure_total\nA1,10\nA2,20\n",
            )
        ),
        auth={"org_id": "org_physical_types"},
    )

    columns = response["schema"]["columns"]
    assert columns
    assert all(str(column.get("physical_type", "")).strip() for column in columns)
    record_id = next(column for column in columns if column["name"] == "record_id")
    measure_total = next(column for column in columns if column["name"] == "measure_total")
    assert record_id["physical_type"] == "string"
    assert measure_total["physical_type"] in {"int64", "double"}


@pytest.mark.anyio
async def test_register_source_returns_structured_400_when_schema_build_fails(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    def _raise_schema_graph(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("schema graph boom")

    monkeypatch.setattr("apps.api_server.routers.sources.build_schema_graph", _raise_schema_graph)

    with pytest.raises(HTTPException) as exc_info:
        await register_source(
            RegisterRequest(
                source=DataSource(
                    name="TicketsRegister",
                    csv="ticket_id,total_usd\n1,19.5\n2,21.0\n",
                )
            ),
            auth={"org_id": "org_register_fail"},
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail["error"]
    assert detail["code"] == "source_registration_failed"
    assert detail["details"]["stage"] == "build_schema_graph"
    assert detail["details"]["error_type"] == "RuntimeError"
    assert "schema graph boom" in detail["message"]


@pytest.mark.anyio
async def test_register_source_survives_planner_prewarm_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    async def _fake_incremental(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return False, "rev_before"

    async def _raise_planner(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("planner prewarm boom")

    monkeypatch.setattr(
        "apps.api_server.routers.sources._try_incremental_registry_planner_update",
        _fake_incremental,
    )
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _raise_planner)

    response = await register_source(
        RegisterRequest(
            source=DataSource(
                name="TicketsPlannerFallback",
                csv="ticket_id,total_usd\n10,100.0\n11,125.0\n",
            )
        ),
        auth={"org_id": "org_planner_fail"},
    )

    assert response["status"] == "registered"
    assert response["planner_cache_hit"] is False
    assert isinstance(response["planner_schema_revision"], str)
    assert response["planner_schema_revision"]
    assert response["planner_prewarm_ms"] >= 0
    entry = reg.get_source_entry("org_planner_fail", str(response["source_id"]))
    assert entry is not None


def test_source_meta_cache_reuses_registered_schema_without_disk_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    schema_meta = {
        "row_count": 2,
        "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
        "roles_summary": {"identifier": 1},
    }
    reg.register_source(
        org_id="org_meta_cache",
        source_id="src_meta_cache",
        name="MetaCacheSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta=schema_meta,
        graph_nodes={},
        profile={},
    )

    read_calls = {"count": 0}
    original_read_json = reg._read_json

    def _counting_read_json(path: Path):  # type: ignore[no-untyped-def]
        read_calls["count"] += 1
        return original_read_json(path)

    monkeypatch.setattr(reg, "_read_json", _counting_read_json)

    first = reg.get_source_meta("org_meta_cache", "src_meta_cache")
    second = reg.get_source_meta("org_meta_cache", "src_meta_cache")

    assert first == schema_meta
    assert second == schema_meta
    assert read_calls["count"] == 0


def test_build_join_blocks_excludes_internal_metadata_columns() -> None:
    join_blocks = reg._build_join_blocks(
        {
            "columns": [
                {"name": "__synthetic_row_id", "role": "identifier", "is_numeric": False},
                {"name": "__source_record_key", "role": "identifier", "is_numeric": False},
                {"name": "company_code", "role": "identifier", "is_numeric": False},
            ],
            "planner_profile": {
                "__synthetic_row_id": {
                    "is_numeric": False,
                    "fill_rate": 1.0,
                    "total_count": 100,
                    "unique_count": 100,
                    "sample_values": [1, 2, 3],
                },
                "__source_record_key": {
                    "is_numeric": False,
                    "fill_rate": 1.0,
                    "total_count": 100,
                    "unique_count": 100,
                    "sample_values": ["a", "b", "c"],
                },
                "company_code": {
                    "is_numeric": False,
                    "fill_rate": 1.0,
                    "total_count": 100,
                    "unique_count": 100,
                    "sample_values": ["C1", "C2", "C3"],
                },
            },
        }
    )

    assert [block["name"] for block in join_blocks] == ["company_code"]


def test_build_join_blocks_excludes_generic_time_columns() -> None:
    join_blocks = reg._build_join_blocks(
        {
            "columns": [
                {"name": "updated_dte", "role": "time", "is_numeric": False},
                {"name": "entered", "role": "time", "is_numeric": False},
                {"name": "company_code", "role": "identifier", "is_numeric": False},
            ],
            "planner_profile": {
                "updated_dte": {
                    "is_numeric": False,
                    "fill_rate": 1.0,
                    "total_count": 100,
                    "unique_count": 80,
                    "sample_values": ["2026-01-01", "2026-01-02"],
                },
                "entered": {
                    "is_numeric": False,
                    "fill_rate": 1.0,
                    "total_count": 100,
                    "unique_count": 80,
                    "sample_values": ["2026-01-01", "2026-01-02"],
                },
                "company_code": {
                    "is_numeric": False,
                    "fill_rate": 1.0,
                    "total_count": 100,
                    "unique_count": 100,
                    "sample_values": ["C1", "C2", "C3"],
                },
            },
        }
    )

    assert [block["name"] for block in join_blocks] == ["company_code"]


def test_build_join_blocks_excludes_generic_surrogate_row_identifiers() -> None:
    join_blocks = reg._build_join_blocks(
        {
            "columns": [
                {"name": "INFERRED_ROW_ID", "role": "identifier", "is_numeric": True},
                {"name": "SOURCE_ROW_ID", "role": "identifier", "is_numeric": True},
                {"name": "ORDER_ID", "role": "identifier", "is_numeric": False},
            ],
            "planner_profile": {
                "INFERRED_ROW_ID": {
                    "is_numeric": True,
                    "fill_rate": 1.0,
                    "total_count": 100,
                    "unique_count": 100,
                    "sample_values": list(range(8)),
                },
                "SOURCE_ROW_ID": {
                    "is_numeric": True,
                    "fill_rate": 1.0,
                    "total_count": 100,
                    "unique_count": 100,
                    "sample_values": list(range(8)),
                },
                "ORDER_ID": {
                    "is_numeric": False,
                    "fill_rate": 1.0,
                    "total_count": 100,
                    "unique_count": 100,
                    "sample_values": [f"O{i:03d}" for i in range(8)],
                },
            },
        }
    )

    assert [block["name"] for block in join_blocks] == ["ORDER_ID"]


def test_source_entry_cache_reuses_registered_index_entry_without_disk_reload(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    reg.register_source(
        org_id="org_entry_cache",
        source_id="src_entry_cache",
        name="EntryCacheSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    read_calls = {"count": 0}
    original_read_json = reg._read_json

    def _counting_read_json(path: Path):  # type: ignore[no-untyped-def]
        read_calls["count"] += 1
        return original_read_json(path)

    monkeypatch.setattr(reg, "_read_json", _counting_read_json)

    first = reg.get_source_entry("org_entry_cache", "src_entry_cache")
    second = reg.get_source_entry("org_entry_cache", "src_entry_cache")

    assert first is not None
    assert first["name"] == "EntryCacheSource"
    assert isinstance(first["source_schema_revision"], str)
    assert len(first["source_schema_revision"]) == 24
    assert second == first
    assert read_calls["count"] == 0


def test_update_source_meta_refreshes_entry_source_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    reg.register_source(
        org_id="org_source_revision_sync",
        source_id="src_revision_sync",
        name="RevisionSyncSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    before = reg.get_source_entry("org_source_revision_sync", "src_revision_sync")
    assert before is not None
    before_revision = str(before.get("source_schema_revision") or "")
    assert before_revision

    updated_meta = reg.update_source_meta(
        "org_source_revision_sync",
        "src_revision_sync",
        {"schema_revision": "planner_revision_after_prewarm"},
    )

    assert updated_meta is not None

    after = reg.get_source_entry("org_source_revision_sync", "src_revision_sync")
    assert after is not None
    after_revision = str(after.get("source_schema_revision") or "")
    assert after_revision
    assert after_revision == reg.source_schema_revision(
        "org_source_revision_sync",
        "src_revision_sync",
    )
    assert after_revision != before_revision


def test_update_source_entry_without_touching_schema_preserves_org_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    reg._SCHEMA_REVISION_CACHE.clear()

    reg.register_source(
        org_id="org_entry_revision_stable",
        source_id="src_entry_revision_stable",
        name="EntryRevisionStable",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    before = reg.schema_revision("org_entry_revision_stable")
    updated = reg.update_source_entry(
        "org_entry_revision_stable",
        "src_entry_revision_stable",
        {"schema_revision": "planner_revision_after_prewarm"},
        touch_schema=False,
    )
    after = reg.schema_revision("org_entry_revision_stable")

    assert updated is not None
    assert updated["schema_revision"] == "planner_revision_after_prewarm"
    assert after == before


def test_update_source_entry_noop_preserves_org_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    reg.register_source(
        org_id="org_entry_noop",
        source_id="src_entry_noop",
        name="EntryNoopSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
        dataset_name="EntryNoopSource",
    )

    before = reg.schema_revision("org_entry_noop")
    updated = reg.update_source_entry(
        "org_entry_noop",
        "src_entry_noop",
        {"dataset_name": "EntryNoopSource"},
    )
    after = reg.schema_revision("org_entry_noop")

    assert updated is not None
    assert updated["dataset_name"] == "EntryNoopSource"
    assert after == before


def test_update_source_meta_without_touching_schema_preserves_org_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    reg._SCHEMA_REVISION_CACHE.clear()

    reg.register_source(
        org_id="org_meta_revision_stable",
        source_id="src_meta_revision_stable",
        name="MetaRevisionStable",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    before = reg.schema_revision("org_meta_revision_stable")
    updated = reg.update_source_meta(
        "org_meta_revision_stable",
        "src_meta_revision_stable",
        {"schema_revision": "planner_revision_after_prewarm"},
        touch_schema=False,
    )
    after = reg.schema_revision("org_meta_revision_stable")

    assert updated is not None
    assert updated["schema_revision"] == "planner_revision_after_prewarm"
    assert after == before


def test_update_source_meta_noop_preserves_org_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    reg.register_source(
        org_id="org_meta_noop",
        source_id="src_meta_noop",
        name="MetaNoopSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    before = reg.schema_revision("org_meta_noop")
    updated = reg.update_source_meta(
        "org_meta_noop",
        "src_meta_noop",
        {"row_count": 2},
    )
    after = reg.schema_revision("org_meta_noop")

    assert updated is not None
    assert updated["row_count"] == 2
    assert after == before


@pytest.mark.anyio
async def test_register_source_reuses_identical_parquet_content_within_org(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    parquet_b64 = base64.b64encode(
        _parquet_bytes(
            [
                {"entity_key": "A", "measure_total": 10.0},
                {"entity_key": "B", "measure_total": 20.0},
            ]
        )
    ).decode()

    first = await register_source(
        RegisterRequest(source=DataSource(name="ParquetFirst", parquet_b64=parquet_b64)),
        auth={"org_id": "org_repeat"},
    )
    second = await register_source(
        RegisterRequest(source=DataSource(name="ParquetSecond", parquet_b64=parquet_b64)),
        auth={"org_id": "org_repeat"},
    )

    assert first["status"] == "registered"
    assert second["status"] == "already_registered"
    assert second["source_id"] == first["source_id"]
    assert second["row_count"] == first["row_count"] == 2
    assert [s["id"] for s in reg.list_sources("org_repeat")] == [first["source_id"]]


@pytest.mark.anyio
async def test_register_source_duplicate_content_keeps_org_schema_revision_stable(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    payload = RegisterRequest(
        source=DataSource(
            name="StableSchema",
            csv="entity_key,measure_total\nA,10\nB,20\n",
        )
    )

    first = await register_source(payload, auth={"org_id": "org_schema_stable"})
    revision_after_first = reg.schema_revision("org_schema_stable")
    second = await register_source(payload, auth={"org_id": "org_schema_stable"})
    revision_after_second = reg.schema_revision("org_schema_stable")

    assert first["status"] == "registered"
    assert first["planner_cache_hit"] is False
    assert second["status"] == "already_registered"
    assert second["planner_cache_hit"] is True
    assert first["source_id"] == second["source_id"]
    assert revision_after_first == revision_after_second
    assert first["planner_schema_revision"] == revision_after_first
    assert second["planner_schema_revision"] == revision_after_second


@pytest.mark.anyio
async def test_register_source_reuses_identical_excel_content_within_org(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    excel_b64 = _excel_b64(
        [
            {"part_number": "00123", "measure_total": 10.0},
            {"part_number": "00456", "measure_total": 20.0},
        ]
    )

    first = await register_source(
        RegisterRequest(source=DataSource(name="ExcelFirst", excel_b64=excel_b64)),
        auth={"org_id": "org_excel"},
    )
    second = await register_source(
        RegisterRequest(source=DataSource(name="ExcelSecond", excel_b64=excel_b64)),
        auth={"org_id": "org_excel"},
    )

    assert first["status"] == "registered"
    assert second["status"] == "already_registered"
    assert second["source_id"] == first["source_id"]
    assert [s["id"] for s in reg.list_sources("org_excel")] == [first["source_id"]]


@pytest.mark.anyio
async def test_register_source_builds_connected_graph_for_real_march_corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()
    _JOIN_PROJECTION_CACHE.clear()
    _JOIN_VALUE_CANDIDATE_CACHE.clear()
    _JOIN_NAME_STATS_CACHE.clear()

    auth = {"org_id": "org_march_real"}
    test_files = Path(__file__).resolve().parents[1] / "test_files"

    def _csv_text(filename: str) -> str:
        return (test_files / filename).read_text(encoding="utf-8-sig", errors="replace")

    orders_detail = await register_source(
        RegisterRequest(
            source=DataSource(
                name="orders_detail",
                csv=_csv_text("850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv"),
            )
        ),
        auth=auth,
    )
    top_inaccurate_items = await register_source(
        RegisterRequest(
            source=DataSource(
                name="top_inaccurate_items",
                csv=_csv_text(
                    "630a0f6c-a250-4bd7-af2e-bed6184619ac_top_inaccurate_items_v3_2026-03-01_2026-03-31.csv"
                ),
            )
        ),
        auth=auth,
    )
    orders_financial = await register_source(
        RegisterRequest(
            source=DataSource(
                name="orders_financial",
                csv=_csv_text("aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv"),
            )
        ),
        auth=auth,
    )
    restaurant_rating = await register_source(
        RegisterRequest(
            source=DataSource(
                name="restaurant_rating_sku_local",
                csv=_csv_text(
                    "3d9b2e55-c7ea-4e31-90ea-ca5797a69c2b_restaurant_rating_sku_local_2026-03-01_2026-03-31.csv"
                ),
            )
        ),
        auth=auth,
    )

    with pytest.raises(HTTPException) as exc_info:
        await register_source(
            RegisterRequest(
                source=DataSource(
                    name="store_pause",
                    csv=_csv_text(
                        "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv"
                    ),
                )
            ),
            auth=auth,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"]["code"] == "empty_source"

    financial_meta = reg.get_source_meta("org_march_real", str(orders_financial["source_id"]))
    assert financial_meta is not None
    assert financial_meta["row_count"] == 2026

    connections = reg.get_connections("org_march_real")

    def _has_connection(
        left_name: str,
        left_col: str,
        right_name: str,
        right_col: str,
        *,
        cardinality: str | None = None,
    ) -> bool:
        for connection in connections:
            if connection.get("source_a_name") != left_name:
                continue
            if connection.get("col_a") != left_col:
                continue
            if connection.get("source_b_name") != right_name:
                continue
            if connection.get("col_b") != right_col:
                continue
            if cardinality is not None and connection.get("cardinality") != cardinality:
                continue
            return True
        return False

    assert orders_detail["status"] == "registered"
    assert top_inaccurate_items["status"] == "registered"
    assert restaurant_rating["status"] == "registered"
    assert _has_connection(
        "orders_financial",
        "Order ID as per Uber Eats manager",
        "orders_detail",
        "Order ID",
    )
    assert _has_connection(
        "restaurant_rating_sku_local",
        "Store",
        "top_inaccurate_items",
        "Store",
        cardinality="many_to_many",
    )
    assert _has_connection(
        "orders_financial",
        "Store name as per Uber Eats manager",
        "top_inaccurate_items",
        "Store",
        cardinality="many_to_many",
    )


@pytest.mark.anyio
async def test_register_source_reuses_incremental_planner_cache_update(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    async def _fake_incremental(*args, **kwargs):  # type: ignore[no-untyped-def]
        return True, "rev_inc"

    async def _planner_should_not_rebuild(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError(
            "_get_registry_planner should not rebuild when incremental update succeeds"
        )

    monkeypatch.setattr(
        "apps.api_server.routers.sources._try_incremental_registry_planner_update",
        _fake_incremental,
    )
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner",
        _planner_should_not_rebuild,
    )

    response = await register_source(
        RegisterRequest(
            source=DataSource(
                name="IncPlanner",
                csv="account_code,measure_total\n00123,10\n00456,20\n",
            )
        ),
        auth={"org_id": "org_inc"},
    )

    assert response["status"] == "registered"
    assert response["planner_cache_hit"] is True
    assert response["planner_schema_revision"] == "rev_inc"


@pytest.mark.anyio
async def test_register_source_preserves_sparse_numeric_csv_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()

    payload = RegisterRequest(
        source=DataSource(
            name="L0",
            csv="row_key,local_group,late_value\nrow_01,g_a,\nrow_02,g_b,\nrow_03,g_c,110.0\nrow_04,g_d,112.5\n",
        )
    )

    registered = await register_source(payload, auth={"org_id": "org_a"})
    parquet_bytes = reg.get_source_parquet("org_a", registered["source_id"])
    assert parquet_bytes is not None

    table = pq.read_table(io.BytesIO(parquet_bytes))
    rows = table.to_pylist()

    assert rows[0]["late_value"] is None
    assert isinstance(rows[2]["late_value"], float)
    assert rows[2]["late_value"] == 110.0


@pytest.mark.anyio
async def test_register_source_persists_full_cardinality_stats_beyond_sample_limit(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    lines = ["entity_key,measure_total"]
    lines.extend(f"K{i:04d},{i}" for i in range(600))
    payload = RegisterRequest(source=DataSource(name="WideKeys", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_stats"})
    meta = reg.get_source_meta("org_stats", registered["source_id"])

    assert meta is not None
    profile = meta["planner_profile"]["entity_key"]
    assert profile["unique_count"] == 600
    assert profile["total_count"] == 600


def _parquet_bytes(rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), buf)
    return buf.getvalue()


def _parquet_bytes_with_row_group_size(rows: list[dict], *, row_group_size: int) -> bytes:
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), buf, row_group_size=row_group_size)
    return buf.getvalue()


def _excel_b64(rows: list[dict]) -> str:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    headers = list(rows[0].keys()) if rows else []
    if headers:
        ws.append(headers)
        for row in rows:
            ws.append([row.get(header) for header in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def _schema_meta_for_columns(
    row_count: int,
    columns: list[dict[str, object]],
) -> dict:
    planner_profile: dict[str, dict[str, object]] = {}
    column_meta: list[dict[str, object]] = []
    roles_summary: dict[str, int] = {}
    for col in columns:
        name = str(col["name"])
        role = str(col.get("role", "identifier"))
        fill_rate = float(col.get("fill_rate", 1.0))
        unique_count = int(col.get("unique_count", row_count))
        total_count = int(col.get("total_count", max(int(round(row_count * fill_rate)), 1)))
        is_numeric = bool(col.get("is_numeric", False))
        samples = list(col.get("samples", []))
        planner_profile[name] = {
            "is_numeric": is_numeric,
            "strings": [str(v) for v in samples[:5]],
            "sample_values": [str(v) for v in samples[:5]],
            "unique_count": unique_count,
            "total_count": total_count,
            "fill_rate": fill_rate,
            "mean": 0.0,
            "std": 0.0,
        }
        col_meta = {
            "name": name,
            "role": role,
            "is_numeric": is_numeric,
            "fill_rate": fill_rate,
        }
        if not is_numeric:
            col_meta["cardinality"] = unique_count
        if samples:
            col_meta["samples"] = [str(v) for v in samples[:5]]
        column_meta.append(col_meta)
        roles_summary[role] = roles_summary.get(role, 0) + 1

    return {
        "source": "synthetic",
        "row_count": row_count,
        "columns": column_meta,
        "formulas": [],
        "roles_summary": roles_summary,
        "query_hints": [],
        "planner_profile": planner_profile,
    }


def test_deep_join_projection_columns_caps_and_deduplicates():
    join_blocks = [
        {"name": "entity_key"},
        {"name": "entity_key"},
        {"name": "measure_total"},
        {"name": "segment_label"},
    ]

    projected = _deep_join_projection_columns(join_blocks, limit=2)

    assert projected == ["entity_key", "measure_total"]


def test_deep_join_projection_columns_keeps_low_cardinality_dimension_extensions():
    join_blocks = [{"name": f"ranked_{idx}"} for idx in range(12)] + [
        {
            "name": "Store name as per Uber Eats manager",
            "unique_count": 2,
            "unique_ratio": 0.001,
        },
        {
            "name": "Merchant location",
            "unique_count": 3,
            "unique_ratio": 0.01,
        },
    ]

    projected = _deep_join_projection_columns(join_blocks, limit=12)

    assert "Store name as per Uber Eats manager" in projected
    assert "Merchant location" in projected


def test_load_join_projection_reads_ranked_join_columns_only():
    parquet_bytes = _parquet_bytes(
        [
            {
                "entity_key": "A",
                "measure_total": 10.0,
                "noise_a": "n1",
                "noise_b": "n2",
            },
        ]
    )

    projected = _load_join_projection(
        parquet_bytes,
        [
            {"name": "entity_key"},
            {"name": "measure_total"},
        ],
    )

    assert list(projected.columns) == ["entity_key", "measure_total"]


def test_load_join_projection_respects_max_rows():
    parquet_bytes = _parquet_bytes(
        [
            {"entity_key": "A", "measure_total": 10.0},
            {"entity_key": "B", "measure_total": 20.0},
            {"entity_key": "C", "measure_total": 30.0},
        ]
    )

    projected = _load_join_projection(
        parquet_bytes,
        [{"name": "entity_key"}],
        max_rows=2,
    )

    assert list(projected.columns) == ["entity_key"]
    assert projected.to_dict(orient="records") == [
        {"entity_key": "A"},
        {"entity_key": "B"},
    ]


def test_load_join_projection_spreads_capped_rows_across_row_groups():
    parquet_bytes = _parquet_bytes_with_row_group_size(
        [
            {"entity_key": "A1", "measure_total": 10.0},
            {"entity_key": "A2", "measure_total": 11.0},
            {"entity_key": "B1", "measure_total": 20.0},
            {"entity_key": "B2", "measure_total": 21.0},
            {"entity_key": "C1", "measure_total": 30.0},
            {"entity_key": "C2", "measure_total": 31.0},
        ],
        row_group_size=2,
    )

    projected = _load_join_projection(
        parquet_bytes,
        [{"name": "entity_key"}],
        max_rows=3,
    )

    assert list(projected.columns) == ["entity_key"]
    assert projected.to_dict(orient="records") == [
        {"entity_key": "A1"},
        {"entity_key": "B1"},
        {"entity_key": "C1"},
    ]


def test_load_join_projection_spreads_capped_rows_across_batches_when_single_row_group(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "apps.api_server.services.source_join_cache._JOIN_PROJECTION_BATCH_SIZE",
        2,
    )
    parquet_bytes = _parquet_bytes_with_row_group_size(
        [
            {"entity_key": "A1", "measure_total": 10.0},
            {"entity_key": "A2", "measure_total": 11.0},
            {"entity_key": "B1", "measure_total": 20.0},
            {"entity_key": "B2", "measure_total": 21.0},
            {"entity_key": "C1", "measure_total": 30.0},
            {"entity_key": "C2", "measure_total": 31.0},
        ],
        row_group_size=16,
    )

    projected = _load_join_projection(
        parquet_bytes,
        [{"name": "entity_key"}],
        max_rows=3,
    )

    assert list(projected.columns) == ["entity_key"]
    assert projected.to_dict(orient="records") == [
        {"entity_key": "A1"},
        {"entity_key": "B1"},
        {"entity_key": "C1"},
    ]


def test_load_join_projection_cached_reuses_projection_until_source_revision_changes(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    _JOIN_PROJECTION_CACHE.clear()
    _JOIN_VALUE_CANDIDATE_CACHE.clear()

    meta = _schema_meta_for_columns(
        2,
        [{"name": "entity_key", "role": "identifier", "unique_count": 2, "samples": ["A", "B"]}],
    )
    reg.register_source(
        "org_cached_projection",
        "s_cached",
        "CachedSource",
        _parquet_bytes(
            [
                {"entity_key": "A", "measure_total": 10.0},
                {"entity_key": "B", "measure_total": 20.0},
            ]
        ),
        meta,
        graph_nodes={},
        profile={},
    )
    parquet_path = reg.get_source_parquet_path("org_cached_projection", "s_cached")
    assert parquet_path is not None

    calls = 0
    original = _load_join_projection

    def _counting_load(
        parquet_bytes_arg,
        join_blocks_arg,
        *,
        parquet_path=None,
        max_rows=None,
    ):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(
            parquet_bytes_arg,
            join_blocks_arg,
            parquet_path=parquet_path,
            max_rows=max_rows,
        )

    monkeypatch.setattr("apps.api_server.routers.sources._load_join_projection", _counting_load)

    df_first = _load_join_projection_cached(
        org_id="org_cached_projection",
        source_id="s_cached",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key"}],
    )
    df_second = _load_join_projection_cached(
        org_id="org_cached_projection",
        source_id="s_cached",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key"}],
    )

    assert calls == 1
    assert df_first is df_second

    reg.update_source_meta(
        "org_cached_projection", "s_cached", {"semantic_aliases": {"entity": ["entity_key"]}}
    )

    _load_join_projection_cached(
        org_id="org_cached_projection",
        source_id="s_cached",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key"}],
    )

    assert calls == 2


def test_build_join_value_candidates_prefers_joinable_high_uniqueness_columns():
    df = pd.DataFrame(
        {
            "entity_key": [f"K{i:03d}" for i in range(20)],
            "noise_code": [f"N{i:03d}" for i in range(20)],
            "low_cardinality": ["A"] * 20,
        }
    )

    candidates = _build_join_value_candidates(
        df,
        [
            {"name": "entity_key", "joinability": 2.5},
            {"name": "noise_code", "joinability": 0.2},
            {"name": "low_cardinality", "joinability": 3.0},
        ],
    )

    assert list(candidates)[:2] == ["entity_key", "noise_code"]
    assert "low_cardinality" not in candidates
    assert candidates["entity_key"]["sample_size"] == 20
    assert candidates["entity_key"]["values"][:3] == ["K000", "K001", "K002"]


def test_build_join_value_candidates_keeps_low_ratio_keylike_columns_for_large_fact_tables():
    df = pd.DataFrame(
        {
            "airport_id": [f"AIR_{index % 40:03d}" for index in range(1000)],
            "bags_processed": [index % 17 for index in range(1000)],
        }
    )

    candidates = _build_join_value_candidates(
        df,
        [
            {
                "name": "airport_id",
                "joinability": 2.4,
                "key_like": True,
                "role": "identifier",
            },
            {
                "name": "bags_processed",
                "joinability": 0.3,
                "key_like": False,
                "role": "metric",
            },
        ],
    )

    assert "airport_id" in candidates
    assert "bags_processed" not in candidates
    assert candidates["airport_id"]["sample_size"] == 1000


def test_build_join_value_candidates_keeps_substantial_sparse_dimension_with_moderate_joinability():
    df = pd.DataFrame(
        {
            "airport_id": [f"AIR_{index % 460:03d}" for index in range(100_000)],
            "supplier_id": [f"SUP_{index % 37:03d}" for index in range(100_000)],
        }
    )

    candidates = _build_join_value_candidates(
        df,
        [
            {
                "name": "airport_id",
                "joinability": 1.400157,
                "key_like": True,
                "role": "identifier",
            },
            {
                "name": "supplier_id",
                "joinability": 1.400013,
                "key_like": True,
                "role": "identifier",
            },
        ],
    )

    assert "airport_id" in candidates
    assert "supplier_id" not in candidates
    assert candidates["airport_id"]["sample_size"] == 100_000


def test_build_join_value_candidates_keeps_constant_keylike_column_and_normalizes_numeric_strings():
    df = pd.DataFrame(
        {
            "airline_id": [1.0] * 250,
            "bags_processed": [index % 5 for index in range(250)],
        }
    )

    candidates = _build_join_value_candidates(
        df,
        [
            {
                "name": "airline_id",
                "joinability": 1.403175,
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
            },
            {
                "name": "bags_processed",
                "joinability": 0.3,
                "key_like": False,
                "role": "metric",
                "fill_rate": 1.0,
            },
        ],
    )

    assert "airline_id" in candidates
    assert candidates["airline_id"]["values"] == ["1"]
    assert "bags_processed" not in candidates


def test_build_join_value_candidates_keeps_small_unique_keylike_dimension_identifier():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["oneworld", "SkyTeam", "Star Alliance"],
        }
    )

    candidates = _build_join_value_candidates(
        df,
        [
            {
                "name": "id",
                "joinability": 1.2,
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
            },
            {
                "name": "name",
                "joinability": 0.2,
                "key_like": False,
                "role": "dimension",
                "fill_rate": 1.0,
            },
        ],
    )

    assert "id" in candidates
    assert candidates["id"]["values"] == ["1", "2", "3"]
    assert "name" not in candidates


def test_build_join_value_candidates_keeps_sparse_small_domain_keylike_identifier():
    df = pd.DataFrame(
        {
            "alliance_id": [1, None, None, None, 2, None, None, 3],
            "carrier_name": [f"Carrier {index:03d}" for index in range(8)],
        }
    )

    candidates = _build_join_value_candidates(
        df,
        [
            {
                "name": "alliance_id",
                "joinability": 1.27,
                "key_like": True,
                "role": "identifier",
                "fill_rate": 0.375,
            },
            {
                "name": "carrier_name",
                "joinability": 0.2,
                "key_like": False,
                "role": "dimension",
                "fill_rate": 1.0,
            },
        ],
    )

    assert "alliance_id" in candidates
    assert candidates["alliance_id"]["values"] == ["1", "2", "3"]


def test_build_join_value_candidates_keeps_moderate_domain_keylike_identifier():
    df = pd.DataFrame(
        {
            "aircraft_type_id": [((index % 19) + 1) for index in range(252)],
            "registration": [f"N{index:04d}" for index in range(252)],
        }
    )

    candidates = _build_join_value_candidates(
        df,
        [
            {
                "name": "aircraft_type_id",
                "joinability": 1.46,
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
            },
            {
                "name": "registration",
                "joinability": 1.7,
                "key_like": False,
                "role": "identifier",
                "fill_rate": 1.0,
            },
        ],
    )

    assert "aircraft_type_id" in candidates
    assert candidates["aircraft_type_id"]["values"][:5] == ["1", "2", "3", "4", "5"]


def test_build_join_name_stats_captures_counts_and_unique_ratio():
    df = pd.DataFrame(
        {
            "entity_key": ["A", "A", "B", None],
            "segment_code": ["X", "Y", "Y", "Y"],
        }
    )

    stats = _build_join_name_stats(df)

    assert stats["entity_key"]["counts"] == {"A": 2, "B": 1}
    assert stats["entity_key"]["values"] == {"A", "B"}
    assert stats["entity_key"]["unique_ratio"] == 0.5
    assert stats["entity_key"]["all_unique"] is False
    assert stats["segment_code"]["counts"] == {"Y": 3, "X": 1}


def test_build_join_name_stats_normalizes_float_encoded_identifier_values():
    df = pd.DataFrame(
        {
            "city_id": [1.0, 1.0, 2.0, 2.0],
            "airport_id": [1, 1, 2, 2],
        }
    )

    stats = _build_join_name_stats(df)

    assert stats["city_id"]["values"] == {"1", "2"}
    assert stats["city_id"]["counts"] == {"1": 2, "2": 2}
    assert stats["airport_id"]["values"] == {"1", "2"}


def test_build_join_blocks_keeps_constant_keylike_identifier_column():
    blocks = reg._build_join_blocks(
        {
            "planner_profile": {
                "airline_id": {
                    "is_numeric": True,
                    "sample_values": ["1.0", "1.0", "1.0"],
                    "unique_count": 1,
                    "total_count": 250,
                    "fill_rate": 1.0,
                }
            },
            "columns": [
                {
                    "name": "airline_id",
                    "role": "base_measure",
                    "is_numeric": True,
                    "samples": ["1.0", "1.0", "1.0"],
                }
            ],
        }
    )

    assert [block["name"] for block in blocks] == ["airline_id"]
    assert set(blocks[0]["samples"]) == {"1"}


def test_build_join_name_stats_skips_count_map_for_exact_unique_columns():
    df = pd.DataFrame(
        {
            "entity_key": ["A", "B", "C", None],
            "segment_code": ["X", "Y", "Y", "Y"],
        }
    )

    stats = _build_join_name_stats(df)

    assert stats["entity_key"]["all_unique"] is True
    assert stats["entity_key"]["counts"] == {}
    assert stats["entity_key"]["values"] == {"A", "B", "C"}
    assert stats["segment_code"]["all_unique"] is False
    assert stats["segment_code"]["counts"] == {"Y": 3, "X": 1}


def test_infer_shared_column_cardinality_from_stats_uses_exact_unique_shortcut():
    left_stats = {
        "counts": {},
        "values": {"A", "B", "C"},
        "unique_ratio": 0.75,
        "all_unique": True,
    }
    right_stats = {
        "counts": {"A": 2, "B": 1},
        "values": {"A", "B"},
        "unique_ratio": 0.5,
        "all_unique": False,
    }

    cardinality = _infer_shared_column_cardinality_from_stats(
        left_stats,
        right_stats,
        {"A", "B"},
    )

    assert cardinality == "one_to_many"


def test_load_join_value_candidates_cached_reuses_candidates_until_source_revision_changes(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    _JOIN_PROJECTION_CACHE.clear()
    _JOIN_VALUE_CANDIDATE_CACHE.clear()

    meta = _schema_meta_for_columns(
        6,
        [
            {
                "name": "entity_key",
                "role": "identifier",
                "unique_count": 6,
                "samples": ["A", "B", "C"],
            }
        ],
    )
    reg.register_source(
        "org_cached_join_candidates",
        "s_join_cached",
        "JoinCandidateSource",
        _parquet_bytes(
            [
                {"entity_key": "A"},
                {"entity_key": "B"},
                {"entity_key": "C"},
                {"entity_key": "D"},
                {"entity_key": "E"},
                {"entity_key": "F"},
            ]
        ),
        meta,
        graph_nodes={},
        profile={},
    )
    parquet_path = reg.get_source_parquet_path("org_cached_join_candidates", "s_join_cached")
    assert parquet_path is not None

    calls = 0
    original = _build_join_value_candidates

    def _counting_build(df, join_blocks, *, limit=20):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(df, join_blocks, limit=limit)

    monkeypatch.setattr(
        "apps.api_server.routers.sources._build_join_value_candidates",
        _counting_build,
    )

    first = _load_join_value_candidates_cached(
        org_id="org_cached_join_candidates",
        source_id="s_join_cached",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key", "joinability": 2.5}],
    )
    second = _load_join_value_candidates_cached(
        org_id="org_cached_join_candidates",
        source_id="s_join_cached",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key", "joinability": 2.5}],
    )

    assert calls == 1
    assert first is second

    reg.update_source_meta(
        "org_cached_join_candidates",
        "s_join_cached",
        {"semantic_aliases": {"entity": ["entity_key"]}},
    )

    _load_join_value_candidates_cached(
        org_id="org_cached_join_candidates",
        source_id="s_join_cached",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key", "joinability": 2.5}],
    )

    assert calls == 2


def test_load_join_value_candidates_cached_separates_cache_by_candidate_limit(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    _JOIN_PROJECTION_CACHE.clear()
    _JOIN_VALUE_CANDIDATE_CACHE.clear()

    meta = _schema_meta_for_columns(
        6,
        [
            {
                "name": "entity_key",
                "role": "identifier",
                "unique_count": 6,
                "samples": ["A", "B", "C"],
            }
        ],
    )
    reg.register_source(
        "org_cached_join_candidates_limit",
        "s_join_limit",
        "JoinCandidateSourceLimit",
        _parquet_bytes(
            [
                {"entity_key": "A"},
                {"entity_key": "B"},
                {"entity_key": "C"},
                {"entity_key": "D"},
                {"entity_key": "E"},
                {"entity_key": "F"},
            ]
        ),
        meta,
        graph_nodes={},
        profile={},
    )
    parquet_path = reg.get_source_parquet_path("org_cached_join_candidates_limit", "s_join_limit")
    assert parquet_path is not None

    calls = 0
    original = _build_join_value_candidates

    def _counting_build(df, join_blocks, *, limit=20):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(df, join_blocks, limit=limit)

    monkeypatch.setattr(
        "apps.api_server.routers.sources._build_join_value_candidates",
        _counting_build,
    )

    first = _load_join_value_candidates_cached(
        org_id="org_cached_join_candidates_limit",
        source_id="s_join_limit",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key", "joinability": 2.5}],
        limit=8,
    )
    second = _load_join_value_candidates_cached(
        org_id="org_cached_join_candidates_limit",
        source_id="s_join_limit",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key", "joinability": 2.5}],
        limit=8,
    )
    third = _load_join_value_candidates_cached(
        org_id="org_cached_join_candidates_limit",
        source_id="s_join_limit",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key", "joinability": 2.5}],
        limit=20,
    )

    assert calls == 2
    assert first is second
    assert third is not first


def test_load_join_name_stats_cached_reuses_stats_until_source_revision_changes(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    _JOIN_PROJECTION_CACHE.clear()
    _JOIN_NAME_STATS_CACHE.clear()

    meta = _schema_meta_for_columns(
        4,
        [
            {
                "name": "entity_key",
                "role": "identifier",
                "unique_count": 3,
                "samples": ["A", "B", "C"],
            }
        ],
    )
    reg.register_source(
        "org_cached_name_stats",
        "s_name_stats",
        "NameStatsSource",
        _parquet_bytes(
            [
                {"entity_key": "A"},
                {"entity_key": "A"},
                {"entity_key": "B"},
                {"entity_key": "C"},
            ]
        ),
        meta,
        graph_nodes={},
        profile={},
    )
    parquet_path = reg.get_source_parquet_path("org_cached_name_stats", "s_name_stats")
    assert parquet_path is not None

    calls = 0
    original = _build_join_name_stats

    def _counting_build(df):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(df)

    monkeypatch.setattr(
        "apps.api_server.routers.sources._build_join_name_stats",
        _counting_build,
    )

    first = _load_join_name_stats_cached(
        org_id="org_cached_name_stats",
        source_id="s_name_stats",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key", "joinability": 2.5}],
    )
    second = _load_join_name_stats_cached(
        org_id="org_cached_name_stats",
        source_id="s_name_stats",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key", "joinability": 2.5}],
    )

    assert calls == 1
    assert first is second

    reg.update_source_meta(
        "org_cached_name_stats",
        "s_name_stats",
        {"semantic_aliases": {"entity": ["entity_key"]}},
    )

    _load_join_name_stats_cached(
        org_id="org_cached_name_stats",
        source_id="s_name_stats",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key", "joinability": 2.5}],
    )

    assert calls == 2


@pytest.mark.anyio
async def test_detect_joins_between_infers_one_to_one_for_exact_entity_keys(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    mojo_called = False

    async def _unexpected_mojo(*_args, **_kwargs):
        nonlocal mojo_called
        mojo_called = True
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _unexpected_mojo)

    left = _parquet_bytes(
        [
            {"entity_key": "A", "measure_total": 10.0},
            {"entity_key": "B", "measure_total": 20.0},
        ]
    )
    right = _parquet_bytes(
        [
            {"entity_key": "A", "segment_label": "seg_1"},
            {"entity_key": "B", "segment_label": "seg_2"},
        ]
    )

    joins = await _detect_joins_between(
        "org_detect",
        "src_a",
        "S0",
        left,
        "src_b",
        "S1",
        right,
        left_join_blocks=[{"name": "entity_key"}],
        right_join_blocks=[{"name": "entity_key"}],
    )

    assert joins == [
        {
            "source_a": "src_a",
            "source_a_name": "S0",
            "col_a": "entity_key",
            "source_b": "src_b",
            "source_b_name": "S1",
            "col_b": "entity_key",
            "method": "fast_shared_value_join",
            "confidence": 0.99,
            "cardinality": "one_to_one",
            "overlap": 1.0,
        }
    ]
    assert mojo_called is False


@pytest.mark.anyio
async def test_detect_joins_between_uses_metadata_fast_join_for_same_name_key_samples(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _unexpected_mojo(*_args, **_kwargs):
        raise AssertionError("metadata fast join should not call Mojo")

    def _unexpected_projection(*_args, **_kwargs):
        raise AssertionError("metadata fast join should not load projections")

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _unexpected_mojo)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._load_join_projection_cached",
        _unexpected_projection,
    )

    joins = await _detect_joins_between(
        "org_detect_meta",
        "src_a",
        "S0",
        None,
        "src_b",
        "S1",
        None,
        left_join_blocks=[
            {
                "name": "entity_key",
                "norm": "entitykey",
                "key_like": True,
                "role": "identifier",
                "unique_ratio": 1.0,
                "samples": ["A", "B", "C"],
            }
        ],
        right_join_blocks=[
            {
                "name": "entity_key",
                "norm": "entitykey",
                "key_like": True,
                "role": "identifier",
                "unique_ratio": 1.0,
                "samples": ["A", "B", "C", "D"],
            }
        ],
    )

    assert joins == [
        {
            "source_a": "src_a",
            "source_a_name": "S0",
            "col_a": "entity_key",
            "source_b": "src_b",
            "source_b_name": "S1",
            "col_b": "entity_key",
            "method": "metadata_fast_join",
            "confidence": 0.988,
            "cardinality": "one_to_one",
            "overlap": 0.75,
        }
    ]


@pytest.mark.anyio
async def test_register_source_uses_metadata_fast_join_before_projection_preload(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    reg.register_source(
        "org_register_meta_fast",
        "src_existing",
        "ExistingSource",
        _parquet_bytes([{"entity_key": "A100"}]),
        _schema_meta_for_columns(
            100,
            [
                {
                    "name": "entity_key",
                    "role": "identifier",
                    "unique_count": 100,
                    "samples": ["A100", "A101", "A102"],
                }
            ],
        ),
        graph_nodes={},
        profile={},
    )

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_register_meta_fast"

    async def _unexpected_detect(*_args, **_kwargs):
        raise AssertionError("metadata-fast registration should skip deep join detection")

    def _unexpected_projection(*_args, **_kwargs):
        raise AssertionError("metadata-fast registration should skip projection preload")

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )
    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _unexpected_detect)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._load_join_projection_cached",
        _unexpected_projection,
    )

    payload = RegisterRequest(
        source=DataSource(
            name="IncomingSource",
            csv="entity_key,measure_total\nA100,10\nA101,20\nA102,30\n",
        )
    )

    registered = await register_source(payload, auth={"org_id": "org_register_meta_fast"})

    assert registered["join_candidates_considered"] == 1
    assert registered["join_existing_total"] == 1
    assert len(registered["connections_found"]) == 1
    assert registered["connections_found"][0]["col_a"] == "entity_key"
    assert registered["connections_found"][0]["col_b"] == "entity_key"


@pytest.mark.anyio
async def test_register_source_uses_sufficient_metadata_fast_join_before_projection_preload(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    _JOIN_PROJECTION_CACHE.clear()

    org_id = "org_register_meta_fast_sufficient"
    existing_meta = _schema_meta_for_columns(
        512,
        [
            {
                "name": "customer_id",
                "role": "identifier",
                "unique_count": 400,
                "samples": ["C100", "C101", "C102"],
            },
            {
                "name": "part_number",
                "role": "identifier",
                "unique_count": 420,
                "samples": ["P100", "P101", "P102"],
            },
        ],
    )
    reg.register_source(
        org_id,
        "src_existing_sufficient",
        "ExistingSource",
        _parquet_bytes([{"customer_id": "C100", "part_number": "P100"}]),
        existing_meta,
        graph_nodes={},
        profile={},
    )

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_register_meta_fast_sufficient"

    async def _unexpected_detect(*_args, **_kwargs):
        raise AssertionError(
            "sufficient metadata-fast registration should skip deep join detection"
        )

    def _unexpected_projection(*_args, **_kwargs):
        raise AssertionError("sufficient metadata-fast registration should skip projection preload")

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )
    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _unexpected_detect)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._load_join_projection_cached",
        _unexpected_projection,
    )
    monkeypatch.setattr(
        "apps.api_server.routers.sources._metadata_fast_join_candidates",
        lambda **_kwargs: [
            {
                "source_a": "incoming",
                "source_a_name": "IncomingSource",
                "col_a": "customer_id",
                "source_b": "src_existing_sufficient",
                "source_b_name": "ExistingSource",
                "col_b": "customer_id",
                "confidence": 0.83,
                "cardinality": "one_to_many",
                "overlap": 0.35,
            },
            {
                "source_a": "incoming",
                "source_a_name": "IncomingSource",
                "col_a": "part_number",
                "source_b": "src_existing_sufficient",
                "source_b_name": "ExistingSource",
                "col_b": "part_number",
                "confidence": 0.82,
                "cardinality": "many_to_one",
                "overlap": 0.31,
            },
        ],
    )

    payload = RegisterRequest(
        source=DataSource(
            name="IncomingSource",
            csv=(
                "customer_id,part_number,measure_total\nC100,P100,10\nC101,P101,20\nC102,P102,30\n"
            ),
        )
    )

    registered = await register_source(payload, auth={"org_id": org_id})

    assert registered["join_candidates_considered"] == 1
    assert registered["join_existing_total"] == 1
    assert {
        (connection["col_a"], connection["col_b"]) for connection in registered["connections_found"]
    } == {
        ("customer_id", "customer_id"),
        ("part_number", "part_number"),
    }


@pytest.mark.anyio
async def test_detect_joins_between_matches_normalized_key_alias_without_mojo(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    left = _parquet_bytes(
        [
            {"Order ID": "A100", "Sales": 10.0},
            {"Order ID": "A101", "Sales": 12.0},
            {"Order ID": "A101", "Sales": 14.0},
            {"Order ID": "A102", "Sales": 16.0},
            {"Order ID": "A103", "Sales": 18.0},
        ]
    )
    right = _parquet_bytes(
        [
            {"Order ID as per Uber Eats manager": "A100", "Payout": 7.0},
            {"Order ID as per Uber Eats manager": "A101", "Payout": 8.0},
            {"Order ID as per Uber Eats manager": "A101", "Payout": 9.0},
            {"Order ID as per Uber Eats manager": "A102", "Payout": 10.0},
            {"Order ID as per Uber Eats manager": "A103", "Payout": 11.0},
        ]
    )

    joins = await _detect_joins_between(
        "org_detect_alias",
        "src_a",
        "orders_detail",
        left,
        "src_b",
        "orders_financial",
        right,
        left_join_blocks=[{"name": "Order ID"}],
        right_join_blocks=[{"name": "Order ID as per Uber Eats manager"}],
    )

    assert joins == [
        {
            "source_a": "src_a",
            "source_a_name": "orders_detail",
            "col_a": "Order ID",
            "source_b": "src_b",
            "source_b_name": "orders_financial",
            "col_b": "Order ID as per Uber Eats manager",
            "method": "fast_shared_value_join",
            "confidence": 0.78,
            "cardinality": "many_to_many",
            "overlap": 1.0,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_keeps_mojo_for_non_decisive_fast_key_join(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    mojo_calls = 0

    async def _fake_mojo(*_args, **_kwargs):
        nonlocal mojo_calls
        mojo_calls += 1
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _fake_mojo)

    left_rows = [{"part_number": f"P{i:03d}", "measure_total": float(i)} for i in range(100)]
    right_rows = []
    for i in range(6):
        right_rows.append({"part_number": f"P{i:03d}", "segment_label": f"seg_{i}"})
        right_rows.append({"part_number": f"P{i:03d}", "segment_label": f"seg_{i}_dup"})

    joins = await _detect_joins_between(
        "org_detect_non_decisive",
        "src_a",
        "S0",
        _parquet_bytes(left_rows),
        "src_b",
        "S1",
        _parquet_bytes(right_rows),
        left_join_blocks=[{"name": "part_number"}],
        right_join_blocks=[{"name": "part_number"}],
    )

    assert mojo_calls == 1
    assert joins == [
        {
            "source_a": "src_a",
            "source_a_name": "S0",
            "col_a": "part_number",
            "source_b": "src_b",
            "source_b_name": "S1",
            "col_b": "part_number",
            "method": "fast_shared_value_join",
            "confidence": 0.753,
            "cardinality": "one_to_many",
            "overlap": 0.06,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_rejects_mojo_for_semantically_mismatched_surrogate_ids(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _fake_mojo(*_args, **_kwargs):
        return {
            "join_keys": [
                {
                    "field_a": "FAX_ID",
                    "field_b": "EMAIL_CENTER_LINK_ID",
                    "confidence": 0.98,
                    "cardinality": "many_to_one",
                    "overlap": 1.0,
                }
            ]
        }

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _fake_mojo)

    left_rows = [{"FAX_ID": i, "measure_total": float(i)} for i in range(1, 33)]
    right_rows = [{"EMAIL_CENTER_LINK_ID": i, "segment_label": f"seg_{i}"} for i in range(1, 33)]

    joins = await _detect_joins_between(
        "org_detect_semantic_mismatch",
        "src_a",
        "Faxes",
        _parquet_bytes(left_rows),
        "src_b",
        "EmailLinks",
        _parquet_bytes(right_rows),
        left_join_blocks=[{"name": "FAX_ID"}],
        right_join_blocks=[{"name": "EMAIL_CENTER_LINK_ID"}],
    )

    assert joins == []


@pytest.mark.anyio
async def test_detect_joins_between_keeps_mojo_for_same_entity_key_alias(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    async def _fake_mojo(*_args, **_kwargs):
        return {
            "join_keys": [
                {
                    "field_a": "order_id",
                    "field_b": "order_number",
                    "confidence": 0.91,
                    "cardinality": "one_to_one",
                    "overlap": 1.0,
                }
            ]
        }

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _fake_mojo)

    left_rows = [{"order_id": f"O{i:03d}", "measure_total": float(i)} for i in range(1, 17)]
    right_rows = [{"order_number": f"O{i:03d}", "segment_label": f"seg_{i}"} for i in range(1, 17)]

    joins = await _detect_joins_between(
        "org_detect_same_entity_alias",
        "src_a",
        "OrdersLeft",
        _parquet_bytes(left_rows),
        "src_b",
        "OrdersRight",
        _parquet_bytes(right_rows),
        left_join_blocks=[{"name": "order_id"}],
        right_join_blocks=[{"name": "order_number"}],
    )

    assert joins == [
        {
            "source_a": "src_a",
            "source_a_name": "OrdersLeft",
            "col_a": "order_id",
            "source_b": "src_b",
            "source_b_name": "OrdersRight",
            "col_b": "order_number",
            "method": "mojo_join_detect",
            "confidence": 0.91,
            "cardinality": "one_to_one",
            "overlap": 1.0,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_rejects_mojo_for_zero_overlap_edges(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    async def _fake_mojo(*_args, **_kwargs):
        return {
            "join_keys": [
                {
                    "field_a": "account_id",
                    "field_b": "account_id",
                    "confidence": 0.5,
                    "cardinality": "1:1",
                    "overlap": 0.0,
                }
            ]
        }

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _fake_mojo)

    left_rows = [{"account_id": f"A{i:03d}", "measure_total": float(i)} for i in range(1, 17)]
    right_rows = [{"account_id": f"B{i:03d}", "segment_label": f"seg_{i}"} for i in range(1, 17)]

    joins = await _detect_joins_between(
        "org_detect_zero_overlap",
        "src_a",
        "AccountsLeft",
        _parquet_bytes(left_rows),
        "src_b",
        "AccountsRight",
        _parquet_bytes(right_rows),
        left_join_blocks=[{"name": "account_id"}],
        right_join_blocks=[{"name": "account_id"}],
    )

    assert joins == []


@pytest.mark.anyio
async def test_detect_joins_between_adds_source_aligned_foreign_key_for_large_sparse_pair(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    joins = await _detect_joins_between(
        "org_detect_source_aligned_fk",
        "src_a",
        "Ancillaries",
        None,
        "src_b",
        "Pnrs",
        None,
        src_df=pd.DataFrame({"pnr_id": ["PNR_00001"]}),
        other_df=pd.DataFrame({"id": ["PNR_99999"]}),
        src_value_candidates={
            "pnr_id": {
                "values": [f"PNR_{i:05d}" for i in range(1000)],
                "unique_ratio": 0.84,
                "sample_size": 100_000,
            }
        },
        other_value_candidates={
            "id": {
                "values": [f"OTHER_{i:05d}" for i in range(1000)],
                "unique_ratio": 1.0,
                "sample_size": 100_000,
            }
        },
        left_join_blocks=[
            {
                "name": "pnr_id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 0.84,
                "unique_count": 900_000,
            }
        ],
        right_join_blocks=[
            {
                "name": "id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 1.0,
                "unique_count": 900_000,
            }
        ],
    )

    assert joins == [
        {
            "source_a": "src_a",
            "source_a_name": "Ancillaries",
            "col_a": "pnr_id",
            "source_b": "src_b",
            "source_b_name": "Pnrs",
            "col_b": "id",
            "method": "source_aligned_foreign_key_join",
            "confidence": 0.76,
            "cardinality": "many_to_one",
            "overlap": 0.0,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_keeps_sparse_fk_to_tiny_dimension(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    joins = await _detect_joins_between(
        "org_detect_sparse_tiny_dimension_fk",
        "src_alliances",
        "alliances",
        None,
        "src_airlines",
        "airlines",
        None,
        src_df=pd.DataFrame({"id": [1, 2, 3]}),
        other_df=pd.DataFrame(
            {
                "alliance_id": [1, None, None, None, 2, None, None, 3],
            }
        ),
        src_value_candidates={
            "id": {
                "values": ["1", "2", "3"],
                "unique_ratio": 1.0,
                "sample_size": 3,
            }
        },
        other_value_candidates={
            "alliance_id": {
                "values": ["1", "2", "3"],
                "unique_ratio": 0.375,
                "sample_size": 8,
            }
        },
        left_join_blocks=[
            {
                "name": "id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 1.0,
                "unique_count": 3,
            }
        ],
        right_join_blocks=[
            {
                "name": "alliance_id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 0.375,
                "unique_ratio": 0.375,
                "unique_count": 3,
            }
        ],
    )

    assert joins == [
        {
            "source_a": "src_alliances",
            "source_a_name": "alliances",
            "col_a": "id",
            "source_b": "src_airlines",
            "source_b_name": "airlines",
            "col_b": "alliance_id",
            "method": "source_aligned_foreign_key_join",
            "confidence": 0.84,
            "cardinality": "one_to_many",
            "overlap": 1.0,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_rejects_source_aligned_foreign_key_for_small_zero_overlap_pair(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    joins = await _detect_joins_between(
        "org_detect_small_source_aligned_fk",
        "src_a",
        "Orders",
        None,
        "src_b",
        "Customers",
        None,
        src_df=pd.DataFrame({"customer_id": ["C0001"]}),
        other_df=pd.DataFrame({"id": ["C9999"]}),
        src_value_candidates={
            "customer_id": {
                "values": [f"C{i:04d}" for i in range(100)],
                "unique_ratio": 0.8,
                "sample_size": 500,
            }
        },
        other_value_candidates={
            "id": {
                "values": [f"Z{i:04d}" for i in range(100)],
                "unique_ratio": 1.0,
                "sample_size": 500,
            }
        },
        left_join_blocks=[
            {
                "name": "customer_id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 0.8,
                "unique_count": 400,
            }
        ],
        right_join_blocks=[
            {
                "name": "id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 1.0,
                "unique_count": 500,
            }
        ],
    )

    assert joins == []


@pytest.mark.anyio
async def test_register_source_detects_late_sparse_small_dimension_foreign_key(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_sparse_small_dimension"

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    airlines_rows = ["id,alliance_id,name,hub_city_id"]
    for airline_id in range(1, 25):
        alliance_id = ""
        if airline_id == 1:
            alliance_id = "1"
        elif airline_id == 7:
            alliance_id = "2"
        elif airline_id == 19:
            alliance_id = "3"
        airlines_rows.append(
            f"{airline_id},{alliance_id},Carrier {airline_id:03d},{100 + airline_id}"
        )

    airlines_response = await register_source(
        RegisterRequest(
            source=DataSource(
                name="airlines",
                csv="\n".join(airlines_rows) + "\n",
            )
        ),
        auth={"org_id": "org_sparse_small_dimension"},
    )
    assert airlines_response["connections_found"] == []

    alliances_response = await register_source(
        RegisterRequest(
            source=DataSource(
                name="alliances",
                csv=("id,name,hq_city_id\n1,oneworld,201\n2,SkyTeam,202\n3,Star Alliance,203\n"),
            )
        ),
        auth={"org_id": "org_sparse_small_dimension"},
    )

    assert alliances_response["join_candidates_considered"] == 1
    assert alliances_response["join_existing_total"] == 1
    assert alliances_response["connections_found"] == [
        {
            "source_a": alliances_response["source_id"],
            "source_a_name": "alliances",
            "col_a": "id",
            "source_b": airlines_response["source_id"],
            "source_b_name": "airlines",
            "col_b": "alliance_id",
            "method": "source_aligned_foreign_key_join",
            "confidence": 0.9,
            "cardinality": "one_to_one",
            "overlap": 1.0,
        }
    ]


@pytest.mark.anyio
async def test_register_source_detects_late_moderate_domain_dimension_foreign_key(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_moderate_dimension"

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    aircraft_rows = ["id,aircraft_type_id,registration"]
    for aircraft_id in range(1, 39):
        aircraft_type_id = ((aircraft_id - 1) % 19) + 1
        aircraft_rows.append(f"{aircraft_id},{aircraft_type_id},N{aircraft_id:04d}")

    aircraft_response = await register_source(
        RegisterRequest(
            source=DataSource(
                name="aircraft",
                csv="\n".join(aircraft_rows) + "\n",
            )
        ),
        auth={"org_id": "org_moderate_dimension"},
    )
    assert aircraft_response["connections_found"] == []

    aircraft_types_rows = ["id,iata_code"]
    for type_id in range(1, 21):
        aircraft_types_rows.append(f"{type_id},T{type_id:02d}")

    aircraft_types_response = await register_source(
        RegisterRequest(
            source=DataSource(
                name="aircraft_types",
                csv="\n".join(aircraft_types_rows) + "\n",
            )
        ),
        auth={"org_id": "org_moderate_dimension"},
    )

    assert aircraft_types_response["join_candidates_considered"] == 1
    assert aircraft_types_response["join_existing_total"] == 1
    assert aircraft_types_response["connections_found"] == [
        {
            "source_a": aircraft_types_response["source_id"],
            "source_a_name": "aircraft_types",
            "col_a": "id",
            "source_b": aircraft_response["source_id"],
            "source_b_name": "aircraft",
            "col_b": "aircraft_type_id",
            "method": "source_aligned_foreign_key_join",
            "confidence": 0.84,
            "cardinality": "one_to_many",
            "overlap": 0.95,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_ignores_unrelated_bare_id_metadata_fast_join_in_favor_of_source_aligned_fk(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    joins = await _detect_joins_between(
        "org_detect_source_aligned_over_id",
        "src_airports",
        "airports",
        None,
        "src_bags",
        "bag_handling_metrics",
        None,
        src_df=pd.DataFrame({"id": ["AIRPORT_9000"]}),
        other_df=pd.DataFrame({"id": ["BAG_9000"], "airport_id": ["AIRPORT_0001"]}),
        src_value_candidates={
            "id": {
                "values": [f"AIRPORT_{i:04d}" for i in range(40)],
                "unique_ratio": 1.0,
                "sample_size": 3_557,
            }
        },
        other_value_candidates={
            "id": {
                "values": [f"AIRPORT_{i:04d}" for i in range(40)],
                "unique_ratio": 1.0,
                "sample_size": 100_000,
            },
            "airport_id": {
                "values": [f"AIRPORT_{i:04d}" for i in range(40)],
                "unique_ratio": 0.04,
                "sample_size": 100_000,
            },
        },
        left_join_blocks=[
            {
                "name": "id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 1.0,
                "unique_count": 3_557,
                "samples": ["AIRPORT_0001", "AIRPORT_0002", "AIRPORT_0003"],
            }
        ],
        right_join_blocks=[
            {
                "name": "id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 1.0,
                "unique_count": 100_000,
                "samples": ["AIRPORT_0001", "AIRPORT_0002", "AIRPORT_0003"],
            },
            {
                "name": "airport_id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 0.04,
                "unique_count": 3_557,
                "samples": ["AIRPORT_0001", "AIRPORT_0002", "AIRPORT_0003"],
            },
        ],
    )

    assert joins == [
        {
            "source_a": "src_airports",
            "source_a_name": "airports",
            "col_a": "id",
            "source_b": "src_bags",
            "source_b_name": "bag_handling_metrics",
            "col_b": "airport_id",
            "method": "source_aligned_foreign_key_join",
            "confidence": 0.84,
            "cardinality": "one_to_many",
            "overlap": 1.0,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_does_not_treat_bare_name_as_source_aligned_reference(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    joins = await _detect_joins_between(
        "org_detect_source_aligned_name_guard",
        "src_bags",
        "bag_handling_metrics",
        None,
        "src_airports",
        "airports",
        None,
        src_df=pd.DataFrame({"airport_id": ["AIRPORT_0001"]}),
        other_df=pd.DataFrame({"id": ["AIRPORT_0001"], "name": ["AIRPORT_0001"]}),
        src_value_candidates={
            "airport_id": {
                "values": [f"AIRPORT_{i:04d}" for i in range(40)],
                "unique_ratio": 0.04,
                "sample_size": 100_000,
            }
        },
        other_value_candidates={
            "id": {
                "values": [f"AIRPORT_{i:04d}" for i in range(40)],
                "unique_ratio": 1.0,
                "sample_size": 3_557,
            },
            "name": {
                "values": [f"AIRPORT_{i:04d}" for i in range(40)],
                "unique_ratio": 1.0,
                "sample_size": 3_557,
            },
        },
        left_join_blocks=[
            {
                "name": "airport_id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 0.04,
                "unique_count": 3_557,
                "samples": ["AIRPORT_0001", "AIRPORT_0002", "AIRPORT_0003"],
            }
        ],
        right_join_blocks=[
            {
                "name": "id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 1.0,
                "unique_count": 3_557,
                "samples": ["AIRPORT_0001", "AIRPORT_0002", "AIRPORT_0003"],
            },
            {
                "name": "name",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 1.0,
                "unique_count": 3_557,
                "samples": ["AIRPORT_0001", "AIRPORT_0002", "AIRPORT_0003"],
            },
        ],
    )

    assert joins == [
        {
            "source_a": "src_bags",
            "source_a_name": "bag_handling_metrics",
            "col_a": "airport_id",
            "source_b": "src_airports",
            "source_b_name": "airports",
            "col_b": "id",
            "method": "source_aligned_foreign_key_join",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_rejects_unrelated_bare_id_fast_and_mojo_shortcuts(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _fake_mojo(*_args, **_kwargs):
        return {
            "join_keys": [
                {
                    "field_a": "id",
                    "field_b": "id",
                    "confidence": 0.95,
                    "overlap": 0.9,
                    "cardinality": "1:1",
                }
            ]
        }

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _fake_mojo)

    joins = await _detect_joins_between(
        "org_detect_bare_id_shortcuts",
        "src_cities",
        "cities",
        None,
        "src_airports",
        "airports",
        None,
        src_df=pd.DataFrame(
            {
                "id": [str(index) for index in range(1, 41)],
                "name": [f"CITY_{index:03d}" for index in range(1, 41)],
            }
        ),
        other_df=pd.DataFrame(
            {
                "id": [str(index) for index in range(1, 41)],
                "name": [f"AIRPORT_{index:03d}" for index in range(1, 41)],
            }
        ),
        left_join_blocks=[
            {
                "name": "id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 1.0,
                "unique_count": 40,
                "samples": ["1", "2", "3"],
            }
        ],
        right_join_blocks=[
            {
                "name": "id",
                "key_like": True,
                "role": "identifier",
                "fill_rate": 1.0,
                "unique_ratio": 1.0,
                "unique_count": 40,
                "samples": ["1", "2", "3"],
            }
        ],
    )

    assert joins == []


@pytest.mark.anyio
async def test_detect_joins_between_skips_mojo_for_very_large_pair_with_single_normalized_key(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _should_not_call_mojo(*_args, **_kwargs):
        raise AssertionError(
            "Mojo join detect should not run for a very large pair already connected by a strong normalized key"
        )

    monkeypatch.setattr(
        "apps.api_server.routers.sources._call_mojo_join_detect",
        _should_not_call_mojo,
    )

    left_unique = [f"P{i:04d}" for i in range(2_000)]
    right_unique = [f"P{i:04d}" for i in range(246)]
    left_df = pd.DataFrame(
        {
            "PART_NUMBER": [left_unique[i % len(left_unique)] for i in range(20_050)],
            "measure_total": [float(i % 101) for i in range(20_050)],
        }
    )
    right_df = pd.DataFrame(
        {
            "PART_NUMBER": [right_unique[i % len(right_unique)] for i in range(4_920)],
            "segment_label": [f"seg_{i}" for i in range(4_920)],
        }
    )

    joins = await _detect_joins_between(
        "org_detect_large_normalized_key",
        "src_a",
        "S0",
        None,
        "src_b",
        "S1",
        None,
        src_df=left_df,
        other_df=right_df,
        left_join_blocks=[{"name": "PART_NUMBER"}],
        right_join_blocks=[{"name": "PART_NUMBER"}],
    )

    assert joins == [
        {
            "source_a": "src_a",
            "source_a_name": "S0",
            "col_a": "PART_NUMBER",
            "source_b": "src_b",
            "source_b_name": "S1",
            "col_b": "PART_NUMBER",
            "method": "fast_shared_value_join",
            "confidence": 0.622,
            "cardinality": "many_to_many",
            "overlap": 0.123,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_skips_mojo_for_medium_large_pair_with_single_normalized_key(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _should_not_call_mojo(*_args, **_kwargs):
        raise AssertionError(
            "Mojo join detect should not run once a medium-large pair is already connected by a strong normalized key"
        )

    monkeypatch.setattr(
        "apps.api_server.routers.sources._call_mojo_join_detect",
        _should_not_call_mojo,
    )

    left_unique = [f"P{i:04d}" for i in range(1_200)]
    right_unique = [f"P{i:04d}" for i in range(160)]
    left_df = pd.DataFrame(
        {
            "PART_NUMBER": [left_unique[i % len(left_unique)] for i in range(10_250)],
            "measure_total": [float(i % 101) for i in range(10_250)],
        }
    )
    right_df = pd.DataFrame(
        {
            "PART_NUMBER": right_unique,
            "segment_label": [f"seg_{i}" for i in range(len(right_unique))],
        }
    )

    joins = await _detect_joins_between(
        "org_detect_medium_large_normalized_key",
        "src_a",
        "S0",
        None,
        "src_b",
        "S1",
        None,
        src_df=left_df,
        other_df=right_df,
        left_join_blocks=[{"name": "PART_NUMBER"}],
        right_join_blocks=[{"name": "PART_NUMBER"}],
    )

    assert joins == [
        {
            "source_a": "src_a",
            "source_a_name": "S0",
            "col_a": "PART_NUMBER",
            "source_b": "src_b",
            "source_b_name": "S1",
            "col_b": "PART_NUMBER",
            "method": "fast_shared_value_join",
            "confidence": 0.769,
            "cardinality": "many_to_one",
            "overlap": 0.1333,
        }
    ]


@pytest.mark.anyio
async def test_detect_joins_between_reduces_value_candidate_limit_when_fast_connections_exist(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()
    captured_limits: list[tuple[str, int]] = []

    async def _fake_mojo(*_args, **_kwargs):
        return None

    def _fake_value_candidates(*, source_id, limit=20, **_kwargs):  # type: ignore[no-untyped-def]
        captured_limits.append((source_id, limit))
        return {
            "part_number": {
                "values": [f"P{i:03d}" for i in range(12)],
                "unique_ratio": 1.0,
                "sample_size": 12,
            }
        }

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _fake_mojo)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._load_join_value_candidates_cached",
        _fake_value_candidates,
    )

    left_rows = [{"part_number": f"P{i:03d}", "measure_total": float(i)} for i in range(100)]
    right_rows = []
    for i in range(6):
        right_rows.append({"part_number": f"P{i:03d}", "segment_label": f"seg_{i}"})
        right_rows.append({"part_number": f"P{i:03d}", "segment_label": f"seg_{i}_dup"})

    await _detect_joins_between(
        "org_detect_non_decisive_limit",
        "src_a",
        "S0",
        _parquet_bytes(left_rows),
        "src_b",
        "S1",
        _parquet_bytes(right_rows),
        left_join_blocks=[{"name": "part_number"}],
        right_join_blocks=[{"name": "part_number"}],
    )

    assert captured_limits == [("src_a", 8), ("src_b", 8)]


@pytest.mark.anyio
async def test_detect_joins_between_reduces_value_candidate_limit_for_wide_large_sources(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()
    captured_limits: list[tuple[str, int]] = []

    async def _fake_mojo(*_args, **_kwargs):
        return None

    def _fake_name_stats(*, source_id, **_kwargs):  # type: ignore[no-untyped-def]
        return {
            f"{source_id}_key": {
                "counts": {},
                "values": set(),
                "unique_ratio": 1.0,
                "all_unique": True,
            }
        }

    def _fake_value_candidates(*, source_id, limit=20, **_kwargs):  # type: ignore[no-untyped-def]
        captured_limits.append((source_id, limit))
        return {
            "part_number": {
                "values": [f"P{i:03d}" for i in range(12)],
                "unique_ratio": 1.0,
                "sample_size": 12,
            }
        }

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _fake_mojo)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._load_join_name_stats_cached",
        _fake_name_stats,
    )
    monkeypatch.setattr(
        "apps.api_server.routers.sources._load_join_value_candidates_cached",
        _fake_value_candidates,
    )

    left_df = pd.DataFrame(
        {f"left_{i:02d}": [f"L{i}_{row}" for row in range(8_100)] for i in range(56)}
    )
    right_df = pd.DataFrame(
        {f"right_{i:02d}": [f"R{i}_{row}" for row in range(8_050)] for i in range(57)}
    )

    await _detect_joins_between(
        "org_detect_wide_large_limit",
        "src_a",
        "S0",
        None,
        "src_b",
        "S1",
        None,
        src_df=left_df,
        other_df=right_df,
    )

    assert captured_limits == [("src_a", 6), ("src_b", 6)]


@pytest.mark.anyio
async def test_detect_joins_between_skips_name_stats_without_metadata_name_signal(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()
    captured_limits: list[tuple[str, int]] = []

    async def _fake_mojo(*_args, **_kwargs):
        return None

    def _unexpected_name_stats(**_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("name stats should be skipped when metadata shows no name signal")

    def _fake_value_candidates(*, source_id, limit=20, **_kwargs):  # type: ignore[no-untyped-def]
        captured_limits.append((source_id, limit))
        return {}

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _fake_mojo)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._load_join_name_stats_cached",
        _unexpected_name_stats,
    )
    monkeypatch.setattr(
        "apps.api_server.routers.sources._load_join_value_candidates_cached",
        _fake_value_candidates,
    )

    left_df = pd.DataFrame(
        {
            "alpha_metric": [f"A{row}" for row in range(250)],
            "alpha_total": list(range(250)),
        }
    )
    right_df = pd.DataFrame(
        {
            "vendor_region": [f"R{row}" for row in range(250)],
            "vendor_state": [f"S{row % 10}" for row in range(250)],
        }
    )

    joins = await _detect_joins_between(
        "org_detect_no_name_signal",
        "src_a",
        "Alpha",
        None,
        "src_b",
        "Vendor",
        None,
        src_df=left_df,
        other_df=right_df,
        left_join_blocks=[{"name": "alpha_metric", "tail": "alpha_metric"}],
        right_join_blocks=[{"name": "vendor_region", "tail": "vendor_region"}],
    )

    assert joins == []
    assert captured_limits == [("src_a", 20), ("src_b", 20)]


@pytest.mark.anyio
async def test_detect_joins_between_accepts_preloaded_source_projection(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    left = _parquet_bytes(
        [
            {"entity_key": "A", "measure_total": 10.0},
            {"entity_key": "B", "measure_total": 20.0},
        ]
    )
    right = _parquet_bytes(
        [
            {"entity_key": "A", "segment_label": "seg_1"},
            {"entity_key": "B", "segment_label": "seg_2"},
        ]
    )
    preloaded_left = _load_join_projection(left, [{"name": "entity_key"}])

    joins = await _detect_joins_between(
        "org_detect_preloaded",
        "src_a",
        "S0",
        left,
        "src_b",
        "S1",
        right,
        src_df=preloaded_left,
        left_join_blocks=[{"name": "entity_key"}],
        right_join_blocks=[{"name": "entity_key"}],
    )

    assert joins[0]["col_a"] == "entity_key"
    assert joins[0]["col_b"] == "entity_key"
    assert joins[0]["cardinality"] == "one_to_one"


@pytest.mark.anyio
async def test_detect_joins_between_supports_parquet_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    left_meta = _schema_meta_for_columns(
        2,
        [{"name": "entity_key", "role": "identifier", "unique_count": 2, "samples": ["A", "B"]}],
    )
    right_meta = _schema_meta_for_columns(
        2,
        [{"name": "entity_key", "role": "identifier", "unique_count": 2, "samples": ["A", "B"]}],
    )
    reg.register_source(
        "org_detect_paths",
        "src_a",
        "S0",
        _parquet_bytes(
            [
                {"entity_key": "A", "measure_total": 10.0},
                {"entity_key": "B", "measure_total": 20.0},
            ]
        ),
        left_meta,
        graph_nodes={},
        profile={},
    )
    reg.register_source(
        "org_detect_paths",
        "src_b",
        "S1",
        _parquet_bytes(
            [
                {"entity_key": "A", "segment_label": "seg_1"},
                {"entity_key": "B", "segment_label": "seg_2"},
            ]
        ),
        right_meta,
        graph_nodes={},
        profile={},
    )

    left_path = reg.get_source_parquet_path("org_detect_paths", "src_a")
    right_path = reg.get_source_parquet_path("org_detect_paths", "src_b")
    assert left_path is not None
    assert right_path is not None

    joins = await _detect_joins_between(
        "org_detect_paths",
        "src_a",
        "S0",
        None,
        "src_b",
        "S1",
        None,
        src_parquet_path=left_path,
        other_parquet_path=right_path,
        left_join_blocks=[{"name": "entity_key"}],
        right_join_blocks=[{"name": "entity_key"}],
    )

    assert joins[0]["col_a"] == "entity_key"
    assert joins[0]["col_b"] == "entity_key"
    assert joins[0]["cardinality"] == "one_to_one"


@pytest.mark.anyio
async def test_detect_joins_between_skips_generic_many_to_many_same_name_columns(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    left = _parquet_bytes(
        [
            {"local_group": "g_a", "late_value": 1.0},
            {"local_group": "g_a", "late_value": 2.0},
            {"local_group": "g_b", "late_value": 3.0},
            {"local_group": "g_b", "late_value": 4.0},
        ]
    )
    right = _parquet_bytes(
        [
            {"local_group": "g_a", "measure_total": 10.0},
            {"local_group": "g_a", "measure_total": 20.0},
            {"local_group": "g_b", "measure_total": 30.0},
            {"local_group": "g_b", "measure_total": 40.0},
        ]
    )

    joins = await _detect_joins_between(
        "org_detect_many", "src_a", "L0", left, "src_b", "S0", right
    )

    assert joins == []


@pytest.mark.anyio
async def test_detect_joins_between_skips_mojo_when_fast_joins_already_prove_pair(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    async def _should_not_call_mojo(*_args, **_kwargs):
        raise AssertionError(
            "Mojo join detect should not run when fast joins already prove the pair"
        )

    monkeypatch.setattr(
        "apps.api_server.routers.sources._call_mojo_join_detect",
        _should_not_call_mojo,
    )

    left = _parquet_bytes(
        [
            {"customer_id": "C1", "part_number": "P1", "measure_total": 10.0},
            {"customer_id": "C1", "part_number": "P2", "measure_total": 12.0},
            {"customer_id": "C2", "part_number": "P2", "measure_total": 14.0},
            {"customer_id": "C2", "part_number": "P3", "measure_total": 16.0},
            {"customer_id": "C3", "part_number": "P3", "measure_total": 18.0},
            {"customer_id": "C3", "part_number": "P4", "measure_total": 20.0},
            {"customer_id": "C4", "part_number": "P4", "measure_total": 22.0},
            {"customer_id": "C4", "part_number": "P1", "measure_total": 24.0},
        ]
    )
    right = _parquet_bytes(
        [
            {"customer_id": "C1", "part_number": "P1", "segment_label": "s1"},
            {"customer_id": "C1", "part_number": "P2", "segment_label": "s2"},
            {"customer_id": "C2", "part_number": "P2", "segment_label": "s3"},
            {"customer_id": "C2", "part_number": "P3", "segment_label": "s4"},
            {"customer_id": "C3", "part_number": "P3", "segment_label": "s5"},
            {"customer_id": "C3", "part_number": "P4", "segment_label": "s6"},
            {"customer_id": "C4", "part_number": "P4", "segment_label": "s7"},
            {"customer_id": "C4", "part_number": "P1", "segment_label": "s8"},
        ]
    )

    joins = await _detect_joins_between(
        "org_detect_fast_only",
        "src_a",
        "L0",
        left,
        "src_b",
        "S0",
        right,
        left_join_blocks=[{"name": "customer_id"}, {"name": "part_number"}],
        right_join_blocks=[{"name": "customer_id"}, {"name": "part_number"}],
    )

    assert _has_sufficient_fast_join_evidence(joins) is True
    assert joins == _bounded_fast_join_connections(joins)
    assert {(join["col_a"], join["col_b"]) for join in joins} == {
        ("customer_id", "customer_id"),
        ("part_number", "part_number"),
    }


@pytest.mark.anyio
async def test_detect_joins_between_skips_mojo_for_wide_pair_with_strong_fast_edges(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _should_not_call_mojo(*_args, **_kwargs):
        raise AssertionError(
            "Mojo join detect should not run for a wide pair already connected by fast edges"
        )

    monkeypatch.setattr(
        "apps.api_server.routers.sources._call_mojo_join_detect",
        _should_not_call_mojo,
    )

    left_rows = [
        {
            "customer_id": f"C{i % 8}",
            "store_name": f"Store {i % 4}",
            "measure_total": float(i),
        }
        for i in range(128)
    ]
    right_rows = [
        {
            "customer_id": f"C{i % 8}",
            "store_name": f"Store {i % 4}",
            "segment_label": f"seg_{i}",
        }
        for i in range(16)
    ]
    left_join_blocks = [
        {"name": "customer_id"},
        {"name": "store_name"},
        *({"name": f"wide_key_{i:02d}"} for i in range(10)),
    ]
    right_join_blocks = [
        {"name": "customer_id"},
        {"name": "store_name"},
        *({"name": f"wide_key_{i:02d}"} for i in range(10)),
    ]

    joins = await _detect_joins_between(
        "org_detect_fast_wide_pair",
        "src_a",
        "L0",
        _parquet_bytes(left_rows),
        "src_b",
        "S0",
        _parquet_bytes(right_rows),
        left_join_blocks=left_join_blocks,
        right_join_blocks=right_join_blocks,
    )

    assert {(join["col_a"], join["col_b"]) for join in joins} == {
        ("customer_id", "customer_id"),
        ("store_name", "store_name"),
    }


@pytest.mark.anyio
async def test_detect_joins_between_skips_mojo_for_very_large_wide_pair_with_one_strong_key(
    monkeypatch,
):
    _JOIN_PROJECTION_CACHE.clear()

    async def _should_not_call_mojo(*_args, **_kwargs):
        raise AssertionError(
            "Mojo join detect should not run for a very large wide pair with a strong key-like fast edge"
        )

    monkeypatch.setattr(
        "apps.api_server.routers.sources._call_mojo_join_detect",
        _should_not_call_mojo,
    )

    left_df = pd.DataFrame(
        {
            "part_number": [f"P{i:05d}" for i in range(25_000)],
            "measure_total": [float(i % 101) for i in range(25_000)],
        }
    )
    right_df = pd.DataFrame(
        {
            "part_number": [f"P{i:05d}" for i in range(8_000)],
            "segment_label": [f"seg_{i}" for i in range(8_000)],
        }
    )
    filler_blocks = [{"name": f"wide_key_{i:02d}"} for i in range(8)]
    left_join_blocks = [
        {
            "name": "part_number",
            "samples": ["P00000", "P00001", "P00002", "P00003"],
            "unique_ratio": 1.0,
        },
        *filler_blocks,
    ]
    right_join_blocks = [
        {
            "name": "part_number",
            "samples": ["P00000", "P00001", "P00002", "P00003"],
            "unique_ratio": 1.0,
        },
        *filler_blocks,
    ]

    joins = await _detect_joins_between(
        "org_detect_very_large_wide_fast_pair",
        "src_a",
        "L0",
        None,
        "src_b",
        "S0",
        None,
        src_df=left_df,
        other_df=right_df,
        left_join_blocks=left_join_blocks,
        right_join_blocks=right_join_blocks,
    )

    assert joins == [
        {
            "source_a": "src_a",
            "source_a_name": "L0",
            "col_a": "part_number",
            "source_b": "src_b",
            "source_b_name": "S0",
            "col_b": "part_number",
            "method": "metadata_fast_join",
            "confidence": 0.99,
            "cardinality": "one_to_one",
            "overlap": 1.0,
        }
    ]


def test_schema_revision_changes_with_registered_sources_and_connections(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    empty_rev = reg.schema_revision("org_rev")

    reg.register_source(
        "org_rev",
        "src_a",
        "Alpha",
        _parquet_bytes([{"entity_key": "A", "measure_total": 10.0}]),
        {
            "row_count": 1,
            "roles_summary": {"derived_measure": 1},
            "columns": [{"name": "measure_total"}],
        },
        graph_nodes={},
        profile={},
    )
    source_rev = reg.schema_revision("org_rev")

    reg.upsert_connections(
        "org_rev",
        [
            {
                "source_a": "src_a",
                "source_a_name": "Alpha",
                "col_a": "entity_key",
                "source_b": "src_b",
                "source_b_name": "Beta",
                "col_b": "entity_key",
                "confidence": 0.97,
                "cardinality": "one_to_one",
                "overlap": 1.0,
            }
        ],
    )
    graph_rev = reg.schema_revision("org_rev")

    assert empty_rev != source_rev
    assert source_rev != graph_rev


def test_schema_revision_reuses_cached_revision_when_registry_fingerprint_is_unchanged(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    reg._SCHEMA_REVISION_CACHE.clear()

    reg.register_source(
        "org_rev_cached",
        "src_a",
        "Alpha",
        _parquet_bytes([{"entity_key": "A", "measure_total": 10.0}]),
        {
            "row_count": 1,
            "roles_summary": {"derived_measure": 1},
            "columns": [{"name": "measure_total"}],
        },
        graph_nodes={},
        profile={},
    )
    first = reg.schema_revision("org_rev_cached")

    meta_path = Path(tmp_path) / "sources" / "org_rev_cached" / "src_a.meta.json"
    real_read_json = reg._read_json
    meta_reads = {"count": 0}

    def _counting_read_json(path: Path):  # type: ignore[no-untyped-def]
        if path == meta_path:
            meta_reads["count"] += 1
        return real_read_json(path)

    monkeypatch.setattr(reg, "_read_json", _counting_read_json)

    second = reg.schema_revision("org_rev_cached")
    third = reg.schema_revision("org_rev_cached")

    assert first == second == third
    assert meta_reads["count"] == 0


def test_schema_revision_cold_path_skips_source_meta_reads(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    reg._SCHEMA_REVISION_CACHE.clear()

    reg.register_source(
        "org_rev_no_meta_scan",
        "src_a",
        "Alpha",
        _parquet_bytes([{"entity_key": "A", "measure_total": 10.0}]),
        {
            "row_count": 1,
            "roles_summary": {"derived_measure": 1},
            "columns": [{"name": "measure_total"}],
            "semantic_aliases": {"sales": ["revenue"]},
            "query_hints": [{"hint": "sales", "column": "measure_total"}],
        },
        graph_nodes={},
        profile={},
    )
    reg._SCHEMA_REVISION_CACHE.clear()

    meta_path = Path(tmp_path) / "sources" / "org_rev_no_meta_scan" / "src_a.meta.json"
    real_read_json = reg._read_json
    meta_reads = {"count": 0}

    def _counting_read_json(path: Path):  # type: ignore[no-untyped-def]
        if path == meta_path:
            meta_reads["count"] += 1
        return real_read_json(path)

    monkeypatch.setattr(reg, "_read_json", _counting_read_json)

    revision = reg.schema_revision("org_rev_no_meta_scan")

    assert revision
    assert meta_reads["count"] == 0


@pytest.mark.anyio
async def test_register_source_prewarms_registry_planner_for_registered_and_already_registered(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    calls: list[tuple[str, str]] = []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        calls.append((org_id, llm_policy))
        return object(), len(calls) > 1, f"rev_{len(calls)}"

    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    payload = RegisterRequest(
        source=DataSource(
            name="S0",
            csv="entity_key,measure_total\nA,10\nB,20\n",
        )
    )

    first = await register_source(payload, auth={"org_id": "org_a"})
    second = await register_source(payload, auth={"org_id": "org_a"})

    assert first["status"] == "registered"
    assert second["status"] == "already_registered"
    assert first["planner_cache_hit"] is False
    assert second["planner_cache_hit"] is True
    assert len(calls) == 2
    assert calls == [("org_a", "never"), ("org_a", "never")]


@pytest.mark.anyio
async def test_register_source_reuses_new_source_join_stats_across_join_pairs(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for idx in range(2):
        meta = _schema_meta_for_columns(
            100,
            [
                {
                    "name": "customer_id",
                    "role": "identifier",
                    "unique_count": 100,
                    "samples": [f"C{idx:03d}", f"C{idx + 1:03d}", f"C{idx + 2:03d}"],
                },
                {
                    "name": "measure_total",
                    "role": "derived_measure",
                    "is_numeric": True,
                    "samples": [10, 20, 30],
                },
            ],
        )
        reg.register_source(
            "org_join_precompute",
            f"s_{idx}",
            f"S{idx}",
            _parquet_bytes(
                [
                    {"customer_id": f"C{idx:03d}", "measure_total": 10},
                    {"customer_id": f"C{idx + 1:03d}", "measure_total": 20},
                ]
            ),
            meta,
            graph_nodes={},
            profile={},
        )

    seen_name_stats: list[dict[str, dict[str, object]]] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **kwargs,
    ):
        seen_name_stats.append(kwargs["src_name_stats"])
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_join_precompute"

    monkeypatch.setattr(
        "apps.api_server.routers.sources._metadata_fast_join_candidates", lambda **_kwargs: []
    )
    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    payload = RegisterRequest(
        source=DataSource(
            name="Incoming",
            csv=(
                "customer_id,measure_total\n"
                + "\n".join(f"C{i:03d},{i}" for i in range(100))
                + "\n"
            ),
        )
    )

    registered = await register_source(payload, auth={"org_id": "org_join_precompute"})

    assert registered["join_existing_total"] == 2
    assert len(seen_name_stats) == 2
    assert len({id(item) for item in seen_name_stats}) == 1
    assert seen_name_stats[0]


def test_candidate_join_sources_blocks_large_org_to_likely_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    matching_meta = _schema_meta_for_columns(
        200,
        [
            {
                "name": "customer_id",
                "role": "identifier",
                "unique_count": 180,
                "samples": ["C100", "C200"],
            },
            {
                "name": "segment_label",
                "role": "category",
                "unique_count": 6,
                "samples": ["ENT", "SMB"],
            },
        ],
    )
    reg.register_source(
        "org_block",
        "match_src",
        "Match",
        _parquet_bytes([{"customer_id": "C100", "segment_label": "ENT"}]),
        matching_meta,
        graph_nodes={},
        profile={},
    )

    for i in range(40):
        meta = _schema_meta_for_columns(
            200,
            [
                {
                    "name": f"unrelated_key_{i}",
                    "role": "identifier",
                    "unique_count": 180,
                    "samples": [f"U{i}_1", f"U{i}_2"],
                },
                {
                    "name": f"status_{i}",
                    "role": "category",
                    "unique_count": 3,
                    "samples": ["open", "closed"],
                },
            ],
        )
        reg.register_source(
            "org_block",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes([{f"unrelated_key_{i}": f"U{i}_1", f"status_{i}": "open"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    incoming_meta = _schema_meta_for_columns(
        300,
        [
            {
                "name": "customer_id",
                "role": "identifier",
                "unique_count": 260,
                "samples": ["C100", "C300"],
            },
            {
                "name": "order_number",
                "role": "identifier",
                "unique_count": 300,
                "samples": ["O1", "O2"],
            },
        ],
    )

    candidates = reg.candidate_join_sources("org_block", "incoming", incoming_meta)
    candidate_ids = {entry["id"] for entry in candidates}

    assert "match_src" in candidate_ids
    assert len(candidates) <= 24
    assert len(candidates) < 41


def test_candidate_join_sources_keeps_exhaustive_mode_for_small_org(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    for i in range(3):
        meta = _schema_meta_for_columns(
            100,
            [
                {
                    "name": f"entity_{i}_id",
                    "role": "identifier",
                    "unique_count": 90,
                    "samples": [f"E{i}1"],
                }
            ],
        )
        reg.register_source(
            "org_small",
            f"s_{i}",
            f"S{i}",
            _parquet_bytes([{f"entity_{i}_id": f"E{i}1"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    incoming_meta = _schema_meta_for_columns(
        100,
        [{"name": "customer_id", "role": "identifier", "unique_count": 90, "samples": ["C1"]}],
    )
    candidates = reg.candidate_join_sources("org_small", "incoming", incoming_meta)

    assert {entry["id"] for entry in candidates} == {"s_0", "s_1", "s_2"}


def test_candidate_join_sources_prefers_source_aligned_foreign_key_targets(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    airport_meta = _schema_meta_for_columns(
        5_000,
        [
            {"name": "id", "role": "identifier", "unique_count": 5_000, "samples": ["A1", "A2"]},
            {
                "name": "iata_code",
                "role": "identifier",
                "unique_count": 4_800,
                "samples": ["JFK", "LAX"],
            },
        ],
    )
    reg.register_source(
        "org_source_aligned_candidates",
        "airports_src",
        "airports",
        _parquet_bytes([{"id": "A1", "iata_code": "JFK"}]),
        airport_meta,
        graph_nodes={},
        profile={},
    )

    for i in range(30):
        meta = _schema_meta_for_columns(
            5_000,
            [
                {
                    "name": f"entity_{i}_code",
                    "role": "identifier",
                    "unique_count": 4_500,
                    "samples": [f"E{i}1", f"E{i}2"],
                },
                {
                    "name": f"status_{i}",
                    "role": "category",
                    "unique_count": 4,
                    "samples": ["open", "closed"],
                },
            ],
        )
        reg.register_source(
            "org_source_aligned_candidates",
            f"noise_{i}",
            f"Noise{i}",
            _parquet_bytes([{f"entity_{i}_code": f"E{i}1", f"status_{i}": "open"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    incoming_meta = _schema_meta_for_columns(
        250_000,
        [
            {
                "name": "airport_id",
                "role": "identifier",
                "unique_count": 12_000,
                "samples": ["A10", "A11"],
            },
            {"name": "bags_mishandled", "role": "metric", "unique_count": 100, "samples": [1, 2]},
        ],
    )

    candidates = reg.candidate_join_sources(
        "org_source_aligned_candidates",
        "incoming",
        incoming_meta,
        source_name="bag_handling_metrics",
        exhaustive_threshold=0,
        limit=6,
    )

    assert any(entry["id"] == "airports_src" for entry in candidates)


@pytest.mark.anyio
async def test_register_source_uses_scored_join_scan_for_medium_sources_with_many_existing_candidates(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    matching_meta = _schema_meta_for_columns(
        200,
        [
            {
                "name": "customer_id",
                "role": "identifier",
                "unique_count": 180,
                "samples": ["C100", "C200"],
            },
            {
                "name": "order_number",
                "role": "identifier",
                "unique_count": 190,
                "samples": ["O100", "O200"],
            },
        ],
    )
    reg.register_source(
        "org_medium_scored",
        "match_src",
        "Match",
        _parquet_bytes([{"customer_id": "C100", "order_number": "O100"}]),
        matching_meta,
        graph_nodes={},
        profile={},
    )

    for i in range(11):
        meta = _schema_meta_for_columns(
            200,
            [
                {
                    "name": f"unrelated_key_{i}",
                    "role": "identifier",
                    "unique_count": 180,
                    "samples": [f"U{i}_1", f"U{i}_2"],
                },
                {
                    "name": f"segment_label_{i}",
                    "role": "category",
                    "unique_count": 4,
                    "samples": ["seg_a", "seg_b"],
                },
            ],
        )
        reg.register_source(
            "org_medium_scored",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes([{f"unrelated_key_{i}": f"U{i}_1", f"segment_label_{i}": "seg_a"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    join_calls: list[str] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **_kwargs,
    ):
        join_calls.append(other_id)
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_medium_scored"

    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = ["customer_id,order_number,vendor_code,serial_key,measure_total"]
    lines.extend(f"C{i:04d},O{i:04d},V{i:04d},S{i:04d},{i}" for i in range(3000))
    payload = RegisterRequest(source=DataSource(name="IncomingMedium", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_medium_scored"})

    assert registered["join_existing_total"] == 12
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] < 12
    assert "match_src" in join_calls
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.anyio
async def test_register_source_uses_scored_join_scan_for_expensive_small_org_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(5):
        col_name = "customer_id" if i == 0 else f"unrelated_key_{i}"
        samples = ["C100", "C200"] if i == 0 else [f"U{i}_1", f"U{i}_2"]
        meta = _schema_meta_for_columns(
            200,
            [{"name": col_name, "role": "identifier", "unique_count": 180, "samples": samples}],
        )
        reg.register_source(
            "org_small_scored",
            f"s_{i}",
            f"S{i}",
            _parquet_bytes([{col_name: samples[0]}]),
            meta,
            graph_nodes={},
            profile={},
        )

    join_calls: list[str] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **_kwargs,
    ):
        join_calls.append(other_id)
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_small_scored"

    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:04d},{i}" for i in range(6000))
    payload = RegisterRequest(source=DataSource(name="IncomingLarge", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_small_scored"})

    assert registered["join_existing_total"] == 5
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] < 5
    assert join_calls == ["s_0"]


@pytest.mark.anyio
async def test_register_source_uses_scored_join_scan_for_expensive_tiny_org_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    matching_meta = _schema_meta_for_columns(
        5_500,
        [
            {
                "name": "customer_id",
                "role": "identifier",
                "unique_count": 5_200,
                "samples": ["C100", "C200"],
            }
        ],
    )
    unrelated_meta = _schema_meta_for_columns(
        5_500,
        [
            {
                "name": "vendor_code",
                "role": "identifier",
                "unique_count": 5_100,
                "samples": ["V100", "V200"],
            }
        ],
    )
    reg.register_source(
        "org_tiny_scored",
        "match_src",
        "Match",
        _parquet_bytes([{"customer_id": "C100"}]),
        matching_meta,
        graph_nodes={},
        profile={},
    )
    reg.register_source(
        "org_tiny_scored",
        "other_src",
        "Other",
        _parquet_bytes([{"vendor_code": "V100"}]),
        unrelated_meta,
        graph_nodes={},
        profile={},
    )

    join_calls: list[str] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **_kwargs,
    ):
        join_calls.append(other_id)
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_tiny_scored"

    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:04d},{i}" for i in range(6_000))
    payload = RegisterRequest(source=DataSource(name="IncomingTiny", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_tiny_scored"})

    assert registered["join_existing_total"] == 2
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] == 1
    assert join_calls == ["match_src"]


@pytest.mark.anyio
async def test_register_source_skips_exhaustive_join_scan_for_expensive_single_unrelated_source(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    unrelated_meta = _schema_meta_for_columns(
        5_500,
        [
            {
                "name": "vendor_code",
                "role": "identifier",
                "unique_count": 5_100,
                "samples": ["V100", "V200"],
            }
        ],
    )
    reg.register_source(
        "org_single_scored",
        "other_src",
        "Other",
        _parquet_bytes([{"vendor_code": "V100"}]),
        unrelated_meta,
        graph_nodes={},
        profile={},
    )

    join_calls: list[str] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **_kwargs,
    ):
        join_calls.append(other_id)
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_single_scored"

    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:04d},{i}" for i in range(6_000))
    payload = RegisterRequest(source=DataSource(name="IncomingSingle", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_single_scored"})

    assert registered["join_existing_total"] == 1
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] == 0
    assert join_calls == []


@pytest.mark.anyio
async def test_register_source_uses_scored_join_scan_for_low_row_mid_org_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    matching_meta = _schema_meta_for_columns(
        20_000,
        [
            {
                "name": "customer_id",
                "role": "identifier",
                "unique_count": 18_000,
                "samples": ["C100", "C200"],
            }
        ],
    )
    reg.register_source(
        "org_mid_scored_low_rows",
        "match_src",
        "Match",
        _parquet_bytes([{"customer_id": "C100"}]),
        matching_meta,
        graph_nodes={},
        profile={},
    )
    for i in range(7):
        meta = _schema_meta_for_columns(
            20_000,
            [
                {
                    "name": f"vendor_code_{i}",
                    "role": "identifier",
                    "unique_count": 18_500,
                    "samples": [f"V{i}1", f"V{i}2"],
                }
            ],
        )
        reg.register_source(
            "org_mid_scored_low_rows",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes([{f"vendor_code_{i}": f"V{i}1"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    join_calls: list[str] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **_kwargs,
    ):
        join_calls.append(other_id)
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_mid_scored_low_rows"

    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:04d},{i}" for i in range(500))
    payload = RegisterRequest(
        source=DataSource(name="IncomingMidLowRows", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_mid_scored_low_rows"})

    assert registered["join_existing_total"] == 8
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidate_limit"] == 8
    assert registered["join_candidate_min_score"] == 6.0
    assert registered["join_candidates_considered"] == 1
    assert join_calls == ["match_src"]


def test_low_row_join_candidate_policy_tightens_candidate_budget_and_score():
    schema_meta = _schema_meta_for_columns(
        500,
        [
            {
                "name": "customer_id",
                "role": "identifier",
                "unique_count": 500,
                "samples": ["C001", "C002"],
            },
            {
                "name": "measure_total",
                "role": "derived_measure",
                "is_numeric": True,
                "samples": [10, 20],
            },
        ],
    )

    assert _join_candidate_limit(row_count=1_500, schema_meta=schema_meta, existing_total=16) == 8
    assert _join_candidate_limit(row_count=128, schema_meta=schema_meta, existing_total=16) == 6
    assert _join_candidate_limit(row_count=128, schema_meta=schema_meta, existing_total=24) == 4
    assert (
        _join_candidate_min_score(
            row_count=1_500,
            schema_meta=schema_meta,
            existing_total=16,
        )
        == 6.0
    )
    assert (
        _join_candidate_min_score(
            row_count=128,
            schema_meta=schema_meta,
            existing_total=16,
        )
        == 8.0
    )

    wide_large_schema = _schema_meta_for_columns(
        10_500,
        [
            {
                "name": "part_number",
                "role": "identifier",
                "unique_count": 10_100,
                "samples": ["P001", "P002"],
            },
            {
                "name": "order_number",
                "role": "identifier",
                "unique_count": 9_900,
                "samples": ["O001", "O002"],
            },
            *[
                {
                    "name": f"attribute_{i:02d}",
                    "role": "text",
                    "samples": [f"Value{i:02d}", f"Value{i + 1:02d}"],
                }
                for i in range(58)
            ],
        ],
    )
    assert (
        _join_candidate_limit(
            row_count=10_500,
            schema_meta=wide_large_schema,
            existing_total=52,
        )
        == 4
    )
    assert (
        _join_candidate_min_score(
            row_count=10_500,
            schema_meta=wide_large_schema,
            existing_total=52,
        )
        == 30.0
    )

    extra_wide_large_schema = _schema_meta_for_columns(
        45_000,
        [
            {
                "name": "part_number",
                "role": "identifier",
                "unique_count": 40_000,
                "samples": ["P001", "P002"],
            },
            {
                "name": "order_number",
                "role": "identifier",
                "unique_count": 38_000,
                "samples": ["O001", "O002"],
            },
            *[
                {
                    "name": f"attribute_{i:02d}",
                    "role": "text",
                    "samples": [f"Value{i:02d}", f"Value{i + 1:02d}"],
                }
                for i in range(78)
            ],
        ],
    )
    assert (
        _join_candidate_limit(
            row_count=45_000,
            schema_meta=extra_wide_large_schema,
            existing_total=64,
        )
        == 2
    )
    assert (
        _join_candidate_min_score(
            row_count=45_000,
            schema_meta=extra_wide_large_schema,
            existing_total=64,
            build_join_blocks_fn=reg._build_join_blocks,
        )
        == 30.0
    )

    ultra_wide_crowded_schema = _schema_meta_for_columns(
        12_500,
        [
            {
                "name": "part_number",
                "role": "identifier",
                "unique_count": 11_500,
                "samples": ["P001", "P002"],
            },
            {
                "name": "order_number",
                "role": "identifier",
                "unique_count": 11_000,
                "samples": ["O001", "O002"],
            },
            *[
                {
                    "name": f"attribute_{i:04d}",
                    "role": "text",
                    "samples": [f"Value{i:04d}", f"Value{i + 1:04d}"],
                }
                for i in range(1_198)
            ],
        ],
    )
    assert (
        _join_candidate_limit(
            row_count=12_500,
            schema_meta=ultra_wide_crowded_schema,
            existing_total=36,
        )
        == 4
    )
    assert (
        _join_candidate_min_score(
            row_count=12_500,
            schema_meta=ultra_wide_crowded_schema,
            existing_total=36,
            build_join_blocks_fn=reg._build_join_blocks,
        )
        == 30.0
    )

    large_crowded_schema = _schema_meta_for_columns(
        12_500,
        [
            {
                "name": "part_number",
                "role": "identifier",
                "unique_count": 11_500,
                "samples": ["P001", "P002"],
            },
            {
                "name": "order_number",
                "role": "identifier",
                "unique_count": 11_000,
                "samples": ["O001", "O002"],
            },
            *[
                {
                    "name": f"attribute_{i:02d}",
                    "role": "text",
                    "samples": [f"Value{i:02d}", f"Value{i + 1:02d}"],
                }
                for i in range(24)
            ],
        ],
    )
    assert (
        _join_candidate_limit(
            row_count=12_500,
            schema_meta=large_crowded_schema,
            existing_total=32,
        )
        == 8
    )
    assert (
        _join_candidate_min_score(
            row_count=12_500,
            schema_meta=large_crowded_schema,
            existing_total=32,
            build_join_blocks_fn=reg._build_join_blocks,
        )
        == 30.0
    )

    wide_medium_crowded_schema = _schema_meta_for_columns(
        16_730,
        [
            {
                "name": "part_number",
                "role": "identifier",
                "unique_count": 16_000,
                "samples": ["P001", "P002"],
            },
            {
                "name": "quote_number",
                "role": "identifier",
                "unique_count": 15_500,
                "samples": ["Q001", "Q002"],
            },
            *[
                {
                    "name": f"attribute_{i:03d}",
                    "role": "text",
                    "samples": [f"Value{i:03d}", f"Value{i + 1:03d}"],
                }
                for i in range(145)
            ],
        ],
    )
    assert (
        _join_candidate_limit(
            row_count=16_730,
            schema_meta=wide_medium_crowded_schema,
            existing_total=64,
        )
        == 4
    )
    assert (
        _join_candidate_min_score(
            row_count=16_730,
            schema_meta=wide_medium_crowded_schema,
            existing_total=64,
            build_join_blocks_fn=reg._build_join_blocks,
        )
        == 30.0
    )

    wide_mid_org_schema = _schema_meta_for_columns(
        5_820,
        [
            {
                "name": "part_number",
                "role": "identifier",
                "unique_count": 5_200,
                "samples": ["P001", "P002"],
            },
            {
                "name": "inventory_ref",
                "role": "identifier",
                "unique_count": 5_000,
                "samples": ["I001", "I002"],
            },
            *[
                {
                    "name": f"attribute_{i:03d}",
                    "role": "text",
                    "samples": [f"Value{i:03d}", f"Value{i + 1:03d}"],
                }
                for i in range(242)
            ],
        ],
    )
    assert (
        _join_candidate_limit(
            row_count=5_820,
            schema_meta=wide_mid_org_schema,
            existing_total=8,
        )
        == 4
    )
    assert (
        _join_candidate_min_score(
            row_count=5_820,
            schema_meta=wide_mid_org_schema,
            existing_total=8,
            build_join_blocks_fn=reg._build_join_blocks,
        )
        == 30.0
    )

    very_large_crowded_schema = _schema_meta_for_columns(
        33_125,
        [
            {
                "name": "quote_number",
                "role": "identifier",
                "unique_count": 32_500,
                "samples": ["Q001", "Q002"],
            },
            {
                "name": "part_number",
                "role": "identifier",
                "unique_count": 31_900,
                "samples": ["P001", "P002"],
            },
            *[
                {
                    "name": f"attribute_{i:02d}",
                    "role": "text",
                    "samples": [f"Value{i:02d}", f"Value{i + 1:02d}"],
                }
                for i in range(34)
            ],
        ],
    )
    assert (
        _join_candidate_limit(
            row_count=33_125,
            schema_meta=very_large_crowded_schema,
            existing_total=36,
        )
        == 4
    )
    assert (
        _join_candidate_min_score(
            row_count=33_125,
            schema_meta=very_large_crowded_schema,
            existing_total=36,
            build_join_blocks_fn=reg._build_join_blocks,
        )
        == 20.0
    )

    crowded_low_row_schema = _schema_meta_for_columns(
        511,
        [
            {
                "name": "part_number",
                "role": "identifier",
                "unique_count": 420,
                "samples": ["P001", "P002"],
            },
            {"name": "description", "role": "text", "samples": ["Widget", "Valve"]},
            {"name": "manufacturer", "role": "text", "samples": ["AAR", "TE-DRI"]},
        ],
    )
    assert (
        _join_candidate_limit(
            row_count=511,
            schema_meta=crowded_low_row_schema,
            existing_total=48,
        )
        == 4
    )
    assert (
        _join_candidate_min_score(
            row_count=511,
            schema_meta=crowded_low_row_schema,
            existing_total=48,
            build_join_blocks_fn=reg._build_join_blocks,
        )
        == 6.0
    )


@pytest.mark.anyio
async def test_register_source_reduces_exhaustive_join_scan_for_low_row_mid_org_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(12):
        meta = _schema_meta_for_columns(
            25_000,
            [
                {
                    "name": f"vendor_code_{i}",
                    "role": "identifier",
                    "unique_count": 22_500,
                    "samples": [f"V{i}1", f"V{i}2"],
                },
                {
                    "name": f"vendor_ref_{i}",
                    "role": "identifier",
                    "unique_count": 22_000,
                    "samples": [f"R{i}1", f"R{i}2"],
                },
                {
                    "name": f"vendor_key_{i}",
                    "role": "identifier",
                    "unique_count": 21_500,
                    "samples": [f"K{i}1", f"K{i}2"],
                },
                {
                    "name": f"vendor_guid_{i}",
                    "role": "identifier",
                    "unique_count": 21_000,
                    "samples": [f"G{i}1", f"G{i}2"],
                },
            ],
        )
        reg.register_source(
            "org_mid_scored_none",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes(
                [
                    {
                        f"vendor_code_{i}": f"V{i}1",
                        f"vendor_ref_{i}": f"R{i}1",
                        f"vendor_key_{i}": f"K{i}1",
                        f"vendor_guid_{i}": f"G{i}1",
                    }
                ]
            ),
            meta,
            graph_nodes={},
            profile={},
        )

    join_calls: list[str] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **_kwargs,
    ):
        join_calls.append(other_id)
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_mid_scored_none"

    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = ["audit_id,quality_ref,review_code"]
    lines.extend(f"A{i:02d},Q{i:02d},R{i:02d}" for i in range(12))
    payload = RegisterRequest(
        source=DataSource(name="IncomingMidNoCandidates", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_mid_scored_none"})

    assert registered["join_existing_total"] == 12
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] < 12
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.anyio
async def test_register_source_limits_deep_join_checks_to_blocked_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(30):
        col_name = "customer_id" if i == 0 else f"unrelated_key_{i}"
        samples = ["C100", "C200"] if i == 0 else [f"U{i}_1", f"U{i}_2"]
        meta = _schema_meta_for_columns(
            200,
            [{"name": col_name, "role": "identifier", "unique_count": 180, "samples": samples}],
        )
        reg.register_source(
            "org_join_block",
            f"s_{i}",
            f"S{i}",
            _parquet_bytes([{col_name: samples[0]}]),
            meta,
            graph_nodes={},
            profile={},
        )

    join_calls: list[str] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **_kwargs,
    ):
        join_calls.append(other_id)
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_block"

    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    payload = RegisterRequest(
        source=DataSource(
            name="Incoming",
            csv="customer_id,measure_total\nC100,10\nC200,20\n",
        )
    )

    registered = await register_source(payload, auth={"org_id": "org_join_block"})

    assert registered["join_existing_total"] == 30
    assert registered["join_candidates_considered"] < 30
    assert "s_0" in join_calls
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.anyio
async def test_register_source_caps_join_candidates_for_large_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(30):
        meta = _schema_meta_for_columns(
            20_000,
            [
                {
                    "name": "customer_id",
                    "role": "identifier",
                    "unique_count": 18_000,
                    "samples": [f"C{i:04d}", f"C{i + 1:04d}"],
                },
            ],
        )
        reg.register_source(
            "org_join_limit",
            f"s_{i}",
            f"S{i}",
            _parquet_bytes([{"customer_id": f"C{i:04d}"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    join_calls: list[str] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **_kwargs,
    ):
        join_calls.append(other_id)
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_join_limit"

    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:05d},{i}" for i in range(35_000))
    payload = RegisterRequest(source=DataSource(name="IncomingHuge", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_join_limit"})

    assert registered["join_existing_total"] == 30
    assert registered["join_candidate_limit"] == 8
    assert registered["join_candidate_min_score"] == 4.5
    assert registered["join_candidates_considered"] <= 8
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.anyio
async def test_register_source_caps_join_candidates_more_aggressively_for_very_large_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(30):
        meta = _schema_meta_for_columns(
            25_000,
            [
                {
                    "name": "customer_id",
                    "role": "identifier",
                    "unique_count": 22_000,
                    "samples": [f"C{i:04d}", f"C{i + 1:04d}"],
                },
            ],
        )
        reg.register_source(
            "org_join_limit_very_large",
            f"s_{i}",
            f"S{i}",
            _parquet_bytes([{"customer_id": f"C{i:04d}"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    join_calls: list[str] = []

    async def _fake_detect(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        **_kwargs,
    ):
        join_calls.append(other_id)
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_join_limit_very_large"

    monkeypatch.setattr("apps.api_server.routers.sources._detect_joins_between", _fake_detect)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:05d},{i}" for i in range(60_000))
    payload = RegisterRequest(
        source=DataSource(name="IncomingVeryLarge", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_join_limit_very_large"})

    assert registered["join_existing_total"] == 30
    assert registered["join_candidate_limit"] == 6
    assert registered["join_candidate_min_score"] == 4.5
    assert registered["join_candidates_considered"] <= 6
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.anyio
async def test_register_source_raises_join_candidate_min_score_for_medium_sparse_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(12):
        meta = _schema_meta_for_columns(
            18_000,
            [
                {
                    "name": f"vendor_code_{i}",
                    "role": "identifier",
                    "unique_count": 16_500,
                    "samples": [f"V{i}1", f"V{i}2"],
                },
                {
                    "name": f"vendor_ref_{i}",
                    "role": "identifier",
                    "unique_count": 16_000,
                    "samples": [f"R{i}1", f"R{i}2"],
                },
                {
                    "name": f"vendor_key_{i}",
                    "role": "identifier",
                    "unique_count": 15_500,
                    "samples": [f"K{i}1", f"K{i}2"],
                },
            ],
        )
        reg.register_source(
            "org_medium_sparse_floor",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes(
                [
                    {
                        f"vendor_code_{i}": f"V{i}1",
                        f"vendor_ref_{i}": f"R{i}1",
                        f"vendor_key_{i}": f"K{i}1",
                    }
                ]
            ),
            meta,
            graph_nodes={},
            profile={},
        )

    captured: dict[str, float | int] = {}

    def _fake_candidate_join_sources(
        org_id: str,
        source_id: str,
        schema_meta: dict,
        *,
        source_name: str | None = None,
        limit: int = 24,
        exhaustive_threshold: int = 24,
        min_score: float = 4.5,
    ) -> list[dict]:
        captured["limit"] = limit
        captured["exhaustive_threshold"] = exhaustive_threshold
        captured["min_score"] = min_score
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_medium_sparse_floor"

    monkeypatch.setattr(reg, "candidate_join_sources", _fake_candidate_join_sources)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = ["customer_id,order_number,vendor_code,serial_key,measure_total"]
    lines.extend(f"C{i:04d},O{i:04d},V{i:04d},S{i:04d},{i}" for i in range(4_000))
    payload = RegisterRequest(
        source=DataSource(name="IncomingMediumSparse", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_medium_sparse_floor"})

    assert registered["join_existing_total"] == 12
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidate_min_score"] == 20.0
    assert captured == {
        "limit": 24,
        "exhaustive_threshold": 0,
        "min_score": 20.0,
    }


@pytest.mark.anyio
async def test_register_source_raises_join_candidate_min_score_for_wide_medium_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(12):
        meta = _schema_meta_for_columns(
            18_000,
            [
                {
                    "name": f"vendor_code_{i}",
                    "role": "identifier",
                    "unique_count": 16_500,
                    "samples": [f"V{i}1", f"V{i}2"],
                },
                {
                    "name": f"vendor_ref_{i}",
                    "role": "identifier",
                    "unique_count": 16_000,
                    "samples": [f"R{i}1", f"R{i}2"],
                },
                {
                    "name": f"vendor_key_{i}",
                    "role": "identifier",
                    "unique_count": 15_500,
                    "samples": [f"K{i}1", f"K{i}2"],
                },
            ],
        )
        reg.register_source(
            "org_wide_medium_floor",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes(
                [
                    {
                        f"vendor_code_{i}": f"V{i}1",
                        f"vendor_ref_{i}": f"R{i}1",
                        f"vendor_key_{i}": f"K{i}1",
                    }
                ]
            ),
            meta,
            graph_nodes={},
            profile={},
        )

    captured: dict[str, float | int] = {}

    def _fake_candidate_join_sources(
        org_id: str,
        source_id: str,
        schema_meta: dict,
        *,
        source_name: str | None = None,
        limit: int = 24,
        exhaustive_threshold: int = 24,
        min_score: float = 4.5,
    ) -> list[dict]:
        captured["limit"] = limit
        captured["exhaustive_threshold"] = exhaustive_threshold
        captured["min_score"] = min_score
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_wide_medium_floor"

    monkeypatch.setattr(reg, "candidate_join_sources", _fake_candidate_join_sources)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    lines = [
        "customer_id,order_number,vendor_code,serial_key,account_ref,shipment_code,quote_number,measure_total"
    ]
    lines.extend(
        f"C{i:05d},O{i:05d},V{i:05d},S{i:05d},A{i:05d},SH{i:05d},Q{i:05d},{i}"
        for i in range(10_500)
    )
    payload = RegisterRequest(
        source=DataSource(name="IncomingWideMedium", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_wide_medium_floor"})

    assert registered["join_existing_total"] == 12
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidate_min_score"] == 30.0
    assert captured == {
        "limit": 12,
        "exhaustive_threshold": 0,
        "min_score": 30.0,
    }


@pytest.mark.anyio
async def test_register_source_tightens_join_candidate_budget_for_wide_large_sparse_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(30):
        meta = _schema_meta_for_columns(
            12_000,
            [
                {
                    "name": "part_number",
                    "role": "identifier",
                    "unique_count": 11_500,
                    "samples": [f"P{i}1", f"P{i}2"],
                },
                {
                    "name": "order_number",
                    "role": "identifier",
                    "unique_count": 11_000,
                    "samples": [f"O{i}1", f"O{i}2"],
                },
                *[
                    {
                        "name": f"attribute_{j:02d}_{i}",
                        "role": "text",
                        "samples": [f"Value{j:02d}", f"Value{j + 1:02d}"],
                    }
                    for j in range(58)
                ],
            ],
        )
        reg.register_source(
            "org_wide_large_sparse_floor",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes([{"part_number": f"P{i}1", "order_number": f"O{i}1"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    captured: dict[str, float | int] = {}

    def _fake_candidate_join_sources(
        org_id: str,
        source_id: str,
        schema_meta: dict,
        *,
        source_name: str | None = None,
        limit: int = 24,
        exhaustive_threshold: int = 24,
        min_score: float = 4.5,
    ) -> list[dict]:
        captured["limit"] = limit
        captured["exhaustive_threshold"] = exhaustive_threshold
        captured["min_score"] = min_score
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_wide_large_sparse_floor"

    monkeypatch.setattr(reg, "candidate_join_sources", _fake_candidate_join_sources)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    header = ["part_number", "order_number", *[f"attribute_{i:02d}" for i in range(58)]]
    lines = [",".join(header)]
    for i in range(10_500):
        values = [
            f"P{i:05d}",
            f"O{i:05d}",
            *[f"Value{j:02d}" for j in range(58)],
        ]
        lines.append(",".join(values))
    payload = RegisterRequest(
        source=DataSource(name="IncomingWideLargeSparse", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_wide_large_sparse_floor"})

    assert registered["join_existing_total"] == 30
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidate_limit"] == 6
    assert registered["join_candidate_min_score"] == 25.0
    assert captured == {
        "limit": 6,
        "exhaustive_threshold": 0,
        "min_score": 25.0,
    }


@pytest.mark.anyio
async def test_register_source_tightens_join_candidate_budget_for_extra_wide_large_crowded_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(64):
        meta = _schema_meta_for_columns(
            32_000,
            [
                {
                    "name": f"part_number_{i}",
                    "role": "identifier",
                    "unique_count": 28_000,
                    "samples": [f"P{i}1", f"P{i}2"],
                },
                {
                    "name": f"order_number_{i}",
                    "role": "identifier",
                    "unique_count": 27_500,
                    "samples": [f"O{i}1", f"O{i}2"],
                },
                *[
                    {
                        "name": f"attribute_{j:02d}_{i}",
                        "role": "text",
                        "samples": [f"Value{j:02d}", f"Value{j + 1:02d}"],
                    }
                    for j in range(62)
                ],
            ],
        )
        reg.register_source(
            "org_extra_wide_large_floor",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes(
                [
                    {
                        f"part_number_{i}": f"P{i}1",
                        f"order_number_{i}": f"O{i}1",
                        **{f"attribute_{j:02d}_{i}": f"Value{j:02d}" for j in range(62)},
                    }
                ]
            ),
            meta,
            graph_nodes={},
            profile={},
        )

    captured: dict[str, float | int] = {}

    def _fake_candidate_join_sources(
        org_id: str,
        source_id: str,
        schema_meta: dict,
        *,
        source_name: str | None = None,
        limit: int = 24,
        exhaustive_threshold: int = 24,
        min_score: float = 4.5,
    ) -> list[dict]:
        captured["limit"] = limit
        captured["exhaustive_threshold"] = exhaustive_threshold
        captured["min_score"] = min_score
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_extra_wide_large_floor"

    monkeypatch.setattr(reg, "candidate_join_sources", _fake_candidate_join_sources)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    header = ["part_number", "order_number", *[f"attribute_{i:02d}" for i in range(78)]]
    lines = [",".join(header)]
    for i in range(32_000):
        values = [
            f"P{i:05d}",
            f"O{i:05d}",
            *[f"Value{j:02d}" for j in range(78)],
        ]
        lines.append(",".join(values))
    payload = RegisterRequest(
        source=DataSource(name="IncomingExtraWideLarge", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_extra_wide_large_floor"})

    assert registered["join_existing_total"] == 64
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidate_limit"] == 2
    assert registered["join_candidate_min_score"] == 30.0
    assert captured == {
        "limit": 2,
        "exhaustive_threshold": 0,
        "min_score": 30.0,
    }


@pytest.mark.anyio
async def test_register_source_tightens_join_candidate_budget_for_ultra_wide_crowded_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(36):
        meta = _schema_meta_for_columns(
            12_500,
            [
                {
                    "name": f"part_number_{i}",
                    "role": "identifier",
                    "unique_count": 11_500,
                    "samples": [f"P{i}1", f"P{i}2"],
                },
                {
                    "name": f"order_number_{i}",
                    "role": "identifier",
                    "unique_count": 11_000,
                    "samples": [f"O{i}1", f"O{i}2"],
                },
                *[
                    {
                        "name": f"attribute_{j:04d}_{i}",
                        "role": "text",
                        "samples": [f"Value{j:04d}", f"Value{j + 1:04d}"],
                    }
                    for j in range(1_198)
                ],
            ],
        )
        reg.register_source(
            "org_ultra_wide_crowded_floor",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes(
                [
                    {
                        f"part_number_{i}": f"P{i}1",
                        f"order_number_{i}": f"O{i}1",
                        **{f"attribute_{j:04d}_{i}": f"Value{j:04d}" for j in range(1_198)},
                    }
                ]
            ),
            meta,
            graph_nodes={},
            profile={},
        )

    captured: dict[str, float | int] = {}

    def _fake_candidate_join_sources(
        org_id: str,
        source_id: str,
        schema_meta: dict,
        *,
        source_name: str | None = None,
        limit: int = 24,
        exhaustive_threshold: int = 24,
        min_score: float = 4.5,
    ) -> list[dict]:
        captured["limit"] = limit
        captured["exhaustive_threshold"] = exhaustive_threshold
        captured["min_score"] = min_score
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_ultra_wide_crowded_floor"

    monkeypatch.setattr(reg, "candidate_join_sources", _fake_candidate_join_sources)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    header = ["part_number", "order_number", *[f"attribute_{i:04d}" for i in range(1_198)]]
    lines = [",".join(header)]
    for i in range(12_500):
        values = [
            f"P{i:05d}",
            f"O{i:05d}",
            *[f"Value{j:04d}" for j in range(1_198)],
        ]
        lines.append(",".join(values))
    payload = RegisterRequest(
        source=DataSource(name="IncomingUltraWideCrowded", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_ultra_wide_crowded_floor"})

    assert registered["join_existing_total"] == 36
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidate_limit"] == 4
    assert registered["join_candidate_min_score"] == 30.0
    assert captured == {
        "limit": 4,
        "exhaustive_threshold": 0,
        "min_score": 30.0,
    }


@pytest.mark.anyio
async def test_register_source_tightens_join_candidate_budget_for_large_crowded_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(32):
        meta = _schema_meta_for_columns(
            12_500,
            [
                {
                    "name": f"part_number_{i}",
                    "role": "identifier",
                    "unique_count": 11_500,
                    "samples": [f"P{i}1", f"P{i}2"],
                },
                {
                    "name": f"order_number_{i}",
                    "role": "identifier",
                    "unique_count": 11_000,
                    "samples": [f"O{i}1", f"O{i}2"],
                },
                *[
                    {
                        "name": f"attribute_{j:02d}_{i}",
                        "role": "text",
                        "samples": [f"Value{j:02d}", f"Value{j + 1:02d}"],
                    }
                    for j in range(24)
                ],
            ],
        )
        reg.register_source(
            "org_large_crowded_floor",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes(
                [
                    {
                        f"part_number_{i}": f"P{i}1",
                        f"order_number_{i}": f"O{i}1",
                        **{f"attribute_{j:02d}_{i}": f"Value{j:02d}" for j in range(24)},
                    }
                ]
            ),
            meta,
            graph_nodes={},
            profile={},
        )

    captured: dict[str, float | int] = {}

    def _fake_candidate_join_sources(
        org_id: str,
        source_id: str,
        schema_meta: dict,
        *,
        source_name: str | None = None,
        limit: int = 24,
        exhaustive_threshold: int = 24,
        min_score: float = 4.5,
    ) -> list[dict]:
        captured["limit"] = limit
        captured["exhaustive_threshold"] = exhaustive_threshold
        captured["min_score"] = min_score
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_large_crowded_floor"

    monkeypatch.setattr(reg, "candidate_join_sources", _fake_candidate_join_sources)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    header = ["part_number", "order_number", *[f"attribute_{i:02d}" for i in range(24)]]
    lines = [",".join(header)]
    for i in range(12_500):
        values = [
            f"P{i:05d}",
            f"O{i:05d}",
            *[f"Value{j:02d}" for j in range(24)],
        ]
        lines.append(",".join(values))
    payload = RegisterRequest(
        source=DataSource(name="IncomingLargeCrowded", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_large_crowded_floor"})

    assert registered["join_existing_total"] == 32
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidate_limit"] == 8
    assert registered["join_candidate_min_score"] == 20.0
    assert captured == {
        "limit": 8,
        "exhaustive_threshold": 0,
        "min_score": 20.0,
    }


@pytest.mark.anyio
async def test_register_source_tightens_join_candidate_budget_for_very_large_crowded_sources(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    for i in range(36):
        meta = _schema_meta_for_columns(
            33_125,
            [
                {
                    "name": f"quote_number_{i}",
                    "role": "identifier",
                    "unique_count": 32_500,
                    "samples": [f"Q{i}1", f"Q{i}2"],
                },
                {
                    "name": f"part_number_{i}",
                    "role": "identifier",
                    "unique_count": 31_900,
                    "samples": [f"P{i}1", f"P{i}2"],
                },
                *[
                    {
                        "name": f"attribute_{j:02d}_{i}",
                        "role": "text",
                        "samples": [f"Value{j:02d}", f"Value{j + 1:02d}"],
                    }
                    for j in range(34)
                ],
            ],
        )
        reg.register_source(
            "org_very_large_crowded_floor",
            f"v_{i}",
            f"V{i}",
            _parquet_bytes(
                [
                    {
                        f"quote_number_{i}": f"Q{i}1",
                        f"part_number_{i}": f"P{i}1",
                        **{f"attribute_{j:02d}_{i}": f"Value{j:02d}" for j in range(34)},
                    }
                ]
            ),
            meta,
            graph_nodes={},
            profile={},
        )

    captured: dict[str, float | int] = {}

    def _fake_candidate_join_sources(
        org_id: str,
        source_id: str,
        schema_meta: dict,
        *,
        source_name: str | None = None,
        limit: int = 24,
        exhaustive_threshold: int = 24,
        min_score: float = 4.5,
    ) -> list[dict]:
        captured["limit"] = limit
        captured["exhaustive_threshold"] = exhaustive_threshold
        captured["min_score"] = min_score
        return []

    async def _fake_profile(*_args, **_kwargs):
        return {"profiles": {}}

    async def _fake_relations(*_args, **_kwargs):
        return []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        return object(), False, "rev_very_large_crowded_floor"

    monkeypatch.setattr(reg, "candidate_join_sources", _fake_candidate_join_sources)
    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _fake_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)
    monkeypatch.setattr(
        "apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner
    )

    header = ["quote_number", "part_number", *[f"attribute_{i:02d}" for i in range(34)]]
    lines = [",".join(header)]
    for i in range(33_125):
        values = [
            f"Q{i:05d}",
            f"P{i:05d}",
            *[f"Value{j:02d}" for j in range(34)],
        ]
        lines.append(",".join(values))
    payload = RegisterRequest(
        source=DataSource(name="IncomingVeryLargeCrowded", csv="\n".join(lines) + "\n")
    )

    registered = await register_source(payload, auth={"org_id": "org_very_large_crowded_floor"})

    assert registered["join_existing_total"] == 36
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidate_limit"] == 4
    assert registered["join_candidate_min_score"] == 20.0
    assert captured == {
        "limit": 4,
        "exhaustive_threshold": 0,
        "min_score": 20.0,
    }


@pytest.mark.anyio
async def test_register_source_returns_structured_503_when_mojo_profiling_fails_in_strict_mode(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    async def _raise_profile(*_args, **_kwargs):
        raise MojoInstrumentationError(
            "column_profile",
            "Mojo column profiling failed while strict runtime fallbacks are disabled.",
        )

    async def _fake_relations(*_args, **_kwargs):
        return []

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_column_profile", _raise_profile)
    monkeypatch.setattr("apps.api_server.routers.sources._detect_relations", _fake_relations)

    payload = RegisterRequest(
        source=DataSource(
            name="StrictMojoFailure",
            csv="customer_id,measure_total\nC100,10\nC200,20\n",
        )
    )

    with pytest.raises(HTTPException) as excinfo:
        await register_source(payload, auth={"org_id": "org_strict"})

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail["error"]["code"] == "mojo_instrumentation_unavailable"
