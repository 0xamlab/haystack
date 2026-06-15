"""Tests for repository_intelligence_service: language.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_language_for_path_detects_luau_suffix_and_markers() -> None:
    assert repository_service._language_for_path(
        Path("src/Main.luau"),
        text="--!strict\nreturn {}\n",
    ) == "luau"
    assert repository_service._language_for_path(
        Path("src/Main.lua"),
        text="--!strict\nexport type Packet = { id: string }\nreturn {}\n",
    ) == "luau"


def test_language_for_path_caches_classic_visual_basic_project_context_for_relative_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-context-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\nModule=modMain; src/modMain.bas\nStartup="modMain"\nName="Project1"\n',
        encoding="utf-8",
    )
    source_text = (
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n"
    )
    (repo_path / "src" / "modMain.bas").write_text(source_text, encoding="utf-8")

    repository_service._CLASSIC_VISUAL_BASIC_PROJECT_MEMBER_CACHE.clear()
    repository_service._CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE.clear()

    source_path = Path("src/modMain.bas")
    assert (
        repository_service._language_for_path(
            source_path,
            text=source_text,
            repo_root=repo_path,
        )
        == "vb6"
    )
    assert repository_service._CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE == {
        (str(repo_path), "src/modmain.bas"): True
    }
    assert (
        repository_service._language_for_path(
            source_path,
            text=source_text,
            repo_root=repo_path,
        )
        == "vb6"
    )
    assert repository_service._CLASSIC_VISUAL_BASIC_PROJECT_CONTEXT_CACHE == {
        (str(repo_path), "src/modmain.bas"): True
    }


def test_language_for_path_keeps_supported_suffixes_explicit() -> None:
    assert repository_service._language_for_path(Path("src/main.c")) == "c"
    assert repository_service._language_for_path(Path("src/Application.cfc")) == "cfml"
    assert repository_service._language_for_path(Path("views/index.cfm")) == "cfml"
    assert repository_service._language_for_path(Path("src/main.php")) == "php"
    assert repository_service._language_for_path(Path("src/Main.elm")) == "elm"
    assert repository_service._language_for_path(Path("src/main.el")) == "emacslisp"
    assert repository_service._language_for_path(Path("functions/helper.fish")) == "fish"
    assert repository_service._language_for_path(Path("plugin/fugitive.vim")) == "unknown"
    assert repository_service._language_for_path(Path("src/Main.as")) == "actionscript"
    assert repository_service._language_for_path(Path("scripts/Main.ahk")) == "autohotkey"
    assert repository_service._language_for_path(Path("scripts/Main.au3")) == "autoit"
    assert repository_service._language_for_path(Path("Dockerfile")) == "dockerfile"
    assert repository_service._language_for_path(Path("Containerfile")) == "dockerfile"
    assert repository_service._language_for_path(Path("docker/build.Dockerfile")) == "dockerfile"
    assert repository_service._language_for_path(Path("src/main.cu")) == "cuda"
    assert repository_service._language_for_path(Path("include/math.cuh")) == "cuda"
    assert repository_service._language_for_path(Path("shaders/main.hlsl")) == "hlsl"
    assert repository_service._language_for_path(Path("shaders/common.hlsli")) == "hlsl"
    assert repository_service._language_for_path(Path("Shaders/Main.shader")) == "shaderlab"
    assert repository_service._language_for_path(Path("pkg/main.pyx")) == "cython"
    assert repository_service._language_for_path(Path("pkg/helpermod.pxd")) == "cython"
    assert repository_service._language_for_path(Path("pkg/defs.pxi")) == "cython"
    assert repository_service._language_for_path(Path("models/main.stan")) == "stan"
    assert repository_service._language_for_path(Path("tests/login.robot")) == "robotframework"
    assert repository_service._language_for_path(Path("resources/common.resource")) == "robotframework"
    assert repository_service._language_for_path(Path("styles/main.scss")) == "scss"
    assert repository_service._language_for_path(Path("docs/main.typ")) == "typst"
    assert repository_service._language_for_path(Path("scripts/vscripts/main.nut")) == "squirrel"
    assert repository_service._language_for_path(Path("lib/math.awk")) == "awk"
    assert repository_service._language_for_path(Path("src/main.coffee")) == "coffeescript"
    assert repository_service._language_for_path(Path("docs/demo.litcoffee")) == "coffeescript"
    assert repository_service._language_for_path(Path("src/main.vala")) == "vala"
    assert repository_service._language_for_path(Path("vapi/demo.vapi")) == "vala"
    assert repository_service._language_for_path(Path("Experts/Main.mq5")) == "mql5"
    assert repository_service._language_for_path(Path("Include/Helper.mqh")) == "mql5"
    assert repository_service._language_for_path(Path("MetaTrader/demo.mqproj")) == "mql5"
    assert repository_service._language_for_path(Path("models/main.gms")) == "gams"
    assert repository_service._language_for_path(Path("models/main.scad")) == "openscad"
    assert repository_service._language_for_path(Path("src/Main.purs")) == "purescript"
    assert repository_service._language_for_path(Path("src/lib.cairo")) == "cairo"
    assert repository_service._language_for_path(Path("src/Main.re")) == "reasonml"
    assert repository_service._language_for_path(Path("src/Helper.rei")) == "reasonml"
    assert repository_service._language_for_path(Path("src/main.gleam")) == "gleam"
    assert repository_service._language_for_path(Path("src/main.bal")) == "ballerina"
    assert repository_service._language_for_path(Path("src/main.janet")) == "janet"
    assert repository_service._language_for_path(Path("dashboards/main.jsonnet")) == "jsonnet"
    assert repository_service._language_for_path(Path("libraries/core.libsonnet")) == "jsonnet"
    assert repository_service._language_for_path(Path("lib/autoconf/autoconf.m4")) == "m4"
    assert repository_service._language_for_path(Path("kernel/main.fth")) == "forth"
    assert repository_service._language_for_path(Path("proof/Main.thy")) == "isabelle"
    assert repository_service._language_for_path(Path("rules/fix.sed")) == "sed"
    assert repository_service._language_for_path(Path("installer/setup.nsi")) == "nsis"
    assert repository_service._language_for_path(Path("include/shared.nsh")) == "nsis"
    assert repository_service._language_for_path(Path("styles/main.xsl")) == "xslt"
    assert repository_service._language_for_path(Path("queries/main.xqy")) == "xquery"
    assert repository_service._language_for_path(Path("scripts/main.q")) == "q"
    assert repository_service._language_for_path(Path("src/main.ijs")) == "j"
    assert repository_service._language_for_path(Path("src/main.ijt")) == "j"
    assert repository_service._language_for_path(Path("src/Main.idr")) == "idris"
    assert repository_service._language_for_path(Path("demo.ipkg")) == "idris"
    assert repository_service._language_for_path(Path("lib/Demo/Helper.rakumod")) == "raku"
    assert repository_service._language_for_path(Path("bin/demo.raku")) == "raku"
    assert repository_service._language_for_path(Path("scripts/main.nu")) == "nushell"
    assert repository_service._language_for_path(Path("src/Main.hx")) == "haxe"
    assert repository_service._language_for_path(Path("src/Main.hack")) == "hack"
    assert repository_service._language_for_path(Path("build.hxml")) == "haxe"
    assert repository_service._language_for_path(Path("sketches/Bubbles/Bubbles.pde")) == "processing"
    assert (
        repository_service._language_for_path(
            Path("contracts/lib.cairo"),
            text="use core::traits::Into;\nfn main() {}\n",
        )
        == "cairo"
    )
    assert (
        repository_service._language_for_path(
            Path("contracts/main.sw"),
            text="script;\nuse std::auth::msg_sender;\nfn main() {}\n",
        )
        == "sway"
    )
    assert (
        repository_service._language_for_path(
            Path("models/prod.mod"),
            text="param demand;\nvar Make >= 0;\nmaximize Profit: 2 * Make;\n",
        )
        == "ampl"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/main.run"),
            text="model ../models/prod.mod;\nsolve;\ndisplay Profit;\n",
        )
        == "ampl"
    )
    assert (
        repository_service._language_for_path(
            Path("src/OEUnit/Runners/OEUnitRunner.cls"),
            text=(
                "USING Progress.Lang.*.\n"
                "CLASS OEUnit.Runners.OEUnitRunner INHERITS BaseRunner:\n"
                "  DEFINE PROTECTED VARIABLE currentTest AS Object NO-UNDO.\n"
                "END CLASS.\n"
            ),
        )
        == "openedge"
    )
    assert (
        repository_service._language_for_path(
            Path("src/OEUnit/Automation/Pct/RunTests.p"),
            text=(
                "ROUTINE-LEVEL ON ERROR UNDO, THROW.\n"
                "DEFINE INPUT PARAMETER testLocation AS CHARACTER NO-UNDO.\n"
                "RUN FindClassFiles(INPUT testLocation).\n"
            ),
        )
        == "openedge"
    )
    assert repository_service._language_for_path(Path("gamemodes/main.pwn")) == "pawn"
    assert repository_service._language_for_path(Path("http/client.pony")) == "pony"
    assert repository_service._language_for_path(Path("smali/com/example/Main.smali")) == "smali"
    assert repository_service._language_for_path(Path("BUILD.bazel")) == "starlark"
    assert repository_service._language_for_path(Path("MODULE.bazel")) == "starlark"
    assert repository_service._language_for_path(Path("rules/demo.bzl")) == "starlark"
    assert repository_service._language_for_path(Path("flake.nix")) == "nix"
    assert repository_service._language_for_path(Path("src/main.pb")) == "purebasic"
    assert repository_service._language_for_path(Path("include/helpers.pbi")) == "purebasic"
    assert repository_service._language_for_path(Path("docs/manual.ps")) == "postscript"
    assert repository_service._language_for_path(Path("docs/diagram.eps")) == "postscript"
    assert repository_service._language_for_path(Path("nix/lib/formatter.nix")) == "nix"
    assert repository_service._language_for_path(Path("v.mod")) == "v"
    assert repository_service._language_for_path(Path("src/Demo-Core/package.st")) == "smalltalk"
    assert repository_service._language_for_path(Path("src/Demo-Core/Helper.class.st")) == "smalltalk"
    assert repository_service._language_for_path(Path("games/Maze.sb3")) == "scratch"
    assert (
        repository_service._language_for_path(
            Path("PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml")
        )
        == "xpp"
    )
    assert repository_service._language_for_path(Path("src/main.ex")) == "ex"
    assert repository_service._language_for_path(Path("src/main.cs")) == "cs"
    assert repository_service._language_for_path(Path("src/zcl_math.clas.abap")) == "abap"
    assert repository_service._language_for_path(Path("src/boot.asm")) == "assembly"
    assert repository_service._language_for_path(Path("src/main.prolog")) == "prolog"
    assert repository_service._language_for_path(Path("src/main.cbl")) == "cobol"
    assert repository_service._language_for_path(Path("db/order_api.pkb")) == "plsql"
    assert repository_service._language_for_path(Path("programs/report.sas")) == "sas"
    assert repository_service._language_for_path(Path("src/main.sml")) == "sml"
    assert repository_service._language_for_path(Path("src/core.sig")) == "sml"
    assert repository_service._language_for_path(Path("src/make.fun")) == "sml"
    assert repository_service._language_for_path(Path("logic/Main.L5X")) == "ladder"
    assert repository_service._language_for_path(Path("App.lvproj")) == "labview"
    assert repository_service._language_for_path(Path("Source/Main.vi")) == "labview"
    assert repository_service._language_for_path(Path("systems/acme.asd")) == "lisp"
    assert repository_service._language_for_path(Path("src/app.lisp")) == "lisp"
    assert repository_service._language_for_path(Path("src/app.lsp")) == "lisp"
    assert repository_service._language_for_path(Path("src/main.sw")) == "sway"
    assert repository_service._language_for_path(Path("src/main.scm")) == "scheme"
    assert repository_service._language_for_path(Path("src/main.ss")) == "scheme"
    assert repository_service._language_for_path(Path("src/lib.sld")) == "scheme"
    assert repository_service._language_for_path(Path("src/program.sps")) == "scheme"
    assert repository_service._language_for_path(Path("src/main.rkt")) == "racket"
    assert repository_service._language_for_path(Path("src/lib.rktl")) == "racket"
    assert repository_service._language_for_path(Path("policy/main.rego")) == "rego"
    assert repository_service._language_for_path(Path("infra/main.tf")) == "hcl"
    assert repository_service._language_for_path(Path("metadata.json")) == "json"
    assert repository_service._language_for_path(Path("rules/index.yar")) == "yara"
    assert repository_service._language_for_path(Path("Kernel/Helpers.wl")) == "wolfram"
    assert repository_service._language_for_path(Path("Scripts/BuildPaclet.wls")) == "wolfram"
    assert repository_service._language_for_path(Path("scripts/main.tcl")) == "tcl"
    assert repository_service._language_for_path(Path("modules/sha1/sha1.tm")) == "tcl"
    assert repository_service._language_for_path(Path("rtl/top.sv")) == "systemverilog"
    assert repository_service._language_for_path(Path("rtl/defs.svh")) == "systemverilog"
    assert repository_service._language_for_path(Path("App/AcmeApp.dpr")) == "delphi"
    assert repository_service._language_for_path(Path("scripts/player.gd")) == "gdscript"
    assert repository_service._language_for_path(Path("rtl/top.vhd")) == "vhdl"
    assert repository_service._language_for_path(Path("rtl/pkg.vhdl")) == "vhdl"


def test_language_for_path_disambiguates_v_from_verilog_with_content() -> None:
    assert (
        repository_service._language_for_path(
            Path("src/main.v"),
            text="module main\n\nfn main() {\n}\n",
        )
        == "v"
    )
    assert (
        repository_service._language_for_path(
            Path("rtl/child.v"),
            text="module child;\n  reg ready;\nendmodule\n",
        )
        == "verilog"
    )
    assert (
        repository_service._language_for_path(
            Path("rtl/top.v"),
            text="module top(input logic clk);\nendmodule\n",
        )
        == "systemverilog"
    )
    assert repository_service._language_for_path(Path("database/Acme.sqlproj")) == "tsql"
    assert repository_service._language_for_path(Path("database/Acme.dbproj")) == "tsql"
    assert repository_service._language_for_path(Path("programs/main.prg")) == "unknown"
    assert repository_service._language_for_path(Path("src/module.bas")) == "unknown"
    assert repository_service._language_for_path(Path("src/main.kt")) == "kotlin"


def test_language_for_path_uses_nested_v_repo_hint_before_coq_detection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "nested-v-service-language-repo"
    (repo_path / "apps" / "demo").mkdir(parents=True)
    (repo_path / "apps" / "demo" / "v.mod").write_text(
        "Module {\n    name: 'demo'\n}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repository_service.coq_adapter,
        "is_probable_coq_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("nested v repo hint should bypass coq detection for .v sources")
        ),
    )

    assert (
        repository_service._language_for_path(
            repo_path / "button.v",
            text="module ui\n\npub fn render() {\n    println('ok')\n}\n",
            repo_root=repo_path,
        )
        == "v"
    )


def test_language_for_path_uses_coq_repo_hint_before_v_detection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "coq-service-language-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "_coqproject").write_text(
        "-Q theories Demo\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repository_service.v_adapter,
        "is_probable_v_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("coq repo hint should bypass v detection for .v sources")
        ),
    )

    assert (
        repository_service._language_for_path(
            repo_path / "Main.v",
            text="From Coq Require Import Arith.\nTheorem id_demo : True.\nProof. exact I. Qed.\n",
            repo_root=repo_path,
        )
        == "coq"
    )


def test_language_for_path_uses_cpp_repo_hint_before_objective_c_header_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "cpp-service-language-repo"
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text("project(fmt LANGUAGES CXX)\n", encoding="utf-8")
    (repo_path / "include" / "format.h").write_text(
        "template <typename T>\nstruct box { T value; };\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "format.cc").write_text(
        "#include \"format.h\"\nint main() { return 0; }\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repository_service.objc_adapter,
        "is_probable_objective_c_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cpp repo hint should bypass objective-c header fallback")
        ),
    )
    repository_service._AMBIGUOUS_C_HEADER_REPO_HINT_CACHE.clear()

    assert (
        repository_service._language_for_path(
            repo_path / "include" / "format.h",
            text="template <typename T>\nstruct box { T value; };\n",
            repo_root=repo_path,
        )
        == "cpp"
    )


def test_language_for_path_preserves_objective_c_header_fallback_for_objective_c_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "objective-c-service-language-repo"
    (repo_path / "ios").mkdir(parents=True)
    (repo_path / "ios" / "AppDelegate.m").write_text(
        "#import <Foundation/Foundation.h>\n@implementation AppDelegate\n@end\n",
        encoding="utf-8",
    )
    header_text = "#import <Foundation/Foundation.h>\n@interface AppDelegate : NSObject\n@end\n"
    (repo_path / "ios" / "AppDelegate.h").write_text(header_text, encoding="utf-8")

    repository_service._AMBIGUOUS_C_HEADER_REPO_HINT_CACHE.clear()

    assert (
        repository_service._language_for_path(
            repo_path / "ios" / "AppDelegate.h",
            text=header_text,
            repo_root=repo_path,
        )
        == "objectivec"
    )
    assert repository_service._language_for_path(Path("src/main.m")) == "unknown"
    assert repository_service._language_for_path(Path("ios/Renderer.mm")) == "objectivec"
    assert repository_service._language_for_path(Path("+acme/helper.m")) == "matlab"
    assert repository_service._language_for_path(Path("Kernel/init.m")) == "wolfram"
    assert (
        repository_service._language_for_path(
            Path("include/common.inc"),
            text="$include ../models/main.gms\nparameter demand(i);\n",
        )
        == "gams"
    )
    assert (
        repository_service._language_for_path(
            Path("parts/gear.scad"),
            text="include <lib/threads.scad>;\nmodule gear(teeth) { cylinder(r=teeth); }\n",
        )
        == "openscad"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.purs"),
            text="module Main where\n\nimport Prelude\n\nmain = unit\n",
        )
        == "purescript"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.agda"),
            text="module Main where\n\nopen import Data.Helper using (helper)\n",
        )
        == "agda"
    )
    assert (
        repository_service._language_for_path(
            Path("kernel/main.fs"),
            text=": greet ( -- ) cr ;\ninclude lib.fs\n",
        )
        == "forth"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.fs"),
            text="module Demo\nlet x = 1\n",
        )
        == "fsharp"
    )
    assert (
        repository_service._language_for_path(
            Path("proof/Main.thy"),
            text="theory Main\nimports Base\nbegin\nlemma run: \"helper = helper\"\nend\n",
        )
        == "isabelle"
    )
    assert (
        repository_service._language_for_path(
            Path("styles/main.xsl"),
            text=(
                '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
                '  <xsl:template name="Helper"/>\n'
                "</xsl:stylesheet>\n"
            ),
        )
        == "xslt"
    )
    assert (
        repository_service._language_for_path(
            Path("styles/main.xsl"),
            text="plain notes without stylesheet markers\n",
        )
        == "unknown"
    )
    assert (
        repository_service._language_for_path(
            Path("queries/main.xqy"),
            text='xquery version "3.1";\ndeclare function local:helper() { "ok" };\n',
        )
        == "xquery"
    )
    assert (
        repository_service._language_for_path(
            Path("queries/main.xqy"),
            text="plain notes without xquery markers\n",
        )
        == "unknown"
    )
    assert (
        repository_service._language_for_path(
            Path("grammar/main.y"),
            text="%token NUMBER\n%%\nexpr: term ;\nterm: NUMBER ;\n%%\n",
        )
        == "yacc"
    )
    assert (
        repository_service._language_for_path(
            Path("grammar/main.y"),
            text="plain notes without grammar markers\n",
        )
        == "unknown"
    )
    assert (
        repository_service._language_for_path(
            Path("scanner/main.l"),
            text="DIGIT   [0-9]\n%%\n{DIGIT}+    { return NUMBER; }\n%%\n",
        )
        == "lex"
    )
    assert (
        repository_service._language_for_path(
            Path("scanner/main.l"),
            text="plain notes without scanner markers\n",
        )
        == "unknown"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/main.q"),
            text="helper:{[x]\n  x + 1\n}\n",
        )
        == "q"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/main.q"),
            text="plain notes without q syntax\n",
        )
        == "unknown"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.ijs"),
            text="helper =: 3 : 0\n  y + 1\n)\n",
        )
        == "j"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.ijs"),
            text="plain notes without j syntax\n",
        )
        == "unknown"
    )
    assert (
        repository_service._language_for_path(
            Path("rules/fix.sed"),
            text=":loop\ns/cat/dog/g\nt loop\n",
        )
        == "sed"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.mo"),
            text='import Array "mo:base/Array";\nactor Main {}\n',
        )
        == "motoko"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.mo"),
            text="model Example\n  Real x;\nequation\n  der(x) = -x;\nend Example;\n",
        )
        == "modelica"
    )
    assert (
        repository_service._language_for_path(
            Path("standard-library.agda-lib"),
            text="name: demo\ninclude: src\n",
        )
        == "agda"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.gleam"),
            text="import demo/helper.{render_json}\n\npub fn main() {\n  render_json()\n}\n",
        )
        == "gleam"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.bal"),
            text=(
                "import ballerina/io;\n\n"
                "public function main() returns error? {\n"
                "    io:println(\"hello\");\n"
                "}\n"
            ),
        )
        == "ballerina"
    )
    assert (
        repository_service._language_for_path(
            Path("Ballerina.toml"),
            text="[package]\norg = \"acme\"\nname = \"demo\"\nversion = \"0.1.0\"\n",
        )
        == "ballerina"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/main.nu"),
            text="source modules/helper.nu\nuse modules/helper.nu\n\ndef main [] {\n  render-json\n}\n",
        )
        == "nushell"
    )
    assert (
        repository_service._language_for_path(
            Path("terragrunt.hcl"),
            text='locals {\n  env = "prod"\n}\n',
        )
        == "hcl"
    )
    assert (
        repository_service._language_for_path(
            Path("policy/main.rego"),
            text="package policy.main\n\nimport data.policy.lib.helpers as helper\n\nallow if {\n  helper.render_json\n}\n",
        )
        == "rego"
    )
    assert (
        repository_service._language_for_path(
            Path("metadata.json"),
            text='{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        )
        == "puppet"
    )
    assert (
        repository_service._language_for_path(
            Path("Puppetfile"),
            text="mod 'puppetlabs-stdlib'\n",
        )
        == "puppet"
    )
    assert (
        repository_service._language_for_path(
            Path("manifests/init.pp"),
            text="class apache {\n  include apache::params\n}\n",
        )
        == "puppet"
    )
    assert (
        repository_service._language_for_path(
            Path("manifests/install.pp"),
            text="class { 'apache::install':\n  ensure => present,\n}\n",
        )
        == "puppet"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.pp"),
            text="program Main;\nbegin\nend.\n",
        )
        == "pascal"
    )
    assert (
        repository_service._language_for_path(
            Path("rules/main.yar"),
            text='import "pe"\n\nrule main_rule {\n  condition:\n    pe.is_dll\n}\n',
        )
        == "yara"
    )
    assert (
        repository_service._language_for_path(
            Path("functions/helper.fish"),
            text="function helper\n    render_json\nend\n",
        )
        == "fish"
    )
    assert (
        repository_service._language_for_path(
            Path("bin/fish-runner"),
            text="#!/usr/bin/env fish\nfunction helper\n    echo ok\nend\n",
        )
        == "fish"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.hx"),
            text=(
                "package demo;\n"
                "\n"
                "import demo.Helper;\n"
                "\n"
                "class Main {\n"
                "    static function main() {\n"
                "        Helper.renderJson();\n"
                "    }\n"
                "}\n"
            ),
        )
        == "haxe"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.odin"),
            text='package main\n\nimport "core:fmt"\n\nmain :: proc() {\n    fmt.println("ok")\n}\n',
        )
        == "odin"
    )
    assert (
        repository_service._language_for_path(
            Path("ols.json"),
            text='{"profile":"default","profiles":[{"name":"default","checker_path":["src"]}]}\n',
        )
        == "json"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Ref.php"),
            text="<?hh\nnamespace Demo;\nfinal class Ref<T> {}\n",
        )
        == "hack"
    )
    assert (
        repository_service._language_for_path(
            Path("src/User.hack"),
            text="namespace Demo;\nfinal class User {}\n",
        )
        == "hack"
    )
    assert (
        repository_service._language_for_path(
            Path(".hhconfig"),
            text="assume_php = false\n",
        )
        == "hack"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.chpl"),
            text=(
                "module Main {\n"
                "use Utils;\n"
                "proc run() {\n"
                "  return helper();\n"
                "}\n"
                "}\n"
            ),
        )
        == "chapel"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/Main.ahk"),
            text='#Include "Lib/Helper.ahk"\nMain() {\n    RenderJson("{}")\n}\n',
        )
        == "autohotkey"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/Main.au3"),
            text='#include "Includes/Helper.au3"\nFunc Main()\n    Return RenderJson("{}")\nEndFunc\n',
        )
        == "autoit"
    )
    assert (
        repository_service._language_for_path(
            Path("build.hxml"),
            text="-cp src\n-main demo.Main\n",
        )
        == "haxe"
    )
    assert (
        repository_service._language_for_path(
            Path("project.xml"),
            text='<project><source path="src"/><app main="demo.Main"/></project>\n',
        )
        == "haxe"
    )
    assert (
        repository_service._language_for_path(
            Path("pom.xml"),
            text="<project><modelVersion>4.0.0</modelVersion></project>\n",
        )
        == "maven"
    )
    assert (
        repository_service._language_for_path(
            Path("flake.nix"),
            text="{ inputs, ... }: { outputs = inputs: { formatter = null; }; }\n",
        )
        == "nix"
    )
    assert (
        repository_service._language_for_path(
            Path("plugin/fugitive.vim"),
            text="function! fugitive#run()\nendfunction\n",
        )
        == "vimscript"
    )
    assert (
        repository_service._language_for_path(
            Path("vimrc"),
            text="set number\n",
        )
        == "vimscript"
    )
    assert (
        repository_service._language_for_path(
            Path(".vimrc"),
            text="let mapleader = ','\n",
        )
        == "vimscript"
    )


def test_language_for_path_skips_haxe_comment_stripping_for_non_project_xml_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_haxe_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(repository_haxe_primitives, "strip_comments", counting_strip_comments)

    assert (
        repository_service._language_for_path(
            Path("pom.xml"),
            text="<project><modelVersion>4.0.0</modelVersion></project>\n",
        )
        == "maven"
    )
    assert strip_call_count["value"] == 0

    assert (
        repository_service._language_for_path(
            Path("project.xml"),
            text='<project><source path="src"/><app main="demo.Main"/></project>\n',
        )
        == "haxe"
    )
    assert strip_call_count["value"] == 1
    assert (
        repository_service._language_for_path(
            Path(".mvn/maven.config"),
            text="--batch-mode\n",
        )
        == "maven"
    )
    assert (
        repository_service._language_for_path(
            Path("Source/Main.vim"),
            text="RSRC\nLVIN\n",
        )
        == "labview"
    )


def test_language_for_path_uses_fsharp_project_context_before_forth_detection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "fsharp-service-language-repo"
    (repo_path / "src" / "Host").mkdir(parents=True)
    (repo_path / "src" / "Host" / "Host.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repository_service.forth_adapter,
        "is_probable_forth_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("fsharp project context should bypass forth detection for .fs sources")
        ),
    )

    assert (
        repository_service._language_for_path(
            repo_path / "src" / "Host" / "Program.fs",
            text="module Host\nlet main = 1\n",
            repo_root=repo_path,
        )
        == "fsharp"
    )


def test_language_for_path_detects_extensionless_awk_shebang() -> None:
    assert (
        repository_service._language_for_path(
            Path("bin/translate"),
            text="#!/usr/bin/env gawk -f\nBEGIN { print 1 }\n",
        )
        == "awk"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Application.cfc"),
            text=(
                "component {\n"
                "    function onApplicationStart() {\n"
                "    }\n"
                "}\n"
            ),
        )
        == "cfml"
    )
    assert (
        repository_service._language_for_path(
            Path("views/index.cfm"),
            text='<cfinclude template="../config/app.cfm">\n',
        )
        == "cfml"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.m"),
            text="function value = main()\nvalue = helper();\nend\n",
        )
        == "matlab"
    )
    assert (
        repository_service._language_for_path(
            Path("Kernel/init.m"),
            text='Get["Acme`Helpers`"];\n',
        )
        == "wolfram"
    )
    assert (
        repository_service._language_for_path(
            Path("Source/Controls/Config.ctl"),
            text="RSRC\r\n\x00\x03LVCCLBVW",
        )
        == "labview"
    )
    assert (
        repository_service._language_for_path(
            Path("ios/AppDelegate.m"),
            text="#import <Foundation/Foundation.h>\n@implementation AppDelegate\n@end\n",
        )
        == "objectivec"
    )
    assert (
        repository_service._language_for_path(
            Path("ios/AppDelegate.h"),
            text="#import <Foundation/Foundation.h>\n@interface AppDelegate : NSObject\n@end\n",
        )
        == "objectivec"
    )
    assert (
        repository_service._language_for_path(
            Path("rtl/child.v"),
            text="module child;\n  reg ready;\nendmodule\n",
        )
        == "verilog"
    )
    assert (
        repository_service._language_for_path(
            Path("rtl/defs.vh"),
            text="`ifndef DEFS_VH\n`define DEFS_VH\n`endif\n",
        )
        == "verilog"
    )
    assert (
        repository_service._language_for_path(
            Path("include/io.inc"),
            text="extern print_string\n",
        )
        == "assembly"
    )
    assert (
        repository_service._language_for_path(
            Path("database/Acme.sqlproj"),
            text=(
                "<Project>\n"
                "  <ItemGroup>\n"
                '    <Build Include="dbo\\\\Stored Procedures\\\\LoadCustomers.sql" />\n'
                "  </ItemGroup>\n"
                "</Project>\n"
            ),
        )
        == "tsql"
    )
    assert (
        repository_service._language_for_path(
            Path("database/dbo/Stored Procedures/LoadCustomers.sql"),
            text=(
                "create or alter procedure dbo.LoadCustomers\n"
                "as\n"
                "begin\n"
                "    set nocount on;\n"
                "    exec dbo.LoadHelpers;\n"
                "end\n"
                "go\n"
            ),
        )
        == "tsql"
    )
    assert (
        repository_service._language_for_path(
            Path("src/family.pl"),
            text=":- module(family, [parent/2]).\nparent(alice, bob).\n",
        )
        == "prolog"
    )
    assert (
        repository_service._language_for_path(
            Path("script/app.pl"),
            text="use strict;\nsub run {\n    return 1;\n}\n",
        )
        == "perl"
    )
    assert (
        repository_service._language_for_path(
            Path("App/MainForm.pas"),
            text=(
                "unit MainForm;\n"
                "interface\n"
                "uses System.SysUtils, Vcl.Forms;\n"
                "{$R *.dfm}\n"
                "implementation\n"
                "end.\n"
            ),
        )
        == "delphi"
    )
    assert (
        repository_service._language_for_path(
            Path("app/mainform.pas"),
            text=(
                "unit MainForm;\n"
                "interface\n"
                "{$mode objfpc}{$H+}\n"
                "uses Classes, SysUtils;\n"
                "implementation\n"
                "end.\n"
            ),
        )
        == "pascal"
    )
    assert (
        repository_service._language_for_path(
            Path("src/modMain.bas"),
            text='Attribute VB_Name = "modMain"\nOption Explicit\nPublic Sub RunApp()\nEnd Sub\n',
        )
        == "vba"
    )
    assert (
        repository_service._language_for_path(
            Path("programs/main.prg"),
            text="LPARAMETERS to_json\nFUNCTION main()\n    RETURN to_json\nENDFUNC\n",
        )
        == "foxpro"
    )
    assert (
        repository_service._language_for_path(
            Path("contracts/Counter.sol"),
            text='pragma solidity ^0.8.20;\ncontract Counter {\n    function increment() public {}\n}\n',
        )
        == "solidity"
    )
    assert (
        repository_service._language_for_path(
            Path("PackagesLocalDirectory/Acme/Descriptor/Acme.xml"),
            text=(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                "<AxModelInfo>\n"
                "  <Name>Acme</Name>\n"
                "</AxModelInfo>\n"
            ),
        )
        == "xpp"
    )
    assert (
        repository_service._language_for_path(
            Path("Cakefile"),
            text="task 'build', ->\n  console.log 'ok'\n",
        )
        == "coffeescript"
    )
    assert (
        repository_service._language_for_path(
            Path("PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml"),
            text=(
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                "<AxClass>\n"
                "  <Name>AcmeMain</Name>\n"
                "  <SourceCode>\n"
                "    <Declaration><![CDATA[\n"
                "class AcmeMain\n"
                "{\n"
                "}\n"
                "]]></Declaration>\n"
                "  </SourceCode>\n"
                "</AxClass>\n"
            ),
        )
        == "xpp"
    )
    assert (
        repository_service._language_for_path(
            Path("force-app/main/default/classes/AccountTriggerHandler.cls"),
            text=(
                "public with sharing class AccountTriggerHandler {\n"
                "    public static void run() {\n"
                "    }\n"
                "}\n"
            ),
        )
        == "apex"
    )
    assert (
        repository_service._language_for_path(
            Path("force-app/main/default/triggers/AccountTrigger.trigger"),
            text=(
                "trigger AccountTrigger on Account (before insert) {\n"
                "    AccountTriggerHandler.run();\n"
                "}\n"
            ),
        )
        == "apex"
    )
    assert repository_service._language_for_path(Path("scripts/build.vbs")) == "vbscript"
    assert repository_service._language_for_path(Path("scripts/Helper.applescript")) == "applescript"
    assert repository_service._language_for_path(Path("QRPGLESRC/ORD100.PGM.RPGLE")) == "rpg"
    assert repository_service._language_for_path(Path("QPROTOSRC/CUSTOMER.RPGLEINC")) == "rpg"
    assert repository_service._language_for_path(Path("src/report.sqlrpgle")) == "rpg"
    assert (
        repository_service._language_for_path(
            Path("scripts/main.wsf"),
            text=(
                '<job>\n'
                '  <script language="VBScript" src="lib/helper.vbs"></script>\n'
                '  <script language="VBScript">\n'
                "    Option Explicit\n"
                "    Sub Main()\n"
                "    End Sub\n"
                "  </script>\n"
                "</job>\n"
            ),
        )
        == "vbscript"
    )
    assert (
        repository_service._language_for_path(
            Path("scripts/Helper.scpt"),
            text=(
                "script HelperScript\n"
                "    on RenderJson(value)\n"
                "        return value\n"
                "    end RenderJson\n"
                "end script\n"
            ),
        )
        == "applescript"
    )
    assert (
        repository_service._language_for_path(
            Path("src/cHelper.cls"),
            text='VERSION 1.0 CLASS\nAttribute VB_Name = "cHelper"\nOption Explicit\n',
        )
        == "vba"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Form1.frm"),
            text='VERSION 5.00\nBegin VB.Form Form1\nEnd\nAttribute VB_Name = "Form1"\n',
        )
        == "vb6"
    )
    assert (
        repository_service._language_for_path(
            Path("src/ctxWinsock.ctl"),
            text='Begin VB.UserControl ctxWinsock\nEnd\nAttribute VB_Name = "ctxWinsock"\n',
        )
        == "vb6"
    )
    assert (
        repository_service._language_for_path(
            Path("Project1.vbp"),
            text='Type=Exe\nForm=src/Form1.frm\nStartup="Form1"\nName="Project1"\n',
        )
        == "vb6"
    )
    assert repository_service._language_for_path(Path("src/main.adb_body")) == "unknown"


def test_language_for_path_uses_vbp_repo_context_before_vba(tmp_path: Path) -> None:
    repo_path = tmp_path / "vb6-context-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project1.vbp").write_text(
        'Type=Exe\n'
        'Class=cHelper; src/cHelper.cls\n'
        'Module=modMain; src/modMain.bas\n'
        'Startup="modMain"\n'
        'Name="Project1"\n',
        encoding="utf-8",
    )
    module_text = (
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n"
    )
    class_text = (
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
    )

    assert repository_service._language_for_path(
        repo_path / "src" / "modMain.bas",
        text=module_text,
        repo_root=repo_path,
    ) == "vb6"
    assert repository_service._language_for_path(
        repo_path / "src" / "cHelper.cls",
        text=class_text,
        repo_root=repo_path,
    ) == "vb6"
    assert repository_service._language_for_path(
        Path("src/modMain.bas"),
        text=module_text,
    ) == "vba"
    assert repository_service._language_for_path(
        Path("src/cHelper.cls"),
        text=class_text,
    ) == "vba"


def test_language_for_path_ignores_commented_classic_visual_basic_markers() -> None:
    assert (
        repository_service._language_for_path(
            Path("src/Form1.frm"),
            text=(
                "' Begin VB.Form Form1\n"
                "' Attribute VB_Name = \"Form1\"\n"
                "Option Explicit\n"
            ),
        )
        == "unknown"
    )


def test_language_for_path_skips_apex_comment_stripping_for_braceless_cls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_strip_comments(_text: str) -> str:
        raise AssertionError("brace-less .cls files should not run Apex comment stripping")

    monkeypatch.setattr(repository_service.apex_adapter, "strip_comments", _unexpected_strip_comments)

    assert (
        repository_service._language_for_path(
            Path("src/cHelper.cls"),
            text='VERSION 1.0 CLASS\nAttribute VB_Name = "cHelper"\nOption Explicit\n',
        )
        == "vba"
    )


def test_language_for_path_skips_tex_comment_stripping_for_non_tex_cls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_strip_comments(_text: str) -> str:
        raise AssertionError("non-TeX .cls files should not run TeX comment stripping")

    monkeypatch.setattr(repository_service.tex_adapter, "strip_comments", _unexpected_strip_comments)

    assert (
        repository_service._language_for_path(
            Path("src/cHelper.cls"),
            text='VERSION 1.0 CLASS\nAttribute VB_Name = "cHelper"\nOption Explicit\n',
        )
        == "vba"
    )


def test_language_for_path_bypasses_apex_and_tex_detection_for_vba_cls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_apex_detection(*, path: Path, text: str) -> bool:
        raise AssertionError("classic VB/VBA .cls files should not probe Apex detection first")

    def _unexpected_tex_detection(*, path: Path, text: str) -> bool:
        raise AssertionError("classic VB/VBA .cls files should not probe TeX detection first")

    monkeypatch.setattr(
        repository_service.apex_adapter,
        "is_probable_apex_source",
        _unexpected_apex_detection,
    )
    monkeypatch.setattr(
        repository_service.tex_adapter,
        "is_probable_tex_source",
        _unexpected_tex_detection,
    )

    assert (
        repository_service._language_for_path(
            Path("src/CController.cls"),
            text=(
                "VERSION 1.0 CLASS\n"
                "BEGIN\n"
                "  MultiUse = -1  'True\n"
                "END\n"
                'Attribute VB_Name = "CController"\n'
                "Attribute VB_Creatable = False\n"
                "Option Explicit\n"
                "\n"
                "Implements IController\n"
                "\n"
                "Private Property Get Events() As IControllerEvents\n"
                "End Property\n"
            ),
        )
        == "vba"
    )


def test_language_for_path_skips_fish_comment_stripping_for_non_runtime_suffixless_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_strip_comments(_text: str) -> str:
        raise AssertionError("non-Fish suffixless files should bypass Fish comment stripping")

    monkeypatch.setattr(repository_service.fish_adapter, "strip_comments", _unexpected_strip_comments)

    assert (
        repository_service._language_for_path(
            Path("vendor/tool"),
            text="plain text without fish markers\n",
        )
        == "unknown"
    )


def test_language_for_path_skips_objective_c_sanitization_for_plain_cpp_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_sanitize_text(_text: str) -> str:
        raise AssertionError("plain C/C++ headers should bypass Objective-C sanitization")

    monkeypatch.setattr(
        repository_objective_c_primitives,
        "sanitize_text",
        _unexpected_sanitize_text,
    )

    assert (
        repository_service._language_for_path(
            Path("include/widget.h"),
            text="class Widget final { public: void run() const; };\n",
        )
        == "cpp"
    )


def test_classic_visual_basic_strip_comments_skips_line_scans_without_comment_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.services.repository_intelligence_adapters import (
        classic_visual_basic_primitives as repository_classic_visual_basic_primitives,
    )

    def _unexpected_strip_inline_comment(_raw_line: str) -> str:
        raise AssertionError("comment-free VB files should bypass per-line comment stripping")

    monkeypatch.setattr(
        repository_classic_visual_basic_primitives,
        "_strip_inline_comment",
        _unexpected_strip_inline_comment,
    )

    source_text = (
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n"
    )

    assert repository_service.classic_visual_basic_adapter.strip_comments(source_text) == source_text


def test_actionscript_strip_comments_reuses_cached_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_actionscript_primitives._strip_comments_cached.cache_clear()
    calls = 0
    original = repository_actionscript_primitives._strip_comments_uncached

    def _counting_strip_comments(text: str) -> str:
        nonlocal calls
        calls += 1
        return original(text)

    monkeypatch.setattr(
        repository_actionscript_primitives,
        "_strip_comments_uncached",
        _counting_strip_comments,
    )

    source_text = (
        "package sample {\n"
        "  // comment\n"
        "  public class Main {}\n"
        "}\n"
    )
    expected = (
        "package sample {\n"
        "            \n"
        "  public class Main {}\n"
        "}\n"
    )

    assert repository_actionscript_primitives.strip_comments(source_text) == expected
    assert repository_actionscript_primitives.strip_comments(source_text) == expected
    assert calls == 1
    repository_actionscript_primitives._strip_comments_cached.cache_clear()


def test_cfml_strip_comments_reuses_cached_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_cfml_primitives._strip_comments_cached.cache_clear()
    calls = 0
    original = repository_cfml_primitives._strip_comments_uncached

    def _counting_strip_comments(text: str) -> str:
        nonlocal calls
        calls += 1
        return original(text)

    monkeypatch.setattr(
        repository_cfml_primitives,
        "_strip_comments_uncached",
        _counting_strip_comments,
    )

    source_text = (
        "<cfscript>\n"
        "component extends=\"app.Base\" {\n"
        "  // comment\n"
        "}\n"
        "</cfscript>\n"
    )
    expected = (
        "<cfscript>\n"
        "component extends=\"app.Base\" {\n"
        "  \n"
        "}\n"
        "</cfscript>"
    )

    assert repository_cfml_primitives.strip_comments(source_text) == expected
    assert repository_cfml_primitives.strip_comments(source_text) == expected
    assert calls == 1
    repository_cfml_primitives._strip_comments_cached.cache_clear()
