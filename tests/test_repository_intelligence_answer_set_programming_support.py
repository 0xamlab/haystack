from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_answer_set_programming_parser_dispatch as repository_answer_set_programming_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    answer_set_programming_analysis_support as repository_answer_set_programming_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    answer_set_programming_primitives as repository_answer_set_programming_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_answer_set_programming_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["answer set programming"] is (
        repository_answer_set_programming_parser_dispatch._parse_answer_set_programming_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["answer set programming"] is (
        repository_answer_set_programming_parser_dispatch._parse_answer_set_programming_dependencies_only
    )


def test_repository_intelligence_answer_set_programming_helpers_are_modularized() -> None:
    assert repository_service.answer_set_programming_adapter.strip_comments is (
        repository_answer_set_programming_primitives.strip_comments
    )
    assert repository_service.answer_set_programming_adapter.has_answer_set_programming_path_hints is (
        repository_answer_set_programming_primitives.has_answer_set_programming_path_hints
    )
    assert repository_service.answer_set_programming_adapter.is_probable_answer_set_programming_source is (
        repository_answer_set_programming_analysis_support.is_probable_answer_set_programming_source
    )
    assert repository_service.answer_set_programming_adapter.module_aliases_for_path is (
        repository_answer_set_programming_analysis_support.module_aliases_for_path
    )
    assert repository_service.answer_set_programming_adapter.parse_dependencies_only is (
        repository_answer_set_programming_analysis_support.parse_dependencies_only
    )
    assert repository_service.answer_set_programming_adapter.parse_file is (
        repository_answer_set_programming_analysis_support.parse_file
    )


def test_answer_set_programming_adapter_module_aliases_include_module_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "asp-alias-repo"
    (repo_path / "examples").mkdir(parents=True)
    (repo_path / "examples" / "blocks.lp").write_text(
        '#program base.\n'
        "{ move(X,Y,t) : block(X), location(Y), X != Y } = 1.\n"
        "holds(F,0) :- init(F).\n"
        "#show move/3.\n",
        encoding="utf-8",
    )

    aliases = repository_service.answer_set_programming_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="examples/blocks.lp",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "examples/blocks.lp" in aliases
    assert "blocks.lp" in aliases
    assert "blocks" in aliases
    assert "move" in aliases
    assert "holds" in aliases


def test_answer_set_programming_adapter_parse_file_resolves_include_and_symbol_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "examples/bird.lp",
            "examples/include.lp",
        ],
        root_path=Path("/tmp/asp-index"),
    )
    text = (
        '#include "bird.lp".\n'
        "#program base.\n"
        "#external q(X) : p(X).\n"
        "r(X) :- q(X), p(X).\n"
        "#show r/1.\n"
    )

    symbols, dependencies, references = repository_service.answer_set_programming_adapter.parse_file(
        "examples/include.lp",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "base" and symbol.symbol_kind == "program" for symbol in symbols)
    assert any(symbol.symbol_name == "q" and symbol.symbol_kind == "external" for symbol in symbols)
    assert any(symbol.symbol_name == "r" and symbol.symbol_kind == "predicate" for symbol in symbols)
    assert any(
        dependency.target_file == "examples/bird.lp" and dependency.dependency_type == "includes"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("bird",) for reference in references)
    assert any(reference.target_names == ("p",) for reference in references)
    assert any(
        reference.target_file == "examples/include.lp" and reference.target_names == ("q",)
        for reference in references
    )
    assert any(reference.target_names == ("r",) for reference in references)


def test_answer_set_programming_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".lp" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("examples/blocks.lp"),
            text="#program base.\n{ move(X,Y,t) : block(X), location(Y), X != Y } = 1.\n",
        )
        == "answer set programming"
    )
    assert (
        repository_service._language_for_path(
            Path("examples/graph.lp"),
            text="node(1..6).\nedge(1,(2;3;4)).\n",
        )
        == "answer set programming"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/model.lp"),
            text="linear programming notes only\n",
        )
        == "unknown"
    )


def test_candidate_ecosystems_for_path_detects_answer_set_programming_with_repo_context(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "asp-candidate-repo"
    (repo_path / "examples").mkdir(parents=True)
    (repo_path / "examples" / "showa.lp").write_text(
        "{ q(X) : p(X) }.\n"
        "a :- q(1).\n"
        "#show a/0.\n",
        encoding="utf-8",
    )

    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    assert probe_module._candidate_ecosystems_for_path(
        "examples/showa.lp",
        repo_path=repo_path,
    ) == {"answer set programming"}


def test_operational_seed_plan_without_diagnostics_promotes_answer_set_programming_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "asp-profile-repo"
    (repo_path / "examples").mkdir(parents=True)
    (repo_path / "examples" / "bird.lp").write_text(
        "bird(tweety).\n"
        "penguin(polly).\n",
        encoding="utf-8",
    )
    for index in range(4):
        (repo_path / "examples" / f"program_{index}.lp").write_text(
            '#include "bird.lp".\n'
            "#program base.\n"
            f"selected({index}) :- bird(tweety).\n"
            f"#show selected/{1}.\n",
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

    assert "answer set programming" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "answer set programming"
    assert any(path.endswith(".lp") for path in seed_plan["entrypoint_files"])
