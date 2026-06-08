"""Tests for detect joins a.

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


