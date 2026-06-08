"""Tests for repository_intelligence_real_repo_probe: repo_profile.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_repo_profile_candidate_paths_include_uppercase_r_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "r-candidate-paths-repo"
    (repo_path / "R").mkdir(parents=True)
    (repo_path / "DESCRIPTION").write_text(
        "Package: acme\nVersion: 0.0.0\n",
        encoding="utf-8",
    )
    (repo_path / "R" / "main.R").write_text(
        "run <- function() {\n  1\n}\n",
        encoding="utf-8",
    )

    candidate_paths = _repo_profile_candidate_paths(
        repo_path=repo_path,
        focus_paths=[],
        max_files=128,
    )

    assert "R/main.R" in candidate_paths


def test_repo_profile_config_paths_discovers_nested_pubspec_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "dart-workspace-config-repo"
    (repo_path / "pkgs" / "app").mkdir(parents=True)
    (repo_path / "pkgs" / "http").mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "pkgs" / "http" / "pubspec.yaml").write_text(
        "name: http\n",
        encoding="utf-8",
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == [
        "pkgs/app/pubspec.yaml",
        "pkgs/http/pubspec.yaml",
    ]


def test_repo_profile_config_paths_discovers_tsconfig_variants(tmp_path: Path) -> None:
    repo_path = tmp_path / "tsconfig-variant-config-repo"
    (repo_path / "packages" / "web").mkdir(parents=True)
    (repo_path / "tsconfig.base.json").write_text("{}", encoding="utf-8")
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text(
        "{}",
        encoding="utf-8",
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == [
        "packages/web/tsconfig.app.json",
        "tsconfig.base.json",
    ]


