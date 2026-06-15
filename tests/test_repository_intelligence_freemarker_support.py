from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_freemarker_parser_dispatch as repository_freemarker_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    freemarker_analysis_support as repository_freemarker_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    freemarker_primitives as repository_freemarker_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_freemarker_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["freemarker"] is (
        repository_freemarker_parser_dispatch._parse_freemarker_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["freemarker"] is (
        repository_freemarker_parser_dispatch._parse_freemarker_dependencies_only
    )


def test_repository_intelligence_freemarker_helpers_are_modularized() -> None:
    assert repository_service.freemarker_adapter.strip_comments is (
        repository_freemarker_primitives.strip_comments
    )
    assert repository_service.freemarker_adapter.has_freemarker_path_hints is (
        repository_freemarker_primitives.has_freemarker_path_hints
    )
    assert repository_service.freemarker_adapter.iter_dependency_entries is (
        repository_freemarker_primitives.iter_dependency_entries
    )
    assert repository_service.freemarker_adapter.iter_reference_entries is (
        repository_freemarker_primitives.iter_reference_entries
    )
    assert repository_service.freemarker_adapter.iter_symbol_entries is (
        repository_freemarker_primitives.iter_symbol_entries
    )
    assert repository_service.freemarker_adapter.resolve_import is (
        repository_freemarker_primitives.resolve_import
    )
    assert repository_service.freemarker_adapter.is_probable_freemarker_source is (
        repository_freemarker_analysis_support.is_probable_freemarker_source
    )
    assert repository_service.freemarker_adapter.module_aliases_for_path is (
        repository_freemarker_analysis_support.module_aliases_for_path
    )
    assert repository_service.freemarker_adapter.parse_dependencies_only is (
        repository_freemarker_analysis_support.parse_dependencies_only
    )
    assert repository_service.freemarker_adapter.parse_file is (
        repository_freemarker_analysis_support.parse_file
    )


def test_freemarker_adapter_module_aliases_include_template_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "freemarker-alias-repo"
    (repo_path / "templates" / "macros").mkdir(parents=True)
    (repo_path / "templates" / "macros" / "common.ftl").write_text(
        "<#macro renderButton label><button>${label}</button></#macro>\n",
        encoding="utf-8",
    )

    aliases = repository_service.freemarker_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="templates/macros/common.ftl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "templates/macros/common.ftl" in aliases
    assert "macros.common" in aliases
    assert "renderButton" in aliases


def test_freemarker_adapter_parse_file_resolves_imports_includes_and_macro_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "freemarker-parse-repo"
    (repo_path / "templates" / "layout").mkdir(parents=True)
    (repo_path / "templates" / "macros").mkdir(parents=True)
    (repo_path / "templates" / "layout" / "base.ftl").write_text(
        "<#assign pageTitle = 'Demo'>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "macros" / "common.ftl").write_text(
        "<#macro renderButton label><button>${label}</button></#macro>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "index.ftl").write_text(
        '<#include "layout/base.ftl">\n'
        '<#import "macros/common.ftl" as common>\n'
        '<@common.renderButton label="Ship it" />\n',
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "templates/layout/base.ftl",
            "templates/macros/common.ftl",
            "templates/index.ftl",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "templates" / "index.ftl").read_text(encoding="utf-8")

    dependencies = repository_service.freemarker_adapter.parse_dependencies_only(
        "templates/index.ftl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.freemarker_adapter.parse_file(
        "templates/index.ftl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "templates/layout/base.ftl" for dependency in dependencies)
    assert any(
        dependency.target_file == "templates/macros/common.ftl" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "index" for symbol in symbols)
    assert any(
        reference.target_file == "templates/macros/common.ftl"
        and reference.target_names == ("renderButton",)
        for reference in references
    )


def test_freemarker_language_detection_supports_ftl_suffix_without_overclaiming_plain_ftl() -> None:
    assert ".ftl" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("templates/index.ftl"),
        text='<#include "layout/base.ftl">\n${title!""}\n',
    ) == "freemarker"
    assert (
        repository_service._language_for_path(
            Path("locales/messages.ftl"),
            text="welcome = Welcome to the product\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_freemarker_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "freemarker-profile-repo"
    (repo_path / "templates" / "layout").mkdir(parents=True)
    (repo_path / "templates" / "macros").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "templates" / "layout" / "base.ftl").write_text(
        "<#assign pageTitle = 'Demo'>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "macros" / "common.ftl").write_text(
        "<#macro renderButton label><button>${label}</button></#macro>\n",
        encoding="utf-8",
    )
    (repo_path / "templates" / "index.ftl").write_text(
        '<#include "layout/base.ftl">\n'
        '<#import "macros/common.ftl" as common>\n'
        '<@common.renderButton label="Ship it" />\n',
        encoding="utf-8",
    )
    (repo_path / "templates" / "page.ftl").write_text(
        '<#include "layout/base.ftl">\n${pageTitle!""}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "App.java").write_text(
        "final class App { String render() { return \"ok\"; } }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "freemarker" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "freemarker"
    assert "templates/index.ftl" in seed_plan["entrypoint_files"]
