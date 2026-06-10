"""Tests for repository_intelligence_real_repo_probe: candidate_ecosystems_a.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_candidate_ecosystems_for_path_treats_custom_suffixes_and_ambiguous_m_files_carefully(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-ecosystems-repo"
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "script").mkdir(parents=True)
    (repo_path / "ios").mkdir(parents=True)
    (repo_path / "lisp").mkdir(parents=True)
    (repo_path / "foxpro").mkdir(parents=True)
    (repo_path / "Kernel").mkdir(parents=True)
    (repo_path / "vb6").mkdir(parents=True)
    (repo_path / "vba").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "cfml-app" / "models").mkdir(parents=True)
    (repo_path / "cfml-app" / "public").mkdir(parents=True)
    (repo_path / "database" / "dbo" / "Stored Procedures").mkdir(parents=True)
    (repo_path / "coffee-app" / "src").mkdir(parents=True)
    (repo_path / "delphi-app" / "source").mkdir(parents=True)
    (repo_path / "elm-app" / "src" / "Page").mkdir(parents=True)
    (repo_path / "elisp-app" / "lisp").mkdir(parents=True)
    (repo_path / "smalltalk-app" / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / "vala-app" / "src").mkdir(parents=True)
    (repo_path / "vala-app" / "vapi").mkdir(parents=True)
    (repo_path / "mql5-app" / "Experts").mkdir(parents=True)
    (repo_path / "mql5-app" / "Include").mkdir(parents=True)
    (repo_path / "gams-app" / "include").mkdir(parents=True)
    (repo_path / "openscad-app" / "lib").mkdir(parents=True)
    (repo_path / "purescript-app" / "src" / "Data").mkdir(parents=True)
    (repo_path / "purescript-app" / "test").mkdir(parents=True)
    (repo_path / "gleam-app" / "src" / "demo").mkdir(parents=True)
    (repo_path / "gleam-app" / "test").mkdir(parents=True)
    (repo_path / "janet-app" / "src" / "demo").mkdir(parents=True)
    (repo_path / "janet-app" / "test").mkdir(parents=True)
    (repo_path / "dhall-app" / "schemas").mkdir(parents=True)
    (repo_path / "dhall-app" / "tests").mkdir(parents=True)
    (repo_path / "rego-app" / "policy" / "lib").mkdir(parents=True)
    (repo_path / "agda-app" / "src" / "Data").mkdir(parents=True)
    (repo_path / "idris-app" / "src" / "Demo").mkdir(parents=True)
    (repo_path / "idris-app" / "tests").mkdir(parents=True)
    (repo_path / "raku-app" / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "raku-app" / "bin").mkdir(parents=True)
    (repo_path / "nushell-app" / "modules").mkdir(parents=True)
    (repo_path / "fish-app" / "functions").mkdir(parents=True)
    (repo_path / "fish-app" / "conf.d").mkdir(parents=True)
    (repo_path / "haxe-app" / "src" / "demo").mkdir(parents=True)
    (repo_path / "lean-app" / "Batteries").mkdir(parents=True)
    (repo_path / "starlark-app" / "rules").mkdir(parents=True)
    (repo_path / "starlark-app" / "lib").mkdir(parents=True)
    (repo_path / "nix-app" / "nix" / "lib").mkdir(parents=True)
    (repo_path / "scheme-app" / "lib" / "acme").mkdir(parents=True)
    (repo_path / "racket-app" / "private").mkdir(parents=True)
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "tcllib").mkdir(parents=True)
    (repo_path / "contracts").mkdir(parents=True)
    (repo_path / "logic").mkdir(parents=True)
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "vhdl").mkdir(parents=True)
    (repo_path / "godot" / "scripts").mkdir(parents=True)
    (repo_path / "labview" / "Source").mkdir(parents=True)
    (repo_path / "labview" / "Controls").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "classes").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "triggers").mkdir(parents=True)
    (repo_path / "src" / "boot.asm").write_text(
        "global start\nstart:\n    ret\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "translate").write_text(
        "#!/usr/bin/env gawk -f\n"
        '@include "../lib/math.awk"\n'
        "BEGIN { print add(1, 2) }\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "cfml-app" / "box.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "cfml-app" / "Application.cfc").write_text(
        "component {\n"
        "    function onApplicationStart() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "cfml-app" / "models" / "UserService.cfc").write_text(
        "component {\n"
        "    function run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "cfml-app" / "public" / "index.cfm").write_text(
        '<cfinclude template="../Application.cfc">\n',
        encoding="utf-8",
    )
    (repo_path / "database" / "Acme.sqlproj").write_text(
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <Build Include="dbo\\Stored Procedures\\LoadCustomers.sql" />\n'
        "  </ItemGroup>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "_CoqProject").write_text(
        "-Q theories Demo\n"
        "theories/Main.v\n",
        encoding="utf-8",
    )
    (repo_path / "lean-app" / "lean-toolchain").write_text(
        "leanprover/lean4:stable\n",
        encoding="utf-8",
    )
    (repo_path / "lean-app" / "lakefile.lean").write_text(
        "package batteries where\n\n"
        "lean_lib Batteries\n",
        encoding="utf-8",
    )
    (repo_path / "lean-app" / "Batteries" / "Main.lean").write_text(
        "import Batteries.Helper\n\n"
        "def main : Nat := Batteries.Helper.helper\n",
        encoding="utf-8",
    )
    (repo_path / "lean-app" / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 1\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Main.v").write_text(
        "From Demo Require Import Helper.\n"
        "Definition main := Helper.helper.\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper := 1.\n",
        encoding="utf-8",
    )
    (
        repo_path / "database" / "dbo" / "Stored Procedures" / "LoadCustomers.sql"
    ).write_text(
        "create or alter procedure dbo.LoadCustomers\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    select 1 as id;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )
    (repo_path / "delphi-app" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpr</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "delphi-app" / "AcmeApp.dpr").write_text(
        "program AcmeApp;\n"
        "uses MainForm in 'source/MainForm.pas';\n"
        "begin\n"
        "  MainForm.Run;\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "delphi-app" / "source" / "MainForm.pas").write_text(
        "unit MainForm;\n"
        "interface\n"
        "uses System.SysUtils, Vcl.Forms;\n"
        "{$R *.dfm}\n"
        "implementation\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "elm-app" / "elm.json").write_text(
        json.dumps(
            {
                "type": "application",
                "source-directories": ["src"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "elm-app" / "src" / "Main.elm").write_text(
        "module Main exposing (main)\n\n"
        "import Page.Home exposing (homeView)\n\n"
        "main : String\n"
        "main =\n"
        "    homeView\n",
        encoding="utf-8",
    )
    (repo_path / "elm-app" / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (homeView)\n\n"
        "homeView : String\n"
        "homeView =\n"
        "    \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "coffee-app" / "Cakefile").write_text(
        "task 'build', ->\n"
        "  require './src/main'\n",
        encoding="utf-8",
    )
    (repo_path / "coffee-app" / "src" / "main.coffee").write_text(
        "run = ->\n"
        "  console.log 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "vala-app" / "src" / "main.vala").write_text(
        "namespace Demo {\n"
        "    public class App : Object {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "vala-app" / "vapi" / "demo.vapi").write_text(
        "namespace Demo {\n"
        "    public class Helper : Object;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "mql5-app" / "demo.mqproj").write_text(
        '<Project><Files><File>Experts/Main.mq5</File><File>Include/Helper.mqh</File></Files></Project>\n',
        encoding="utf-8",
    )
    (repo_path / "mql5-app" / "Experts" / "Main.mq5").write_text(
        '#include "../Include/Helper.mqh"\n'
        "void OnStart()\n"
        "{\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "mql5-app" / "Include" / "Helper.mqh").write_text(
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
    (repo_path / "gams-app" / "main.gms").write_text(
        "$include include/common.inc\n"
        "set i /a,b/;\n"
        "parameter demand(i);\n",
        encoding="utf-8",
    )
    (repo_path / "gams-app" / "include" / "common.inc").write_text(
        "parameter supply(i);\n",
        encoding="utf-8",
    )
    (repo_path / "openscad-app" / "main.scad").write_text(
        "include <lib/helper.scad>;\n"
        "module build() {\n"
        "  gusset(10);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "openscad-app" / "lib" / "helper.scad").write_text(
        "module gusset(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "purescript-app" / "spago.yaml").write_text(
        "package:\n"
        "  name: demo\n"
        "workspace:\n"
        "  package_set:\n"
        "    registry: 64.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "purescript-app" / "src" / "Main.purs").write_text(
        "module Main where\n\nimport Data.Helper (helperValue)\n\nmain = helperValue\n",
        encoding="utf-8",
    )
    (repo_path / "purescript-app" / "src" / "Data" / "Helper.purs").write_text(
        "module Data.Helper where\n\nhelperValue :: Int\nhelperValue = 1\n",
        encoding="utf-8",
    )
    (repo_path / "purescript-app" / "test" / "Main.purs").write_text(
        "module Test.Main where\n\nmain = 1\n",
        encoding="utf-8",
    )
    (repo_path / "gleam-app" / "gleam.toml").write_text(
        'name = "demo"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (repo_path / "gleam-app" / "src" / "main.gleam").write_text(
        "import demo/helper.{render_json}\n\npub fn main() {\n  render_json()\n}\n",
        encoding="utf-8",
    )
    (repo_path / "gleam-app" / "src" / "demo" / "helper.gleam").write_text(
        "pub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )
    (repo_path / "gleam-app" / "test" / "main.gleam").write_text(
        "pub fn test_main() {\n  Nil\n}\n",
        encoding="utf-8",
    )
    (repo_path / "janet-app" / "project.janet").write_text(
        '(declare-project :name "demo" :source @["src"] :main "src/main.janet")\n',
        encoding="utf-8",
    )
    (repo_path / "janet-app" / "src" / "main.janet").write_text(
        '(import ./demo/helper :as helper)\n\n(defn main []\n  (helper/render-json))\n',
        encoding="utf-8",
    )
    (repo_path / "janet-app" / "src" / "demo" / "helper.janet").write_text(
        "(defn render-json [] @{})\n",
        encoding="utf-8",
    )
    (repo_path / "janet-app" / "test" / "main.janet").write_text(
        "(defn test-main [] @{})\n",
        encoding="utf-8",
    )
    (repo_path / "dhall-app" / "package.dhall").write_text(
        "{ Type = ./schemas/Step.dhall }\n",
        encoding="utf-8",
    )
    (repo_path / "dhall-app" / "schemas" / "Step.dhall").write_text(
        "{ Type = \"step\", default = \"run\" }\n",
        encoding="utf-8",
    )
    (repo_path / "dhall-app" / "workflow.dhall").write_text(
        "let Package = ./package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )
    (repo_path / "dhall-app" / "tests" / "workflow_test.dhall").write_text(
        "let Package = ../package.dhall\nin Package.Type\n",
        encoding="utf-8",
    )
    (repo_path / "rego-app" / "policy" / "main.rego").write_text(
        "package policy.main\n\n"
        "import data.policy.lib.helpers as helper\n\n"
        "allow if {\n"
        "    helper.render_json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "rego-app" / "policy" / "lib" / "helpers.rego").write_text(
        "package policy.lib.helpers\n\n"
        "render_json if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "yara-app" / "rules" / "lib").mkdir(parents=True)
    (repo_path / "yara-app" / "tests").mkdir(parents=True)
    (repo_path / "yara-app" / "rules" / "index.yar").write_text(
        'include "./main.yar"\n'
        'include "./lib/helper.yar"\n',
        encoding="utf-8",
    )
    (repo_path / "yara-app" / "rules" / "main.yar").write_text(
        "rule main_rule {\n"
        "  condition:\n"
        "    helper_rule\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "yara-app" / "rules" / "lib" / "helper.yar").write_text(
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "yara-app" / "tests" / "rules_test.yar").write_text(
        "rule rules_test {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "bitbake-app" / "conf").mkdir(parents=True)
    (repo_path / "bitbake-app" / "classes").mkdir(parents=True)
    (repo_path / "bitbake-app" / "recipes-core" / "base").mkdir(parents=True)
    (repo_path / "bitbake-app" / "recipes-core" / "images").mkdir(parents=True)
    (repo_path / "bitbake-app" / "conf" / "layer.conf").write_text(
        'BBPATH .= ":${LAYERDIR}"\n'
        'BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"\n',
        encoding="utf-8",
    )
    (repo_path / "bitbake-app" / "classes" / "image.bbclass").write_text(
        "python do_rootfs() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "bitbake-app" / "recipes-core" / "base" / "base.inc").write_text(
        'BASE_NAME = "base"\n',
        encoding="utf-8",
    )
    (repo_path / "bitbake-app" / "recipes-core" / "images" / "core-image-minimal.bb").write_text(
        "require ../base/base.inc\n"
        "inherit image\n"
        'IMAGE_FEATURES += "ssh-server-dropbear"\n',
        encoding="utf-8",
    )
    (repo_path / "hcl-app" / "modules" / "child").mkdir(parents=True)
    (repo_path / "hcl-app" / "main.tf").write_text(
        'module "child" {\n'
        '  source = "./modules/child"\n'
        '}\n\n'
        'variable "name" {\n'
        '  default = "demo"\n'
        '}\n\n'
        "locals {\n"
        '  prefix = "vpc-${var.name}"\n'
        "}\n\n"
        'output "full_name" {\n'
        "  value = local.prefix\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "hcl-app" / "modules" / "child" / "main.tf").write_text(
        'output "child_id" {\n'
        '  value = "child"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "agda-app" / "standard-library.agda-lib").write_text(
        "name: demo\ninclude: src\n",
        encoding="utf-8",
    )
    (repo_path / "agda-app" / "src" / "Main.agda").write_text(
        "module Main where\n\n"
        "open import Data.Helper using (helper)\n\n"
        "main : Set\n"
        "main = helper\n",
        encoding="utf-8",
    )
    (repo_path / "agda-app" / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )
    (repo_path / "idris-app" / "demo.ipkg").write_text(
        "package demo\n"
        "sourcedir = src\n"
        "modules = Demo.Helper\n"
        "main = Main\n",
        encoding="utf-8",
    )
    (repo_path / "idris-app" / "src" / "Main.idr").write_text(
        "module Main\n\n"
        "import Demo.Helper\n\n"
        "main : IO ()\n"
        "main = renderJson\n",
        encoding="utf-8",
    )
    (repo_path / "idris-app" / "src" / "Demo" / "Helper.idr").write_text(
        "module Demo.Helper\n\n"
        "renderJson : IO ()\n"
        "renderJson = pure ()\n",
        encoding="utf-8",
    )
    (repo_path / "idris-app" / "tests" / "Main.idr").write_text(
        "module Tests.Main\n\n"
        "testMain : IO ()\n"
        "testMain = pure ()\n",
        encoding="utf-8",
    )
    (repo_path / "raku-app" / "META6.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "provides": {"Demo::Helper": "lib/Demo/Helper.rakumod"},
                "bin": ["demo.raku"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "raku-app" / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() is export { \"{}\" }\n",
        encoding="utf-8",
    )
    (repo_path / "raku-app" / "bin" / "demo.raku").write_text(
        "use Demo::Helper;\n\nsub main() {\n    Demo::Helper::render-json();\n}\n",
        encoding="utf-8",
    )
    (repo_path / "nushell-app" / "main.nu").write_text(
        "source modules/helper.nu\n\n"
        "def main [] {\n"
        "  render-json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "nushell-app" / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "fish-app" / "main.fish").write_text(
        "source functions/helper.fish\n\n"
        "function main\n"
        "    helper\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "fish-app" / "functions" / "helper.fish").write_text(
        "function helper\n"
        "    echo '{}'\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "fish-app" / "conf.d" / "init.fish").write_text(
        "helper\n",
        encoding="utf-8",
    )
    (repo_path / "haxe-app" / "build.hxml").write_text(
        "-cp src\n-main demo.Main\n",
        encoding="utf-8",
    )
    (repo_path / "haxe-app" / "src" / "demo" / "Main.hx").write_text(
        "package demo;\n"
        "\n"
        "import demo.Helper;\n"
        "\n"
        "class Main {\n"
        "    static function main() {\n"
        "        Helper.renderJson();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "haxe-app" / "src" / "demo" / "Helper.hx").write_text(
        "package demo;\n"
        "\n"
        "class Helper {\n"
        "    public static function renderJson():String {\n"
        '        return "{}";\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "automation").mkdir(parents=True, exist_ok=True)
    (repo_path / "automation" / "Main.ahk").write_text(
        '#Include "../Lib/Helper.ahk"\n'
        "Main() {\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Lib").mkdir(parents=True, exist_ok=True)
    (repo_path / "Lib" / "Helper.ahk").write_text(
        "RenderJson(value) {\n"
        "    return value\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "starlark-app" / "MODULE.bazel").write_text(
        'module(name = "acme")\n',
        encoding="utf-8",
    )
    (repo_path / "starlark-app" / "BUILD.bazel").write_text(
        'load("//rules:demo.bzl", "demo_macro")\n'
        '\n'
        'demo_macro(name = "app")\n',
        encoding="utf-8",
    )
    (repo_path / "starlark-app" / "rules" / "demo.bzl").write_text(
        'load("//lib:common.bzl", "render_json")\n'
        "\n"
        "def demo_macro(name):\n"
        "    return render_json(name)\n",
        encoding="utf-8",
    )
    (repo_path / "starlark-app" / "lib" / "common.bzl").write_text(
        "def render_json(name):\n"
        "    return name\n",
        encoding="utf-8",
    )
    (repo_path / "nix-app" / "flake.nix").write_text(
        "{\n"
        "  inputs.nixpkgs.url = \"github:NixOS/nixpkgs\";\n"
        "  outputs = { self, nixpkgs }:\n"
        "    let formatter = import ./nix/lib/formatter.nix { pkgs = nixpkgs.legacyPackages.x86_64-linux; }; in {\n"
        "      formatter = formatter.mkFormatter nixpkgs.legacyPackages.x86_64-linux.alejandra;\n"
        "    };\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "nix-app" / "nix" / "lib" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "{\n"
        "  mkFormatter = package: package;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "smalltalk-app" / ".smalltalk.ston").write_text(
        "{ }\n",
        encoding="utf-8",
    )
    (repo_path / "smalltalk-app" / "src" / "Demo-Core" / "package.st").write_text(
        "Package { #name : 'Demo-Core' }\n",
        encoding="utf-8",
    )
    (repo_path / "smalltalk-app" / "src" / "Demo-Core" / "Helper.class.st").write_text(
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
    (repo_path / "elisp-app" / "Cask").write_text(
        "(source gnu)\n"
        '(package-file "main.el")\n',
        encoding="utf-8",
    )
    (repo_path / "elisp-app" / "main.el").write_text(
        "(require 'helper)\n"
        "(provide 'main)\n"
        "(defun run () (helper-fn))\n",
        encoding="utf-8",
    )
    (repo_path / "elisp-app" / "lisp" / "helper.el").write_text(
        "(provide 'helper)\n"
        "(defun helper-fn () 1)\n",
        encoding="utf-8",
    )
    (repo_path / "scheme-app" / "package.scm").write_text(
        "(define-library (acme app)\n"
        "  (export run)\n"
        "  (import (acme helper))\n"
        "  (begin\n"
        "    (define (run) (helper))))\n",
        encoding="utf-8",
    )
    (repo_path / "scheme-app" / "main.scm").write_text(
        "#!r6rs\n"
        "(import (acme helper))\n"
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "scheme-app" / "lib" / "acme" / "helper.sld").write_text(
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n",
        encoding="utf-8",
    )
    (repo_path / "racket-app" / "info.rkt").write_text(
        "#lang info\n"
        '(define collection "racket-app")\n',
        encoding="utf-8",
    )
    (repo_path / "racket-app" / "main.rkt").write_text(
        "#lang racket\n"
        '(require "private/helper.rkt")\n'
        "(define (run) (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "racket-app" / "private" / "helper.rkt").write_text(
        "#lang racket\n"
        "(define (helper) 1)\n",
        encoding="utf-8",
    )
    (repo_path / "include" / "io.inc").write_text(
        "extern print_string\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.c").write_text(
        '#include "io.h"\n'
        "int main(void) { return 0; }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.as").write_text(
        "package demo.app {\n"
        "    public class Main {\n"
        "        public function boot():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2]).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )
    (repo_path / "script" / "app.pl").write_text(
        "use strict;\n"
        "use warnings;\n"
        "sub run { return 1; }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.m").write_text(
        "function value = main()\nvalue = helper();\nend\n",
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "Helpers.wl").write_text(
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        "helper[] := 1;\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )
    (repo_path / "Kernel" / "init.m").write_text(
        'Get["Acme`Helpers`"];\n',
        encoding="utf-8",
    )
    (repo_path / "ios" / "AppDelegate.m").write_text(
        "#import <Foundation/Foundation.h>\n@implementation AppDelegate\n@end\n",
        encoding="utf-8",
    )
    (repo_path / "ios" / "AppDelegate.h").write_text(
        "#import <Foundation/Foundation.h>\n@interface AppDelegate : NSObject\n@end\n",
        encoding="utf-8",
    )
    (repo_path / "vb6" / "Project1.vbp").write_text(
        'Type=Exe\nForm=Form1.frm\nStartup="Form1"\nName="Project1"\n',
        encoding="utf-8",
    )
    (repo_path / "vb6" / "Form1.frm").write_text(
        "VERSION 5.00\n"
        "Begin VB.Form Form1\n"
        "End\n"
        'Attribute VB_Name = "Form1"\n',
        encoding="utf-8",
    )
    (repo_path / "vb6" / "modMain.bas").write_text(
        'Attribute VB_Name = "modMain"\n'
        "Option Explicit\n"
        "Public Sub RunApp()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "vba" / "JsonConverter.bas").write_text(
        'Attribute VB_Name = "JsonConverter"\n'
        "Option Explicit\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "build.vbs").write_text(
        "Option Explicit\n"
        "Sub Main()\n"
        "End Sub\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.wsf").write_text(
        "<job>\n"
        '  <script language="VBScript" src="build.vbs"></script>\n'
        '  <script language="VBScript">\n'
        "    Option Explicit\n"
        "    Sub Main()\n"
        "    End Sub\n"
        "  </script>\n"
        "</job>\n",
        encoding="utf-8",
    )
    (repo_path / "automation").mkdir(parents=True, exist_ok=True)
    (repo_path / "automation" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on RenderJson(value)\n"
        "        return value\n"
        "    end RenderJson\n"
        "end script\n",
        encoding="utf-8",
    )
    (repo_path / "automation" / "Main.applescript").write_text(
        'property helperScript : load script POSIX file "Helper.applescript"\n'
        "on run\n"
        "    helperScript's RenderJson(\"{}\")\n"
        "end run\n",
        encoding="utf-8",
    )
    (repo_path / "automation" / "Compiled.scpt").write_text(
        "on run\n"
        "    return 1\n"
        "end run\n",
        encoding="utf-8",
    )
    (repo_path / "tcllib" / "pkgIndex.tcl").write_text(
        "package ifneeded sha1 2.0.5 [list source [file join $dir sha1.tcl]]\n",
        encoding="utf-8",
    )
    (repo_path / "tcllib" / "sha1.tcl").write_text(
        "package provide sha1 2.0.5\n"
        "proc ::sha1::run {} {\n"
        "    return ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lisp" / "acme.asd").write_text(
        '(asdf:defsystem "acme"\n'
        '  :components ((:file "package") (:file "helper") (:file "app")))\n',
        encoding="utf-8",
    )
    (repo_path / "lisp" / "app.lisp").write_text(
        "(defpackage #:acme.app (:use #:cl))\n"
        "(in-package #:acme.app)\n"
        "(defun run () (helper))\n",
        encoding="utf-8",
    )
    (repo_path / "foxpro" / "main.prg").write_text(
        "LPARAMETERS value\n"
        "FUNCTION main()\n"
        "    RETURN value\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )
    (repo_path / "contracts" / "Counter.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "contract Counter {\n"
        "    function increment() public {}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.sv").write_text(
        "module top;\nendmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "child.v").write_text(
        "module child;\nendmodule\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "defs.vh").write_text(
        "`ifndef DEFS_VH\n`define DEFS_VH\n`endif\n",
        encoding="utf-8",
    )
    (repo_path / "vhdl" / "top.vhd").write_text(
        "entity top is\n"
        "end entity;\n"
        "architecture rtl of top is\n"
        "begin\n"
        "end architecture;\n",
        encoding="utf-8",
    )
    (repo_path / "godot" / "scripts" / "player.gd").write_text(
        "class_name Player\n"
        "extends Node\n"
        "func ready_up() -> void:\n"
        "    pass\n",
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
    (repo_path / "logic" / "Types.L5X").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        '<RSLogix5000Content TargetType="DataType">\n'
        '  <Controller Name="PlantController">\n'
        "    <DataTypes>\n"
        '      <DataType Name="MotorStatus">\n'
        "        <Members>\n"
        '          <Member Name="Running" DataType="BOOL"/>\n'
        "        </Members>\n"
        "      </DataType>\n"
        "    </DataTypes>\n"
        "  </Controller>\n"
        "</RSLogix5000Content>\n",
        encoding="utf-8",
    )
    (repo_path / "labview" / "App.lvproj").write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Project Type=\"Project\">\n"
        '  <Item Name="Main" Type="VI" URL="Source/Main.vi" />\n'
        '  <Item Name="Config" Type="Control" URL="Controls/Config.ctl" />\n'
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "labview" / "Source" / "Main.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "labview" / "Controls" / "Config.ctl").write_bytes(b"RSRC\r\n\x00\x03LVCCLBVW")
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
        / "Acme"
        / "AxClass"
        / "AcmeMain.xml"
    ).write_text(
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
        "</AxClass>\n",
        encoding="utf-8",
    )
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
    (repo_path / "puppet-app" / "manifests").mkdir(parents=True)
    (repo_path / "puppet-app" / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    (repo_path / "puppet-app" / "Puppetfile").write_text(
        "mod 'puppetlabs-stdlib'\n",
        encoding="utf-8",
    )
    (repo_path / "puppet-app" / "manifests" / "init.pp").write_text(
        "class apache {\n"
        "  include apache::params\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "hack-app" / "src").mkdir(parents=True)
    (repo_path / "hack-app" / "tests").mkdir(parents=True)
    (repo_path / "hack-app" / ".hhconfig").write_text(
        "assume_php = false\n",
        encoding="utf-8",
    )
    (repo_path / "hack-app" / "src" / "Ref.php").write_text(
        "<?hh\nnamespace Demo;\nfinal class Ref<T> {}\n",
        encoding="utf-8",
    )
    (repo_path / "hack-app" / "src" / "Vec.hack").write_text(
        "namespace Demo;\nnewtype Vec<T> = vec<T>;\n",
        encoding="utf-8",
    )
    (repo_path / "hack-app" / "tests" / "RefTest.php").write_text(
        "<?hh\nnamespace Demo;\nfinal class RefTest {}\n",
        encoding="utf-8",
    )
    (repo_path / "pascal-app" / "src").mkdir(parents=True)
    (repo_path / "pascal-app" / "src" / "main.pp").write_text(
        "program Main;\n"
        "begin\n"
        "end.\n",
        encoding="utf-8",
    )
    (repo_path / "batch-app" / "scripts").mkdir(parents=True)
    (repo_path / "batch-app" / "build.bat").write_text(
        "@echo off\n"
        "call scripts\\helper.cmd\n",
        encoding="utf-8",
    )
    (repo_path / "batch-app" / "scripts" / "helper.cmd").write_text(
        "@echo off\n"
        "echo helper\n",
        encoding="utf-8",
    )
    (repo_path / "make-app" / "mk").mkdir(parents=True)
    (repo_path / "make-app" / "Makefile").write_text(
        "include mk/common.mk\n"
        "build:\n"
        "\t$(MAKE) helper\n",
        encoding="utf-8",
    )
    (repo_path / "make-app" / "mk" / "common.mk").write_text(
        "helper:\n"
        "\t@echo helper\n",
        encoding="utf-8",
    )

    assert probe_module._candidate_ecosystems_for_path("fixtures/main.adb_body") == {"unknown"}
    assert probe_module._candidate_ecosystems_for_path("fixtures/main.unknown_ext") == {
        "unknown"
    }
    assert probe_module._candidate_ecosystems_for_path("src/main.adb") == {"ada"}
    assert probe_module._candidate_ecosystems_for_path("src/main.c") == {"c"}
    assert probe_module._candidate_ecosystems_for_path("src/Main.as") == {"actionscript"}
    assert probe_module._candidate_ecosystems_for_path(
        "bin/translate",
        repo_path=repo_path,
    ) == {"awk"}
    assert probe_module._candidate_ecosystems_for_path("lib/math.awk") == {"awk"}
    assert probe_module._candidate_ecosystems_for_path("coffee-app/src/main.coffee") == {
        "coffeescript"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "coffee-app/Cakefile",
        repo_path=repo_path,
    ) == {"coffeescript"}
    assert probe_module._candidate_ecosystems_for_path(
        "cfml-app/Application.cfc"
    ) == {"cfml"}
    assert probe_module._candidate_ecosystems_for_path(
        "cfml-app/public/index.cfm"
    ) == {"cfml"}
    assert probe_module._candidate_ecosystems_for_path(
        "cfml-app/box.json",
        repo_path=repo_path,
    ) == {"cfml"}
    assert probe_module._candidate_ecosystems_for_path(
        "database/Acme.sqlproj",
        repo_path=repo_path,
    ) == {"tsql"}
    assert probe_module._candidate_ecosystems_for_path(
        "database/dbo/Stored Procedures/LoadCustomers.sql",
        repo_path=repo_path,
    ) == {"tsql"}
    assert probe_module._candidate_ecosystems_for_path(
        "delphi-app/AcmeApp.dproj",
        repo_path=repo_path,
    ) == {"delphi"}
    assert probe_module._candidate_ecosystems_for_path(
        "delphi-app/AcmeApp.dpr",
        repo_path=repo_path,
    ) == {"delphi"}
    assert probe_module._candidate_ecosystems_for_path(
        "delphi-app/source/MainForm.pas",
        repo_path=repo_path,
    ) == {"delphi"}
    assert probe_module._candidate_ecosystems_for_path("elm-app/src/Main.elm") == {"elm"}
    assert probe_module._candidate_ecosystems_for_path("vala-app/src/main.vala") == {"vala"}
    assert probe_module._candidate_ecosystems_for_path("vala-app/vapi/demo.vapi") == {"vala"}
    assert probe_module._candidate_ecosystems_for_path("mql5-app/Experts/Main.mq5") == {"mql5"}
    assert probe_module._candidate_ecosystems_for_path("mql5-app/Include/Helper.mqh") == {"mql5"}
    assert probe_module._candidate_ecosystems_for_path("mql5-app/demo.mqproj") == {"mql5"}
    assert probe_module._candidate_ecosystems_for_path(
        "gams-app/main.gms",
        repo_path=repo_path,
    ) == {"gams"}
    assert probe_module._candidate_ecosystems_for_path(
        "gams-app/include/common.inc",
        repo_path=repo_path,
    ) == {"gams"}
    assert probe_module._candidate_ecosystems_for_path(
        "openscad-app/main.scad",
        repo_path=repo_path,
    ) == {"openscad"}
    assert probe_module._candidate_ecosystems_for_path(
        "haxe-app/build.hxml",
        repo_path=repo_path,
    ) == {"haxe"}
    assert probe_module._candidate_ecosystems_for_path(
        "haxe-app/src/demo/Main.hx",
        repo_path=repo_path,
    ) == {"haxe"}
    assert probe_module._candidate_ecosystems_for_path(
        "automation/Main.ahk",
        repo_path=repo_path,
    ) == {"autohotkey"}
    assert probe_module._candidate_ecosystems_for_path(
        "batch-app/build.bat",
        repo_path=repo_path,
    ) == {"batchfile"}
    assert probe_module._candidate_ecosystems_for_path(
        "make-app/Makefile",
        repo_path=repo_path,
    ) == {"makefile"}
    assert probe_module._candidate_ecosystems_for_path(
        "make-app/mk/common.mk",
        repo_path=repo_path,
    ) == {"makefile"}
    assert probe_module._candidate_ecosystems_for_path(
        "purescript-app/spago.yaml",
        repo_path=repo_path,
    ) == {"purescript"}
    assert probe_module._candidate_ecosystems_for_path(
        "purescript-app/src/Main.purs",
        repo_path=repo_path,
    ) == {"purescript"}
    assert probe_module._candidate_ecosystems_for_path(
        "gleam-app/gleam.toml",
        repo_path=repo_path,
    ) == {"gleam"}
    assert probe_module._candidate_ecosystems_for_path(
        "gleam-app/src/main.gleam",
        repo_path=repo_path,
    ) == {"gleam"}
    assert probe_module._candidate_ecosystems_for_path(
        "janet-app/project.janet",
        repo_path=repo_path,
    ) == {"janet"}
    assert probe_module._candidate_ecosystems_for_path(
        "janet-app/src/main.janet",
        repo_path=repo_path,
    ) == {"janet"}
    assert probe_module._candidate_ecosystems_for_path(
        "dhall-app/package.dhall",
        repo_path=repo_path,
    ) == {"dhall"}
    assert probe_module._candidate_ecosystems_for_path(
        "dhall-app/workflow.dhall",
        repo_path=repo_path,
    ) == {"dhall"}
    assert probe_module._candidate_ecosystems_for_path(
        "puppet-app/metadata.json",
        repo_path=repo_path,
    ) == {"puppet"}
    assert probe_module._candidate_ecosystems_for_path(
        "puppet-app/Puppetfile",
        repo_path=repo_path,
    ) == {"puppet"}
    assert probe_module._candidate_ecosystems_for_path(
        "puppet-app/manifests/init.pp",
        repo_path=repo_path,
    ) == {"puppet"}
    assert probe_module._candidate_ecosystems_for_path(
        "hack-app/.hhconfig",
        repo_path=repo_path,
    ) == {"hack"}
    assert probe_module._candidate_ecosystems_for_path(
        "hack-app/src/Ref.php",
        repo_path=repo_path,
    ) == {"hack"}
    assert probe_module._candidate_ecosystems_for_path(
        "hack-app/src/Vec.hack",
        repo_path=repo_path,
    ) == {"hack"}
    assert probe_module._candidate_ecosystems_for_path(
        "pascal-app/src/main.pp",
        repo_path=repo_path,
    ) == {"pascal"}
    assert probe_module._candidate_ecosystems_for_path(
        "rego-app/policy/main.rego",
        repo_path=repo_path,
    ) == {"rego"}
    assert probe_module._candidate_ecosystems_for_path(
        "rego-app/policy/lib/helpers.rego",
        repo_path=repo_path,
    ) == {"rego"}
    assert probe_module._candidate_ecosystems_for_path(
        "yara-app/rules/index.yar",
        repo_path=repo_path,
    ) == {"yara"}
    assert probe_module._candidate_ecosystems_for_path(
        "yara-app/rules/lib/helper.yar",
        repo_path=repo_path,
    ) == {"yara"}
    assert probe_module._candidate_ecosystems_for_path(
        "bitbake-app/conf/layer.conf",
        repo_path=repo_path,
    ) == {"bitbake"}
    assert probe_module._candidate_ecosystems_for_path(
        "bitbake-app/recipes-core/images/core-image-minimal.bb",
        repo_path=repo_path,
    ) == {"bitbake"}
    assert probe_module._candidate_ecosystems_for_path(
        "hcl-app/main.tf",
        repo_path=repo_path,
    ) == {"hcl"}
    assert probe_module._candidate_ecosystems_for_path(
        "hcl-app/modules/child/main.tf",
        repo_path=repo_path,
    ) == {"hcl"}
    assert probe_module._candidate_ecosystems_for_path(
        "bicep-app/bicepconfig.json",
        repo_path=repo_path,
    ) == {"bicep"}
    assert probe_module._candidate_ecosystems_for_path(
        "bicep-app/main.bicep",
        repo_path=repo_path,
    ) == {"bicep"}
    assert probe_module._candidate_ecosystems_for_path(
        "tlaplus-app/Spec.tla",
        repo_path=repo_path,
    ) == {"tlaplus"}
    assert probe_module._candidate_ecosystems_for_path(
        "agda-app/standard-library.agda-lib",
        repo_path=repo_path,
    ) == {"agda"}
    assert probe_module._candidate_ecosystems_for_path(
        "agda-app/src/Main.agda",
        repo_path=repo_path,
    ) == {"agda"}
    assert probe_module._candidate_ecosystems_for_path(
        "idris-app/demo.ipkg",
        repo_path=repo_path,
    ) == {"idris"}
    assert probe_module._candidate_ecosystems_for_path(
        "idris-app/src/Main.idr",
        repo_path=repo_path,
    ) == {"idris"}
    assert probe_module._candidate_ecosystems_for_path(
        "raku-app/META6.json",
        repo_path=repo_path,
    ) == {"raku"}
    assert probe_module._candidate_ecosystems_for_path(
        "raku-app/lib/Demo/Helper.rakumod",
        repo_path=repo_path,
    ) == {"raku"}
    assert probe_module._candidate_ecosystems_for_path(
        "nushell-app/main.nu",
        repo_path=repo_path,
    ) == {"nushell"}
    assert probe_module._candidate_ecosystems_for_path(
        "fish-app/main.fish",
        repo_path=repo_path,
    ) == {"fish"}
    assert probe_module._candidate_ecosystems_for_path(
        "fish-app/functions/helper.fish",
        repo_path=repo_path,
    ) == {"fish"}
    assert probe_module._candidate_ecosystems_for_path(
        "starlark-app/MODULE.bazel",
        repo_path=repo_path,
    ) == {"starlark"}
    assert probe_module._candidate_ecosystems_for_path(
        "starlark-app/BUILD.bazel",
        repo_path=repo_path,
    ) == {"starlark"}
    assert probe_module._candidate_ecosystems_for_path(
        "starlark-app/rules/demo.bzl",
        repo_path=repo_path,
    ) == {"starlark"}
    assert probe_module._candidate_ecosystems_for_path(
        "nix-app/flake.nix",
        repo_path=repo_path,
    ) == {"nix"}
    assert probe_module._candidate_ecosystems_for_path(
        "nix-app/nix/lib/formatter.nix",
        repo_path=repo_path,
    ) == {"nix"}
    assert probe_module._candidate_ecosystems_for_path(
        "smalltalk-app/.smalltalk.ston",
        repo_path=repo_path,
    ) == {"smalltalk"}
    assert probe_module._candidate_ecosystems_for_path(
        "smalltalk-app/src/Demo-Core/Helper.class.st",
        repo_path=repo_path,
    ) == {"smalltalk"}
    assert probe_module._candidate_ecosystems_for_path(
        "elisp-app/Cask",
        repo_path=repo_path,
    ) == {"emacslisp"}
    assert probe_module._candidate_ecosystems_for_path(
        "elisp-app/main.el",
        repo_path=repo_path,
    ) == {"emacslisp"}
    assert probe_module._candidate_ecosystems_for_path(
        "elisp-app/lisp/helper.el",
        repo_path=repo_path,
    ) == {"emacslisp"}
    assert probe_module._candidate_ecosystems_for_path("scheme-app/package.scm") == {"scheme"}
    assert probe_module._candidate_ecosystems_for_path("scheme-app/main.scm") == {"scheme"}
    assert probe_module._candidate_ecosystems_for_path("scheme-app/lib/acme/helper.sld") == {
        "scheme"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "racket-app/info.rkt",
        repo_path=repo_path,
    ) == {"racket"}
    assert probe_module._candidate_ecosystems_for_path(
        "racket-app/main.rkt",
        repo_path=repo_path,
    ) == {"racket"}
    assert probe_module._candidate_ecosystems_for_path("games/Maze.sb3") == {"scratch"}
    assert probe_module._candidate_ecosystems_for_path("imports/Legacy.xpo") == {"xpp"}
    assert probe_module._candidate_ecosystems_for_path("src/boot.asm") == {"assembly"}
    assert probe_module._candidate_ecosystems_for_path("src/zcl_math.clas.abap") == {"abap"}
    assert probe_module._candidate_ecosystems_for_path("src/main.cbl") == {"cobol"}
    assert probe_module._candidate_ecosystems_for_path("db/order_api.pkb") == {"plsql"}
    assert probe_module._candidate_ecosystems_for_path("programs/report.sas") == {"sas"}
    assert probe_module._candidate_ecosystems_for_path("src/main.sml") == {"sml"}
    assert probe_module._candidate_ecosystems_for_path("src/main.prolog") == {"prolog"}
    assert probe_module._candidate_ecosystems_for_path("logic/Main.L5X") == {"ladder"}
    assert probe_module._candidate_ecosystems_for_path("src/main.m") == {"unknown"}
    assert probe_module._candidate_ecosystems_for_path("Kernel/Helpers.wl") == {"wolfram"}
    assert probe_module._candidate_ecosystems_for_path("scripts/tree_api/tree_api.gml") == {
        "gml"
    }
    assert probe_module._candidate_ecosystems_for_path("src/family.pl", repo_path=repo_path) == {
        "prolog"
    }
    assert probe_module._candidate_ecosystems_for_path("script/app.pl", repo_path=repo_path) == {
        "perl"
    }
    assert probe_module._candidate_ecosystems_for_path("src/main.m", repo_path=repo_path) == {
        "matlab"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "Kernel/init.m",
        repo_path=repo_path,
    ) == {"wolfram"}
    assert probe_module._candidate_ecosystems_for_path(
        "ios/AppDelegate.m",
        repo_path=repo_path,
    ) == {"objectivec"}
    assert probe_module._candidate_ecosystems_for_path(
        "ios/AppDelegate.h",
        repo_path=repo_path,
    ) == {"objectivec"}
    assert probe_module._candidate_ecosystems_for_path(
        "include/io.inc",
        repo_path=repo_path,
    ) == {"assembly"}
    assert probe_module._candidate_ecosystems_for_path(
        "vb6/modMain.bas",
        repo_path=repo_path,
    ) == {"vba"}
    assert probe_module._candidate_ecosystems_for_path(
        "vb6/Form1.frm",
        repo_path=repo_path,
    ) == {"vb6"}
    assert probe_module._candidate_ecosystems_for_path(
        "vba/JsonConverter.bas",
        repo_path=repo_path,
    ) == {"vba"}
    assert probe_module._candidate_ecosystems_for_path(
        "vb6/Project1.vbp",
        repo_path=repo_path,
    ) == {"vb6"}
    assert probe_module._candidate_ecosystems_for_path("scripts/build.vbs") == {"vbscript"}
    assert probe_module._candidate_ecosystems_for_path(
        "scripts/main.wsf",
        repo_path=repo_path,
    ) == {"vbscript"}
    assert probe_module._candidate_ecosystems_for_path("automation/Helper.applescript") == {
        "applescript"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "automation/Compiled.scpt",
        repo_path=repo_path,
    ) == {"applescript"}
    assert probe_module._candidate_ecosystems_for_path("tcllib/pkgIndex.tcl") == {"tcl"}
    assert probe_module._candidate_ecosystems_for_path("tcllib/sha1.tcl") == {"tcl"}
    assert probe_module._candidate_ecosystems_for_path("qrpglesrc/ORD101.PGM.RPGLE") == {"rpg"}
    assert probe_module._candidate_ecosystems_for_path("qprotosrc/CUSTOMER.RPGLEINC") == {
        "rpg"
    }
    assert probe_module._candidate_ecosystems_for_path("lisp/acme.asd") == {"lisp"}
    assert probe_module._candidate_ecosystems_for_path(
        "lisp/app.lisp",
        repo_path=repo_path,
    ) == {"lisp"}
    assert probe_module._candidate_ecosystems_for_path(
        "foxpro/main.prg",
        repo_path=repo_path,
    ) == {"foxpro"}
    assert probe_module._candidate_ecosystems_for_path(
        "contracts/Counter.sol",
        repo_path=repo_path,
    ) == {"solidity"}
    assert probe_module._candidate_ecosystems_for_path(
        "shaders/noise.glsl",
        repo_path=repo_path,
    ) == {"glsl"}
    assert probe_module._candidate_ecosystems_for_path(
        "shaders/main.frag",
        repo_path=repo_path,
    ) == {"glsl"}
    assert probe_module._candidate_ecosystems_for_path(
        "shaders/passthrough.vert",
        repo_path=repo_path,
    ) == {"glsl"}
    assert probe_module._candidate_ecosystems_for_path(
        "_CoqProject",
        repo_path=repo_path,
    ) == {"coq"}
    assert probe_module._candidate_ecosystems_for_path(
        "theories/Main.v",
        repo_path=repo_path,
    ) == {"coq"}
    assert probe_module._candidate_ecosystems_for_path(
        "lean-app/lean-toolchain",
        repo_path=repo_path,
    ) == {"lean"}
    assert probe_module._candidate_ecosystems_for_path(
        "lean-app/Batteries/Main.lean",
        repo_path=repo_path,
    ) == {"lean"}
    assert probe_module._candidate_ecosystems_for_path("rtl/top.sv") == {"systemverilog"}
    assert probe_module._candidate_ecosystems_for_path(
        "rtl/child.v",
        repo_path=repo_path,
    ) == {"verilog"}
    assert probe_module._candidate_ecosystems_for_path(
        "rtl/defs.vh",
        repo_path=repo_path,
    ) == {"verilog"}
    assert probe_module._candidate_ecosystems_for_path(
        "vhdl/top.vhd",
        repo_path=repo_path,
    ) == {"vhdl"}
    assert probe_module._candidate_ecosystems_for_path(
        "godot/scripts/player.gd",
        repo_path=repo_path,
    ) == {"gdscript"}
    assert probe_module._candidate_ecosystems_for_path(
        "logic/Main.L5X",
        repo_path=repo_path,
    ) == {"ladder"}
    assert probe_module._candidate_ecosystems_for_path(
        "logic/Types.L5X",
        repo_path=repo_path,
    ) == {"ladder"}
    assert probe_module._candidate_ecosystems_for_path("labview/App.lvproj") == {"labview"}
    assert probe_module._candidate_ecosystems_for_path("labview/Source/Main.vi") == {"labview"}
    assert probe_module._candidate_ecosystems_for_path(
        "PackagesLocalDirectory/Acme/Acme/AxClass/AcmeMain.xml",
        repo_path=repo_path,
    ) == {"xpp"}
    assert probe_module._candidate_ecosystems_for_path(
        "PackagesLocalDirectory/Acme/Descriptor/Acme.xml",
        repo_path=repo_path,
    ) == {"xpp"}
    assert probe_module._candidate_ecosystems_for_path(
        "labview/Controls/Config.ctl",
        repo_path=repo_path,
    ) == {"labview"}
    assert probe_module._candidate_ecosystems_for_path(
        "force-app/main/default/classes/AccountTriggerHandler.cls",
        repo_path=repo_path,
    ) == {"apex"}
    assert probe_module._candidate_ecosystems_for_path(
        "force-app/main/default/triggers/AccountTrigger.trigger",
        repo_path=repo_path,
    ) == {"apex"}

