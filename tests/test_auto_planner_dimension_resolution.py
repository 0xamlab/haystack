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


def test_resolve_dimension_prefers_exact_source_match_over_partial_source_overlap(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "aircraft": {
            "registration": _planner_node("text"),
            "airline_id": _planner_node("identifier"),
        },
        "aircraft_components": {
            "aircraft_id": _planner_node("identifier"),
            "serial_number": _planner_node("text"),
        },
    }
    planner.profiles = {
        "aircraft": {
            "registration": {
                "fill_rate": 1.0,
                "unique_count": 200,
                "total_count": 200,
                "strings": ["N123AA", "N456BB"],
            },
            "airline_id": {
                "fill_rate": 1.0,
                "unique_count": 20,
                "total_count": 200,
                "strings": ["1", "2"],
            },
        },
        "aircraft_components": {
            "aircraft_id": {
                "fill_rate": 1.0,
                "unique_count": 200,
                "total_count": 5000,
                "strings": ["1", "2"],
            },
            "serial_number": {
                "fill_rate": 1.0,
                "unique_count": 5000,
                "total_count": 5000,
                "strings": ["SN-1", "SN-2"],
            },
        },
    }

    src, col, _score, _steps = planner.resolve_dimension(
        "aircraft",
        preferred_source="aircraft_components",
    )

    assert src == "aircraft"
    assert col == "registration"


def test_resolve_dimension_prefers_display_column_for_exact_source_hint(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "airlines": {
            "name": _planner_node("text"),
            "airline_type": _planner_node("category"),
            "id": _planner_node("identifier"),
        },
        "aircraft": {
            "airline_id": _planner_node("identifier"),
        },
    }
    planner.profiles = {
        "airlines": {
            "name": {
                "fill_rate": 1.0,
                "unique_count": 50,
                "total_count": 50,
                "strings": ["Delta", "United"],
            },
            "airline_type": {
                "fill_rate": 1.0,
                "unique_count": 3,
                "total_count": 50,
                "strings": ["Legacy", "LCC"],
            },
            "id": {
                "fill_rate": 1.0,
                "unique_count": 50,
                "total_count": 50,
                "strings": ["1", "2"],
            },
        },
        "aircraft": {
            "airline_id": {
                "fill_rate": 1.0,
                "unique_count": 50,
                "total_count": 200,
                "strings": ["1", "2"],
            },
        },
    }

    src, col, _score, _steps = planner.resolve_dimension(
        "airlines",
        preferred_source="aircraft",
    )

    assert src == "airlines"
    assert col == "name"


def test_resolve_dimension_prefers_exact_plural_source_hint(tmp_path):
    planner = AutoPlanner(data_dir=Path(tmp_path), llm_policy="never")
    planner.mojo_engines = []
    planner.graph = {
        "aircraft_types": {
            "iata_code": _planner_node("text"),
            "description": _planner_node("text"),
        },
        "aircraft_components": {
            "aircraft_id": _planner_node("identifier"),
            "component_type": _planner_node("category"),
        },
    }
    planner.profiles = {
        "aircraft_types": {
            "iata_code": {
                "fill_rate": 1.0,
                "unique_count": 12,
                "total_count": 12,
                "strings": ["A320", "B737"],
            },
            "description": {
                "fill_rate": 1.0,
                "unique_count": 12,
                "total_count": 12,
                "strings": ["Narrowbody", "Widebody"],
            },
        },
        "aircraft_components": {
            "aircraft_id": {
                "fill_rate": 1.0,
                "unique_count": 252,
                "total_count": 6000,
                "strings": ["1", "2"],
            },
            "component_type": {
                "fill_rate": 1.0,
                "unique_count": 6,
                "total_count": 6000,
                "strings": ["engine", "apu"],
            },
        },
    }

    src, col, _score, _steps = planner.resolve_dimension(
        "aircraft types",
        preferred_source="aircraft",
    )

    assert src == "aircraft_types"
    assert col == "iata_code"
