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
    assert repository_service._language_for_path(Path("src/main.gleam")) == "gleam"
    assert repository_service._language_for_path(Path("src/main.janet")) == "janet"
    assert repository_service._language_for_path(Path("src/Main.idr")) == "idris"
    assert repository_service._language_for_path(Path("demo.ipkg")) == "idris"
    assert repository_service._language_for_path(Path("lib/Demo/Helper.rakumod")) == "raku"
    assert repository_service._language_for_path(Path("bin/demo.raku")) == "raku"
    assert repository_service._language_for_path(Path("scripts/main.nu")) == "nushell"
    assert repository_service._language_for_path(Path("src/Main.hx")) == "haxe"
    assert repository_service._language_for_path(Path("src/Main.hack")) == "hack"
    assert repository_service._language_for_path(Path("build.hxml")) == "haxe"
    assert repository_service._language_for_path(Path("BUILD.bazel")) == "starlark"
    assert repository_service._language_for_path(Path("MODULE.bazel")) == "starlark"
    assert repository_service._language_for_path(Path("rules/demo.bzl")) == "starlark"
    assert repository_service._language_for_path(Path("flake.nix")) == "nix"
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
    assert (
        repository_service._language_for_path(
            Path("Source/Main.vim"),
            text="RSRC\nLVIN\n",
        )
        == "labview"
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

