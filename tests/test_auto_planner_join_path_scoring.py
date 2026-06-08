from pathlib import Path
from types import SimpleNamespace

from apps.api_server.services.auto_planner import AutoPlanner


def _planner_node(role: str, *, is_numeric: bool = False, fill_rate: float = 1.0):
    node = SimpleNamespace()
    node.role = role
    node.is_numeric = is_numeric
    node.fill_rate = fill_rate
    node.formula = None
    node.magnitude_class = None
    return node


def test_join_candidate_effective_conf_prefers_source_aligned_foreign_key(tmp_path):
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

    bare_id_candidate = {
        "source_a": "aircraft_components",
        "field_a": "id",
        "source_b": "aircraft",
        "field_b": "id",
        "confidence": 0.95,
        "cardinality": "many_to_one",
        "overlap": 1.0,
        "evidence_source": "registry",
    }
    foreign_key_candidate = {
        "source_a": "aircraft_components",
        "field_a": "aircraft_id",
        "source_b": "aircraft",
        "field_b": "id",
        "confidence": 0.93,
        "cardinality": "many_to_one",
        "overlap": 1.0,
        "evidence_source": "registry",
    }

    bare_score = planner._join_candidate_effective_conf(
        bare_id_candidate,
        group_col="registration",
    )
    foreign_score = planner._join_candidate_effective_conf(
        foreign_key_candidate,
        group_col="registration",
    )

    assert foreign_score > bare_score


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


