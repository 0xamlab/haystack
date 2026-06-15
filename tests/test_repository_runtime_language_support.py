from __future__ import annotations

import pytest

from apps.api_server.services.repository_intelligence_runtime_language_support import (
    build_repository_runtime_language_support_report,
    repository_runtime_language_route_index,
)
from apps.api_server.services.repository_language_priority import supported_repository_languages


def test_repository_runtime_language_support_report_matches_current_runtime_truth() -> None:
    report = build_repository_runtime_language_support_report()
    expected_supported_count = len(supported_repository_languages())
    expected_registered_count = len(report.registered_adapter_languages)
    expected_special_case_count = len(report.workflow_special_case_languages)

    assert report.supported_language_count == expected_supported_count
    assert report.registered_adapter_language_count == expected_registered_count
    assert report.workflow_special_case_language_count == expected_special_case_count
    assert report.runtime_covered_language_count == expected_supported_count
    assert report.registered_adapter_progress_percent == pytest.approx(
        round((expected_registered_count / expected_supported_count) * 100.0, 2),
        abs=0.01,
    )
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

    assert route_index["4d"].route_kind == "registered_adapter"
    assert route_index["4d"].route_family == "four_d"
    assert route_index["4d"].file_plane.raw_language_keys == ("4d",)

    assert route_index["ballerina"].route_kind == "registered_adapter"
    assert route_index["ballerina"].route_family == "ballerina"
    assert route_index["ballerina"].file_plane.raw_language_keys == ("ballerina",)

    assert route_index["bqn"].route_kind == "registered_adapter"
    assert route_index["bqn"].route_family == "bqn"
    assert route_index["bqn"].file_plane.raw_language_keys == ("bqn",)

    assert route_index["circom"].route_kind == "registered_adapter"
    assert route_index["circom"].route_family == "circom"
    assert route_index["circom"].file_plane.raw_language_keys == ("circom",)

    assert route_index["dafny"].route_kind == "registered_adapter"
    assert route_index["dafny"].route_family == "dafny"
    assert route_index["dafny"].file_plane.raw_language_keys == ("dafny",)

    assert route_index["rebol"].route_kind == "registered_adapter"
    assert route_index["rebol"].route_family == "rebol"
    assert route_index["rebol"].file_plane.raw_language_keys == ("rebol",)

    assert route_index["ampl"].route_kind == "registered_adapter"
    assert route_index["ampl"].route_family == "ampl"
    assert route_index["ampl"].file_plane.raw_language_keys == ("ampl",)

    assert route_index["openedge"].route_kind == "registered_adapter"
    assert route_index["openedge"].route_family == "openedge"
    assert route_index["openedge"].file_plane.raw_language_keys == ("openedge",)

    assert route_index["metal"].route_kind == "registered_adapter"
    assert route_index["metal"].route_family == "metal"
    assert route_index["metal"].file_plane.raw_language_keys == ("metal",)

    assert route_index["nsis"].route_kind == "registered_adapter"
    assert route_index["nsis"].route_family == "nsis"
    assert route_index["nsis"].file_plane.raw_language_keys == ("nsis",)

    assert route_index["python"].route_kind == "workflow_special_case"
    assert route_index["python"].route_family == "python_language"

    assert route_index["javascript"].route_kind == "workflow_special_case"
    assert route_index["javascript"].route_family == "js_like"

    assert route_index["go"].route_kind == "workflow_special_case"
    assert route_index["go"].route_family == "go_language"

    assert route_index["java"].route_kind == "workflow_special_case"
    assert route_index["java"].route_family == "jvm"

    assert route_index["processing"].route_kind == "workflow_special_case"
    assert route_index["processing"].route_family == "jvm"

    assert route_index["c"].route_kind == "workflow_special_case"
    assert route_index["c"].route_family == "c_family"
