"""Tests for register source d.

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


