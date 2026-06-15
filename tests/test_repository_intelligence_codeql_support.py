from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_codeql_parser_dispatch as repository_intelligence_codeql_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    codeql_analysis_support as repository_codeql_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    codeql_primitives as repository_codeql_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_codeql_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["codeql"] is (
        repository_intelligence_codeql_parser_dispatch._parse_codeql_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["codeql"] is (
        repository_intelligence_codeql_parser_dispatch._parse_codeql_dependencies_only
    )


def test_repository_intelligence_codeql_helpers_are_modularized() -> None:
    assert repository_service.codeql_adapter.strip_comments is (
        repository_codeql_primitives.strip_comments
    )
    assert repository_service.codeql_adapter.has_codeql_path_hints is (
        repository_codeql_primitives.has_codeql_path_hints
    )
    assert repository_service.codeql_adapter.is_probable_codeql_source is (
        repository_codeql_analysis_support.is_probable_codeql_source
    )
    assert repository_service.codeql_adapter.is_probable_codeql_config is (
        repository_codeql_analysis_support.is_probable_codeql_config
    )
    assert repository_service.codeql_adapter.module_aliases_for_path is (
        repository_codeql_analysis_support.module_aliases_for_path
    )
    assert repository_service.codeql_adapter.parse_dependencies_only is (
        repository_codeql_analysis_support.parse_dependencies_only
    )
    assert repository_service.codeql_adapter.parse_file is (
        repository_codeql_analysis_support.parse_file
    )


def test_codeql_adapter_module_aliases_include_trimmed_module_and_declared_symbol(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "codeql-alias-repo"
    (repo_path / "ql" / "lib").mkdir(parents=True)
    (repo_path / "ql" / "lib" / "Helpers.qll").write_text(
        "module Helpers\npredicate helperPredicate() { any() }\n",
        encoding="utf-8",
    )

    aliases = repository_service.codeql_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="ql/lib/Helpers.qll",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "ql/lib/Helpers.qll" in aliases
    assert "Helpers" in aliases
    assert "helperPredicate" in aliases


def test_codeql_adapter_parse_file_resolves_imports_and_qualified_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "codeql-parse-repo"
    (repo_path / "ql" / "lib").mkdir(parents=True)
    (repo_path / "ql" / "src").mkdir(parents=True)
    (repo_path / "ql" / "lib" / "Helpers.qll").write_text(
        "module Helpers\npredicate helperPredicate() { any() }\n",
        encoding="utf-8",
    )
    (repo_path / "ql" / "src" / "main.ql").write_text(
        "import Helpers\n"
        "query MainQuery {\n"
        "  Helpers.helperPredicate()\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["ql/lib/Helpers.qll", "ql/src/main.ql"],
        root_path=repo_path,
    )
    text = (repo_path / "ql" / "src" / "main.ql").read_text(encoding="utf-8")

    dependencies = repository_service.codeql_adapter.parse_dependencies_only(
        "ql/src/main.ql",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.codeql_adapter.parse_file(
        "ql/src/main.ql",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "ql/lib/Helpers.qll" for dependency in dependencies)
    assert any(symbol.symbol_name == "MainQuery" for symbol in symbols)
    assert any(
        reference.target_file == "ql/lib/Helpers.qll"
        and reference.target_names == ("helperPredicate",)
        for reference in references
    )


def test_codeql_language_detection_supports_query_and_pack_files_without_overclaiming() -> None:
    assert ".ql" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("ql/src/query.ql"),
        text="import Helpers\nquery MainQuery {\n  Helpers.helperPredicate()\n}\n",
    ) == "codeql"
    assert repository_service._language_for_path(
        Path("qlpack.yml"),
        text="name: demo/codeql-pack\nversion: 0.0.1\n",
    ) == "codeql"
    assert (
        repository_service._language_for_path(
            Path("ql/src/query.ql"),
            text="plain text without query syntax\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_codeql_when_query_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "codeql-profile-repo"
    (repo_path / "ql" / "lib").mkdir(parents=True)
    (repo_path / "ql" / "src").mkdir(parents=True)
    (repo_path / "qlpack.yml").write_text(
        "name: demo/codeql-pack\nversion: 0.0.1\n",
        encoding="utf-8",
    )
    (repo_path / "ql" / "lib" / "Helpers.qll").write_text(
        "module Helpers\npredicate helperPredicate() { any() }\n",
        encoding="utf-8",
    )
    (repo_path / "ql" / "src" / "main.ql").write_text(
        "import Helpers\nquery MainQuery {\n  Helpers.helperPredicate()\n}\n",
        encoding="utf-8",
    )
    (repo_path / "ql" / "src" / "security.ql").write_text(
        "import Helpers\nquery SecurityQuery {\n  Helpers.helperPredicate()\n}\n",
        encoding="utf-8",
    )
    (repo_path / "src").mkdir()
    (repo_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=64,
    )

    assert "codeql" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "codeql"
    assert "ql/src/main.ql" in seed_plan["entrypoint_files"]
    assert "qlpack.yml" in seed_plan["config_paths"]
