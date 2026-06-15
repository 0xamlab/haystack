from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_alloy_parser_dispatch as repository_alloy_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    alloy_analysis_support as repository_alloy_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    alloy_primitives as repository_alloy_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_alloy_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["alloy"] is (
        repository_alloy_parser_dispatch._parse_alloy_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["alloy"] is (
        repository_alloy_parser_dispatch._parse_alloy_dependencies_only
    )


def test_repository_intelligence_alloy_helpers_are_modularized() -> None:
    assert repository_service.alloy_adapter.strip_comments is (
        repository_alloy_primitives.strip_comments
    )
    assert repository_service.alloy_adapter.has_alloy_path_hints is (
        repository_alloy_primitives.has_alloy_path_hints
    )
    assert repository_service.alloy_adapter.is_probable_alloy_source is (
        repository_alloy_analysis_support.is_probable_alloy_source
    )
    assert repository_service.alloy_adapter.module_aliases_for_path is (
        repository_alloy_analysis_support.module_aliases_for_path
    )
    assert repository_service.alloy_adapter.parse_dependencies_only is (
        repository_alloy_analysis_support.parse_dependencies_only
    )
    assert repository_service.alloy_adapter.parse_file is (
        repository_alloy_analysis_support.parse_file
    )


def test_alloy_adapter_module_aliases_include_declared_module_and_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "alloy-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "main.als").write_text(
        "module models/main\n"
        "open models/shared as shared\n"
        "sig Node {}\n"
        "pred reachable[n: Node] { some Node }\n",
        encoding="utf-8",
    )

    aliases = repository_service.alloy_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/main.als",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/main.als" in aliases
    assert "models/main" in aliases
    assert "models.main" in aliases
    assert "main" in aliases
    assert "Node" in aliases
    assert "reachable" in aliases


def test_alloy_adapter_parse_file_resolves_open_dependencies_and_symbol_references() -> None:
    module_index = repository_service._build_module_index(
        ["models/shared.als", "models/main.als"],
        root_path=Path("/tmp/alloy-index"),
    )
    text = (
        "module models/main\n"
        "open models/shared as shared\n"
        "sig Node {}\n"
        "pred reachable[n: Node] { some Node }\n"
    )

    symbols, dependencies, references = repository_service.alloy_adapter.parse_file(
        "models/main.als",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "Node" and symbol.symbol_kind == "signature" for symbol in symbols)
    assert any(
        dependency.target_file == "models/shared.als"
        and dependency.dependency_type == "opens"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("models/shared",) for reference in references)
    assert any(reference.target_names == ("Node",) for reference in references)


def test_alloy_language_detection_supports_alloy_sources_without_overclaiming() -> None:
    assert ".als" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("models/main.als"),
            text="module models/main\nsig Node {}\nrun {}\n",
        )
        == "alloy"
    )
    assert (
        repository_service._language_for_path(
            Path("models/main.als"),
            text="plain notes without alloy constructs\n",
        )
        == "unknown"
    )


def test_candidate_ecosystems_for_path_detects_alloy_with_repo_context(tmp_path: Path) -> None:
    repo_path = tmp_path / "alloy-candidate-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "main.als").write_text(
        "module models/main\nsig Node {}\nrun {}\n",
        encoding="utf-8",
    )

    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    assert probe_module._candidate_ecosystems_for_path(
        "models/main.als",
        repo_path=repo_path,
    ) == {"alloy"}


def test_operational_seed_plan_without_diagnostics_promotes_alloy_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "alloy-profile-repo"
    (repo_path / "models").mkdir(parents=True)
    for index in range(6):
        (repo_path / "models" / f"model_{index}.als").write_text(
            f"module models/model_{index}\n"
            f"sig Node{index} {{}}\n"
            "run {}\n",
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

    assert "alloy" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "alloy"
    assert any(path.endswith(".als") for path in seed_plan["entrypoint_files"])
