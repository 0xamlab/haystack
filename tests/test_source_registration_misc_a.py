"""Tests for misc a.

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


def test_source_meta_cache_reuses_registered_schema_without_disk_reload(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    schema_meta = {
        "row_count": 2,
        "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
        "roles_summary": {"identifier": 1},
    }
    reg.register_source(
        org_id="org_meta_cache",
        source_id="src_meta_cache",
        name="MetaCacheSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta=schema_meta,
        graph_nodes={},
        profile={},
    )

    read_calls = {"count": 0}
    original_read_json = reg._read_json

    def _counting_read_json(path: Path):  # type: ignore[no-untyped-def]
        read_calls["count"] += 1
        return original_read_json(path)

    monkeypatch.setattr(reg, "_read_json", _counting_read_json)

    first = reg.get_source_meta("org_meta_cache", "src_meta_cache")
    second = reg.get_source_meta("org_meta_cache", "src_meta_cache")

    assert first == schema_meta
    assert second == schema_meta
    assert read_calls["count"] == 0


def test_source_entry_cache_reuses_registered_index_entry_without_disk_reload(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    reg.register_source(
        org_id="org_entry_cache",
        source_id="src_entry_cache",
        name="EntryCacheSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    read_calls = {"count": 0}
    original_read_json = reg._read_json

    def _counting_read_json(path: Path):  # type: ignore[no-untyped-def]
        read_calls["count"] += 1
        return original_read_json(path)

    monkeypatch.setattr(reg, "_read_json", _counting_read_json)

    first = reg.get_source_entry("org_entry_cache", "src_entry_cache")
    second = reg.get_source_entry("org_entry_cache", "src_entry_cache")

    assert first is not None
    assert first["name"] == "EntryCacheSource"
    assert isinstance(first["source_schema_revision"], str)
    assert len(first["source_schema_revision"]) == 24
    assert second == first
    assert read_calls["count"] == 0


def test_update_source_meta_refreshes_entry_source_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    reg.register_source(
        org_id="org_source_revision_sync",
        source_id="src_revision_sync",
        name="RevisionSyncSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    before = reg.get_source_entry("org_source_revision_sync", "src_revision_sync")
    assert before is not None
    before_revision = str(before.get("source_schema_revision") or "")
    assert before_revision

    updated_meta = reg.update_source_meta(
        "org_source_revision_sync",
        "src_revision_sync",
        {"schema_revision": "planner_revision_after_prewarm"},
    )

    assert updated_meta is not None

    after = reg.get_source_entry("org_source_revision_sync", "src_revision_sync")
    assert after is not None
    after_revision = str(after.get("source_schema_revision") or "")
    assert after_revision
    assert after_revision == reg.source_schema_revision(
        "org_source_revision_sync",
        "src_revision_sync",
    )
    assert after_revision != before_revision


def test_update_source_entry_without_touching_schema_preserves_org_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    reg._SCHEMA_REVISION_CACHE.clear()

    reg.register_source(
        org_id="org_entry_revision_stable",
        source_id="src_entry_revision_stable",
        name="EntryRevisionStable",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    before = reg.schema_revision("org_entry_revision_stable")
    updated = reg.update_source_entry(
        "org_entry_revision_stable",
        "src_entry_revision_stable",
        {"schema_revision": "planner_revision_after_prewarm"},
        touch_schema=False,
    )
    after = reg.schema_revision("org_entry_revision_stable")

    assert updated is not None
    assert updated["schema_revision"] == "planner_revision_after_prewarm"
    assert after == before


def test_update_source_entry_noop_preserves_org_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    reg.register_source(
        org_id="org_entry_noop",
        source_id="src_entry_noop",
        name="EntryNoopSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
        dataset_name="EntryNoopSource",
    )

    before = reg.schema_revision("org_entry_noop")
    updated = reg.update_source_entry(
        "org_entry_noop",
        "src_entry_noop",
        {"dataset_name": "EntryNoopSource"},
    )
    after = reg.schema_revision("org_entry_noop")

    assert updated is not None
    assert updated["dataset_name"] == "EntryNoopSource"
    assert after == before


def test_update_source_meta_without_touching_schema_preserves_org_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    reg._SCHEMA_REVISION_CACHE.clear()

    reg.register_source(
        org_id="org_meta_revision_stable",
        source_id="src_meta_revision_stable",
        name="MetaRevisionStable",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    before = reg.schema_revision("org_meta_revision_stable")
    updated = reg.update_source_meta(
        "org_meta_revision_stable",
        "src_meta_revision_stable",
        {"schema_revision": "planner_revision_after_prewarm"},
        touch_schema=False,
    )
    after = reg.schema_revision("org_meta_revision_stable")

    assert updated is not None
    assert updated["schema_revision"] == "planner_revision_after_prewarm"
    assert after == before


def test_update_source_meta_noop_preserves_org_schema_revision(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    reg.register_source(
        org_id="org_meta_noop",
        source_id="src_meta_noop",
        name="MetaNoopSource",
        parquet_bytes=_parquet_bytes([{"customer_id": "A"}, {"customer_id": "B"}]),
        schema_meta={
            "row_count": 2,
            "columns": [{"name": "customer_id", "role": "identifier", "is_numeric": False}],
            "roles_summary": {"identifier": 1},
        },
        graph_nodes={},
        profile={},
    )

    before = reg.schema_revision("org_meta_noop")
    updated = reg.update_source_meta(
        "org_meta_noop",
        "src_meta_noop",
        {"row_count": 2},
    )
    after = reg.schema_revision("org_meta_noop")

    assert updated is not None
    assert updated["row_count"] == 2
    assert after == before


def test_deep_join_projection_columns_caps_and_deduplicates():
    join_blocks = [
        {"name": "entity_key"},
        {"name": "entity_key"},
        {"name": "measure_total"},
        {"name": "segment_label"},
    ]

    projected = _deep_join_projection_columns(join_blocks, limit=2)

    assert projected == ["entity_key", "measure_total"]


def test_deep_join_projection_columns_keeps_low_cardinality_dimension_extensions():
    join_blocks = [{"name": f"ranked_{idx}"} for idx in range(12)] + [
        {
            "name": "Store name as per Uber Eats manager",
            "unique_count": 2,
            "unique_ratio": 0.001,
        },
        {
            "name": "Merchant location",
            "unique_count": 3,
            "unique_ratio": 0.01,
        },
    ]

    projected = _deep_join_projection_columns(join_blocks, limit=12)

    assert "Store name as per Uber Eats manager" in projected
    assert "Merchant location" in projected


def test_infer_shared_column_cardinality_from_stats_uses_exact_unique_shortcut():
    left_stats = {
        "counts": {},
        "values": {"A", "B", "C"},
        "unique_ratio": 0.75,
        "all_unique": True,
    }
    right_stats = {
        "counts": {"A": 2, "B": 1},
        "values": {"A", "B"},
        "unique_ratio": 0.5,
        "all_unique": False,
    }

    cardinality = _infer_shared_column_cardinality_from_stats(
        left_stats,
        right_stats,
        {"A", "B"},
    )

    assert cardinality == "one_to_many"


def test_schema_revision_changes_with_registered_sources_and_connections(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    empty_rev = reg.schema_revision("org_rev")

    reg.register_source(
        "org_rev",
        "src_a",
        "Alpha",
        _parquet_bytes([{"entity_key": "A", "measure_total": 10.0}]),
        {
            "row_count": 1,
            "roles_summary": {"derived_measure": 1},
            "columns": [{"name": "measure_total"}],
        },
        graph_nodes={},
        profile={},
    )
    source_rev = reg.schema_revision("org_rev")

    reg.upsert_connections(
        "org_rev",
        [
            {
                "source_a": "src_a",
                "source_a_name": "Alpha",
                "col_a": "entity_key",
                "source_b": "src_b",
                "source_b_name": "Beta",
                "col_b": "entity_key",
                "confidence": 0.97,
                "cardinality": "one_to_one",
                "overlap": 1.0,
            }
        ],
    )
    graph_rev = reg.schema_revision("org_rev")

    assert empty_rev != source_rev
    assert source_rev != graph_rev


def test_schema_revision_reuses_cached_revision_when_registry_fingerprint_is_unchanged(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    reg._SCHEMA_REVISION_CACHE.clear()

    reg.register_source(
        "org_rev_cached",
        "src_a",
        "Alpha",
        _parquet_bytes([{"entity_key": "A", "measure_total": 10.0}]),
        {
            "row_count": 1,
            "roles_summary": {"derived_measure": 1},
            "columns": [{"name": "measure_total"}],
        },
        graph_nodes={},
        profile={},
    )
    first = reg.schema_revision("org_rev_cached")

    meta_path = Path(tmp_path) / "sources" / "org_rev_cached" / "src_a.meta.json"
    real_read_json = reg._read_json
    meta_reads = {"count": 0}

    def _counting_read_json(path: Path):  # type: ignore[no-untyped-def]
        if path == meta_path:
            meta_reads["count"] += 1
        return real_read_json(path)

    monkeypatch.setattr(reg, "_read_json", _counting_read_json)

    second = reg.schema_revision("org_rev_cached")
    third = reg.schema_revision("org_rev_cached")

    assert first == second == third
    assert meta_reads["count"] == 0


def test_schema_revision_cold_path_skips_source_meta_reads(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    reg._SCHEMA_REVISION_CACHE.clear()

    reg.register_source(
        "org_rev_no_meta_scan",
        "src_a",
        "Alpha",
        _parquet_bytes([{"entity_key": "A", "measure_total": 10.0}]),
        {
            "row_count": 1,
            "roles_summary": {"derived_measure": 1},
            "columns": [{"name": "measure_total"}],
            "semantic_aliases": {"sales": ["revenue"]},
            "query_hints": [{"hint": "sales", "column": "measure_total"}],
        },
        graph_nodes={},
        profile={},
    )
    reg._SCHEMA_REVISION_CACHE.clear()

    meta_path = Path(tmp_path) / "sources" / "org_rev_no_meta_scan" / "src_a.meta.json"
    real_read_json = reg._read_json
    meta_reads = {"count": 0}

    def _counting_read_json(path: Path):  # type: ignore[no-untyped-def]
        if path == meta_path:
            meta_reads["count"] += 1
        return real_read_json(path)

    monkeypatch.setattr(reg, "_read_json", _counting_read_json)

    revision = reg.schema_revision("org_rev_no_meta_scan")

    assert revision
    assert meta_reads["count"] == 0


def test_candidate_join_sources_blocks_large_org_to_likely_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

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
                "name": "segment_label",
                "role": "category",
                "unique_count": 6,
                "samples": ["ENT", "SMB"],
            },
        ],
    )
    reg.register_source(
        "org_block",
        "match_src",
        "Match",
        _parquet_bytes([{"customer_id": "C100", "segment_label": "ENT"}]),
        matching_meta,
        graph_nodes={},
        profile={},
    )

    for i in range(40):
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
                    "name": f"status_{i}",
                    "role": "category",
                    "unique_count": 3,
                    "samples": ["open", "closed"],
                },
            ],
        )
        reg.register_source(
            "org_block",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes([{f"unrelated_key_{i}": f"U{i}_1", f"status_{i}": "open"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    incoming_meta = _schema_meta_for_columns(
        300,
        [
            {
                "name": "customer_id",
                "role": "identifier",
                "unique_count": 260,
                "samples": ["C100", "C300"],
            },
            {
                "name": "order_number",
                "role": "identifier",
                "unique_count": 300,
                "samples": ["O1", "O2"],
            },
        ],
    )

    candidates = reg.candidate_join_sources("org_block", "incoming", incoming_meta)
    candidate_ids = {entry["id"] for entry in candidates}

    assert "match_src" in candidate_ids
    assert len(candidates) <= 24
    assert len(candidates) < 41


def test_candidate_join_sources_keeps_exhaustive_mode_for_small_org(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    for i in range(3):
        meta = _schema_meta_for_columns(
            100,
            [
                {
                    "name": f"entity_{i}_id",
                    "role": "identifier",
                    "unique_count": 90,
                    "samples": [f"E{i}1"],
                }
            ],
        )
        reg.register_source(
            "org_small",
            f"s_{i}",
            f"S{i}",
            _parquet_bytes([{f"entity_{i}_id": f"E{i}1"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    incoming_meta = _schema_meta_for_columns(
        100,
        [{"name": "customer_id", "role": "identifier", "unique_count": 90, "samples": ["C1"]}],
    )
    candidates = reg.candidate_join_sources("org_small", "incoming", incoming_meta)

    assert {entry["id"] for entry in candidates} == {"s_0", "s_1", "s_2"}


def test_candidate_join_sources_prefers_source_aligned_foreign_key_targets(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    airport_meta = _schema_meta_for_columns(
        5_000,
        [
            {"name": "id", "role": "identifier", "unique_count": 5_000, "samples": ["A1", "A2"]},
            {
                "name": "iata_code",
                "role": "identifier",
                "unique_count": 4_800,
                "samples": ["JFK", "LAX"],
            },
        ],
    )
    reg.register_source(
        "org_source_aligned_candidates",
        "airports_src",
        "airports",
        _parquet_bytes([{"id": "A1", "iata_code": "JFK"}]),
        airport_meta,
        graph_nodes={},
        profile={},
    )

    for i in range(30):
        meta = _schema_meta_for_columns(
            5_000,
            [
                {
                    "name": f"entity_{i}_code",
                    "role": "identifier",
                    "unique_count": 4_500,
                    "samples": [f"E{i}1", f"E{i}2"],
                },
                {
                    "name": f"status_{i}",
                    "role": "category",
                    "unique_count": 4,
                    "samples": ["open", "closed"],
                },
            ],
        )
        reg.register_source(
            "org_source_aligned_candidates",
            f"noise_{i}",
            f"Noise{i}",
            _parquet_bytes([{f"entity_{i}_code": f"E{i}1", f"status_{i}": "open"}]),
            meta,
            graph_nodes={},
            profile={},
        )

    incoming_meta = _schema_meta_for_columns(
        250_000,
        [
            {
                "name": "airport_id",
                "role": "identifier",
                "unique_count": 12_000,
                "samples": ["A10", "A11"],
            },
            {"name": "bags_mishandled", "role": "metric", "unique_count": 100, "samples": [1, 2]},
        ],
    )

    candidates = reg.candidate_join_sources(
        "org_source_aligned_candidates",
        "incoming",
        incoming_meta,
        source_name="bag_handling_metrics",
        exhaustive_threshold=0,
        limit=6,
    )

    assert any(entry["id"] == "airports_src" for entry in candidates)


