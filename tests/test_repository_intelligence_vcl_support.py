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
    repository_intelligence_vcl_parser_dispatch as repository_intelligence_vcl_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    vcl_analysis_support as repository_vcl_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vcl_primitives as repository_vcl_primitives,
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


def test_repository_intelligence_vcl_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["vcl"] is (
        repository_intelligence_vcl_parser_dispatch._parse_vcl_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["vcl"] is (
        repository_intelligence_vcl_parser_dispatch._parse_vcl_dependencies_only
    )


def test_repository_intelligence_vcl_helpers_are_modularized() -> None:
    assert repository_service.vcl_adapter.strip_comments is (
        repository_vcl_primitives.strip_comments
    )
    assert repository_service.vcl_adapter.has_vcl_path_hints is (
        repository_vcl_primitives.has_vcl_path_hints
    )
    assert repository_service.vcl_adapter.is_probable_vcl_source is (
        repository_vcl_analysis_support.is_probable_vcl_source
    )
    assert repository_service.vcl_adapter.module_aliases_for_path is (
        repository_vcl_primitives.module_aliases_for_path
    )
    assert repository_service.vcl_adapter.parse_dependencies_only is (
        repository_vcl_analysis_support.parse_dependencies_only
    )
    assert repository_service.vcl_adapter.parse_file is (
        repository_vcl_analysis_support.parse_file
    )


def test_vcl_adapter_parse_file_extracts_include_edges_and_local_references() -> None:
    module_index = {"common.vcl": "common.vcl"}
    text = (
        'include "common.vcl";\n'
        "vcl 4.1;\n"
        "backend api {\n"
        '  .host = "127.0.0.1";\n'
        '  .port = "8080";\n'
        "}\n"
        "sub authorize {\n}\n"
        "sub vcl_recv {\n"
        "  call authorize;\n"
        "  set req.backend_hint = api;\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.vcl_adapter.parse_file(
        "default.vcl",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "api" for symbol in symbols)
    assert any(symbol.symbol_name == "authorize" for symbol in symbols)
    assert any(dependency.dependency_type == "include" for dependency in dependencies)
    assert any(reference.target_names == ("authorize",) for reference in references)
    assert any(reference.target_names == ("api",) for reference in references)


def test_vcl_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".vcl" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("etc/default.vcl"),
            text='vcl 4.1;\nbackend default { .host = "127.0.0.1"; }\n',
        )
        == "vcl"
    )
    assert (
        repository_service._language_for_path(
            Path("etc/default.vcl"),
            text="plain notes without vcl markers\n",
        )
        == "unknown"
    )


def test_repository_snapshot_graph_contains_vcl_include_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "vcl-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "common.vcl").write_text(
        "vcl 4.1;\nsub helper {\n}\n",
        encoding="utf-8",
    )
    (repo_path / "default.vcl").write_text(
        'include "common.vcl";\n'
        "vcl 4.1;\n"
        "sub vcl_recv {\n  call helper;\n}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.vcl"],
            max_files=16,
        ),
    )
    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "include"
        and str(row["source_node"]) == "file:default.vcl"
        and str(row["target_node"]) == "file:common.vcl"
        for row in graph_rows
    )
