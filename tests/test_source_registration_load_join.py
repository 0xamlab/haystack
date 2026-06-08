"""Tests for load join.

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


