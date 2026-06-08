from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_antlr_parser_dispatch as repository_antlr_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    antlr_analysis_support as repository_antlr_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    antlr_primitives as repository_antlr_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-qm", "Initial commit"], check=True)


def test_repository_intelligence_antlr_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["antlr"] is (
        repository_antlr_parser_dispatch._parse_antlr_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["antlr"] is (
        repository_antlr_parser_dispatch._parse_antlr_dependencies_only
    )


def test_repository_intelligence_antlr_helpers_are_modularized() -> None:
    assert repository_service.antlr_adapter.has_antlr_path_hints is (
        repository_antlr_primitives.has_antlr_path_hints
    )
    assert repository_service.antlr_adapter.is_probable_antlr_source is (
        repository_antlr_analysis_support.is_probable_antlr_source
    )
    assert repository_service.antlr_adapter.iter_rule_entries is (
        repository_antlr_primitives.iter_rule_entries
    )
    assert repository_service.antlr_adapter.iter_dependency_entries is (
        repository_antlr_primitives.iter_dependency_entries
    )
    assert repository_service.antlr_adapter.iter_reference_entries is (
        repository_antlr_primitives.iter_reference_entries
    )
    assert repository_service.antlr_adapter.module_aliases_for_path is (
        repository_antlr_analysis_support.module_aliases_for_path
    )
    assert repository_service.antlr_adapter.parse_dependencies_only is (
        repository_antlr_analysis_support.parse_dependencies_only
    )
    assert repository_service.antlr_adapter.parse_file is (
        repository_antlr_analysis_support.parse_file
    )


def test_antlr_adapter_module_aliases_include_grammar_name(tmp_path: Path) -> None:
    repo_path = tmp_path / "antlr-alias-repo"
    (repo_path / "grammars").mkdir(parents=True)
    (repo_path / "grammars" / "Expr.g4").write_text(
        "grammar Expr;\nexpr: term PLUS term;\nterm: INT;\nPLUS: '+';\nINT: [0-9]+;\n",
        encoding="utf-8",
    )

    aliases = repository_service.antlr_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="grammars/Expr.g4",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "grammars/Expr.g4" in aliases
    assert "Expr" in aliases


def test_antlr_adapter_parse_dependencies_resolves_import_and_token_vocab(tmp_path: Path) -> None:
    repo_path = tmp_path / "antlr-deps-repo"
    (repo_path / "grammars").mkdir(parents=True)
    (repo_path / "grammars" / "CommonLexer.g4").write_text(
        "lexer grammar CommonLexer;\nID: [a-z]+;\n",
        encoding="utf-8",
    )
    (repo_path / "grammars" / "SharedRules.g4").write_text(
        "parser grammar SharedRules;\nshared: ID;\n",
        encoding="utf-8",
    )
    parser_path = repo_path / "grammars" / "ExprParser.g4"
    parser_path.write_text(
        "parser grammar ExprParser;\n"
        "options { tokenVocab=CommonLexer; }\n"
        "import SharedRules;\n"
        "expr: shared ID;\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        [
            "grammars/CommonLexer.g4",
            "grammars/SharedRules.g4",
            "grammars/ExprParser.g4",
        ],
        root_path=repo_path,
    )
    text = parser_path.read_text(encoding="utf-8")

    dependencies = repository_service.antlr_adapter.parse_dependencies_only(
        "grammars/ExprParser.g4",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert {dependency.target_file for dependency in dependencies} == {
        "grammars/CommonLexer.g4",
        "grammars/SharedRules.g4",
    }


def test_antlr_language_detection_supports_g4_suffix() -> None:
    assert ".g4" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("grammars/Expr.g4"),
        text="grammar Expr;\nexpr: term;\nterm: INT;\nINT: [0-9]+;\n",
    ) == "antlr"


def test_operational_seed_plan_without_diagnostics_promotes_antlr_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "antlr-profile-repo"
    (repo_path / "grammars").mkdir(parents=True)
    (repo_path / "grammars" / "ExampleLexer.g4").write_text(
        "lexer grammar ExampleLexer;\nID: [a-z]+;\nWS: [ \\t\\r\\n]+ -> skip;\n",
        encoding="utf-8",
    )
    (repo_path / "grammars" / "ExampleParser.g4").write_text(
        "parser grammar ExampleParser;\noptions { tokenVocab=ExampleLexer; }\nexpr: ID;\n",
        encoding="utf-8",
    )
    (repo_path / "grammars" / "SharedRules.g4").write_text(
        "parser grammar SharedRules;\nshared: ID;\n",
        encoding="utf-8",
    )
    (repo_path / "tools").mkdir(parents=True)
    (repo_path / "tools" / "helper.py").write_text("print('antlr')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "antlr" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "antlr"
    assert "grammars/ExampleParser.g4" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_antlr_first_in_java_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "antlr-mixed-java-repo"
    (repo_path / "grammars").mkdir(parents=True)
    (repo_path / "grammars" / "ExampleLexer.g4").write_text(
        "lexer grammar ExampleLexer;\nID: [a-z]+;\n",
        encoding="utf-8",
    )
    (repo_path / "grammars" / "ExampleParser.g4").write_text(
        "parser grammar ExampleParser;\noptions { tokenVocab=ExampleLexer; }\nexpr: ID;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "java" / "pkg").mkdir(parents=True)
    for index in range(18):
        (repo_path / "src" / "main" / "java" / "pkg" / f"Cls{index}.java").write_text(
            f"package pkg; class Cls{index} {{ int value() {{ return {index}; }} }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "antlr" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "antlr"
    assert "java" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_antlr_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "antlr-graph-repo"
    (repo_path / "grammars").mkdir(parents=True)
    (repo_path / "grammars" / "Expr.g4").write_text(
        "grammar Expr;\n"
        "expr: term PLUS term;\n"
        "term: INT;\n"
        "PLUS: '+';\n"
        "INT: [0-9]+;\n"
        "WS: [ \\t\\r\\n]+ -> skip;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["grammars/**/*.g4", "grammars/*.g4", "*.g4"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    expr_symbol_id = symbol_ids[("grammars/Expr.g4", "expr")]
    term_symbol_id = symbol_ids[("grammars/Expr.g4", "term")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{expr_symbol_id}"
        and str(row["target_node"]) == f"symbol:{term_symbol_id}"
        for row in graph
    )

