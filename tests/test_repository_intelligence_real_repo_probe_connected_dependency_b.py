"""Tests for repository_intelligence_real_repo_probe: connected_dependency_b.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_connected_dependency_map_follows_systemverilog_include_and_instantiation_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "systemverilog-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["rtl/top.sv"],
        bridge_paths=["rtl"],
        include_patterns=["**/*.sv", "*.sv", "**/*.svh", "*.svh", "**/*.v", "*.v", "**/*.vh", "*.vh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "rtl/child.sv",
        "rtl/defs.svh",
        "rtl/top.sv",
    ]


def test_connected_dependency_map_follows_verilog_include_and_instantiation_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "verilog-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["rtl/top.v"],
        bridge_paths=["rtl"],
        include_patterns=["**/*.v", "*.v", "**/*.vh", "*.vh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "rtl/child.v",
        "rtl/defs.vh",
        "rtl/top.v",
    ]


def test_connected_dependency_map_follows_gdscript_preload_and_extends_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gdscript-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/player.gd"],
        bridge_paths=["src"],
        include_patterns=["**/*.gd", "*.gd", "project.godot"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "src/base_actor.gd",
        "src/player.gd",
        "src/utils.gd",
    ]


def test_connected_dependency_map_follows_gml_script_and_object_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gml-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["objects/Entity/Create_0.gml"],
        bridge_paths=["scripts", "objects"],
        include_patterns=["**/*.gml", "*.gml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "objects/Entity/Create_0.gml",
        "scripts/tree_api/tree_api.gml",
        "scripts/tree_runtime/tree_runtime.gml",
    ]


def test_connected_dependency_map_follows_vhdl_use_and_instantiation_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vhdl-connected-map-repo"
    (repo_path / "rtl").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["rtl/top.vhd"],
        bridge_paths=["rtl"],
        include_patterns=["**/*.vhd", "*.vhd", "**/*.vhdl", "*.vhdl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "rtl/child.vhd",
        "rtl/defs.vhd",
        "rtl/top.vhd",
    ]


def test_connected_dependency_map_follows_prolog_use_module_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "prolog-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "related.pl").write_text(
        ":- module(related, [related/2]).\n"
        ":- use_module('family.pl', [ancestor/2]).\n"
        "related(X, Y) :- ancestor(X, Y).\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/related.pl"],
        bridge_paths=["src"],
        include_patterns=[
            "src/**/*.pl",
            "src/*.pl",
            "src/**/*.prolog",
            "src/*.prolog",
            "*.pl",
            "*.prolog",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/family.pl",
        "src/related.pl",
    ]


def test_connected_dependency_map_follows_ml_open_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ml-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "project.mlb").write_text(
        "src/Util.sml\n"
        "src/Main.sml\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Util.sml").write_text(
        "structure Util = struct\n"
        "fun helper () = 1\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.sml").write_text(
        "structure Main = struct\n"
        "open Util\n"
        "val run = helper ()\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.sml"],
        bridge_paths=["src", "project.mlb"],
        include_patterns=[
            "src/**/*.sml",
            "src/*.sml",
            "src/**/*.sig",
            "src/*.sig",
            "src/**/*.fun",
            "src/*.fun",
            "*.mlb",
            "*.cm",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/Main.sml",
        "src/Util.sml",
    ]


def test_connected_dependency_map_follows_classic_visual_basic_project_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\n'
        'Class=cHelper; src/cHelper.cls\n'
        'Module=modMain; src/modMain.bas\n'
        'Form=src/Form1.frm\n'
        'Startup="Form1"\n'
        'Name="Project1"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        "End\n"
        'Attribute VB_Name = "Form1"\n'
        "Option Explicit\n"
        "Private mHelper As cHelper\n"
        "Private Sub Form_Load()\n"
        "    Set mHelper = New cHelper\n"
        "    Debug.Print mHelper.Helper()\n"
        "    modMain.RunApp\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "cHelper.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
        "Public Function Helper() As String\n"
        '    Helper = "ok"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Form1.frm"],
        bridge_paths=["src", "Project1.vbp"],
        include_patterns=[
            "src/**/*.bas",
            "src/*.bas",
            "src/**/*.cls",
            "src/*.cls",
            "src/**/*.frm",
            "src/*.frm",
            "*.vbp",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 3
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "src/Form1.frm" in connected_map["connected_files"]
    assert "src/cHelper.cls" in connected_map["connected_files"]
    assert "src/modMain.bas" in connected_map["connected_files"]


def test_connected_dependency_map_follows_vba_module_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "vba-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "JsonData.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "JsonData"\n'
        "Option Explicit\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "JsonConverter.bas").write_text(
        'Attribute VB_Name = "JsonConverter"\n'
        "Option Explicit\n"
        "Public Sub Main()\n"
        "    Dim data As JsonData\n"
        "    Set data = New JsonData\n"
        "    Debug.Print data.ToJson()\n"
        "End Sub\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/JsonConverter.bas"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.bas", "src/*.bas", "src/**/*.cls", "src/*.cls"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/JsonConverter.bas",
        "src/JsonData.cls",
    ]


def test_connected_dependency_map_skips_missing_classic_visual_basic_project_targets(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-missing-target-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\n'
        'Class=cMissing; [CLASS]/cMissing.cls\n'
        'Module=modMain; src/modMain.bas\n'
        'Form=src/Form1.frm\n'
        'Startup="Form1"\n'
        'Name="Project1"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        "End\n"
        'Attribute VB_Name = "Form1"\n'
        "Option Explicit\n"
        "Private Sub Form_Load()\n"
        "    modMain.RunApp\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Form1.frm"],
        bridge_paths=["src", "Project1.vbp"],
        include_patterns=[
            "src/**/*.bas",
            "src/*.bas",
            "src/**/*.cls",
            "src/*.cls",
            "src/**/*.frm",
            "src/*.frm",
            "*.vbp",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert "src/Form1.frm" in connected_map["connected_files"]
    assert "src/modMain.bas" in connected_map["connected_files"]
    assert "[CLASS]/cMissing.cls" not in connected_map["connected_files"]
    assert connected_map["unresolved_dependency_count"] >= 1


def test_connected_dependency_map_follows_lisp_asd_and_package_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lisp-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/app.lisp"],
        bridge_paths=["src", "acme.asd"],
        include_patterns=["*.asd", "src/**/*.lisp", "src/*.lisp"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "src/app.lisp" in connected_map["connected_files"]
    assert "src/helper.lisp" in connected_map["connected_files"]


def test_connected_dependency_map_follows_emacslisp_require_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "emacslisp-connected-map-repo"
    (repo_path / "lisp").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.el"],
        bridge_paths=["lisp", "Cask"],
        include_patterns=["*.el", "lisp/**/*.el", "lisp/*.el", "Cask"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "main.el" in connected_map["connected_files"]
    assert "lisp/helper.el" in connected_map["connected_files"]


def test_connected_dependency_map_follows_vimscript_source_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vimscript-connected-map-repo"
    (repo_path / "plugin").mkdir(parents=True)
    (repo_path / "autoload").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["plugin/fugitive.vim"],
        bridge_paths=["plugin", "autoload"],
        include_patterns=[
            "plugin/**/*.vim",
            "plugin/*.vim",
            "autoload/**/*.vim",
            "autoload/*.vim",
            "*.vim",
            ".vimrc",
            "vimrc",
            "gvimrc",
            "_vimrc",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "plugin/fugitive.vim" in connected_map["connected_files"]
    assert "autoload/fugitive.vim" in connected_map["connected_files"]


def test_connected_dependency_map_follows_racket_require_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "racket-connected-map-repo"
    (repo_path / "private").mkdir(parents=True)
    (repo_path / "info.rkt").write_text(
        "#lang info\n"
        '(define collection "acme")\n',
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.rkt"],
        bridge_paths=["private", "info.rkt"],
        include_patterns=["*.rkt", "private/**/*.rkt", "private/*.rkt"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "main.rkt" in connected_map["connected_files"]
    assert "private/helper.rkt" in connected_map["connected_files"]


def test_connected_dependency_map_follows_scheme_import_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scheme-connected-map-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.scm"],
        bridge_paths=["lib", "package.scm"],
        include_patterns=["*.scm", "lib/**/*.sld", "lib/*.sld", "*.sld"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert "main.scm" in connected_map["connected_files"]
    assert "lib/acme/helper.sld" in connected_map["connected_files"]


def test_connected_dependency_map_follows_foxpro_set_procedure_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "foxpro-connected-map-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "include" / "common.h").write_text(
        '#define APP_NAME "Acme"\n',
        encoding="utf-8",
    )
    (repo_path / "programs" / "util.prg").write_text(
        "FUNCTION helper()\n"
        "    RETURN 1\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "programs" / "main.prg").write_text(
        '#INCLUDE "../include/common.h"\n'
        "SET PROCEDURE TO programs/util ADDITIVE\n"
        "FUNCTION run()\n"
        "    RETURN helper()\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["programs/main.prg"],
        bridge_paths=["programs", "include"],
        include_patterns=[
            "programs/**/*.prg",
            "programs/*.prg",
            "include/**/*.h",
            "include/*.h",
            "*.prg",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "include/common.h",
        "programs/main.prg",
        "programs/util.prg",
    ]


