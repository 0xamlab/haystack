from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_brightscript_parser_dispatch as repository_intelligence_brightscript_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    brightscript_analysis_support as repository_brightscript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    brightscript_primitives as repository_brightscript_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_brightscript_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["brightscript"] is (
        repository_intelligence_brightscript_parser_dispatch._parse_brightscript_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["brightscript"] is (
        repository_intelligence_brightscript_parser_dispatch._parse_brightscript_dependencies_only
    )


def test_repository_intelligence_brightscript_helpers_are_modularized() -> None:
    assert repository_service.brightscript_adapter.strip_comments is (
        repository_brightscript_primitives.strip_comments
    )
    assert repository_service.brightscript_adapter.has_brightscript_path_hints is (
        repository_brightscript_primitives.has_brightscript_path_hints
    )
    assert repository_service.brightscript_adapter.is_probable_brightscript_source is (
        repository_brightscript_analysis_support.is_probable_brightscript_source
    )
    assert repository_service.brightscript_adapter.is_probable_brightscript_config is (
        repository_brightscript_analysis_support.is_probable_brightscript_config
    )
    assert repository_service.brightscript_adapter.module_aliases_for_path is (
        repository_brightscript_analysis_support.module_aliases_for_path
    )
    assert repository_service.brightscript_adapter.parse_dependencies_only is (
        repository_brightscript_analysis_support.parse_dependencies_only
    )
    assert repository_service.brightscript_adapter.parse_file is (
        repository_brightscript_analysis_support.parse_file
    )


def test_brightscript_adapter_parse_file_resolves_library_imports_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "brightscript-parse-repo"
    (repo_path / "source").mkdir(parents=True)
    (repo_path / "source" / "utils.brs").write_text(
        "function GetGreeting() as String\n    return \"hi\"\nend function\n",
        encoding="utf-8",
    )
    (repo_path / "source" / "main.brs").write_text(
        'Library "pkg:/source/utils.brs"\n'
        "sub Main()\n"
        "    message = GetGreeting()\n"
        "end sub\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["source/utils.brs", "source/main.brs"],
        root_path=repo_path,
    )
    text = (repo_path / "source" / "main.brs").read_text(encoding="utf-8")

    aliases = repository_service.brightscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="source/main.brs",
        stable_identifier=repository_service._stable_identifier,
    )
    symbols, dependencies, references = repository_service.brightscript_adapter.parse_file(
        "source/main.brs",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert "source/main.brs" in aliases
    assert "source.main" in aliases
    assert "Main" in aliases
    assert any(symbol.symbol_name == "Main" for symbol in symbols)
    assert any(dependency.target_file == "source/utils.brs" for dependency in dependencies)
    assert any(
        reference.target_file == "source/utils.brs"
        and reference.target_names == ("GetGreeting",)
        for reference in references
    )


def test_brightscript_language_detection_supports_brs_and_manifest_without_overclaiming() -> None:
    assert ".brs" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("source/main.brs"),
        text="sub Main()\nend sub\n",
    ) == "brightscript"
    assert repository_service._language_for_path(
        Path("manifest"),
        text="title=Demo\nmajor_version=1\nminor_version=0\nbuild_version=1\n",
    ) == "brightscript"
    assert (
        repository_service._language_for_path(
            Path("source/main.brs"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_brightscript_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "brightscript-profile-repo"
    (repo_path / "source").mkdir(parents=True)
    (repo_path / "components").mkdir(parents=True)
    (repo_path / "manifest").write_text(
        "title=Demo\nmajor_version=1\nminor_version=0\nbuild_version=1\n",
        encoding="utf-8",
    )
    (repo_path / "source" / "utils.brs").write_text(
        "function GetGreeting() as String\n    return \"hi\"\nend function\n",
        encoding="utf-8",
    )
    (repo_path / "source" / "main.brs").write_text(
        'Library "pkg:/source/utils.brs"\n'
        "sub Main()\n"
        "    message = GetGreeting()\n"
        "end sub\n",
        encoding="utf-8",
    )
    (repo_path / "components" / "MainScene.brs").write_text(
        "sub Init()\n    Main()\nend sub\n",
        encoding="utf-8",
    )
    (repo_path / "README.md").write_text("# demo\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=64,
    )

    assert "brightscript" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "brightscript"
    assert "manifest" in seed_plan["config_paths"]
    assert any(path.endswith(".brs") for path in seed_plan["entrypoint_files"])
