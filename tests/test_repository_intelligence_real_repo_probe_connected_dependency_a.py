"""Tests for repository_intelligence_real_repo_probe: connected_dependency_a.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_connected_dependency_map_follows_relative_and_workspace_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "util.ts").write_text(
        "export const helper = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export const shared = (): string => 'shared';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { helper } from './util';\n"
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => `${helper()}-${shared()}`;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts", "packages/**/*.ts", "packages/**/*.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "packages/common/src/shared.ts",
        "services/app/src/main.ts",
        "services/app/src/util.ts",
    ]


def test_connected_dependency_map_bridges_reverse_dependents_from_scope(tmp_path: Path) -> None:
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export const shared = (): string => 'shared';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => shared();\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["packages/common/src/shared.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts", "packages/**/*.ts", "packages/**/*.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["bridged_importer_count"] == 1
    assert connected_map["bridged_importers"] == ["services/app/src/main.ts"]
    assert "services/app/src/main.ts" in connected_map["connected_files"]


def test_connected_dependency_map_prefers_operational_reverse_dependents_over_tests(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export const shared = (): string => 'shared';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => shared();\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.test.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const testRun = (): string => shared();\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["packages/common/src/shared.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts", "packages/**/*.ts", "packages/**/*.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["bridged_importers"] == ["services/app/src/main.ts"]
    assert "services/app/src/main.ts" in connected_map["connected_files"]
    assert "services/app/src/main.test.ts" not in connected_map["connected_files"]


def test_connected_dependency_map_uses_dependency_only_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "util.ts").write_text(
        "export const helper = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { helper } from './util';\n"
        "export const run = (): string => helper();\n",
        encoding="utf-8",
    )

    def _unexpected_analyze_file(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("connected-map cold path should not require full file analysis")

    monkeypatch.setattr(repository_service, "_analyze_file", _unexpected_analyze_file)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1


def test_connected_dependency_map_follows_fortran_use_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "fortran-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "fpm.toml").write_text(
        'name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "math_utils.f90").write_text(
        "module math_utils\n"
        "implicit none\n"
        "contains\n"
        "subroutine helper()\n"
        "end subroutine helper\n"
        "end module math_utils\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.f90").write_text(
        "program main\n"
        "use math_utils, only: helper\n"
        "implicit none\n"
        "call helper()\n"
        "end program main\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.f90"],
        bridge_paths=["src"],
        include_patterns=[
            "src/**/*.f90",
            "src/*.f90",
            "src/**/*.f95",
            "src/*.f95",
            "src/**/*.f03",
            "src/*.f03",
            "src/**/*.f08",
            "src/*.f08",
            "src/**/*.f",
            "src/*.f",
            "src/**/*.for",
            "src/*.for",
            "fpm.toml",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/main.f90",
        "src/math_utils.f90",
    ]


def test_connected_dependency_map_follows_ada_with_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ada-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "alire.toml").write_text(
        'name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme-util.adb").write_text(
        "package body Acme.Util is\n"
        "   procedure Helper is\n"
        "   begin\n"
        "      null;\n"
        "   end Helper;\n"
        "end Acme.Util;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.adb").write_text(
        "with Acme.Util;\n"
        "procedure Main is\n"
        "begin\n"
        "   Acme.Util.Helper;\n"
        "end Main;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.adb"],
        bridge_paths=["src"],
        include_patterns=[
            "src/**/*.adb",
            "src/*.adb",
            "src/**/*.ads",
            "src/*.ads",
            "*.adb",
            "*.ads",
            "*.ada",
            "alire.toml",
            "*.gpr",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme-util.adb",
        "src/main.adb",
    ]


def test_connected_dependency_map_follows_pascal_uses_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "pascal-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.lpr"],
        bridge_paths=["src"],
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
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "main.lpr",
        "src/AcmeUtil.pas",
    ]


def test_connected_dependency_map_follows_delphi_uses_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "delphi-connected-map-repo"
    (repo_path / "App" / "source").mkdir(parents=True)
    (repo_path / "App" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpr</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "source" / "MainForm.pas").write_text(
        "unit MainForm;\n"
        "interface\n"
        "uses System.SysUtils, Vcl.Forms;\n"
        "type\n"
        "  TMainForm = class\n"
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
        "uses MainForm in 'source/MainForm.pas';\n"
        "begin\n"
        "  MainForm.Run;\n"
        "end.\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["App/AcmeApp.dpr"],
        bridge_paths=["App/source"],
        include_patterns=[
            "App/**/*.pas",
            "App/*.pas",
            "App/*.dpr",
            "App/*.dpk",
            "App/*.dproj",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "App/AcmeApp.dpr",
        "App/source/MainForm.pas",
    ]


def test_connected_dependency_map_follows_cobol_copy_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "cobol-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "copybooks").mkdir(parents=True)
    (repo_path / "src" / "MAINAPP.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MAINAPP.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       COPY PERSON-REC.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           CALL \"UTILS\".\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "UTILS.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. UTILS.\n"
        "       PROCEDURE DIVISION.\n"
        "       UTILS-MAIN.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )
    (repo_path / "copybooks" / "PERSON-REC.cpy").write_text(
        "       01 PERSON-REC.\n"
        "          05 PERSON-ID PIC 9(4).\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/MAINAPP.cbl"],
        bridge_paths=["src", "copybooks"],
        include_patterns=[
            "src/**/*.cbl",
            "src/*.cbl",
            "src/**/*.cob",
            "src/*.cob",
            "copybooks/**/*.cpy",
            "copybooks/*.cpy",
            "*.cbl",
            "*.cob",
            "*.cobol",
            "*.cpy",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "copybooks/PERSON-REC.cpy",
        "src/MAINAPP.cbl",
        "src/UTILS.cbl",
    ]


def test_connected_dependency_map_follows_rpg_copy_and_extpgm_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "rpg-connected-map-repo"
    (repo_path / "QRPGLESRC").mkdir(parents=True)
    (repo_path / "QPROTOSRC").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["QRPGLESRC/ORD100.PGM.RPGLE"],
        bridge_paths=["QRPGLESRC", "QPROTOSRC"],
        include_patterns=[
            "QRPGLESRC/**/*.RPGLE",
            "QRPGLESRC/*.RPGLE",
            "QRPGLESRC/**/*.SQLRPGLE",
            "QRPGLESRC/*.SQLRPGLE",
            "QPROTOSRC/**/*.RPGLEINC",
            "QPROTOSRC/*.RPGLEINC",
            "*.RPGLE",
            "*.SQLRPGLE",
            "*.RPGLEINC",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "QPROTOSRC/CUSTOMER.RPGLEINC",
        "QRPGLESRC/ORD100.PGM.RPGLE",
        "QRPGLESRC/ORD101.PGM.RPGLE",
    ]


def test_connected_dependency_map_follows_ladder_jsr_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ladder-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["logic/Main.L5X"],
        bridge_paths=["logic"],
        include_patterns=[
            "logic/**/*.L5X",
            "logic/*.L5X",
            "*.L5X",
            "logic/**/*.l5x",
            "logic/*.l5x",
            "*.l5x",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "logic/Child.L5X",
        "logic/Main.L5X",
    ]


def test_connected_dependency_map_follows_actionscript_import_and_extends_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "actionscript-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/demo/app/Main.as"],
        bridge_paths=["src"],
        include_patterns=["**/*.as", "*.as", "asconfig.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "src/demo/app/Main.as",
        "src/demo/base/BaseActor.as",
        "src/demo/utils/Utils.as",
    ]


def test_connected_dependency_map_keeps_scratch_projects_indexable(tmp_path: Path) -> None:
    repo_path = tmp_path / "scratch-connected-map-repo"
    _write_scratch_project(
        repo_path / "games" / "Maze.sb3",
        _scratch_project_payload(),
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["games/Maze.sb3"],
        bridge_paths=["games"],
        include_patterns=["**/*.sb3", "*.sb3"],
        max_files=128,
        max_file_size_bytes=150_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 1
    assert connected_map["connected_files"] == ["games/Maze.sb3"]


def test_connected_dependency_map_follows_labview_project_and_library_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "labview-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["App.lvproj"],
        bridge_paths=["Source"],
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
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 5
    assert connected_map["resolved_dependency_edges"] >= 4
    assert connected_map["connected_files"] == [
        "App.lvproj",
        "Source/Controls/Config.ctl",
        "Source/Libraries/Helper.vi",
        "Source/Libraries/Helpers.lvlib",
        "Source/Main.vi",
    ]


def test_connected_dependency_map_follows_tcl_pkgindex_and_source_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tcl-connected-map-repo"
    (repo_path / "modules" / "demo").mkdir(parents=True)
    (repo_path / "modules" / "demo" / "pkgIndex.tcl").write_text(
        "package ifneeded demo 1.0 [list source [file join $dir demo.tcl]]\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "demo" / "helpers.tcl").write_text(
        "package provide helpers 1.0\n"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["modules/demo/pkgIndex.tcl"],
        bridge_paths=["modules/demo"],
        include_patterns=["**/*.tcl", "*.tcl", "**/*.tm", "*.tm"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "modules/demo/demo.tcl",
        "modules/demo/helpers.tcl",
        "modules/demo/pkgIndex.tcl",
    ]


