from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_dataweave_parser_dispatch as repository_intelligence_dataweave_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dataweave_analysis_support as repository_dataweave_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dataweave_primitives as repository_dataweave_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_dataweave_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["dataweave"] is (
        repository_intelligence_dataweave_parser_dispatch._parse_dataweave_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["dataweave"] is (
        repository_intelligence_dataweave_parser_dispatch._parse_dataweave_dependencies_only
    )


def test_repository_intelligence_dataweave_helpers_are_modularized() -> None:
    assert repository_service.dataweave_adapter.strip_comments is (
        repository_dataweave_primitives.strip_comments
    )
    assert repository_service.dataweave_adapter.has_dataweave_path_hints is (
        repository_dataweave_primitives.has_dataweave_path_hints
    )
    assert repository_service.dataweave_adapter.is_probable_dataweave_source is (
        repository_dataweave_analysis_support.is_probable_dataweave_source
    )
    assert repository_service.dataweave_adapter.module_aliases_for_path is (
        repository_dataweave_analysis_support.module_aliases_for_path
    )
    assert repository_service.dataweave_adapter.parse_dependencies_only is (
        repository_dataweave_analysis_support.parse_dependencies_only
    )
    assert repository_service.dataweave_adapter.parse_file is (
        repository_dataweave_analysis_support.parse_file
    )


def test_dataweave_adapter_parse_file_resolves_local_imports_and_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dataweave-parse-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "helpers.dwl").write_text(
        "%dw 2.0\nfun titleCase(name) = upper(name)\n---\ntitleCase(\"angel\")\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "transform.dwl").write_text(
        "%dw 2.0\nimport titleCase from helpers\noutput application/json\n---\n{name: titleCase(\"angel\")}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["modules/helpers.dwl", "modules/transform.dwl"],
        root_path=repo_path,
    )
    source_text = (repo_path / "modules" / "transform.dwl").read_text(encoding="utf-8")
    imported_text = (repo_path / "modules" / "helpers.dwl").read_text(encoding="utf-8")

    aliases = repository_service.dataweave_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/transform.dwl",
        stable_identifier=repository_service._stable_identifier,
    )
    imported_symbols, _, _ = repository_service.dataweave_adapter.parse_file(
        "modules/helpers.dwl",
        imported_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, dependencies, references = repository_service.dataweave_adapter.parse_file(
        "modules/transform.dwl",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert "modules/transform.dwl" in aliases
    assert "modules.transform" in aliases
    assert "modules::transform" in aliases
    assert any(symbol.symbol_name == "titleCase" for symbol in imported_symbols)
    assert any(symbol.symbol_name == "modules.transform" for symbol in symbols)
    assert any(dependency.target_file == "modules/helpers.dwl" for dependency in dependencies)
    assert any(
        reference.target_file == "modules/helpers.dwl"
        and reference.target_names == ("modules.helpers",)
        for reference in references
    )


def test_dataweave_language_detection_supports_dwl_without_overclaiming() -> None:
    assert ".dwl" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("modules/transform.dwl"),
        text="%dw 2.0\noutput application/json\n---\n{}\n",
    ) == "dataweave"
    assert (
        repository_service._language_for_path(
            Path("modules/transform.dwl"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_dataweave_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dataweave-profile-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "helpers.dwl").write_text(
        "%dw 2.0\nfun titleCase(name) = upper(name)\n---\ntitleCase(\"angel\")\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "transform.dwl").write_text(
        "%dw 2.0\nimport titleCase from helpers\noutput application/json\n---\n{name: titleCase(\"angel\")}\n",
        encoding="utf-8",
    )
    (repo_path / "README.md").write_text("# demo\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["modules"],
        max_files=32,
    )

    assert "dataweave" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "dataweave"
    assert any(path.endswith(".dwl") for path in seed_plan["entrypoint_files"])
