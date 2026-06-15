from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_intelligence_adapters import (
    yara_analysis_support as repository_yara_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    yara_primitives as repository_yara_primitives,
)


def test_repository_intelligence_yara_helpers_are_modularized() -> None:
    assert repository_service.yara_adapter.strip_comments is (
        repository_yara_primitives.strip_comments
    )
    assert repository_service.yara_adapter.has_yara_path_hints is (
        repository_yara_primitives.has_yara_path_hints
    )
    assert repository_service.yara_adapter.is_probable_yara_source is (
        repository_yara_primitives.is_probable_yara_source
    )
    assert repository_service.yara_adapter.parse_include_statements is (
        repository_yara_primitives.parse_include_statements
    )
    assert repository_service.yara_adapter.module_aliases_for_path is (
        repository_yara_analysis_support.module_aliases_for_path
    )
    assert repository_service.yara_adapter.resolve_include is (
        repository_yara_analysis_support.resolve_include
    )
    assert repository_service.yara_adapter.parse_dependencies_only is (
        repository_yara_analysis_support.parse_dependencies_only
    )
    assert repository_service.yara_adapter.parse_file is (
        repository_yara_analysis_support.parse_file
    )


def test_yara_adapter_module_aliases_include_rule_names_with_single_strip_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "yara-alias-repo"
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "rules" / "helper.yar").write_text(
        "// banner comment\n"
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    call_count = 0
    original_strip_comments = repository_yara_analysis_support.strip_comments

    def counting_strip_comments(text: str) -> str:
        nonlocal call_count
        call_count += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_yara_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    aliases = repository_service.yara_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rules/helper.yar",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rules/helper.yar" in aliases
    assert "rules/helper" in aliases
    assert "helper_rule" in aliases
    assert call_count == 1


def test_yara_adapter_parse_file_extracts_dependencies_and_local_references_with_single_strip_pass(
    monkeypatch,
) -> None:
    module_index = repository_service._build_module_index(
        ["rules/helper.yar", "rules/main.yar"],
        root_path=Path("/tmp/yara-index"),
    )
    text = (
        'include "helper.yar"\n'
        'import "pe"\n'
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n"
        "rule main_rule {\n"
        "  condition:\n"
        "    helper_rule and pe.entry_point >= 0\n"
        "}\n"
    )

    call_count = 0
    original_strip_comments = repository_yara_analysis_support.strip_comments

    def counting_strip_comments(source_text: str) -> str:
        nonlocal call_count
        call_count += 1
        return original_strip_comments(source_text)

    monkeypatch.setattr(
        repository_yara_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    symbols, dependencies, references = repository_service.yara_adapter.parse_file(
        "rules/main.yar",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "helper_rule" for symbol in symbols)
    assert any(symbol.symbol_name == "main_rule" for symbol in symbols)
    assert any(
        dependency.dependency_type == "includes"
        and dependency.target_file == "rules/helper.yar"
        for dependency in dependencies
    )
    assert any(
        dependency.dependency_type == "imports" and dependency.target_symbol == "pe"
        for dependency in dependencies
    )
    assert any(
        reference.target_file == "rules/main.yar"
        and reference.target_names == ("helper_rule",)
        and reference.target_symbol_id is not None
        for reference in references
    )
    assert all(reference.target_names != ("pe",) for reference in references)
    assert call_count == 1
