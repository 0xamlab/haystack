from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services.repository_intelligence_adapters import (
    purescript_analysis_support as repository_purescript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    purescript_primitives as repository_purescript_primitives,
)


def test_purescript_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-alias-repo"
    (repo_path / "src" / "Control").mkdir(parents=True)
    (repo_path / "src" / "Control" / "Helper.purs").write_text(
        "module Control.Helper where\n\n"
        "renderJson :: String\n"
        "renderJson = helper\n\n"
        "helper :: String\n"
        "helper = \"ok\"\n",
        encoding="utf-8",
    )

    aliases = repository_service.purescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Control/Helper.purs",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Control/Helper.purs" in aliases
    assert "src/Control/Helper" in aliases
    assert "src.Control.Helper" in aliases
    assert "Helper" in aliases
    assert "Control.Helper" in aliases
    assert "renderJson" in aliases
    assert "helper" in aliases
    assert "Control.Helper.renderJson" in aliases


def test_purescript_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "purescript-inline-text-repo"
    (repo_path / "src" / "Control").mkdir(parents=True)
    source_text = (
        "module Control.Helper where\n\n"
        "renderJson :: String\n"
        "renderJson = helper\n\n"
        "helper :: String\n"
        "helper = \"ok\"\n"
    )
    file_path = repo_path / "src" / "Control" / "Helper.purs"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.purescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Control/Helper.purs",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_purescript_primitives.strip_comments(source_text),
    )

    assert "Control.Helper" in aliases
    assert "renderJson" in aliases
    assert "helper" in aliases


def test_purescript_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_purescript_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_purescript_primitives,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_purescript_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    source_text = (
        "module Main where\n\n"
        "import Control.Helper (helper)\n\n"
        "main :: String\n"
        "main = helper\n"
    )
    module_index = {
        "Main": "src/Main.purs",
        "Control.Helper": "src/Control/Helper.purs",
        "src/Control/Helper.purs": "src/Control/Helper.purs",
    }

    repository_service.purescript_adapter.parse_dependencies_only(
        "src/Main.purs",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.purescript_adapter.parse_file(
        "src/Main.purs",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_purescript_iter_symbol_entries_reuse_cached_stripped_text_entries() -> None:
    repository_purescript_primitives._iter_symbol_entries_from_stripped_text.cache_clear()
    stripped_text = repository_purescript_primitives.strip_comments(
        "module Control.Helper where\n\n"
        "renderJson :: String\n"
        "renderJson = helper\n\n"
        "helper :: String\n"
        "helper = \"ok\"\n"
    )

    first_result = repository_purescript_primitives.iter_symbol_entries(
        "",
        stripped_text=stripped_text,
    )
    first_cache_info = (
        repository_purescript_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )
    second_result = repository_purescript_primitives.iter_symbol_entries(
        "",
        stripped_text=stripped_text,
    )
    second_cache_info = (
        repository_purescript_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_purescript_adapter_parse_file_extracts_import_dependencies_and_references() -> None:
    module_index = {
        "Main": "src/Main.purs",
        "Control.Helper": "src/Control/Helper.purs",
        "src/Control/Helper.purs": "src/Control/Helper.purs",
    }
    source_text = (
        "module Main where\n\n"
        "import Control.Helper (helper)\n\n"
        "main :: String\n"
        "main = helper\n"
    )

    symbols, dependencies, references = repository_service.purescript_adapter.parse_file(
        "src/Main.purs",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "src/Control/Helper.purs" for dependency in dependencies)
    assert any(symbol.symbol_name == "main" for symbol in symbols)
    assert any(reference.target_file == "src/Control/Helper.purs" for reference in references)
