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
    repository_intelligence_xquery_parser_dispatch as repository_intelligence_xquery_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    xquery_analysis_support as repository_xquery_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    xquery_primitives as repository_xquery_primitives,
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


def test_repository_intelligence_xquery_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["xquery"] is (
        repository_intelligence_xquery_parser_dispatch._parse_xquery_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["xquery"] is (
        repository_intelligence_xquery_parser_dispatch._parse_xquery_dependencies_only
    )


def test_repository_intelligence_xquery_helpers_are_modularized() -> None:
    assert repository_service.xquery_adapter.has_xquery_path_hints is (
        repository_xquery_primitives.has_xquery_path_hints
    )
    assert repository_service.xquery_adapter.is_probable_xquery_source is (
        repository_xquery_analysis_support.is_probable_xquery_source
    )
    assert repository_service.xquery_adapter.iter_dependency_entries is (
        repository_xquery_primitives.iter_dependency_entries
    )
    assert repository_service.xquery_adapter.module_aliases_for_path is (
        repository_xquery_analysis_support.module_aliases_for_path
    )
    assert repository_service.xquery_adapter.parse_file is (
        repository_xquery_analysis_support.parse_file
    )


def test_xquery_adapter_parse_file_extracts_import_dependencies_and_function_references() -> None:
    module_index = {
        "lib/common.xqm": "lib/common.xqm",
        "common.xqm": "lib/common.xqm",
    }
    text = (
        'xquery version "3.1";\n'
        'import module namespace common = "urn:common" at "../lib/common.xqm";\n'
        "declare function local:helper() { common:run() };\n"
        "declare function local:runner() { local:helper() };\n"
    )

    symbols, dependencies, references = repository_service.xquery_adapter.parse_file(
        "queries/main.xqy",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "lib/common.xqm" for dependency in dependencies)
    assert any(symbol.symbol_name == "local:helper" for symbol in symbols)
    assert any(symbol.symbol_name == "local:runner" for symbol in symbols)
    assert any(reference.target_names == ("local:helper",) for reference in references)
    assert any(reference.target_file == "lib/common.xqm" for reference in references)


def test_xquery_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".xq" in repository_service._TEXT_FILE_SUFFIXES
    assert ".xqy" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("queries/main.xqy"),
            text='xquery version "3.1";\ndeclare function local:helper() { "ok" };\n',
        )
        == "xquery"
    )
    assert (
        repository_service._language_for_path(
            Path("queries/main.xqy"),
            text="plain notes without xquery markers\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_xquery_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "xquery-profile-repo"
    (repo_path / "queries").mkdir(parents=True)
    for index in range(6):
        (repo_path / "queries" / f"module_{index}.xqy").write_text(
            'xquery version "3.1";\n'
            f"declare function local:helper{index}() {{ \"ok\" }};\n",
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

    assert "xquery" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "xquery"


def test_repository_snapshot_graph_contains_xquery_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "xquery-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.xqy").write_text(
        'xquery version "3.1";\n'
        "declare function local:helper() { 1 };\n"
        "declare function local:runner() { local:helper() };\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.xq", "*.xquery", "*.xqy", "*.xql", "*.xqm"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    runner_symbol_id = symbol_ids[("main.xqy", "local:runner")]
    helper_symbol_id = symbol_ids[("main.xqy", "local:helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
