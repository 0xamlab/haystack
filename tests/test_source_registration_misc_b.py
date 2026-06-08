"""Tests for misc b.

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


