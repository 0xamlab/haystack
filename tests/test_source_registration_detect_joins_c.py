"""Tests for detect joins c.

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


