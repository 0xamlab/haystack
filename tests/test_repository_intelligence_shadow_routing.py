"""AR-OPT-5b: shadow routing — an observe-only tier classifier.

The classifier emits the tier it *would* pick (vs the tier actually requested) for
offline calibration; auto-routing is disabled by default and the planner never
changes its routing based on it.
"""
from __future__ import annotations

from apps.api_server.services import repository_intelligence_planner_generation as planner


def test_failing_tests_route_to_verified_agentic() -> None:
    decision = planner._shadow_routing_decision(
        signals={"failing_tests": ["tests/test_x.py::a"]},
        suspect_files=["a.py"],
        evidence_items=[],
        actual_requested_tier="provider_backed_chat",
    )
    assert decision["chosen_tier"] == "verified_agentic"
    assert decision["actual_requested_tier"] == "provider_backed_chat"
    assert decision["routing_enabled"] is False  # shadow only by default
    assert decision["estimated_tokens"] >= 500


def test_multi_file_blast_radius_routes_to_verified_agentic() -> None:
    decision = planner._shadow_routing_decision(
        signals={},
        suspect_files=["a.py", "b.py", "c.py"],
        evidence_items=[],
        actual_requested_tier="verified_agentic",
    )
    assert decision["chosen_tier"] == "verified_agentic"


def test_single_localized_diagnostic_routes_to_deterministic_local() -> None:
    decision = planner._shadow_routing_decision(
        signals={"diagnostics": [{"path": "a.py", "line": 1}]},
        suspect_files=["a.py"],
        evidence_items=[],
        actual_requested_tier="deterministic_local",
    )
    assert decision["chosen_tier"] == "deterministic_local"


def test_small_localized_change_routes_to_provider_chat() -> None:
    decision = planner._shadow_routing_decision(
        signals={"diagnostics": [{}], "changed_files": ["a.py"]},
        suspect_files=["a.py", "b.py"],
        evidence_items=[],
        actual_requested_tier="provider_backed_chat",
    )
    assert decision["chosen_tier"] == "provider_backed_chat"


def test_auto_routing_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_REPOSITORIES_AUTO_ROUTING_ENABLED", raising=False)
    assert planner._auto_routing_enabled() is False
    monkeypatch.setenv("ALGENTA_REPOSITORIES_AUTO_ROUTING_ENABLED", "true")
    assert planner._auto_routing_enabled() is True
    monkeypatch.setenv("ALGENTA_REPOSITORIES_AUTO_ROUTING_ENABLED", "false")
    assert planner._auto_routing_enabled() is False