def test_probe_join_keys_uses_ordered_python_probe_cache(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner._join_cache = {
        ("aircraft", "aircraft_components"): [
            {
                "source_a": "aircraft_components",
                "field_a": "id",
                "source_b": "aircraft",
                "field_b": "id",
                "confidence": 0.95,
                "cardinality": "many_to_one",
                "overlap": 1.0,
            }
        ]
    }
    calls: list[tuple[str, str]] = []

    def _fake_python_join_keys(src_a: str, src_b: str) -> list[dict]:
        calls.append((src_a, src_b))
        return [
            {
                "source_a": src_a,
                "field_a": "aircraft_id",
                "source_b": src_b,
                "field_b": "id",
                "confidence": 0.91,
                "cardinality": "many_to_one",
                "overlap": 1.0,
            }
        ]

    planner._python_join_keys = _fake_python_join_keys  # type: ignore[method-assign]

    first = planner._probe_join_keys("aircraft_components", "aircraft")
    second = planner._probe_join_keys("aircraft_components", "aircraft")

    assert calls == [("aircraft_components", "aircraft")]
    assert first == second
    assert planner._join_cache[("aircraft", "aircraft_components")][0]["field_a"] == "id"


def test_python_join_keys_detects_source_aligned_foreign_keys_with_low_sample_overlap(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.profiles = {
        "aircraft_components": {
            "id": {
                "fill_rate": 1.0,
                "is_numeric": True,
                "unique_count": 6552,
                "total_count": 6552,
                "strings": ["1", "2", "3", "4", "5"],
            },
            "aircraft_id": {
                "fill_rate": 1.0,
                "is_numeric": True,
                "unique_count": 252,
                "total_count": 6552,
                "strings": ["1"] * 50,
            },
        },
        "aircraft": {
            "id": {
                "fill_rate": 1.0,
                "is_numeric": True,
                "unique_count": 252,
                "total_count": 252,
                "strings": [str(index) for index in range(1, 51)],
            },
        },
    }

    candidates = planner._python_join_keys("aircraft_components", "aircraft")

    assert any(
        candidate["field_a"] == "aircraft_id"
        and candidate["field_b"] == "id"
        and candidate["cardinality"] == "many_to_one"
        for candidate in candidates
    )


def test_python_join_keys_handles_plural_source_alignment_for_foreign_keys(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.profiles = {
        "aircraft": {
            "airline_id": {
                "fill_rate": 1.0,
                "is_numeric": True,
                "unique_count": 1,
                "total_count": 252,
                "strings": ["1"] * 50,
            },
        },
        "airlines": {
            "id": {
                "fill_rate": 1.0,
                "is_numeric": True,
                "unique_count": 408,
                "total_count": 408,
                "strings": [str(index) for index in range(1, 51)],
            },
        },
    }

    candidates = planner._python_join_keys("aircraft", "airlines")

    assert any(
        candidate["field_a"] == "airline_id"
        and candidate["field_b"] == "id"
        and candidate["cardinality"] == "many_to_one"
        for candidate in candidates
    )


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


def test_search_join_path_prefers_plain_bridge_over_qualified_shortcut(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "aircraft_lease_agreements": {
            "contract_id": _planner_node("identifier"),
            "lessor_supplier_id": _planner_node("identifier"),
            "maintenance_reserve_usd": _planner_node("base_measure", is_numeric=True),
        },
        "contracts": {
            "id": _planner_node("identifier"),
            "supplier_id": _planner_node("identifier"),
        },
        "suppliers": {
            "id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft_lease_agreements": {
            "contract_id": {
                "fill_rate": 1.0,
                "unique_count": 182,
                "total_count": 182,
                "strings": ["1", "2"],
            },
            "lessor_supplier_id": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 182,
                "strings": ["10", "20"],
            },
            "maintenance_reserve_usd": {
                "fill_rate": 1.0,
                "unique_count": 182,
                "total_count": 182,
                "strings": ["100", "200"],
            },
        },
        "contracts": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 1763,
                "total_count": 1763,
                "strings": ["1", "2"],
            },
            "supplier_id": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 1763,
                "strings": ["10", "20"],
            },
        },
        "suppliers": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 600,
                "strings": ["10", "20"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 600,
                "strings": ["Supplier A", "Supplier B"],
            },
        },
    }
    planner._connections = [
        {
            "source_a_name": "aircraft_lease_agreements",
            "source_b_name": "suppliers",
            "col_a": "lessor_supplier_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 0.055,
        },
        {
            "source_a_name": "aircraft_lease_agreements",
            "source_b_name": "contracts",
            "col_a": "contract_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 0.0508,
        },
        {
            "source_a_name": "contracts",
            "source_b_name": "suppliers",
            "col_a": "supplier_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
    ]

    hops, conf, _notes, error = planner._search_join_path(
        "aircraft_lease_agreements",
        "suppliers",
        group_col="name",
    )

    assert error is None
    assert conf >= 0.14
    assert [(hop.left_source, hop.left_key, hop.right_source, hop.right_key) for hop in hops] == [
        ("aircraft_lease_agreements", "contract_id", "contracts", "id"),
        ("contracts", "supplier_id", "suppliers", "id"),
    ]


def test_search_join_path_prefers_plain_location_hierarchy_over_headquarters_shortcut(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.graph = {
        "bag_handling_metrics": {
            "airport_id": _planner_node("identifier"),
            "supplier_id": _planner_node("identifier"),
            "bags_processed": _planner_node("base_measure", is_numeric=True),
        },
        "airports": {
            "id": _planner_node("identifier"),
            "city_id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
        "suppliers": {
            "id": _planner_node("identifier"),
            "hq_city_id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
        "cities": {
            "id": _planner_node("identifier"),
            "name": _planner_node("text"),
        },
    }
    planner.profiles = {
        "bag_handling_metrics": {
            "airport_id": {
                "fill_rate": 1.0,
                "unique_count": 3557,
                "total_count": 2350784,
                "strings": ["1", "2"],
            },
            "supplier_id": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 2350784,
                "strings": ["10", "20"],
            },
            "bags_processed": {
                "fill_rate": 1.0,
                "unique_count": 2500,
                "total_count": 2350784,
                "strings": ["100", "200"],
            },
        },
        "airports": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 3557,
                "total_count": 3557,
                "strings": ["1", "2"],
            },
            "city_id": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 3557,
                "strings": ["100", "200"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 3557,
                "total_count": 3557,
                "strings": ["Airport A", "Airport B"],
            },
        },
        "suppliers": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 600,
                "strings": ["10", "20"],
            },
            "hq_city_id": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 600,
                "strings": ["100", "200"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 600,
                "total_count": 600,
                "strings": ["Supplier A", "Supplier B"],
            },
        },
        "cities": {
            "id": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 143,
                "strings": ["100", "200"],
            },
            "name": {
                "fill_rate": 1.0,
                "unique_count": 143,
                "total_count": 143,
                "strings": ["Paris", "Tokyo"],
            },
        },
    }
    planner._connections = [
        {
            "source_a_name": "bag_handling_metrics",
            "source_b_name": "airports",
            "col_a": "airport_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 0.1478,
        },
        {
            "source_a_name": "airports",
            "source_b_name": "cities",
            "col_a": "city_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 1.0,
        },
        {
            "source_a_name": "bag_handling_metrics",
            "source_b_name": "suppliers",
            "col_a": "supplier_id",
            "col_b": "id",
            "confidence": 0.839,
            "cardinality": "many_to_one",
            "overlap": 0.147,
        },
        {
            "source_a_name": "suppliers",
            "source_b_name": "cities",
            "col_a": "hq_city_id",
            "col_b": "id",
            "confidence": 0.84,
            "cardinality": "many_to_one",
            "overlap": 0.951,
        },
    ]

    hops, conf, _notes, error = planner._search_join_path(
        "bag_handling_metrics",
        "cities",
        group_col="name",
    )

    assert error is None
    assert conf >= 0.14
    assert [(hop.left_source, hop.left_key, hop.right_source, hop.right_key) for hop in hops] == [
        ("bag_handling_metrics", "airport_id", "airports", "id"),
        ("airports", "city_id", "cities", "id"),
    ]
