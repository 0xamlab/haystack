"""Tests for repository_intelligence_service: languages_a.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_c_family_operational_reference_name_filters_macro_like_noise() -> None:
    assert repository_service._is_c_family_operational_reference_name("format_value")
    assert not repository_service._is_c_family_operational_reference_name("FMT_ENABLE_IF")
    assert not repository_service._is_c_family_operational_reference_name("__attribute__")
    assert not repository_service._is_c_family_operational_reference_name("va_end")


def test_visual_basic_adapter_module_aliases_include_namespace_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "visual-basic-alias-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "src" / "Acme" / "Services.vb").write_text(
        "Namespace Acme.Core\n"
        "Public Class Mediator\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )

    aliases = repository_service.visual_basic_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Acme/Services.vb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme/services.vb" in aliases
    assert "src/acme/services" in aliases
    assert "src.acme.services" in aliases
    assert "acme.core" in aliases
    assert "acme.core.services" in aliases
    assert "acme.core.mediator" in aliases


def test_fortran_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "fortran-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "math_utils.f90").write_text(
        "module math_utils\n"
        "implicit none\n"
        "contains\n"
        "subroutine helper()\n"
        "end subroutine helper\n"
        "end module math_utils\n",
        encoding="utf-8",
    )

    aliases = repository_service.fortran_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/math_utils.f90",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "math_utils" in aliases
    assert "math_utils.helper" in aliases
    assert "helper" in aliases


def test_d_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "d-alias-repo"
    (repo_path / "source" / "acme").mkdir(parents=True)
    (repo_path / "source" / "acme" / "util.d").write_text(
        "module acme.util;\n"
        "struct Worker {}\n"
        "void helper() {}\n",
        encoding="utf-8",
    )

    aliases = repository_service.d_language_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="source/acme/util.d",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "acme.util" in aliases
    assert "util" in aliases
    assert "Worker" in aliases
    assert "acme.util.Worker" in aliases
    assert "acme.util.helper" in aliases


def test_ada_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "ada-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "acme-util.adb").write_text(
        "package body Acme.Util is\n"
        "   procedure Helper is\n"
        "   begin\n"
        "      null;\n"
        "   end Helper;\n"
        "end Acme.Util;\n",
        encoding="utf-8",
    )

    aliases = repository_service.ada_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme-util.adb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme-util.adb" in aliases
    assert "src/acme-util" in aliases
    assert "acme.util" in aliases
    assert "util" in aliases
    assert "acme.util.helper" in aliases


def test_ada_adapter_preserves_unresolved_binding_targets_as_none() -> None:
    file_path = "src/main.adb"
    text = (
        "with Missing.Util;\n"
        "procedure Main is\n"
        "begin\n"
        "   Missing.Util.Helper;\n"
        "end Main;\n"
    )

    dependencies = repository_service.ada_adapter.parse_dependencies_only(
        file_path,
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, module_index: None,
    )
    _, _, references = repository_service.ada_adapter.parse_file(
        file_path,
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, module_index: None,
    )

    assert len(dependencies) == 1
    assert dependencies[0]["dependency_type"] == "imports"
    assert dependencies[0]["target_file"] is None
    assert references == ()


def test_assembly_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "assembly-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "boot.asm").write_text(
        "global start\n"
        "start:\n"
        "    call print_string\n"
        "    ret\n"
        "print_string:\n"
        "    ret\n",
        encoding="utf-8",
    )

    aliases = repository_service.assembly_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/boot.asm",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/boot.asm" in aliases
    assert "src/boot" in aliases
    assert "src.boot" in aliases
    assert "boot" in aliases
    assert "start" in aliases
    assert "boot.start" in aliases
    assert "print_string" in aliases


def test_prolog_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "prolog-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )

    aliases = repository_service.prolog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/family.pl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/family.pl" in aliases
    assert "src/family" in aliases
    assert "src.family" in aliases
    assert "family" in aliases
    assert "ancestor" in aliases
    assert "family.ancestor" in aliases
    assert "family:ancestor" in aliases


def test_prolog_marker_detection_ignores_empty_directives() -> None:
    assert repository_prolog_primitives.has_prolog_markers("\t\t:-\n") is False


def test_foxpro_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "foxpro-alias-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "programs" / "report.prg").write_text(
        "DEFINE CLASS JsonRunner AS Custom\n"
        "ENDDEFINE\n"
        "FUNCTION Helper()\n"
        "    RETURN 1\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )

    aliases = repository_service.foxpro_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="programs/report.prg",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "programs/report.prg" in aliases
    assert "programs/report" in aliases
    assert "programs.report" in aliases
    assert "report" in aliases
    assert "helper" in aliases
    assert "report.helper" in aliases
    assert "jsonrunner" in aliases


def test_solidity_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "solidity-alias-repo"
    (repo_path / "src" / "access").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{"name":"solidity-alias-repo"}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "access" / "Ownable.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "abstract contract Ownable {\n"
        "    function owner() public view returns (address) {}\n"
        "}\n"
        "interface IOwnable {\n"
        "    function owner() external view returns (address);\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.solidity_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/access/Ownable.sol",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/access/Ownable.sol" in aliases
    assert "src/access/Ownable" in aliases
    assert "src.access.Ownable" in aliases
    assert "access/Ownable.sol" in aliases
    assert "access/Ownable" in aliases
    assert "solidity-alias-repo/access/Ownable.sol" in aliases
    assert "Ownable" in aliases
    assert "IOwnable" in aliases
    assert "owner" in aliases


def test_systemverilog_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "systemverilog-alias-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "top.sv").write_text(
        "package util_pkg;\n"
        "endpackage\n"
        "module top;\n"
        "endmodule\n",
        encoding="utf-8",
    )

    aliases = repository_service.systemverilog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.sv",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rtl/top.sv" in aliases
    assert "rtl/top" in aliases
    assert "rtl.top" in aliases
    assert "top" in aliases
    assert "module:top" in aliases
    assert "util_pkg" in aliases
    assert "package:util_pkg" in aliases


def test_verilog_adapter_module_aliases_include_module_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "verilog-alias-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "top.v").write_text(
        "module top;\n"
        "  function helper;\n"
        "  endfunction\n"
        "endmodule\n",
        encoding="utf-8",
    )

    aliases = repository_service.verilog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.v",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rtl/top.v" in aliases
    assert "rtl/top" in aliases
    assert "rtl.top" in aliases
    assert "top" in aliases
    assert "module:top" in aliases


def test_actionscript_adapter_module_aliases_include_package_type_and_method_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "actionscript-alias-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "app" / "Main.as").write_text(
        "package demo.app {\n"
        "    public class Main {\n"
        "        public function boot():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.actionscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/app/Main.as",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/app/Main.as" in aliases
    assert "src/demo/app/Main" in aliases
    assert "src.demo.app.Main" in aliases
    assert "Main" in aliases
    assert "demo.app" in aliases
    assert "package:demo.app" in aliases
    assert "demo.app.Main" in aliases
    assert "class:Main" in aliases
    assert "class:demo.app.Main" in aliases
    assert "boot" in aliases
    assert "Main.boot" in aliases
    assert "demo.app.Main.boot" in aliases


def test_awk_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "awk-alias-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.awk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib/math.awk",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "lib/math.awk" in aliases
    assert "lib/math" in aliases
    assert "lib.math" in aliases
    assert "math" in aliases
    assert "add" in aliases
    assert "math.add" in aliases


def test_coffeescript_adapter_module_aliases_include_class_and_function_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coffeescript-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.coffee").write_text(
        "class App\n"
        "  boot: ->\n"
        "    true\n"
        "\n"
        "renderJson = ->\n"
        "  '{}'\n"
        "\n"
        "exports.compile = ->\n"
        "  true\n",
        encoding="utf-8",
    )

    aliases = repository_service.coffeescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.coffee",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/main.coffee" in aliases
    assert "src/main" in aliases
    assert "src.main" in aliases
    assert "main" in aliases
    assert "App" in aliases
    assert "boot" in aliases
    assert "renderJson" in aliases
    assert "compile" in aliases
    assert "main.boot" in aliases
    assert "main.renderJson" in aliases
    assert "main.compile" in aliases


def test_vala_adapter_module_aliases_include_namespace_type_and_method_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vala-alias-repo"
    (repo_path / "src" / "App").mkdir(parents=True)
    (repo_path / "src" / "App" / "MainWindow.vala").write_text(
        "namespace Demo.App {\n"
        "    public class MainWindow : Object {\n"
        "        public void present_window () {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.vala_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/App/MainWindow.vala",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/App/MainWindow.vala" in aliases
    assert "src/App/MainWindow" in aliases
    assert "src.app.mainwindow" in aliases
    assert "MainWindow" in aliases
    assert "demo.app" in aliases
    assert "Demo.App.MainWindow" in aliases
    assert "present_window" in aliases
    assert "Demo.App.MainWindow.present_window" in aliases


def test_mql5_adapter_module_aliases_include_type_and_function_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mql5-alias-repo"
    (repo_path / "Experts").mkdir(parents=True)
    (repo_path / "Experts" / "Main.mq5").write_text(
        "class Helper\n"
        "{\n"
        "public:\n"
        "   string RenderJson()\n"
        "     {\n"
        '      return "{}";\n'
        "     }\n"
        "};\n"
        "\n"
        "void OnStart()\n"
        "{\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.mql5_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Experts/Main.mq5",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Experts/Main.mq5" in aliases
    assert "Experts/Main" in aliases
    assert "Experts.Main" in aliases
    assert "Main" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "OnStart" in aliases
    assert "Helper.RenderJson" in aliases
    assert "Main.OnStart" in aliases


def test_gams_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "gams-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "main.gms").write_text(
        "$include ../include/common.inc\n"
        "set i /a,b/;\n"
        "parameter cost(i);\n"
        "equation balance;\n"
        "balance.. cost('a') =e= 1;\n",
        encoding="utf-8",
    )

    aliases = repository_service.gams_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/main.gms",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/main.gms" in aliases
    assert "models/main" in aliases
    assert "models.main" in aliases
    assert "main" in aliases
    assert "i" in aliases
    assert "cost" in aliases
    assert "balance" in aliases
    assert "main.balance" in aliases


def test_nix_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "nix-alias-repo"
    (repo_path / "nix").mkdir(parents=True)
    (repo_path / "nix" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "let\n"
        "  mkFormatter = package: package;\n"
        "in {\n"
        "  mkFormatter = mkFormatter;\n"
        "  formatter = mkFormatter pkgs.alejandra;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.nix_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="nix/formatter.nix",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "nix/formatter.nix" in aliases
    assert "nix/formatter" in aliases
    assert "nix.formatter" in aliases
    assert "formatter" in aliases
    assert "mkFormatter" in aliases
    assert "formatter.mkFormatter" in aliases


def test_openscad_adapter_module_aliases_include_module_and_function_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openscad-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "helpers.scad").write_text(
        "module shelf(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n"
        "function render_profile(value) = value + 1;\n",
        encoding="utf-8",
    )

    aliases = repository_service.openscad_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/helpers.scad",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/helpers.scad" in aliases
    assert "models/helpers" in aliases
    assert "models.helpers" in aliases
    assert "shelf" in aliases
    assert "render_profile" in aliases
    assert "helpers.shelf" in aliases
    assert "helpers.render_profile" in aliases


def test_purescript_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-alias-repo"
    (repo_path / "src" / "Control").mkdir(parents=True)
    (repo_path / "src" / "Control" / "Helper.purs").write_text(
        "module Control.Helper where\n"
        "\n"
        "data Helper = Helper\n"
        "\n"
        "renderJson :: String\n"
        "renderJson = \"{}\"\n",
        encoding="utf-8",
    )

    aliases = repository_service.purescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Control/Helper.purs",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Control/Helper.purs" in aliases
    assert "src/Control/Helper" in aliases
    assert "src.Control.Helper" in aliases
    assert "Control.Helper" in aliases
    assert "renderJson" in aliases
    assert "Helper" in aliases
    assert "Control.Helper.renderJson" in aliases


def test_gleam_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gleam-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub type Helper {\n  Helper\n}\n\npub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    aliases = repository_service.gleam_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/helper.gleam",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/helper.gleam" in aliases
    assert "src/demo/helper" in aliases
    assert "src.demo.helper" in aliases
    assert "demo/helper" in aliases
    assert "demo.helper" in aliases
    assert "render_json" in aliases
    assert "Helper" in aliases
    assert "demo.helper.render_json" in aliases


def test_janet_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "janet-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "init.janet").write_text(
        "(defn render-json [] @{})\n(def helper-state @{})\n",
        encoding="utf-8",
    )

    aliases = repository_service.janet_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/init.janet",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/init.janet" in aliases
    assert "src/demo/init" in aliases
    assert "src.demo.init" in aliases
    assert "init" in aliases
    assert "demo" in aliases
    assert "render-json" in aliases
    assert "helper-state" in aliases
    assert "demo/render-json" in aliases
    assert "demo.render-json" in aliases


def test_dhall_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dhall-alias-repo"
    (repo_path / "schemas" / "Step").mkdir(parents=True)
    (repo_path / "schemas" / "Step" / "package.dhall").write_text(
        "{ Type = \"step\", default = \"run\" }\n",
        encoding="utf-8",
    )

    aliases = repository_service.dhall_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="schemas/Step/package.dhall",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "schemas/Step/package.dhall" in aliases
    assert "schemas/Step/package" in aliases
    assert "schemas.Step.package" in aliases
    assert "schemas/Step" in aliases
    assert "schemas.Step" in aliases
    assert "Step" in aliases
    assert "Type" in aliases
    assert "default" in aliases
    assert "schemas/Step.Type" in aliases
    assert "schemas.Step.Type" in aliases


def test_puppet_adapter_module_aliases_include_manifest_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "puppet-alias-repo"
    (repo_path / "manifests").mkdir(parents=True)
    (repo_path / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    (repo_path / "manifests" / "params.pp").write_text(
        "class apache::params { }\n",
        encoding="utf-8",
    )

    aliases = repository_service.puppet_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="manifests/params.pp",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "manifests/params.pp" in aliases
    assert "manifests/params" in aliases
    assert "manifests::params" in aliases
    assert "params" in aliases
    assert "apache::params" in aliases
    assert "apache/params" in aliases
    assert "apache.params" in aliases


def test_coq_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coq-alias-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )

    aliases = repository_service.coq_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="theories/Helper.v",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "theories/Helper.v" in aliases
    assert "theories.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases


def test_lean_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-alias-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )

    aliases = repository_service.lean_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Batteries/Helper.lean",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Batteries/Helper.lean" in aliases
    assert "Batteries.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases


def test_rego_adapter_module_aliases_include_package_and_rule_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rego-alias-repo"
    (repo_path / "policy" / "lib").mkdir(parents=True)
    (repo_path / "policy" / "lib" / "helpers.rego").write_text(
        "package policy.lib.helpers\n\n"
        "render_json if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.rego_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="policy/lib/helpers.rego",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "policy/lib/helpers.rego" in aliases
    assert "policy/lib/helpers" in aliases
    assert "policy.lib.helpers" in aliases
    assert "policy/lib/helpers" in aliases
    assert "data.policy.lib.helpers" in aliases
    assert "render_json" in aliases
    assert "policy.lib.helpers.render_json" in aliases
    assert "data.policy.lib.helpers.render_json" in aliases


def test_yara_adapter_module_aliases_include_rule_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "yara-alias-repo"
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "rules" / "helper.yar").write_text(
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.yara_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rules/helper.yar",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rules/helper.yar" in aliases
    assert "rules/helper" in aliases
    assert "helper_rule" in aliases


