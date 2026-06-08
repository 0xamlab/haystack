"""Tests for build join.

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


