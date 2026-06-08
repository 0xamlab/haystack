"""Tests for repository_intelligence_service: repository_snapshot_c.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_clojure_refer_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "clojure-refer-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"] :main acme.core}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "util.clj").write_text(
        "(ns acme.util)\n"
        "(defn helper [] :ok)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core\n"
        "  (:require [acme.util :refer [helper]]))\n"
        "(defn run []\n"
        "  (helper))\n",
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

    run_symbol_id = symbol_ids[("src/acme/core.clj", "run")]
    helper_symbol_id = symbol_ids[("src/acme/util.clj", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_lua_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "lua-dependency-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "acme-scm-1.rockspec").write_text(
        'package = "acme"\n'
        'build = { modules = { ["acme.core"] = "lua/acme/core.lua", ["acme.util"] = "lua/acme/util.lua" } }\n',
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\n"
        "function M.helper()\n"
        "  return 'ok'\n"
        "end\n"
        "return M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "core.lua").write_text(
        "local util = require('acme.util')\n"
        "local function run()\n"
        "  return util.helper()\n"
        "end\n"
        "return { run = run }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lua"],
            include_patterns=["lua/**/*.lua", "*.rockspec"],
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
        and str(row["source_node"]) == "file:lua/acme/core.lua"
        and str(row["target_node"]) == "file:lua/acme/util.lua"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("lua/acme/core.lua", "run")]
    helper_symbol_id = symbol_ids[("lua/acme/util.lua", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_lua_require_member_and_method_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "lua-member-binding-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "acme-scm-1.rockspec").write_text(
        'package = "acme"\n'
        'build = { modules = { ["acme.util"] = "lua/acme/util.lua", ["acme.core"] = "lua/acme/core.lua" } }\n',
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\n"
        "function M.helper()\n"
        "  return 'ok'\n"
        "end\n"
        "function M:push()\n"
        "  return self:helper()\n"
        "end\n"
        "return M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "core.lua").write_text(
        "local util = require('acme.util')\n"
        "local helper = require('acme.util').helper\n"
        "local function run()\n"
        "  util:push()\n"
        "  return helper()\n"
        "end\n"
        "return { run = run }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["lua"],
            include_patterns=["lua/**/*.lua", "*.rockspec"],
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

    run_symbol_id = symbol_ids[("lua/acme/core.lua", "run")]
    helper_symbol_id = symbol_ids[("lua/acme/util.lua", "helper")]
    push_symbol_id = symbol_ids[("lua/acme/util.lua", "push")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{push_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_luau_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "luau-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "default.project.json").write_text(
        '{\n  "name": "demo",\n  "tree": {\n    "$path": "src/Main.luau"\n  }\n}\n',
        encoding="utf-8",
    )
    (repo_path / "wally.toml").write_text(
        "[package]\nname = 'demo/demo'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Utils.luau").write_text(
        "--!strict\nlocal M = {}\nfunction M.helper()\n  return 'ok'\nend\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.luau").write_text(
        "--!strict\nlocal Utils = require(script.Parent.Utils)\n"
        "local function run()\n  return Utils.helper()\nend\nreturn run\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.luau", "default.project.json", "wally.toml"],
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
        and str(row["source_node"]) == "file:src/Main.luau"
        and str(row["target_node"]) == "file:src/Utils.luau"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/Main.luau", "run")]
    helper_symbol_id = symbol_ids[("src/Utils.luau", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_dhall_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "dhall-dependency-repo"
    (repo_path / "schemas").mkdir(parents=True)
    (repo_path / "package.dhall").write_text(
        "{ Type = ./schemas/Step.dhall }\n",
        encoding="utf-8",
    )
    (repo_path / "schemas" / "Step.dhall").write_text(
        "{ Type = \"step\", default = \"run\" }\n",
        encoding="utf-8",
    )
    (repo_path / "workflow.dhall").write_text(
        "let Package = ./package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.dhall", "*.dhall"],
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
        and str(row["source_node"]) == "file:workflow.dhall"
        and str(row["target_node"]) == "file:package.dhall"
        for row in graph_rows
    )

    package_symbol_id = symbol_ids[("workflow.dhall", "Package")]
    type_symbol_id = symbol_ids[("package.dhall", "Type")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{package_symbol_id}"
        and str(row["target_node"]) == f"symbol:{type_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_coq_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "coq-dependency-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "_CoqProject").write_text(
        "-Q theories Demo\n"
        "theories/Main.v\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Main.v").write_text(
        "Require Import Helper.\n"
        "Lemma run : nat.\n"
        "Proof.\n"
        "  exact helper.\n"
        "Qed.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["theories", "_CoqProject"],
            include_patterns=["theories/**/*.v", "_CoqProject"],
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
        and str(row["source_node"]) == "file:theories/Main.v"
        and str(row["target_node"]) == "file:theories/Helper.v"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("theories/Main.v", "run")]
    helper_symbol_id = symbol_ids[("theories/Helper.v", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_lean_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "lean-dependency-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "lean-toolchain").write_text(
        "leanprover/lean4:stable\n",
        encoding="utf-8",
    )
    (repo_path / "lakefile.lean").write_text(
        "package batteries where\n\n"
        "lean_lib Batteries\n",
        encoding="utf-8",
    )
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )
    (repo_path / "Batteries" / "Main.lean").write_text(
        "import Batteries.Helper\n\n"
        "def run : Nat := Batteries.Helper.helper\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Batteries", "lean-toolchain", "lakefile.lean"],
            include_patterns=["Batteries/**/*.lean", "lean-toolchain", "lakefile.lean"],
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
        and str(row["source_node"]) == "file:Batteries/Main.lean"
        and str(row["target_node"]) == "file:Batteries/Helper.lean"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("Batteries/Main.lean", "run")]
    helper_symbol_id = symbol_ids[("Batteries/Helper.lean", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_glsl_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "glsl-dependency-repo"
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "lib" / "noise.glsl").write_text(
        "float noise() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.frag").write_text(
        '#version 300 es\n'
        '#include "./lib/noise.glsl"\n'
        "float render() {\n"
        "  return noise();\n"
        "}\n"
        "void main() {}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.glsl", "src/**/*.frag"],
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
        str(row["edge_type"]) == "includes"
        and str(row["source_node"]) == "file:src/main.frag"
        and str(row["target_node"]) == "file:src/lib/noise.glsl"
        for row in graph_rows
    )

    render_symbol_id = symbol_ids[("src/main.frag", "render")]
    noise_symbol_id = symbol_ids[("src/lib/noise.glsl", "noise")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{render_symbol_id}"
        and str(row["target_node"]) == f"symbol:{noise_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_shell_source_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "shell-dependency-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "lib" / "util.zsh").write_text(
        "helper() {\n"
        "  echo ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.sh").write_text(
        "#!/usr/bin/env bash\n"
        ". ../lib/util.zsh\n"
        "run() {\n"
        "  helper\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts", "lib"],
            include_patterns=["scripts/*.sh", "lib/*.zsh"],
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
        and str(row["source_node"]) == "file:scripts/main.sh"
        and str(row["target_node"]) == "file:lib/util.zsh"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("scripts/main.sh", "run")]
    helper_symbol_id = symbol_ids[("lib/util.zsh", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_powershell_import_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "powershell-dependency-repo"
    (repo_path / "Private").mkdir(parents=True)
    (repo_path / "Private" / "Helpers.ps1").write_text(
        "function Get-Helper {\n"
        "  return 'ok'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Module.psm1").write_text(
        '. "$PSScriptRoot/Private/Helpers.ps1"\n'
        "function Invoke-Main {\n"
        "  Get-Helper\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Module.psm1", "Private"],
            include_patterns=["*.psm1", "Private/*.ps1"],
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
        and str(row["source_node"]) == "file:Module.psm1"
        and str(row["target_node"]) == "file:Private/Helpers.ps1"
        for row in graph_rows
    )

    invoke_symbol_id = symbol_ids[("Module.psm1", "Invoke-Main")]
    helper_symbol_id = symbol_ids[("Private/Helpers.ps1", "Get-Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{invoke_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_erlang_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "erlang-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "rebar.config").write_text("{erl_opts, [debug_info]}.\n", encoding="utf-8")
    (repo_path / "src" / "acme_util.erl").write_text(
        "-module(acme_util).\n"
        "-export([helper/0]).\n"
        "helper() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n"
        "-export([run/0]).\n"
        "run() -> acme_util:helper().\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.erl", "src/**/*.hrl", "rebar.config"],
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
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:src/acme.erl"
        and str(row["target_node"]) == "file:src/acme_util.erl"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/acme.erl", "run")]
    helper_symbol_id = symbol_ids[("src/acme_util.erl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_nim_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "nim-dependency-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*(): string =\n"
        "  \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.nim").write_text(
        "import acme/util\n"
        "proc run*(): string =\n"
        "  util.helper()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.nim", "*.nimble", "config.nims"],
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
        str(row["edge_type"]) in {"imports", "references"}
        and str(row["source_node"]) == "file:src/acme.nim"
        and str(row["target_node"]) == "file:src/acme/util.nim"
        for row in graph_rows
    )

    run_symbol_id = symbol_ids[("src/acme.nim", "run")]
    helper_symbol_id = symbol_ids[("src/acme/util.nim", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


