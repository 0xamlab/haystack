"""Tests for test_auto_planner: misc_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_7fba9f9f-465-5/tests/test_auto_planner.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_helpers import *  # noqa: F401,F403


def test_search_join_path_prefers_registry_adjacency_before_broad_pair_probing(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "S0": {
            "METRIC": ColumnNode(
                name="METRIC", role="derived_measure", is_numeric=True, fill_rate=1.0
            )
        },
        "S1": {
            "MID_LABEL": ColumnNode(
                name="MID_LABEL", role="category", is_numeric=False, fill_rate=1.0
            )
        },
        "S2": {
            "FINAL_LABEL": ColumnNode(
                name="FINAL_LABEL", role="category", is_numeric=False, fill_rate=1.0
            )
        },
        "S3": {
            "UNUSED": ColumnNode(name="UNUSED", role="category", is_numeric=False, fill_rate=1.0)
        },
    }
    planner.profiles = {
        "S0": {
            "S1_ID": {
                "fill_rate": 1.0,
                "unique_count": 10,
                "total_count": 10,
                "strings": ["1", "2"],
            }
        },
        "S1": {
            "ID": {"fill_rate": 1.0, "unique_count": 10, "total_count": 10, "strings": ["1", "2"]},
            "S2_ID": {
                "fill_rate": 1.0,
                "unique_count": 5,
                "total_count": 10,
                "strings": ["10", "20"],
            },
            "MID_LABEL": {
                "fill_rate": 1.0,
                "unique_count": 10,
                "total_count": 10,
                "strings": ["A", "B"],
            },
        },
        "S2": {
            "ID": {"fill_rate": 1.0, "unique_count": 5, "total_count": 5, "strings": ["10", "20"]},
            "FINAL_LABEL": {
                "fill_rate": 1.0,
                "unique_count": 5,
                "total_count": 5,
                "strings": ["X", "Y"],
            },
        },
        "S3": {
            "UNUSED": {"fill_rate": 1.0, "unique_count": 5, "total_count": 5, "strings": ["U", "V"]}
        },
    }
    planner._connections = [
        {
            "source_a_name": "S0",
            "source_b_name": "S1",
            "col_a": "S1_ID",
            "col_b": "ID",
            "confidence": 0.92,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
        {
            "source_a_name": "S1",
            "source_b_name": "S2",
            "col_a": "S2_ID",
            "col_b": "ID",
            "confidence": 0.91,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
    ]

    calls: list[tuple[str, str]] = []

    def _fake_direct_join_candidates(
        left_source: str, right_source: str
    ) -> list[dict[str, object]]:
        calls.append((left_source, right_source))
        mapping = {
            ("S0", "S1"): [
                {
                    "field_a": "S1_ID",
                    "source_a": "S0",
                    "field_b": "ID",
                    "source_b": "S1",
                    "confidence": 0.92,
                    "cardinality": "many_to_one",
                    "overlap": 1.0,
                    "evidence_source": "registry",
                }
            ],
            ("S1", "S2"): [
                {
                    "field_a": "S2_ID",
                    "source_a": "S1",
                    "field_b": "ID",
                    "source_b": "S2",
                    "confidence": 0.91,
                    "cardinality": "many_to_one",
                    "overlap": 1.0,
                    "evidence_source": "registry",
                }
            ],
        }
        if (left_source, right_source) not in mapping:
            raise AssertionError(
                f"registry-focused search should not probe unrelated pair {(left_source, right_source)}"
            )
        return mapping[(left_source, right_source)]

    planner._direct_join_candidates = _fake_direct_join_candidates  # type: ignore[method-assign]

    hops, conf, notes, err = planner._search_join_path("S0", "S2", "FINAL_LABEL")

    assert err is None
    assert len(hops) == 2
    assert [(hop.left_source, hop.right_source) for hop in hops] == [("S0", "S1"), ("S1", "S2")]
    assert conf >= 0.18
    assert calls == [("S0", "S1"), ("S1", "S2")]
    assert any(note.startswith("multi-hop path via") for note in notes)


def test_discover_sources_includes_local_parquet(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(
        pa.Table.from_pylist([{"entity_id": "A1", "measure_total": 10.0}]),
        tmp_path / "S0.parquet",
    )
    (tmp_path / "S1.csv").write_text("entity_id,measure_total\nB1,20\n", encoding="utf-8")

    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")

    assert planner.discover_sources() == ["S0", "S1"]


def test_build_knowledge_loads_local_parquet_sources(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = [
        {"entity_id": "A1", "local_group": "g_a", "measure_total": 10.0},
        {"entity_id": "A2", "local_group": "g_b", "measure_total": 20.0},
        {"entity_id": "A3", "local_group": "g_a", "measure_total": 30.0},
    ]
    pq.write_table(pa.Table.from_pylist(rows), tmp_path / "S0.parquet")

    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.build_knowledge()

    assert "S0" in planner.tables
    assert len(planner.tables["S0"]) == 3
    assert planner.profiles["S0"]["measure_total"]["is_numeric"] is True
    assert planner.profiles["S0"]["local_group"]["strings"] == ["g_a", "g_b", "g_a"]


def test_from_registry_uses_persisted_profiles_and_lazy_loads_records(tmp_path, monkeypatch):
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")

    rows = [
        {"entity_id": "A1", "local_group": "g_a", "measure_total": 10.0},
        {"entity_id": "A2", "local_group": "g_b", "measure_total": 20.0},
    ]
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), buf)

    reg.register_source(
        "org_registry",
        "src_a",
        "S0",
        buf.getvalue(),
        {
            "source": "S0",
            "row_count": 2,
            "columns": [
                {
                    "name": "entity_id",
                    "role": "identifier",
                    "is_numeric": False,
                    "fill_rate": 1.0,
                    "samples": ["A1", "A2"],
                },
                {
                    "name": "local_group",
                    "role": "category",
                    "is_numeric": False,
                    "fill_rate": 1.0,
                    "samples": ["g_a", "g_b"],
                    "cardinality": 2,
                },
                {
                    "name": "measure_total",
                    "role": "derived_measure",
                    "is_numeric": True,
                    "fill_rate": 1.0,
                    "mean": 15.0,
                    "magnitude": "large",
                },
            ],
            "query_hints": [
                {
                    "metric_role": "derived_measure",
                    "columns": [
                        {
                            "name": "measure_total",
                            "fill_rate": 1.0,
                            "samples": ["10.0", "20.0"],
                            "mean": 15.0,
                        }
                    ],
                }
            ],
            "planner_profile": {
                "entity_id": {
                    "is_numeric": False,
                    "strings": ["A1", "A2"],
                    "sample_values": ["A1", "A2"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                },
                "local_group": {
                    "is_numeric": False,
                    "strings": ["g_a", "g_b"],
                    "sample_values": ["g_a", "g_b"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                },
                "measure_total": {
                    "is_numeric": True,
                    "sample_values": ["10.0", "20.0"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                    "mean": 15.0,
                    "std": 5.0,
                },
            },
            "roles_summary": {"identifier": 1, "category": 1, "derived_measure": 1},
            "formulas": [],
        },
        graph_nodes={},
        profile={},
    )

    planner = AutoPlanner.from_registry("org_registry", data_dir=Path(tmp_path), llm_policy="never")

    assert "S0" not in planner.tables
    assert planner.profiles["S0"]["measure_total"]["mean"] == 15.0
    assert planner.profiles["S0"]["local_group"]["strings"] == ["g_a", "g_b"]
    assert planner._parquet_paths["S0"].exists()

    planner._ensure_records("S0")

    assert "S0" in planner.tables
    assert len(planner.tables["S0"]) == 2


def test_from_registry_reuses_cached_graph_nodes_across_rebuilds(tmp_path, monkeypatch):
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    monkeypatch.setattr(reg, "_SOURCES_DIR", Path(tmp_path) / "sources")
    query_router._GRAPH_NODE_CACHE.clear()
    AutoPlanner.from_registry.__globals__["_REGISTRY_SOURCE_ARTIFACT_CACHE"].clear()

    rows = [
        {"entity_id": "A1", "measure_total": 10.0},
        {"entity_id": "A2", "measure_total": 20.0},
    ]
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), buf)

    reg.register_source(
        "org_registry",
        "src_a",
        "S0",
        buf.getvalue(),
        {
            "source": "S0",
            "row_count": 2,
            "columns": [
                {"name": "entity_id", "role": "identifier", "is_numeric": False, "fill_rate": 1.0},
                {
                    "name": "measure_total",
                    "role": "derived_measure",
                    "is_numeric": True,
                    "fill_rate": 1.0,
                    "mean": 15.0,
                    "magnitude": "medium",
                },
            ],
            "planner_profile": {
                "entity_id": {
                    "is_numeric": False,
                    "strings": ["A1", "A2"],
                    "sample_values": ["A1", "A2"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                },
                "measure_total": {
                    "is_numeric": True,
                    "sample_values": ["10.0", "20.0"],
                    "unique_count": 2,
                    "total_count": 2,
                    "fill_rate": 1.0,
                    "mean": 15.0,
                    "std": 5.0,
                },
            },
            "roles_summary": {"identifier": 1, "derived_measure": 1},
            "formulas": [],
        },
        graph_nodes={},
        profile={},
    )

    calls = {"graph": 0, "profile": 0}
    original_graph = query_router._graph_nodes_from_meta
    original_profiles = AutoPlanner.from_registry.__globals__["_profiles_from_registry_meta"]

    def _counting_graph_nodes(meta: dict) -> dict[str, ColumnNode]:
        calls["graph"] += 1
        return original_graph(meta)

    def _counting_profiles(meta: dict) -> dict[str, dict]:
        calls["profile"] += 1
        return original_profiles(meta)

    monkeypatch.setattr(query_router, "_graph_nodes_from_meta", _counting_graph_nodes)
    monkeypatch.setitem(
        AutoPlanner.from_registry.__globals__,
        "_profiles_from_registry_meta",
        _counting_profiles,
    )

    first = AutoPlanner.from_registry("org_registry", data_dir=Path(tmp_path), llm_policy="never")
    second = AutoPlanner.from_registry("org_registry", data_dir=Path(tmp_path), llm_policy="never")

    assert "S0" in first.graph
    assert "S0" in second.graph
    assert calls["graph"] == 1
    assert calls["profile"] == 1


def test_python_field_map_prefers_percentage_when_hint_mentions_percent():
    analysis = AutoPlanner._python_field_map("aar margin percent")

    assert analysis["unit"] == "percentage"
    assert analysis["semantic_type"] == "percentage"


