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
    repository_intelligence_yacc_parser_dispatch as repository_intelligence_yacc_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    yacc_analysis_support as repository_yacc_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    yacc_primitives as repository_yacc_primitives,
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


def test_repository_intelligence_yacc_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["yacc"] is (
        repository_intelligence_yacc_parser_dispatch._parse_yacc_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["yacc"] is (
        repository_intelligence_yacc_parser_dispatch._parse_yacc_dependencies_only
    )


def test_repository_intelligence_yacc_helpers_are_modularized() -> None:
    assert repository_service.yacc_adapter.has_yacc_path_hints is (
        repository_yacc_primitives.has_yacc_path_hints
    )
    assert repository_service.yacc_adapter.is_probable_yacc_source is (
        repository_yacc_analysis_support.is_probable_yacc_source
    )
    assert repository_service.yacc_adapter.iter_reference_entries is (
        repository_yacc_primitives.iter_reference_entries
    )
    assert repository_service.yacc_adapter.module_aliases_for_path is (
        repository_yacc_analysis_support.module_aliases_for_path
    )
    assert repository_service.yacc_adapter.parse_file is repository_yacc_analysis_support.parse_file


def test_yacc_adapter_parse_file_extracts_local_rule_references() -> None:
    text = "%token NUMBER\n%%\nexpr: term ;\nterm: NUMBER ;\n%%\n"

    symbols, dependencies, references = repository_service.yacc_adapter.parse_file(
        "grammar/main.y",
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert not dependencies
    assert any(symbol.symbol_name == "expr" for symbol in symbols)
    assert any(symbol.symbol_name == "term" for symbol in symbols)
    assert any(reference.target_names == ("term",) for reference in references)


def test_yacc_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".y" in repository_service._TEXT_FILE_SUFFIXES
    assert ".yacc" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("grammar/main.y"),
            text="%token NUMBER\n%%\nexpr: term ;\nterm: NUMBER ;\n%%\n",
        )
        == "yacc"
    )
    assert (
        repository_service._language_for_path(
            Path("grammar/main.y"),
            text="plain notes without grammar markers\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_yacc_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "yacc-profile-repo"
    (repo_path / "grammar").mkdir(parents=True)
    for index in range(6):
        (repo_path / "grammar" / f"parser_{index}.y").write_text(
            f"%token NUMBER\n%%\nexpr{index}: term{index} ;\nterm{index}: NUMBER ;\n%%\n",
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

    assert "yacc" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "yacc"


def test_repository_snapshot_graph_contains_yacc_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "yacc-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.y").write_text(
        "%token NUMBER\n%%\nexpr: term ;\nterm: NUMBER ;\n%%\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.y", "*.yacc"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    expr_symbol_id = symbol_ids[("main.y", "expr")]
    term_symbol_id = symbol_ids[("main.y", "term")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{expr_symbol_id}"
        and str(row["target_node"]) == f"symbol:{term_symbol_id}"
        for row in graph
    )
