from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_dafny_parser_dispatch as repository_dafny_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dafny_analysis_support as repository_dafny_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dafny_primitives as repository_dafny_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_dafny_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["dafny"] is (
        repository_dafny_parser_dispatch._parse_dafny_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["dafny"] is (
        repository_dafny_parser_dispatch._parse_dafny_dependencies_only
    )


def test_repository_intelligence_dafny_helpers_are_modularized() -> None:
    assert repository_service.dafny_adapter.has_dafny_path_hints is (
        repository_dafny_primitives.has_dafny_path_hints
    )
    assert repository_service.dafny_adapter.is_probable_dafny_source is (
        repository_dafny_analysis_support.is_probable_dafny_source
    )
    assert repository_service.dafny_adapter.iter_include_entries is (
        repository_dafny_primitives.iter_include_entries
    )
    assert repository_service.dafny_adapter.resolve_include is (
        repository_dafny_analysis_support.resolve_include
    )
    assert repository_service.dafny_adapter.parse_file is (
        repository_dafny_analysis_support.parse_file
    )


def test_dafny_adapter_parse_file_extracts_includes_and_symbol_references() -> None:
    module_index = repository_service._build_module_index(
        ["src/Helpers.dfy", "src/Main.dfy"],
        root_path=Path("/tmp/dafny-index"),
    )
    text = (
        'include "Helpers.dfy"\n'
        "module Main {\n"
        "  import opened Helpers\n"
        "  method Run() returns (value: int) {\n"
        "    value := Helper();\n"
        "  }\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.dafny_adapter.parse_file(
        "src/Main.dfy",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "src/Helpers.dfy" for dependency in dependencies)
    assert any(symbol.symbol_name == "Main" for symbol in symbols)
    assert any(symbol.symbol_name == "Run" for symbol in symbols)
    assert any(reference.target_file == "src/Helpers.dfy" for reference in references)


def test_dafny_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".dfy" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("src/Main.dfy"),
            text=(
                "module Main {\n"
                "  method Run() {}\n"
                "}\n"
            ),
        )
        == "dafny"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/example.dfy"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_dafny_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dafny-profile-repo"
    src_dir = repo_path / "src"
    src_dir.mkdir(parents=True)
    for index in range(6):
        (src_dir / f"Module{index}.dfy").write_text(
            (
                "module Main {\n"
                f"  function Helper{index}(): int {{ {index} }}\n"
                "}\n"
            ),
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

    assert "dafny" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "dafny"
