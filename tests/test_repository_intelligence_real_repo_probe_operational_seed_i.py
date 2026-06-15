"""Tests for repository_intelligence_real_repo_probe: operational_seed_i.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_plan_without_diagnostics_uses_vhdl_ls_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vhdl-profile-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "tb").mkdir(parents=True)
    (repo_path / "vhdl_ls.toml").write_text(
        "[libraries.work]\n"
        "files = [\n"
        '  "rtl/defs.vhd",\n'
        '  "rtl/child.vhd",\n'
        '  "rtl/top.vhd",\n'
        '  "tb/top_tb.vhd",\n'
        "]\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "defs.vhd").write_text(
        "package util_pkg is\n"
        "  function helper return integer;\n"
        "end package;\n",
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
        "end architecture;\n",
        encoding="utf-8",
    )
    (repo_path / "tb" / "top_tb.vhd").write_text(
        "entity top_tb is\n"
        "end entity;\n"
        "architecture tb of top_tb is\n"
        "begin\n"
        "  dut: entity work.top port map();\n"
        "end architecture;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vhdl"]
    assert seed_plan["operational_ecosystems"] == ["vhdl"]
    assert "vhdl_ls.toml" in seed_plan["config_paths"]
    assert "rtl" in seed_plan["support_roots"]
    assert "rtl/top.vhd" in seed_plan["entrypoint_files"]
    assert "rtl/defs.vhd" not in seed_plan["entrypoint_files"]
    assert "tb/top_tb.vhd" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_rpg_iproj_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rpg-profile-repo"
    (repo_path / "QRPGLESRC").mkdir(parents=True)
    (repo_path / "QPROTOSRC").mkdir(parents=True)
    (repo_path / "iproj.json").write_text(
        '{\n'
        '  "includePath": ["QPROTOSRC"],\n'
        '  "compileCommand": "/QOpenSys/pkgs/bin/makei c -f {filename}"\n'
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

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["rpg"]
    assert seed_plan["operational_ecosystems"] == ["rpg"]
    assert "iproj.json" in seed_plan["config_paths"]
    assert "QRPGLESRC" in seed_plan["support_roots"]
    assert "QPROTOSRC" in seed_plan["support_roots"]
    assert "QRPGLESRC/ORD100.PGM.RPGLE" in seed_plan["entrypoint_files"]
    assert "QRPGLESRC/ORD101.PGM.RPGLE" in seed_plan["entrypoint_files"]
    assert "QPROTOSRC/CUSTOMER.RPGLEINC" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_apex_sfdx_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "apex-profile-repo"
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
        / "classes"
        / "AccountTriggerHandlerTest.cls"
    ).write_text(
        "@IsTest\n"
        "private class AccountTriggerHandlerTest {\n"
        "    @IsTest static void testRun() {\n"
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

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["apex"]
    assert seed_plan["operational_ecosystems"] == ["apex"]
    assert "sfdx-project.json" in seed_plan["config_paths"]
    assert "force-app/main/default/classes" in seed_plan["support_roots"]
    assert "force-app/main/default/triggers" in seed_plan["support_roots"]
    assert "force-app/main/default/classes/AccountTriggerHandler.cls" in seed_plan["entrypoint_files"]
    assert "force-app/main/default/triggers/AccountTrigger.trigger" in seed_plan["entrypoint_files"]
    assert (
        "force-app/main/default/classes/AccountTriggerHandlerTest.cls"
        not in seed_plan["entrypoint_files"]
    )


def test_operational_seed_plan_without_diagnostics_uses_wolfram_paclet_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "wolfram-profile-repo"
    (repo_path / "Kernel").mkdir(parents=True)
    (repo_path / "Resources").mkdir(parents=True)
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
    (repo_path / "Resources" / "Tooling.wl").write_text(
        "tooling[] := 1;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["wolfram"]
    assert seed_plan["operational_ecosystems"] == ["wolfram"]
    assert "PacletInfo.wl" in seed_plan["config_paths"]
    assert "Kernel" in seed_plan["support_roots"]
    assert "Resources" in seed_plan["support_roots"]
    assert "Kernel/init.m" in seed_plan["entrypoint_files"]
    assert "Kernel/Main.wl" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_ada_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ada-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "alire.toml").write_text(
        'name = "acme"\n'
        'executables = ["main"]\n',
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
    (repo_path / "src" / "acme-util.adb").write_text(
        "package body Acme.Util is\n"
        "   procedure Helper is\n"
        "   begin\n"
        "      null;\n"
        "   end Helper;\n"
        "end Acme.Util;\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_tests.adb").write_text(
        "procedure Main_Tests is\nbegin\n   null;\nend Main_Tests;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "ada" in seed_plan["detected_ecosystems"]
    assert "alire.toml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/main.adb" in seed_plan["entrypoint_files"]
    assert "src/acme-util.adb" in seed_plan["entrypoint_files"]
    assert "tests/main_tests.adb" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_fpm_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fortran-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "fpm.toml").write_text(
        'name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.f90").write_text(
        "module acme\nimplicit none\nend module acme\n",
        encoding="utf-8",
    )
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "app" / "main.f90").write_text(
        "program main\nuse acme\nend program main\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "main.f90").write_text(
        "program test_main\nend program test_main\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "fortran" in seed_plan["detected_ecosystems"]
    assert "fpm.toml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "app" in seed_plan["support_roots"]
    assert "src/acme.f90" in seed_plan["entrypoint_files"]
    assert "app/main.f90" in seed_plan["entrypoint_files"]
    assert "test/main.f90" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_cobol_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cobol-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "copybooks").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
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
    (repo_path / "tests" / "MAINAPP_TEST.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MAINAPP-TEST.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["cobol"]
    assert "src/MAINAPP.cbl" in seed_plan["entrypoint_files"]
    assert "copybooks/PERSON-REC.cpy" not in seed_plan["entrypoint_files"]
    assert "tests/MAINAPP_TEST.cbl" not in seed_plan["entrypoint_files"]
    assert "copybooks/PERSON-REC.cpy" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_prefers_cobol_over_course_tex_docs(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cobol-course-repo"
    (repo_path / "Course 1").mkdir(parents=True)
    (repo_path / "Course 2" / "Labs" / "cbl").mkdir(parents=True)
    (repo_path / "Course 3" / "Labs" / "cbl").mkdir(parents=True)
    (repo_path / "Course 4" / "Labs" / "cbl").mkdir(parents=True)
    for course_name in ("Course 1", "Course 2", "Course 3", "Course 4"):
        (repo_path / course_name / "Front_Matter.tex").write_text(
            "\\chapter{Course}\n",
            encoding="utf-8",
        )
    for relative_path, program_id in (
        ("Course 2/Labs/cbl/HELLO.cobol", "HELLO"),
        ("Course 2/Labs/cbl/ADDAMT.cobol", "ADDAMT"),
        ("Course 3/Labs/cbl/DEBUGME.cbl", "DEBUGME"),
        ("Course 4/Labs/cbl/DEPTPAY.CBL", "DEPTPAY"),
    ):
        (repo_path / relative_path).write_text(
            "       IDENTIFICATION DIVISION.\n"
            f"       PROGRAM-ID. {program_id}.\n"
            "       PROCEDURE DIVISION.\n"
            "           GOBACK.\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "tex" in seed_plan["detected_ecosystems"]
    assert "cobol" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "cobol"
    assert any(path.lower().endswith((".cbl", ".cobol")) for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_uses_pascal_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "pascal-project-repo"
    (repo_path / "app" / "source").mkdir(parents=True)
    (repo_path / "app" / "tests").mkdir(parents=True)
    (repo_path / "app" / "Acme.lpi").write_text("<CONFIG></CONFIG>\n", encoding="utf-8")
    (repo_path / "app" / "main.lpr").write_text(
        "program AcmeApp;\n"
        "uses AcmeUtil;\n"
        "begin\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "source" / "AcmeUtil.pas").write_text(
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
    (repo_path / "app" / "tests" / "MainTests.pas").write_text(
        "unit MainTests;\ninterface\nimplementation\nend.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "pascal" in seed_plan["detected_ecosystems"]
    assert "app/Acme.lpi" in seed_plan["config_paths"]
    assert "app" in seed_plan["support_roots"]
    assert "app/source" in seed_plan["support_roots"]
    assert "app/main.lpr" in seed_plan["entrypoint_files"]
    assert "app/tests/MainTests.pas" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_delphi_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "delphi-project-repo"
    (repo_path / "App" / "source").mkdir(parents=True)
    (repo_path / "App" / "tests").mkdir(parents=True)
    (repo_path / "App" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpr</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "AcmeApp.dpr").write_text(
        "program AcmeApp;\n"
        "uses MainForm in 'source/MainForm.pas';\n"
        "begin\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "source" / "MainForm.pas").write_text(
        "unit MainForm;\n"
        "interface\n"
        "uses System.SysUtils, Vcl.Forms;\n"
        "{$R *.dfm}\n"
        "implementation\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "tests" / "MainTests.pas").write_text(
        "unit MainTests;\ninterface\nimplementation\nend.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["delphi"]
    assert seed_plan["operational_ecosystems"] == ["delphi"]
    assert "App/AcmeApp.dproj" in seed_plan["config_paths"]
    assert "App" in seed_plan["support_roots"]
    assert "App/source" in seed_plan["support_roots"]
    assert "App/AcmeApp.dpr" in seed_plan["entrypoint_files"]
    assert "App/source/MainForm.pas" in seed_plan["candidate_file_paths"]
    assert "App/tests/MainTests.pas" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_lisp_asd_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lisp-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "acme.asd").write_text(
        '(asdf:defsystem "acme"\n'
        '  :pathname "src"\n'
        '  :components ((:file "package") (:file "helper") (:file "app")))\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "package.lisp").write_text(
        "(defpackage #:acme.helper (:use #:cl) (:export #:helper))\n"
        "(defpackage #:acme.app (:use #:cl) (:import-from #:acme.helper #:helper))\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.lisp").write_text(
        "(in-package #:acme.helper)\n"
        "(defun helper () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "app.lisp").write_text(
        "(in-package #:acme.app)\n"
        "(defun run () (helper))\n",
        encoding="utf-8",
    )

    seed_plan = probe_module._derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["lisp"]
    assert seed_plan["operational_ecosystems"] == ["lisp"]
    assert "acme.asd" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/package.lisp" in seed_plan["entrypoint_files"]
    assert "src/app.lisp" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_foxpro_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "foxpro-profile-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
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
    (repo_path / "tests" / "main_test.prg").write_text(
        "FUNCTION run_test()\n"
        "    RETURN .T.\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )

    seed_plan = probe_module._derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["foxpro"]
    assert seed_plan["operational_ecosystems"] == ["foxpro"]
    assert "programs/main.prg" in seed_plan["entrypoint_files"]
    assert "tests/main_test.prg" not in seed_plan["entrypoint_files"]
    assert "programs/util.prg" in seed_plan["candidate_file_paths"]
    assert "programs" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_prefers_foxpro_over_package_json_host(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "foxpro-node-profile-repo"
    (repo_path / "nfJson").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{"name":"nfjson","private":true}',
        encoding="utf-8",
    )
    (repo_path / "nfJson" / "nfOpenJson.prg").write_text(
        "FUNCTION nfOpenJson(tcJson)\n"
        "    RETURN tcJson\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "nfJson" / "nfJsonCreate.prg").write_text(
        "FUNCTION nfJsonCreate()\n"
        "    RETURN '{}'\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "nfJson" / "nfJsonRead.prg").write_text(
        "FUNCTION nfJsonRead(tcJson)\n"
        "    RETURN tcJson\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )

    seed_plan = probe_module._derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "node" in seed_plan["detected_ecosystems"]
    assert "foxpro" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "foxpro"
    assert "nfJson/nfOpenJson.prg" in seed_plan["entrypoint_files"]
    assert "package.json" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_detects_solidity_foundry_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "solidity-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "foundry.toml").write_text(
        '[profile.default]\nsrc = "src"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Ownable.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "abstract contract Ownable {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Counter.sol").write_text(
        'pragma solidity ^0.8.20;\n'
        'import {Ownable} from "./Ownable.sol";\n'
        "contract Counter is Ownable {}\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "Counter.t.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "contract CounterTest {}\n",
        encoding="utf-8",
    )

    seed_plan = probe_module._derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["solidity"]
    assert seed_plan["operational_ecosystems"] == ["solidity"]
    assert "src/Counter.sol" in seed_plan["entrypoint_files"]
    assert "test/Counter.t.sol" not in seed_plan["entrypoint_files"]
    assert "src" in seed_plan["support_roots"]
    assert "foundry.toml" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_plsql_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "plsql-profile-repo"
    (repo_path / "db").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "db" / "app_util.pks").write_text(
        "create or replace package app_util as\n"
        "  procedure record_order(p_order_id in number);\n"
        "end app_util;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "db" / "order_api.pks").write_text(
        "create or replace package order_api as\n"
        "  procedure submit_order;\n"
        "end order_api;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "db" / "order_api.pkb").write_text(
        "create or replace package body order_api as\n"
        "  procedure submit_order is\n"
        "  begin\n"
        "    app_util.record_order(42);\n"
        "  end submit_order;\n"
        "end order_api;\n"
        "/\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "order_api_test.prc").write_text(
        "create or replace procedure order_api_test is\nbegin\n  null;\nend;\n/\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["plsql"]
    assert "db/order_api.pkb" in seed_plan["entrypoint_files"]
    assert "db/order_api.pks" not in seed_plan["entrypoint_files"]
    assert "tests/order_api_test.prc" not in seed_plan["entrypoint_files"]
    assert "db/order_api.pks" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_sas_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sas-profile-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "macros").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
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
    (repo_path / "tests" / "report_test.sas").write_text(
        "%macro report_test();\n"
        "  %put test;\n"
        "%mend report_test;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["sas"]
    assert "programs/report.sas" in seed_plan["entrypoint_files"]
    assert "tests/report_test.sas" not in seed_plan["entrypoint_files"]
    assert "macros/render_table.sas" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_matlab_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "matlab-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "helper.m").write_text(
        "function value = helper()\n"
        "value = 1;\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.m").write_text(
        "function value = main()\n"
        "value = helper();\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_test.m").write_text(
        "function value = main_test()\n"
        "value = 0;\n"
        "end\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["matlab"]
    assert "src/main.m" in seed_plan["entrypoint_files"]
    assert "src/helper.m" in seed_plan["candidate_file_paths"]
    assert "tests/main_test.m" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_objective_c_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "objective-c-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "ACMHelper.h").write_text(
        "#import <Foundation/Foundation.h>\n"
        "@interface ACMHelper : NSObject\n"
        "+ (void)work;\n"
        "@end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "ACMClient.m").write_text(
        "#import \"ACMHelper.h\"\n"
        "@interface ACMClient : NSObject\n"
        "- (void)run;\n"
        "@end\n"
        "@implementation ACMClient\n"
        "- (void)run {\n"
        "    [ACMHelper work];\n"
        "}\n"
        "@end\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "ACMClientTests.m").write_text(
        "#import <Foundation/Foundation.h>\n"
        "@interface ACMClientTests : NSObject\n"
        "@end\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["objectivec"]
    assert "src/ACMClient.m" in seed_plan["entrypoint_files"]
    assert "src/ACMHelper.h" in seed_plan["candidate_file_paths"]
    assert "tests/ACMClientTests.m" not in seed_plan["entrypoint_files"]
