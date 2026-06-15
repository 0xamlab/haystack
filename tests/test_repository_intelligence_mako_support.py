from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_mako_parser_dispatch as repository_intelligence_mako_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mako_analysis_support as repository_mako_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mako_primitives as repository_mako_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_mako_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["mako"] is (
        repository_intelligence_mako_parser_dispatch._parse_mako_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["mako"] is (
        repository_intelligence_mako_parser_dispatch._parse_mako_dependencies_only
    )


def test_repository_intelligence_mako_helpers_are_modularized() -> None:
    assert repository_service.mako_adapter.strip_comments is (
        repository_mako_primitives.strip_comments
    )
    assert repository_service.mako_adapter.has_mako_path_hints is (
        repository_mako_primitives.has_mako_path_hints
    )
    assert repository_service.mako_adapter.iter_dependency_entries is (
        repository_mako_primitives.iter_dependency_entries
    )
    assert repository_service.mako_adapter.iter_reference_entries is (
        repository_mako_primitives.iter_reference_entries
    )
    assert repository_service.mako_adapter.iter_symbol_entries is (
        repository_mako_primitives.iter_symbol_entries
    )
    assert repository_service.mako_adapter.resolve_import is (
        repository_mako_primitives.resolve_import
    )
    assert repository_service.mako_adapter.is_probable_mako_source is (
        repository_mako_analysis_support.is_probable_mako_source
    )
    assert repository_service.mako_adapter.module_aliases_for_path is (
        repository_mako_analysis_support.module_aliases_for_path
    )
    assert repository_service.mako_adapter.parse_dependencies_only is (
        repository_mako_analysis_support.parse_dependencies_only
    )
    assert repository_service.mako_adapter.parse_file is (
        repository_mako_analysis_support.parse_file
    )


def test_mako_adapter_module_aliases_include_template_module_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "mako-alias-repo"
    (repo_path / "templates" / "common").mkdir(parents=True)
    (repo_path / "templates" / "common" / "layout.mako").write_text(
        '<%def name="render_title(value)">${value}</%def>\n',
        encoding="utf-8",
    )

    aliases = repository_service.mako_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="templates/common/layout.mako",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "templates/common/layout.mako" in aliases
    assert "common.layout" in aliases
    assert "render_title" in aliases


def test_mako_adapter_parse_file_resolves_dependencies_and_namespace_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mako-parse-repo"
    (repo_path / "templates" / "common").mkdir(parents=True)
    (repo_path / "templates" / "common" / "layout.mako").write_text(
        '<%def name="render_title(value)">${value}</%def>\n',
        encoding="utf-8",
    )
    (repo_path / "templates" / "base.mako").write_text(
        '<%block name="content"></%block>\n',
        encoding="utf-8",
    )
    (repo_path / "templates" / "page.mako").write_text(
        '<%inherit file="base.mako"/>\n'
        '<%namespace name="layout" file="common/layout.mako"/>\n'
        '${layout.render_title("Ship it")}\n'
        '<%def name="render_page()">${layout.render_title("Again")}</%def>\n',
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "templates/base.mako",
            "templates/common/layout.mako",
            "templates/page.mako",
        ],
        root_path=repo_path,
    )
    text = (repo_path / "templates" / "page.mako").read_text(encoding="utf-8")

    dependencies = repository_service.mako_adapter.parse_dependencies_only(
        "templates/page.mako",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.mako_adapter.parse_file(
        "templates/page.mako",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "templates/base.mako" for dependency in dependencies)
    assert any(
        dependency.target_file == "templates/common/layout.mako" for dependency in dependencies
    )
    assert any(symbol.symbol_name == "render_page" for symbol in symbols)
    assert any(
        reference.target_file == "templates/common/layout.mako"
        and reference.target_names == ("render_title",)
        for reference in references
    )


def test_mako_language_detection_supports_mako_suffix_without_overclaiming() -> None:
    assert ".mako" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("templates/page.mako"),
        text='<%inherit file="base.mako"/>\n${next.body()}\n',
    ) == "mako"
    assert (
        repository_service._language_for_path(
            Path("templates/page.mako"),
            text="plain notes without templating markers\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_mako_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mako-profile-repo"
    (repo_path / "templates" / "common").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "templates" / "common" / "layout.mako").write_text(
        '<%def name="render_title(value)">${value}</%def>\n',
        encoding="utf-8",
    )
    (repo_path / "templates" / "base.mako").write_text(
        '<%block name="content"></%block>\n',
        encoding="utf-8",
    )
    (repo_path / "templates" / "page.mako").write_text(
        '<%inherit file="base.mako"/>\n'
        '<%namespace name="layout" file="common/layout.mako"/>\n'
        '${layout.render_title("Ship it")}\n',
        encoding="utf-8",
    )
    (repo_path / "templates" / "summary.mako").write_text(
        '<%include file="base.mako"/>\n${"ok"}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "mako" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "mako"
    assert "templates/page.mako" in seed_plan["entrypoint_files"]
