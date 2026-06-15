from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_plpgsql_parser_dispatch as repository_plpgsql_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    plpgsql_analysis_support as repository_plpgsql_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    plpgsql_primitives as repository_plpgsql_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_plpgsql_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["plpgsql"] is (
        repository_plpgsql_parser_dispatch._parse_plpgsql_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["plpgsql"] is (
        repository_plpgsql_parser_dispatch._parse_plpgsql_dependencies_only
    )


def test_repository_intelligence_plpgsql_helpers_are_modularized() -> None:
    assert repository_service.plpgsql_adapter.strip_comments is (
        repository_plpgsql_primitives.strip_comments
    )
    assert repository_service.plpgsql_adapter.has_plpgsql_path_hints is (
        repository_plpgsql_primitives.has_plpgsql_path_hints
    )
    assert repository_service.plpgsql_adapter.is_probable_plpgsql_source is (
        repository_plpgsql_analysis_support.is_probable_plpgsql_source
    )
    assert repository_service.plpgsql_adapter.module_aliases_for_path is (
        repository_plpgsql_analysis_support.module_aliases_for_path
    )
    assert repository_service.plpgsql_adapter.parse_dependencies_only is (
        repository_plpgsql_analysis_support.parse_dependencies_only
    )
    assert repository_service.plpgsql_adapter.parse_file is (
        repository_plpgsql_analysis_support.parse_file
    )


def test_plpgsql_adapter_parse_file_resolves_function_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "plpgsql-parse-repo"
    (repo_path / "db").mkdir(parents=True)
    (repo_path / "db" / "shared.pgsql").write_text(
        "create or replace function shared_fn() returns integer as $$\n"
        "begin\n"
        "  return 7;\n"
        "end;\n"
        "$$ language plpgsql;\n",
        encoding="utf-8",
    )
    (repo_path / "db" / "app.pgsql").write_text(
        "create or replace function app_fn() returns integer as $$\n"
        "begin\n"
        "  return shared_fn();\n"
        "end;\n"
        "$$ language plpgsql;\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["db/shared.pgsql", "db/app.pgsql"],
        root_path=repo_path,
    )
    text = (repo_path / "db" / "app.pgsql").read_text(encoding="utf-8")

    aliases = repository_service.plpgsql_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="db/app.pgsql",
        stable_identifier=repository_service._stable_identifier,
    )
    symbols, dependencies, references = repository_service.plpgsql_adapter.parse_file(
        "db/app.pgsql",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert "db/app.pgsql" in aliases
    assert "db.app" in aliases
    assert any(symbol["symbol_name"] == "app_fn" for symbol in symbols)
    assert any(dependency["target_file"] == "db/shared.pgsql" for dependency in dependencies)
    assert any(reference["target_file"] == "db/shared.pgsql" for reference in references)
    assert any(reference["target_names"] == ("shared_fn",) for reference in references)


def test_plpgsql_language_detection_supports_pgsql_and_sql_without_overclaiming() -> None:
    assert ".pgsql" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("db/functions/app.pgsql"),
        text="create function app_fn() returns int as $$ begin return 1; end; $$ language plpgsql;",
    ) == "plpgsql"
    assert repository_service._language_for_path(
        Path("db/functions/app.sql"),
        text="create function app_fn() returns int as $$ begin return 1; end; $$ language plpgsql;",
    ) == "plpgsql"
    assert repository_service._language_for_path(
        Path("db/functions/notes.sql"),
        text="select 1;\n",
    ) == "sql"


def test_operational_seed_plan_without_diagnostics_promotes_plpgsql_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "plpgsql-profile-repo"
    (repo_path / "db" / "functions").mkdir(parents=True)
    for index in range(4):
        (repo_path / "db" / "functions" / f"fn_{index}.sql").write_text(
            "create or replace function fn_{0}() returns integer as $$\n"
            "begin\n"
            "  return {0};\n"
            "end;\n"
            "$$ language plpgsql;\n".format(index),
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

    assert "plpgsql" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "plpgsql"
    assert any(path.endswith(".sql") for path in seed_plan["entrypoint_files"])
