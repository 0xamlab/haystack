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
    odin_analysis_support as repository_odin_analysis_support,
)


def test_odin_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-alias-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    source_text = (
        "package common\n"
        "\n"
        "Config :: struct {\n"
        "    value: int,\n"
        "}\n"
        "\n"
        "helper :: proc() -> int {\n"
        "    return 1\n"
        "}\n"
    )
    (repo_path / "src" / "common" / "helper.odin").write_text(source_text, encoding="utf-8")

    aliases = repository_service.odin_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/common/helper.odin",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )

    assert "src/common/helper.odin" in aliases
    assert "src/common/helper" in aliases
    assert "helper" in aliases
    assert "src:common" in aliases
    assert "common" in aliases
    assert "common.Config" in aliases
    assert "common.helper" in aliases


def test_odin_adapter_module_aliases_can_skip_symbol_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "odin-module-only-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    source_text = (
        "package common\n"
        "\n"
        "Config :: struct {\n"
        "    value: int,\n"
        "}\n"
        "\n"
        "helper :: proc() -> int {\n"
        "    return 1\n"
        "}\n"
    )
    (repo_path / "src" / "common" / "helper.odin").write_text(source_text, encoding="utf-8")

    def _unexpected_collect_symbols(*args: object, **kwargs: object) -> object:
        raise AssertionError("module-only odin aliases should skip symbol collection")

    monkeypatch.setattr(
        repository_odin_analysis_support,
        "_collect_symbols",
        _unexpected_collect_symbols,
    )

    aliases = repository_service.odin_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/common/helper.odin",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        include_symbol_aliases=False,
    )

    assert "src/common/helper.odin" in aliases
    assert "src/common/helper" in aliases
    assert "helper" in aliases
    assert "src:common" in aliases
    assert "common" in aliases
    assert "common.Config" not in aliases
    assert "common.helper" not in aliases


def test_build_module_index_reuses_preloaded_text_for_odin_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "odin-module-index-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    source_file = repo_path / "src" / "common" / "helper.odin"
    source_text = (
        "package common\n"
        "\n"
        "Config :: struct {\n"
        "    value: int,\n"
        "}\n"
        "\n"
        "helper :: proc() -> int {\n"
        "    return 1\n"
        "}\n"
    )
    source_file.write_text(source_text, encoding="utf-8")

    original_read_text = Path.read_text
    read_count = {"value": 0}
    observed_texts: list[str | None] = []
    observed_include_symbol_aliases: list[bool | None] = []
    loaded_adapter = repository_root_scoped_aliases.odin_adapter._load()
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
        ["src/common/helper.odin"],
        root_path=repo_path,
    )

    assert read_count["value"] == 1
    assert observed_texts == [source_text]
    assert observed_include_symbol_aliases == [False]
    assert module_index["src/common/helper.odin"] == "src/common/helper.odin"
    assert module_index["src:common"] == "src/common/helper.odin"
    assert module_index["common"] == "src/common/helper.odin"
    assert "common.Config" not in module_index
    assert "common.helper" not in module_index
