"""Tests for repository_intelligence_real_repo_probe: operational_seed_b.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_plan_without_diagnostics_uses_root_package_dir_for_nimble_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nimble-root-package-repo"
    (repo_path / "acme" / "private").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "acme.nim").write_text("proc run*() = discard\n", encoding="utf-8")
    (repo_path / "acme" / "routing.nim").write_text(
        "proc route*() = discard\n",
        encoding="utf-8",
    )
    (repo_path / "acme" / "private" / "util.nim").write_text(
        "proc helper*() = discard\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "suite.nim").write_text("discard\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nim"]
    assert "acme.nimble" in seed_plan["config_paths"]
    assert "acme" in seed_plan["support_roots"]
    assert "acme.nim" in seed_plan["entrypoint_files"]
    assert "acme/routing.nim" in seed_plan["entrypoint_files"]
    assert "acme/private/util.nim" in seed_plan["entrypoint_files"]
    assert "tests/suite.nim" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_config_nims_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nim-config-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "config.nims").write_text("switch(\"opt\", \"speed\")\n", encoding="utf-8")
    (repo_path / "src" / "acme.nim").write_text("proc run*() = discard\n", encoding="utf-8")
    (repo_path / "tests" / "suite.nim").write_text("discard\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nim"]
    assert "config.nims" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.nim" in seed_plan["entrypoint_files"]
    assert "tests/suite.nim" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_ignores_nested_non_operational_nim_configs(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nim-nested-config-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "acme.nimble").write_text("version = \"0.1.0\"\n", encoding="utf-8")
    (repo_path / "tests" / "config.nims").write_text(
        "switch(\"warning\", \"off\")\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.nim").write_text("proc run*() = discard\n", encoding="utf-8")
    (repo_path / "src" / "acme" / "util.nim").write_text(
        "proc helper*() = discard\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "example.nim").write_text("discard\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "nim" in seed_plan["detected_ecosystems"]
    assert "acme.nimble" in seed_plan["config_paths"]
    assert "tests/config.nims" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "tests" not in seed_plan["support_roots"]
    assert "src/acme.nim" in seed_plan["entrypoint_files"]
    assert "tests/example.nim" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_dune_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ocaml-dune-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "dune-project").write_text("(lang dune 3.0)\n", encoding="utf-8")
    (repo_path / "src" / "dune").write_text("(library (name acme))\n", encoding="utf-8")
    (repo_path / "src" / "main.ml").write_text("let run () = Util.helper ()\n", encoding="utf-8")
    (repo_path / "src" / "util.ml").write_text("let helper () = 1\n", encoding="utf-8")
    (repo_path / "test" / "dune").write_text("(test (name main))\n", encoding="utf-8")
    (repo_path / "test" / "main.ml").write_text("let () = ()\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ocaml"]
    assert "dune-project" in seed_plan["config_paths"]
    assert "src/dune" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "test" not in seed_plan["support_roots"]
    assert "src/main.ml" in seed_plan["entrypoint_files"]
    assert "src/util.ml" in seed_plan["entrypoint_files"]
    assert "test/main.ml" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_opam_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ocaml-opam-profile-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "acme.opam").write_text("opam-version: \"2.0\"\n", encoding="utf-8")
    (repo_path / "lib" / "acme.ml").write_text("let run () = Util.helper ()\n", encoding="utf-8")
    (repo_path / "lib" / "util.ml").write_text("let helper () = 1\n", encoding="utf-8")
    (repo_path / "test" / "acme_test.ml").write_text("let () = ()\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ocaml"]
    assert "acme.opam" in seed_plan["config_paths"]
    assert any(root in seed_plan["support_roots"] for root in {"lib", "lib/Demo"})
    assert "lib/acme.ml" in seed_plan["entrypoint_files"]
    assert "lib/util.ml" in seed_plan["candidate_file_paths"]
    assert "test/acme_test.ml" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_inferrs_manifestless_ocaml_ecosystem(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "manifestless-ocaml-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "src" / "main.ml").write_text("let run () = Util.helper ()\n", encoding="utf-8")
    (repo_path / "src" / "util.ml").write_text("let helper () = 1\n", encoding="utf-8")
    (repo_path / "test" / "main.ml").write_text("let () = ()\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ocaml"]
    assert "src/main.ml" in seed_plan["entrypoint_files"]
    assert "test/main.ml" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_cpanfile_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "perl-cpanfile-profile-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "t").mkdir(parents=True)
    (repo_path / "cpanfile").write_text("requires 'strict';\n", encoding="utf-8")
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\nsub run { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "My" / "Util.pm").write_text(
        "package My::Util;\nsub helper { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "t" / "main.t").write_text("use Test::More;\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["perl"]
    assert "cpanfile" in seed_plan["config_paths"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/My/Main.pm" in seed_plan["entrypoint_files"]
    assert "lib/My/Util.pm" in seed_plan["candidate_file_paths"]
    assert "t/main.t" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_makefile_pl_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "perl-makefile-pl-profile-repo"
    (repo_path / "lib" / "My").mkdir(parents=True)
    (repo_path / "script").mkdir(parents=True)
    (repo_path / "Makefile.PL").write_text("use ExtUtils::MakeMaker;\n", encoding="utf-8")
    (repo_path / "lib" / "My" / "Main.pm").write_text(
        "package My::Main;\nsub run { 1 }\n1;\n",
        encoding="utf-8",
    )
    (repo_path / "script" / "app.pl").write_text(
        "use My::Main;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["perl"]
    assert "Makefile.PL" in seed_plan["config_paths"]
    assert "lib" in seed_plan["support_roots"]
    assert "script" in seed_plan["support_roots"]
    assert "lib/My/Main.pm" in seed_plan["entrypoint_files"]
    assert "script/app.pl" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_detects_manifestless_prolog_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "prolog-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.pl").write_text(
        ":- module(main, [run/0]).\n"
        ":- use_module('family.pl', [ancestor/2]).\n"
        "run :- ancestor(alice, bob).\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main_test.pl").write_text(
        ":- module(main_test, [run_test/0]).\n"
        "run_test :- true.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["prolog"]
    assert "src/main.pl" in seed_plan["entrypoint_files"]
    assert "src/family.pl" in seed_plan["candidate_file_paths"]
    assert "tests/main_test.pl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_mlb_profile(tmp_path: Path) -> None:
    repo_path = tmp_path / "ml-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
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
    (repo_path / "tests" / "MainTest.sml").write_text(
        "structure MainTest = struct\n"
        "val run = 0\n"
        "end\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["ml"]
    assert "project.mlb" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.sml" in seed_plan["entrypoint_files"]
    assert "src/Util.sml" in seed_plan["candidate_file_paths"]
    assert "tests/MainTest.sml" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_r_description_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "r-description-profile-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "tests" / "testthat").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    (repo_path / "R" / "main.R").write_text(
        "run <- function() {\n  helper()\n}\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "helper.R").write_text(
        "helper <- function() {\n  1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "testthat" / "test-main.R").write_text(
        "test_that('run works', { expect_true(TRUE) })\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["r"]
    assert "DESCRIPTION" in seed_plan["config_paths"]
    assert "NAMESPACE" in seed_plan["config_paths"]
    assert "R" in seed_plan["support_roots"]
    assert "R/main.R" in seed_plan["entrypoint_files"]
    assert "R/helper.R" in seed_plan["candidate_file_paths"]
    assert "tests/testthat/test-main.R" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_primary_r_code_over_auxiliary_tooling(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "r-primary-with-tooling-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "inst" / "www" / "shared" / "bootstrap" / "js").mkdir(parents=True)
    (repo_path / "srcts" / "types" / "extras").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "NAMESPACE").write_text("export(run)\n", encoding="utf-8")
    for index in range(10):
        (repo_path / "R" / f"module_{index}.R").write_text(
            f"module_{index} <- function() {{\n  {index}\n}}\n",
            encoding="utf-8",
        )
    (repo_path / "package.json").write_text(
        json.dumps(
            {
                "name": "@acme/pkg",
                "types": "srcts/types/extras/global.d.ts",
                "scripts": {
                    "build": "tsx srcts/build/index.ts",
                },
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "tsconfig.json").write_text(
        json.dumps(
            {
                "include": [
                    "srcts/src/**/*.ts",
                    "srcts/build/*.ts",
                ]
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "inst" / "www" / "shared" / "bootstrap" / "js" / "bootstrap.js").write_text(
        "window.bootstrap = true;\n",
        encoding="utf-8",
    )
    (repo_path / "srcts" / "types" / "extras" / "global.d.ts").write_text(
        "declare global {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "r" in seed_plan["detected_ecosystems"]
    assert "node" in seed_plan["detected_ecosystems"]
    assert "typescript" in seed_plan["detected_ecosystems"]
    assert seed_plan["entrypoint_files"]
    assert all(path.startswith("R/") for path in seed_plan["entrypoint_files"])
    assert "srcts/types/extras/global.d.ts" not in seed_plan["entrypoint_files"]
    assert "inst/www/shared/bootstrap/js/bootstrap.js" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_julia_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "julia-project-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "Project.toml").write_text(
        'name = "Acme"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (repo_path / "Manifest.toml").write_text("# generated\n", encoding="utf-8")
    (repo_path / "src" / "Acme.jl").write_text(
        'module Acme\ninclude("Helper.jl")\nend\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.jl").write_text("helper() = 1\n", encoding="utf-8")
    (repo_path / "test" / "runtests.jl").write_text("using Test\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["julia"]
    assert "Project.toml" in seed_plan["config_paths"]
    assert "Manifest.toml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Acme.jl" in seed_plan["entrypoint_files"]
    assert "src/Helper.jl" in seed_plan["candidate_file_paths"]
    assert "test/runtests.jl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_shard_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "crystal-shard-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "spec").mkdir(parents=True)
    (repo_path / "shard.yml").write_text(
        "name: acme\n"
        "version: 0.1.0\n"
        "targets:\n"
        "  acme:\n"
        "    main: src/acme.cr\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme.cr").write_text(
        'require "./acme/*"\nmodule Acme\nend\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "helper.cr").write_text(
        "module Acme::Helper\nend\n",
        encoding="utf-8",
    )
    (repo_path / "spec" / "acme_spec.cr").write_text(
        "describe Acme do\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src", "shard.yml"],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["crystal"]
    assert "shard.yml" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/acme.cr" in seed_plan["entrypoint_files"]
    assert "src/acme/helper.cr" in seed_plan["candidate_file_paths"]
    assert "spec/acme_spec.cr" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_discovers_nested_pubspec_workspace_profiles(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-workspace-profile-repo"
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
    (repo_path / "pkgs" / "app" / "lib" / "app.dart").write_text(
        "import 'package:http/http.dart' show Client;\n\n"
        "String run() => Client().ping();\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "http.dart").write_text(
        "export 'src/client.dart' show Client;\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "src" / "client.dart").write_text(
        "class Client {\n"
        "  String ping() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=256,
    )

    assert seed_plan["detected_ecosystems"] == ["dart"]
    assert "pkgs/app/pubspec.yaml" in seed_plan["config_paths"]
    assert "pkgs/http/pubspec.yaml" in seed_plan["config_paths"]
    assert "pkgs/http/lib/http.dart" in seed_plan["candidate_file_paths"]
    assert "pkgs/http/lib/src/client.dart" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_profile_roots_for_initial_candidate_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "dart-profile-seeded-candidate-repo"
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
    (repo_path / "pkgs" / "app" / "lib" / "app.dart").write_text(
        "import 'package:http/http.dart' show Client;\n"
        "String run() => Client().ping();\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "http.dart").write_text(
        "export 'src/client.dart' show Client;\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "lib" / "src" / "client.dart").write_text(
        "class Client {\n"
        "  String ping() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )

    candidate_calls: list[dict[str, list[str]]] = []
    original_candidate_repository_file_paths = probe_module._candidate_repository_file_paths

    def _recording_candidate_repository_file_paths(
        *,
        repo_path: Path,
        seed_paths: list[str],
        bridge_paths: list[str],
        include_patterns: list[str],
        max_files: int,
    ) -> list[str]:
        candidate_calls.append(
            {
                "seed_paths": list(seed_paths),
                "bridge_paths": list(bridge_paths),
            }
        )
        return original_candidate_repository_file_paths(
            repo_path=repo_path,
            seed_paths=seed_paths,
            bridge_paths=bridge_paths,
            include_patterns=include_patterns,
            max_files=max_files,
        )

    monkeypatch.setattr(
        probe_module,
        "_candidate_repository_file_paths",
        _recording_candidate_repository_file_paths,
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert candidate_calls
    assert "pkgs/app/lib/app.dart" in candidate_calls[0]["seed_paths"]
    assert "pkgs/app/lib" in candidate_calls[0]["bridge_paths"]
    assert "pkgs/http/lib" in candidate_calls[0]["bridge_paths"]
    assert candidate_calls[0]["bridge_paths"] != ["."]
    assert "pkgs/http/lib/src/client.dart" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_keeps_later_workspace_entrypoints_in_candidates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dart-workspace-candidates-repo"
    app_lib_dir = repo_path / "pkgs" / "app" / "lib"
    parser_lib_dir = repo_path / "pkgs" / "http_parser" / "lib"
    parser_src_dir = parser_lib_dir / "src"
    app_lib_dir.mkdir(parents=True)
    parser_src_dir.mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http_parser" / "pubspec.yaml").write_text(
        "name: http_parser\n",
        encoding="utf-8",
    )
    (app_lib_dir / "app.dart").write_text(
        "import 'package:http_parser/http_parser.dart';\n"
        "String run() => MediaType.text;\n",
        encoding="utf-8",
    )
    for index in range(40):
        (app_lib_dir / f"worker_{index}.dart").write_text(
            f"int worker{index}() => {index};\n",
            encoding="utf-8",
        )
    (parser_lib_dir / "http_parser.dart").write_text(
        "export 'src/media_type.dart';\n",
        encoding="utf-8",
    )
    (parser_src_dir / "media_type.dart").write_text(
        "class MediaType {\n"
        "  static const String text = 'text/plain';\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=32,
    )

    assert "pkgs/http_parser/lib/http_parser.dart" in seed_plan["candidate_file_paths"]
    assert "pkgs/http_parser/lib/src/media_type.dart" in seed_plan["candidate_file_paths"]
    assert "pkgs/http_parser/lib/http_parser.dart" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_seeds_support_scan_from_entrypoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "dart-support-scan-seeds-repo"
    app_lib_dir = repo_path / "pkgs" / "app" / "lib"
    parser_lib_dir = repo_path / "pkgs" / "http_parser" / "lib"
    parser_src_dir = parser_lib_dir / "src"
    app_lib_dir.mkdir(parents=True)
    parser_src_dir.mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http_parser" / "pubspec.yaml").write_text(
        "name: http_parser\n",
        encoding="utf-8",
    )
    (app_lib_dir / "app.dart").write_text(
        "import 'package:http_parser/http_parser.dart';\n"
        "String run() => MediaType.text;\n",
        encoding="utf-8",
    )
    for index in range(96):
        (app_lib_dir / f"worker_{index}.dart").write_text(
            f"int worker{index}() => {index};\n",
            encoding="utf-8",
        )
    (parser_lib_dir / "http_parser.dart").write_text(
        "export 'src/media_type.dart';\n",
        encoding="utf-8",
    )
    (parser_src_dir / "media_type.dart").write_text(
        "class MediaType {\n"
        "  static const String text = 'text/plain';\n"
        "}\n",
        encoding="utf-8",
    )

    candidate_calls: list[dict[str, list[str]]] = []
    original_candidate_repository_file_paths = probe_module._candidate_repository_file_paths

    def _recording_candidate_repository_file_paths(
        *,
        repo_path: Path,
        seed_paths: list[str],
        bridge_paths: list[str],
        include_patterns: list[str],
        max_files: int,
    ) -> list[str]:
        candidate_calls.append(
            {
                "seed_paths": list(seed_paths),
                "bridge_paths": list(bridge_paths),
            }
        )
        return original_candidate_repository_file_paths(
            repo_path=repo_path,
            seed_paths=seed_paths,
            bridge_paths=bridge_paths,
            include_patterns=include_patterns,
            max_files=max_files,
        )

    monkeypatch.setattr(
        probe_module,
        "_candidate_repository_file_paths",
        _recording_candidate_repository_file_paths,
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=[],
        max_files=64,
    )

    support_scan_calls = [
        call
        for call in candidate_calls
        if "pkgs/http_parser/lib" in call["bridge_paths"]
        and "pkgs/app/lib" not in call["bridge_paths"]
    ]

    if support_scan_calls:
        assert any(
            "pkgs/app/lib/app.dart" in call["seed_paths"]
            and "pkgs/http_parser/lib/http_parser.dart" in call["seed_paths"]
            for call in support_scan_calls
        )
    else:
        assert candidate_calls
        assert "pkgs/app/lib/app.dart" in candidate_calls[0]["seed_paths"]
        assert "pkgs/http_parser/lib/http_parser.dart" in candidate_calls[0]["seed_paths"]
        assert "pkgs/http_parser/lib" in candidate_calls[0]["bridge_paths"]
    assert "pkgs/http_parser/lib/src/media_type.dart" in seed_plan["candidate_file_paths"]


