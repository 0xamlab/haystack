from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_xtend_parser_dispatch as repository_xtend_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    xtend_analysis_support as repository_xtend_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    xtend_primitives as repository_xtend_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_xtend_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["xtend"] is (
        repository_xtend_parser_dispatch._parse_xtend_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["xtend"] is (
        repository_xtend_parser_dispatch._parse_xtend_dependencies_only
    )


def test_repository_intelligence_xtend_helpers_are_modularized() -> None:
    assert repository_service.xtend_adapter.has_xtend_path_hints is (
        repository_xtend_primitives.has_xtend_path_hints
    )
    assert repository_service.xtend_adapter.is_probable_xtend_source is (
        repository_xtend_analysis_support.is_probable_xtend_source
    )
    assert repository_service.xtend_adapter.module_aliases_for_path is (
        repository_xtend_analysis_support.module_aliases_for_path
    )
    assert repository_service.xtend_adapter.parse_dependencies_only is (
        repository_xtend_analysis_support.parse_dependencies_only
    )
    assert repository_service.xtend_adapter.parse_file is (
        repository_xtend_analysis_support.parse_file
    )


def test_xtend_adapter_parse_file_resolves_imports_and_type_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "xtend-parse-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "Base.xtend").write_text(
        "package demo\n\nclass Base {\n}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "App.xtend").write_text(
        "package demo\n\nimport demo.Base\n\nclass App {\n  def Base build() {\n    new Base\n  }\n}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/demo/Base.xtend", "src/demo/App.xtend"],
        root_path=repo_path,
    )
    text = (repo_path / "src" / "demo" / "App.xtend").read_text(encoding="utf-8")

    aliases = repository_service.xtend_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/App.xtend",
        stable_identifier=repository_service._stable_identifier,
    )
    symbols, dependencies, references = repository_service.xtend_adapter.parse_file(
        "src/demo/App.xtend",
        text,
        module_index,
        collect_type_symbol_entries=repository_service._collect_type_symbol_entries,
        stable_identifier=repository_service._stable_identifier,
        resolve_import=repository_service._resolve_jvm_import,
    )

    assert "src/demo/App.xtend" in aliases
    assert "src.demo.App" in aliases
    assert any(symbol.symbol_name == "App" for symbol in symbols)
    assert any(dependency.target_file == "src/demo/Base.xtend" for dependency in dependencies)
    assert any(reference.target_file == "src/demo/Base.xtend" for reference in references)
    assert any(reference.target_names == ("Base",) for reference in references)


def test_xtend_language_detection_supports_xtend_suffix_without_overclaiming() -> None:
    assert ".xtend" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("src/demo/App.xtend"),
        text="package demo\nclass App {}\n",
    ) == "xtend"
    assert repository_service._language_for_path(
        Path("notes/App.xtend"),
        text="plain notes only\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_xtend_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "xtend-profile-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    for index in range(4):
        (repo_path / "src" / "demo" / f"Feature{index}.xtend").write_text(
            "package demo\n\nclass Feature{0} {{\n}}\n".format(index),
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.py").write_text(
        "def helper() -> int:\n    return 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "xtend" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "xtend"
    assert any(path.endswith(".xtend") for path in seed_plan["entrypoint_files"])
