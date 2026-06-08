"""Tests for repository_intelligence_real_repo_probe: connected_dependency_e.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_connected_dependency_map_follows_stan_include_and_call_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "stan-connected-map-repo"
    (repo_path / "models" / "lib").mkdir(parents=True)
    (repo_path / "models" / "lib" / "math.stan").write_text(
        "functions {\n"
        "  real add_one(real x) {\n"
        "    return x + 1;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "main.stan").write_text(
        '#include "lib/math.stan"\n'
        "\n"
        "functions {\n"
        "  real run(real x) {\n"
        "    return add_one(x);\n"
        "  }\n"
        "}\n"
        "data {\n"
        "  real x;\n"
        "}\n"
        "model {\n"
        "  target += run(x);\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["models/main.stan"],
        bridge_paths=["models"],
        include_patterns=["models/**/*.stan", "models/*.stan"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert "models/main.stan" in connected_map["connected_files"]
    assert "models/lib/math.stan" in connected_map["connected_files"]
    assert connected_map["resolved_dependency_edges"] >= 1


def test_connected_dependency_map_follows_v_import_and_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "v-connected-map-repo"
    (repo_path / "src" / "helper").mkdir(parents=True)
    (repo_path / "main.v").write_text(
        "module main\n"
        "\n"
        "import helper\n"
        "\n"
        "fn run() {\n"
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.v"],
        bridge_paths=["src/helper"],
        include_patterns=["**/*.v", "*.v", "v.mod"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "main.v",
        "src/helper/helper.v",
    }


def test_connected_dependency_map_follows_smalltalk_class_message_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "smalltalk-connected-map-repo"
    (repo_path / "src" / "Demo-App").mkdir(parents=True)
    (repo_path / "src" / "Demo-Core").mkdir(parents=True)
    (repo_path / ".smalltalk.ston").write_text("{ }\n", encoding="utf-8")
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
        "}\n"
        "\n"
        "{ #category : 'rendering' }\n"
        "Helper class >> renderJson [\n"
        "\t^ '{}'\n"
        "]\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-App" / "package.st").write_text(
        "Package { #name : 'Demo-App' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo-App" / "Main.class.st").write_text(
        "Class {\n"
        "\t#name : 'Main',\n"
        "\t#superclass : 'Object',\n"
        "\t#category : 'Demo-App',\n"
        "\t#package : 'Demo-App'\n"
        "}\n"
        "\n"
        "{ #category : 'running' }\n"
        "Main >> run [\n"
        "\t^ Helper renderJson\n"
        "]\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Demo-App/Main.class.st"],
        bridge_paths=["src"],
        include_patterns=["**/*.st", "*.st", "**/*.ston", "*.ston"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Demo-App/Main.class.st",
        "src/Demo-Core/Helper.class.st",
    }


def test_connected_dependency_map_follows_visual_basic_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "visual-basic-connected-map-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "Acme.vbproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme" / "Mediator.vb").write_text(
        "Namespace Acme\n"
        "Public Class Mediator\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme" / "Handler.vb").write_text(
        "Imports Acme.Mediator\n"
        "Namespace Acme\n"
        "Public Class Handler\n"
        "    Private ReadOnly _mediator As Mediator = New Mediator()\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Acme/Handler.vb"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.vb", "src/*.vb", "*.vbproj"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/Acme/Handler.vb",
        "src/Acme/Mediator.vb",
    ]


def test_connected_dependency_map_follows_vbscript_wsf_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "vbscript-connected-map-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "helper.vbs").write_text(
        "Class Helper\n"
        "    Public Sub Run()\n"
        "    End Sub\n"
        "End Class\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.wsf").write_text(
        "<job>\n"
        '  <script language="VBScript" src="lib/helper.vbs"></script>\n'
        '  <script language="VBScript">\n'
        "    Option Explicit\n"
        "    Sub Main()\n"
        "        Dim helper\n"
        "        Set helper = New Helper\n"
        "        helper.Run()\n"
        "    End Sub\n"
        "  </script>\n"
        "</job>\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/main.wsf"],
        bridge_paths=["scripts"],
        include_patterns=["scripts/**/*.vbs", "scripts/**/*.wsf", "scripts/*.vbs", "scripts/*.wsf"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "scripts/lib/helper.vbs",
        "scripts/main.wsf",
    ]


def test_connected_dependency_map_follows_applescript_load_script_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "applescript-connected-map-repo"
    (repo_path / "scripts" / "lib").mkdir(parents=True)
    (repo_path / "scripts" / "lib" / "Helper.applescript").write_text(
        "script HelperScript\n"
        "    on RenderJson(value)\n"
        "        return value\n"
        "    end RenderJson\n"
        "end script\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "Main.applescript").write_text(
        'property helperScript : load script POSIX file "lib/Helper.applescript"\n'
        "on run\n"
        "    helperScript's RenderJson(\"{}\")\n"
        "end run\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/Main.applescript"],
        bridge_paths=["scripts"],
        include_patterns=[
            "scripts/**/*.applescript",
            "scripts/*.applescript",
            "scripts/**/*.scpt",
            "scripts/*.scpt",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "scripts/Main.applescript",
        "scripts/lib/Helper.applescript",
    ] or connected_map["connected_files"] == [
        "scripts/lib/Helper.applescript",
        "scripts/Main.applescript",
    ]


def test_connected_dependency_map_follows_cfml_include_and_component_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cfml-connected-map-repo"
    (repo_path / "config").mkdir(parents=True)
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "config" / "app.cfm").write_text(
        "<cfset request.ready = true />\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "UserService.cfc").write_text(
        "component {\n"
        "    function run() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Application.cfc").write_text(
        "component {\n"
        '    include "config/app.cfm";\n'
        "    function onApplicationStart() {\n"
        "        local.userService = new models.UserService();\n"
        "        local.userService.run();\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Application.cfc"],
        bridge_paths=["config", "models"],
        include_patterns=["**/*.cfc", "*.cfc", "**/*.cfm", "*.cfm"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert "Application.cfc" in connected_map["connected_files"]
    assert "config/app.cfm" in connected_map["connected_files"]
    assert "models/UserService.cfc" in connected_map["connected_files"]


def test_connected_dependency_map_follows_apex_trigger_and_handler_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "apex-connected-map-repo"
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
        / "triggers"
        / "AccountTrigger.trigger"
    ).write_text(
        "trigger AccountTrigger on Account (before insert) {\n"
        "    AccountTriggerHandler.run();\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["force-app/main/default/triggers/AccountTrigger.trigger"],
        bridge_paths=["force-app/main/default"],
        include_patterns=["force-app/**/*.cls", "force-app/**/*.trigger", "sfdx-project.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "force-app/main/default/classes/AccountTriggerHandler.cls",
        "force-app/main/default/triggers/AccountTrigger.trigger",
    ]


def test_connected_dependency_map_follows_wolfram_get_and_needs_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "wolfram-connected-map-repo"
    (repo_path / "Kernel").mkdir(parents=True)
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

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Kernel/init.m"],
        bridge_paths=["Kernel"],
        include_patterns=["Kernel/**/*.wl", "Kernel/**/*.m", "PacletInfo.wl"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "Kernel/Helpers.wl",
        "Kernel/Main.wl",
        "Kernel/init.m",
    ]


def test_connected_dependency_map_follows_sql_relation_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "sql-connected-map-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "dbt_project.yml").write_text(
        "name: acme\n"
        "model-paths:\n"
        "  - models\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "customers.sql").write_text(
        "create table customers as\n"
        "select 1 as id;\n",
        encoding="utf-8",
    )
    (repo_path / "models" / "orders.sql").write_text(
        "create view orders as\n"
        "select * from customers;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["models/orders.sql"],
        bridge_paths=["models"],
        include_patterns=["models/**/*.sql", "models/*.sql", "dbt_project.yml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "models/orders.sql",
        "models/customers.sql",
    }


def test_connected_dependency_map_follows_tsql_execute_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "tsql-connected-map-repo"
    (repo_path / "database" / "dbo" / "Stored Procedures").mkdir(parents=True)
    (repo_path / "database" / "Acme.sqlproj").write_text(
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <Build Include="dbo\\Stored Procedures\\LoadCustomers.sql" />\n'
        '    <Build Include="dbo\\Stored Procedures\\LoadOrders.sql" />\n'
        "  </ItemGroup>\n"
        "</Project>\n",
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
    (repo_path / "database" / "dbo" / "Stored Procedures" / "LoadOrders.sql").write_text(
        "create or alter procedure dbo.LoadOrders\n"
        "as\n"
        "begin\n"
        "    set nocount on;\n"
        "    exec dbo.LoadCustomers;\n"
        "end\n"
        "go\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["database/dbo/Stored Procedures/LoadOrders.sql"],
        bridge_paths=["database/dbo/Stored Procedures"],
        include_patterns=["database/**/*.sql", "database/*.sql", "database/*.sqlproj"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "database/dbo/Stored Procedures/LoadOrders.sql",
        "database/dbo/Stored Procedures/LoadCustomers.sql",
    }


def test_connected_dependency_map_follows_ruby_require_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ruby-connected-map-repo"
    (repo_path / "lib" / "jekyll").mkdir(parents=True)
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "lib" / "jekyll.rb").write_text(
        'require "jekyll/cache"\n'
        "module Jekyll\n"
        "  def self.run\n"
        "    Jekyll::Cache.helper\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "jekyll" / "cache.rb").write_text(
        "module Jekyll\n"
        "  class Cache\n"
        "    def self.helper\n"
        "      1\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lib/jekyll.rb"],
        bridge_paths=["lib"],
        include_patterns=["lib/*.rb", "lib/**/*.rb", "Gemfile"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "lib/jekyll.rb",
        "lib/jekyll/cache.rb",
    ]


def test_connected_dependency_map_follows_ruby_new_inheritance_and_mixin_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ruby-structure-connected-map-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "lib" / "acme" / "base_runner.rb").write_text(
        "module Acme\n"
        "  class BaseRunner\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "serializable.rb").write_text(
        "module Acme\n"
        "  module Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme" / "runner.rb").write_text(
        'require "acme/base_runner"\n'
        'require "acme/serializable"\n'
        "module Acme\n"
        "  class Runner < BaseRunner\n"
        "    include Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.rb").write_text(
        'require "acme/runner"\n'
        "module Acme\n"
        "  def self.build\n"
        "    Runner.new\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lib/acme.rb"],
        bridge_paths=["lib"],
        include_patterns=["lib/*.rb", "lib/**/*.rb", "Gemfile"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 4
    assert connected_map["resolved_dependency_edges"] >= 3
    assert connected_map["connected_files"] == [
        "lib/acme.rb",
        "lib/acme/base_runner.rb",
        "lib/acme/runner.rb",
        "lib/acme/serializable.rb",
    ]


def test_connected_dependency_map_follows_php_trait_docblock_and_type_hint_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "php-connected-map-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "app" / "Traits").mkdir(parents=True)
    (repo_path / "database" / "Factories").mkdir(parents=True)
    (repo_path / "app" / "Models" / "User.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "class User {}\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "Traits" / "HasAudit.php").write_text(
        "<?php\n"
        "namespace App\\Traits;\n"
        "trait HasAudit {}\n",
        encoding="utf-8",
    )
    (repo_path / "database" / "Factories" / "UserFactory.php").write_text(
        "<?php\n"
        "namespace Database\\Factories;\n"
        "class UserFactory {}\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "Models" / "AuditedUser.php").write_text(
        "<?php\n"
        "namespace App\\Models;\n"
        "use App\\Traits\\HasAudit;\n"
        "use Database\\Factories\\UserFactory;\n"
        "/** @use HasAudit<UserFactory> */\n"
        "class AuditedUser extends User {\n"
        "    use HasAudit;\n"
        "    public function __construct(private UserFactory $factory) {}\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["app/Models/AuditedUser.php"],
        bridge_paths=["app", "database"],
        include_patterns=["app/**/*.php", "database/**/*.php"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 4
    assert connected_map["resolved_dependency_edges"] >= 3
    assert connected_map["connected_files"] == [
        "app/Models/AuditedUser.php",
        "app/Models/User.php",
        "app/Traits/HasAudit.php",
        "database/Factories/UserFactory.php",
    ]


def test_connected_dependency_map_uses_profile_support_roots_without_reverse_bridging(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "frontend-support-roots-repo"
    (repo_path / "src" / "pages").mkdir(parents=True)
    (repo_path / "src" / "lib").mkdir(parents=True)
    (repo_path / "src" / "types").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{\n'
        '  "name": "frontend-profile",\n'
        '  "scripts": { "dev": "vite", "build": "vite build" }\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "tsconfig.app.json").write_text(
        '{\n'
        '  "compilerOptions": {\n'
        '    "baseUrl": ".",\n'
        '    "paths": { "@/*": ["./src/*"] }\n'
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "lib" / "utils.ts").write_text(
        "export const cn = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "types" / "quote.ts").write_text(
        "export interface Quote { id: string }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "pages" / "Index.tsx").write_text(
        "import type { Quote } from '@/types/quote';\n"
        "import { cn } from '@/lib/utils';\n"
        "export const Index = (): Quote => ({ id: cn() });\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "App.tsx").write_text(
        "import { Index } from './pages/Index';\n"
        "export const App = () => Index();\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.tsx").write_text(
        "import { App } from './App';\n"
        "export const bootstrap = () => App();\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )
    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=list(seed_plan["entrypoint_files"]),
        bridge_paths=[],
        candidate_scope_paths=list(seed_plan["support_roots"]),
        enable_reverse_bridging=False,
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["bridged_importer_count"] == 0
    assert "src/lib/utils.ts" in connected_map["connected_files"]
    assert "src/types/quote.ts" in connected_map["connected_files"]


