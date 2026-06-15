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
    repository_intelligence_thrift_parser_dispatch as repository_intelligence_thrift_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    thrift_analysis_support as repository_thrift_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    thrift_primitives as repository_thrift_primitives,
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


def test_repository_intelligence_thrift_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["thrift"] is (
        repository_intelligence_thrift_parser_dispatch._parse_thrift_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["thrift"] is (
        repository_intelligence_thrift_parser_dispatch._parse_thrift_dependencies_only
    )


def test_repository_intelligence_thrift_helpers_are_modularized() -> None:
    assert repository_service.thrift_adapter.has_thrift_path_hints is (
        repository_thrift_primitives.has_thrift_path_hints
    )
    assert repository_service.thrift_adapter.is_probable_thrift_source is (
        repository_thrift_analysis_support.is_probable_thrift_source
    )
    assert repository_service.thrift_adapter.iter_import_entries is (
        repository_thrift_primitives.iter_import_entries
    )
    assert repository_service.thrift_adapter.module_aliases_for_path is (
        repository_thrift_primitives.module_aliases_for_path
    )
    assert repository_service.thrift_adapter.parse_file is (
        repository_thrift_analysis_support.parse_file
    )


def test_thrift_adapter_parse_file_extracts_imports_and_type_references() -> None:
    module_index = {"common.thrift": "idl/common.thrift"}
    text = (
        'include "common.thrift"\n'
        "namespace py demo.api\n"
        "struct User {\n"
        "  1: required Address address\n"
        "}\n"
        "struct Address {\n"
        "  1: required string line1\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.thrift_adapter.parse_file(
        "idl/user.thrift",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "User" for symbol in symbols)
    assert any(symbol.symbol_name == "Address" for symbol in symbols)
    assert any(dependency.dependency_type == "imports" for dependency in dependencies)
    assert any(reference.target_names == ("Address",) for reference in references)


def test_thrift_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".thrift" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("idl/user.thrift"),
            text="namespace py demo.api\nstruct User {\n  1: string name\n}\n",
        )
        == "thrift"
    )
    assert (
        repository_service._language_for_path(
            Path("idl/user.thrift"),
            text="plain notes without thrift declarations\n",
        )
        == "unknown"
    )


def test_repository_snapshot_graph_contains_thrift_dependency_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "thrift-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "common.thrift").write_text(
        "namespace py demo.api\nstruct Address {\n  1: required string line1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "user.thrift").write_text(
        'include "common.thrift"\n'
        "namespace py demo.api\n"
        "struct User {\n"
        "  1: required Address address\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.thrift"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:user.thrift"
        and str(row["target_node"]) == "file:common.thrift"
        for row in graph
    )
