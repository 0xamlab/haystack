"""Tests for repository_intelligence_real_repo_probe: operational_seed_h.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_plan_without_diagnostics_uses_v_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "v-profile-repo"
    (repo_path / "src" / "helper").mkdir(parents=True)
    (repo_path / "v.mod").write_text(
        "Module {\n"
        "    name: 'demo'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.v").write_text(
        "module main\n"
        "\n"
        "import helper\n"
        "\n"
        "fn main() {\n"
        "    helper.render_json()\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper" / "helper.v").write_text(
        "module helper\n"
        "\n"
        "pub fn render_json() string {\n"
        "    return '{}'\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["v"]
    assert seed_plan["operational_ecosystems"] == ["v"]
    assert "v.mod" in seed_plan["config_paths"]
    assert "main.v" in seed_plan["entrypoint_files"]
    assert "src/helper" in seed_plan["support_roots"]
    assert "src/helper/helper.v" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_verilog_manifestless_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "verilog-profile-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "defs.vh").write_text(
        "`ifndef DEFS_VH\n"
        "`define DEFS_VH\n"
        "`endif\n",
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
        "endmodule\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["verilog"]
    assert seed_plan["operational_ecosystems"] == ["verilog"]
    assert "rtl/top.v" in seed_plan["entrypoint_files"]
    assert "rtl" in seed_plan["support_roots"]
    assert "rtl/child.v" in seed_plan["candidate_file_paths"]
    assert "rtl/defs.vh" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_smalltalk_ston_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smalltalk-profile-repo"
    (repo_path / "src" / "Demo-Baseline").mkdir(parents=True)
    (repo_path / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / "tests" / "Demo-Core-Tests").mkdir(parents=True)
    (repo_path / ".smalltalk.ston").write_text("{ }\n", encoding="utf-8")
    (repo_path / "src" / "Demo-Baseline" / "package.st").write_text(
        "Package { #name : 'Demo-Baseline' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-Baseline" / "BaselineOfDemo.class.st").write_text(
        "Class {\n"
        "\t#name : 'BaselineOfDemo',\n"
        "\t#superclass : 'BaselineOf',\n"
        "\t#category : 'Demo-Baseline',\n"
        "\t#package : 'Demo-Baseline'\n"
        "}\n",
        encoding="utf-8",
    )
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
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Demo-Core-Tests" / "HelperTest.class.st").write_text(
        "Class {\n"
        "\t#name : 'HelperTest',\n"
        "\t#superclass : 'TestCase',\n"
        "\t#category : 'Demo-Core-Tests',\n"
        "\t#package : 'Demo-Core-Tests'\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["smalltalk"]
    assert seed_plan["operational_ecosystems"] == ["smalltalk"]
    assert ".smalltalk.ston" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Demo-Baseline/BaselineOfDemo.class.st" in seed_plan["entrypoint_files"]
    assert "src/Demo-Core/Helper.class.st" in seed_plan["candidate_file_paths"]
    assert "tests/Demo-Core-Tests/HelperTest.class.st" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_emacslisp_cask_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "emacslisp-profile-repo"
    (repo_path / "lisp").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Cask").write_text(
        "(source gnu)\n"
        '(package-file "main.el")\n',
        encoding="utf-8",
    )
    (repo_path / "main.el").write_text(
        "(require 'helper)\n"
        "(provide 'main)\n"
        "(defun run () (helper-fn))\n",
        encoding="utf-8",
    )
    (repo_path / "lisp" / "helper.el").write_text(
        "(provide 'helper)\n"
        "(defun helper-fn () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main-test.el").write_text(
        "(provide 'main-test)\n"
        "(defun run-test () t)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["emacslisp"]
    assert seed_plan["operational_ecosystems"] == ["emacslisp"]
    assert seed_plan["config_paths"] == ["Cask"]
    assert "lisp" in seed_plan["support_roots"]
    assert "main.el" in seed_plan["entrypoint_files"]
    assert "lisp/helper.el" in seed_plan["entrypoint_files"]
    assert "tests/main-test.el" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_vimscript_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vimscript-profile-repo"
    (repo_path / "plugin").mkdir(parents=True)
    (repo_path / "autoload").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "vimrc").write_text("set runtimepath^=.\n", encoding="utf-8")
    (repo_path / "autoload" / "fugitive.vim").write_text(
        "function! fugitive#run()\n"
        "  return '{}'\n"
        "endfunction\n",
        encoding="utf-8",
    )
    (repo_path / "plugin" / "fugitive.vim").write_text(
        "source ../autoload/fugitive.vim\n"
        "call fugitive#run()\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "fugitive_spec.vim").write_text(
        "call assert_equal('{}', fugitive#run())\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["vimscript"]
    assert seed_plan["operational_ecosystems"] == ["vimscript"]
    assert "vimrc" in seed_plan["config_paths"]
    assert "plugin/fugitive.vim" in seed_plan["entrypoint_files"]
    assert "tests/fugitive_spec.vim" not in seed_plan["entrypoint_files"]
    assert "autoload" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_uses_racket_info_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "racket-profile-repo"
    (repo_path / "private").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "info.rkt").write_text(
        "#lang info\n"
        '(define collection "racket-profile-repo")\n',
        encoding="utf-8",
    )
    (repo_path / "main.rkt").write_text(
        "#lang racket\n"
        '(require "private/helper.rkt")\n'
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "private" / "helper.rkt").write_text(
        "#lang racket\n"
        "(define (helper) 1)\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main-test.rkt").write_text(
        "#lang racket\n"
        "(define (test-run) 1)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["racket"]
    assert seed_plan["operational_ecosystems"] == ["racket"]
    assert seed_plan["config_paths"] == ["info.rkt"]
    assert "private" in seed_plan["support_roots"]
    assert "main.rkt" in seed_plan["entrypoint_files"]
    assert "private/helper.rkt" in seed_plan["entrypoint_files"]
    assert "tests/main-test.rkt" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_scheme_package_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scheme-profile-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "package.scm").write_text(
        "(define-library (acme app)\n"
        "  (export run)\n"
        "  (import (acme helper))\n"
        "  (begin\n"
        "    (define (run) (helper))))\n",
        encoding="utf-8",
    )
    (repo_path / "main.scm").write_text(
        "#!r6rs\n"
        "(import (acme helper))\n"
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "helper.sld").write_text(
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "helper-test.scm").write_text(
        "#!r6rs\n"
        "(define (test-helper) 1)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["scheme"]
    assert seed_plan["operational_ecosystems"] == ["scheme"]
    assert seed_plan["config_paths"] == ["package.scm"]
    assert any(root == "lib" or root.startswith("lib/") for root in seed_plan["support_roots"])
    assert "main.scm" in seed_plan["entrypoint_files"]
    assert "lib/acme/helper.sld" in seed_plan["entrypoint_files"]
    assert "tests/helper-test.scm" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_xpp_descriptor_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "xpp-profile-repo"
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Acme"
        / "AxClass"
    ).mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Descriptor"
    ).mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Descriptor"
        / "Acme.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxModelInfo>\n"
        "  <Name>Acme</Name>\n"
        "</AxModelInfo>\n",
        encoding="utf-8",
    )
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
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Tests"
        / "AxClass"
    ).mkdir(parents=True)
    (
        repo_path
        / "PackagesLocalDirectory"
        / "Acme"
        / "Tests"
        / "AxClass"
        / "MainWorkerTest.xml"
    ).write_text(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<AxClass>\n"
        "  <Name>MainWorkerTest</Name>\n"
        "  <SourceCode>\n"
        "    <Declaration><![CDATA[\n"
        "class MainWorkerTest\n"
        "{\n"
        "}\n"
        "]]></Declaration>\n"
        "  </SourceCode>\n"
        "</AxClass>\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["xpp"]
    assert seed_plan["operational_ecosystems"] == ["xpp"]
    assert seed_plan["config_paths"] == ["PackagesLocalDirectory/Acme/Descriptor/Acme.xml"]
    assert "PackagesLocalDirectory/Acme/Acme/AxClass" in seed_plan["support_roots"]
    assert "PackagesLocalDirectory/Acme/Acme/AxClass/MainWorker.xml" in seed_plan["entrypoint_files"]
    assert "PackagesLocalDirectory/Acme/Acme/AxClass/BaseWorker.xml" in seed_plan["entrypoint_files"]
    assert "PackagesLocalDirectory/Acme/Tests/AxClass/MainWorkerTest.xml" not in seed_plan[
        "entrypoint_files"
    ]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_scratch_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scratch-profile-repo"
    _write_scratch_project(
        repo_path / "games" / "Maze.sb3",
        _scratch_project_payload(),
    )
    _write_scratch_project(
        repo_path / "tests" / "MazeTest.sb3",
        _scratch_project_payload(name="TestSprite"),
    )
    (repo_path / "README.md").write_text("# Scratch Repo\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["scratch"]
    assert seed_plan["operational_ecosystems"] == ["scratch"]
    assert seed_plan["config_paths"] == []
    assert "games" in seed_plan["support_roots"]
    assert "games/Maze.sb3" in seed_plan["entrypoint_files"]
    assert "tests/MazeTest.sb3" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_labview_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "labview-profile-repo"
    (repo_path / "Source" / "Libraries").mkdir(parents=True)
    (repo_path / "Source" / "Controls").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "App.lvproj").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Project Type=\"Project\">\n"
        '  <Item Name="Main" Type="VI" URL="Source/Main.vi" />\n'
        '  <Item Name="Helpers" Type="Library" URL="Source/Libraries/Helpers.lvlib" />\n'
        '  <Item Name="Config" Type="Control" URL="Source/Controls/Config.ctl" />\n'
        '  <Item Name="MainTest" Type="VI" URL="tests/MainTest.vi" />\n'
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
    (repo_path / "tests" / "MainTest.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["labview"]
    assert seed_plan["operational_ecosystems"] == ["labview"]
    assert "App.lvproj" in seed_plan["config_paths"]
    assert "Source" in seed_plan["support_roots"]
    assert "Source/Libraries" in seed_plan["support_roots"]
    assert "Source/Controls" in seed_plan["support_roots"]
    assert "Source/Main.vi" in seed_plan["entrypoint_files"]
    assert "Source/Libraries/Helpers.lvlib" in seed_plan["entrypoint_files"]
    assert "Source/Controls/Config.ctl" not in seed_plan["entrypoint_files"]
    assert "tests/MainTest.vi" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_tcl_pkgindex_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tcl-profile-repo"
    (repo_path / "modules" / "demo").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
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
    (repo_path / "tests" / "demo_test.tcl").write_text(
        "source ../modules/demo/demo.tcl\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["tcl"]
    assert seed_plan["operational_ecosystems"] == ["tcl"]
    assert "modules/demo/pkgIndex.tcl" in seed_plan["config_paths"]
    assert "modules/demo" in seed_plan["support_roots"]
    assert "modules/demo/demo.tcl" in seed_plan["entrypoint_files"]
    assert "modules/demo/pkgIndex.tcl" not in seed_plan["entrypoint_files"]
    assert "tests/demo_test.tcl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_systemverilog_bender_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "systemverilog-profile-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Bender.yml").write_text(
        "sources:\n"
        "  - rtl/defs.svh\n"
        "  - rtl/child.sv\n"
        "  - rtl/top.sv\n",
        encoding="utf-8",
    )
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
    (repo_path / "tests" / "top_test.sv").write_text(
        "module top_test;\n"
        "  top dut();\n"
        "endmodule\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["systemverilog"]
    assert seed_plan["operational_ecosystems"] == ["systemverilog"]
    assert "Bender.yml" in seed_plan["config_paths"]
    assert "rtl" in seed_plan["support_roots"]
    assert "rtl/top.sv" in seed_plan["entrypoint_files"]
    assert "rtl/defs.svh" not in seed_plan["entrypoint_files"]
    assert "tests/top_test.sv" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_project_godot_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gdscript-profile-repo"
    (repo_path / "src" / "Autoload").mkdir(parents=True)
    (repo_path / "scenes").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "project.godot").write_text(
        "[application]\n"
        'run/main_scene="res://scenes/main.tscn"\n'
        "\n"
        "[autoload]\n"
        'Global="*res://src/Autoload/Global.gd"\n',
        encoding="utf-8",
    )
    (repo_path / "scenes" / "main.tscn").write_text(
        '[gd_scene format=3]\n'
        '[ext_resource type="Script" path="res://src/main.gd" id="1"]\n'
        '[node name="Root" type="Node"]\n'
        'script = ExtResource("1")\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.gd").write_text(
        "class_name MainScene\n"
        "extends Node\n"
        "func _ready() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Autoload" / "Global.gd").write_text(
        "class_name Global\n"
        "extends Node\n"
        "func ping() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "player_test.gd").write_text(
        "extends Node\n"
        "func _ready() -> void:\n"
        "    pass\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["gdscript"]
    assert seed_plan["operational_ecosystems"] == ["gdscript"]
    assert "project.godot" in seed_plan["config_paths"]
    assert any(root in seed_plan["support_roots"] for root in {"src", "src/Autoload"})
    assert "src/main.gd" in seed_plan["entrypoint_files"]
    assert "src/Autoload/Global.gd" in seed_plan["entrypoint_files"]
    assert "tests/player_test.gd" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_gml_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gml-profile-repo"
    (repo_path / "scripts" / "tree_runtime").mkdir(parents=True)
    (repo_path / "scripts" / "tree_api").mkdir(parents=True)
    (repo_path / "objects" / "Entity").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "BehaviorTree.yyp").write_text(
        "{\n"
        '  "resources": [\n'
        '    {\n'
        '      "id": {\n'
        '        "path": "scripts/tree_runtime/tree_runtime.yy",\n'
        "      },\n"
        "    },\n"
        '    {\n'
        '      "id": {\n'
        '        "path": "scripts/tree_api/tree_api.yy",\n'
        "      },\n"
        "    },\n"
        '    {\n'
        '      "id": {\n'
        '        "path": "objects/Entity/Entity.yy",\n'
        "      },\n"
        "    },\n"
        "  ],\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_runtime" / "tree_runtime.yy").write_text(
        "{\n}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_runtime" / "tree_runtime.gml").write_text(
        "function __BHTree() constructor {\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_api" / "tree_api.yy").write_text(
        "{\n}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "tree_api" / "tree_api.gml").write_text(
        "function bh_tree() {\n"
        "    return new __BHTree();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "objects" / "Entity" / "Entity.yy").write_text(
        "{\n}\n",
        encoding="utf-8",
    )
    (repo_path / "objects" / "Entity" / "Create_0.gml").write_text(
        "function setup() {\n"
        "    return bh_tree();\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "tree_test.gml").write_text(
        "function tree_test() {\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["gml"]
    assert seed_plan["operational_ecosystems"] == ["gml"]
    assert "BehaviorTree.yyp" in seed_plan["config_paths"]
    assert any(root in seed_plan["support_roots"] for root in {"scripts", "scripts/tree_api"})
    assert any(root in seed_plan["support_roots"] for root in {"objects", "objects/Entity"})
    assert "scripts/tree_runtime/tree_runtime.gml" in seed_plan["entrypoint_files"]
    assert "scripts/tree_api/tree_api.gml" in seed_plan["entrypoint_files"]
    assert "objects/Entity/Create_0.gml" in seed_plan["entrypoint_files"]
    assert "tests/tree_test.gml" not in seed_plan["entrypoint_files"]


