"""Tests for repository_intelligence_real_repo_probe: default_probe.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

import benchmarks.repository_intelligence_real_repo_probe_runtime_support as probe_runtime_support

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


def test_default_probe_matches_root_focus_path_without_filtering_git_files(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "root-focus-probe-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "README.md").write_text("# Root focus\n", encoding="utf-8")
    (repo_path / "src" / "main.typ").write_text("#let title = [Demo]\n", encoding="utf-8")

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=["."],
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=32,
    )

    assert "README.md" in candidate_paths
    assert "src/main.typ" in candidate_paths


def test_probe_repo_state_uses_binary_status_shape_shared_with_repository_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "probe-repo-state-git-status"
    repo_path.mkdir()
    observed_commands: list[tuple[tuple[str, ...], dict[str, object]]] = []

    monkeypatch.setattr(probe_module.repository_service, "_is_git_repository", lambda _: True)

    def _fake_git_command(args, **kwargs):  # type: ignore[no-untyped-def]
        observed_commands.append((tuple(str(arg) for arg in args), dict(kwargs)))
        if tuple(str(arg) for arg in args) == ("git", "-C", str(repo_path), "rev-parse", "HEAD"):
            return "deadbeef\n"
        if tuple(str(arg) for arg in args) == (
            "git",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ):
            assert kwargs["cwd"] == repo_path
            assert kwargs["timeout"] == 60.0
            assert kwargs["binary"] is True
            return b"M  src/Main.agda\0?? scratch.txt\0R  renamed/new.agda\0renamed/old.agda\0"
        raise AssertionError(f"unexpected git command: {args}")

    monkeypatch.setattr(probe_module.repository_service, "_git_command", _fake_git_command)

    state = probe_runtime_support.probe_repo_state(repo_path)

    expected_status_entries = [
        "M  src/Main.agda",
        "?? scratch.txt",
        "R  renamed/new.agda",
    ]
    assert state == {
        "cache_enabled": True,
        "cache_mode": "git",
        "reason": None,
        "resolved_revision": "deadbeef",
        "state_id": probe_module.repository_service._hash_payload(  # type: ignore[attr-defined]
            {"resolved_revision": "deadbeef", "status_lines": expected_status_entries}
        ),
        "dirty": True,
        "status_entry_count": 3,
        "status_hash": probe_module.repository_service._hash_payload(expected_status_entries),  # type: ignore[attr-defined]
    }
    assert observed_commands[0][0] == ("git", "-C", str(repo_path), "rev-parse", "HEAD")
    assert observed_commands[1][0] == (
        "git",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )


def test_leaf_support_roots_keeps_only_deepest_nested_roots() -> None:
    leaf_roots = probe_module._leaf_support_roots(
        {
            "cpp",
            "cpp/0_Introduction",
            "cpp/0_Introduction/asyncAPI",
            "cpp/0_Introduction/asyncAPI/src",
            "cpp/0_Introduction/clock",
            "cpp/0_Introduction/clock/src",
            "Common",
        }
    )

    assert leaf_roots == {
        "cpp/0_Introduction/asyncAPI/src",
        "cpp/0_Introduction/clock/src",
        "Common",
    }


def test_compute_probe_prepass_uses_precomputed_operational_seed_plan(tmp_path: Path) -> None:
    repo_path = tmp_path / "precomputed-seed-plan-repo"
    repo_path.mkdir()
    captured: dict[str, object] = {}
    operational_seed_plan = {
        "candidate_file_paths": ["src/main.typ"],
        "config_paths": ["typst.toml"],
        "detected_ecosystems": ["typst"],
        "entrypoint_files": ["src/main.typ"],
        "operational_ecosystems": ["typst"],
        "support_roots": ["src"],
    }

    deps = probe_runtime_support.ProbePrepassDependencies(
        default_exclude_patterns=[],
        default_include_patterns=["**/*"],
        prepass_cache_schema_version="test",
        build_connected_dependency_map=lambda **kwargs: (
            captured.update(
                {
                    "bridge_paths": kwargs["bridge_paths"],
                    "candidate_file_paths": kwargs["candidate_file_paths"],
                    "candidate_scope_paths": kwargs["candidate_scope_paths"],
                }
            )
            or {
                "connected_files": ["src/main.typ"],
                "seed_files": ["src/main.typ"],
                "connected_file_count": 1,
            }
        ),
        candidate_config_focus_paths=lambda **kwargs: ["typst.toml"],
        candidate_solutions=lambda diagnostics: [],
        derive_operational_seed_plan_without_diagnostics=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("precomputed operational seed plan should bypass derivation")
        ),
        effective_focus_paths_for_snapshot=lambda **kwargs: ["src"],
        focus_paths_from_diagnostics=lambda **kwargs: ["src"],
        inventory_repo_surface=lambda **kwargs: {"file_count": 1},
        parse_repository_diagnostics=lambda **kwargs: [],
        resolve_diagnostic_base_path=lambda repo_path, diagnostic_command, diagnostic_base_path: repo_path,
        resolve_diagnostic_project_path=lambda repo_path, diagnostic_command, diagnostic_base_path: None,
        run_command=lambda repo_path, diagnostic_command: {
            "combined_output": "",
            "command": diagnostic_command,
            "elapsed_ms": 0.0,
            "exit_code": 0,
            "returncode": 0,
        },
    )

    result = probe_runtime_support.compute_probe_prepass(
        repo_path=repo_path,
        focus_paths=["src"],
        operational_seed_plan=operational_seed_plan,
        diagnostic_command=None,
        diagnostic_base_path=None,
        repository_runtime_root=tmp_path / "runtime",
        max_files=32,
        max_file_size_bytes=50_000,
        max_dependency_depth=2,
        max_connected_files=16,
        deps=deps,
    )

    assert result["cache_status"] == "disabled_precomputed_seed_plan"
    assert result["cache_enabled"] is False
    assert result["cache_reason"] == "precomputed_operational_seed_plan"
    assert result["cache_key"] is None
    assert result["operational_seed_plan"] == operational_seed_plan
    assert captured["bridge_paths"] == []
    assert captured["candidate_file_paths"] == ["src/main.typ"]
    assert captured["candidate_scope_paths"] == ["src"]


def test_compute_probe_prepass_bypasses_repo_state_for_precomputed_operational_seed_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "precomputed-seed-plan-no-repo-state-repo"
    repo_path.mkdir()
    operational_seed_plan = {
        "candidate_file_paths": ["src/main.typ"],
        "config_paths": ["typst.toml"],
        "detected_ecosystems": ["typst"],
        "entrypoint_files": ["src/main.typ"],
        "operational_ecosystems": ["typst"],
        "support_roots": ["src"],
    }

    monkeypatch.setattr(
        probe_runtime_support,
        "probe_repo_state",
        lambda _repo_path: (_ for _ in ()).throw(
            AssertionError("precomputed seed-plan path should bypass repo state probing")
        ),
    )

    deps = probe_runtime_support.ProbePrepassDependencies(
        default_exclude_patterns=[],
        default_include_patterns=["**/*"],
        prepass_cache_schema_version="test",
        build_connected_dependency_map=lambda **kwargs: {
            "connected_files": ["src/main.typ"],
            "seed_files": ["src/main.typ"],
            "connected_file_count": 1,
        },
        candidate_config_focus_paths=lambda **kwargs: ["typst.toml"],
        candidate_solutions=lambda diagnostics: [],
        derive_operational_seed_plan_without_diagnostics=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("precomputed operational seed plan should bypass derivation")
        ),
        effective_focus_paths_for_snapshot=lambda **kwargs: ["src"],
        focus_paths_from_diagnostics=lambda **kwargs: ["src"],
        inventory_repo_surface=lambda **kwargs: {"file_count": 1},
        parse_repository_diagnostics=lambda **kwargs: [],
        resolve_diagnostic_base_path=lambda repo_path, diagnostic_command, diagnostic_base_path: repo_path,
        resolve_diagnostic_project_path=lambda repo_path, diagnostic_command, diagnostic_base_path: None,
        run_command=lambda repo_path, diagnostic_command: {
            "combined_output": "",
            "command": diagnostic_command,
            "elapsed_ms": 0.0,
            "exit_code": 0,
            "returncode": 0,
        },
    )

    result = probe_runtime_support.compute_probe_prepass(
        repo_path=repo_path,
        focus_paths=["src"],
        operational_seed_plan=operational_seed_plan,
        diagnostic_command=None,
        diagnostic_base_path=None,
        repository_runtime_root=tmp_path / "runtime",
        max_files=32,
        max_file_size_bytes=50_000,
        max_dependency_depth=2,
        max_connected_files=16,
        deps=deps,
    )

    assert result["cache_status"] == "disabled_precomputed_seed_plan"
    assert result["cache_enabled"] is False
    assert result["cache_reason"] == "precomputed_operational_seed_plan"


def test_compute_probe_prepass_can_use_seed_files_as_connected_map(tmp_path: Path) -> None:
    repo_path = tmp_path / "seed-only-connected-map-repo"
    repo_path.mkdir()
    operational_seed_plan = {
        "candidate_file_paths": ["src/main.shader", "src/include.cginc"],
        "config_paths": ["src/render.meta"],
        "detected_ecosystems": ["shaderlab"],
        "entrypoint_files": ["src/main.shader", "src/include.cginc"],
        "operational_ecosystems": ["shaderlab"],
        "support_roots": ["src"],
    }

    deps = probe_runtime_support.ProbePrepassDependencies(
        default_exclude_patterns=[],
        default_include_patterns=["**/*"],
        prepass_cache_schema_version="test",
        build_connected_dependency_map=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("seed-only connected-map path should bypass dependency graph construction")
        ),
        candidate_config_focus_paths=lambda **kwargs: ["src/render.meta"],
        candidate_solutions=lambda diagnostics: [],
        derive_operational_seed_plan_without_diagnostics=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("precomputed operational seed plan should bypass derivation")
        ),
        effective_focus_paths_for_snapshot=lambda **kwargs: sorted(
            set(kwargs["connected_files"]) | set(kwargs["config_focus_paths"])
        ),
        focus_paths_from_diagnostics=lambda **kwargs: ["src"],
        inventory_repo_surface=lambda **kwargs: {"file_count": len(kwargs["focus_paths"])},
        parse_repository_diagnostics=lambda **kwargs: [],
        resolve_diagnostic_base_path=lambda repo_path, diagnostic_command, diagnostic_base_path: repo_path,
        resolve_diagnostic_project_path=lambda repo_path, diagnostic_command, diagnostic_base_path: None,
        run_command=lambda repo_path, diagnostic_command: {
            "combined_output": "",
            "command": diagnostic_command,
            "elapsed_ms": 0.0,
            "exit_code": 0,
            "returncode": 0,
        },
    )

    result = probe_runtime_support.compute_probe_prepass(
        repo_path=repo_path,
        focus_paths=["src"],
        operational_seed_plan=operational_seed_plan,
        use_seed_files_as_connected_map=True,
        diagnostic_command=None,
        diagnostic_base_path=None,
        repository_runtime_root=tmp_path / "runtime",
        max_files=32,
        max_file_size_bytes=50_000,
        max_dependency_depth=2,
        max_connected_files=16,
        deps=deps,
    )

    assert result["connected_map"]["seed_files"] == ["src/main.shader", "src/include.cginc"]
    assert result["connected_map"]["connected_files"] == ["src/main.shader", "src/include.cginc"]
    assert result["connected_map"]["connected_file_count"] == 2
    assert result["connected_map"]["resolved_dependency_edges"] == 0
    assert result["effective_focus_paths"] == [
        "src/include.cginc",
        "src/main.shader",
        "src/render.meta",
    ]
