from __future__ import annotations

import pytest

from apps.api_server.services.repository_intelligence_runtime_language_support import (
    build_repository_runtime_language_support_report,
    repository_runtime_language_route_index,
)


def test_repository_runtime_language_support_report_matches_current_runtime_truth() -> None:
    report = build_repository_runtime_language_support_report()

    assert report.supported_language_count == 180
    assert report.registered_adapter_language_count == 149
    assert report.workflow_special_case_language_count == 31
    assert report.runtime_covered_language_count == 180
    assert report.registered_adapter_progress_percent == pytest.approx(82.78, abs=0.01)
    assert report.runtime_coverage_percent == 100.0
    assert report.missing_languages == ()


def test_repository_runtime_language_support_exposes_registered_and_special_case_routes() -> None:
    route_index = repository_runtime_language_route_index()

    assert route_index["elixir"].route_kind == "registered_adapter"
    assert route_index["elixir"].route_family == "scripting"
    assert route_index["elixir"].file_plane.raw_language_keys == ("ex",)

    assert route_index["visualbasic"].route_kind == "registered_adapter"
    assert route_index["visualbasic"].route_family == "native"
    assert route_index["visualbasic"].file_plane.raw_language_keys == ("vb",)

    assert route_index["python"].route_kind == "workflow_special_case"
    assert route_index["python"].route_family == "python_language"

    assert route_index["javascript"].route_kind == "workflow_special_case"
    assert route_index["javascript"].route_family == "js_like"

    assert route_index["go"].route_kind == "workflow_special_case"
    assert route_index["go"].route_family == "go_language"

    assert route_index["java"].route_kind == "workflow_special_case"
    assert route_index["java"].route_family == "jvm"

    assert route_index["c"].route_kind == "workflow_special_case"
    assert route_index["c"].route_family == "c_family"
