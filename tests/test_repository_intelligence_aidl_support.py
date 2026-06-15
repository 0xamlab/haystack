from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_aidl_parser_dispatch as repository_aidl_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    aidl_analysis_support as repository_aidl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    aidl_primitives as repository_aidl_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_aidl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["aidl"] is (
        repository_aidl_parser_dispatch._parse_aidl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["aidl"] is (
        repository_aidl_parser_dispatch._parse_aidl_dependencies_only
    )


def test_repository_intelligence_aidl_helpers_are_modularized() -> None:
    assert repository_service.aidl_adapter.has_aidl_path_hints is (
        repository_aidl_primitives.has_aidl_path_hints
    )
    assert repository_service.aidl_adapter.is_probable_aidl_source is (
        repository_aidl_analysis_support.is_probable_aidl_source
    )
    assert repository_service.aidl_adapter.module_aliases_for_path is (
        repository_aidl_analysis_support.module_aliases_for_path
    )
    assert repository_service.aidl_adapter.parse_dependencies_only is (
        repository_aidl_analysis_support.parse_dependencies_only
    )
    assert repository_service.aidl_adapter.parse_file is repository_aidl_analysis_support.parse_file


def test_aidl_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "aidl-alias-repo"
    (repo_path / "aidl" / "demo").mkdir(parents=True)
    (repo_path / "aidl" / "demo" / "IRemote.aidl").write_text(
        "package demo;\n"
        "interface IRemote {\n"
        "  String ping();\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.aidl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="aidl/demo/IRemote.aidl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "aidl/demo/IRemote.aidl" in aliases
    assert "IRemote" in aliases
    assert "demo.IRemote" in aliases


def test_aidl_adapter_parse_file_resolves_imports_and_same_package_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "aidl/demo/IRemote.aidl",
            "aidl/demo/Request.aidl",
        ],
        root_path=Path("/tmp/aidl-index"),
    )
    text = (
        "package demo;\n"
        "import demo.Request;\n"
        "interface IRemote {\n"
        "  Request ping(in Request request);\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.aidl_adapter.parse_file(
        "aidl/demo/IRemote.aidl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        symbol.symbol_name == "IRemote" and symbol.symbol_kind == "interface"
        for symbol in symbols
    )
    assert any(
        dependency.target_file == "aidl/demo/Request.aidl"
        and dependency.dependency_type == "imports"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("Request",) for reference in references)


def test_aidl_language_detection_supports_aidl_sources_without_overclaiming() -> None:
    assert ".aidl" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("aidl/demo/IRemote.aidl"),
            text="package demo;\noneway interface IRemote {}\n",
        )
        == "aidl"
    )
    assert (
        repository_service._language_for_path(
            Path("aidl/demo/IRemote.aidl"),
            text="#!/bin/sh\necho hi\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_aidl_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "aidl-profile-repo"
    (repo_path / "aidl" / "demo").mkdir(parents=True)
    for index in range(6):
        (repo_path / "aidl" / "demo" / f"IRemote{index}.aidl").write_text(
            "package demo;\n"
            f"interface IRemote{index} {{\n"
            "  String ping();\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "def helper() -> int:\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "aidl" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "aidl"
