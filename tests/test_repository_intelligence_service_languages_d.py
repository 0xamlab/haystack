"""Tests for repository_intelligence_service: languages_d.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_applescript_adapter_module_aliases_include_script_and_handler_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "applescript-alias-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on RenderJson(value)\n"
        "        return value\n"
        "    end RenderJson\n"
        "end script\n",
        encoding="utf-8",
    )

    aliases = repository_service.applescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/Helper.applescript",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/Helper.applescript" in aliases
    assert "scripts/helper.applescript" in aliases
    assert "scripts/Helper" in aliases
    assert "scripts.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases
    assert "HelperScript" in aliases
    assert "helperscript" in aliases
    assert "RenderJson" in aliases
    assert "renderjson" in aliases
    assert "Helper.RenderJson" in aliases
    assert "helper.renderjson" in aliases


def test_apex_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "apex-alias-repo"
    (repo_path / "force-app" / "main" / "default" / "classes").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "classes" / "AccountTriggerHandler.cls").write_text(
        "public with sharing class AccountTriggerHandler\n"
        "{\n"
        "    public static void run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.apex_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="force-app/main/default/classes/AccountTriggerHandler.cls",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "force-app/main/default/classes/AccountTriggerHandler.cls" in aliases
    assert "force-app/main/default/classes/AccountTriggerHandler" in aliases
    assert "force-app.main.default.classes.AccountTriggerHandler" in aliases
    assert "AccountTriggerHandler" in aliases
    assert "run" in aliases
    assert "AccountTriggerHandler.run" in aliases


def test_wolfram_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "wolfram-alias-repo"
    (repo_path / "Kernel").mkdir(parents=True)
    (repo_path / "Kernel" / "Helpers.wl").write_text(
        'BeginPackage["Acme`"];\n'
        'helper::usage = "helper";\n'
        'Begin["`Private`"];\n'
        "helper[] := 1;\n"
        "End[];\n"
        "EndPackage[];\n",
        encoding="utf-8",
    )

    aliases = repository_service.wolfram_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Kernel/Helpers.wl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Kernel/Helpers.wl" in aliases
    assert "Kernel/Helpers" in aliases
    assert "Kernel.Helpers" in aliases
    assert "Helpers" in aliases
    assert "Acme`Helpers`" in aliases
    assert "helper" in aliases
    assert "Acme`helper" in aliases


def test_rpg_adapter_module_aliases_include_object_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rpg-alias-repo"
    (repo_path / "QRPGLESRC").mkdir(parents=True)
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

    aliases = repository_service.rpg_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="QRPGLESRC/ORD101.PGM.RPGLE",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "qrpglesrc/ord101.pgm.rpgle" in aliases
    assert "qrpglesrc/ord101.pgm" in aliases
    assert "qrpglesrc.ord101.pgm" in aliases
    assert "ord101.pgm" in aliases
    assert "ord101" in aliases
    assert "Updord" in aliases
    assert "updord" in aliases


def test_ml_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "ml-alias-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "util.sml").write_text(
        "structure Util = struct\n"
        "fun helper () = 1\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.ml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme/util.sml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme/util.sml" in aliases
    assert "src/acme/util" in aliases
    assert "src.acme.util" in aliases
    assert "acme.util" in aliases
    assert "util" in aliases
    assert "helper" in aliases
    assert "util.helper" in aliases


def test_classic_visual_basic_adapter_module_aliases_include_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vb6-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "cHelper.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "cHelper"\n'
        "Option Explicit\n"
        "\n"
        "Public Function Helper() As String\n"
        '    Helper = "ok"\n'
        "End Function\n",
        encoding="utf-8",
    )

    aliases = repository_service.classic_visual_basic_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/cHelper.cls",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/chelper.cls" in aliases
    assert "src/chelper" in aliases
    assert "src.chelper" in aliases
    assert "chelper" in aliases
    assert "helper" in aliases
    assert "chelper.helper" in aliases


def test_vba_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "vba-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "JsonData.cls").write_text(
        "VERSION 1.0 CLASS\n"
        'Attribute VB_Name = "JsonData"\n'
        "Option Explicit\n"
        "\n"
        "Public Function ToJson() As String\n"
        '    ToJson = "{}"\n'
        "End Function\n",
        encoding="utf-8",
    )

    aliases = repository_service.vba_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/JsonData.cls",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/jsondata.cls" in aliases
    assert "src/jsondata" in aliases
    assert "src.jsondata" in aliases
    assert "jsondata" in aliases
    assert "tojson" in aliases
    assert "jsondata.tojson" in aliases


def test_lisp_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lisp-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.lisp").write_text(
        "(defpackage #:acme.helper (:use #:cl) (:export #:helper))\n"
        "(in-package #:acme.helper)\n"
        "(defun helper () 1)\n",
        encoding="utf-8",
    )

    aliases = repository_service.lisp_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/helper.lisp",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/helper.lisp" in aliases
    assert "src/helper" in aliases
    assert "src.helper" in aliases
    assert "helper" in aliases
    assert "acme.helper" in aliases
    assert "acme.helper.helper" in aliases
    assert "acme.helper:helper" in aliases


def test_scheme_adapter_module_aliases_include_library_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scheme-alias-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "lib" / "acme" / "helper.sld").write_text(
        "(define-library (acme helper)\n"
        "  (export helper)\n"
        "  (begin\n"
        "    (define (helper) 1)))\n",
        encoding="utf-8",
    )

    aliases = repository_service.scheme_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib/acme/helper.sld",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "lib/acme/helper.sld" in aliases
    assert "lib/acme/helper" in aliases
    assert "lib.acme.helper" in aliases
    assert "helper" in aliases
    assert "acme.helper" in aliases
    assert "acme.helper.helper" in aliases


def test_cobol_adapter_module_aliases_include_program_and_paragraph_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cobol-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "MAINAPP.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. MAINAPP.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           DISPLAY 'ok'.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )

    aliases = repository_service.cobol_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/MAINAPP.cbl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/mainapp.cbl" in aliases
    assert "src/mainapp" in aliases
    assert "src.mainapp" in aliases
    assert "mainapp" in aliases
    assert "mainapp.main-para" in aliases


def test_plsql_adapter_module_aliases_include_package_and_declared_routines(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "plsql-alias-repo"
    (repo_path / "db").mkdir(parents=True)
    (repo_path / "db" / "app_util.pks").write_text(
        "create or replace package app_util as\n"
        "  procedure record_order(p_order_id in number);\n"
        "end app_util;\n"
        "/\n",
        encoding="utf-8",
    )

    aliases = repository_service.plsql_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="db/app_util.pks",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "db/app_util.pks" in aliases
    assert "db/app_util" in aliases
    assert "db.app_util" in aliases
    assert "app_util" in aliases
    assert "app_util.record_order" in aliases


def test_sas_adapter_module_aliases_include_declared_macros(tmp_path: Path) -> None:
    repo_path = tmp_path / "sas-alias-repo"
    (repo_path / "macros").mkdir(parents=True)
    (repo_path / "macros" / "quality_checks.sas").write_text(
        "%macro assert_nonempty();\n"
        "  %put validating;\n"
        "%mend assert_nonempty;\n"
        "%macro assert_positive();\n"
        "  %put validating;\n"
        "%mend assert_positive;\n",
        encoding="utf-8",
    )

    aliases = repository_service.sas_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="macros/quality_checks.sas",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "macros/quality_checks.sas" in aliases
    assert "macros/quality_checks" in aliases
    assert "macros.quality_checks" in aliases
    assert "quality_checks" in aliases
    assert "assert_nonempty" in aliases
    assert "assert_positive" in aliases


def test_abap_adapter_module_aliases_include_object_and_method_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "abap-alias-repo"
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

    aliases = repository_service.abap_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/zcl_math.clas.abap",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/zcl_math.clas.abap" in aliases
    assert "src/zcl_math.clas" in aliases
    assert "src.zcl_math.clas" in aliases
    assert "zcl_math" in aliases
    assert "zcl_math.add_one" in aliases


def test_matlab_adapter_module_aliases_include_package_and_class_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "matlab-alias-repo"
    (repo_path / "+acme" / "@pipeline").mkdir(parents=True)
    (repo_path / "+acme" / "@pipeline" / "run.m").write_text(
        "function value = run(obj)\n"
        "value = helper();\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.matlab_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="+acme/@pipeline/run.m",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "run" in aliases
    assert "acme.pipeline" in aliases
    assert "acme.pipeline.run" in aliases


def test_objective_c_adapter_module_aliases_include_declared_types_and_selectors(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "objective-c-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "ACMHelper.h").write_text(
        "#import <Foundation/Foundation.h>\n"
        "@interface ACMHelper : NSObject\n"
        "+ (void)work;\n"
        "@end\n",
        encoding="utf-8",
    )

    aliases = repository_service.objective_c_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/ACMHelper.h",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acmhelper.h" in aliases
    assert "src/acmhelper" in aliases
    assert "src.acmhelper" in aliases
    assert "acmhelper" in aliases
    assert "work" in aliases
    assert "acmhelper.work" in aliases


def test_sql_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "sql-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "customers.sql").write_text(
        "create table sales.customers as\n"
        "select 1 as id;\n",
        encoding="utf-8",
    )

    aliases = repository_service.sql_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/customers.sql",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/customers.sql" in aliases
    assert "models/customers" in aliases
    assert "models.customers" in aliases
    assert "customers" in aliases
    assert "sales.customers" in aliases


def test_tsql_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "tsql-alias-repo"
    (repo_path / "dbo" / "Stored Procedures").mkdir(parents=True)
    (repo_path / "dbo" / "Stored Procedures" / "LoadCustomers.sql").write_text(
        "create or alter procedure dbo.LoadCustomers\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    select 1 as id;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )

    aliases = repository_service.tsql_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="dbo/Stored Procedures/LoadCustomers.sql",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "dbo/stored procedures/loadcustomers.sql" in aliases
    assert "loadcustomers" in aliases
    assert "dbo.loadcustomers" in aliases


def test_puppet_adapter_parse_file_resolves_manifest_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "puppet-parse-repo"
    (repo_path / "manifests").mkdir(parents=True)
    (repo_path / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    init_path = repo_path / "manifests" / "init.pp"
    init_path.write_text(
        "class apache {\n"
        "  include apache::params\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "manifests" / "params.pp").write_text(
        "class apache::params { }\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["manifests/init.pp", "manifests/params.pp"],
        root_path=repo_path,
    )
    text = init_path.read_text(encoding="utf-8")
    dependencies = repository_service.puppet_adapter.parse_dependencies_only(
        "manifests/init.pp",
        text,
        module_index,
        root_path=repo_path,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.puppet_adapter.parse_file(
        "manifests/init.pp",
        text,
        module_index,
        root_path=repo_path,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "manifests/params.pp"
        and dependency.target_symbol == "apache::params"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "apache" for symbol in symbols)
    assert any(
        reference.target_file == "manifests/params.pp"
        and "apache::params" in reference.target_names
        for reference in references
    )


def test_hack_adapter_parse_file_resolves_imported_type_dependencies(tmp_path: Path) -> None:
    repo_path = tmp_path / "hack-parse-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Ref.php").write_text(
        "<?hh\n"
        "namespace Demo;\n"
        "\n"
        "final class Ref<T> {}\n",
        encoding="utf-8",
    )
    user_path = repo_path / "src" / "User.hack"
    user_path.write_text(
        "<?hh\n"
        "namespace Demo;\n"
        "\n"
        "use type Demo\\Ref;\n"
        "\n"
        "final class User {\n"
        "  public function make(): Ref<int> {\n"
        "    return new Ref();\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/Ref.php", "src/User.hack"],
        root_path=repo_path,
    )
    text = user_path.read_text(encoding="utf-8")
    dependencies = repository_service.hack_adapter.parse_dependencies_only(
        "src/User.hack",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.hack_adapter.parse_file(
        "src/User.hack",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/Ref.php" and dependency.target_symbol == "Ref"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "User" for symbol in symbols)
    assert any(
        reference.target_file == "src/Ref.php" and "Ref" in reference.target_names
        for reference in references
    )


def test_odin_adapter_parse_file_resolves_import_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-parse-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "src" / "common" / "helper.odin").write_text(
        "package common\n"
        "\n"
        "helper :: proc() -> int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    main_path = repo_path / "src" / "main.odin"
    main_path.write_text(
        "package main\n"
        "\n"
        'import "src:common"\n'
        "\n"
        "run :: proc() -> int {\n"
        "    return common.helper()\n"
        "}\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["src/common/helper.odin", "src/main.odin"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.odin_adapter.parse_dependencies_only(
        "src/main.odin",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.odin_adapter.parse_file(
        "src/main.odin",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "src/common/helper.odin"
        and dependency.target_symbol == "common"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "src/common/helper.odin"
        and "helper" in reference.target_names
        for reference in references
    )


def test_factor_adapter_parse_file_resolves_using_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "factor-parse-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )
    main_path = repo_path / "app" / "main.factor"
    main_path.write_text(
        "USING: math ;\n"
        "IN: app.main\n\n"
        ": run ( n -- n ) square ;\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["app/main.factor", "math/math.factor"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.factor_adapter.parse_dependencies_only(
        "app/main.factor",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.factor_adapter.parse_file(
        "app/main.factor",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "math/math.factor"
        and dependency.target_symbol == "math"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "math/math.factor"
        and "square" in reference.target_names
        for reference in references
    )


def test_cue_adapter_parse_file_resolves_module_dependencies_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cue-parse-repo"
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
    main_path = repo_path / "main.cue"
    main_path.write_text(
        'package main\n\nimport schema "example.com/demo/pkg/schema"\n\nvalue: schema.#Answer\n',
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["main.cue", "pkg/schema/schema.cue"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.cue_adapter.parse_dependencies_only(
        "main.cue",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
        root_path=repo_path,
    )
    symbols, _, references = repository_service.cue_adapter.parse_file(
        "main.cue",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
        root_path=repo_path,
    )

    assert any(
        dependency.target_file == "pkg/schema/schema.cue"
        and dependency.target_symbol == "example.com/demo/pkg/schema"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "value" for symbol in symbols)
    assert any(
        reference.target_file == "pkg/schema/schema.cue"
        and "#Answer" in reference.target_names
        for reference in references
    )


