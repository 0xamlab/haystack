"""Tests for repository_intelligence_service: repository_snapshot_f.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_graph_contains_sas_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "sas-dependency-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "macros").mkdir(parents=True)
    (repo_path / "macros" / "render_table.sas").write_text(
        "%macro render_table();\n"
        "  %put rendering table;\n"
        "%mend render_table;\n",
        encoding="utf-8",
    )
    (repo_path / "programs" / "report.sas").write_text(
        "%include \"../macros/render_table.sas\";\n"
        "%macro build_report();\n"
        "  %render_table();\n"
        "%mend build_report;\n"
        "%build_report();\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["programs", "macros"],
            include_patterns=[
                "programs/**/*.sas",
                "programs/*.sas",
                "macros/**/*.sas",
                "macros/*.sas",
                "*.sas",
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
        and str(row["source_node"]) == "file:programs/report.sas"
        and str(row["target_node"]) == "file:macros/render_table.sas"
        for row in graph_rows
    )
    build_report_symbol_id = symbol_ids[("programs/report.sas", "build_report")]
    render_table_symbol_id = symbol_ids[("macros/render_table.sas", "render_table")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_report_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_table_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_abap_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "abap-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "zcl_math.clas.abap").write_text(
        "CLASS zcl_math DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    CLASS-METHODS add_one IMPORTING iv_value TYPE i RETURNING VALUE(rv_value) TYPE i.\n"
        "ENDCLASS.\n"
        "\n"
        "CLASS zcl_math IMPLEMENTATION.\n"
        "  METHOD add_one.\n"
        "    rv_value = iv_value + 1.\n"
        "  ENDMETHOD.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "zcl_report.clas.abap").write_text(
        "CLASS zcl_report DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    METHODS run.\n"
        "ENDCLASS.\n"
        "\n"
        "CLASS zcl_report IMPLEMENTATION.\n"
        "  INCLUDE zcl_report.clas.locals_imp.\n"
        "ENDCLASS.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "zcl_report.clas.locals_imp.abap").write_text(
        "METHOD run.\n"
        "  DATA(result) = zcl_math=>add_one( 1 ).\n"
        "ENDMETHOD.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.abap", "src/*.abap", "*.abap"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    run_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "src/zcl_report.clas.locals_imp.abap"
        and str(row["symbol_name"]) == "run"
    )
    add_one_symbol_ids = {
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "src/zcl_math.clas.abap"
        and str(row["symbol_name"]) == "add_one"
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/zcl_report.clas.abap"
        and str(row["target_node"]) == "file:src/zcl_report.clas.locals_imp.abap"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) in {f"symbol:{symbol_id}" for symbol_id in add_one_symbol_ids}
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_pascal_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "pascal-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Acme.lpi").write_text("<CONFIG></CONFIG>\n", encoding="utf-8")
    (repo_path / "src" / "AcmeUtil.pas").write_text(
        "unit AcmeUtil;\n"
        "interface\n"
        "procedure Helper;\n"
        "implementation\n"
        "procedure Helper;\n"
        "begin\n"
        "end;\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "main.lpr").write_text(
        "program AcmeApp;\n"
        "uses AcmeUtil;\n"
        "begin\n"
        "  AcmeUtil.Helper;\n"
        "end.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "main.lpr", "Acme.lpi"],
            include_patterns=[
                "src/**/*.pas",
                "src/*.pas",
                "*.pas",
                "*.pp",
                "*.lpr",
                "*.dpr",
                "*.dpk",
                "*.lpi",
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
        and str(row["source_node"]) == "file:main.lpr"
        and str(row["target_node"]) == "file:src/AcmeUtil.pas"
        for row in graph_rows
    )
    app_symbol_id = symbol_ids[("main.lpr", "AcmeApp")]
    helper_symbol_id = symbol_ids[("src/AcmeUtil.pas", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{app_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_delphi_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "delphi-dependency-repo"
    (repo_path / "App").mkdir(parents=True)
    (repo_path / "App" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpr</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "MainForm.pas").write_text(
        "unit MainForm;\n"
        "interface\n"
        "uses System.SysUtils, Vcl.Forms;\n"
        "type\n"
        "  TMainForm = class(TForm)\n"
        "  public\n"
        "    class procedure Run;\n"
        "  end;\n"
        "{$R *.dfm}\n"
        "implementation\n"
        "class procedure TMainForm.Run;\n"
        "begin\n"
        "end;\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "AcmeApp.dpr").write_text(
        "program AcmeApp;\n"
        "uses MainForm in 'MainForm.pas';\n"
        "begin\n"
        "  MainForm.Run;\n"
        "end.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["App"],
            include_patterns=[
                "App/**/*.pas",
                "App/*.pas",
                "App/*.dpr",
                "App/*.dproj",
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
        and str(row["source_node"]) == "file:App/AcmeApp.dpr"
        and str(row["target_node"]) == "file:App/MainForm.pas"
        for row in graph_rows
    )
    app_symbol_id = symbol_ids[("App/AcmeApp.dpr", "AcmeApp")]
    run_symbol_ids = {
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "App/MainForm.pas" and str(row["symbol_name"]) == "Run"
    }
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{app_symbol_id}"
        and str(row["target_node"]) in {f"symbol:{symbol_id}" for symbol_id in run_symbol_ids}
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_foxpro_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "foxpro-dependency-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "programs" / "util.prg").write_text(
        "FUNCTION helper()\n"
        "    RETURN 1\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "programs" / "main.prg").write_text(
        "SET PROCEDURE TO programs/util ADDITIVE\n"
        "FUNCTION run()\n"
        "    RETURN helper()\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["programs"],
            include_patterns=["programs/**/*.prg", "programs/*.prg", "*.prg"],
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
        and str(row["source_node"]) == "file:programs/main.prg"
        and str(row["target_node"]) == "file:programs/util.prg"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("programs/main.prg", "run")]
    helper_symbol_id = symbol_ids[("programs/util.prg", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_solidity_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "solidity-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "foundry.toml").write_text(
        '[profile.default]\nsrc = "src"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Ownable.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "abstract contract Ownable {\n"
        "    function owner() public view returns (address) {}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Counter.sol").write_text(
        'pragma solidity ^0.8.20;\n'
        'import {Ownable} from "./Ownable.sol";\n'
        "contract Counter is Ownable {\n"
        "    function increment() public {}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.sol", "src/*.sol", "*.sol"],
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
        and str(row["source_node"]) == "file:src/Counter.sol"
        and str(row["target_node"]) == "file:src/Ownable.sol"
        for row in graph_rows
    )
    counter_symbol_id = symbol_ids[("src/Counter.sol", "Counter")]
    ownable_symbol_id = symbol_ids[("src/Ownable.sol", "Ownable")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{counter_symbol_id}"
        and str(row["target_node"]) == f"symbol:{ownable_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_ladder_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "ladder-dependency-repo"
    (repo_path / "logic").mkdir(parents=True)
    (repo_path / "logic" / "Child.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="SupportProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="ChildRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[XIC(StartPB)OTE(RunMotor);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "logic" / "Main.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<RSLogix5000Content>\n"
        '  <Controller Name="PlantController">\n'
        "    <Programs>\n"
        '      <Program Name="MainProgram">\n'
        "        <Routines>\n"
        '          <Routine Name="MainRoutine" Type="RLL">\n'
        "            <RLLContent>\n"
        '              <Rung Number="0"><Text><![CDATA[JSR(ChildRoutine,0);]]></Text></Rung>\n'
        "            </RLLContent>\n"
        "          </Routine>\n"
        "        </Routines>\n"
        "      </Program>\n"
        "    </Programs>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["logic"],
            include_patterns=[
                "logic/**/*.L5X",
                "logic/*.L5X",
                "*.L5X",
                "logic/**/*.l5x",
                "logic/*.l5x",
                "*.l5x",
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
        and str(row["source_node"]) == "file:logic/Main.L5X"
        and str(row["target_node"]) == "file:logic/Child.L5X"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("logic/Main.L5X", "MainRoutine")]
    child_symbol_id = symbol_ids[("logic/Child.L5X", "ChildRoutine")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{child_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_labview_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "labview-dependency-repo"
    (repo_path / "Source" / "Libraries").mkdir(parents=True)
    (repo_path / "Source" / "Controls").mkdir(parents=True)
    (repo_path / "App.lvproj").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Project Type=\"Project\">\n"
        '  <Item Name="Main" Type="VI" URL="Source/Main.vi" />\n'
        '  <Item Name="Helpers" Type="Library" URL="Source/Libraries/Helpers.lvlib" />\n'
        '  <Item Name="Config" Type="Control" URL="Source/Controls/Config.ctl" />\n'
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "Source" / "Libraries" / "Helpers.lvlib").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Library Name=\"Helpers\">\n"
        '  <Item Name="Helper" Type="VI" URL="Helper.vi" />\n'
        "</Library>\n",
        encoding="utf-8",
    )
    (repo_path / "Source" / "Main.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "Source" / "Libraries" / "Helper.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "Source" / "Controls" / "Config.ctl").write_bytes(b"RSRC\r\n\x00\x03LVCCLBVW")
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=[
                "**/*.lvproj",
                "*.lvproj",
                "**/*.lvlib",
                "*.lvlib",
                "**/*.lvclass",
                "*.lvclass",
                "**/*.vi",
                "*.vi",
                "**/*.vim",
                "*.vim",
                "**/*.vit",
                "*.vit",
                "**/*.ctl",
                "*.ctl",
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
        and str(row["source_node"]) == "file:App.lvproj"
        and str(row["target_node"]) == "file:Source/Libraries/Helpers.lvlib"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:Source/Libraries/Helpers.lvlib"
        and str(row["target_node"]) == "file:Source/Libraries/Helper.vi"
        for row in graph_rows
    )
    helpers_symbol_id = symbol_ids[("Source/Libraries/Helpers.lvlib", "Helpers")]
    helper_symbol_id = symbol_ids[("Source/Libraries/Helper.vi", "Helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{helpers_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_actionscript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "actionscript-dependency-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "base").mkdir(parents=True)
    (repo_path / "src" / "demo" / "utils").mkdir(parents=True)
    (repo_path / "src" / "demo" / "base" / "BaseActor.as").write_text(
        "package demo.base {\n"
        "    public class BaseActor {\n"
        "        public function baseReady():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "utils" / "Utils.as").write_text(
        "package demo.utils {\n"
        "    public class Utils {\n"
        "        public static function helper():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "app" / "Main.as").write_text(
        "package demo.app {\n"
        "    import demo.base.BaseActor;\n"
        "    import demo.utils.Utils;\n"
        "    public class Main extends BaseActor {\n"
        "        public function boot():void {\n"
        "            var utils:Utils = new Utils();\n"
        "            Utils.helper();\n"
        "            utils.helper();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["**/*.as", "*.as", "asconfig.json"],
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
        and str(row["source_node"]) == "file:src/demo/app/Main.as"
        and str(row["target_node"]) == "file:src/demo/base/BaseActor.as"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/demo/app/Main.as"
        and str(row["target_node"]) == "file:src/demo/utils/Utils.as"
        for row in graph_rows
    )
    boot_symbol_id = symbol_ids[("src/demo/app/Main.as", "boot")]
    helper_symbol_id = symbol_ids[("src/demo/utils/Utils.as", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{boot_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_coffeescript_dependency_and_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "coffeescript-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.coffee").write_text(
        "renderJson = ->\n"
        "  '{}'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.coffee").write_text(
        "helper = require './helper'\n"
        "\n"
        "run = ->\n"
        "  helper.renderJson('{}')\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.coffee", "src/*.coffee", "*.coffee", "Cakefile"],
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
        and str(row["source_node"]) == "file:src/main.coffee"
        and str(row["target_node"]) == "file:src/helper.coffee"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/main.coffee", "run")]
    render_symbol_id = symbol_ids[("src/helper.coffee", "renderJson")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{render_symbol_id}"
        for row in graph_rows
    )


