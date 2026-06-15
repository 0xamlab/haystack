from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_pkl_parser_dispatch as repository_pkl_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    pkl_analysis_support as repository_pkl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    pkl_primitives as repository_pkl_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_pkl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["pkl"] is (
        repository_pkl_parser_dispatch._parse_pkl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["pkl"] is (
        repository_pkl_parser_dispatch._parse_pkl_dependencies_only
    )


def test_repository_intelligence_pkl_helpers_are_modularized() -> None:
    assert repository_service.pkl_adapter.strip_comments is repository_pkl_primitives.strip_comments
    assert repository_service.pkl_adapter.has_pkl_path_hints is (
        repository_pkl_primitives.has_pkl_path_hints
    )
    assert repository_service.pkl_adapter.is_probable_pkl_source is (
        repository_pkl_analysis_support.is_probable_pkl_source
    )
    assert repository_service.pkl_adapter.is_probable_pkl_config is (
        repository_pkl_analysis_support.is_probable_pkl_config
    )
    assert repository_service.pkl_adapter.module_aliases_for_path is (
        repository_pkl_analysis_support.module_aliases_for_path
    )
    assert repository_service.pkl_adapter.parse_dependencies_only is (
        repository_pkl_analysis_support.parse_dependencies_only
    )
    assert repository_service.pkl_adapter.parse_file is (
        repository_pkl_analysis_support.parse_file
    )


def test_pkl_adapter_parse_file_resolves_imports_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "pkl-parse-repo"
    (repo_path / "config").mkdir(parents=True)
    (repo_path / "config" / "base.pkl").write_text(
        "class Service {\n  endpoint = \"https://example.test\"\n}\n",
        encoding="utf-8",
    )
    (repo_path / "config" / "app.pkl").write_text(
        'import "base.pkl"\n'
        "local buildService = () -> new Service {}\n"
        "service = buildService.apply()\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["config/base.pkl", "config/app.pkl"],
        root_path=repo_path,
    )
    text = (repo_path / "config" / "app.pkl").read_text(encoding="utf-8")

    aliases = repository_service.pkl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="config/app.pkl",
        stable_identifier=repository_service._stable_identifier,
    )
    symbols, dependencies, references = repository_service.pkl_adapter.parse_file(
        "config/app.pkl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert "config/app.pkl" in aliases
    assert "config.app" in aliases
    assert "buildService" in aliases
    assert any(symbol.symbol_name == "buildService" for symbol in symbols)
    assert any(dependency.target_file == "config/base.pkl" for dependency in dependencies)
    assert any(reference.target_names == ("Service",) for reference in references)
    assert any(reference.target_names == ("buildService",) for reference in references)


def test_pkl_language_detection_supports_config_and_source_without_overclaiming() -> None:
    assert ".pkl" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("config/app.pkl"),
        text='import "base.pkl"\nservice = new Service {}\n',
    ) == "pkl"
    assert repository_service._language_for_path(
        Path("PklProject"),
        text='amends "pkl:settings"\n',
    ) == "pkl"
    assert repository_service._language_for_path(
        Path("artifacts/cache.pkl"),
        text="pickle payload placeholder\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_pkl_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "pkl-profile-repo"
    (repo_path / "config").mkdir(parents=True)
    (repo_path / "PklProject").write_text(
        'amends "pkl:settings"\nmodule demo\n',
        encoding="utf-8",
    )
    (repo_path / "config" / "base.pkl").write_text(
        "class Service {\n  endpoint = \"https://example.test\"\n}\n",
        encoding="utf-8",
    )
    for index in range(4):
        (repo_path / "config" / f"service_{index}.pkl").write_text(
            'import "base.pkl"\n'
            f"local service{index} = () -> new Service {{}}\n"
            f"entry{index} = service{index}.apply()\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.js").write_text(
        "export const helper = 1;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "pkl" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "pkl"
    assert any(
        path.endswith(".pkl") or path.endswith("PklProject")
        for path in seed_plan["entrypoint_files"]
    )
