from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_root_scoped_aliases as repository_root_scoped_aliases,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gleam_analysis_support as repository_gleam_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gleam_primitives as repository_gleam_primitives,
)


def test_gleam_adapter_module_aliases_include_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "gleam-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub type Helper {\n  Helper\n}\n\npub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    aliases = repository_service.gleam_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/helper.gleam",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/helper.gleam" in aliases
    assert "src/demo/helper" in aliases
    assert "src.demo.helper" in aliases
    assert "demo/helper" in aliases
    assert "demo.helper" in aliases
    assert "render_json" in aliases
    assert "Helper" in aliases
    assert "demo.helper.render_json" in aliases


def test_gleam_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "gleam-alias-inline-text-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    source_text = "pub type Helper {\n  Helper\n}\n\npub fn render_json() {\n  Nil\n}\n"
    file_path = repo_path / "src" / "demo" / "helper.gleam"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.gleam_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/helper.gleam",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_gleam_primitives.strip_comments(source_text),
    )

    assert "src/demo/helper.gleam" in aliases
    assert "demo.helper" in aliases
    assert "render_json" in aliases


def test_gleam_adapter_module_aliases_can_skip_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "gleam-module-only-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub type Helper {\n  Helper\n}\n\npub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    aliases = repository_service.gleam_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/helper.gleam",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "src/demo/helper.gleam" in aliases
    assert "demo.helper" in aliases
    assert "render_json" not in aliases
    assert "Helper" not in aliases
    assert "demo.helper.render_json" not in aliases


def test_gleam_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_gleam_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_gleam_primitives,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_gleam_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    source_text = (
        "import demo/helper.{Helper, render_json}\n\n"
        "pub fn main() {\n"
        "  render_json()\n"
        "  let _value = Helper\n"
        "}\n"
    )
    module_index = {
        "src/demo/helper.gleam": "src/demo/helper.gleam",
        "src/main.gleam": "src/main.gleam",
    }

    repository_service.gleam_adapter.parse_dependencies_only(
        "src/main.gleam",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.gleam_adapter.parse_file(
        "src/main.gleam",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_gleam_iter_symbol_entries_reuse_cached_stripped_text_entries() -> None:
    repository_gleam_primitives._iter_symbol_entries_from_stripped_text.cache_clear()
    stripped_text = repository_gleam_primitives.strip_comments(
        "pub type Helper {\n  Helper\n}\n\npub fn render_json() {\n  Nil\n}\n",
    )

    first_result = repository_gleam_primitives.iter_symbol_entries(
        "",
        stripped_text=stripped_text,
    )
    first_cache_info = (
        repository_gleam_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )
    second_result = repository_gleam_primitives.iter_symbol_entries(
        "",
        stripped_text=stripped_text,
    )
    second_cache_info = (
        repository_gleam_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_build_module_index_reuses_preloaded_text_for_gleam_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "gleam-module-index-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    source_file = repo_path / "src" / "demo" / "helper.gleam"
    source_file.write_text(
        "pub type Helper {\n  Helper\n}\n\npub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text
    read_count = {"value": 0}
    observed_include_symbol_aliases: list[bool | None] = []
    loaded_adapter = repository_root_scoped_aliases.gleam_adapter._load()
    original_module_aliases_for_path = loaded_adapter.module_aliases_for_path

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == source_file:
            read_count["value"] += 1
        return original_read_text(self, *args, **kwargs)

    def _recording_module_aliases_for_path(**kwargs) -> set[str]:
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original_module_aliases_for_path(**kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(
        loaded_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["src/demo/helper.gleam"],
        root_path=repo_path,
    )

    assert read_count["value"] == 1
    assert observed_include_symbol_aliases == [False]
    assert module_index["src/demo/helper.gleam"] == "src/demo/helper.gleam"
    assert module_index["demo.helper"] == "src/demo/helper.gleam"
    assert "render_json" not in module_index
    assert "demo.helper.render_json" not in module_index
