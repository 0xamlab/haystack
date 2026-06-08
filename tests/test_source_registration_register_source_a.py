"""Tests for register source a.

Extracted from tests/test_source_registration.py during modularization.
"""
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


