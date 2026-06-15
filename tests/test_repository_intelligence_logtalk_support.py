from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_intelligence_adapters import (
    logtalk_analysis_support as repository_logtalk_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    logtalk_primitives as repository_logtalk_primitives,
)


def test_logtalk_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "logtalk-inline-text-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        ":- object(main).\n"
        "    :- public(run/0).\n"
        "    run :- helper::answer(_).\n"
        ":- end_object.\n"
    )
    file_path = repo_path / "src" / "main.lgt"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    stripped_text = repository_logtalk_primitives.strip_comments(source_text)
    symbol_entries = repository_logtalk_analysis_support._collect_symbol_entries(
        file_path="src/main.lgt",
        text=source_text,
        stable_identifier=repository_service._stable_identifier,
        stripped_text=stripped_text,
    )
    aliases = repository_service.logtalk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.lgt",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=stripped_text,
        symbol_entries=symbol_entries,
    )

    assert "src/main.lgt" in aliases
    assert "src/main" in aliases
    assert "main" in aliases
    assert "run" in aliases


def test_logtalk_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_logtalk_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_logtalk_primitives,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_logtalk_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    source_text = (
        ":- object(main).\n"
        "    :- uses(helper).\n"
        "    :- public(run/0).\n"
        "    run :- helper::answer(_).\n"
        ":- end_object.\n"
    )
    module_index = {
        "src/main.lgt": "src/main.lgt",
        "src/helper.lgt": "src/helper.lgt",
        "helper": "src/helper.lgt",
    }

    repository_service.logtalk_adapter.parse_dependencies_only(
        "src/main.lgt",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.logtalk_adapter.parse_file(
        "src/main.lgt",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_logtalk_adapter_parse_file_resolves_imports_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "logtalk-parse-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.lgt").write_text(
        ":- object(helper).\n"
        "    :- public(answer/1).\n"
        "    answer(42).\n"
        ":- end_object.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.lgt").write_text(
        ":- object(main).\n"
        "    :- uses(helper).\n"
        "    :- public(run/0).\n"
        "    run :- helper::answer(_).\n"
        ":- end_object.\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/main.lgt", "src/helper.lgt"],
        root_path=repo_path,
    )
    text = (repo_path / "src" / "main.lgt").read_text(encoding="utf-8")

    dependencies = repository_service.logtalk_adapter.parse_dependencies_only(
        "src/main.lgt",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, parsed_dependencies, references = repository_service.logtalk_adapter.parse_file(
        "src/main.lgt",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "main" for symbol in symbols)
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        dependency.target_file == "src/helper.lgt"
        and dependency.dependency_type == "references"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "src/helper.lgt"
        and dependency.dependency_type == "references"
        for dependency in parsed_dependencies
    )
    assert any(
        reference.target_file == "src/helper.lgt" and "answer" in reference.target_names
        for reference in references
    )
