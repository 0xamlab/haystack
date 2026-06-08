"""Tests for repository_intelligence_real_repo_probe: connected_dependency_g.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_connected_dependency_map_follows_awk_include_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "awk-connected-map-repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "translate").write_text(
        "#!/usr/bin/env gawk -f\n"
        '@include "../lib/math.awk"\n'
        "BEGIN {\n"
        "    print add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["bin/translate"],
        bridge_paths=["bin", "lib"],
        include_patterns=["bin/translate", "lib/*.awk", "**/*.awk", "*.awk"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "bin/translate",
        "lib/math.awk",
    ]


def test_connected_dependency_map_follows_coffeescript_require_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "coffeescript-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.coffee").write_text(
        "renderJson = (value) ->\n"
        "  value\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.coffee").write_text(
        "helper = require './helper'\n"
        "run = ->\n"
        "  helper.renderJson '{}'\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.coffee"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.coffee", "src/*.coffee", "*.coffee", "Cakefile"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/helper.coffee",
        "src/main.coffee",
    ]


def test_connected_dependency_map_follows_elm_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "elm-connected-map-repo"
    (repo_path / "src" / "Page").mkdir(parents=True)
    (repo_path / "src" / "Page" / "Home.elm").write_text(
        "module Page.Home exposing (homeView)\n\n"
        "homeView : String\n"
        "homeView =\n"
        "    \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.elm").write_text(
        "module Main exposing (main)\n\n"
        "import Page.Home exposing (homeView)\n\n"
        "main : String\n"
        "main =\n"
        "    homeView\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.elm"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.elm", "src/*.elm", "elm.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/Main.elm",
        "src/Page/Home.elm",
    ]


def test_connected_dependency_map_follows_powershell_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "powershell-connected-map-repo"
    (repo_path / "Private").mkdir(parents=True)
    (repo_path / "Private" / "Helpers.ps1").write_text(
        "function Get-Helper {\n"
        "  return 'ok'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Module.psm1").write_text(
        '. "$PSScriptRoot/Private/Helpers.ps1"\n'
        "function Invoke-Main {\n"
        "  Get-Helper\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["Module.psm1"],
        bridge_paths=["Private", "Module.psm1"],
        include_patterns=["*.psm1", "Private/*.ps1", "*.psd1"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "Module.psm1",
        "Private/Helpers.ps1",
    ]


def test_connected_dependency_map_follows_erlang_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "erlang-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "acme_util.erl").write_text(
        "-module(acme_util).\n-export([helper/0]).\nhelper() -> ok.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.erl").write_text(
        "-module(acme).\n-export([run/0]).\nrun() -> acme_util:helper().\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme.erl"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.erl", "src/**/*.hrl", "rebar.config"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme.erl",
        "src/acme_util.erl",
    ]


def test_connected_dependency_map_follows_nim_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "nim-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*(): string =\n"
        "  \"ok\"\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.nim").write_text(
        "import acme/util\n"
        "proc run*(): string =\n"
        "  util.helper()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme.nim"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.nim", "*.nimble", "config.nims"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme.nim",
        "src/acme/util.nim",
    ]


def test_connected_dependency_map_follows_ocaml_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "ocaml-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "util.ml").write_text(
        "let helper () = 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.ml").write_text(
        "let run () = Util.helper ()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.ml"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.ml", "src/*.ml", "dune-project", "**/dune", "*.opam"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/main.ml",
        "src/util.ml",
    ]


def test_connected_dependency_map_follows_perl_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "perl-connected-map-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\nsub helper { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\nuse My::Util;\nsub run { My::Util->helper() }\n1;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lib/My/Main.pm"],
        bridge_paths=["lib"],
        include_patterns=["lib/**/*.pm", "lib/*.pm", "cpanfile", "Makefile.PL", "Build.PL"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "lib/My/Main.pm",
        "lib/My/Util.pm",
    ]


def test_connected_dependency_map_follows_perl_imported_call_and_parent_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "perl-imported-call-connected-map-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "lib" / "My" / "Base.pm").write_text(
        "package My::Base;\nsub parent_method { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\nsub helper { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\nuse parent 'My::Base';\nuse My::Util qw(helper);\nsub run { helper() }\n1;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lib/My/Main.pm"],
        bridge_paths=["lib"],
        include_patterns=["lib/**/*.pm", "lib/*.pm", "cpanfile", "Makefile.PL", "Build.PL"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "lib/My/Base.pm",
        "lib/My/Main.pm",
        "lib/My/Util.pm",
    ]


def test_connected_dependency_map_follows_r_source_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "r-connected-map-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function() {\n  1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        'source("helper.R")\n'
        "run <- function() {\n"
        "  helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["R/main.R"],
        bridge_paths=["R"],
        include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "R/helper.R",
        "R/main.R",
    ]


def test_connected_dependency_map_follows_r_package_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "r-package-symbol-connected-map-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function() {\n  1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        "run <- function() {\n"
        "  helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["R/main.R"],
        bridge_paths=["R"],
        include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "R/helper.R",
        "R/main.R",
    ]


def test_connected_dependency_map_ignores_r_builtin_collisions_for_package_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "r-package-builtin-connected-map-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "builtin-shadow.R").write_text(
        "names <- function(x) {\n"
        "  x\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function(x) {\n"
        "  x\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        "run <- function(x) {\n"
        "  names(x)\n"
        "  helper(x)\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["R/main.R"],
        bridge_paths=["R"],
        include_patterns=["R/**/*.R", "R/*.R", "DESCRIPTION", "NAMESPACE"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "R/helper.R",
        "R/main.R",
    ]


def test_connected_dependency_map_follows_julia_include_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "julia-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.jl").write_text(
        "module Helper\nhelper() = 1\nend\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Helper.jl")\nusing .Helper: helper\n'
        "run() = helper()\nend\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Acme.jl"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.jl", "src/*.jl", "Project.toml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/Acme.jl",
        "src/Helper.jl",
    ]


def test_connected_dependency_map_follows_crystal_wildcard_requires(tmp_path: Path) -> None:
    repo_path = tmp_path / "crystal-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.cr").write_text(
        'require "./acme/*"\nmodule Acme\nend\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "helper.cr").write_text(
        "module Acme::Helper\n"
        "  def self.helper : Int32\n"
        "    1\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme.cr"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme.cr",
        "src/acme/helper.cr",
    ]


def test_connected_dependency_map_follows_crystal_type_annotation_and_mixin_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "crystal-type-annotation-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\nversion: 0.1.0\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "base_runner.cr").write_text(
        "module Acme\n"
        "  class BaseRunner\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "serializable.cr").write_text(
        "module Acme\n"
        "  module Serializable\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "options.cr").write_text(
        "module Acme\n"
        "  class Options\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "runner.cr").write_text(
        "module Acme\n"
        "  class Runner < BaseRunner\n"
        "    include Serializable\n"
        "    def initialize(options : Options)\n"
        "    end\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme/runner.cr"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.cr", "src/*.cr", "shard.yml"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 4
    assert connected_map["resolved_dependency_edges"] >= 3
    assert connected_map["connected_files"] == [
        "src/acme/base_runner.cr",
        "src/acme/options.cr",
        "src/acme/runner.cr",
        "src/acme/serializable.cr",
    ]


def test_connected_dependency_map_uses_precomputed_candidate_files_for_dart_workspace_packages(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-workspace-packages-repo"
    (repo_path / "pkgs" / "app" / "lib").mkdir(parents=True)
    (repo_path / "pkgs" / "http" / "lib" / "src").mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "pubspec.yaml").write_text(
        "name: http\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "src" / "base.dart").write_text(
        "class Client {\n"
        "  String ping() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "http.dart").write_text(
        "export 'src/base.dart' show Client;\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "app" / "lib" / "app.dart").write_text(
        "import 'package:http/http.dart' show Client;\n\n"
        "String run() => Client().ping();\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["pkgs/app/lib/app.dart"],
        bridge_paths=["pkgs/app/lib"],
        candidate_file_paths=[
            "pkgs/app/lib/app.dart",
            "pkgs/http/lib/http.dart",
            "pkgs/http/lib/src/base.dart",
        ],
        include_patterns=["pkgs/**/*.dart"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "pkgs/app/lib/app.dart",
        "pkgs/http/lib/http.dart",
        "pkgs/http/lib/src/base.dart",
    ]


def test_connected_dependency_map_follows_cpp_include_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "cpp-workspace-repo"
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme" / "core.hpp").write_text("#pragma once\n", encoding="utf-8")
    (repo_path / "src" / "format.hpp").write_text(
        '#include "acme/core.hpp"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cpp").write_text(
        '#include "format.hpp"\n',
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.cpp"],
        bridge_paths=["src", "include"],
        include_patterns=["src/**/*.cpp", "src/**/*.hpp", "include/**/*.hpp"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "include/acme/core.hpp",
        "src/format.hpp",
        "src/main.cpp",
    ]


def test_connected_dependency_map_follows_mojo_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "mojo-workspace-repo"
    (repo_path / "helper").mkdir(parents=True)
    (repo_path / "helper" / "util.mojo").write_text(
        "fn value():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (repo_path / "main.mojo").write_text(
        "import helper.util\n\n"
        "fn run():\n"
        "    return util.value()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.mojo"],
        bridge_paths=["."],
        include_patterns=["*.mojo", "**/*.mojo"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper/util.mojo",
        "main.mojo",
    ]


