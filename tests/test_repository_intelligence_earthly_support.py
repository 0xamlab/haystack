from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_earthly_parser_dispatch as repository_intelligence_earthly_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    earthly_analysis_support as repository_earthly_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    earthly_primitives as repository_earthly_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_earthly_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["earthly"] is (
        repository_intelligence_earthly_parser_dispatch._parse_earthly_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["earthly"] is (
        repository_intelligence_earthly_parser_dispatch._parse_earthly_dependencies_only
    )


def test_repository_intelligence_earthly_helpers_are_modularized() -> None:
    assert repository_service.earthly_adapter.strip_comments is (
        repository_earthly_primitives.strip_comments
    )
    assert repository_service.earthly_adapter.has_earthly_path_hints is (
        repository_earthly_primitives.has_earthly_path_hints
    )
    assert repository_service.earthly_adapter.is_probable_earthly_source is (
        repository_earthly_analysis_support.is_probable_earthly_source
    )
    assert repository_service.earthly_adapter.module_aliases_for_path is (
        repository_earthly_analysis_support.module_aliases_for_path
    )
    assert repository_service.earthly_adapter.parse_dependencies_only is (
        repository_earthly_analysis_support.parse_dependencies_only
    )
    assert repository_service.earthly_adapter.parse_file is (
        repository_earthly_analysis_support.parse_file
    )


def test_earthly_adapter_parse_file_resolves_imported_targets_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "earthly-parse-repo"
    (repo_path / "lib1").mkdir(parents=True)
    (repo_path / "lib1" / "Earthfile").write_text(
        "VERSION 0.8\n"
        "build:\n"
        "  RUN echo build lib1\n"
        "install:\n"
        "  RUN echo install lib1\n",
        encoding="utf-8",
    )
    (repo_path / "Earthfile").write_text(
        "VERSION 0.8\n"
        "IMPORT ./lib1 AS common\n"
        "deps:\n"
        "  BUILD ./lib1+build\n"
        "use-import:\n"
        "  DO common+install\n"
        "all:\n"
        "  FROM +deps\n"
        "  BUILD +use-import\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["Earthfile", "lib1/Earthfile"],
        root_path=repo_path,
    )
    source_text = (repo_path / "Earthfile").read_text(encoding="utf-8")

    aliases = repository_service.earthly_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib1/Earthfile",
        stable_identifier=repository_service._stable_identifier,
    )
    symbols, dependencies, references = repository_service.earthly_adapter.parse_file(
        "Earthfile",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert "lib1/Earthfile" in aliases
    assert "lib1" in aliases
    assert any(symbol.symbol_name == "deps" for symbol in symbols)
    assert any(symbol.symbol_name == "use-import" for symbol in symbols)
    assert any(
        dependency.target_file == "lib1/Earthfile" and dependency.target_symbol == "build"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "lib1/Earthfile" and dependency.target_symbol == "install"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "Earthfile" and dependency.target_symbol == "deps"
        for dependency in dependencies
    )
    assert any(
        reference.target_file == "lib1/Earthfile" and reference.target_names == ("install",)
        for reference in references
    )
    assert any(reference.target_file == "Earthfile" and reference.target_names == ("deps",) for reference in references)


def test_earthly_language_detection_supports_earthfile_without_overclaiming() -> None:
    assert "Earthfile" in repository_service._TEXT_FILE_BASENAMES
    assert repository_service._language_for_path(
        Path("Earthfile"),
        text="VERSION 0.8\nbuild:\n  BUILD +deps\n",
    ) == "earthly"
    assert (
        repository_service._language_for_path(
            Path("Earthfile"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_earthly_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "earthly-profile-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "Earthfile").write_text(
        "VERSION 0.8\nall:\n  BUILD ./lib0+build\n  BUILD ./lib1+build\n",
        encoding="utf-8",
    )
    for index in range(4):
        library_dir = repo_path / f"lib{index}"
        library_dir.mkdir(parents=True)
        (library_dir / "Earthfile").write_text(
            "VERSION 0.8\nbuild:\n  RUN echo build\n",
            encoding="utf-8",
        )
    (repo_path / "README.md").write_text("# earthly\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=32,
    )

    assert "earthly" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "earthly"
    assert any(path.endswith("Earthfile") for path in seed_plan["entrypoint_files"])
