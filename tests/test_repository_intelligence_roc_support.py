from __future__ import annotations

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services.repository_intelligence_adapters import (
    roc_analysis_support as repository_roc_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    roc_primitives as repository_roc_primitives,
)


def test_roc_adapter_parse_dependencies_only_reuses_single_stripped_text(
    monkeypatch,
) -> None:
    original_strip_comments = repository_roc_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_roc_primitives,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_roc_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    source_text = (
        "import Util exposing [helper]\n\n"
        "main =\n"
        "    helper\n"
    )
    module_index = {
        "src/Main.roc": "src/Main.roc",
        "src/Util.roc": "src/Util.roc",
        "src.Util": "src/Util.roc",
        "Util.roc": "src/Util.roc",
        "Util": "src/Util.roc",
    }

    repository_service.roc_adapter.parse_dependencies_only(
        "src/Main.roc",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 1


def test_roc_adapter_parse_file_reuses_single_stripped_text(
    monkeypatch,
) -> None:
    original_strip_comments = repository_roc_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_roc_primitives,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_roc_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    source_text = (
        "import Util exposing [helper]\n\n"
        "main =\n"
        "    Util.helper\n"
    )
    module_index = {
        "src/Main.roc": "src/Main.roc",
        "src/Util.roc": "src/Util.roc",
        "src.Util": "src/Util.roc",
        "Util.roc": "src/Util.roc",
        "Util": "src/Util.roc",
    }

    repository_service.roc_adapter.parse_file(
        "src/Main.roc",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 1
