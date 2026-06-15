from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_asl_parser_dispatch as repository_asl_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    asl_analysis_support as repository_asl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    asl_primitives as repository_asl_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_asl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["asl"] is (
        repository_asl_parser_dispatch._parse_asl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["asl"] is (
        repository_asl_parser_dispatch._parse_asl_dependencies_only
    )


def test_repository_intelligence_asl_helpers_are_modularized() -> None:
    assert repository_service.asl_adapter.strip_comments is (
        repository_asl_primitives.strip_comments
    )
    assert repository_service.asl_adapter.has_asl_path_hints is (
        repository_asl_primitives.has_asl_path_hints
    )
    assert repository_service.asl_adapter.is_probable_asl_source is (
        repository_asl_analysis_support.is_probable_asl_source
    )
    assert repository_service.asl_adapter.module_aliases_for_path is (
        repository_asl_analysis_support.module_aliases_for_path
    )
    assert repository_service.asl_adapter.parse_dependencies_only is (
        repository_asl_analysis_support.parse_dependencies_only
    )
    assert repository_service.asl_adapter.parse_file is (
        repository_asl_analysis_support.parse_file
    )


def test_asl_adapter_module_aliases_include_module_and_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "asl-alias-repo"
    (repo_path / "firmware" / "acpi").mkdir(parents=True)
    (repo_path / "firmware" / "acpi" / "SSDT-XOSI.dsl").write_text(
        'DefinitionBlock ("", "SSDT", 2, "TEST", "XOSI", 0x00000000)\n'
        "{\n"
        "    Name (OSX, \"Darwin\")\n"
        "    Method (OSID, 0, NotSerialized)\n"
        "    {\n"
        "        Return (OSX)\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.asl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="firmware/acpi/SSDT-XOSI.dsl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "firmware/acpi/SSDT-XOSI.dsl" in aliases
    assert "SSDT-XOSI.dsl" in aliases
    assert "SSDT-XOSI" in aliases
    assert "OSX" in aliases
    assert "OSID" in aliases


def test_asl_adapter_parse_file_resolves_include_and_symbol_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "acpi/includes/common.asl",
            "acpi/SSDT-MAIN.dsl",
        ],
        root_path=Path("/tmp/asl-index"),
    )
    text = (
        '#include "includes/common.asl"\n'
        'DefinitionBlock ("", "SSDT", 2, "TEST", "MAIN", 0x00000000)\n'
        "{\n"
        "    External (_SB.PCI0.GNUM, MethodObj)\n"
        "    Name (MODE, One)\n"
        "    Method (PKGX, 3, Serialized)\n"
        "    {\n"
        "        Return (GNUM (MODE))\n"
        "    }\n"
        "    Method (CALL, 0, NotSerialized)\n"
        "    {\n"
        "        Return (PKGX (MODE, MODE, MODE))\n"
        "    }\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.asl_adapter.parse_file(
        "acpi/SSDT-MAIN.dsl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "MODE" and symbol.symbol_kind == "name" for symbol in symbols)
    assert any(symbol.symbol_name == "PKGX" and symbol.symbol_kind == "method" for symbol in symbols)
    assert any(symbol.symbol_name == "CALL" and symbol.symbol_kind == "method" for symbol in symbols)
    assert any(
        dependency.target_file == "acpi/includes/common.asl"
        and dependency.dependency_type == "includes"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("common",) for reference in references)
    assert any(reference.target_names[0] == "GNUM" for reference in references)
    assert any(reference.target_file == "acpi/SSDT-MAIN.dsl" and reference.target_names == ("PKGX",) for reference in references)


def test_asl_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".asl" in repository_service._TEXT_FILE_SUFFIXES
    assert ".dsl" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("firmware/acpi/SSDT-XOSI.dsl"),
            text='DefinitionBlock ("", "SSDT", 2, "TEST", "XOSI", 0x00000000)\n'
            "{\n"
            "    Scope (_SB)\n"
            "    {\n"
            "        Method (OSID, 0, NotSerialized)\n"
            "        {\n"
            "            Return (Zero)\n"
            "        }\n"
            "    }\n"
            "}\n",
        )
        == "asl"
    )
    assert (
        repository_service._language_for_path(
            Path("firmware/tables/MAIN.asl"),
            text='DefinitionBlock ("", "DSDT", 2, "TEST", "MAIN", 0x00000000)\n'
            "{\n"
            "    Name (MODE, One)\n"
            "    Method (RUN, 0, NotSerialized)\n"
            "    {\n"
            "        Return (MODE)\n"
            "    }\n"
            "}\n",
        )
        == "asl"
    )
    assert (
        repository_service._language_for_path(
            Path("specs/model.dsl"),
            text="model App { value: string }\n",
        )
        == "unknown"
    )


def test_candidate_ecosystems_for_path_detects_asl_with_repo_context(tmp_path: Path) -> None:
    repo_path = tmp_path / "asl-candidate-repo"
    (repo_path / "firmware" / "acpi").mkdir(parents=True)
    (repo_path / "firmware" / "acpi" / "SSDT-XOSI.dsl").write_text(
        'DefinitionBlock ("", "SSDT", 2, "TEST", "XOSI", 0x00000000)\n'
        "{\n"
        "    Scope (_SB)\n"
        "    {\n"
        "        Name (OSX, \"Darwin\")\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    assert probe_module._candidate_ecosystems_for_path(
        "firmware/acpi/SSDT-XOSI.dsl",
        repo_path=repo_path,
    ) == {"asl"}


def test_operational_seed_plan_without_diagnostics_promotes_asl_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "asl-profile-repo"
    (repo_path / "firmware" / "acpi" / "origin").mkdir(parents=True)
    for index in range(4):
        (repo_path / "firmware" / "acpi" / "origin" / f"SSDT-{index}.dsl").write_text(
            'DefinitionBlock ("", "SSDT", 2, "TEST", "MAIN", 0x00000000)\n'
            "{\n"
            f"    Name (VAL{index}, Zero)\n"
            f"    Method (RUN{index}, 0, NotSerialized)\n"
            "    {\n"
            f"        Return (VAL{index})\n"
            "    }\n"
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

    assert "asl" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "asl"
    assert any(path.endswith(".dsl") for path in seed_plan["entrypoint_files"])
