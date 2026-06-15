from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_common_workflow_language_parser_dispatch as repository_intelligence_common_workflow_language_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    common_workflow_language_analysis_support as repository_common_workflow_language_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    common_workflow_language_primitives as repository_common_workflow_language_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_common_workflow_language_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["common workflow language"] is (
        repository_intelligence_common_workflow_language_parser_dispatch._parse_common_workflow_language_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["common workflow language"] is (
        repository_intelligence_common_workflow_language_parser_dispatch._parse_common_workflow_language_dependencies_only
    )


def test_repository_intelligence_common_workflow_language_helpers_are_modularized() -> None:
    assert repository_service.common_workflow_language_adapter.strip_comments is (
        repository_common_workflow_language_primitives.strip_comments
    )
    assert repository_service.common_workflow_language_adapter.has_common_workflow_language_path_hints is (
        repository_common_workflow_language_primitives.has_common_workflow_language_path_hints
    )
    assert repository_service.common_workflow_language_adapter.is_probable_common_workflow_language_source is (
        repository_common_workflow_language_analysis_support.is_probable_common_workflow_language_source
    )
    assert repository_service.common_workflow_language_adapter.module_aliases_for_path is (
        repository_common_workflow_language_analysis_support.module_aliases_for_path
    )
    assert repository_service.common_workflow_language_adapter.parse_dependencies_only is (
        repository_common_workflow_language_analysis_support.parse_dependencies_only
    )
    assert repository_service.common_workflow_language_adapter.parse_file is (
        repository_common_workflow_language_analysis_support.parse_file
    )


def test_common_workflow_language_adapter_parse_file_resolves_run_dependencies(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cwl-parse-repo"
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "workflows").mkdir(parents=True)
    (repo_path / "tools" / "echo.cwl").write_text(
        "cwlVersion: v1.2\nclass: CommandLineTool\nbaseCommand: echo\n",
        encoding="utf-8",
    )
    (repo_path / "workflows" / "hello.cwl").write_text(
        "cwlVersion: v1.2\nclass: Workflow\nsteps:\n  say_hello:\n    run: ../tools/echo.cwl\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["tools/echo.cwl", "workflows/hello.cwl"],
        root_path=repo_path,
    )
    source_text = (repo_path / "workflows" / "hello.cwl").read_text(encoding="utf-8")

    aliases = repository_service.common_workflow_language_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="workflows/hello.cwl",
        stable_identifier=repository_service._stable_identifier,
    )
    symbols, dependencies, references = repository_service.common_workflow_language_adapter.parse_file(
        "workflows/hello.cwl",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert "workflows/hello.cwl" in aliases
    assert "workflows.hello" in aliases
    assert any(symbol.symbol_name == "Workflow" for symbol in symbols)
    assert any(dependency.target_file == "tools/echo.cwl" for dependency in dependencies)
    assert any(
        reference.target_file == "tools/echo.cwl"
        and reference.target_names == ("tools.echo",)
        for reference in references
    )


def test_common_workflow_language_detection_supports_cwl_without_overclaiming() -> None:
    assert ".cwl" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("workflows/hello.cwl"),
        text="cwlVersion: v1.2\nclass: Workflow\nsteps: {}\n",
    ) == "common workflow language"
    assert (
        repository_service._language_for_path(
            Path("workflows/hello.cwl"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_common_workflow_language_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cwl-profile-repo"
    (repo_path / "src" / "_includes" / "cwl").mkdir(parents=True)
    (repo_path / "src" / "_includes" / "cwl" / "echo.cwl").write_text(
        "cwlVersion: v1.2\nclass: CommandLineTool\nbaseCommand: echo\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "_includes" / "cwl" / "workflow.cwl").write_text(
        "cwlVersion: v1.2\nclass: Workflow\nsteps:\n  say_hello:\n    run: echo.cwl\n",
        encoding="utf-8",
    )
    (repo_path / "README.md").write_text("# demo\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src/_includes/cwl"],
        max_files=32,
    )

    assert "common workflow language" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "common workflow language"
    assert any(path.endswith(".cwl") for path in seed_plan["entrypoint_files"])
