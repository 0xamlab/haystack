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
    fsharp as repository_fsharp_adapter,
)


def test_fsharp_adapter_module_aliases_include_namespace_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fsharp-alias-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    source_text = (
        "namespace Demo.Tools\n\n"
        "module Helper =\n"
        "    let renderJson value = value\n"
    )
    (repo_path / "src" / "Demo" / "Helper.fs").write_text(source_text, encoding="utf-8")

    aliases = repository_service.fsharp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Demo/Helper.fs",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )

    assert "Demo.Helper" in aliases
    assert "Demo.Tools" in aliases
    assert "Demo.Tools.Helper" in aliases
    assert "Demo.Tools.Helper.renderJson" in aliases


def test_fsharp_adapter_module_aliases_can_skip_symbol_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "fsharp-module-only-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    source_text = (
        "namespace Demo.Tools\n\n"
        "module Helper =\n"
        "    let renderJson value = value\n"
    )
    (repo_path / "src" / "Demo" / "Helper.fs").write_text(source_text, encoding="utf-8")

    def _unexpected_collect_symbol_entries(*args: object, **kwargs: object) -> object:
        raise AssertionError("module-only fsharp aliases should skip symbol collection")

    monkeypatch.setattr(
        repository_fsharp_adapter,
        "collect_symbol_entries",
        _unexpected_collect_symbol_entries,
    )

    aliases = repository_service.fsharp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Demo/Helper.fs",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        include_symbol_aliases=False,
    )

    assert "Demo.Helper" in aliases
    assert "Demo.Tools" in aliases
    assert "Demo.Tools.Helper" in aliases
    assert "Demo.Tools.Helper.renderJson" not in aliases


def test_build_module_index_reuses_preloaded_text_for_fsharp_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "fsharp-module-index-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    source_file = repo_path / "src" / "Demo" / "Helper.fs"
    source_text = (
        "namespace Demo.Tools\n\n"
        "module Helper =\n"
        "    let renderJson value = value\n"
    )
    source_file.write_text(source_text, encoding="utf-8")

    original_read_text = Path.read_text
    read_count = {"value": 0}
    observed_texts: list[str | None] = []
    observed_include_symbol_aliases: list[bool | None] = []
    loaded_adapter = repository_root_scoped_aliases.fsharp_adapter._load()
    original_module_aliases_for_path = loaded_adapter.module_aliases_for_path

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == source_file:
            read_count["value"] += 1
        return original_read_text(self, *args, **kwargs)

    def _recording_module_aliases_for_path(**kwargs) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original_module_aliases_for_path(**kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(
        loaded_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["src/Demo/Helper.fs"],
        root_path=repo_path,
    )

    assert read_count["value"] == 1
    assert observed_texts == [source_text]
    # The preloaded-text reuse is the speed optimization under test (one read, text
    # threaded into the adapter). Symbol-level aliases must still be built, though:
    # F# resolves qualified member references through the module index, so the index
    # has to carry the module-member aliases or the references_symbol graph edges drop.
    assert observed_include_symbol_aliases == [True]
    assert module_index["Demo.Tools"] == "src/Demo/Helper.fs"
    assert module_index["Demo.Tools.Helper"] == "src/Demo/Helper.fs"
    assert module_index["Demo.Tools.Helper.renderJson"] == "src/Demo/Helper.fs"
