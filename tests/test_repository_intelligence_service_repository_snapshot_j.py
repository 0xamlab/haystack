"""Tests for repository_intelligence_service: repository_snapshot_j.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_mql5_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "mql5-dependency-repo"
    (repo_path / "Experts").mkdir(parents=True)
    (repo_path / "Include").mkdir(parents=True)
    (repo_path / "demo.mqproj").write_text(
        '<Project><Files><File>Experts/Main.mq5</File><File>Include/Helper.mqh</File></Files></Project>\n',
        encoding="utf-8",
    )
    (repo_path / "Include" / "Helper.mqh").write_text(
        "class Helper\n"
        "{\n"
        "public:\n"
        "   string RenderJson()\n"
        "     {\n"
        '      return "{}";\n'
        "     }\n"
        "};\n",
        encoding="utf-8",
    )
    (repo_path / "Experts" / "Main.mq5").write_text(
        '#include "../Include/Helper.mqh"\n'
        "\n"
        "void OnStart()\n"
        "{\n"
        "   Helper helper;\n"
        "   helper.RenderJson();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["Experts", "Include", "demo.mqproj"],
            include_patterns=[
                "Experts/**/*.mq5",
                "Experts/*.mq5",
                "Include/**/*.mqh",
                "Include/*.mqh",
                "*.mqproj",
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
        and str(row["source_node"]) == "file:Experts/Main.mq5"
        and str(row["target_node"]) == "file:Include/Helper.mqh"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("Experts/Main.mq5", "OnStart")]
    render_symbol_id = symbol_ids[("Include/Helper.mqh", "RenderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_smalltalk_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "smalltalk-dependency-repo"
    (repo_path / "src" / "Demo-App").mkdir(parents=True)
    (repo_path / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / ".smalltalk.ston").write_text("{ }\n", encoding="utf-8")
    (repo_path / "src" / "Demo-Core" / "package.st").write_text(
        "Package { #name : 'Demo-Core' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-Core" / "Helper.class.st").write_text(
        "Class {\n"
        "\t#name : 'Helper',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-Core',\n"
        "\t#package : 'Demo-Core'\n"
        "}\n"
        "\n"
        "{ #category : 'rendering' }\n"
        "Helper class >> renderJson [\n"
        "\t^ '{}'\n"
        "]\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-App" / "package.st").write_text(
        "Package { #name : 'Demo-App' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-App" / "Main.class.st").write_text(
        "Class {\n"
        "\t#name : 'Main',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-App',\n"
        "\t#package : 'Demo-App'\n"
        "}\n"
        "\n"
        "{ #category : 'running' }\n"
        "Main >> run [\n"
        "\t^ Helper renderJson\n"
        "]\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", ".smalltalk.ston"],
            include_patterns=["**/*.st", "*.st", "**/*.ston", "*.ston"],
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
        and str(row["source_node"]) == "file:src/Demo-App/Main.class.st"
        and str(row["target_node"]) == "file:src/Demo-Core/Helper.class.st"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/Demo-App/Main.class.st", "run")]
    render_symbol_id = symbol_ids[("src/Demo-Core/Helper.class.st", "renderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_cfml_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "cfml-dependency-repo"
    (repo_path / "config").mkdir(parents=True)
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "config" / "app.cfm").write_text(
        "<cfset request.ready = true />\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "UserService.cfc").write_text(
        "component {\n"
        "    function run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Application.cfc").write_text(
        "component {\n"
        '    include "config/app.cfm";\n'
        "    function onApplicationStart() {\n"
        "        local.userService = new models.UserService();\n"
        "        local.userService.run();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["**/*.cfc", "*.cfc", "**/*.cfm", "*.cfm"],
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
        and str(row["source_node"]) == "file:Application.cfc"
        and str(row["target_node"]) == "file:config/app.cfm"
        for row in graph_rows
    )
    on_application_start_symbol_id = symbol_ids[("Application.cfc", "onApplicationStart")]
    run_symbol_id = symbol_ids[("models/UserService.cfc", "run")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{on_application_start_symbol_id}"
        and str(row["target_node"]) == f"symbol:{run_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_awk_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "awk-dependency-repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "translate").write_text(
        "#!/usr/bin/env gawk -f\n"
        '@include "../lib/math.awk"\n'
        "BEGIN {\n"
        "    print add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["bin", "lib"],
            include_patterns=["bin/translate", "**/*.awk", "*.awk"],
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
        and str(row["source_node"]) == "file:bin/translate"
        and str(row["target_node"]) == "file:lib/math.awk"
        for row in graph_rows
    )
    begin_symbol_id = symbol_ids[("bin/translate", "BEGIN")]
    add_symbol_id = symbol_ids[("lib/math.awk", "add")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{begin_symbol_id}"
        and str(row["target_node"]) == f"symbol:{add_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_elm_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "elm-dependency-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    (repo_path / "elm.json").write_text(
        json.dumps(
            {
                "type": "application",
                "source-directories": ["src"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (Model, homeView)\n\n"
        "type alias Model =\n"
        "    { title : String }\n\n"
        "homeView : Model -> String\n"
        "homeView model =\n"
        "    model.title\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.elm").write_text(
        "module Main exposing (main)\n\n"
        "import Page.Home exposing (Model, homeView)\n\n"
        "main : String\n"
        "main =\n"
        "    homeView { title = \"ok\" }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.elm", "src/*.elm", "elm.json"],
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
        and str(row["source_node"]) == "file:src/Main.elm"
        and str(row["target_node"]) == "file:src/Page/Home.elm"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/Main.elm", "main")]
    home_view_symbol_id = symbol_ids[("src/Page/Home.elm", "homeView")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{home_view_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_racket_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "racket-dependency-repo"
    (repo_path / "private").mkdir(parents=True)
    (repo_path / "info.rkt").write_text(
        "#lang info\n"
        '(define collection "racket-dependency-repo")\n',
        encoding="utf-8",
    )
    (repo_path / "private" / "helper.rkt").write_text(
        "#lang racket\n"
        "(define (helper) 1)\n",
        encoding="utf-8",
    )
    (repo_path / "main.rkt").write_text(
        "#lang racket\n"
        '(require "private/helper.rkt")\n'
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.rkt", "private/**/*.rkt", "private/*.rkt", "info.rkt"],
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
        and str(row["source_node"]) == "file:main.rkt"
        and str(row["target_node"]) == "file:private/helper.rkt"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("main.rkt", "run")]
    helper_symbol_id = symbol_ids[("private/helper.rkt", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_xpp_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "xpp-dependency-repo"
    (repo_path / "PackagesLocalDirectory" / "Acme" / "Acme" / "AxClass").mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "BaseWorker.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>BaseWorker</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class BaseWorker\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "    <Methods>\n"
        "      <Method>\n"
        "        <Name>doWork</Name>\n"
        "        <Source><![CDATA[\n"
        "public static void doWork()\n"
        "{\n"
        "}\n"
        "]]></Source>\n"
        "      </Method>\n"
        "    </Methods>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
        / "MainWorker.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>MainWorker</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class MainWorker extends BaseWorker\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "    <Methods>\n"
        "      <Method>\n"
        "        <Name>boot</Name>\n"
        "        <Source><![CDATA[\n"
        "public static void boot()\n"
        "{\n"
        "    BaseWorker::doWork();\n"
        "}\n"
        "]]></Source>\n"
        "      </Method>\n"
        "    </Methods>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["PackagesLocalDirectory"],
            include_patterns=["**/*.xml", "*.xml"],
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
        and str(row["source_node"])
        == "file:PackagesLocalDirectory/Acme/Acme/AxClass/MainWorker.xml"
        and str(row["target_node"])
        == "file:PackagesLocalDirectory/Acme/Acme/AxClass/BaseWorker.xml"
        for row in graph_rows
    )
    boot_symbol_id = symbol_ids[
        ("PackagesLocalDirectory/Acme/Acme/AxClass/MainWorker.xml", "boot")
    ]
    do_work_symbol_id = symbol_ids[
        ("PackagesLocalDirectory/Acme/Acme/AxClass/BaseWorker.xml", "doWork")
    ]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{boot_symbol_id}"
        and str(row["target_node"]) == f"symbol:{do_work_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_scratch_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scratch-dependency-repo"
    _write_scratch_project(
        repo_path / "games" / "Maze.sb3",
        _scratch_project_payload(),
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["games"],
            include_patterns=["**/*.sb3", "*.sb3"],
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

    init_symbol_id = symbol_ids[("games/Maze.sb3", "init")]
    start_symbol_id = symbol_ids[("games/Maze.sb3", "start")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{init_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{start_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_analyzes_scratch_project_json_when_archive_exceeds_size_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "scratch-large-archive-repo"
    large_asset = b"".join(
        hashlib.sha256(f"scratch-asset-{index}".encode()).digest()
        for index in range(14_000)
    )
    _write_scratch_project(
        repo_path / "games" / "Large Maze.sb3",
        _scratch_project_payload(),
        extra_assets={"costumes/large.bin": large_asset},
    )
    assert (repo_path / "games" / "Large Maze.sb3").stat().st_size > 350_000
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["games"],
            include_patterns=["**/*.sb3", "*.sb3"],
            max_file_size_bytes=350_000,
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_names = {
        (str(row["file_path"]), str(row["symbol_name"]))
        for row in symbol_rows
    }

    assert ("games/Large Maze.sb3", "init") in symbol_names
    assert ("games/Large Maze.sb3", "start") in symbol_names


def test_repository_snapshot_graph_contains_tcl_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "tcl-dependency-repo"
    (repo_path / "modules" / "demo").mkdir(parents=True)
    (repo_path / "modules" / "demo" / "pkgIndex.tcl").write_text(
        "package ifneeded demo 1.0 [list source [file join $dir demo.tcl]]\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "demo" / "helpers.tcl").write_text(
        "package provide helpers 1.0\n"
        "namespace eval ::helpers {}\n"
        "proc ::helpers::run {} {\n"
        "    return ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "demo" / "demo.tcl").write_text(
        "package provide demo 1.0\n"
        "source helpers.tcl\n"
        "proc ::demo::main {} {\n"
        "    ::helpers::run\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["modules"],
            include_patterns=["**/*.tcl", "*.tcl", "**/*.tm", "*.tm"],
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
        and str(row["source_node"]) == "file:modules/demo/pkgIndex.tcl"
        and str(row["target_node"]) == "file:modules/demo/demo.tcl"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:modules/demo/demo.tcl"
        and str(row["target_node"]) == "file:modules/demo/helpers.tcl"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("modules/demo/demo.tcl", "main")]
    helper_symbol_id = symbol_ids[("modules/demo/helpers.tcl", "run")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_systemverilog_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "systemverilog-dependency-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.svh").write_text(
        "package util_pkg;\n"
        "  function int helper();\n"
        "    return 1;\n"
        "  endfunction\n"
        "endpackage\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.sv").write_text(
        "module child;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.sv").write_text(
        '`include "defs.svh"\n'
        "import util_pkg::*;\n"
        "module top;\n"
        "  child u_child();\n"
        "  int value = util_pkg::helper();\n"
        "endmodule\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["rtl"],
            include_patterns=["**/*.sv", "*.sv", "**/*.svh", "*.svh", "**/*.v", "*.v"],
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
        and str(row["source_node"]) == "file:rtl/top.sv"
        and str(row["target_node"]) == "file:rtl/defs.svh"
        for row in graph_rows
    )
    top_symbol_id = symbol_ids[("rtl/top.sv", "top")]
    child_symbol_id = symbol_ids[("rtl/child.sv", "child")]
    helper_symbol_id = symbol_ids[("rtl/defs.svh", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_symbol_id}"
        and str(row["target_node"]) == f"symbol:{child_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{top_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


