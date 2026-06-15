"""Tests for repository_intelligence_service: parse.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import c_family as repository_c_family_adapter

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_parse_c_family_file_skips_attribute_noise_symbols() -> None:
    symbols, dependencies, symbol_references = repository_service._parse_c_family_file(
        "src/net.c",
        "__attribute__((unused)) static int helper(void);\n"
        "int run(void) {\n"
        "    va_end(args);\n"
        "    return helper();\n"
        "}\n",
        {},
    )

    symbol_names = {symbol.symbol_name for symbol in symbols}
    assert "__attribute__" not in symbol_names
    assert "helper" in symbol_names
    assert "run" in symbol_names
    assert dependencies == ()
    assert all("va_end" not in candidate.target_names for candidate in symbol_references)


def test_c_family_sanitize_text_reuses_cached_result() -> None:
    source_text = (
        "__attribute__((unused)) static int helper(void);\n"
        "int run(void) {\n"
        "    return helper(); // trailing comment\n"
        "}\n"
    )

    repository_c_family_adapter._strip_comments_cached.cache_clear()
    repository_c_family_adapter._strip_attributes_cached.cache_clear()
    repository_c_family_adapter._sanitize_text_cached.cache_clear()

    first = repository_c_family_adapter.sanitize_text(source_text)
    first_cache = repository_c_family_adapter._sanitize_text_cached.cache_info()
    second = repository_c_family_adapter.sanitize_text(source_text)
    second_cache = repository_c_family_adapter._sanitize_text_cached.cache_info()

    assert first == second
    assert "__attribute__" not in first
    assert "trailing comment" not in first
    assert first_cache.hits == 0
    assert second_cache.hits >= 1


def test_c_family_parse_file_preserves_line_numbers_without_repeated_newline_scans() -> None:
    symbols, _, _ = repository_c_family_adapter.parse_file(
        "src/main.cpp",
        "class Widget {};\n"
        "int helper() {\n"
        "    return 1;\n"
        "}\n"
        "int run() {\n"
        "    return helper();\n"
        "}\n",
        {},
        stable_identifier=repository_service._stable_identifier,
        resolve_include=lambda **_kwargs: None,
    )

    assert {(symbol.symbol_name, symbol.start_line) for symbol in symbols} == {
        ("Widget", 1),
        ("helper", 2),
        ("run", 5),
    }


def test_c_family_parse_file_materializes_unique_reference_ids_once() -> None:
    stable_identifier_calls: list[tuple[str, Any]] = []

    def stable_identifier(prefix: str, payload: Any) -> str:
        stable_identifier_calls.append((prefix, payload))
        return repository_service._stable_identifier(prefix, payload)

    _, _, references = repository_c_family_adapter.parse_file(
        "src/main.cpp",
        '#include "dep.hpp"\n'
        "int helper() { return 1; }\n"
        "int run() {\n"
        "    helper();\n"
        "    helper();\n"
        "    dep_call();\n"
        "    dep_call();\n"
        "    return 0;\n"
        "}\n",
        {"dep.hpp": "include/dep.hpp"},
        stable_identifier=stable_identifier,
        resolve_include=(
            lambda **kwargs: "include/dep.hpp"
            if kwargs.get("import_target") == "dep.hpp"
            else None
        ),
    )

    reference_identifier_calls = [payload for prefix, payload in stable_identifier_calls if prefix == "ref"]

    assert len(reference_identifier_calls) == len(references)
    assert {
        (reference.target_file, reference.target_symbol_id, reference.target_names)
        for reference in references
    } == {
        ("include/dep.hpp", None, ("dep_call",)),
        ("include/dep.hpp", None, ("helper",)),
        ("include/dep.hpp", None, ("run",)),
    }


def test_parse_clojure_dependencies_only_follows_refer_edges() -> None:
    dependencies = repository_service._parse_clojure_dependencies_only(
        "src/acme/core.clj",
        "(ns acme.core\n"
        "  (:require [acme.util :refer [helper]]))\n"
        "(defn run []\n"
        "  (helper))\n",
        {"acme.util": "src/acme/util.clj"},
    )

    assert any(
        dependency.dependency_type == "references"
        and dependency.target_file == "src/acme/util.clj"
        and dependency.target_symbol == "helper"
        for dependency in dependencies
    )


def test_parse_shell_dependencies_only_follows_source_and_filters_builtins() -> None:
    dependencies = repository_service._parse_shell_dependencies_only(
        "scripts/main.sh",
        '. ../lib/util.zsh\n'
        "run() {\n"
        "  helper\n"
        "  printf '%s\\n' ok\n"
        "}\n",
        {
            "lib/util.zsh": "lib/util.zsh",
            "lib/util": "lib/util.zsh",
        },
    )

    assert any(
        dependency.dependency_type == "imports"
        and dependency.target_file == "lib/util.zsh"
        for dependency in dependencies
    )
    assert any(
        dependency.dependency_type == "references"
        and dependency.target_file == "lib/util.zsh"
        and dependency.target_symbol == "helper"
        for dependency in dependencies
    )
    assert not any(
        dependency.dependency_type == "references"
        and dependency.target_symbol == "printf"
        for dependency in dependencies
    )


def test_parse_powershell_dependencies_only_follows_imports_and_filters_builtins() -> None:
    dependencies = repository_service._parse_powershell_dependencies_only(
        "Public/Main.ps1",
        'Import-Module "$PSScriptRoot/../Private/Helpers.ps1"\n'
        "function Invoke-Main {\n"
        "  Get-Helper\n"
        "  Write-Verbose 'ok'\n"
        "}\n",
        {
            "Private/Helpers.ps1": "Private/Helpers.ps1",
            "Private/Helpers": "Private/Helpers.ps1",
        },
    )

    assert any(
        dependency.dependency_type == "imports"
        and dependency.target_file == "Private/Helpers.ps1"
        for dependency in dependencies
    )
    assert any(
        dependency.dependency_type == "references"
        and dependency.target_file == "Private/Helpers.ps1"
        and dependency.target_symbol == "Get-Helper"
        for dependency in dependencies
    )
    assert not any(
        dependency.dependency_type == "references"
        and dependency.target_symbol == "Write-Verbose"
        for dependency in dependencies
    )


def test_parse_batchfile_dependencies_only_follows_calls_and_filters_local_labels(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "batchfile-parse-deps-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "scripts" / "build.bat").write_text(
        "@echo off\n"
        "call ..\\tools\\helper.cmd\n"
        "call :done\n"
        ":done\n"
        "exit /b 0\n",
        encoding="utf-8",
    )
    (repo_path / "tools" / "helper.cmd").write_text(
        "@echo off\n"
        "echo helper\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["scripts/build.bat", "tools/helper.cmd"],
        root_path=repo_path,
    )
    text = (repo_path / "scripts" / "build.bat").read_text(encoding="utf-8")

    dependencies = repository_batchfile_parser_dispatch._parse_batchfile_dependencies_only(
        "scripts/build.bat",
        text,
        module_index,
    )

    assert len(dependencies) == 1
    assert dependencies[0].target_file == "tools/helper.cmd"
    assert dependencies[0].target_symbol == "helper"


def test_parse_makefile_dependencies_only_follows_include_directives(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "makefile-parse-deps-repo"
    (repo_path / "mk").mkdir(parents=True)
    (repo_path / "Makefile").write_text(
        "include mk/common.mk\n"
        "build:\n"
        "\t@echo build\n",
        encoding="utf-8",
    )
    (repo_path / "mk" / "common.mk").write_text(
        "helper:\n"
        "\t@echo helper\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["Makefile", "mk/common.mk"],
        root_path=repo_path,
    )
    text = (repo_path / "Makefile").read_text(encoding="utf-8")

    dependencies = repository_makefile_parser_dispatch._parse_makefile_dependencies_only(
        "Makefile",
        text,
        module_index,
    )

    assert len(dependencies) == 1
    assert dependencies[0].target_file == "mk/common.mk"
    assert dependencies[0].target_symbol == "common"
