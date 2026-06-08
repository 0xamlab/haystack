"""Tests for detect joins b.

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


