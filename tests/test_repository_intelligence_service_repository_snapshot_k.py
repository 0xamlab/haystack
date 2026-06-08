"""Tests for repository_intelligence_service: repository_snapshot_k.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_verilog_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "verilog-dependency-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.vh").write_text(
        "function helper;\n"
        "endfunction\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.v").write_text(
        "module child;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.v").write_text(
        '`include "defs.vh"\n'
        "module top;\n"
        "  child u_child();\n"
        "  assign ready = helper;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["rtl"],
            include_patterns=["**/*.v", "*.v", "**/*.vh", "*.vh"],
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
        and str(row["source_node"]) == "file:rtl/top.v"
        and str(row["target_node"]) == "file:rtl/defs.vh"
        for row in graph_rows
    )
    top_symbol_id = symbol_ids[("rtl/top.v", "top")]
    child_symbol_id = symbol_ids[("rtl/child.v", "child")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_symbol_id}"
        and str(row["target_node"]) == f"symbol:{child_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_vhdl_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vhdl-dependency-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.vhd").write_text(
        "package util_pkg is\n"
        "  function helper return integer;\n"
        "end package;\n"
        "package body util_pkg is\n"
        "  function helper return integer is\n"
        "  begin\n"
        "    return 1;\n"
        "  end function;\n"
        "end package body;\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.vhd").write_text(
        "entity child is\n"
        "end entity;\n"
        "architecture rtl of child is\n"
        "begin\n"
        "end architecture;\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.vhd").write_text(
        "library work;\n"
        "use work.util_pkg.all;\n"
        "entity top is\n"
        "end entity;\n"
        "architecture rtl of top is\n"
        "begin\n"
        "  u_child: entity work.child port map();\n"
        "  value_proc: process is\n"
        "    variable value : integer := util_pkg.helper;\n"
        "  begin\n"
        "    wait;\n"
        "  end process;\n"
        "end architecture;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["rtl"],
            include_patterns=["**/*.vhd", "*.vhd", "**/*.vhdl", "*.vhdl"],
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
        and str(row["source_node"]) == "file:rtl/top.vhd"
        and str(row["target_node"]) == "file:rtl/defs.vhd"
        for row in graph_rows
    )
    top_arch_symbol_id = symbol_ids[("rtl/top.vhd", "top.rtl")]
    child_symbol_id = symbol_ids[("rtl/child.vhd", "child")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_arch_symbol_id}"
        and str(row["target_node"]) == f"symbol:{child_symbol_id}"
        for row in graph_rows
    )
    helper_symbol_ids = {
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "rtl/defs.vhd" and str(row["symbol_name"]) == "helper"
    }
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_arch_symbol_id}"
        and str(row["target_node"]) in {f"symbol:{symbol_id}" for symbol_id in helper_symbol_ids}
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_gdscript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "gdscript-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "base_actor.gd").write_text(
        "class_name BaseActor\n"
        "extends Node\n"
        "func base_ready() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "utils.gd").write_text(
        "class_name Utils\n"
        "extends RefCounted\n"
        "func helper() -> int:\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "player.gd").write_text(
        "class_name Player\n"
        'extends "res://src/base_actor.gd"\n'
        'const UtilsRef = preload("res://src/utils.gd")\n'
        "func _ready() -> void:\n"
        "    UtilsRef.helper()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["**/*.gd", "*.gd", "project.godot"],
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
        str(row["edge_type"]) == "extends"
        and str(row["source_node"]) == "file:src/player.gd"
        and str(row["target_node"]) == "file:src/base_actor.gd"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/player.gd"
        and str(row["target_node"]) == "file:src/utils.gd"
        for row in graph_rows
    )
    ready_symbol_id = symbol_ids[("src/player.gd", "_ready")]
    helper_symbol_id = symbol_ids[("src/utils.gd", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{ready_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_gml_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "gml-dependency-repo"
    (repo_path / "scripts" / "tree_runtime").mkdir(parents=True)
    (repo_path / "scripts" / "tree_api").mkdir(parents=True)
    (repo_path / "objects" / "Entity").mkdir(parents=True)
    (repo_path / "scripts" / "tree_runtime" / "tree_runtime.gml").write_text(
        "function __BHTree() constructor {\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_api" / "tree_api.gml").write_text(
        "function bh_tree() {\n"
        "    return new __BHTree();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "objects" / "Entity" / "Create_0.gml").write_text(
        "function setup() {\n"
        "    return bh_tree();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts", "objects"],
            include_patterns=["**/*.gml", "*.gml"],
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
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:objects/Entity/Create_0.gml"
        and str(row["target_node"]) == "file:scripts/tree_api/tree_api.gml"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:scripts/tree_api/tree_api.gml"
        and str(row["target_node"]) == "file:scripts/tree_runtime/tree_runtime.gml"
        for row in graph_rows
    )
    setup_symbol_id = symbol_ids[("objects/Entity/Create_0.gml", "setup")]
    tree_factory_symbol_id = symbol_ids[("scripts/tree_api/tree_api.gml", "bh_tree")]
    tree_api_symbol_id = symbol_ids[("scripts/tree_api/tree_api.gml", "tree_api")]
    runtime_symbol_id = symbol_ids[("scripts/tree_runtime/tree_runtime.gml", "__BHTree")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{setup_symbol_id}"
        and str(row["target_node"]) == f"symbol:{tree_factory_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{tree_api_symbol_id}"
        and str(row["target_node"]) == f"symbol:{runtime_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_vbscript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "vbscript-dependency-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "helper.vbs").write_text(
        "Class Helper\n"
        "    Public Sub Run()\n"
        "    End Sub\n"
        "End Class\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.wsf").write_text(
        "<job>\n"
        '  <script language="VBScript" src="lib/helper.vbs"></script>\n'
        '  <script language="VBScript">\n'
        "    Option Explicit\n"
        "    Sub Main()\n"
        "        Dim helper\n"
        "        Set helper = New Helper\n"
        "        helper.Run()\n"
        "    End Sub\n"
        "  </script>\n"
        "</job>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts"],
            include_patterns=["scripts/**/*.vbs", "scripts/**/*.wsf", "scripts/*.vbs", "scripts/*.wsf"],
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
        and str(row["source_node"]) == "file:scripts/main.wsf"
        and str(row["target_node"]) == "file:scripts/lib/helper.vbs"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("scripts/main.wsf", "Main")]
    helper_symbol_id = symbol_ids[("scripts/lib/helper.vbs", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_applescript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "applescript-dependency-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on renderJson(value)\n"
        "        return value\n"
        "    end renderJson\n"
        "end script\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "Main.applescript").write_text(
        'property helperScript : load script POSIX file "lib/Helper.applescript"\n'
        "\n"
        "on run\n"
        "    helperScript's renderJson(\"{}\")\n"
        "end run\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["scripts"],
            include_patterns=[
                "scripts/**/*.applescript",
                "scripts/*.applescript",
                "scripts/**/*.scpt",
                "scripts/*.scpt",
            ],
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
        and str(row["source_node"]) == "file:scripts/Main.applescript"
        and str(row["target_node"]) == "file:scripts/lib/Helper.applescript"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("scripts/Main.applescript", "run")]
    render_symbol_id = symbol_ids[("scripts/lib/Helper.applescript", "renderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_rpg_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "rpg-dependency-repo"
    (repo_path / "QRPGLESRC").mkdir(parents=True)
    (repo_path / "QPROTOSRC").mkdir(parents=True)
    (repo_path / "iproj.json").write_text(
        '{\n'
        '  "includePath": ["QPROTOSRC"]\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "QPROTOSRC" / "CUSTOMER.RPGLEINC").write_text(
        "dcl-ds Customer qualified;\n"
        "   id packed(5);\n"
        "end-ds;\n",
        encoding="utf-8",
    )
    (repo_path / "QRPGLESRC" / "ORD101.PGM.RPGLE").write_text(
        "**free\n"
        "dcl-proc Updord export;\n"
        "   dcl-pi *n ind;\n"
        "      id packed(5);\n"
        "   end-pi;\n"
        "   return *on;\n"
        "end-proc;\n",
        encoding="utf-8",
    )
    (repo_path / "QRPGLESRC" / "ORD100.PGM.RPGLE").write_text(
        "**free\n"
        "/copy CUSTOMER.RPGLEINC\n"
        "dcl-pr Updord extpgm('ORD101');\n"
        "   id packed(5);\n"
        "end-pr;\n"
        "dcl-proc Run export;\n"
        "   dcl-pi *n;\n"
        "   end-pi;\n"
        "   return Updord(1);\n"
        "end-proc;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["QRPGLESRC", "QPROTOSRC"],
            include_patterns=[
                "QRPGLESRC/**/*.RPGLE",
                "QRPGLESRC/*.RPGLE",
                "QPROTOSRC/**/*.RPGLEINC",
                "QPROTOSRC/*.RPGLEINC",
                "iproj.json",
            ],
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
        and str(row["source_node"]) == "file:QRPGLESRC/ORD100.PGM.RPGLE"
        and str(row["target_node"]) == "file:QPROTOSRC/CUSTOMER.RPGLEINC"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:QRPGLESRC/ORD100.PGM.RPGLE"
        and str(row["target_node"]) == "file:QRPGLESRC/ORD101.PGM.RPGLE"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("QRPGLESRC/ORD100.PGM.RPGLE", "Run")]
    updord_symbol_id = symbol_ids[("QRPGLESRC/ORD101.PGM.RPGLE", "Updord")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{updord_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_apex_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "apex-dependency-repo"
    (repo_path / "force-app" / "main" / "default" / "classes").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "triggers").mkdir(parents=True)
    (repo_path / "sfdx-project.json").write_text(
        '{\n'
        '  "packageDirectories": [\n'
        '    { "path": "force-app", "default": true }\n'
        "  ],\n"
        '  "sourceApiVersion": "60.0"\n'
        '}\n',
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "classes"
        / "AccountTriggerHandler.cls"
    ).write_text(
        "public with sharing class AccountTriggerHandler {\n"
        "    public static void run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "force-app"
        / "main"
        / "default"
        / "triggers"
        / "AccountTrigger.trigger"
    ).write_text(
        "trigger AccountTrigger on Account (before insert) {\n"
        "    AccountTriggerHandler.run();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["force-app"],
            include_patterns=[
                "force-app/**/*.cls",
                "force-app/**/*.trigger",
                "sfdx-project.json",
            ],
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
        str(row["edge_type"]) == "references"
        and str(row["source_node"])
        == "file:force-app/main/default/triggers/AccountTrigger.trigger"
        and str(row["target_node"])
        == "file:force-app/main/default/classes/AccountTriggerHandler.cls"
        for row in graph_rows
    )
    trigger_symbol_id = symbol_ids[
        ("force-app/main/default/triggers/AccountTrigger.trigger", "AccountTrigger")
    ]
    handler_symbol_id = symbol_ids[
        ("force-app/main/default/classes/AccountTriggerHandler.cls", "AccountTriggerHandler")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{trigger_symbol_id}"
        and str(row["target_node"]) == f"symbol:{handler_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_wolfram_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "wolfram-dependency-repo"
    (repo_path / "Kernel").mkdir(parents=True)
    (repo_path / "PacletInfo.wl").write_text(
        'PacletObject[<|"Name" -> "Acme/Test", "Extensions" -> {{"Kernel", "Root" -> "Kernel", "Context" -> {"Acme`"}}}|>]\n',
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "init.m").write_text(
        'Get["Acme`Main`"];\n',
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Main.wl").write_text(
        'BeginPackage["Acme`", {"Acme`Helpers`"}];\n'
        'run::usage = "run";\n'
        'Begin["`Private`"];\n'
        "run[] := helper[];\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Helpers.wl").write_text(
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        'Begin["`Private`"];\n'
        "helper[] := 1;\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Kernel"],
            include_patterns=["Kernel/**/*.wl", "Kernel/**/*.m", "PacletInfo.wl"],
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
        str(row["edge_type"]) == "loads"
        and str(row["source_node"]) == "file:Kernel/init.m"
        and str(row["target_node"]) == "file:Kernel/Main.wl"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Kernel/Main.wl"
        and str(row["target_node"]) == "file:Kernel/Helpers.wl"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("Kernel/Main.wl", "run")]
    helper_symbol_id = symbol_ids[("Kernel/Helpers.wl", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_fsharp_dependency_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "fsharp-dependency-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "src" / "Acme" / "Core.fs").write_text(
        "namespace Acme\n\n"
        "type Request = { Name: string }\n\n"
        "module RequestOps =\n"
        "    let render (request: Request) = request.Name\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme" / "Http.fs").write_text(
        "namespace Acme\n\n"
        "open Acme\n\n"
        "module Http =\n"
        "    let handle (request: Request) = RequestOps.render request\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.fs"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "references"
        and str(row["source_node"]) == "file:src/Acme/Http.fs"
        and str(row["target_node"]) == "file:src/Acme/Core.fs"
        for row in graph_rows
    )

    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }
    handle_symbol_id = symbol_ids[("src/Acme/Http.fs", "handle")]
    render_symbol_id = symbol_ids[("src/Acme/Core.fs", "render")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{handle_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


