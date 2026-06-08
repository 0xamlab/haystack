"""Tests for register source b.

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


