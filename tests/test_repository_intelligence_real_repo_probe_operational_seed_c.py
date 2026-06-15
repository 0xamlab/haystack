"""Tests for repository_intelligence_real_repo_probe: operational_seed_c.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_plan_without_diagnostics_skips_support_rescan_when_roots_are_covered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "dart-covered-support-roots-repo"
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
        max_files=256,
    )

    assert len(candidate_calls) == 1
    assert "pkgs/http_parser/lib/src/media_type.dart" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_excludes_github_yaml_fallbacks(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "python-gh-noise-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / ".github" / "workflows").mkdir(parents=True)
    (repo_path / ".github" / "DISCUSSION_TEMPLATE").mkdir(parents=True)
    (repo_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "acme"\n'
        "[project.scripts]\n"
        'acme = "acme.cli:main"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "cli.py").write_text(
        "def main() -> int:\n    return 0\n",
        encoding="utf-8",
    )
    (repo_path / ".github" / "workflows" / "test.yml").write_text(
        "name: test\n",
        encoding="utf-8",
    )
    (repo_path / ".github" / "DISCUSSION_TEMPLATE" / "questions.yml").write_text(
        "body: []\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "src/acme/cli.py" in seed_plan["entrypoint_files"]
    assert all(not path.startswith(".github/") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_uses_maven_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "java-maven-repo"
    (repo_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (repo_path / ".github" / "workflows").mkdir(parents=True)
    (repo_path / "pom.xml").write_text(
        "<project><modelVersion>4.0.0</modelVersion></project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "java" / "com" / "example" / "PetClinicApplication.java").write_text(
        "package com.example;\npublic class PetClinicApplication {}\n",
        encoding="utf-8",
    )
    (repo_path / ".github" / "workflows" / "build.yml").write_text(
        "name: build\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "pom.xml" in seed_plan["config_paths"]
    assert "java" in seed_plan["detected_ecosystems"]
    assert "src/main/java" in seed_plan["support_roots"]
    assert any(path.endswith(".java") for path in seed_plan["entrypoint_files"])
    assert all(not path.startswith(".github/") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_deprioritizes_jvm_resource_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "java-resource-repo"
    (repo_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
    (repo_path / "src" / "main" / "resources" / "db").mkdir(parents=True)
    (repo_path / "pom.xml").write_text(
        "<project><modelVersion>4.0.0</modelVersion></project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "java" / "com" / "example" / "PetClinicApplication.java").write_text(
        "package com.example;\npublic class PetClinicApplication {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "resources" / "db" / "schema.sql").write_text(
        "create table demo(id int);\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert any(path.endswith(".java") for path in seed_plan["entrypoint_files"])
    assert all(not path.endswith(".sql") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_excludes_text_control_fallbacks(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "go-library-repo"
    (repo_path / ".github" / "workflows").mkdir(parents=True)
    (repo_path / "doc").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/acme\n", encoding="utf-8")
    (repo_path / "cobra.go").write_text("package cobra\nfunc New() {}\n", encoding="utf-8")
    (repo_path / "args.go").write_text("package cobra\nfunc Args() {}\n", encoding="utf-8")
    (repo_path / "Makefile").write_text("test:\n\tgo test ./...\n", encoding="utf-8")
    (repo_path / "LICENSE.txt").write_text("license\n", encoding="utf-8")
    (repo_path / ".github" / "workflows" / "test.yml").write_text("name: test\n", encoding="utf-8")
    (repo_path / "doc" / "usage.md").write_text("# usage\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "go" in seed_plan["detected_ecosystems"]
    assert any(path.endswith(".go") for path in seed_plan["entrypoint_files"])
    assert all(not path.endswith("_test.go") for path in seed_plan["entrypoint_files"])
    assert "Makefile" not in seed_plan["entrypoint_files"]
    assert "LICENSE.txt" not in seed_plan["entrypoint_files"]
    assert all(not path.startswith(".github/") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_deprioritizes_docs_examples(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "python-docs-heavy-repo"
    (repo_path / "fastapi").mkdir(parents=True)
    (repo_path / "docs_src" / "tutorial").mkdir(parents=True)
    (repo_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "fastapi-like"\n'
        "[project.scripts]\n"
        'fastapi = "fastapi.cli:main"\n',
        encoding="utf-8",
    )
    (repo_path / "fastapi" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (repo_path / "fastapi" / "cli.py").write_text("def main() -> int:\n    return 0\n", encoding="utf-8")
    (repo_path / "fastapi" / "routing.py").write_text("class Router: ...\n", encoding="utf-8")
    (repo_path / "docs_src" / "tutorial" / "main.py").write_text(
        "def tutorial() -> int:\n    return 0\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "fastapi/cli.py" in seed_plan["entrypoint_files"]
    assert any(path.startswith("fastapi/") for path in seed_plan["entrypoint_files"])
    assert "docs_src/tutorial/main.py" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_composer_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "php-composer-repo"
    (repo_path / "app" / "Models").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "composer.json").write_text(
        '{\n'
        '  "autoload": { "psr-4": { "App\\\\\\\\": "app/" } },\n'
        '  "bin": ["artisan"]\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "app" / "ConsoleKernel.php").write_text("<?php\n", encoding="utf-8")
    (repo_path / "app" / "Models" / "User.php").write_text("<?php\n", encoding="utf-8")
    (repo_path / "public" / "index.php").write_text("<?php\n", encoding="utf-8")
    (repo_path / "artisan").write_text("#!/usr/bin/env php\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "php" in seed_plan["detected_ecosystems"]
    assert "composer.json" in seed_plan["config_paths"]
    assert "app" in seed_plan["support_roots"]
    assert "public/index.php" in seed_plan["entrypoint_files"] or "artisan" in seed_plan["entrypoint_files"]
    assert "app/Models/User.php" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_hack_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hack-hhconfig-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / ".hhconfig").write_text("assume_php = false\n", encoding="utf-8")
    (repo_path / "src" / "Ref.php").write_text(
        "<?hh\nnamespace Demo;\nfinal class Ref<T> {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "User.hack").write_text(
        "namespace Demo;\nuse type Demo\\Ref;\nfinal class User { public function make(): Ref<int> { return new Ref(); } }\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "UserTest.php").write_text(
        "<?hh\nnamespace Demo;\nfinal class UserTest {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"][0] == "hack"
    assert seed_plan["operational_ecosystems"][0] == "hack"
    assert ".hhconfig" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Ref.php" in seed_plan["entrypoint_files"] or "src/User.hack" in seed_plan["entrypoint_files"]
    assert "tests/UserTest.php" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_mix_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "elixir-mix-repo"
    (repo_path / "lib" / "acme").mkdir(parents=True)
    (repo_path / "mix.exs").write_text(
        "defmodule Acme.MixProject do\n"
        "  use Mix.Project\n"
        "  def project do\n"
        "    [app: :acme]\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.ex").write_text("defmodule Acme do\nend\n", encoding="utf-8")
    (repo_path / "lib" / "acme" / "repo.ex").write_text("defmodule Acme.Repo do\nend\n", encoding="utf-8")
    (repo_path / "lib" / "acme" / "application.ex").write_text(
        "defmodule Acme.Application do\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "elixir" in seed_plan["detected_ecosystems"]
    assert "mix.exs" in seed_plan["config_paths"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/acme.ex" in seed_plan["entrypoint_files"] or "lib/acme/application.ex" in seed_plan["entrypoint_files"]
    assert "lib/acme/repo.ex" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_deprioritizes_static_assets(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "elixir-node-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "priv" / "static").mkdir(parents=True)
    (repo_path / "mix.exs").write_text(
        "defmodule Acme.MixProject do\n"
        "  use Mix.Project\n"
        "  def project do\n"
        "    [app: :acme]\n"
        "  end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        json.dumps({"name": "acme", "main": "priv/static/app.js"}),
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme.ex").write_text("defmodule Acme do\nend\n", encoding="utf-8")
    (repo_path / "priv" / "static" / "app.js").write_text("export const app = true;\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "lib/acme.ex" in seed_plan["entrypoint_files"]
    assert "priv/static/app.js" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_swift_package_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "swift-package-repo"
    (repo_path / "Sources" / "AcmeCLI").mkdir(parents=True)
    (repo_path / "Package.swift").write_text(
        'let package = Package(name: "AcmeCLI")\n',
        encoding="utf-8",
    )
    (repo_path / "Sources" / "AcmeCLI" / "main.swift").write_text(
        'print("ok")\n',
        encoding="utf-8",
    )
    (repo_path / "Sources" / "AcmeCLI" / "Command.swift").write_text(
        "struct Command {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "swift" in seed_plan["detected_ecosystems"]
    assert "Package.swift" in seed_plan["config_paths"]
    assert "Sources" in seed_plan["support_roots"]
    assert "Sources/AcmeCLI/main.swift" in seed_plan["entrypoint_files"]
    assert "Sources/AcmeCLI/Command.swift" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_swift_library_sources(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "swift-library-repo"
    (repo_path / "Sources" / "ArgumentParser").mkdir(parents=True)
    (repo_path / "Package.swift").write_text(
        'let package = Package(name: "ArgumentParser")\n',
        encoding="utf-8",
    )
    (repo_path / "Sources" / "ArgumentParser" / "Argument.swift").write_text(
        "public struct Argument {}\n",
        encoding="utf-8",
    )
    (repo_path / "Sources" / "ArgumentParser" / "Parser.swift").write_text(
        "public struct Parser {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "swift" in seed_plan["detected_ecosystems"]
    assert "Sources/ArgumentParser/Argument.swift" in seed_plan["entrypoint_files"]
    assert "Sources/ArgumentParser/Parser.swift" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_scala_build_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scala-build-repo"
    (repo_path / "src" / "main" / "scala" / "acme").mkdir(parents=True)
    (repo_path / "src" / "test" / "scala" / "acme").mkdir(parents=True)
    (repo_path / "build.sbt").write_text(
        'name := "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "scala" / "acme" / "Main.scala").write_text(
        "package acme\nobject Main\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "scala" / "acme" / "Routes.scala").write_text(
        "package acme\nobject Routes\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "test" / "scala" / "acme" / "RoutesSpec.scala").write_text(
        "package acme\nobject RoutesSpec\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "scala" in seed_plan["detected_ecosystems"]
    assert "build.sbt" in seed_plan["config_paths"]
    assert "src/main/scala" in seed_plan["support_roots"]
    assert "src/main/scala/acme/Main.scala" in seed_plan["entrypoint_files"]
    assert "src/main/scala/acme/Routes.scala" in seed_plan["entrypoint_files"]
    assert "src/test/scala/acme/RoutesSpec.scala" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_mill_scala_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mill-scala-repo"
    (repo_path / "upack" / "src" / "upack").mkdir(parents=True)
    (repo_path / "upickle" / "src" / "upickle").mkdir(parents=True)
    (repo_path / "bench" / "src").mkdir(parents=True)
    (repo_path / "build.mill").write_text(
        "import mill._\n",
        encoding="utf-8",
    )
    (repo_path / "upack" / "src" / "upack" / "Msg.scala").write_text(
        "package upack\nobject Msg\n",
        encoding="utf-8",
    )
    (repo_path / "upickle" / "src" / "upickle" / "Api.scala").write_text(
        "package upickle\nobject Api\n",
        encoding="utf-8",
    )
    (repo_path / "bench" / "src" / "Common.scala").write_text(
        "package bench\nobject Common\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "scala" in seed_plan["detected_ecosystems"]
    assert "build.mill" in seed_plan["config_paths"]
    assert "upack/src/upack" in seed_plan["support_roots"]
    assert "upickle/src/upickle" in seed_plan["support_roots"]
    assert "upack/src/upack/Msg.scala" in seed_plan["entrypoint_files"]
    assert "upickle/src/upickle/Api.scala" in seed_plan["entrypoint_files"]
    assert "bench/src/Common.scala" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_scala_profile_roots_for_initial_candidate_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "scala-profile-seeded-candidate-repo"
    (repo_path / "play-json" / "shared" / "src" / "main" / "scala" / "play" / "api" / "libs" / "json").mkdir(parents=True)
    (repo_path / "play-json" / "jvm" / "src" / "main" / "scala" / "play" / "api" / "libs" / "json").mkdir(parents=True)
    (repo_path / "benchmarks" / "src" / "main" / "scala").mkdir(parents=True)
    (repo_path / "build.sbt").write_text(
        'name := "play-json"\n',
        encoding="utf-8",
    )
    (
        repo_path
        / "play-json"
        / "shared"
        / "src"
        / "main"
        / "scala"
        / "play"
        / "api"
        / "libs"
        / "json"
        / "Json.scala"
    ).write_text(
        "package play.api.libs.json\nobject Json\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "play-json"
        / "jvm"
        / "src"
        / "main"
        / "scala"
        / "play"
        / "api"
        / "libs"
        / "json"
        / "JvmJson.scala"
    ).write_text(
        "package play.api.libs.json\nobject JvmJson\n",
        encoding="utf-8",
    )
    (repo_path / "benchmarks" / "src" / "main" / "scala" / "Bench.scala").write_text(
        "package benchmarks\nobject Bench\n",
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
    assert candidate_calls[0]["bridge_paths"] != ["."]
    assert "play-json/shared/src/main/scala" in candidate_calls[0]["bridge_paths"]
    assert "play-json/jvm/src/main/scala" in candidate_calls[0]["bridge_paths"]
    assert "benchmarks/src" not in candidate_calls[0]["bridge_paths"]
    assert "play-json/shared/src/main/scala/play/api/libs/json/Json.scala" in seed_plan["candidate_file_paths"]
    assert "play-json/jvm/src/main/scala/play/api/libs/json/JvmJson.scala" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_gradle_groovy_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gradle-groovy-repo"
    (repo_path / "src" / "main" / "groovy" / "org" / "example").mkdir(parents=True)
    (repo_path / "src" / "test" / "groovy" / "org" / "example").mkdir(parents=True)
    (repo_path / "build.gradle").write_text(
        "plugins { id 'groovy' }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "groovy" / "org" / "example" / "Main.groovy").write_text(
        "package org.example\nclass Main {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "groovy" / "org" / "example" / "Helper.groovy").write_text(
        "package org.example\nclass Helper {}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "test" / "groovy" / "org" / "example" / "MainSpec.groovy").write_text(
        "package org.example\nclass MainSpec {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "groovy" in seed_plan["detected_ecosystems"]
    assert "java" in seed_plan["detected_ecosystems"]
    assert "build.gradle" in seed_plan["config_paths"]
    assert "src/main/groovy" in seed_plan["support_roots"]
    assert "src/main/groovy/org/example/Main.groovy" in seed_plan["entrypoint_files"]
    assert "src/main/groovy/org/example/Helper.groovy" in seed_plan["candidate_file_paths"]
    assert "src/test/groovy/org/example/MainSpec.groovy" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_gradle_kotlin_main_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gradle-kotlin-repo"
    (repo_path / "src" / "main" / "kotlin" / "org" / "example").mkdir(parents=True)
    (repo_path / "src" / "jvmTest" / "java" / "org" / "example").mkdir(parents=True)
    (repo_path / "buildSrc" / "src" / "main" / "kotlin" / "buildlogic").mkdir(parents=True)
    (repo_path / "build.gradle.kts").write_text(
        "plugins { kotlin(\"jvm\") version \"2.0.0\" }\n",
        encoding="utf-8",
    )
    (repo_path / "settings.gradle.kts").write_text(
        'rootProject.name = "acme"\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "kotlin" / "org" / "example" / "Main.kt").write_text(
        "package org.example\nclass Main\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main" / "kotlin" / "org" / "example" / "Helper.kt").write_text(
        "package org.example\nclass Helper\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "jvmTest" / "java" / "org" / "example" / "JavaNoise.java").write_text(
        "package org.example; public class JavaNoise {}\n",
        encoding="utf-8",
    )
    (repo_path / "buildSrc" / "build.gradle.kts").write_text(
        "plugins { kotlin(\"jvm\") version \"2.0.0\" }\n",
        encoding="utf-8",
    )
    (repo_path / "buildSrc" / "src" / "main" / "kotlin" / "buildlogic" / "BuildLogic.kt").write_text(
        "package buildlogic\nclass BuildLogic\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "kotlin" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "kotlin"
    assert "build.gradle.kts" in seed_plan["config_paths"]
    assert "src/main/kotlin" in seed_plan["support_roots"]
    assert "buildSrc/src/main/kotlin" not in seed_plan["support_roots"]
    assert "src/main/kotlin/org/example/Main.kt" in seed_plan["entrypoint_files"]
    assert "src/main/kotlin/org/example/Helper.kt" in seed_plan["candidate_file_paths"]
    assert "src/jvmTest/java/org/example/JavaNoise.java" not in seed_plan["entrypoint_files"]
    assert "buildSrc/src/main/kotlin/buildlogic/BuildLogic.kt" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_gradle_settings_included_projects(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gradle-settings-repo"
    (repo_path / "app" / "src" / "main" / "groovy").mkdir(parents=True)
    (repo_path / "feature" / "core" / "src" / "main" / "groovy").mkdir(parents=True)
    (repo_path / "settings.gradle").write_text(
        'include "app", ":feature:core"\n',
        encoding="utf-8",
    )
    (repo_path / "app" / "src" / "main" / "groovy" / "Main.groovy").write_text(
        "class Main {}\n",
        encoding="utf-8",
    )
    (
        repo_path
        / "feature"
        / "core"
        / "src"
        / "main"
        / "groovy"
        / "Application.groovy"
    ).write_text(
        "class Application {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "groovy" in seed_plan["detected_ecosystems"]
    assert "java" in seed_plan["detected_ecosystems"]
    assert "settings.gradle" in seed_plan["config_paths"]
    assert "app/src/main/groovy" in seed_plan["support_roots"]
    assert "feature/core/src/main/groovy" in seed_plan["support_roots"]
    assert "app" not in seed_plan["support_roots"]
    assert "feature/core" not in seed_plan["support_roots"]
    assert "app/src/main/groovy/Main.groovy" in seed_plan["entrypoint_files"]
    assert "feature/core/src/main/groovy/Application.groovy" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_robotframework_suites(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "robotframework-repo"
    (repo_path / "login_tests").mkdir(parents=True)
    (repo_path / "resources").mkdir(parents=True)
    (repo_path / "demoapp").mkdir(parents=True)
    (repo_path / "README.rst").write_text(
        "WebDemo\n=======\n\nRobot Framework demo.\n",
        encoding="utf-8",
    )
    (repo_path / "BUILD.rst").write_text(
        "Build\n=====\n\nRun the demo app.\n",
        encoding="utf-8",
    )
    (repo_path / "resources" / "resource.robot").write_text(
        "*** Keywords ***\nOpen Login Page\n    Log    hello\n",
        encoding="utf-8",
    )
    (repo_path / "login_tests" / "valid_login.robot").write_text(
        "*** Settings ***\nResource    ../resources/resource.robot\n\n*** Test Cases ***\nValid Login\n    Open Login Page\n",
        encoding="utf-8",
    )
    (repo_path / "demoapp" / "server.py").write_text(
        "def main():\n    return None\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "robotframework" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "robotframework"
    assert "login_tests" in seed_plan["support_roots"]
    assert "login_tests/valid_login.robot" in seed_plan["entrypoint_files"]
    assert "resources/resource.robot" in seed_plan["candidate_file_paths"]

