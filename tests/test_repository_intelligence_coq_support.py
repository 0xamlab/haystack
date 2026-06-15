from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_intelligence_adapters import (
    coq_analysis_support as repository_coq_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    coq_primitives as repository_coq_primitives,
)


def test_coq_adapter_probable_source_skips_comment_stripping_without_raw_coq_markers(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        repository_coq_primitives,
        "strip_comments",
        lambda _text: (_ for _ in ()).throw(
            AssertionError("raw Coq marker fast path should skip comment stripping")
        ),
    )

    assert repository_coq_primitives.is_probable_coq_source(
        path=Path("src/main.v"),
        text="module main\n\nfn main() {\n    println('ok')\n}\n",
    ) is False


def test_coq_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_coq_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_coq_primitives,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_coq_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    source_text = (
        "From Foo Require Import Bar.\n\n"
        "Lemma helper : True.\n"
        "Proof.\n"
        "  exact I.\n"
        "Qed.\n"
    )
    module_index = {
        "Foo.Bar": "theories/Foo/Bar.v",
        "Bar": "theories/Foo/Bar.v",
    }

    repository_service.coq_adapter.parse_dependencies_only(
        "theories/Main.v",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    assert strip_call_count["value"] == 1

    strip_call_count["value"] = 0
    repository_service.coq_adapter.parse_file(
        "theories/Main.v",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_coq_iter_symbol_entries_reuse_cached_stripped_text_entries() -> None:
    repository_coq_primitives._iter_symbol_entries_from_stripped_text.cache_clear()
    stripped_text = repository_coq_primitives.strip_comments(
        "Lemma helper : True.\n"
        "Proof.\n"
        "  exact I.\n"
        "Qed.\n"
    )

    first_result = repository_coq_primitives.iter_symbol_entries(
        "",
        stripped_text=stripped_text,
    )
    first_cache_info = (
        repository_coq_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )
    second_result = repository_coq_primitives.iter_symbol_entries(
        "",
        stripped_text=stripped_text,
    )
    second_cache_info = (
        repository_coq_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1
