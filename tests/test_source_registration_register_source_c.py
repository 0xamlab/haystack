"""Tests for register source c.

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


