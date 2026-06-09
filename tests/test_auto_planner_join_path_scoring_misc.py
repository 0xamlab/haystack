"""Tests for test_auto_planner_join_path_scoring: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-1/tests/test_auto_planner_join_path_scoring.py during modularization.
"""
from __future__ import annotations

from tests._test_auto_planner_join_path_scoring_helpers import *  # noqa: F401,F403


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


