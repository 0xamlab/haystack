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
    repository_intelligence_lex_parser_dispatch as repository_intelligence_lex_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    lex_analysis_support as repository_lex_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    lex_primitives as repository_lex_primitives,
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


def test_repository_intelligence_lex_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["lex"] is (
        repository_intelligence_lex_parser_dispatch._parse_lex_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["lex"] is (
        repository_intelligence_lex_parser_dispatch._parse_lex_dependencies_only
    )


def test_repository_intelligence_lex_helpers_are_modularized() -> None:
    assert repository_service.lex_adapter.has_lex_path_hints is (
        repository_lex_primitives.has_lex_path_hints
    )
    assert repository_service.lex_adapter.is_probable_lex_source is (
        repository_lex_analysis_support.is_probable_lex_source
    )
    assert repository_service.lex_adapter.iter_reference_entries is (
        repository_lex_primitives.iter_reference_entries
    )
    assert repository_service.lex_adapter.module_aliases_for_path is (
        repository_lex_analysis_support.module_aliases_for_path
    )
    assert repository_service.lex_adapter.parse_file is repository_lex_analysis_support.parse_file


def test_lex_adapter_parse_file_extracts_local_definition_references() -> None:
    text = "DIGIT   [0-9]\n%%\n{DIGIT}+    { return NUMBER; }\n%%\n"

    symbols, dependencies, references = repository_service.lex_adapter.parse_file(
        "scanner/main.l",
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert not dependencies
    assert any(symbol.symbol_name == "DIGIT" for symbol in symbols)
    assert any(reference.target_names == ("DIGIT",) for reference in references)


def test_lex_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".l" in repository_service._TEXT_FILE_SUFFIXES
    assert ".lex" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("scanner/main.l"),
            text="DIGIT   [0-9]\n%%\n{DIGIT}+    { return NUMBER; }\n%%\n",
        )
        == "lex"
    )
    assert (
        repository_service._language_for_path(
            Path("scanner/main.l"),
            text="plain notes without scanner markers\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_lex_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lex-profile-repo"
    (repo_path / "scanner").mkdir(parents=True)
    for index in range(6):
        (repo_path / "scanner" / f"token_{index}.l").write_text(
            f"DIGIT{index}   [0-9]\n%%\n{{DIGIT{index}}}+    {{ return NUMBER; }}\n%%\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"helper_{index}.py").write_text(
            "print('helper')\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "lex" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "lex"


def test_repository_snapshot_graph_contains_lex_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "lex-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.l").write_text(
        "DIGIT   [0-9]\n%%\n{DIGIT}+    { return NUMBER; }\n%%\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.l", "*.lex"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    main_symbol_id = symbol_ids[("main.l", "main")]
    digit_symbol_id = symbol_ids[("main.l", "DIGIT")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{digit_symbol_id}"
        for row in graph
    )
