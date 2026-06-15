from __future__ import annotations

import pytest

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_intelligence_adapters import (
    wolfram as repository_wolfram_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    wolfram_support as repository_wolfram_support,
)


def test_wolfram_strip_comments_reuses_cached_results() -> None:
    source_text = (
        'BeginPackage["Acme`"];\n'
        "(* comment block *)\n"
        "helper[] := 1;\n"
    )
    repository_wolfram_support._strip_comments_cached.cache_clear()

    first_result = repository_wolfram_support.strip_comments(source_text)
    first_cache_info = repository_wolfram_support._strip_comments_cached.cache_info()
    second_result = repository_wolfram_support.strip_comments(source_text)
    second_cache_info = repository_wolfram_support._strip_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_wolfram_declared_symbol_extraction_reuses_cached_results() -> None:
    source_text = (
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        'Begin["`Private`"];\n'
        "helper[] := 1;\n"
        "End[];\n"
        "EndPackage[];\n"
    )
    stripped_text = repository_wolfram_support.strip_comments(source_text)
    repository_wolfram_support._extract_declared_symbols.cache_clear()

    first_symbols = repository_wolfram_support._extract_declared_symbols(
        stripped_text,
        current_package="Acme`",
    )
    first_cache_info = repository_wolfram_support._extract_declared_symbols.cache_info()
    second_symbols = repository_wolfram_support._extract_declared_symbols(
        stripped_text,
        current_package="Acme`",
    )
    second_cache_info = repository_wolfram_support._extract_declared_symbols.cache_info()

    assert first_symbols == second_symbols
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_wolfram_declared_symbol_alias_extraction_matches_full_symbol_names() -> None:
    source_text = (
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        'Begin["`Private`"];\n'
        "helper[] := 1;\n"
        "helperValue = helper[];\n"
        "End[];\n"
        "EndPackage[];\n"
    )
    stripped_text = repository_wolfram_support.strip_comments(source_text)

    full_symbols = repository_wolfram_support._extract_declared_symbols(
        stripped_text,
        current_package="Acme`",
    )
    alias_entries = repository_wolfram_support._extract_declared_symbol_aliases(
        stripped_text,
        current_package="Acme`",
    )

    assert alias_entries == tuple(
        (
            str(entry["symbol_name"]),
            str(entry["qualified_name"]),
        )
        for entry in full_symbols
    )


def test_wolfram_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_wolfram_support.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_wolfram_support,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_wolfram_adapter,
        "strip_comments",
        counting_strip_comments,
    )

    source_text = (
        'BeginPackage["Acme`", {"Acme`Helpers`"}];\n'
        'run::usage = "run";\n'
        'Begin["`Private`"];\n'
        "run[] := helper[];\n"
        "End[];\n"
        "EndPackage[];\n"
    )
    module_index = {
        "Kernel/Main.wl": "Kernel/Main.wl",
        "Acme`Helpers`": "Kernel/Helpers.wl",
        "Acme`Helpers": "Kernel/Helpers.wl",
        "Acme`Helpers`helper": "Kernel/Helpers.wl",
    }

    repository_service.wolfram_adapter.parse_dependencies_only(
        "Kernel/Main.wl",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.wolfram_adapter.parse_file(
        "Kernel/Main.wl",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_wolfram_adapter_parse_file_extracts_import_dependencies_and_references() -> None:
    module_index = {
        "Kernel/Main.wl": "Kernel/Main.wl",
        "Acme`Helpers`": "Kernel/Helpers.wl",
        "Acme`Helpers": "Kernel/Helpers.wl",
        "Acme`Helpers`helper": "Kernel/Helpers.wl",
    }
    source_text = (
        'BeginPackage["Acme`", {"Acme`Helpers`"}];\n'
        'run::usage = "run";\n'
        'Begin["`Private`"];\n'
        "run[] := helper[];\n"
        "End[];\n"
        "EndPackage[];\n"
    )

    symbols, dependencies, references = repository_service.wolfram_adapter.parse_file(
        "Kernel/Main.wl",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "Kernel/Helpers.wl" for dependency in dependencies)
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(reference.target_file == "Kernel/Helpers.wl" for reference in references)
