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
    repository_intelligence_moonscript_parser_dispatch as repository_intelligence_moonscript_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    moonscript_analysis_support as repository_moonscript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    moonscript_primitives as repository_moonscript_primitives,
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


def test_repository_intelligence_moonscript_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["moonscript"] is (
        repository_intelligence_moonscript_parser_dispatch._parse_moonscript_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["moonscript"] is (
        repository_intelligence_moonscript_parser_dispatch._parse_moonscript_dependencies_only
    )


def test_repository_intelligence_moonscript_helpers_are_modularized() -> None:
    assert repository_service.moonscript_adapter.has_moonscript_path_hints is (
        repository_moonscript_primitives.has_moonscript_path_hints
    )
    assert repository_service.moonscript_adapter.is_probable_moonscript_source is (
        repository_moonscript_analysis_support.is_probable_moonscript_source
    )
    assert repository_service.moonscript_adapter.iter_reference_entries is (
        repository_moonscript_primitives.iter_reference_entries
    )
    assert repository_service.moonscript_adapter.module_aliases_for_path is (
        repository_moonscript_analysis_support.module_aliases_for_path
    )
    assert repository_service.moonscript_adapter.parse_file is (
        repository_moonscript_analysis_support.parse_file
    )


def test_moonscript_adapter_tracks_class_relations_and_imports() -> None:
    text = 'Base = ->\nclass Child extends Base\nhelper = require "./helper"\n'
    module_index = {"src/helper.moon": "src/helper.moon", "helper.moon": "src/helper.moon"}

    symbols, dependencies, references = repository_service.moonscript_adapter.parse_file(
        "src/main.moon",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "Base" for symbol in symbols)
    assert any(symbol.symbol_name == "Child" for symbol in symbols)
    assert any(reference.target_names == ("Base",) for reference in references)
    assert any(dependency.dependency_type == "imports" for dependency in dependencies)


def test_moonscript_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".moon" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("src/main.moon"),
            text='class Child extends Base\nrun = -> print "ok"\n',
        )
        == "moonscript"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.moon"),
            text="plain notes without moonscript markers\n",
        )
        == "unknown"
    )


def test_repository_snapshot_graph_contains_moonscript_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "moonscript-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.moon").write_text(
        "Base = ->\nclass Child extends Base\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.moon"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    child_symbol_id = symbol_ids[("main.moon", "Child")]
    base_symbol_id = symbol_ids[("main.moon", "Base")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{child_symbol_id}"
        and str(row["target_node"]) == f"symbol:{base_symbol_id}"
        for row in graph
    )
