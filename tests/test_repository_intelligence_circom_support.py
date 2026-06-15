from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_circom_parser_dispatch as repository_circom_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    circom_analysis_support as repository_circom_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    circom_primitives as repository_circom_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_circom_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["circom"] is (
        repository_circom_parser_dispatch._parse_circom_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["circom"] is (
        repository_circom_parser_dispatch._parse_circom_dependencies_only
    )


def test_repository_intelligence_circom_helpers_are_modularized() -> None:
    assert repository_service.circom_adapter.has_circom_path_hints is (
        repository_circom_primitives.has_circom_path_hints
    )
    assert repository_service.circom_adapter.is_probable_circom_source is (
        repository_circom_analysis_support.is_probable_circom_source
    )
    assert repository_service.circom_adapter.iter_include_entries is (
        repository_circom_primitives.iter_include_entries
    )
    assert repository_service.circom_adapter.resolve_include is (
        repository_circom_analysis_support.resolve_include
    )
    assert repository_service.circom_adapter.parse_file is (
        repository_circom_analysis_support.parse_file
    )


def test_circom_adapter_parse_file_extracts_includes_and_component_references() -> None:
    module_index = repository_service._build_module_index(
        ["circuits/hash.circom", "circuits/main.circom"],
        root_path=Path("/tmp/circom-index"),
    )
    text = (
        'pragma circom 2.0.0;\n'
        'include "hash.circom";\n\n'
        "template Main() {\n"
        "    component mainHash = Hash();\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.circom_adapter.parse_file(
        "circuits/main.circom",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "circuits/hash.circom" for dependency in dependencies)
    assert any(symbol.symbol_name == "Main" for symbol in symbols)
    assert any(symbol.symbol_name == "mainHash" for symbol in symbols)
    assert any(reference.target_file == "circuits/hash.circom" for reference in references)


def test_circom_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".circom" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("circuits/main.circom"),
            text=(
                "pragma circom 2.0.0;\n"
                "template Main() {\n"
                "    signal input in;\n"
                "}\n"
            ),
        )
        == "circom"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/example.circom"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_circom_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "circom-profile-repo"
    circuits_dir = repo_path / "circuits"
    circuits_dir.mkdir(parents=True)
    for index in range(6):
        (circuits_dir / f"main_{index}.circom").write_text(
            (
                "pragma circom 2.0.0;\n"
                f"template Main{index}() {{\n"
                "    signal input in;\n"
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

    assert "circom" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "circom"
