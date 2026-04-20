import base64
import io
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import HTTPException

from apps.api_server.routers.data_map import DataSource, MojoInstrumentationError
from apps.api_server.routers.query import _CACHE_LOCK, _PLANNER_CACHE, _SOURCE_CACHE
from apps.api_server.routers.sources import (
    _JOIN_PROJECTION_CACHE,
    RegisterRequest,
    _deep_join_projection_columns,
    _detect_joins_between,
    _load_join_projection,
    _load_join_projection_cached,
    register_source,
)
from apps.api_server.services import source_registry as reg


@pytest.mark.asyncio
async def test_register_source_persists_cached_content_for_each_org(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()

    payload = RegisterRequest(source=DataSource(
        name="S0",
        csv="account_code,local_group,measure_total\n00123,g_a,10\n00456,g_b,20\n",
    ))

    first = await register_source(payload, auth={"org_id": "org_a"})
    second = await register_source(payload, auth={"org_id": "org_b"})

    assert first["status"] == "registered"
    assert second["status"] == "registered"
    assert first["source_id"] == second["source_id"]

    org_a_sources = reg.list_sources("org_a")
    org_b_sources = reg.list_sources("org_b")

    assert [s["id"] for s in org_a_sources] == [first["source_id"]]
    assert [s["id"] for s in org_b_sources] == [second["source_id"]]

    meta_b = reg.get_source_meta("org_b", second["source_id"])
    assert meta_b is not None
    assert meta_b["row_count"] == 2


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


@pytest.mark.asyncio
async def test_register_source_reuses_identical_parquet_content_within_org(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    parquet_b64 = base64.b64encode(
        _parquet_bytes(
            [
                {"entity_key": "A", "measure_total": 10.0},
                {"entity_key": "B", "measure_total": 20.0},
            ]
        )
    ).decode()

    first = await register_source(
        RegisterRequest(source=DataSource(name="ParquetFirst", parquet_b64=parquet_b64)),
        auth={"org_id": "org_repeat"},
    )
    second = await register_source(
        RegisterRequest(source=DataSource(name="ParquetSecond", parquet_b64=parquet_b64)),
        auth={"org_id": "org_repeat"},
    )

    assert first["status"] == "registered"
    assert second["status"] == "already_registered"
    assert second["source_id"] == first["source_id"]
    assert [s["id"] for s in reg.list_sources("org_repeat")] == [first["source_id"]]


@pytest.mark.asyncio
async def test_register_source_reuses_identical_excel_content_within_org(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    excel_b64 = _excel_b64(
        [
            {"part_number": "00123", "measure_total": 10.0},
            {"part_number": "00456", "measure_total": 20.0},
        ]
    )

    first = await register_source(
        RegisterRequest(source=DataSource(name="ExcelFirst", excel_b64=excel_b64)),
        auth={"org_id": "org_excel"},
    )
    second = await register_source(
        RegisterRequest(source=DataSource(name="ExcelSecond", excel_b64=excel_b64)),
        auth={"org_id": "org_excel"},
    )

    assert first["status"] == "registered"
    assert second["status"] == "already_registered"
    assert second["source_id"] == first["source_id"]
    assert [s["id"] for s in reg.list_sources("org_excel")] == [first["source_id"]]


@pytest.mark.asyncio
async def test_register_source_preserves_sparse_numeric_csv_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()

    payload = RegisterRequest(source=DataSource(
        name="L0",
        csv="row_key,local_group,late_value\nrow_01,g_a,\nrow_02,g_b,\nrow_03,g_c,110.0\nrow_04,g_d,112.5\n",
    ))

    registered = await register_source(payload, auth={"org_id": "org_a"})
    parquet_bytes = reg.get_source_parquet("org_a", registered["source_id"])
    assert parquet_bytes is not None

    table = pq.read_table(io.BytesIO(parquet_bytes))
    rows = table.to_pylist()

    assert rows[0]["late_value"] is None
    assert isinstance(rows[2]["late_value"], float)
    assert rows[2]["late_value"] == 110.0


@pytest.mark.asyncio
async def test_register_source_persists_full_cardinality_stats_beyond_sample_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    lines = ["entity_key,measure_total"]
    lines.extend(f"K{i:04d},{i}" for i in range(600))
    payload = RegisterRequest(source=DataSource(name="WideKeys", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_stats"})
    meta = reg.get_source_meta("org_stats", registered["source_id"])

    assert meta is not None
    profile = meta["planner_profile"]["entity_key"]
    assert profile["unique_count"] == 600
    assert profile["total_count"] == 600


def _parquet_bytes(rows: list[dict]) -> bytes:
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), buf)
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


def test_deep_join_projection_columns_caps_and_deduplicates():
    join_blocks = [
        {"name": "entity_key"},
        {"name": "entity_key"},
        {"name": "measure_total"},
        {"name": "segment_label"},
    ]

    projected = _deep_join_projection_columns(join_blocks, limit=2)

    assert projected == ["entity_key", "measure_total"]


def test_load_join_projection_reads_ranked_join_columns_only():
    parquet_bytes = _parquet_bytes([
        {
            "entity_key": "A",
            "measure_total": 10.0,
            "noise_a": "n1",
            "noise_b": "n2",
        },
    ])

    projected = _load_join_projection(
        parquet_bytes,
        [
            {"name": "entity_key"},
            {"name": "measure_total"},
        ],
    )

    assert list(projected.columns) == ["entity_key", "measure_total"]


def test_load_join_projection_cached_reuses_projection_until_source_revision_changes(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    _JOIN_PROJECTION_CACHE.clear()

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
    ):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(parquet_bytes_arg, join_blocks_arg, parquet_path=parquet_path)

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

    reg.update_source_meta("org_cached_projection", "s_cached", {"semantic_aliases": {"entity": ["entity_key"]}})

    _load_join_projection_cached(
        org_id="org_cached_projection",
        source_id="s_cached",
        parquet_path=parquet_path,
        join_blocks=[{"name": "entity_key"}],
    )

    assert calls == 2


@pytest.mark.asyncio
async def test_detect_joins_between_infers_one_to_one_for_exact_entity_keys(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    mojo_called = False

    async def _unexpected_mojo(*_args, **_kwargs):
        nonlocal mojo_called
        mojo_called = True
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _unexpected_mojo)

    left = _parquet_bytes([
        {"entity_key": "A", "measure_total": 10.0},
        {"entity_key": "B", "measure_total": 20.0},
    ])
    right = _parquet_bytes([
        {"entity_key": "A", "segment_label": "seg_1"},
        {"entity_key": "B", "segment_label": "seg_2"},
    ])

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

    assert joins == [{
        "source_a": "src_a",
        "source_a_name": "S0",
        "col_a": "entity_key",
        "source_b": "src_b",
        "source_b_name": "S1",
        "col_b": "entity_key",
        "confidence": 0.99,
        "cardinality": "one_to_one",
        "overlap": 1.0,
    }]
    assert mojo_called is False


@pytest.mark.asyncio
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
        left_join_blocks=[{
            "name": "entity_key",
            "norm": "entitykey",
            "key_like": True,
            "role": "identifier",
            "unique_ratio": 1.0,
            "samples": ["A", "B", "C"],
        }],
        right_join_blocks=[{
            "name": "entity_key",
            "norm": "entitykey",
            "key_like": True,
            "role": "identifier",
            "unique_ratio": 1.0,
            "samples": ["A", "B", "C", "D"],
        }],
    )

    assert joins == [{
        "source_a": "src_a",
        "source_a_name": "S0",
        "col_a": "entity_key",
        "source_b": "src_b",
        "source_b_name": "S1",
        "col_b": "entity_key",
        "confidence": 0.988,
        "cardinality": "one_to_one",
        "overlap": 0.75,
    }]


@pytest.mark.asyncio
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
    assert joins == [{
        "source_a": "src_a",
        "source_a_name": "S0",
        "col_a": "part_number",
        "source_b": "src_b",
        "source_b_name": "S1",
        "col_b": "part_number",
        "confidence": 0.753,
        "cardinality": "one_to_many",
        "overlap": 0.06,
    }]


@pytest.mark.asyncio
async def test_detect_joins_between_accepts_preloaded_source_projection(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    left = _parquet_bytes([
        {"entity_key": "A", "measure_total": 10.0},
        {"entity_key": "B", "measure_total": 20.0},
    ])
    right = _parquet_bytes([
        {"entity_key": "A", "segment_label": "seg_1"},
        {"entity_key": "B", "segment_label": "seg_2"},
    ])
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


@pytest.mark.asyncio
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
        _parquet_bytes([
            {"entity_key": "A", "measure_total": 10.0},
            {"entity_key": "B", "measure_total": 20.0},
        ]),
        left_meta,
        graph_nodes={},
        profile={},
    )
    reg.register_source(
        "org_detect_paths",
        "src_b",
        "S1",
        _parquet_bytes([
            {"entity_key": "A", "segment_label": "seg_1"},
            {"entity_key": "B", "segment_label": "seg_2"},
        ]),
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


@pytest.mark.asyncio
async def test_detect_joins_between_skips_generic_many_to_many_same_name_columns(monkeypatch):
    _JOIN_PROJECTION_CACHE.clear()

    async def _no_mojo(*_args, **_kwargs):
        return None

    monkeypatch.setattr("apps.api_server.routers.sources._call_mojo_join_detect", _no_mojo)

    left = _parquet_bytes([
        {"local_group": "g_a", "late_value": 1.0},
        {"local_group": "g_a", "late_value": 2.0},
        {"local_group": "g_b", "late_value": 3.0},
        {"local_group": "g_b", "late_value": 4.0},
    ])
    right = _parquet_bytes([
        {"local_group": "g_a", "measure_total": 10.0},
        {"local_group": "g_a", "measure_total": 20.0},
        {"local_group": "g_b", "measure_total": 30.0},
        {"local_group": "g_b", "measure_total": 40.0},
    ])

    joins = await _detect_joins_between("org_detect_many", "src_a", "L0", left, "src_b", "S0", right)

    assert joins == []


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
        [{
            "source_a": "src_a",
            "source_a_name": "Alpha",
            "col_a": "entity_key",
            "source_b": "src_b",
            "source_b_name": "Beta",
            "col_b": "entity_key",
            "confidence": 0.97,
            "cardinality": "one_to_one",
            "overlap": 1.0,
        }],
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


@pytest.mark.asyncio
async def test_register_source_prewarms_registry_planner_for_registered_and_already_registered(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    async with _CACHE_LOCK:
        _SOURCE_CACHE.clear()
        _PLANNER_CACHE.clear()

    calls: list[tuple[str, str]] = []

    async def _fake_get_registry_planner(org_id: str, *, llm_policy: str = "never", **_kwargs):
        calls.append((org_id, llm_policy))
        return object(), len(calls) > 1, f"rev_{len(calls)}"

    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    payload = RegisterRequest(source=DataSource(
        name="S0",
        csv="entity_key,measure_total\nA,10\nB,20\n",
    ))

    first = await register_source(payload, auth={"org_id": "org_a"})
    second = await register_source(payload, auth={"org_id": "org_a"})

    assert first["status"] == "registered"
    assert second["status"] == "already_registered"
    assert first["planner_cache_hit"] is False
    assert second["planner_cache_hit"] is True
    assert len(calls) == 2
    assert calls == [("org_a", "never"), ("org_a", "never")]


def test_candidate_join_sources_blocks_large_org_to_likely_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    matching_meta = _schema_meta_for_columns(
        200,
        [
            {"name": "customer_id", "role": "identifier", "unique_count": 180, "samples": ["C100", "C200"]},
            {"name": "segment_label", "role": "category", "unique_count": 6, "samples": ["ENT", "SMB"]},
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
            {"name": "customer_id", "role": "identifier", "unique_count": 260, "samples": ["C100", "C300"]},
            {"name": "order_number", "role": "identifier", "unique_count": 300, "samples": ["O1", "O2"]},
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
            [{"name": f"entity_{i}_id", "role": "identifier", "unique_count": 90, "samples": [f"E{i}1"]}],
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


@pytest.mark.asyncio
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
            {"name": "customer_id", "role": "identifier", "unique_count": 180, "samples": ["C100", "C200"]},
            {"name": "order_number", "role": "identifier", "unique_count": 190, "samples": ["O100", "O200"]},
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    lines = ["customer_id,order_number,vendor_code,serial_key,measure_total"]
    lines.extend(
        f"C{i:04d},O{i:04d},V{i:04d},S{i:04d},{i}"
        for i in range(3000)
    )
    payload = RegisterRequest(source=DataSource(name="IncomingMedium", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_medium_scored"})

    assert registered["join_existing_total"] == 12
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] < 12
    assert "match_src" in join_calls
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.asyncio
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:04d},{i}" for i in range(6000))
    payload = RegisterRequest(source=DataSource(name="IncomingLarge", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_small_scored"})

    assert registered["join_existing_total"] == 5
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] < 5
    assert join_calls == ["s_0"]


@pytest.mark.asyncio
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
        [{"name": "customer_id", "role": "identifier", "unique_count": 5_200, "samples": ["C100", "C200"]}],
    )
    unrelated_meta = _schema_meta_for_columns(
        5_500,
        [{"name": "vendor_code", "role": "identifier", "unique_count": 5_100, "samples": ["V100", "V200"]}],
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:04d},{i}" for i in range(6_000))
    payload = RegisterRequest(source=DataSource(name="IncomingTiny", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_tiny_scored"})

    assert registered["join_existing_total"] == 2
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] == 1
    assert join_calls == ["match_src"]


@pytest.mark.asyncio
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
        [{"name": "vendor_code", "role": "identifier", "unique_count": 5_100, "samples": ["V100", "V200"]}],
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:04d},{i}" for i in range(6_000))
    payload = RegisterRequest(source=DataSource(name="IncomingSingle", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_single_scored"})

    assert registered["join_existing_total"] == 1
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] == 0
    assert join_calls == []


@pytest.mark.asyncio
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
        [{"name": "customer_id", "role": "identifier", "unique_count": 18_000, "samples": ["C100", "C200"]}],
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
            [{"name": f"vendor_code_{i}", "role": "identifier", "unique_count": 18_500, "samples": [f"V{i}1", f"V{i}2"]}],
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:04d},{i}" for i in range(500))
    payload = RegisterRequest(source=DataSource(name="IncomingMidLowRows", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_mid_scored_low_rows"})

    assert registered["join_existing_total"] == 8
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] == 1
    assert join_calls == ["match_src"]


@pytest.mark.asyncio
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
                {"name": f"vendor_code_{i}", "role": "identifier", "unique_count": 22_500, "samples": [f"V{i}1", f"V{i}2"]},
                {"name": f"vendor_ref_{i}", "role": "identifier", "unique_count": 22_000, "samples": [f"R{i}1", f"R{i}2"]},
                {"name": f"vendor_key_{i}", "role": "identifier", "unique_count": 21_500, "samples": [f"K{i}1", f"K{i}2"]},
                {"name": f"vendor_guid_{i}", "role": "identifier", "unique_count": 21_000, "samples": [f"G{i}1", f"G{i}2"]},
            ],
        )
        reg.register_source(
            "org_mid_scored_none",
            f"u_{i}",
            f"U{i}",
            _parquet_bytes([
                {
                    f"vendor_code_{i}": f"V{i}1",
                    f"vendor_ref_{i}": f"R{i}1",
                    f"vendor_key_{i}": f"K{i}1",
                    f"vendor_guid_{i}": f"G{i}1",
                }
            ]),
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    lines = ["audit_id,quality_ref,review_code"]
    lines.extend(f"A{i:02d},Q{i:02d},R{i:02d}" for i in range(12))
    payload = RegisterRequest(source=DataSource(name="IncomingMidNoCandidates", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_mid_scored_none"})

    assert registered["join_existing_total"] == 12
    assert registered["join_scan_mode"] == "scored"
    assert registered["join_candidates_considered"] < 12
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.asyncio
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    payload = RegisterRequest(source=DataSource(
        name="Incoming",
        csv="customer_id,measure_total\nC100,10\nC200,20\n",
    ))

    registered = await register_source(payload, auth={"org_id": "org_join_block"})

    assert registered["join_existing_total"] == 30
    assert registered["join_candidates_considered"] < 30
    assert "s_0" in join_calls
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.asyncio
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:05d},{i}" for i in range(35_000))
    payload = RegisterRequest(source=DataSource(name="IncomingHuge", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_join_limit"})

    assert registered["join_existing_total"] == 30
    assert registered["join_candidate_limit"] == 8
    assert registered["join_candidate_min_score"] == 4.5
    assert registered["join_candidates_considered"] <= 8
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.asyncio
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    lines = ["customer_id,measure_total"]
    lines.extend(f"C{i:05d},{i}" for i in range(60_000))
    payload = RegisterRequest(source=DataSource(name="IncomingVeryLarge", csv="\n".join(lines) + "\n"))

    registered = await register_source(payload, auth={"org_id": "org_join_limit_very_large"})

    assert registered["join_existing_total"] == 30
    assert registered["join_candidate_limit"] == 6
    assert registered["join_candidate_min_score"] == 4.5
    assert registered["join_candidates_considered"] <= 6
    assert len(join_calls) == registered["join_candidates_considered"]


@pytest.mark.asyncio
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

    lines = ["customer_id,order_number,vendor_code,serial_key,measure_total"]
    lines.extend(
        f"C{i:04d},O{i:04d},V{i:04d},S{i:04d},{i}"
        for i in range(4_000)
    )
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


@pytest.mark.asyncio
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
    monkeypatch.setattr("apps.api_server.routers.sources._get_registry_planner", _fake_get_registry_planner)

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


@pytest.mark.asyncio
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

    payload = RegisterRequest(source=DataSource(
        name="StrictMojoFailure",
        csv="customer_id,measure_total\nC100,10\nC200,20\n",
    ))

    with pytest.raises(HTTPException) as excinfo:
        await register_source(payload, auth={"org_id": "org_strict"})

    assert excinfo.value.status_code == 503
    assert excinfo.value.detail["error"]["code"] == "mojo_instrumentation_unavailable"
