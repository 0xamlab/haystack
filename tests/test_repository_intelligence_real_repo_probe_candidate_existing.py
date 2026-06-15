"""Tests for repository_intelligence_real_repo_probe: candidate_existing.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_candidate_existing_leaf_roots_prunes_auxiliary_bin_roots(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "pkg" / "lib").mkdir(parents=True)
    (repo_path / "pkg" / "bin").mkdir(parents=True)

    assert _candidate_existing_leaf_roots(
        repo_path,
        roots={"pkg/lib", "pkg/bin"},
    ) == ["pkg/lib"]


def test_candidate_existing_leaf_roots_keeps_bin_without_sibling_code_root(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "pkg" / "bin").mkdir(parents=True)

    assert _candidate_existing_leaf_roots(
        repo_path,
        roots={"pkg/bin"},
    ) == ["pkg/bin"]


def test_candidate_existing_leaf_roots_prunes_top_level_bin_without_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "pkg" / "lib").mkdir(parents=True)

    assert _candidate_existing_leaf_roots(
        repo_path,
        roots={"bin", "pkg/lib"},
        entrypoint_paths={"pkg/lib/main.rb"},
    ) == ["pkg/lib"]


def test_candidate_existing_leaf_roots_keeps_top_level_bin_with_entrypoints(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "pkg" / "lib").mkdir(parents=True)

    assert _candidate_existing_leaf_roots(
        repo_path,
        roots={"bin", "pkg/lib"},
        entrypoint_paths={"bin/tool.rb", "pkg/lib/main.rb"},
    ) == ["bin", "pkg/lib"]


def test_candidate_existing_leaf_roots_drops_parent_roots_when_children_exist(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "leaf-support-roots-repo"
    (repo_path / "app" / "src" / "main" / "groovy").mkdir(parents=True)
    (repo_path / "app" / "src" / "main" / "java").mkdir(parents=True)

    leaf_roots = _candidate_existing_leaf_roots(
        repo_path,
        roots={"app", "app/src", "app/src/main/groovy", "app/src/main/java"},
    )

    assert leaf_roots == ["app/src/main/groovy", "app/src/main/java"]


def test_matches_focus_paths_caches_normalized_focus_specs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_normalize = repository_service._normalize_repository_relative_path
    call_count = {"value": 0}

    def counting_normalize(path: str) -> str:
        call_count["value"] += 1
        return original_normalize(path)

    monkeypatch.setattr(
        repository_service,
        "_normalize_repository_relative_path",
        counting_normalize,
    )

    focus_paths = ["packages/RAD Studio 10.0", "packages/RAD Studio 10.1"]

    assert probe_module._matches_focus_paths(
        "packages/RAD Studio 10.0/VSoft.DUnitXWinR.dpk",
        focus_paths,
    )
    first_call_count = call_count["value"]

    assert probe_module._matches_focus_paths(
        "packages/RAD Studio 10.1/VSoft.DUnitXWinR.dpk",
        list(reversed(focus_paths)),
    )
    assert call_count["value"] == first_call_count
