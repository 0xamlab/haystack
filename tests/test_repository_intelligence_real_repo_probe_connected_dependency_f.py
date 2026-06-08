"""Tests for repository_intelligence_real_repo_probe: connected_dependency_f.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_connected_dependency_map_reuses_shared_dependency_cache_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "workspace-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "util.ts").write_text(
        "export const helper = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { helper } from './util';\n"
        "export const run = (): string => helper();\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    first = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    def _unexpected_analyze_file_dependencies(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("shared dependency-analysis cache should avoid reparsing unchanged files")

    monkeypatch.setattr(
        repository_service,
        "_analyze_file_dependencies",
        _unexpected_analyze_file_dependencies,
    )

    second = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert first["connected_files"] == second["connected_files"]
    assert second["resolved_dependency_edges"] == first["resolved_dependency_edges"]


def test_connected_dependency_map_follows_python_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "python-workspace-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "helper.py").write_text(
        "def helper() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "util.py").write_text(
        "from lib.helper import helper\n\n"
        "def normalize() -> str:\n"
        "    return helper()\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.py").write_text(
        "from app.util import normalize\n\n"
        "def run() -> str:\n"
        "    return normalize()\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["app/main.py"],
        bridge_paths=["app"],
        include_patterns=["app/*.py", "app/**/*.py", "lib/*.py", "lib/**/*.py"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "app/main.py",
        "app/util.py",
        "lib/helper.py",
    ]


def test_connected_dependency_map_follows_rust_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "rust-workspace-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helper.rs").write_text(
        "pub fn value() -> String {\n"
        '    "ok".to_string()\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.rs").write_text(
        "use crate::helper::value;\n"
        "mod helper;\n\n"
        "pub fn run() -> String {\n"
        "    value()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main.rs"],
        bridge_paths=["src"],
        include_patterns=["src/*.rs", "src/**/*.rs"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/helper.rs",
        "src/main.rs",
    ]


def test_connected_dependency_map_follows_go_module_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "go-workspace-repo"
    (repo_path / "helper").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper" / "helper.go").write_text(
        "package helper\n\n"
        "func Value() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package main\n\n"
        'import "example.com/repo/helper"\n\n'
        "func run() string {\n"
        "    return helper.Value()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.go"],
        bridge_paths=["."],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper/helper.go",
        "main.go",
    ]


def test_connected_dependency_map_follows_go_same_package_symbol_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "go-same-package-connected-map-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run() string {\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.go"],
        bridge_paths=["."],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper.go",
        "main.go",
    ]


def test_connected_dependency_map_ignores_go_builtin_collisions_for_same_package_refs(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "go-builtin-connected-map-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "builtin.go").write_text(
        "package cobra\n\n"
        "func len(items []string) int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run(items []string) int {\n"
        "    _ = len(items)\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.go"],
        bridge_paths=["."],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper.go",
        "main.go",
    ]


def test_connected_dependency_map_prefers_non_test_go_same_package_targets(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "go-test-leak-connected-map-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "helper.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "ok"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "helper_test.go").write_text(
        "package cobra\n\n"
        "func helper() string {\n"
        '    return "test"\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "main.go").write_text(
        "package cobra\n\n"
        "func run() string {\n"
        "    return helper()\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.go"],
        bridge_paths=["."],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "helper.go",
        "main.go",
    ]


def test_connected_dependency_map_ignores_go_stdlib_import_file_name_collisions(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "go-stdlib-import-collision-connected-map-repo"
    (repo_path / "middleware").mkdir(parents=True)
    (repo_path / "_examples" / "versions" / "data").mkdir(parents=True)
    (repo_path / "go.mod").write_text("module example.com/repo\n", encoding="utf-8")
    (repo_path / "middleware" / "recoverer.go").write_text(
        "package middleware\n\n"
        'import "errors"\n\n'
        "func Recoverer() error {\n"
        '    return errors.New("boom")\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "_examples" / "versions" / "data" / "errors.go").write_text(
        "package data\n\n"
        "func PresentError() string {\n"
        '    return "boom"\n'
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["middleware/recoverer.go"],
        bridge_paths=[".", "_examples"],
        include_patterns=["*.go", "**/*.go"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_files"] == [
        "middleware/recoverer.go",
    ]


def test_connected_dependency_map_follows_kotlin_multi_type_file_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "kotlin-connected-map-repo"
    package_dir = repo_path / "src" / "main" / "kotlin" / "com" / "example"
    package_dir.mkdir(parents=True)
    (package_dir / "Repositories.kt").write_text(
        "package com.example\n"
        "interface ArticleRepository\n"
        "interface UserRepository\n",
        encoding="utf-8",
    )
    (package_dir / "Controllers.kt").write_text(
        "package com.example\n"
        "class HtmlController(\n"
        "    private val articleRepository: ArticleRepository,\n"
        "    private val userRepository: UserRepository,\n"
        ")\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main/kotlin/com/example/Controllers.kt"],
        bridge_paths=["src/main/kotlin"],
        include_patterns=["src/main/kotlin/**/*.kt"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/main/kotlin/com/example/Controllers.kt",
        "src/main/kotlin/com/example/Repositories.kt",
    ]


def test_connected_dependency_map_follows_groovy_import_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "groovy-connected-map-repo"
    package_dir = repo_path / "src" / "main" / "groovy" / "org" / "example"
    package_dir.mkdir(parents=True)
    (repo_path / "build.gradle").write_text(
        "plugins { id 'groovy' }\n",
        encoding="utf-8",
    )
    (package_dir / "Owner.groovy").write_text(
        "package org.example\nclass Owner {}\n",
        encoding="utf-8",
    )
    (package_dir / "OwnerController.groovy").write_text(
        "package org.example\n"
        "import org.example.Owner as PetOwner\n"
        "class OwnerController {\n"
        "  PetOwner owner\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/main/groovy/org/example/OwnerController.groovy"],
        bridge_paths=["src/main/groovy"],
        include_patterns=["build.gradle", "src/main/groovy/**/*.groovy"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert sorted(connected_map["connected_files"]) == [
        "src/main/groovy/org/example/Owner.groovy",
        "src/main/groovy/org/example/OwnerController.groovy",
    ]


def test_connected_dependency_map_follows_robotframework_resource_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "robotframework-connected-map-repo"
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "resources").mkdir(parents=True)
    (repo_path / "resources" / "common.resource").write_text(
        "*** Keywords ***\nOpen Login Page\n    Log    ready\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "login.robot").write_text(
        "*** Settings ***\nResource    ../resources/common.resource\n\n*** Test Cases ***\nValid Login\n    Open Login Page\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["tests/login.robot"],
        bridge_paths=["tests", "resources"],
        include_patterns=["tests/**/*.robot", "resources/**/*.resource"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert sorted(connected_map["connected_files"]) == [
        "resources/common.resource",
        "tests/login.robot",
    ]


def test_connected_dependency_map_follows_typst_import_include_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "typst-connected-map-repo"
    (repo_path / "content").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "content" / "math.typ").write_text(
        "#let add(x, y) = x + y\n"
        "#let scale(x) = x * 2\n",
        encoding="utf-8",
    )
    (repo_path / "partials" / "common.typ").write_text(
        "#let title() = [Demo]\n",
        encoding="utf-8",
    )
    (repo_path / "main.typ").write_text(
        '#import "content/math.typ": add\n'
        '#import "content/math.typ" as math\n'
        '#include "partials/common.typ"\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "  math.scale(3)\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.typ"],
        bridge_paths=["content", "partials"],
        include_patterns=["*.typ", "content/*.typ", "content/**/*.typ", "partials/*.typ"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert sorted(connected_map["connected_files"]) == [
        "content/math.typ",
        "main.typ",
        "partials/common.typ",
    ]


def test_connected_dependency_map_follows_scss_import_and_reference_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "scss-connected-map-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "_mixins.scss").write_text(
        "@mixin button-base {\n"
        "  color: $brand;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "_functions.scss").write_text(
        "@function helper-fn() {\n"
        "  @return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "app.scss").write_text(
        '@use "styles/mixins" as mixins;\n'
        '@import "styles/functions";\n'
        ".button {\n"
        "  @include mixins.button-base;\n"
        "  color: helper-fn();\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["app.scss"],
        bridge_paths=["styles"],
        include_patterns=["*.scss", "styles/*.scss", "styles/**/*.scss"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert sorted(connected_map["connected_files"]) == [
        "app.scss",
        "styles/_functions.scss",
        "styles/_mixins.scss",
    ]


def test_connected_dependency_map_follows_dockerfile_copy_run_and_stage_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dockerfile-connected-map-repo"
    (repo_path / "docker").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "bootstrap.sh").write_text(
        "#!/usr/bin/env sh\n"
        "echo bootstrap\n",
        encoding="utf-8",
    )
    (repo_path / "docker" / "Dockerfile").write_text(
        "FROM alpine:3.20 AS base\n"
        "COPY ../scripts/bootstrap.sh /usr/local/bin/bootstrap.sh\n"
        "RUN ./../scripts/bootstrap.sh\n"
        "FROM base AS runtime\n"
        "COPY --from=base /usr/local/bin/bootstrap.sh /usr/local/bin/bootstrap.sh\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["docker/Dockerfile"],
        bridge_paths=["scripts"],
        include_patterns=["docker/Dockerfile", "scripts/*.sh", "scripts/**/*.sh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 2
    assert sorted(connected_map["connected_files"]) == [
        "docker/Dockerfile",
        "scripts/bootstrap.sh",
    ]


def test_connected_dependency_map_follows_dart_package_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "dart-workspace-repo"
    (repo_path / "lib" / "src").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "pubspec.yaml").write_text(
        "name: acme_client\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "src" / "helper.dart").write_text(
        "class Helper {\n"
        "  static String value() => 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "acme_client.dart").write_text(
        "export 'src/helper.dart' show Helper;\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "acme_client.dart").write_text(
        "import 'package:acme_client/acme_client.dart' show Helper;\n\n"
        "String run() => Helper.value();\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["bin/acme_client.dart"],
        bridge_paths=["lib", "bin"],
        include_patterns=["lib/*.dart", "lib/**/*.dart", "bin/*.dart", "bin/**/*.dart"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 3
    assert connected_map["resolved_dependency_edges"] >= 2
    assert connected_map["connected_files"] == [
        "bin/acme_client.dart",
        "lib/acme_client.dart",
        "lib/src/helper.dart",
    ]


def test_connected_dependency_map_follows_clojure_namespace_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "clojure-connected-map-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "util.clj").write_text(
        "(ns acme.util)\n(defn helper [] :ok)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.clj").write_text(
        "(ns acme.core\n"
        "  (:require [acme.util :as util]))\n"
        "(defn run []\n"
        "  (util/helper))\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/acme/core.clj"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.clj", "src/**/*.cljc", "src/**/*.cljs"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "src/acme/core.clj",
        "src/acme/util.clj",
    ]


def test_connected_dependency_map_follows_lua_require_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "lua-connected-map-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\nfunction M.helper() return 'ok' end\nreturn M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "core.lua").write_text(
        "local util = require('acme.util')\n"
        "local function run()\n"
        "  return util.helper()\n"
        "end\n"
        "return { run = run }\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lua/acme/core.lua"],
        bridge_paths=["lua"],
        include_patterns=["lua/**/*.lua", "*.rockspec"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "lua/acme/core.lua",
        "lua/acme/util.lua",
    ]


def test_connected_dependency_map_follows_lua_require_member_and_method_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lua-member-connected-map-repo"
    (repo_path / "lua" / "acme").mkdir(parents=True)
    (repo_path / "lua" / "acme" / "util.lua").write_text(
        "local M = {}\n"
        "function M.helper() return 'ok' end\n"
        "function M:push() return self:helper() end\n"
        "return M\n",
        encoding="utf-8",
    )
    (repo_path / "lua" / "acme" / "core.lua").write_text(
        "local util = require('acme.util')\n"
        "local helper = require('acme.util').helper\n"
        "local function run()\n"
        "  util:push()\n"
        "  return helper()\n"
        "end\n"
        "return { run = run }\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["lua/acme/core.lua"],
        bridge_paths=["lua"],
        include_patterns=["lua/**/*.lua", "*.rockspec"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 3
    assert connected_map["connected_files"] == [
        "lua/acme/core.lua",
        "lua/acme/util.lua",
    ]


def test_connected_dependency_map_follows_shell_source_edges(tmp_path: Path) -> None:
    repo_path = tmp_path / "shell-connected-map-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "lib" / "util.zsh").write_text(
        "helper() {\n"
        "  echo ok\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts" / "main.sh").write_text(
        ". ../lib/util.zsh\n"
        "run() {\n"
        "  helper\n"
        "}\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["scripts/main.sh"],
        bridge_paths=["scripts", "lib"],
        include_patterns=["scripts/*.sh", "lib/*.zsh"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert connected_map["connected_files"] == [
        "lib/util.zsh",
        "scripts/main.sh",
    ]


