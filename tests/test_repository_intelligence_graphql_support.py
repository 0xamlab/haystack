from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_graphql_parser_dispatch as repository_graphql_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    graphql_analysis_support as repository_graphql_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    graphql_primitives as repository_graphql_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_graphql_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["graphql"] is (
        repository_graphql_parser_dispatch._parse_graphql_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["graphql"] is (
        repository_graphql_parser_dispatch._parse_graphql_dependencies_only
    )


def test_repository_intelligence_graphql_helpers_are_modularized() -> None:
    assert repository_service.graphql_adapter.strip_comments is (
        repository_graphql_primitives.strip_comments
    )
    assert repository_service.graphql_adapter.has_graphql_path_hints is (
        repository_graphql_primitives.has_graphql_path_hints
    )
    assert repository_service.graphql_adapter.is_probable_graphql_source is (
        repository_graphql_analysis_support.is_probable_graphql_source
    )
    assert repository_service.graphql_adapter.module_aliases_for_path is (
        repository_graphql_analysis_support.module_aliases_for_path
    )
    assert repository_service.graphql_adapter.parse_dependencies_only is (
        repository_graphql_analysis_support.parse_dependencies_only
    )
    assert repository_service.graphql_adapter.parse_file is (
        repository_graphql_analysis_support.parse_file
    )


def test_graphql_adapter_parse_file_resolves_imports_and_type_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "graphql-parse-repo"
    (repo_path / "schema").mkdir(parents=True)
    (repo_path / "schema" / "shared.graphql").write_text(
        "type User { id: ID! name: String! }\n",
        encoding="utf-8",
    )
    (repo_path / "schema" / "query.graphql").write_text(
        '# import "shared.graphql"\n'
        "type Query {\n"
        "  viewer: User\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["schema/shared.graphql", "schema/query.graphql"],
        root_path=repo_path,
    )
    text = (repo_path / "schema" / "query.graphql").read_text(encoding="utf-8")

    aliases = repository_service.graphql_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="schema/query.graphql",
        stable_identifier=repository_service._stable_identifier,
    )
    symbols, dependencies, references = repository_service.graphql_adapter.parse_file(
        "schema/query.graphql",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert "schema/query.graphql" in aliases
    assert "schema.query" in aliases
    assert "Query" in aliases
    assert any(symbol.symbol_name == "Query" for symbol in symbols)
    assert any(dependency.target_file == "schema/shared.graphql" for dependency in dependencies)
    assert any(reference.target_file == "schema/shared.graphql" for reference in references)
    assert any(reference.target_names == ("User",) for reference in references)


def test_graphql_language_detection_supports_ranked_suffixes_without_overclaiming() -> None:
    assert ".graphql" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("schema/query.graphql"),
        text="type Query { viewer: User }\n",
    ) == "graphql"
    assert repository_service._language_for_path(
        Path("doc/example_query.gql"),
        text="{ viewer { id } }\n",
    ) == "graphql"
    assert repository_service._language_for_path(
        Path("notes/schema.graphql"),
        text="plain notes\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_graphql_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "graphql-profile-repo"
    (repo_path / "schema").mkdir(parents=True)
    (repo_path / "schema" / "shared.graphql").write_text(
        "type User { id: ID! }\n",
        encoding="utf-8",
    )
    for index in range(4):
        (repo_path / "schema" / f"query_{index}.graphql").write_text(
            '# import "shared.graphql"\n'
            f"type Query{index} {{ viewer: User }}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.py").write_text(
        "def helper() -> int:\n    return 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "graphql" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "graphql"
    assert any(path.endswith(".graphql") for path in seed_plan["entrypoint_files"])
