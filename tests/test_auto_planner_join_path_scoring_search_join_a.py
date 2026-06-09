"""Tests for test_auto_planner_join_path_scoring: search_join_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-1/tests/test_auto_planner_join_path_scoring.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_join_path_scoring_helpers import *  # noqa: F401,F403


def test_search_join_path_prefers_source_aligned_foreign_key(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "aircraft_components": {
            "id": _planner_node("identifier"),
            "aircraft_id": _planner_node("identifier"),
        },
        "aircraft": {
            "id": _planner_node("identifier"),
            "registration": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft_components": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 6500,
                "total_count": 6500,
                "strings": ["1", "2"],
            },
            "aircraft_id": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 6500,
                "strings": ["1", "2"],
            },
        },
        "aircraft": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 252,
                "strings": ["1", "2"],
            },
            "registration": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 252,
                "strings": ["N1", "N2"],
            },
        },
    }
    planner._connections = [
        {
            "source_a_name": "aircraft_components",
            "source_b_name": "aircraft",
            "col_a": "id",
            "col_b": "id",
            "confidence": 0.95,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
        {
            "source_a_name": "aircraft_components",
            "source_b_name": "aircraft",
            "col_a": "aircraft_id",
            "col_b": "id",
            "confidence": 0.93,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
    ]

    hops, _conf, _notes, error = planner._search_join_path(
        "aircraft_components",
        "aircraft",
        group_col="registration",
    )

    assert error is None
    assert len(hops) == 1
    assert hops[0].left_key == "aircraft_id"
    assert hops[0].right_key == "id"


def test_search_join_path_memoizes_per_planner(tmp_path):
    # Fix #3: the join-path search is memoized on the planner instance, so a repeated
    # (metric_src, group_src, group_col) lookup is served from cache (cold→warm ~9ms).
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "aircraft_components": {
            "id": _planner_node("identifier"),
            "aircraft_id": _planner_node("identifier"),
        },
        "aircraft": {
            "id": _planner_node("identifier"),
            "registration": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft_components": {
            "id": {"fill_rate": 1.0, "unique_count": 6500, "total_count": 6500, "strings": ["1"]},
            "aircraft_id": {"fill_rate": 1.0, "unique_count": 252, "total_count": 6500, "strings": ["1"]},
        },
        "aircraft": {
            "id": {"fill_rate": 1.0, "unique_count": 252, "total_count": 252, "strings": ["1"]},
            "registration": {"fill_rate": 1.0, "unique_count": 252, "total_count": 252, "strings": ["N1"]},
        },
    }
    planner._connections = [
        {
            "source_a_name": "aircraft_components",
            "source_b_name": "aircraft",
            "col_a": "aircraft_id",
            "col_b": "id",
            "confidence": 0.93,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
    ]

    first = planner._search_join_path("aircraft_components", "aircraft", group_col="registration")
    assert ("aircraft_components", "aircraft", "registration") in planner._join_path_cache
    second = planner._search_join_path("aircraft_components", "aircraft", group_col="registration")
    assert second == first  # served from the per-planner cache


def test_search_join_path_respects_expansion_budget(tmp_path, monkeypatch):
    # Fix #1: a dense graph with no registry adjacency would fan out ~all-sources at every
    # node to max_hops (thousands of edge evals). The budget caps that to a small, bounded
    # number — proving the cold-query explosion is contained without dropping real joins.
    import apps.api_server.services.auto_planner_join_paths as jp

    monkeypatch.setattr(jp, "_JOIN_SEARCH_MAX_EXPANSIONS", 3)
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    graph: dict = {"metric_src": {"id": _planner_node("identifier"), "k": _planner_node("identifier")}}
    for i in range(9):
        graph[f"noise_{i}"] = {"id": _planner_node("identifier"), "k": _planner_node("identifier")}
    graph["target_src"] = {"id": _planner_node("identifier"), "label": _planner_node("text")}
    planner.graph = graph
    planner.profiles = {
        src: {
            col: {"fill_rate": 1.0, "unique_count": 100, "total_count": 100, "strings": ["1"]}
            for col in cols
        }
        for src, cols in graph.items()
    }
    planner._connections = []  # no registry adjacency → forces the broad fallback fan-out

    calls = {"n": 0}
    original = planner._direct_join_candidates

    def _counting(a, b):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return original(a, b)

    monkeypatch.setattr(planner, "_direct_join_candidates", _counting)

    # Must terminate (not explode) and stay bounded — without the budget this would be
    # ~10^4 candidate evaluations; with it, well under 30.
    planner._search_join_path("metric_src", "target_src", group_col="label")
    assert calls["n"] < 30


def test_search_join_path_merges_runtime_candidates_when_registry_only_has_generic_ids(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "ai_copilot_recommendations": {
            "id": _planner_node("identifier"),
            "disruption_event_id": _planner_node("identifier"),
        },
        "disruption_events": {
            "id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
    }
    planner.profiles = {
        "ai_copilot_recommendations": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 254,
                "total_count": 254,
                "strings": ["1", "2"],
            },
            "disruption_event_id": {
                "fill_rate": 1.0,
                "unique_count": 205,
                "total_count": 254,
                "strings": ["10", "20"],
            },
        },
        "disruption_events": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 205,
                "total_count": 205,
                "strings": ["10", "20"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 205,
                "total_count": 205,
                "strings": ["Storm", "Strike"],
            },
        },
    }
    planner._connections = [
        {
            "source_a_name": "ai_copilot_recommendations",
            "source_b_name": "disruption_events",
            "col_a": "id",
            "col_b": "id",
            "confidence": 0.95,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
    ]
    planner._probe_join_keys = lambda left, right: [  # type: ignore[method-assign]
        {
            "source_a": left,
            "field_a": "disruption_event_id",
            "source_b": right,
            "field_b": "id",
            "confidence": 0.91,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        }
    ]

    hops, _conf, _notes, error = planner._search_join_path(
        "ai_copilot_recommendations",
        "disruption_events",
        group_col="name",
    )

    assert error is None
    assert len(hops) == 1
    assert hops[0].left_key == "disruption_event_id"
    assert hops[0].right_key == "id"


def test_search_join_path_prefers_low_cardinality_foreign_key_over_generic_id_match(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "aircraft": {
            "id": _planner_node("identifier"),
            "airline_id": _planner_node("identifier"),
        },
        "airlines": {
            "id": _planner_node("identifier"),
            "airline_name": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 252,
                "strings": ["1", "2"],
            },
            "airline_id": {
                "fill_rate": 1.0,
                "unique_count": 1,
                "total_count": 252,
                "strings": ["1"] * 50,
            },
        },
        "airlines": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 408,
                "total_count": 408,
                "strings": [str(index) for index in range(1, 51)],
            },
            "airline_name": {
                "fill_rate": 1.0,
                "unique_count": 408,
                "total_count": 408,
                "strings": ["Aurora", "Atlas"],
            },
        },
    }
    planner._connections = [
        {
            "source_a_name": "aircraft",
            "source_b_name": "airlines",
            "col_a": "id",
            "col_b": "id",
            "confidence": 0.99,
            "cardinality": "one_to_one",
            "overlap": 1.0,
        },
    ]

    hops, conf, _notes, error = planner._search_join_path(
        "aircraft",
        "airlines",
        group_col="airline_name",
    )

    assert error is None
    assert conf >= 0.12
    assert len(hops) == 1
    assert hops[0].left_key == "airline_id"
    assert hops[0].right_key == "id"


def test_search_join_path_rejects_low_coverage_generic_id_registry_edge(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "aircraft_components": {
            "id": _planner_node("identifier"),
        },
        "aircraft_types": {
            "id": _planner_node("identifier"),
            "iata_code": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft_components": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 6552,
                "total_count": 6552,
                "strings": [str(index) for index in range(1, 51)],
            },
        },
        "aircraft_types": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 40,
                "total_count": 40,
                "strings": [str(index) for index in range(1, 41)],
            },
            "iata_code": {
                "fill_rate": 1.0,
                "unique_count": 40,
                "total_count": 40,
                "strings": ["320", "321"],
            },
        },
    }
    planner.tables = {
        "aircraft_components": [{"id": str(index)} for index in range(1, 401)],
        "aircraft_types": [
            {"id": str(index), "iata_code": f"T{index:03d}"} for index in range(1, 41)
        ],
    }
    planner._connections = [
        {
            "source_a_name": "aircraft_components",
            "source_b_name": "aircraft_types",
            "col_a": "id",
            "col_b": "id",
            "confidence": 0.99,
            "cardinality": "one_to_one",
            "overlap": 1.0,
        },
    ]

    hops, conf, _notes, error = planner._search_join_path(
        "aircraft_components",
        "aircraft_types",
        group_col="iata_code",
    )

    assert len(hops) == 1
    assert hops[0].left_key == "id"
    assert hops[0].right_key == "id"
    assert conf < 0.18
    assert error is not None


def test_search_join_path_accepts_non_expanding_two_hop_foreign_key_chain(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "aircraft": {
            "id": _planner_node("identifier"),
            "airline_id": _planner_node("identifier"),
        },
        "airlines": {
            "id": _planner_node("identifier"),
            "alliance_id": _planner_node("identifier"),
        },
        "alliances": {
            "id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft": {
            "airline_id": {
                "fill_rate": 1.0,
                "unique_count": 1,
                "total_count": 252,
                "strings": ["1"] * 50,
            },
            "id": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 252,
                "strings": ["1", "2"],
            },
        },
        "airlines": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 408,
                "total_count": 408,
                "strings": [str(index) for index in range(1, 51)],
            },
            "alliance_id": {
                "fill_rate": 1.0,
                "unique_count": 1,
                "total_count": 408,
                "strings": ["1"] * 50,
            },
        },
        "alliances": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["1", "2", "3"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["oneworld", "SkyTeam", "Star Alliance"],
            },
        },
    }
    planner._connections = []

    hops, conf, _notes, error = planner._search_join_path(
        "aircraft",
        "alliances",
        group_col="name",
    )

    assert error is None
    assert conf >= 0.20
    assert [(hop.left_key, hop.right_key) for hop in hops] == [
        ("airline_id", "id"),
        ("alliance_id", "id"),
    ]


def test_search_join_path_accepts_high_confidence_non_expanding_two_hop_chain_near_floor(
    tmp_path,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "aircraft": {
            "id": _planner_node("identifier"),
            "airline_id": _planner_node("identifier"),
            "total_flight_hours": _planner_node("base_measure", is_numeric=True),
        },
        "airlines": {
            "id": _planner_node("identifier"),
            "alliance_id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
        "alliances": {
            "id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 252,
                "strings": ["1", "2"],
            },
            "airline_id": {
                "fill_rate": 1.0,
                "unique_count": 12,
                "total_count": 252,
                "strings": ["1", "2", "3"],
            },
            "total_flight_hours": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 252,
                "strings": ["100", "200"],
            },
        },
        "airlines": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 408,
                "total_count": 408,
                "strings": [str(index) for index in range(1, 51)],
            },
            "alliance_id": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 408,
                "strings": ["1", "2", "3"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 408,
                "total_count": 408,
                "strings": ["Airline A", "Airline B"],
            },
        },
        "alliances": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["1", "2", "3"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["oneworld", "SkyTeam", "Star Alliance"],
            },
        },
    }
    planner._connections = []

    def _probe(left_source: str, right_source: str):  # type: ignore[no-untyped-def]
        if (left_source, right_source) == ("aircraft", "airlines"):
            return [
                {
                    "field_a": "airline_id",
                    "source_a": "aircraft",
                    "field_b": "id",
                    "source_b": "airlines",
                    "confidence": 0.814,
                    "overlap": 0.02,
                    "cardinality": "many_to_one",
                }
            ]
        if (left_source, right_source) == ("airlines", "alliances"):
            return [
                {
                    "field_a": "alliance_id",
                    "source_a": "airlines",
                    "field_b": "id",
                    "source_b": "alliances",
                    "confidence": 0.81,
                    "overlap": 0.0,
                    "cardinality": "many_to_one",
                }
            ]
        return []

    planner._probe_join_keys = _probe  # type: ignore[method-assign]

    hops, conf, _notes, error = planner._search_join_path(
        "aircraft",
        "alliances",
        group_col="name",
    )

    assert error is None
    assert conf >= 0.18
    assert [(hop.left_key, hop.right_key) for hop in hops] == [
        ("airline_id", "id"),
        ("alliance_id", "id"),
    ]


def test_search_join_path_accepts_live_like_source_aligned_two_hop_chain_below_old_floor(
    tmp_path,
):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "aircraft": {
            "id": _planner_node("identifier"),
            "airline_id": _planner_node("identifier"),
            "total_flight_hours": _planner_node("base_measure", is_numeric=True),
        },
        "airlines": {
            "id": _planner_node("identifier"),
            "alliance_id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
        "alliances": {
            "id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 252,
                "strings": ["1", "2"],
            },
            "airline_id": {
                "fill_rate": 1.0,
                "unique_count": 12,
                "total_count": 252,
                "strings": ["1", "2", "3"],
            },
            "total_flight_hours": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 252,
                "strings": ["100", "200"],
            },
        },
        "airlines": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 408,
                "total_count": 408,
                "strings": [str(index) for index in range(1, 51)],
            },
            "alliance_id": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 408,
                "strings": ["1", "2", "3"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 408,
                "total_count": 408,
                "strings": ["Airline A", "Airline B"],
            },
        },
        "alliances": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["1", "2", "3"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 3,
                "strings": ["oneworld", "SkyTeam", "Star Alliance"],
            },
        },
    }
    planner._connections = []

    def _probe(left_source: str, right_source: str):  # type: ignore[no-untyped-def]
        if (left_source, right_source) == ("aircraft", "airlines"):
            return [
                {
                    "field_a": "airline_id",
                    "source_a": "aircraft",
                    "field_b": "id",
                    "source_b": "airlines",
                    "confidence": 0.79,
                    "overlap": 0.02,
                    "cardinality": "many_to_one",
                }
            ]
        if (left_source, right_source) == ("airlines", "alliances"):
            return [
                {
                    "field_a": "alliance_id",
                    "source_a": "airlines",
                    "field_b": "id",
                    "source_b": "alliances",
                    "confidence": 0.81,
                    "overlap": 0.0,
                    "cardinality": "many_to_one",
                }
            ]
        return []

    planner._probe_join_keys = _probe  # type: ignore[method-assign]

    hops, conf, _notes, error = planner._search_join_path(
        "aircraft",
        "alliances",
        group_col="name",
    )

    assert error is None
    assert conf >= 0.12
    assert [(hop.left_key, hop.right_key) for hop in hops] == [
        ("airline_id", "id"),
        ("alliance_id", "id"),
    ]


