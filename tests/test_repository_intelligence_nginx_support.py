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
    repository_intelligence_nginx_parser_dispatch as repository_intelligence_nginx_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    nginx_analysis_support as repository_nginx_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nginx_primitives as repository_nginx_primitives,
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


def test_repository_intelligence_nginx_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["nginx"] is (
        repository_intelligence_nginx_parser_dispatch._parse_nginx_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["nginx"] is (
        repository_intelligence_nginx_parser_dispatch._parse_nginx_dependencies_only
    )


def test_repository_intelligence_nginx_helpers_are_modularized() -> None:
    assert repository_service.nginx_adapter.strip_comments is (
        repository_nginx_primitives.strip_comments
    )
    assert repository_service.nginx_adapter.has_nginx_path_hints is (
        repository_nginx_primitives.has_nginx_path_hints
    )
    assert repository_service.nginx_adapter.is_probable_nginx_source is (
        repository_nginx_analysis_support.is_probable_nginx_source
    )
    assert repository_service.nginx_adapter.module_aliases_for_path is (
        repository_nginx_primitives.module_aliases_for_path
    )
    assert repository_service.nginx_adapter.parse_dependencies_only is (
        repository_nginx_analysis_support.parse_dependencies_only
    )
    assert repository_service.nginx_adapter.parse_file is (
        repository_nginx_analysis_support.parse_file
    )


def test_nginx_adapter_parse_file_extracts_include_edges_and_upstream_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "conf/nginx.conf",
            "conf/mime.types",
            "conf/sites-enabled/default.conf",
        ],
        root_path=Path("/tmp/nginx-index"),
    )
    text = (
        "include mime.types;\n"
        "http {\n"
        "  upstream app {\n"
        "    server 127.0.0.1:9000;\n"
        "  }\n"
        "  server {\n"
        "    listen 80;\n"
        "    location / {\n"
        "      proxy_pass http://app;\n"
        "    }\n"
        "  }\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.nginx_adapter.parse_file(
        "conf/nginx.conf",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "app" for symbol in symbols)
    assert any(dependency.dependency_type == "include" for dependency in dependencies)
    assert any(reference.target_names == ("app",) for reference in references)


def test_nginx_language_detection_supports_known_paths_without_overclaiming() -> None:
    assert (
        repository_service._language_for_path(
            Path("conf/nginx.conf"),
            text="worker_processes 1;\nevents { worker_connections 1024; }\nhttp { server { listen 80; } }\n",
        )
        == "nginx"
    )
    assert (
        repository_service._language_for_path(
            Path("config/dev.conf"),
            text="server_name example.test;\nlocation / { proxy_pass http://app; }\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_nginx_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nginx-profile-repo"
    (repo_path / "conf").mkdir(parents=True)
    (repo_path / "sites-enabled").mkdir(parents=True)
    (repo_path / "conf" / "nginx.conf").write_text(
        "worker_processes 1;\nevents { worker_connections 1024; }\nhttp { include ../sites-enabled/*.conf; }\n",
        encoding="utf-8",
    )
    for index in range(4):
        (repo_path / "sites-enabled" / f"site-{index}.conf").write_text(
            f"server {{\n  listen 80;\n  server_name site-{index}.test;\n  location / {{ proxy_pass http://app; }}\n}}\n",
            encoding="utf-8",
        )
    (repo_path / "conf" / "mime.types").write_text(
        "types {\n  text/html html;\n}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["conf", "sites-enabled"],
        max_files=128,
    )

    assert "nginx" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "nginx"


def test_repository_snapshot_graph_contains_nginx_include_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "nginx-graph-repo"
    (repo_path / "conf").mkdir(parents=True)
    (repo_path / "conf" / "nginx.conf").write_text(
        "worker_processes 1;\nevents { worker_connections 1024; }\nhttp { include mime.types; }\n",
        encoding="utf-8",
    )
    (repo_path / "conf" / "mime.types").write_text(
        "types {\n  text/html html;\n}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["conf"],
            include_patterns=["conf/**/*.conf", "conf/*", "*.conf"],
            max_files=16,
        ),
    )
    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "include"
        and str(row["source_node"]) == "file:conf/nginx.conf"
        and str(row["target_node"]) == "file:conf/mime.types"
        for row in graph_rows
    )
