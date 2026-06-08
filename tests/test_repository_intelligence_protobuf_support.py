from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_protobuf_parser_dispatch as repository_protobuf_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    protobuf_analysis_support as repository_protobuf_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    protobuf_primitives as repository_protobuf_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _build_connected_dependency_map,
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


def test_repository_intelligence_protobuf_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["protobuf"] is (
        repository_protobuf_parser_dispatch._parse_protobuf_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["protobuf"] is (
        repository_protobuf_parser_dispatch._parse_protobuf_dependencies_only
    )


def test_repository_intelligence_protobuf_helpers_are_modularized() -> None:
    assert repository_service.protobuf_adapter.strip_comments is (
        repository_protobuf_primitives.strip_comments
    )
    assert repository_service.protobuf_adapter.has_protobuf_path_hints is (
        repository_protobuf_primitives.has_protobuf_path_hints
    )
    assert repository_service.protobuf_adapter.is_probable_protobuf_source is (
        repository_protobuf_primitives.is_probable_protobuf_source
    )
    assert repository_service.protobuf_adapter.is_probable_protobuf_config is (
        repository_protobuf_primitives.is_probable_protobuf_config
    )
    assert repository_service.protobuf_adapter.iter_import_entries is (
        repository_protobuf_primitives.iter_import_entries
    )
    assert repository_service.protobuf_adapter.iter_symbol_entries is (
        repository_protobuf_primitives.iter_symbol_entries
    )
    assert repository_service.protobuf_adapter.iter_reference_entries is (
        repository_protobuf_primitives.iter_reference_entries
    )
    assert repository_service.protobuf_adapter.package_name_from_text is (
        repository_protobuf_primitives.package_name_from_text
    )
    assert repository_service.protobuf_adapter.module_aliases_for_path is (
        repository_protobuf_analysis_support.module_aliases_for_path
    )
    assert repository_service.protobuf_adapter.resolve_import is (
        repository_protobuf_analysis_support.resolve_import
    )
    assert repository_service.protobuf_adapter.parse_dependencies_only is (
        repository_protobuf_analysis_support.parse_dependencies_only
    )
    assert repository_service.protobuf_adapter.parse_file is (
        repository_protobuf_analysis_support.parse_file
    )


def test_protobuf_adapter_module_aliases_include_package_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "protobuf-alias-repo"
    (repo_path / "apis" / "demo").mkdir(parents=True)
    (repo_path / "apis" / "demo" / "types.proto").write_text(
        'syntax = "proto3";\n'
        "package demo.common;\n"
        "message User {}\n"
        "service Directory {\n"
        "  rpc Lookup(User) returns (User);\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.protobuf_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="apis/demo/types.proto",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "apis/demo/types.proto" in aliases
    assert "apis/demo/types" in aliases
    assert "apis.demo.types" in aliases
    assert "demo.common" in aliases
    assert "User" in aliases
    assert "Directory" in aliases
    assert "Lookup" in aliases
    assert "demo.common.User" in aliases


def test_protobuf_adapter_parse_file_resolves_imports_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "protobuf-parse-repo"
    (repo_path / "common").mkdir(parents=True)
    (repo_path / "service").mkdir(parents=True)
    (repo_path / "common" / "types.proto").write_text(
        'syntax = "proto3";\n'
        "package demo.common;\n"
        "message User {}\n",
        encoding="utf-8",
    )
    (repo_path / "service" / "api.proto").write_text(
        'syntax = "proto3";\n'
        "package demo.service;\n"
        'import "common/types.proto";\n'
        "service AccountService {\n"
        "  rpc GetUser(demo.common.User) returns (demo.common.User);\n"
        "}\n"
        "message Wrapper {\n"
        "  demo.common.User user = 1;\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["service/api.proto", "common/types.proto"],
        root_path=repo_path,
    )
    text = (repo_path / "service" / "api.proto").read_text(encoding="utf-8")

    dependencies = repository_service.protobuf_adapter.parse_dependencies_only(
        "service/api.proto",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.protobuf_adapter.parse_file(
        "service/api.proto",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "common/types.proto" for dependency in dependencies)
    assert any(symbol.symbol_name == "AccountService" for symbol in symbols)
    assert any(symbol.symbol_name == "GetUser" for symbol in symbols)
    assert any(
        reference.target_file == "common/types.proto" and "User" in reference.target_names
        for reference in references
    )


def test_protobuf_language_detection_supports_proto_and_buf_configs() -> None:
    assert repository_service._language_for_path(Path("apis/demo.proto")) == "protobuf"
    assert (
        repository_service._language_for_path(Path("buf.yaml"), text="version: v1\n")
        == "protobuf"
    )


def test_operational_seed_plan_without_diagnostics_promotes_protobuf_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "protobuf-profile-repo"
    (repo_path / "protos" / "common").mkdir(parents=True)
    (repo_path / "protos" / "service").mkdir(parents=True)
    (repo_path / "protos" / "common" / "types.proto").write_text(
        'syntax = "proto3";\npackage demo.common;\nmessage User {}\n',
        encoding="utf-8",
    )
    (repo_path / "protos" / "service" / "api.proto").write_text(
        'syntax = "proto3";\n'
        "package demo.service;\n"
        'import "common/types.proto";\n'
        "service AccountService {\n"
        "  rpc GetUser(demo.common.User) returns (demo.common.User);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "buf.yaml").write_text("version: v1\n", encoding="utf-8")
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.py").write_text(
        "def main() -> None:\n    return None\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "protobuf" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "protobuf"
    assert "protos/service/api.proto" in seed_plan["entrypoint_files"]
    assert "protos/service" in seed_plan["support_roots"]
    assert "buf.yaml" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_does_not_force_protobuf_first_in_go_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mixed-go-protobuf-repo"
    (repo_path / "api").mkdir(parents=True)
    (repo_path / "cmd").mkdir(parents=True)
    (repo_path / "internal").mkdir(parents=True)
    (repo_path / "api" / "service.proto").write_text(
        'syntax = "proto3";\npackage demo.api;\nmessage Request {}\n',
        encoding="utf-8",
    )
    (repo_path / "api" / "types.proto").write_text(
        'syntax = "proto3";\npackage demo.api;\nmessage Response {}\n',
        encoding="utf-8",
    )
    for index in range(10):
        target_dir = repo_path / ("cmd" if index < 5 else "internal")
        (target_dir / f"file_{index}.go").write_text(
            f"package main\n\nfunc run{index}() {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "protobuf" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "protobuf"


def test_operational_seed_plan_without_diagnostics_prefers_protobuf_over_bazel_scaffolding(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "protobuf-bazel-repo"
    (repo_path / "google" / "api").mkdir(parents=True)
    (repo_path / "BUILD.bazel").write_text('exports_files(["WORKSPACE"])\n', encoding="utf-8")
    (repo_path / "WORKSPACE").write_text('workspace(name = "demo")\n', encoding="utf-8")
    (repo_path / "google" / "api" / "BUILD.bazel").write_text(
        'proto_library(name = "service_proto")\n',
        encoding="utf-8",
    )
    for name in ("annotations", "client", "field_behavior", "http", "label", "resource", "routing", "service", "usage"):
        (repo_path / "google" / "api" / f"{name}.proto").write_text(
            'syntax = "proto3";\n'
            "package google.api;\n"
            f"message {name.title().replace('_', '')} {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "protobuf" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "protobuf"


def test_connected_dependency_map_follows_protobuf_import_and_reference_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "protobuf-connected-map-repo"
    (repo_path / "common").mkdir(parents=True)
    (repo_path / "service").mkdir(parents=True)
    (repo_path / "common" / "types.proto").write_text(
        'syntax = "proto3";\npackage demo.common;\nmessage User {}\n',
        encoding="utf-8",
    )
    (repo_path / "service" / "api.proto").write_text(
        'syntax = "proto3";\n'
        "package demo.service;\n"
        'import "common/types.proto";\n'
        "service AccountService {\n"
        "  rpc GetUser(demo.common.User) returns (demo.common.User);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["service/api.proto"],
        bridge_paths=["common", "service"],
        include_patterns=["*.proto", "common/**/*.proto", "service/**/*.proto"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "service/api.proto" in connected_map["connected_files"]
    assert "common/types.proto" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1


def test_repository_snapshot_graph_contains_protobuf_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "protobuf-dependency-repo"
    (repo_path / "common").mkdir(parents=True)
    (repo_path / "service").mkdir(parents=True)
    (repo_path / "common" / "types.proto").write_text(
        'syntax = "proto3";\npackage demo.common;\nmessage User {}\n',
        encoding="utf-8",
    )
    (repo_path / "service" / "api.proto").write_text(
        'syntax = "proto3";\n'
        "package demo.service;\n"
        'import "common/types.proto";\n'
        "service AccountService {\n"
        "  rpc GetUser(demo.common.User) returns (demo.common.User);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["common", "service"],
            include_patterns=["common/**/*.proto", "service/**/*.proto", "*.proto"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:service/api.proto"
        and str(row["target_node"]) == "file:common/types.proto"
        for row in graph_rows
    )
    service_symbol_id = symbol_ids[("service/api.proto", "GetUser")]
    user_symbol_id = symbol_ids[("common/types.proto", "User")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{service_symbol_id}"
        and str(row["target_node"]) == f"symbol:{user_symbol_id}"
        for row in graph_rows
    )
