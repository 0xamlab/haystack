from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_ats_parser_dispatch as repository_ats_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ats_analysis_support as repository_ats_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ats_primitives as repository_ats_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_ats_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["ats"] is (
        repository_ats_parser_dispatch._parse_ats_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["ats"] is (
        repository_ats_parser_dispatch._parse_ats_dependencies_only
    )


def test_repository_intelligence_ats_helpers_are_modularized() -> None:
    assert repository_service.ats_adapter.strip_comments is (
        repository_ats_primitives.strip_comments
    )
    assert repository_service.ats_adapter.has_ats_path_hints is (
        repository_ats_primitives.has_ats_path_hints
    )
    assert repository_service.ats_adapter.is_probable_ats_source is (
        repository_ats_analysis_support.is_probable_ats_source
    )
    assert repository_service.ats_adapter.module_aliases_for_path is (
        repository_ats_analysis_support.module_aliases_for_path
    )
    assert repository_service.ats_adapter.parse_dependencies_only is (
        repository_ats_analysis_support.parse_dependencies_only
    )
    assert repository_service.ats_adapter.parse_file is (
        repository_ats_analysis_support.parse_file
    )


def test_ats_adapter_module_aliases_include_module_and_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "ats-alias-repo"
    (repo_path / "RECIPE" / "Hello").mkdir(parents=True)
    (repo_path / "RECIPE" / "Hello" / "Hello.dats").write_text(
        '#include "share/atspre_staload.hats"\n'
        "typedef greeting = string\n"
        "implement main0() = println!(\"Hello\")\n",
        encoding="utf-8",
    )

    aliases = repository_service.ats_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="RECIPE/Hello/Hello.dats",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "RECIPE/Hello/Hello.dats" in aliases
    assert "Hello" in aliases
    assert "Hello.dats" in aliases
    assert "Hello" in aliases
    assert "greeting" in aliases
    assert "main0" in aliases


def test_ats_adapter_parse_file_resolves_include_and_staload_dependencies() -> None:
    module_index = repository_service._build_module_index(
        [
            "RECIPE/common.hats",
            "SATS/basics.sats",
            "DATS/main.dats",
        ],
        root_path=Path("/tmp/ats-index"),
    )
    text = (
        '#include "./../RECIPE/common.hats"\n'
        '#staload "./../SATS/basics.sats"\n'
        "typedef role = int\n"
        "extern fun print_role(role): void\n"
        "implement main0() = print_role(0)\n"
    )

    symbols, dependencies, references = repository_service.ats_adapter.parse_file(
        "DATS/main.dats",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "role" and symbol.symbol_kind == "type" for symbol in symbols)
    assert any(symbol.symbol_name == "print_role" and symbol.symbol_kind == "function" for symbol in symbols)
    assert any(symbol.symbol_name == "main0" and symbol.symbol_kind == "implementation" for symbol in symbols)
    assert any(
        dependency.target_file == "RECIPE/common.hats" and dependency.dependency_type == "includes"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "SATS/basics.sats" and dependency.dependency_type == "staloads"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("common",) for reference in references)
    assert any(reference.target_names == ("basics",) for reference in references)
    assert any(reference.target_names == ("print_role",) for reference in references)


def test_ats_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".dats" in repository_service._TEXT_FILE_SUFFIXES
    assert ".sats" in repository_service._TEXT_FILE_SUFFIXES
    assert ".hats" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("DATS/main.dats"),
            text='##include "share/atspre_staload.hats"\nimplement main0() = println!("Hello")\n'.replace("##", "#"),
        )
        == "ats"
    )
    assert (
        repository_service._language_for_path(
            Path("SATS/basics.sats"),
            text="datatype role = ROLE of int\n",
        )
        == "ats"
    )
    assert (
        repository_service._language_for_path(
            Path("DATS/main.dats"),
            text="plain notes without ats constructs\n",
        )
        == "unknown"
    )


def test_candidate_ecosystems_for_path_detects_ats_with_repo_context(tmp_path: Path) -> None:
    repo_path = tmp_path / "ats-candidate-repo"
    (repo_path / "DATS").mkdir(parents=True)
    (repo_path / "DATS" / "main.dats").write_text(
        '#include "share/atspre_staload.hats"\nimplement main0() = println!("Hello")\n',
        encoding="utf-8",
    )

    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    assert probe_module._candidate_ecosystems_for_path(
        "DATS/main.dats",
        repo_path=repo_path,
    ) == {"ats"}


def test_operational_seed_plan_without_diagnostics_promotes_ats_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ats-profile-repo"
    (repo_path / "DATS").mkdir(parents=True)
    (repo_path / "SATS").mkdir(parents=True)
    for index in range(4):
        (repo_path / "DATS" / f"recipe_{index}.dats").write_text(
            '#include "share/atspre_staload.hats"\n'
            f"implement recipe_{index}() = ()\n",
            encoding="utf-8",
        )
    for index in range(2):
        (repo_path / "SATS" / f"basis_{index}.sats").write_text(
            f"datatype basis_{index} = BASIS_{index} of int\n",
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

    assert "ats" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "ats"
    assert any(path.endswith(".dats") or path.endswith(".sats") for path in seed_plan["entrypoint_files"])
