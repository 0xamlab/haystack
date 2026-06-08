"""Tests for repository_intelligence_service: repository_snapshot_b.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_rust_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "rust-graph-reference-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.rs").write_text(
        "pub fn value() -> String {\n"
        '    "ok".to_string()\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.rs").write_text(
        "use crate::helper::value;\n"
        "mod helper;\n\n"
        "pub fn run() -> String {\n"
        "    value()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/*.rs", "src/**/*.rs"],
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

    run_symbol_id = symbol_ids[("src/main.rs", "run")]
    value_symbol_id = symbol_ids[("src/helper.rs", "value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_go_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-graph-reference-repo"
    (repo_path / "helper").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper" / "helper.go").write_text(
        "package helper\n\n"
        "func Value() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package main\n\n"
        'import "example.com/repo/helper"\n\n'
        "func run() string {\n"
        "    return helper.Value()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.go", "helper"],
            include_patterns=["*.go", "**/*.go"],
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

    run_symbol_id = symbol_ids[("main.go", "run")]
    value_symbol_id = symbol_ids[("helper/helper.go", "Value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_go_same_package_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-same-package-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run() string {\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.go", "helper.go"],
            include_patterns=["*.go", "**/*.go"],
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

    run_symbol_id = symbol_ids[("main.go", "run")]
    helper_symbol_id = symbol_ids[("helper.go", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_go_builtin_collisions_for_same_package_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-builtin-collision-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "builtin.go").write_text(
        "package cobra\n\n"
        "func len(items []string) int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run(items []string) int {\n"
        "    _ = len(items)\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.go", "helper.go", "builtin.go"],
            include_patterns=["*.go", "**/*.go"],
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

    run_symbol_id = symbol_ids[("main.go", "run")]
    helper_symbol_id = symbol_ids[("helper.go", "helper")]
    builtin_symbol_id = symbol_ids[("builtin.go", "len")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert not any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{builtin_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_ignores_go_stdlib_import_file_name_collisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-stdlib-import-collision-repo"
    (repo_path / "middleware").mkdir(parents=True)
    (repo_path / "_examples" / "versions" / "data").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "middleware" / "recoverer.go").write_text(
        "package middleware\n\n"
        'import "errors"\n\n'
        "func Recoverer() error {\n"
        '    return errors.New("boom")\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "_examples" / "versions" / "data" / "errors.go").write_text(
        "package data\n\n"
        "func PresentError() string {\n"
        '    return "boom"\n'
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["middleware", "_examples/versions/data"],
            include_patterns=["*.go", "**/*.go"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    dependency_rows = pq.read_table(snapshot.dependency_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["source_file"]) == "middleware/recoverer.go"
        and str(row["target_symbol"]) == "errors"
        and row["target_file"] is None
        for row in dependency_rows
    )
    assert not any(
        str(row["source_file"]) == "middleware/recoverer.go"
        and str(row["target_file"]) == "_examples/versions/data/errors.go"
        for row in dependency_rows
    )


def test_repository_snapshot_graph_prefers_non_test_go_same_package_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "go-test-leak-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper_test.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "test"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run() string {\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.go", "helper.go", "helper_test.go"],
            include_patterns=["*.go", "**/*.go"],
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

    run_symbol_id = symbol_ids[("main.go", "run")]
    helper_symbol_id = symbol_ids[("helper.go", "helper")]
    helper_test_symbol_id = symbol_ids[("helper_test.go", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert not any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_test_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_mojo_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "mojo-graph-reference-repo"
    (repo_path / "helper").mkdir(parents=True)
    (repo_path / "helper" / "util.mojo").write_text(
        "fn value():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (repo_path / "main.mojo").write_text(
        "import helper.util\n\n"
        "fn run():\n"
        "    return util.value()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["main.mojo", "helper"],
            include_patterns=["*.mojo", "**/*.mojo"],
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

    run_symbol_id = symbol_ids[("main.mojo", "run")]
    value_symbol_id = symbol_ids[("helper/util.mojo", "value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cpp_include_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cpp-dependency-repo"
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme" / "format.hpp").write_text(
        "#pragma once\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "format.hpp").write_text(
        '#include "acme/format.hpp"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cpp").write_text(
        '#include "format.hpp"\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "include"],
            include_patterns=["src/**/*.cpp", "src/**/*.hpp", "include/**/*.hpp"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/main.cpp"
        and str(row["target_node"]) in {"file:src/format.hpp", "file:include/acme/format.hpp"}
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/format.hpp"
        and str(row["target_node"]) == "file:include/acme/format.hpp"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cpp_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cpp-symbol-graph-repo"
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme" / "format.hpp").write_text(
        "#pragma once\n"
        "namespace acme {\n"
        "int format_value();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cpp").write_text(
        '#include "acme/format.hpp"\n'
        "int run() {\n"
        "    return acme::format_value();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "include"],
            include_patterns=["src/**/*.cpp", "include/**/*.hpp"],
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

    run_symbol_id = symbol_ids[("src/main.cpp", "run")]
    format_value_symbol_id = symbol_ids[("include/acme/format.hpp", "format_value")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{format_value_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ruby_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ruby-dependency-repo"
    (repo_path / "lib" / "jekyll").mkdir(parents=True)
    (repo_path / "lib" / "jekyll" / "cache.rb").write_text(
        "module Jekyll\n"
        "  class Cache\n"
        "    def self.helper\n"
        "      1\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "jekyll.rb").write_text(
        'require "jekyll/cache"\n'
        "module Jekyll\n"
        "  def self.run\n"
        "    Jekyll::Cache.helper\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/*.rb", "lib/**/*.rb"],
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
        and str(row["source_node"]) == "file:lib/jekyll.rb"
        and str(row["target_node"]) == "file:lib/jekyll/cache.rb"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("lib/jekyll.rb", "run")]
    helper_symbol_id = symbol_ids[("lib/jekyll/cache.rb", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ruby_new_inheritance_and_mixin_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ruby-structure-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "lib" / "acme" / "base_runner.rb").write_text(
        "module Acme\n"
        "  class BaseRunner\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "serializable.rb").write_text(
        "module Acme\n"
        "  module Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "runner.rb").write_text(
        'require "acme/base_runner"\n'
        'require "acme/serializable"\n'
        "module Acme\n"
        "  class Runner < BaseRunner\n"
        "    include Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.rb").write_text(
        'require "acme/runner"\n'
        "module Acme\n"
        "  def self.build\n"
        "    Runner.new\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib"],
            include_patterns=["lib/*.rb", "lib/**/*.rb", "Gemfile"],
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

    build_symbol_id = symbol_ids[("lib/acme.rb", "build")]
    runner_symbol_id = symbol_ids[("lib/acme/runner.rb", "Runner")]
    base_runner_symbol_id = symbol_ids[("lib/acme/base_runner.rb", "BaseRunner")]
    serializable_symbol_id = symbol_ids[("lib/acme/serializable.rb", "Serializable")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{runner_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
        and str(row["target_node"]) == f"symbol:{base_runner_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{runner_symbol_id}"
        and str(row["target_node"]) == f"symbol:{serializable_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_dart_package_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "dart-dependency-repo"
    (repo_path / "lib" / "src").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "pubspec.yaml").write_text(
        "name: acme_client\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "src" / "helper.dart").write_text(
        "class Helper {\n"
        "  static String value() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme_client.dart").write_text(
        "export 'src/helper.dart' show Helper;\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "acme_client.dart").write_text(
        "import 'package:acme_client/src/helper.dart' show Helper;\n\n"
        "String run() => Helper.value();\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lib", "bin"],
            include_patterns=["lib/*.dart", "lib/**/*.dart", "bin/*.dart", "bin/**/*.dart"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:bin/acme_client.dart"
        and str(row["target_node"]) == "file:lib/src/helper.dart"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "exports"
        and str(row["source_node"]) == "file:lib/acme_client.dart"
        and str(row["target_node"]) == "file:lib/src/helper.dart"
        for row in graph_rows
    )

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    run_symbol_id = symbol_ids[("bin/acme_client.dart", "run")]
    helper_symbol_id = symbol_ids[("lib/src/helper.dart", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_clojure_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "clojure-dependency-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"] :main acme.core}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "util.clj").write_text(
        "(ns acme.util)\n"
        "(defn helper [] \"ok\")\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core\n"
        "  (:require [acme.util :as util]))\n"
        "(defn run []\n"
        "  (util/helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.clj", "src/**/*.cljc", "src/**/*.cljs"],
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
        and str(row["source_node"]) == "file:src/acme/core.clj"
        and str(row["target_node"]) == "file:src/acme/util.clj"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/acme/core.clj", "run")]
    helper_symbol_id = symbol_ids[("src/acme/util.clj", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


