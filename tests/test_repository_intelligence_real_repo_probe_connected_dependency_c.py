"""Tests for repository_intelligence_real_repo_probe: connected_dependency_c.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_connected_dependency_map_follows_solidity_import_and_inheritance_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "solidity-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Counter.sol"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.sol", "src/*.sol", "*.sol"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "src/Counter.sol",
        "src/Ownable.sol",
    ]


def test_connected_dependency_map_follows_plsql_package_and_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "plsql-connected-map-repo"
    (repo_path / "db").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["db/order_api.pkb"],
        bridge_paths=["db"],
        include_patterns=[
            "db/**/*.pkb",
            "db/*.pkb",
            "db/**/*.pks",
            "db/*.pks",
            "db/**/*.pls",
            "db/*.pls",
            "db/**/*.prc",
            "db/*.prc",
            "db/**/*.fnc",
            "db/*.fnc",
            "db/**/*.trg",
            "db/*.trg",
            "*.pkb",
            "*.pks",
            "*.pls",
            "*.prc",
            "*.fnc",
            "*.trg",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "db/app_util.pks",
        "db/order_api.pkb",
        "db/order_api.pks",
    ]


def test_connected_dependency_map_follows_sas_include_and_macro_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "sas-connected-map-repo"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["programs/report.sas"],
        bridge_paths=["programs", "macros"],
        include_patterns=[
            "programs/**/*.sas",
            "programs/*.sas",
            "macros/**/*.sas",
            "macros/*.sas",
            "*.sas",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "macros/render_table.sas",
        "programs/report.sas",
    ]


def test_connected_dependency_map_follows_matlab_call_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "matlab-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.m"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.m", "src/*.m", "*.m"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/helper.m",
        "src/main.m",
    ]


def test_connected_dependency_map_follows_objective_c_import_and_message_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "objective-c-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/ACMClient.m"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.h", "src/*.h", "src/**/*.m", "src/*.m"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {"src/ACMClient.m", "src/ACMHelper.h"}


def test_connected_dependency_map_follows_assembly_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "assembly-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "include" / "io.inc").write_text(
        "extern print_string\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "io.asm").write_text(
        "global print_string\n"
        "print_string:\n"
        "    ret\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.asm").write_text(
        "%include \"../include/io.inc\"\n"
        "global main\n"
        "main:\n"
        "    call print_string\n"
        "    ret\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.asm"],
        bridge_paths=["src", "include"],
        include_patterns=[
            "src/**/*.asm",
            "src/*.asm",
            "include/**/*.inc",
            "include/*.inc",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert set(connected_map["connected_files"]) == {
        "include/io.inc",
        "src/io.asm",
        "src/main.asm",
    }


def test_connected_dependency_map_follows_abap_include_and_static_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "abap-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "zcl_math.clas.abap").write_text(
        "CLASS zcl_math DEFINITION PUBLIC.\n"
        "  PUBLIC SECTION.\n"
        "    CLASS-METHODS add_one IMPORTING iv_value TYPE i RETURNING VALUE(rv_value) TYPE i.\n"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/zcl_report.clas.abap"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.abap", "src/*.abap", "*.abap"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "src/zcl_math.clas.abap",
        "src/zcl_report.clas.abap",
        "src/zcl_report.clas.locals_imp.abap",
    ]


def test_connected_dependency_map_follows_d_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "d-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "dub.json").write_text(
        '{\n  "name": "acme"\n}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "utils.d").write_text(
        "module acme.utils;\nint helper() { return 1; }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "main.d").write_text(
        "module acme.main;\nimport acme.utils : helper;\nint main() { return helper(); }\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme/main.d"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.d", "src/*.d", "dub.json", "dub.sdl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme/main.d",
        "src/acme/utils.d",
    ]


def test_connected_dependency_map_follows_vala_import_and_method_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vala-connected-map-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "util").mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('demo', 'vala')\n"
        "executable('demo', ['src/demo/app/Main.vala', 'src/demo/util/Helper.vala'])\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "util" / "Helper.vala").write_text(
        "namespace Demo.Util {\n"
        "    public class Helper : Object {\n"
        "        public string render_json () {\n"
        '            return "{}";\n'
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "app" / "Main.vala").write_text(
        "using Demo.Util;\n"
        "\n"
        "namespace Demo.App {\n"
        "    public class App : Object {\n"
        "        public void run () {\n"
        "            Helper helper = new Helper ();\n"
        "            helper.render_json ();\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/demo/app/Main.vala"],
        bridge_paths=["src"],
        include_patterns=[
            "src/**/*.vala",
            "src/*.vala",
            "*.vala",
            "**/*.vapi",
            "*.vapi",
            "meson.build",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/demo/app/Main.vala",
        "src/demo/util/Helper.vala",
    }


def test_connected_dependency_map_follows_mql5_include_and_method_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "mql5-connected-map-repo"
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
        "void OnStart()\n"
        "{\n"
        "   Helper helper;\n"
        "   helper.RenderJson();\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Experts/Main.mq5"],
        bridge_paths=["Experts", "Include"],
        include_patterns=[
            "Experts/**/*.mq5",
            "Experts/*.mq5",
            "Include/**/*.mqh",
            "Include/*.mqh",
            "*.mqproj",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "Experts/Main.mq5",
        "Include/Helper.mqh",
    }


def test_connected_dependency_map_follows_gams_include_and_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "gams-connected-map-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "include" / "common.inc").write_text(
        "parameter demand(i);\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "main.gms").write_text(
        "$include ../include/common.inc\n"
        "set i /a,b/;\n"
        "parameter cost(i);\n"
        "equation balance;\n"
        "balance.. demand('a') =e= cost('a');\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["models/main.gms"],
        bridge_paths=["models", "include"],
        include_patterns=[
            "models/**/*.gms",
            "models/*.gms",
            "include/**/*.inc",
            "include/*.inc",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "models/main.gms",
        "include/common.inc",
    }


def test_connected_dependency_map_follows_openscad_include_and_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "openscad-connected-map-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "helper.scad").write_text(
        "module gusset(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.scad").write_text(
        "include <lib/helper.scad>;\n"
        "module build() {\n"
        "  gusset(10);\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.scad"],
        bridge_paths=["lib"],
        include_patterns=["**/*.scad", "*.scad"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "main.scad",
        "lib/helper.scad",
    }


def test_connected_dependency_map_follows_factor_using_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "factor-connected-map-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.factor").write_text(
        "USING: math ;\nIN: app.main\n\n: run ( n -- n ) square ;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["app/main.factor"],
        bridge_paths=["math"],
        include_patterns=["**/*.factor", "*.factor"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "app/main.factor",
        "math/math.factor",
    }


def test_connected_dependency_map_follows_cue_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cue-connected-map-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "pkg" / "schema").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text(
        'module: "example.com/demo"\n',
        encoding="utf-8",
    )
    (repo_path / "pkg" / "schema" / "schema.cue").write_text(
        "package schema\n\n#Answer: 42\n",
        encoding="utf-8",
    )
    (repo_path / "main.cue").write_text(
        'package main\n\nimport schema "example.com/demo/pkg/schema"\n\nvalue: schema.#Answer\n',
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.cue"],
        bridge_paths=["pkg/schema"],
        include_patterns=["**/*.cue", "*.cue"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] >= 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert {"main.cue", "pkg/schema/schema.cue"} <= set(connected_map["connected_files"])


def test_connected_dependency_map_follows_starlark_load_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "starlark-connected-map-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "lib" / "common.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "helper.bzl").write_text(
        "def emit_name(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "demo.bzl").write_text(
        'load("//lib:common.bzl", "render_json")\n'
        'load(":helper.bzl", "emit_name")\n'
        "\n"
        "def demo_macro(name):\n"
        "    return emit_name(render_json(name))\n",
        encoding="utf-8",
    )
    (repo_path / "BUILD.bazel").write_text(
        'load("rules:demo.bzl", "demo_macro")\n'
        '\n'
        'demo_macro(name = "app")\n',
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["BUILD.bazel"],
        bridge_paths=["rules", "lib"],
        include_patterns=[
            "**/*.bzl",
            "*.bzl",
            "**/*.star",
            "*.star",
            "**/BUILD.bazel",
            "BUILD.bazel",
            "**/BUILD",
            "BUILD",
            "MODULE.bazel",
            "WORKSPACE",
            "WORKSPACE.bazel",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 4
    assert connected_map["resolved_dependency_edges"] >= 3
    assert set(connected_map["connected_files"]) == {
        "BUILD.bazel",
        "rules/demo.bzl",
        "rules/helper.bzl",
        "lib/common.bzl",
    }


def test_connected_dependency_map_follows_nix_import_and_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "nix-connected-map-repo"
    (repo_path / "nix" / "lib").mkdir(parents=True)
    (repo_path / "nix" / "lib" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "{\n"
        "  mkFormatter = package: package;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "flake.nix").write_text(
        "{\n"
        "  inputs.nixpkgs.url = \"github:NixOS/nixpkgs\";\n"
        "  outputs = { self, nixpkgs }:\n"
        "    let formatter = import ./nix/lib/formatter.nix { pkgs = nixpkgs.legacyPackages.x86_64-linux; }; in {\n"
        "      formatter = formatter.mkFormatter nixpkgs.legacyPackages.x86_64-linux.alejandra;\n"
        "    };\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["flake.nix"],
        bridge_paths=["nix"],
        include_patterns=["**/*.nix", "*.nix"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "flake.nix",
        "nix/lib/formatter.nix",
    }


def test_connected_dependency_map_follows_purescript_import_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-connected-map-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "src" / "Main.purs").write_text(
        "module Main where\n\nimport Data.Helper (helperValue)\n\nmain = helperValue\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.purs").write_text(
        "module Data.Helper where\n\nhelperValue :: Int\nhelperValue = 1\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.purs"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.purs", "src/*.purs", "*.purs", "spago.yaml", "bower.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Main.purs",
        "src/Data/Helper.purs",
    }


