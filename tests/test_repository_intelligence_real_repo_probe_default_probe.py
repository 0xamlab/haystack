"""Tests for repository_intelligence_real_repo_probe: default_probe.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_default_probe_include_patterns_cover_generic_src_repos(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "generic-src-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "node_modules" / "pkg").mkdir(parents=True)
    (repo_path / "src" / "main.tsx").write_text(
        "export const App = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text('{"name":"generic-src"}\n', encoding="utf-8")
    (repo_path / "node_modules" / "pkg" / "index.ts").write_text(
        "export const ignored = 1;\n",
        encoding="utf-8",
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=[],
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=32,
    )

    assert "src/main.tsx" in candidate_paths
    assert "package.json" in candidate_paths
    assert all(not path.startswith("node_modules/") for path in candidate_paths)


def test_default_probe_include_patterns_cover_generic_ruby_and_java_repos(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "polyglot-probe-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "src" / "main" / "java" / "com" / "acme").mkdir(parents=True)
    (repo_path / "app" / "worker.rb").write_text("puts 'ok'\n", encoding="utf-8")
    (repo_path / "src" / "main" / "java" / "com" / "acme" / "Main.java").write_text(
        "class Main {}\n",
        encoding="utf-8",
    )
    (repo_path / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")
    (repo_path / "pom.xml").write_text("<project />\n", encoding="utf-8")
    (repo_path / "build.gradle").write_text("plugins {}\n", encoding="utf-8")

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=[],
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=32,
    )

    assert "app/worker.rb" in candidate_paths
    assert "src/main/java/com/acme/Main.java" in candidate_paths
    assert "Gemfile" in candidate_paths
    assert "pom.xml" in candidate_paths
    assert "build.gradle" in candidate_paths


def test_default_probe_include_patterns_cover_generic_cpp_repos(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cpp-probe-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "include" / "acme").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text("add_library(acme src/main.cpp)\n", encoding="utf-8")
    (repo_path / "src" / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
    (repo_path / "include" / "acme" / "core.hpp").write_text("#pragma once\n", encoding="utf-8")

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=[],
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=32,
    )

    assert "CMakeLists.txt" in candidate_paths
    assert "src/main.cpp" in candidate_paths
    assert "include/acme/core.hpp" in candidate_paths


