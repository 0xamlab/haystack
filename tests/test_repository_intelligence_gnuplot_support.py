from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_gnuplot_parser_dispatch as repository_intelligence_gnuplot_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gnuplot_analysis_support as repository_gnuplot_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    gnuplot_primitives as repository_gnuplot_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_gnuplot_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["gnuplot"] is (
        repository_intelligence_gnuplot_parser_dispatch._parse_gnuplot_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["gnuplot"] is (
        repository_intelligence_gnuplot_parser_dispatch._parse_gnuplot_dependencies_only
    )


def test_repository_intelligence_gnuplot_helpers_are_modularized() -> None:
    assert repository_service.gnuplot_adapter.strip_comments is (
        repository_gnuplot_primitives.strip_comments
    )
    assert repository_service.gnuplot_adapter.has_gnuplot_path_hints is (
        repository_gnuplot_primitives.has_gnuplot_path_hints
    )
    assert repository_service.gnuplot_adapter.is_probable_gnuplot_source is (
        repository_gnuplot_analysis_support.is_probable_gnuplot_source
    )
    assert repository_service.gnuplot_adapter.module_aliases_for_path is (
        repository_gnuplot_analysis_support.module_aliases_for_path
    )
    assert repository_service.gnuplot_adapter.parse_dependencies_only is (
        repository_gnuplot_analysis_support.parse_dependencies_only
    )
    assert repository_service.gnuplot_adapter.parse_file is (
        repository_gnuplot_analysis_support.parse_file
    )


def test_gnuplot_adapter_parse_file_resolves_load_dependencies_and_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gnuplot-parse-repo"
    (repo_path / "demo").mkdir(parents=True)
    (repo_path / "demo" / "simple.dem").write_text(
        "f(x) = sin(x)\nplot f(x)\n",
        encoding="utf-8",
    )
    (repo_path / "demo" / "all.dem").write_text(
        'load "simple.dem"\n'
        "reset\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["demo/simple.dem", "demo/all.dem"],
        root_path=repo_path,
    )
    source_text = (repo_path / "demo" / "all.dem").read_text(encoding="utf-8")
    imported_text = (repo_path / "demo" / "simple.dem").read_text(encoding="utf-8")

    aliases = repository_service.gnuplot_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="demo/all.dem",
        stable_identifier=repository_service._stable_identifier,
    )
    imported_symbols, _, _ = repository_service.gnuplot_adapter.parse_file(
        "demo/simple.dem",
        imported_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, dependencies, references = repository_service.gnuplot_adapter.parse_file(
        "demo/all.dem",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert "demo/all.dem" in aliases
    assert "demo.all" in aliases
    assert "all" in aliases
    assert any(symbol.symbol_name == "f" for symbol in imported_symbols)
    assert any(symbol.symbol_name == "demo.all" for symbol in symbols)
    assert any(dependency.target_file == "demo/simple.dem" for dependency in dependencies)
    assert any(
        reference.target_file == "demo/simple.dem"
        and reference.target_names == ("demo.simple",)
        for reference in references
    )


def test_gnuplot_language_detection_supports_demo_and_plot_scripts_without_overclaiming() -> None:
    assert ".dem" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("demo/all.dem"),
        text='load "simple.dem"\nreset\n',
    ) == "gnuplot"
    assert repository_service._language_for_path(
        Path("plots/chart.gp"),
        text="plot sin(x)\n",
    ) == "gnuplot"
    assert (
        repository_service._language_for_path(
            Path("demo/all.dem"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_gnuplot_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gnuplot-profile-repo"
    (repo_path / "demo").mkdir(parents=True)
    (repo_path / "demo" / "simple.dem").write_text(
        "f(x) = sin(x)\nplot f(x)\n",
        encoding="utf-8",
    )
    (repo_path / "demo" / "all.dem").write_text(
        'load "simple.dem"\n'
        "reset\n",
        encoding="utf-8",
    )
    (repo_path / "README.md").write_text("# demo\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["demo"],
        max_files=32,
    )

    assert "gnuplot" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "gnuplot"
    assert any(path.endswith(".dem") for path in seed_plan["entrypoint_files"])
