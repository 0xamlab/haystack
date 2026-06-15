"""Tests for repository_intelligence_real_repo_probe: repo_profile.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from collections import Counter
import os
import stat
from pathlib import PurePosixPath

import benchmarks.repository_intelligence_real_repo_probe_profile_path_classification_support as classification_support
import benchmarks.repository_intelligence_real_repo_probe_profile_build_tooling_support as build_tooling_support
import benchmarks.repository_intelligence_real_repo_probe_profile_candidate_languages_support as candidate_language_support
import benchmarks.repository_intelligence_real_repo_probe_collection_support as collection_support
import benchmarks.repository_intelligence_real_repo_probe_profile_ecosystem_support as ecosystem_support
import benchmarks.repository_intelligence_real_repo_probe_profile_project_languages_b_support as project_languages_b_support
import benchmarks.repository_intelligence_real_repo_probe_profile_path_selection_support as path_selection_support
import benchmarks.repository_intelligence_real_repo_probe_profile_qml_chapel_support as qml_chapel_support
import benchmarks.repository_intelligence_real_repo_probe_profile_server_templates_support as server_template_support
import benchmarks.repository_intelligence_real_repo_probe_seed_plan_support as seed_plan_support
from apps.api_server.services.repository_intelligence_adapters import (
    apex as repository_apex_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    eiffel_analysis_support as repository_eiffel_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    eiffel_primitives as repository_eiffel_primitives,
)

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


def test_repo_profile_manifest_name_uses_cached_suffix_classifier() -> None:
    classification_support._is_repo_profile_manifest_name.cache_clear()

    assert classification_support._is_repo_profile_manifest_name("project.vbp") is True
    first_cache_info = classification_support._is_repo_profile_manifest_name.cache_info()

    assert classification_support._is_repo_profile_manifest_name("project.vbp") is True
    second_cache_info = classification_support._is_repo_profile_manifest_name.cache_info()

    assert classification_support._is_repo_profile_manifest_name("tsconfig.base.json") is True
    assert classification_support._is_repo_profile_manifest_name("notes.txt") is False
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_repo_profile_config_paths_reuses_cached_repo_listing_for_focus_ancestors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "focused-config-cache-repo"
    (repo_path / "packages" / "web" / "src").mkdir(parents=True)
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (repo_path / "tsconfig.base.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files_for_focus_paths",
        lambda _repo_path, *, focus_paths: ["packages/web/src/main.ts"],
    )
    collection_support.clear_git_repo_relative_files_cache()
    collection_support._GIT_REPO_RELATIVE_FILES_CACHE[str(repo_path.resolve())] = [
        "packages/web/src/main.ts",
        "packages/web/tsconfig.app.json",
        "tsconfig.base.json",
    ]

    def fail_iterdir(self: Path):
        raise AssertionError(
            "cached repo listing should satisfy focus-ancestor config discovery without iterdir"
        )

    monkeypatch.setattr(Path, "iterdir", fail_iterdir)

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=["packages/web/src"],
    )

    assert config_paths == [
        "packages/web/tsconfig.app.json",
        "tsconfig.base.json",
    ]
    collection_support.clear_git_repo_relative_files_cache()


def test_repo_profile_config_paths_skip_expensive_specialized_checks_for_irrelevant_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "repo-profile-config-prefilter-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "packages" / "web").mkdir(parents=True)
    (repo_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        probe_module,
        "_is_cfml_box_config_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("CFML config detection should not run for irrelevant files")
        ),
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == ["packages/web/tsconfig.app.json"]


def test_repo_profile_config_paths_skip_filesystem_checks_for_irrelevant_git_listed_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "repo-profile-config-git-prefilter-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "packages" / "web").mkdir(parents=True)
    (repo_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: ["docs/guide.md", "packages/web/tsconfig.app.json"],
    )

    original_lstat = Path.lstat

    def _guarded_lstat(self: Path):
        if self.name == "guide.md":
            raise AssertionError("filesystem checks should not run for irrelevant git-listed files")
        return original_lstat(self)

    monkeypatch.setattr(Path, "lstat", _guarded_lstat)

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == ["packages/web/tsconfig.app.json"]


def test_repo_profile_config_paths_skip_focus_matching_for_irrelevant_git_listed_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "repo-profile-config-focus-prefilter-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "packages" / "web").mkdir(parents=True)
    (repo_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: ["docs/guide.md", "packages/web/tsconfig.app.json"],
    )

    original_matches_focus_paths = probe_module._matches_focus_paths

    def _guarded_matches_focus_paths(relative_path: str, focus_paths: list[str]) -> bool:
        if relative_path == "docs/guide.md":
            raise AssertionError("focus matching should not run for irrelevant git-listed files")
        return original_matches_focus_paths(relative_path, focus_paths)

    monkeypatch.setattr(
        probe_module,
        "_matches_focus_paths",
        _guarded_matches_focus_paths,
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=["packages/web/src"],
    )

    assert config_paths == ["packages/web/tsconfig.app.json"]


def test_repo_profile_config_paths_skip_manifest_detection_for_irrelevant_git_listed_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "repo-profile-config-manifest-prefilter-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "packages" / "web").mkdir(parents=True)
    (repo_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: ["docs/guide.md", "packages/web/tsconfig.app.json"],
    )

    original_is_repo_profile_manifest_name = probe_module._is_repo_profile_manifest_name

    def _guarded_is_repo_profile_manifest_name(name: str) -> bool:
        if name == "guide.md":
            raise AssertionError(
                "manifest detection should not run for irrelevant git-listed files"
            )
        return original_is_repo_profile_manifest_name(name)

    monkeypatch.setattr(
        probe_module,
        "_is_repo_profile_manifest_name",
        _guarded_is_repo_profile_manifest_name,
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == ["packages/web/tsconfig.app.json"]


def test_repo_profile_config_paths_reuse_unfocused_cache_for_focused_lookups(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "repo-profile-config-cache-reuse-repo"
    (repo_path / "packages" / "web").mkdir(parents=True)
    (repo_path / "packages" / "api").mkdir(parents=True)
    (repo_path / "package.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text("{}", encoding="utf-8")
    (repo_path / "packages" / "api" / "tsconfig.app.json").write_text("{}", encoding="utf-8")
    git_list_calls = {"value": 0}

    def _counting_git_repo_relative_files(_repo_path: Path) -> list[str]:
        git_list_calls["value"] += 1
        return [
            "package.json",
            "packages/web/tsconfig.app.json",
            "packages/api/tsconfig.app.json",
        ]

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        _counting_git_repo_relative_files,
    )
    path_selection_support.clear_repo_profile_config_path_cache()

    unfocused_config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )
    focused_config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=["packages/web/src"],
    )

    assert unfocused_config_paths == [
        "package.json",
        "packages/api/tsconfig.app.json",
        "packages/web/tsconfig.app.json",
    ]
    assert focused_config_paths == [
        "package.json",
        "packages/web/tsconfig.app.json",
    ]
    assert git_list_calls["value"] == 1


def test_repo_profile_config_paths_respect_focus_ancestors_without_losing_root_manifests(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "focused-config-repo"
    (repo_path / "packages" / "web" / "src").mkdir(parents=True)
    (repo_path / "packages" / "api").mkdir(parents=True)
    (repo_path / "package.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text("{}", encoding="utf-8")
    (repo_path / "packages" / "api" / "tsconfig.app.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: [
            "package.json",
            "packages/web/tsconfig.app.json",
            "packages/api/tsconfig.app.json",
        ],
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=["packages/web/src"],
    )

    assert config_paths == [
        "package.json",
        "packages/web/tsconfig.app.json",
    ]


def test_repo_profile_config_paths_use_focused_git_listing_without_losing_ancestor_configs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "focused-config-git-listing-repo"
    (repo_path / "packages" / "web" / "src").mkdir(parents=True)
    (repo_path / "packages" / "api").mkdir(parents=True)
    (repo_path / "package.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "packages" / "web" / "tsconfig.app.json").write_text("{}", encoding="utf-8")
    (repo_path / "packages" / "web" / "src" / "tsconfig.feature.json").write_text(
        "{}",
        encoding="utf-8",
    )
    (repo_path / "packages" / "api" / "tsconfig.app.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: (_ for _ in ()).throw(
            AssertionError("focused config lookup should not use whole-repo git listing")
        ),
    )
    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files_for_focus_paths",
        lambda _repo_path, *, focus_paths: ["packages/web/src/tsconfig.feature.json"],
    )
    path_selection_support.clear_repo_profile_config_path_cache()

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=["packages/web/src"],
    )

    assert config_paths == [
        "package.json",
        "packages/web/src/tsconfig.feature.json",
        "packages/web/tsconfig.app.json",
    ]


def test_repo_profile_config_paths_focus_ancestor_scan_avoids_path_lstat_for_irrelevant_siblings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "focused-config-ancestor-scandir-repo"
    (repo_path / "packages" / "web" / "src").mkdir(parents=True)
    (repo_path / "package.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "README.md").write_text("# Readme\n", encoding="utf-8")
    (repo_path / "packages" / "web" / "src" / "main.ts").write_text(
        "export const main = true;\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files_for_focus_paths",
        lambda _repo_path, *, focus_paths: ["packages/web/src/main.ts"],
    )
    collection_support.clear_git_repo_relative_files_cache()
    path_selection_support.clear_repo_profile_config_path_cache()

    original_lstat = Path.lstat

    def _guarded_lstat(self: Path, *args, **kwargs):
        if self == repo_path / "README.md":
            raise AssertionError("focus-ancestor fallback should not lstat irrelevant siblings")
        return original_lstat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", _guarded_lstat)

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=["packages/web/src"],
    )

    assert config_paths == ["package.json"]


def test_git_repo_relative_files_for_focus_paths_keeps_large_sibling_sets_scoped(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "focused-git-sibling-scope-repo"
    sibling_names = [
        "a2c-nums",
        "aa-draw",
        "ab-annotate",
        "abbr",
        "abyss-book",
        "academi-notes-gr",
    ]
    for sibling_name in sibling_names:
        package_dir = repo_path / "packages" / "preview" / sibling_name
        package_dir.mkdir(parents=True)
        (package_dir / "main.typ").write_text(
            f"#let {sibling_name.replace('-', '_')} = 1\n",
            encoding="utf-8",
        )
    unrelated_dir = repo_path / "packages" / "preview" / "zeta-template"
    unrelated_dir.mkdir(parents=True)
    (unrelated_dir / "ignored.typ").write_text("#let ignored = 1\n", encoding="utf-8")
    _init_git_repo(repo_path)
    collection_support.clear_git_repo_relative_files_cache()

    focused_paths = collection_support._git_repo_relative_files_for_focus_paths(
        repo_path,
        focus_paths=[f"packages/preview/{sibling_name}" for sibling_name in sibling_names],
    )

    assert focused_paths is not None
    assert "packages/preview/zeta-template/ignored.typ" not in focused_paths
    assert {
        relative_path.rsplit("/", 1)[0]
        for relative_path in focused_paths
        if relative_path.endswith(".typ")
    } == {f"packages/preview/{sibling_name}" for sibling_name in sibling_names}


def test_git_repo_relative_files_reuses_cached_focus_listing_for_sparse_checkout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "focused-git-sparse-reuse-repo"
    (repo_path / "source").mkdir(parents=True)
    (repo_path / "source" / "index.haml").write_text("%main\n", encoding="utf-8")
    (repo_path / "source" / "layout.haml").write_text("%section\n", encoding="utf-8")
    _init_git_repo(repo_path)
    sparse_checkout_path = repo_path / ".git" / "info" / "sparse-checkout"
    sparse_checkout_path.parent.mkdir(parents=True, exist_ok=True)
    sparse_checkout_path.write_text(
        "/source\n"
        "/source/**\n",
        encoding="utf-8",
    )

    collection_support.clear_git_repo_relative_files_cache()
    collection_support.clear_support_root_caches()
    repo_cache_key = str(repo_path.resolve())
    collection_support._GIT_REPO_RELATIVE_FOCUS_FILES_CACHE[
        (repo_cache_key, ("source",))
    ] = [
        "source/index.haml",
        "source/layout.haml",
    ]

    def _unexpected_git_command(*_args, **_kwargs):
        raise AssertionError("sparse checkout should reuse cached focused listing")

    monkeypatch.setattr(repository_service, "_git_command", _unexpected_git_command)

    relative_paths = collection_support._git_repo_relative_files(repo_path)

    assert relative_paths == [
        "source/index.haml",
        "source/layout.haml",
    ]


def test_git_repo_relative_files_for_focus_paths_reuses_seeded_repo_listing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "seeded-git-repo-listing-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "sinatra.rb").write_text("module Sinatra; end\n", encoding="utf-8")
    (repo_path / "README.md").write_text("# Sinatra\n", encoding="utf-8")
    _init_git_repo(repo_path)

    collection_support.clear_git_repo_relative_files_cache()
    collection_support.seed_git_repo_relative_files_cache(
        repo_path,
        ["lib/sinatra.rb", "README.md"],
    )

    def _unexpected_git_command(*_args, **_kwargs):
        raise AssertionError("seeded repo listing should avoid an extra git ls-files call")

    monkeypatch.setattr(repository_service, "_git_command", _unexpected_git_command)

    relative_paths = collection_support._git_repo_relative_files_for_focus_paths(
        repo_path,
        focus_paths=["lib"],
    )

    assert relative_paths == ["lib/sinatra.rb"]


def test_git_repo_relative_files_uses_tracked_only_listing_for_clean_clone_hint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "clean-clone-git-listing-repo"
    repo_path.mkdir()

    collection_support.clear_git_repo_relative_files_cache()
    collection_support.set_git_repo_assume_clean_clone(repo_path, True)
    commands: list[tuple[str, ...]] = []

    def _fake_git_command(command: list[str], **_kwargs):
        commands.append(tuple(command))
        return ""

    monkeypatch.setattr(repository_service, "_git_command", _fake_git_command)

    try:
        relative_paths = collection_support._git_repo_relative_files(repo_path)
    finally:
        collection_support.set_git_repo_assume_clean_clone(repo_path, False)

    assert relative_paths == []
    assert commands == [
        ("git", "-C", str(repo_path), "ls-files", "--cached"),
    ]


def test_git_repo_relative_files_for_focus_paths_uses_tracked_only_listing_for_clean_clone_hint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "clean-clone-focused-git-listing-repo"
    repo_path.mkdir()

    collection_support.clear_git_repo_relative_files_cache()
    collection_support.set_git_repo_assume_clean_clone(repo_path, True)
    commands: list[tuple[str, ...]] = []

    def _fake_git_command(command: list[str], **_kwargs):
        commands.append(tuple(command))
        return ""

    monkeypatch.setattr(repository_service, "_git_command", _fake_git_command)

    try:
        relative_paths = collection_support._git_repo_relative_files_for_focus_paths(
            repo_path,
            focus_paths=["src"],
        )
    finally:
        collection_support.set_git_repo_assume_clean_clone(repo_path, False)

    assert relative_paths == []
    assert commands == [
        ("git", "-C", str(repo_path), "ls-files", "--cached", "--", "src"),
    ]


def test_seed_git_repo_relative_files_cache_can_trust_canonical_listing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "canonical-seeded-git-repo-listing-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "sinatra.rb").write_text("module Sinatra; end\n", encoding="utf-8")
    _init_git_repo(repo_path)

    collection_support.clear_git_repo_relative_files_cache()

    def _unexpected_normalize(_raw: str) -> str:
        raise AssertionError("canonical seed path should not renormalize tracked listings")

    monkeypatch.setattr(
        repository_service,
        "_normalize_repository_relative_path",
        _unexpected_normalize,
    )

    collection_support.seed_git_repo_relative_files_cache(
        repo_path,
        ["lib/sinatra.rb"],
        relative_paths_are_canonical=True,
    )

    relative_paths = collection_support._git_repo_relative_files_for_focus_paths(
        repo_path,
        focus_paths=["lib"],
    )

    assert relative_paths == ["lib/sinatra.rb"]


def test_compact_focus_paths_for_git_listing_still_collapses_small_sibling_sets() -> None:
    compacted = collection_support._compact_focus_paths_for_git_listing(
        (
            "packages/web/src",
            "packages/web/tests",
        )
    )

    assert compacted == ("packages/web",)


def test_repo_profile_config_paths_do_not_promote_box_json_without_cfml_sources(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "box-json-non-cfml-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "box.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == []


def test_repo_profile_config_paths_reuses_cached_repo_listing_for_non_cfml_box_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "cached-box-json-non-cfml-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "box.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")

    collection_support.clear_git_repo_relative_files_cache()
    collection_support._GIT_REPO_RELATIVE_FILES_CACHE[str(repo_path.resolve())] = [
        "box.json",
        "docs/guide.md",
    ]
    classification_support.clear_probe_language_for_path_cache()
    path_selection_support.clear_repo_profile_config_path_cache()
    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: ["box.json", "docs/guide.md"],
    )
    monkeypatch.setattr(
        os,
        "walk",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cached repo listing should avoid os.walk for non-CFML box.json")
        ),
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == []


def test_repo_profile_config_paths_reuses_cached_repo_listing_for_cfml_box_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "cached-box-json-cfml-repo"
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "box.json").write_text("{}\n", encoding="utf-8")
    (repo_path / "Application.cfc").write_text(
        "component {}\n",
        encoding="utf-8",
    )
    (repo_path / "public" / "index.cfm").write_text(
        "<cfoutput>Hello</cfoutput>\n",
        encoding="utf-8",
    )

    collection_support.clear_git_repo_relative_files_cache()
    collection_support._GIT_REPO_RELATIVE_FILES_CACHE[str(repo_path.resolve())] = [
        "Application.cfc",
        "box.json",
        "public/index.cfm",
    ]
    classification_support.clear_probe_language_for_path_cache()
    path_selection_support.clear_repo_profile_config_path_cache()
    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: ["Application.cfc", "box.json", "public/index.cfm"],
    )
    monkeypatch.setattr(
        os,
        "walk",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cached repo listing should avoid os.walk for CFML box.json")
        ),
    )

    config_paths = _repo_profile_config_paths(
        repo_path=repo_path,
        focus_paths=[],
    )

    assert config_paths == ["box.json"]


def test_probe_language_for_path_detects_cmakelists_manifest(tmp_path: Path) -> None:
    repo_path = tmp_path / "cmake-language-detection-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\nproject(acme LANGUAGES CXX)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

    assert probe_module._probe_language_for_path("CMakeLists.txt", repo_path=repo_path) == "cmake"
    assert probe_module._probe_language_for_path(
        "examples/demo/CMakeLists.txt",
        repo_path=repo_path,
    ) == "cmake"


def test_probe_language_for_path_short_circuits_cmakelists_manifest_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "cmake-fast-language-detection-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\nproject(acme)\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module.repository_service,
        "_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cmake manifest hint should bypass generic language probing")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("CMakeLists.txt", repo_path=repo_path) == "cmake"


def test_probe_language_for_path_short_circuits_direct_text_suffix_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "direct-text-suffix-fast-path-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "index.org").write_text("* Index\n", encoding="utf-8")

    monkeypatch.setattr(
        classification_support,
        "_probe_language_repo_hint",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("direct text suffix hint should bypass repo-hint probing")
        ),
    )
    monkeypatch.setattr(
        probe_module.repository_service,
        "_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("direct text suffix hint should bypass generic language probing")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("docs/index.org", repo_path=repo_path) == "org"


def test_probe_language_for_path_strips_quotes_before_direct_text_suffix_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "quoted-direct-text-suffix-fast-path-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "index.org").write_text("* Index\n", encoding="utf-8")

    monkeypatch.setattr(
        classification_support,
        "_probe_language_repo_hint",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("quoted direct text suffix hint should bypass repo-hint probing")
        ),
    )
    monkeypatch.setattr(
        probe_module.repository_service,
        "_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("quoted direct text suffix hint should bypass generic language probing")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path('"docs/index.org"', repo_path=repo_path) == "org"


def test_probe_language_for_path_short_circuits_direct_tcl_suffix_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "direct-tcl-suffix-fast-path-repo"
    (repo_path / "pkg").mkdir(parents=True)
    (repo_path / "pkg" / "main.tcl").write_text("proc greet {} { return ok }\n", encoding="utf-8")

    original_read_text = Path.read_text

    def _guarded_read_text(self: Path, *args, **kwargs) -> str:
        if self == repo_path / "pkg" / "main.tcl":
            raise AssertionError("tcl suffix hint should bypass reading source text")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _guarded_read_text)
    monkeypatch.setattr(
        probe_module.repository_service,
        "_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("tcl suffix hint should bypass generic language probing")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("pkg/main.tcl", repo_path=repo_path) == "tcl"


def test_probe_language_for_path_reads_ambiguous_fs_sources(tmp_path: Path) -> None:
    repo_path = tmp_path / "forth-fsharp-language-detection-repo"
    (repo_path / "kernel").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "kernel" / "main.fs").write_text(
        ": main 1 ;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Program.fs").write_text(
        "module Demo\nlet main = 1\n",
        encoding="utf-8",
    )

    assert probe_module._probe_language_for_path("kernel/main.fs", repo_path=repo_path) == "forth"
    assert probe_module._probe_language_for_path("src/Program.fs", repo_path=repo_path) == "fsharp"


def test_probe_language_for_path_uses_fsharp_project_context_without_reading_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "fsharp-project-context-repo"
    (repo_path / "src" / "Host").mkdir(parents=True)
    (repo_path / "src" / "Host" / "Host.fsproj").write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"></Project>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Host" / "Program.fs").write_text(
        "module Host\nlet main = 1\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text

    def _guarded_read_text(self: Path, *args, **kwargs) -> str:
        if self == repo_path / "src" / "Host" / "Program.fs":
            raise AssertionError("fsharp project context should avoid reading ambiguous .fs source")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _guarded_read_text)
    monkeypatch.setattr(
        probe_module.repository_service.forth_adapter,
        "is_probable_forth_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("fsharp project context should bypass forth detection for .fs sources")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("src/Host/Program.fs", repo_path=repo_path) == "fsharp"


def test_eiffel_project_config_path_reuses_repo_source_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-project-config-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "project.ecf").write_text(
        '<system name="demo"><target name="demo"/></system>\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    call_counts = {"probe_language": 0}

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        lambda repo_path_arg: ("project.ecf", "src/application.e"),
    )
    monkeypatch.setattr(
        classification_support,
        "_probe_language_for_path",
        lambda path, repo_path=None: call_counts.__setitem__(
            "probe_language", call_counts["probe_language"] + 1
        )
        or ("eiffel" if str(path).endswith(".e") else "unknown"),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._is_eiffel_project_config_path(repo_path, "project.ecf") is True
    assert probe_module._is_eiffel_project_config_path(repo_path, "project.ecf") is True
    assert call_counts["probe_language"] == 1


def test_dm_project_config_path_reuses_cached_manifest_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "dm-project-config-cache-repo"
    repo_path.mkdir(parents=True)
    manifest_path = repo_path / "game.dme"
    manifest_path.write_text(
        "// comment\n#define PROJECT_NAME \"demo\"\n#include \"code/game.dm\"\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text
    read_counts = {"manifest_reads": 0}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == manifest_path:
            read_counts["manifest_reads"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    classification_support.clear_dm_project_config_path_cache()

    assert probe_module._is_dm_project_config_path(repo_path, "game.dme") is True
    assert probe_module._is_dm_project_config_path(repo_path, "game.dme") is True
    assert read_counts["manifest_reads"] == 1


def test_eiffel_profile_hints_from_candidates_reuse_cached_source_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-source-profile-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    source_file = repo_path / "src" / "application.e"
    source_file.write_text(
        "class APPLICATION\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    original_read_text = Path.read_text
    call_counts = {"source_reads": 0}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == source_file:
            call_counts["source_reads"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "eiffel",
    )
    build_tooling_support.clear_eiffel_source_profile_cache()

    first_entrypoints, _first_roots, _first_configs = probe_module._eiffel_profile_hints_from_candidates(
        repo_path,
        ["src/application.e"],
    )
    second_entrypoints, _second_roots, _second_configs = probe_module._eiffel_profile_hints_from_candidates(
        repo_path,
        ["src/application.e"],
    )

    assert first_entrypoints == {"src/application.e"}
    assert second_entrypoints == {"src/application.e"}
    assert call_counts["source_reads"] == 1


def test_eiffel_profile_hints_from_candidates_skip_probe_language_for_eiffel_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-source-profile-no-probe-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: (_ for _ in ()).throw(
            AssertionError("eiffel source candidates should not require probe_language")
        ),
    )
    build_tooling_support.clear_eiffel_source_profile_cache()

    entrypoints, support_roots, config_paths = probe_module._eiffel_profile_hints_from_candidates(
        repo_path,
        ["src/application.e"],
    )

    assert entrypoints == {"src/application.e"}
    assert support_roots == {"src"}
    assert config_paths == set()


def test_eiffel_profile_hints_from_candidates_preferred_roots_skip_unrelated_source_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-preferred-root-traversal-repo"
    (repo_path / "src").mkdir(parents=True)
    application_file = repo_path / "src" / "application.e"
    helper_file = repo_path / "src" / "helper.e"
    unused_file = repo_path / "src" / "unused.e"
    application_file.write_text(
        "class APPLICATION\n"
        "inherit\n"
        "    HELPER\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    helper_file.write_text(
        "class HELPER\nfeature\n    build\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    unused_file.write_text(
        "class UNUSED\nfeature\n    noop\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    original_read_text = Path.read_text
    observed_reads = {"unused": 0}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == unused_file:
            observed_reads["unused"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    build_tooling_support.clear_eiffel_source_profile_cache()

    entrypoints, support_roots, config_paths = probe_module._eiffel_profile_hints_from_candidates(
        repo_path,
        ["src/application.e", "src/helper.e", "src/unused.e"],
        preferred_root_class_names=("APPLICATION",),
    )

    assert entrypoints == {"src/application.e"}
    assert support_roots == {"src"}
    assert config_paths == set()
    assert observed_reads["unused"] == 0


def test_eiffel_profile_hints_from_candidates_collapse_nested_import_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "eiffel-nested-import-roots-repo"
    nested_root = repo_path / "library" / "demo" / "src"
    (nested_root / "encoding" / "implementation").mkdir(parents=True)
    (nested_root / "application.e").write_text(
        "class APPLICATION\n"
        "inherit\n"
        "    ENCODING_I\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    (nested_root / "encoding" / "implementation" / "encoding_i.e").write_text(
        "class ENCODING_I\nfeature\n    convert\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    build_tooling_support.clear_eiffel_source_profile_cache()

    entrypoints, support_roots, config_paths = probe_module._eiffel_profile_hints_from_candidates(
        repo_path,
        [
            "library/demo/src/application.e",
            "library/demo/src/encoding/implementation/encoding_i.e",
        ],
        preferred_root_class_names=("APPLICATION",),
    )

    assert entrypoints == {"library/demo/src/application.e"}
    assert support_roots == {"library/demo/src"}
    assert config_paths == set()


def test_eiffel_profile_hints_from_candidates_large_fallback_skips_full_source_profile_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-large-fallback-fast-path-repo"
    fast_roots = [
        repo_path / "library" / "alpha" / "src",
        repo_path / "library" / "beta" / "src",
    ]
    for root in fast_roots:
        root.mkdir(parents=True, exist_ok=True)
    for index in range(20):
        (fast_roots[0] / f"alpha_{index}.e").write_text(
            f"class ALPHA_{index}\nfeature\n    make\n        do\n        end\nend\n",
            encoding="utf-8",
        )
        (fast_roots[1] / f"beta_{index}.e").write_text(
            f"class BETA_{index}\nfeature\n    make\n        do\n        end\nend\n",
            encoding="utf-8",
        )

    candidate_file_paths = sorted(
        str(path.relative_to(repo_path).as_posix())
        for path in repo_path.rglob("*.e")
        if path.is_file()
    )

    monkeypatch.setattr(
        build_tooling_support,
        "_cached_eiffel_source_profile",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("large Eiffel fallback should avoid full source-profile scans")
        ),
    )
    build_tooling_support.clear_eiffel_source_profile_cache()

    entrypoints, support_roots, config_paths = probe_module._eiffel_profile_hints_from_candidates(
        repo_path,
        candidate_file_paths,
    )

    assert config_paths == set()
    assert support_roots == {"library/alpha/src", "library/beta/src"}
    assert entrypoints == {
        "library/alpha/src/alpha_0.e",
        "library/alpha/src/alpha_1.e",
        "library/alpha/src/alpha_10.e",
        "library/alpha/src/alpha_11.e",
        "library/alpha/src/alpha_12.e",
        "library/alpha/src/alpha_13.e",
        "library/alpha/src/alpha_14.e",
        "library/beta/src/beta_0.e",
    }


def test_cached_eiffel_source_profile_reuses_single_stripped_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-source-profile-strip-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\n"
        "feature\n"
        "    make -- inline comment\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    original_strip_comments = repository_eiffel_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(repository_eiffel_primitives, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_eiffel_analysis_support, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_service.eiffel_adapter, "strip_comments", counting_strip_comments)
    build_tooling_support.clear_eiffel_source_profile_cache()

    source_profile = build_tooling_support._cached_eiffel_source_profile(
        repo_path,
        "src/application.e",
    )

    assert source_profile is not None
    assert "src/application.e" in source_profile.aliases
    assert "src/application" in source_profile.aliases
    assert "application" in source_profile.aliases
    assert "APPLICATION" in source_profile.aliases
    assert "make" not in source_profile.aliases
    assert strip_call_count["value"] == 1


def test_apex_profile_hints_strip_comments_once_per_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "apex-profile-strip-cache-repo"
    (repo_path / "force-app" / "main" / "default" / "classes").mkdir(parents=True)
    (repo_path / "force-app" / "main" / "default" / "triggers").mkdir(parents=True)
    (repo_path / "sfdx-project.json").write_text(
        '{\n'
        '  "packageDirectories": [\n'
        '    { "path": "force-app", "default": true }\n'
        "  ]\n"
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
        / "classes"
        / "AccountTriggerHandlerTest.cls"
    ).write_text(
        "@IsTest\n"
        "private class AccountTriggerHandlerTest {\n"
        "    @IsTest static void testRun() {\n"
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

    original_strip_comments = repository_apex_adapter.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(repository_apex_adapter, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_service.apex_adapter, "strip_comments", counting_strip_comments)

    entrypoints, support_roots, config_paths = ecosystem_support._apex_profile_hints(
        repo_path,
        "sfdx-project.json",
    )

    assert entrypoints == {
        "force-app/main/default/classes/AccountTriggerHandler.cls",
        "force-app/main/default/triggers/AccountTrigger.trigger",
    }
    assert "force-app/main/default/classes" in support_roots
    assert "force-app/main/default/triggers" in support_roots
    assert config_paths == {"sfdx-project.json"}
    assert strip_call_count["value"] == 3


def test_labview_profile_hints_fallback_scans_project_tree_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "labview-profile-fallback-repo"
    (repo_path / "labview" / "Source").mkdir(parents=True)
    (repo_path / "labview" / "Controls").mkdir(parents=True)
    (repo_path / "labview" / "App.lvproj").write_text(
        "<Project>\n"
        "  <Item Name=\"Empty\" Type=\"Folder\" />\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "labview" / "Source" / "Main.vi").write_bytes(b"RSRC\r\n\x00\x03LVINLBVW")
    (repo_path / "labview" / "Source" / "Shared.lvlib").write_text(
        "<Library />\n",
        encoding="utf-8",
    )
    (repo_path / "labview" / "Controls" / "Config.ctl").write_bytes(b"RSRC\r\n\x00\x03LVCCLBVW")

    original_rglob = Path.rglob
    rglob_calls = {"value": 0}
    expected_search_root = (repo_path / "labview").resolve()

    def counting_rglob(self: Path, pattern: str):  # type: ignore[no-untyped-def]
        if self.resolve() == expected_search_root:
            rglob_calls["value"] += 1
            assert pattern == "*"
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", counting_rglob)

    entrypoints, support_roots, config_paths = ecosystem_support._labview_profile_hints(
        repo_path,
        "labview/App.lvproj",
    )

    assert entrypoints == {
        "labview/Source/Main.vi",
        "labview/Source/Shared.lvlib",
    }
    assert "labview" in support_roots
    assert "labview/Source" in support_roots
    assert "labview/Controls" in support_roots
    assert config_paths == {"labview/App.lvproj"}
    assert rglob_calls["value"] == 1


def test_cached_eiffel_source_profile_derives_module_aliases_without_full_alias_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-source-profile-alias-fast-path-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\n"
        "inherit\n"
        "    ANY\n"
        "feature\n"
        "    make\n"
        "        local\n"
        "            formatter: STRING\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )

    def _unexpected_module_aliases_for_path(*args, **kwargs):
        raise AssertionError("cached Eiffel source profiles should avoid full alias scans")

    monkeypatch.setattr(
        repository_service.eiffel_adapter,
        "module_aliases_for_path",
        _unexpected_module_aliases_for_path,
    )
    build_tooling_support.clear_eiffel_source_profile_cache()

    source_profile = build_tooling_support._cached_eiffel_source_profile(
        repo_path,
        "src/application.e",
    )

    assert source_profile is not None
    assert source_profile.aliases == (
        "APPLICATION",
        "application",
        "src/application",
        "src/application.e",
    )
    assert source_profile.dependency_targets == ("ANY",)


def test_eiffel_profile_hints_reuse_single_stripped_text_for_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-manifest-strip-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "project.ecf").write_text(
        '<system name="demo">\n'
        '  <target name="demo">\n'
        '    <root class="APPLICATION"/>\n'
        '    <cluster location="src"/> -- comment\n'
        "  </target>\n"
        "</system>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    original_strip_comments = repository_eiffel_primitives.strip_comments
    strip_call_count = {"value": 0}
    observed: dict[str, tuple[str, ...] | list[str]] = {}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    def _stubbed_profile_hints_from_candidates(
        repo_path_arg: Path,
        candidate_file_paths: list[str],
        *,
        preferred_root_class_names: tuple[str, ...] = (),
    ) -> tuple[set[str], set[str], set[str]]:
        observed["candidate_file_paths"] = candidate_file_paths
        observed["preferred_root_class_names"] = preferred_root_class_names
        return {"src/application.e"}, {"src"}, set()

    monkeypatch.setattr(repository_eiffel_primitives, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_eiffel_analysis_support, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_service.eiffel_adapter, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(
        probe_module,
        "_eiffel_profile_hints_from_candidates",
        _stubbed_profile_hints_from_candidates,
    )

    entrypoints, support_roots, config_paths = build_tooling_support._eiffel_profile_hints(
        repo_path,
        "project.ecf",
    )

    assert entrypoints == {"src/application.e"}
    assert "src" in support_roots
    assert config_paths == {"project.ecf"}
    assert observed["candidate_file_paths"] == ["src/application.e"]
    assert observed["preferred_root_class_names"] == ("APPLICATION",)
    assert strip_call_count["value"] == 1


def test_eiffel_profile_hints_reuse_cached_manifest_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-manifest-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "project.ecf").write_text(
        '<system name="demo">\n'
        '  <target name="demo">\n'
        '    <root class="APPLICATION"/>\n'
        '    <cluster location="src"/>\n'
        "  </target>\n"
        "</system>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    call_counts = {"profile_hints_from_candidates": 0}

    def _stubbed_profile_hints_from_candidates(
        repo_path_arg: Path,
        candidate_file_paths: list[str],
        *,
        preferred_root_class_names: tuple[str, ...] = (),
    ) -> tuple[set[str], set[str], set[str]]:
        call_counts["profile_hints_from_candidates"] += 1
        return {"src/application.e"}, {"src"}, set()

    monkeypatch.setattr(
        probe_module,
        "_eiffel_profile_hints_from_candidates",
        _stubbed_profile_hints_from_candidates,
    )
    build_tooling_support.clear_eiffel_source_profile_cache()

    first_entrypoints, first_support_roots, first_config_paths = build_tooling_support._eiffel_profile_hints(
        repo_path,
        "project.ecf",
    )
    second_entrypoints, second_support_roots, second_config_paths = build_tooling_support._eiffel_profile_hints(
        repo_path,
        "project.ecf",
    )

    assert first_entrypoints == {"src/application.e"}
    assert second_entrypoints == {"src/application.e"}
    assert first_support_roots == {"src"}
    assert second_support_roots == {"src"}
    assert first_config_paths == {"project.ecf"}
    assert second_config_paths == {"project.ecf"}
    assert call_counts["profile_hints_from_candidates"] == 1


def test_eiffel_profile_hints_normalize_manifest_support_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-manifest-support-root-normalization-repo"
    (repo_path / "library" / "demo" / "config" / "ecf").mkdir(parents=True)
    (repo_path / "library" / "demo" / "src").mkdir(parents=True)
    (repo_path / "library" / "demo" / "test" / "unit").mkdir(parents=True)
    (repo_path / "library" / "demo" / "config" / "ecf" / "project.ecf").write_text(
        '<system name="demo">\n'
        '  <target name="demo">\n'
        '    <root class="APPLICATION"/>\n'
        '    <cluster location="../src"/>\n'
        '    <cluster location="../test/unit"/>\n'
        "  </target>\n"
        "</system>\n",
        encoding="utf-8",
    )
    (repo_path / "library" / "demo" / "src" / "application.e").write_text(
        "class APPLICATION\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )

    def _stubbed_profile_hints_from_candidates(
        repo_path_arg: Path,
        candidate_file_paths: list[str],
        *,
        preferred_root_class_names: tuple[str, ...] = (),
    ) -> tuple[set[str], set[str], set[str]]:
        return {"library/demo/src/application.e"}, {"library/demo/src"}, set()

    monkeypatch.setattr(
        probe_module,
        "_eiffel_profile_hints_from_candidates",
        _stubbed_profile_hints_from_candidates,
    )
    build_tooling_support.clear_eiffel_source_profile_cache()

    entrypoints, support_roots, config_paths = build_tooling_support._eiffel_profile_hints(
        repo_path,
        "library/demo/config/ecf/project.ecf",
    )

    assert entrypoints == {"library/demo/src/application.e"}
    assert "library/demo" in support_roots
    assert "library/demo/src" in support_roots
    assert all("/test/" not in root for root in support_roots)
    assert config_paths == {"library/demo/config/ecf/project.ecf"}


def test_eiffel_profile_hints_use_git_listing_for_candidate_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-manifest-git-listing-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "project.ecf").write_text(
        '<system name="demo">\n'
        '  <target name="demo">\n'
        '    <root class="APPLICATION"/>\n'
        '    <cluster location="src"/>\n'
        "  </target>\n"
        "</system>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "utility.e").write_text(
        "class UTILITY\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    observed: dict[str, list[str] | tuple[str, ...]] = {}

    def _stubbed_profile_hints_from_candidates(
        repo_path_arg: Path,
        candidate_file_paths: list[str],
        *,
        preferred_root_class_names: tuple[str, ...] = (),
    ) -> tuple[set[str], set[str], set[str]]:
        observed["candidate_file_paths"] = candidate_file_paths
        observed["preferred_root_class_names"] = preferred_root_class_names
        return {"src/application.e"}, {"src"}, set()

    monkeypatch.setattr(
        collection_support,
        "_git_repo_relative_files",
        lambda _repo_path: ["project.ecf", "src/application.e", "src/utility.e"],
    )
    monkeypatch.setattr(
        probe_module,
        "_eiffel_profile_hints_from_candidates",
        _stubbed_profile_hints_from_candidates,
    )
    monkeypatch.setattr(
        Path,
        "rglob",
        lambda self, pattern: (_ for _ in ()).throw(
            AssertionError("git listing should avoid Eiffel source filesystem walks")
        ),
    )
    build_tooling_support.clear_eiffel_source_profile_cache()

    entrypoints, support_roots, config_paths = build_tooling_support._eiffel_profile_hints(
        repo_path,
        "project.ecf",
    )

    assert entrypoints == {"src/application.e"}
    assert support_roots == {"src"}
    assert config_paths == {"project.ecf"}
    assert observed["candidate_file_paths"] == ["src/application.e", "src/utility.e"]
    assert observed["preferred_root_class_names"] == ("APPLICATION",)


def test_eiffel_profile_hints_reuse_cached_git_listing_candidates_across_manifests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-manifest-shared-git-listing-repo"
    (repo_path / "src").mkdir(parents=True)
    for manifest_name in ("project_a.ecf", "project_b.ecf"):
        (repo_path / manifest_name).write_text(
            '<system name="demo">\n'
            '  <target name="demo">\n'
            '    <root class="APPLICATION"/>\n'
            '    <cluster location="src"/>\n'
            "  </target>\n"
            "</system>\n",
            encoding="utf-8",
        )
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "utility.e").write_text(
        "class UTILITY\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )

    git_listing_call_count = {"value": 0}

    def _stubbed_git_repo_relative_files(_repo_path: Path) -> list[str]:
        git_listing_call_count["value"] += 1
        return [
            "project_a.ecf",
            "project_b.ecf",
            "src/application.e",
            "src/utility.e",
        ]

    monkeypatch.setattr(
        collection_support,
        "_git_repo_relative_files",
        _stubbed_git_repo_relative_files,
    )
    build_tooling_support.clear_eiffel_source_profile_cache()

    first_entrypoints, _first_roots, _first_configs = build_tooling_support._eiffel_profile_hints(
        repo_path,
        "project_a.ecf",
    )
    second_entrypoints, _second_roots, _second_configs = build_tooling_support._eiffel_profile_hints(
        repo_path,
        "project_b.ecf",
    )

    assert "src/application.e" in first_entrypoints
    assert "src/application.e" in second_entrypoints
    assert git_listing_call_count["value"] == 1


def test_eiffel_source_like_root_cache_reuses_repeated_paths() -> None:
    build_tooling_support._cached_eiffel_source_like_root_parts.cache_clear()

    first_root = build_tooling_support._eiffel_source_like_root(
        PurePosixPath("library/demo/src/application.e")
    )
    second_root = build_tooling_support._eiffel_source_like_root(
        PurePosixPath("library/demo/src/application.e")
    )
    cache_info = build_tooling_support._cached_eiffel_source_like_root_parts.cache_info()

    assert first_root == "library/demo/src"
    assert second_root == "library/demo/src"
    assert cache_info.hits >= 1


def test_probe_language_for_path_skips_reading_plain_suffixless_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "plain-suffixless-repo"
    (repo_path / "vendor").mkdir(parents=True)
    (repo_path / "vendor" / "tool").write_text(
        "plain text without script markers\n",
        encoding="utf-8",
    )
    observed: dict[str, str | None] = {}
    original_language_for_path = probe_module.repository_service._language_for_path

    def _capturing_language_for_path(path: Path, *, text: str | None = None, repo_root=None) -> str:
        observed["path"] = str(path)
        observed["text"] = text
        return original_language_for_path(path, text=text, repo_root=repo_root)

    monkeypatch.setattr(
        probe_module.repository_service,
        "_language_for_path",
        _capturing_language_for_path,
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("vendor/tool", repo_path=repo_path) == "unknown"
    assert observed == {"path": "vendor/tool", "text": None}


def test_probe_language_for_path_preserves_extensionless_awk_shebang(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "extensionless-awk-repo"
    (repo_path / "bin").mkdir(parents=True)
    script_path = repo_path / "bin" / "translate"
    script_path.write_text(
        "#!/usr/bin/env gawk -f\nBEGIN { print 1 }\n",
        encoding="utf-8",
    )
    classification_support.clear_probe_language_for_path_cache()
    original_read_text = Path.read_text

    def _raising_read_text(self: Path, *args, **kwargs) -> str:
        if self == script_path:
            raise AssertionError("extensionless awk probe should stop at prefix classification")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _raising_read_text)

    assert probe_module._probe_language_for_path("bin/translate", repo_path=repo_path) == "awk"


def test_probe_language_for_path_detects_suffixless_tcl_shebang(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "extensionless-tcl-repo"
    (repo_path / "apps").mkdir(parents=True)
    script_path = repo_path / "apps" / "dtplite"
    script_path.write_text(
        "#!/usr/bin/env tclsh\n"
        "namespace eval ::dtp {\n"
        "    proc run {} { return ok }\n"
        "}\n",
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)
    classification_support.clear_probe_language_for_path_cache()
    original_read_text = Path.read_text

    def _raising_read_text(self: Path, *args, **kwargs) -> str:
        if self == script_path:
            raise AssertionError("suffixless tcl probe should stop at prefix classification")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _raising_read_text)

    assert probe_module._probe_language_for_path("apps/dtplite", repo_path=repo_path) == "tcl"


def test_probe_language_for_path_detects_suffixless_shell_shebang(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "extensionless-shell-repo"
    (repo_path / "config").mkdir(parents=True)
    script_path = repo_path / "config" / "install-sh"
    script_path.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "printf 'ok\\n'\n",
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR)
    classification_support.clear_probe_language_for_path_cache()
    original_read_text = Path.read_text

    def _raising_read_text(self: Path, *args, **kwargs) -> str:
        if self == script_path:
            raise AssertionError("suffixless shell probe should stop at prefix classification")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _raising_read_text)

    assert probe_module._probe_language_for_path("config/install-sh", repo_path=repo_path) == "shell"


def test_ballerina_profile_hints_skip_generic_language_reprobe_and_nested_duplicate_walks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "ballerina-profile-repo"
    (repo_path / "ballerina").mkdir(parents=True)
    (repo_path / "modules" / "util").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Ballerina.toml").write_text(
        "[package]\nname = 'demo'\norg = 'acme'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (repo_path / "main.bal").write_text(
        "public function main() returns string {\n    return \"ok\";\n}\n",
        encoding="utf-8",
    )
    (repo_path / "ballerina" / "service.bal").write_text(
        "public function serve() returns string {\n    return \"ok\";\n}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "util" / "main.bal").write_text(
        "public function util() returns string {\n    return \"ok\";\n}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "service_test.bal").write_text(
        "public function testServe() returns string {\n    return \"ok\";\n}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("ballerina profile hints should not use generic language probing")
        ),
    )

    probable_source_calls = {"value": 0}
    original_is_probable_ballerina_source = (
        probe_module.repository_service.ballerina_adapter.is_probable_ballerina_source
    )

    def _counting_is_probable_ballerina_source(*args, **kwargs) -> bool:
        probable_source_calls["value"] += 1
        return original_is_probable_ballerina_source(*args, **kwargs)

    monkeypatch.setattr(
        probe_module.repository_service.ballerina_adapter,
        "is_probable_ballerina_source",
        _counting_is_probable_ballerina_source,
    )

    entrypoints, support_roots, config_paths = ecosystem_support._ballerina_profile_hints(
        repo_path,
        "Ballerina.toml",
    )

    assert probable_source_calls["value"] == 3
    assert config_paths == {"Ballerina.toml"}
    assert {"ballerina", "modules", "tests"} <= support_roots
    assert "main.bal" in entrypoints
    assert "ballerina/service.bal" in entrypoints
    assert "modules/util/main.bal" in entrypoints
    assert "tests/service_test.bal" not in entrypoints


def test_probe_language_for_path_uses_v_repo_hint_for_ambiguous_v_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "v-language-detection-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "v.mod").write_text(
        "Module {\n    name: 'demo'\n}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.v").write_text(
        "module main\n\nfn main() {\n    println('ok')\n}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module.repository_service.coq_adapter,
        "is_probable_coq_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("v repo hint should bypass coq detection for .v sources")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("src/main.v", repo_path=repo_path) == "v"


def test_probe_language_for_path_uses_nested_v_repo_hint_for_ambiguous_v_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "nested-v-language-detection-repo"
    (repo_path / "apps" / "demo").mkdir(parents=True)
    (repo_path / "button.v").write_text(
        "module ui\n\npub fn render() {\n    println('ok')\n}\n",
        encoding="utf-8",
    )
    (repo_path / "apps" / "demo" / "v.mod").write_text(
        "Module {\n    name: 'demo'\n}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module.repository_service.coq_adapter,
        "is_probable_coq_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("nested v repo hint should bypass coq detection for .v sources")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("button.v", repo_path=repo_path) == "v"


def test_probe_language_for_path_uses_coq_repo_hint_for_ambiguous_v_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "coq-language-detection-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "_coqproject").write_text(
        "-Q theories Demo\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Main.v").write_text(
        "From Coq Require Import Arith.\nTheorem id_demo : True.\nProof. exact I. Qed.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module.repository_service.v_adapter._load(),
        "is_probable_v_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("coq repo hint should bypass v detection for .v sources")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("theories/Main.v", repo_path=repo_path) == "coq"


def test_probe_language_for_path_uses_verilog_repo_hint_for_ambiguous_v_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "verilog-language-detection-repo"
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "include" / "defs.vh").write_text(
        "`define WIDTH 8\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.v").write_text(
        "module top(input wire clk);\nendmodule\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module.repository_service.coq_adapter,
        "is_probable_coq_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("verilog repo hint should bypass coq detection for .v sources")
        ),
    )
    monkeypatch.setattr(
        probe_module.repository_service.v_adapter,
        "is_probable_v_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("verilog repo hint should bypass v detection for .v sources")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("rtl/top.v", repo_path=repo_path) == "verilog"


def test_probe_language_for_path_uses_systemverilog_repo_hint_for_ambiguous_v_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "systemverilog-language-detection-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "bus_if.sv").write_text(
        "interface bus_if;\n  logic ready;\nendinterface\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.v").write_text(
        "module top;\n  logic ready;\nendmodule\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module.repository_service.coq_adapter,
        "is_probable_coq_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("systemverilog repo hint should bypass coq detection for .v sources")
        ),
    )
    monkeypatch.setattr(
        probe_module.repository_service.v_adapter,
        "is_probable_v_source",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("systemverilog repo hint should bypass v detection for .v sources")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("rtl/top.v", repo_path=repo_path) == "systemverilog"


def test_probe_language_for_path_uses_actionscript_repo_hint_for_ambiguous_as_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "actionscript-language-detection-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "asconfig.json").write_text(
        '{"compilerOptions":{"source-path":["src"]},"mainClass":"Main"}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.as").write_text(
        "plain text should not matter once the repo hint is decisive\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repository_service,
        "_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("actionscript repo hint should bypass generic .as language probing")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("src/Main.as", repo_path=repo_path) == (
        "actionscript"
    )


def test_probe_language_for_path_uses_angelscript_repo_hint_for_ambiguous_as_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "angelscript-language-detection-repo"
    (repo_path / "bin" / "Data" / "Scripts").mkdir(parents=True)
    (repo_path / "bin" / "Data" / "Scripts" / "SceneDemo.as").write_text(
        "namespace Demo {\nvoid Start() {}\n}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repository_service,
        "_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("angelscript repo hint should bypass generic .as language probing")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path(
        "bin/Data/Scripts/SceneDemo.as",
        repo_path=repo_path,
    ) == "angelscript"


def test_probe_language_for_path_uses_cpp_repo_hint_for_ambiguous_headers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "cpp-header-language-detection-repo"
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text("project(fmt LANGUAGES CXX)\n", encoding="utf-8")
    (repo_path / "include" / "format.h").write_text(
        "template <typename T>\nstruct box { T value; };\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "format.cc").write_text(
        "#include \"format.h\"\nint main() { return 0; }\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repository_service,
        "_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cpp repo hint should bypass generic .h language probing")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("include/format.h", repo_path=repo_path) == "cpp"


def test_probe_language_for_path_preserves_objective_c_header_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "objective-c-header-language-detection-repo"
    (repo_path / "ios").mkdir(parents=True)
    (repo_path / "ios" / "AppDelegate.m").write_text(
        "#import <Foundation/Foundation.h>\n@implementation AppDelegate\n@end\n",
        encoding="utf-8",
    )
    (repo_path / "ios" / "AppDelegate.h").write_text(
        "#import <Foundation/Foundation.h>\n@interface AppDelegate : NSObject\n@end\n",
        encoding="utf-8",
    )
    observed: dict[str, object] = {}

    def _fake_language_for_path(path: Path, *, text: str | None = None, repo_root: Path | None = None) -> str:
        observed["path"] = str(path)
        observed["text"] = text
        observed["repo_root"] = repo_root
        return "objectivec"

    monkeypatch.setattr(repository_service, "_language_for_path", _fake_language_for_path)
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._probe_language_for_path("ios/AppDelegate.h", repo_path=repo_path) == (
        "objectivec"
    )
    assert observed["path"] == "ios/AppDelegate.h"
    assert isinstance(observed["text"], str)
    assert observed["repo_root"] == repo_path


def test_operational_profile_entrypoint_candidate_reuses_cached_path_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "entrypoint-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    call_counts = {"repo_profile": 0}

    monkeypatch.setattr(
        classification_support,
        "_probe_language_for_path",
        lambda path, repo_path=None: "python",
    )
    monkeypatch.setattr(
        classification_support,
        "_is_non_operational_profile_path_for_ecosystems",
        lambda path, ecosystems, repo_path=None: False,
    )
    monkeypatch.setattr(
        classification_support,
        "_is_profile_entrypoint_noise",
        lambda path: False,
    )
    monkeypatch.setattr(
        probe_module,
        "_is_repo_profile_code_candidate",
        lambda path, repo_path=None: call_counts.__setitem__(
            "repo_profile", call_counts["repo_profile"] + 1
        )
        or True,
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._is_operational_profile_entrypoint_candidate(
        "src/main.py",
        repo_path=repo_path,
    )
    assert probe_module._is_operational_profile_entrypoint_candidate(
        "src/main.py",
        repo_path=repo_path,
    )
    assert call_counts["repo_profile"] == 1


def test_operational_profile_entrypoint_candidate_short_circuits_cmakelists_language_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "cmake-entrypoint-fast-path-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\nproject(demo)\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        classification_support,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cmake entrypoint fast path should bypass language probing")
        ),
    )
    monkeypatch.setattr(
        classification_support,
        "_is_non_operational_profile_path_for_ecosystems",
        lambda path, ecosystems, repo_path=None: False,
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._is_operational_profile_entrypoint_candidate(
        "CMakeLists.txt",
        repo_path=repo_path,
    )


def test_operational_profile_entrypoint_candidate_short_circuits_test_path_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        classification_support,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("test-path fast path should bypass language probing")
        ),
    )
    classification_support.clear_probe_language_for_path_cache()

    assert (
        probe_module._is_operational_profile_entrypoint_candidate("tests/example.py") is False
    )


def test_repo_profile_code_candidate_reuses_cached_path_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "code-candidate-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    call_counts = {"probe_language": 0}

    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: call_counts.__setitem__(
            "probe_language", call_counts["probe_language"] + 1
        )
        or "python",
    )
    monkeypatch.setattr(probe_module, "_is_xpp_descriptor_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cfml_box_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        probe_module,
        "_is_purescript_bower_config_path",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(probe_module, "_is_rescript_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_moonbit_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        probe_module,
        "_is_delphi_project_config_path",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(probe_module, "_is_cue_module_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    path_selection_support.clear_repo_profile_config_path_cache()

    assert probe_module._is_repo_profile_code_candidate("src/main.py", repo_path=repo_path)
    assert probe_module._is_repo_profile_code_candidate("src/main.py", repo_path=repo_path)
    assert call_counts["probe_language"] == 1


def test_candidate_ecosystems_for_path_short_circuits_sml_manifest_suffixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("SML manifest suffixes should bypass generic path probing")
        ),
    )
    seed_plan_support.clear_candidate_ecosystem_path_cache()

    assert probe_module._candidate_ecosystems_for_path("project.mlb") == {"sml"}
    assert probe_module._candidate_ecosystems_for_path("sources.cm") == {"sml"}


def test_candidate_ecosystems_for_path_short_circuits_static_basename_hints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("static basename hints should bypass generic path probing")
        ),
    )
    seed_plan_support.clear_candidate_ecosystem_path_cache()

    assert probe_module._candidate_ecosystems_for_path("shadow-cljs.edn") == {
        "clojurescript"
    }
    assert probe_module._candidate_ecosystems_for_path("rescript.json") == {"rescript"}


def test_candidate_ecosystems_for_path_preserves_shared_language_aliases() -> None:
    seed_plan_support.clear_candidate_ecosystem_path_cache()

    assert probe_module._candidate_ecosystems_for_path(
        "src/main.ts",
        language="typescript",
    ) == {"node", "typescript"}


def test_probe_collection_rank_skips_static_non_code_artifact_language_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("static non-code artifact suffixes should bypass language probing")
        ),
    )
    monkeypatch.setattr(probe_module, "_is_xpp_descriptor_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cfml_box_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    collection_support.clear_probe_collection_rank_cache()

    rank = probe_module._probe_collection_rank("forms/Main.frx")

    assert rank == (0, 1, 1, 0, "forms/Main.frx")


def test_probe_collection_rank_skips_suffixless_legal_and_metadata_language_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("suffixless legal and metadata files should bypass language probing")
        ),
    )
    monkeypatch.setattr(probe_module, "_is_xpp_descriptor_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cfml_box_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    collection_support.clear_probe_collection_rank_cache()

    license_rank = probe_module._probe_collection_rank("LICENSE-MIT")
    fossil_rank = probe_module._probe_collection_rank(".fossil-settings/binary-glob")

    assert license_rank == (0, 1, 1, 0, "LICENSE-MIT")
    assert fossil_rank == (0, 1, 1, 0, ".fossil-settings/binary-glob")


def test_probe_collection_rank_strips_quotes_before_direct_text_suffix_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("quoted direct-text suffixes should bypass generic path probing")
        ),
    )
    monkeypatch.setattr(probe_module, "_is_xpp_descriptor_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cfml_box_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    collection_support.clear_probe_collection_rank_cache()

    rank = probe_module._probe_collection_rank('"docs/index.org"')

    assert rank == (0, 0, 1, 1, "docs/index.org")


def test_probe_collection_rank_uses_generic_code_like_fallback_for_unknown_source_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generic code-like suffixes should bypass language probing")
        ),
    )
    monkeypatch.setattr(probe_module, "_is_xpp_descriptor_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cfml_box_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    collection_support.clear_probe_collection_rank_cache()

    rank = probe_module._probe_collection_rank("src/application.e")

    assert rank == (0, 0, 1, 0, "src/application.e")


def test_probe_collection_rank_skips_repo_hint_for_non_v_generic_code_like_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        collection_support,
        "_probe_collection_repo_hint_language",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("non-.v generic code-like suffixes should bypass repo-hint probing")
        ),
    )
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generic code-like suffixes should bypass language probing")
        ),
    )
    monkeypatch.setattr(probe_module, "_is_xpp_descriptor_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cfml_box_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    collection_support.clear_probe_collection_rank_cache()

    rank = probe_module._probe_collection_rank("src/application.e")

    assert rank == (0, 0, 1, 0, "src/application.e")


def test_probe_collection_rank_caches_runtime_deps_across_unique_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _EmptyAdapter:
        _KNOWN_BASENAMES: tuple[str, ...] = ()
        MAKEFILE_BASENAMES: tuple[str, ...] = ()
        DOCKERFILE_BASENAMES: tuple[str, ...] = ()
        CMAKE_CONFIG_BASENAMES: tuple[str, ...] = ()

    class _FakeRepositoryService:
        _SHELL_FILE_BASENAMES: tuple[str, ...] = ()
        starlark_adapter = _EmptyAdapter()
        makefile_adapter = _EmptyAdapter()
        dockerfile_adapter = _EmptyAdapter()
        cmake_adapter = _EmptyAdapter()

        def __init__(self) -> None:
            self.direct_text_suffix_language_map_reads = 0
            self.non_code_graph_languages_reads = 0

        def _normalize_repository_relative_path(self, value: str) -> str:
            return str(value).replace("\\", "/").strip().strip("/")

        def _is_test_path(self, _value: str) -> bool:
            return False

        def _language_for_path(self, *_args, **_kwargs) -> str:
            return "unknown"

        @property
        def _DIRECT_TEXT_SUFFIX_LANGUAGE_MAP(self) -> dict[str, str]:
            self.direct_text_suffix_language_map_reads += 1
            return {}

        @property
        def _NON_CODE_GRAPH_LANGUAGES(self) -> frozenset[str]:
            self.non_code_graph_languages_reads += 1
            return frozenset({"txt"})

    class _FakeProbeModule:
        _TEMPLATE_SURFACE_ECOSYSTEMS = frozenset()
        _TEMPLATE_SURFACE_PARTS = frozenset()

        def __init__(self, repository_service: _FakeRepositoryService) -> None:
            self.repository_service = repository_service

        @staticmethod
        def _is_xpp_descriptor_config_path(*_args, **_kwargs) -> bool:
            return False

        @staticmethod
        def _is_cfml_box_config_path(*_args, **_kwargs) -> bool:
            return False

        @staticmethod
        def _is_repo_profile_manifest_name(_basename: str) -> bool:
            return False

        @staticmethod
        def _probe_language_for_path(*_args, **_kwargs) -> str:
            return "unknown"

    fake_repository_service = _FakeRepositoryService()
    fake_probe_module = _FakeProbeModule(fake_repository_service)
    monkeypatch.setattr(collection_support, "_probe_module", lambda: fake_probe_module)
    collection_support.clear_probe_collection_rank_cache()

    assert collection_support._probe_collection_rank("src/application.e") == (
        0,
        0,
        1,
        0,
        "src/application.e",
    )
    assert collection_support._probe_collection_rank("src/other.e") == (
        0,
        0,
        1,
        0,
        "src/other.e",
    )
    assert fake_repository_service.direct_text_suffix_language_map_reads == 1
    assert fake_repository_service.non_code_graph_languages_reads == 1

    collection_support.clear_probe_collection_rank_cache()
    assert collection_support._probe_collection_rank("src/third.e") == (
        0,
        0,
        1,
        0,
        "src/third.e",
    )
    assert fake_repository_service.direct_text_suffix_language_map_reads == 2
    assert fake_repository_service.non_code_graph_languages_reads == 2


def test_probe_collection_special_no_text_basenames_are_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _CountingIterable:
        def __init__(self, values: tuple[str, ...]) -> None:
            self._values = values
            self.iteration_count = 0

        def __iter__(self):
            self.iteration_count += 1
            return iter(self._values)

    starlark_basenames = _CountingIterable(("BUILD",))
    makefile_basenames = _CountingIterable(("Makefile",))
    dockerfile_basenames = _CountingIterable(("Dockerfile",))
    cmake_basenames = _CountingIterable(("CMakeLists.txt",))

    monkeypatch.setattr(
        repository_service.starlark_adapter,
        "_KNOWN_BASENAMES",
        starlark_basenames,
    )
    monkeypatch.setattr(
        repository_service.makefile_adapter,
        "MAKEFILE_BASENAMES",
        makefile_basenames,
    )
    monkeypatch.setattr(
        repository_service.dockerfile_adapter,
        "DOCKERFILE_BASENAMES",
        dockerfile_basenames,
    )
    monkeypatch.setattr(
        repository_service.cmake_adapter,
        "CMAKE_CONFIG_BASENAMES",
        cmake_basenames,
    )
    collection_support._probe_collection_special_no_text_basenames.cache_clear()

    first_basenames = collection_support._probe_collection_special_no_text_basenames()
    second_basenames = collection_support._probe_collection_special_no_text_basenames()

    assert "build" in first_basenames
    assert "makefile" in first_basenames
    assert "dockerfile" in first_basenames
    assert "cmakelists.txt" in first_basenames
    assert first_basenames is second_basenames
    assert starlark_basenames.iteration_count == 1
    assert makefile_basenames.iteration_count == 1
    assert dockerfile_basenames.iteration_count == 1
    assert cmake_basenames.iteration_count == 1


def test_qml_profile_hints_reuse_loaded_text_and_bypass_generic_language_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "qml-profile-hints-repo"
    (repo_path / "components").mkdir(parents=True)
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "qmldir").write_text(
        "module Demo.Controls\n"
        "Button 1.0 components/Button.qml\n",
        encoding="utf-8",
    )
    (repo_path / "main.qml").write_text(
        'import "." as Demo\n'
        "Rectangle {\n"
        "    Demo.Button {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "components" / "Button.qml").write_text(
        "Rectangle {\n"
        "    id: helperButton\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    read_counts: Counter[str] = Counter()
    tracked_paths = {
        repo_path / "qmldir",
        repo_path / "main.qml",
        repo_path / "components" / "Button.qml",
    }
    original_read_text = Path.read_text

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in tracked_paths:
            read_counts[self.relative_to(repo_path).as_posix()] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("QML profile hints should bypass generic language probing")
        ),
    )

    entrypoints, roots, configs = qml_chapel_support._qml_profile_hints_from_candidates(
        repo_path,
        ["docs/guide.md", "main.qml", "components/Button.qml", "qmldir"],
    )

    assert entrypoints == {"main.qml"}
    assert roots == {"components"}
    assert configs == {"qmldir"}
    assert read_counts["main.qml"] == 1
    assert read_counts["components/Button.qml"] == 1


def test_bicep_profile_hints_reuse_loaded_text_for_aliases_and_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "bicep-profile-hints-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "main.bicep").write_text(
        "module storage './modules/storage.bicep' = {\n"
        "  name: 'storage'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "storage.bicep").write_text(
        "param storageName string\n"
        "output storageId string = storageName\n",
        encoding="utf-8",
    )
    read_counts: Counter[str] = Counter()
    tracked_paths = {
        repo_path / "main.bicep",
        repo_path / "modules" / "storage.bicep",
    }
    original_read_text = Path.read_text

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in tracked_paths:
            read_counts[self.relative_to(repo_path).as_posix()] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    entrypoints, roots, configs = build_tooling_support._bicep_profile_hints_from_candidates(
        repo_path,
        ["main.bicep", "modules/storage.bicep"],
    )

    assert entrypoints == {"main.bicep"}
    assert roots == {"modules"}
    assert configs == set()
    assert read_counts["main.bicep"] == 1
    assert read_counts["modules/storage.bicep"] == 1


def test_org_profile_hints_reuse_loaded_text_for_aliases_and_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "org-profile-hints-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "docs" / "index.org").write_text(
        "* Index\n#+INCLUDE: \"guide.org\"\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "guide.org").write_text("* Guide\n", encoding="utf-8")
    read_counts: Counter[str] = Counter()
    tracked_paths = {
        repo_path / "docs" / "index.org",
        repo_path / "docs" / "guide.org",
    }
    original_read_text = Path.read_text

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in tracked_paths:
            read_counts[self.relative_to(repo_path).as_posix()] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("org profile hints should bypass generic language probing")
        ),
    )

    entrypoints, roots, configs = ecosystem_support._org_profile_hints_from_candidates(
        repo_path,
        ["docs/index.org", "docs/guide.org"],
    )

    assert entrypoints == {"docs/index.org", "docs/guide.org"}
    assert roots == {"docs"}
    assert configs == set()
    assert read_counts["docs/index.org"] == 1
    assert read_counts["docs/guide.org"] == 1


def test_mustache_profile_hints_reuse_loaded_text_for_aliases_and_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "mustache-profile-hints-repo"
    (repo_path / "templates").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "templates" / "index.mustache").write_text(
        "{{> header}}\n{{title}}\n",
        encoding="utf-8",
    )
    (repo_path / "partials" / "header.mustache").write_text(
        "<h1>{{title}}</h1>\n",
        encoding="utf-8",
    )
    read_counts: Counter[str] = Counter()
    tracked_paths = {
        repo_path / "templates" / "index.mustache",
        repo_path / "partials" / "header.mustache",
    }
    original_read_text = Path.read_text

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in tracked_paths:
            read_counts[self.relative_to(repo_path).as_posix()] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(probe_module, "_probe_language_for_path", lambda *args, **kwargs: "mustache")

    entrypoints, roots, configs = server_template_support._mustache_profile_hints_from_candidates(
        repo_path,
        ["templates/index.mustache", "partials/header.mustache"],
    )

    assert entrypoints == {"templates/index.mustache"}
    assert roots == {"partials", "templates"}
    assert configs == set()
    assert read_counts["templates/index.mustache"] == 1
    assert read_counts["partials/header.mustache"] == 1


def test_protobuf_profile_hints_reuse_loaded_text_for_aliases_and_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "protobuf-profile-hints-repo"
    (repo_path / "proto").mkdir(parents=True)
    (repo_path / "proto" / "service.proto").write_text(
        'syntax = "proto3";\nimport "proto/types.proto";\nservice Greeter { rpc SayHello (HelloRequest) returns (HelloReply); }\nmessage HelloRequest {}\nmessage HelloReply {}\n',
        encoding="utf-8",
    )
    (repo_path / "proto" / "types.proto").write_text(
        'syntax = "proto3";\nmessage CommonType {}\n',
        encoding="utf-8",
    )
    read_counts: Counter[str] = Counter()
    tracked_paths = {
        repo_path / "proto" / "service.proto",
        repo_path / "proto" / "types.proto",
    }
    original_read_text = Path.read_text

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in tracked_paths:
            read_counts[self.relative_to(repo_path).as_posix()] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(probe_module, "_probe_language_for_path", lambda *args, **kwargs: "protobuf")

    entrypoints, roots, configs = candidate_language_support._protobuf_profile_hints_from_candidates(
        repo_path,
        ["proto/service.proto", "proto/types.proto"],
    )

    assert entrypoints == {"proto/service.proto"}
    assert roots == {"proto"}
    assert configs == set()
    assert read_counts["proto/service.proto"] == 1
    assert read_counts["proto/types.proto"] == 1


def test_tlaplus_profile_hints_reuse_loaded_text_for_aliases_and_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "tlaplus-profile-hints-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "MCSpec.cfg").write_text("SPECIFICATION Spec\n", encoding="utf-8")
    (repo_path / "Spec.tla").write_text(
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals, Util\n\n"
        "Inst == INSTANCE Util\n"
        "VARIABLES x\n\n"
        "Init == x = 0\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "Util.tla").write_text(
        "---- MODULE Util ----\n"
        "Answer == 42\n",
        encoding="utf-8",
    )
    (repo_path / "MCSpec.tla").write_text(
        "---- MODULE MCSpec ----\n"
        "EXTENDS Spec\n",
        encoding="utf-8",
    )
    read_counts: Counter[str] = Counter()
    tracked_paths = {
        repo_path / "Spec.tla",
        repo_path / "lib" / "Util.tla",
        repo_path / "MCSpec.tla",
    }
    original_read_text = Path.read_text

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in tracked_paths:
            read_counts[self.relative_to(repo_path).as_posix()] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(probe_module, "_probe_language_for_path", lambda *args, **kwargs: "tlaplus")

    entrypoints, roots, configs = build_tooling_support._tlaplus_profile_hints_from_candidates(
        repo_path,
        ["MCSpec.cfg", "Spec.tla", "lib/Util.tla", "MCSpec.tla"],
    )

    assert "MCSpec.cfg" in configs
    assert "MCSpec.tla" in entrypoints
    assert "lib" in roots
    assert read_counts["Spec.tla"] == 1
    assert read_counts["lib/Util.tla"] == 1
    assert read_counts["MCSpec.tla"] == 1


def test_jinja_profile_hints_reuse_loaded_text_for_aliases_and_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "jinja-profile-hints-repo"
    (repo_path / "templates" / "partials").mkdir(parents=True)
    (repo_path / "templates" / "page.j2").write_text(
        '{% import "partials/macros.j2" as macros %}\n'
        '{{ macros.render_button("Ship it") }}\n',
        encoding="utf-8",
    )
    (repo_path / "templates" / "partials" / "macros.j2").write_text(
        "{% macro render_button(label) %}<button>{{ label }}</button>{% endmacro %}\n",
        encoding="utf-8",
    )
    read_counts: Counter[str] = Counter()
    tracked_paths = {
        repo_path / "templates" / "page.j2",
        repo_path / "templates" / "partials" / "macros.j2",
    }
    original_read_text = Path.read_text

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in tracked_paths:
            read_counts[self.relative_to(repo_path).as_posix()] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(probe_module, "_probe_language_for_path", lambda *args, **kwargs: "jinja")

    entrypoints, roots, configs = server_template_support._jinja_profile_hints_from_candidates(
        repo_path,
        ["templates/page.j2", "templates/partials/macros.j2"],
    )

    assert entrypoints == {"templates/page.j2"}
    assert roots == {"templates", "templates/partials"}
    assert configs == set()
    assert read_counts["templates/page.j2"] == 1
    assert read_counts["templates/partials/macros.j2"] == 1


def test_moonbit_profile_hints_reuse_loaded_text_for_aliases_and_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "moonbit-profile-hints-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "app" / "moon.pkg").write_text(
        'import { "moonbit/core/math" @math }\n',
        encoding="utf-8",
    )
    (repo_path / "app" / "app.mbt").write_text(
        "pub fn main() -> Int {\n  @math.add(1, 2)\n}\n",
        encoding="utf-8",
    )
    (repo_path / "math" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "math" / "math.mbt").write_text(
        "pub fn add(x : Int, y : Int) -> Int {\n  x + y\n}\n",
        encoding="utf-8",
    )
    read_counts: Counter[str] = Counter()
    tracked_paths = {
        repo_path / "moon.mod",
        repo_path / "app" / "moon.pkg",
        repo_path / "app" / "app.mbt",
        repo_path / "math" / "moon.pkg",
        repo_path / "math" / "math.mbt",
    }
    original_read_text = Path.read_text

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in tracked_paths:
            read_counts[self.relative_to(repo_path).as_posix()] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    entrypoints, roots, configs = ecosystem_support._moonbit_profile_hints_from_candidates(
        repo_path,
        ["moon.mod", "app/moon.pkg", "app/app.mbt", "math/moon.pkg", "math/math.mbt"],
        manifest_path="moon.mod",
    )

    assert "app/app.mbt" in entrypoints
    assert "math/math.mbt" in entrypoints
    assert roots == {"app", "math"}
    assert configs == {"moon.mod", "app/moon.pkg"}
    assert read_counts["moon.mod"] == 1
    assert read_counts["app/moon.pkg"] == 1
    assert read_counts["app/app.mbt"] == 1
    assert read_counts["math/moon.pkg"] == 1
    assert read_counts["math/math.mbt"] == 1


def test_moonbit_profile_hints_build_module_index_without_symbol_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "moonbit-profile-hints-module-only-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "app" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "app" / "app.mbt").write_text(
        "pub fn main() -> Int {\n  1\n}\n",
        encoding="utf-8",
    )
    include_symbol_aliases_calls: list[bool] = []
    original_module_aliases_for_path = (
        probe_module.repository_service.moonbit_adapter.module_aliases_for_path
    )

    def tracking_module_aliases_for_path(**kwargs):
        include_symbol_aliases_calls.append(bool(kwargs.get("include_symbol_aliases", True)))
        return original_module_aliases_for_path(**kwargs)

    monkeypatch.setattr(
        probe_module.repository_service.moonbit_adapter,
        "module_aliases_for_path",
        tracking_module_aliases_for_path,
    )

    entrypoints, roots, configs = ecosystem_support._moonbit_profile_hints_from_candidates(
        repo_path,
        ["moon.mod", "app/moon.pkg", "app/app.mbt"],
        manifest_path="moon.mod",
    )

    assert "app/app.mbt" in entrypoints
    assert roots == {"app"}
    assert configs == {"moon.mod"}
    assert include_symbol_aliases_calls == [False]


def test_moonbit_profile_candidate_paths_reuse_cached_repo_listing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "moonbit-candidate-path-cache-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "app" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "app" / "app.mbt").write_text("pub fn main() -> Int {\n  1\n}\n", encoding="utf-8")
    (repo_path / "README.md").write_text("# docs\n", encoding="utf-8")

    collection_support.clear_git_repo_relative_files_cache()
    collection_support.seed_git_repo_relative_files_cache(
        repo_path,
        ["moon.mod", "app/moon.pkg", "app/app.mbt", "README.md"],
        relative_paths_are_canonical=True,
    )

    def _unexpected_rglob(self: Path, *_args, **_kwargs):
        raise AssertionError("cached repo listing should avoid moonbit rglob scanning")

    monkeypatch.setattr(Path, "rglob", _unexpected_rglob)

    candidate_paths = ecosystem_support._moonbit_profile_candidate_paths(
        repo_path,
        manifest_path="moon.mod",
        max_files=64,
    )

    assert candidate_paths == ["moon.mod", "app/moon.pkg", "app/app.mbt"]


def test_systemverilog_profile_hints_use_manifest_paths_without_language_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "systemverilog-bender-profile-hints-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "Bender.yml").write_text(
        "sources:\n"
        "  - rtl/defs.vh\n"
        "  - rtl/top.v\n"
        "  - tests/top_test.sv\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "defs.vh").write_text(
        "`define WIDTH 32\n",
        encoding="utf-8",
    )
    (repo_path / "rtl" / "top.v").write_text(
        "module top;\nendmodule\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "top_test.sv").write_text(
        "module top_test;\n  top dut();\nendmodule\n",
        encoding="utf-8",
    )

    def _unexpected_probe_language_for_path(*_args, **_kwargs):
        raise AssertionError("Bender manifest sources should not require generic language probing")

    monkeypatch.setattr(
        project_languages_b_support._probe_module(),
        "_probe_language_for_path",
        _unexpected_probe_language_for_path,
    )

    entrypoints, roots, configs = project_languages_b_support._systemverilog_profile_hints(
        repo_path,
        "Bender.yml",
    )

    assert entrypoints == {"rtl/top.v"}
    assert roots == {"rtl"}
    assert configs == {"Bender.yml"}


def test_moonbit_profile_candidate_paths_use_focused_git_listing_before_rglob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "moonbit-candidate-path-focused-git-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "app" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "app" / "app.mbt").write_text("pub fn main() -> Int {\n  1\n}\n", encoding="utf-8")

    collection_support.clear_git_repo_relative_files_cache()
    monkeypatch.setattr(
        collection_support,
        "_git_repo_relative_files_for_focus_paths",
        lambda _repo_path, *, focus_paths: ["moon.mod", "app/moon.pkg", "app/app.mbt"],
    )

    def _unexpected_rglob(self: Path, *_args, **_kwargs):
        raise AssertionError("focused git listing should avoid moonbit rglob scanning")

    monkeypatch.setattr(Path, "rglob", _unexpected_rglob)

    candidate_paths = ecosystem_support._moonbit_profile_candidate_paths(
        repo_path,
        manifest_path="moon.mod",
        max_files=64,
    )

    assert candidate_paths == ["moon.mod", "app/moon.pkg", "app/app.mbt"]


def test_rank_seed_path_and_code_candidate_share_candidate_ecosystem_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "shared-ecosystem-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    call_counts = {"probe_language": 0}

    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: call_counts.__setitem__(
            "probe_language", call_counts["probe_language"] + 1
        )
        or "python",
    )
    monkeypatch.setattr(probe_module, "_is_xpp_descriptor_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cfml_box_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        probe_module,
        "_is_purescript_bower_config_path",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(probe_module, "_is_rescript_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_moonbit_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        probe_module,
        "_is_delphi_project_config_path",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(probe_module, "_is_cue_module_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    path_selection_support.clear_repo_profile_config_path_cache()
    seed_plan_support.clear_candidate_ecosystem_path_cache()

    probe_module._rank_repo_profile_seed_path(
        "src/main.py",
        repo_path=repo_path,
        support_roots={"src"},
    )
    assert probe_module._is_repo_profile_code_candidate("src/main.py", repo_path=repo_path)
    assert call_counts["probe_language"] == 1


def test_repo_profile_code_candidate_reuses_scoped_repo_file_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "code-candidate-stat-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    tracked_file = repo_path / "src" / "main.py"
    tracked_file.write_text("print('ok')\n", encoding="utf-8")
    call_counts = {"stat": 0}
    original_stat = Path.stat

    def _counting_stat(self: Path, *args, **kwargs):
        if self == tracked_file:
            call_counts["stat"] += 1
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _counting_stat)
    monkeypatch.setattr(probe_module, "_probe_language_for_path", lambda path, repo_path=None: "python")
    monkeypatch.setattr(probe_module, "_is_xpp_descriptor_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cfml_box_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        probe_module,
        "_is_purescript_bower_config_path",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(probe_module, "_is_rescript_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_moonbit_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        probe_module,
        "_is_delphi_project_config_path",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(probe_module, "_is_cue_module_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    path_selection_support.clear_repo_profile_config_path_cache()
    classification_support.end_repo_file_stat_cache_scope()

    classification_support.begin_repo_file_stat_cache_scope()
    try:
        assert probe_module._is_repo_profile_code_candidate("src/main.py", repo_path=repo_path)
        assert probe_module._is_repo_profile_code_candidate("src/main.py", repo_path=repo_path)
    finally:
        classification_support.end_repo_file_stat_cache_scope()

    assert call_counts["stat"] == 1


def test_rank_repo_profile_seed_path_reuses_best_matching_support_root_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "seed-rank-support-root-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    original_uncached = path_selection_support._best_matching_support_root_uncached
    call_count = {"value": 0}

    def counting_uncached(normalized_path: str, *, normalized_support_roots: set[str]) -> str | None:
        call_count["value"] += 1
        return original_uncached(
            normalized_path,
            normalized_support_roots=normalized_support_roots,
        )

    monkeypatch.setattr(
        path_selection_support,
        "_best_matching_support_root_uncached",
        counting_uncached,
    )
    path_selection_support.clear_support_root_match_cache()

    first_rank = probe_module._rank_repo_profile_seed_path(
        "src/main.py",
        repo_path=repo_path,
        support_roots={"src"},
    )
    second_rank = probe_module._rank_repo_profile_seed_path(
        "src/main.py",
        repo_path=repo_path,
        support_roots={"src"},
    )

    assert first_rank == second_rank
    assert call_count["value"] == 1


def test_repo_profile_code_candidate_uses_direct_hint_without_repo_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "code-candidate-direct-hint-repo"
    (repo_path / "logic").mkdir(parents=True)
    (repo_path / "logic" / "Main.L5X").write_text(
        "<RSLogix5000Content>\n<Programs />\n</RSLogix5000Content>\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        classification_support,
        "_repo_file_stat",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("direct language hints should bypass repo file stat")
        ),
    )
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("direct language hints should bypass generic language probing")
        ),
    )
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    path_selection_support.clear_repo_profile_config_path_cache()
    seed_plan_support.clear_candidate_ecosystem_path_cache()

    assert probe_module._is_repo_profile_code_candidate("logic/Main.L5X", repo_path=repo_path)


def test_repo_profile_code_candidate_skips_specialized_config_checks_for_irrelevant_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "code-candidate-specialized-prefilter-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(probe_module, "_probe_language_for_path", lambda path, repo_path=None: "python")
    for helper_name in (
        "_is_xpp_descriptor_config_path",
        "_is_cfml_box_config_path",
        "_is_purescript_bower_config_path",
        "_is_rescript_config_path",
        "_is_moonbit_config_path",
        "_is_cue_module_config_path",
    ):
        monkeypatch.setattr(
            probe_module,
            helper_name,
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"{helper_name} should not run for an irrelevant path")
            ),
        )
    monkeypatch.setattr(
        probe_module,
        "_is_delphi_project_config_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("delphi config detection should not run for a non-.dproj path")
        ),
    )
    monkeypatch.setattr(probe_module, "_is_repo_profile_manifest_name", lambda basename: False)
    path_selection_support.clear_repo_profile_config_path_cache()

    assert probe_module._is_repo_profile_code_candidate("src/main.py", repo_path=repo_path)


def test_repo_profile_code_candidate_skips_language_probe_for_specialized_config_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "code-candidate-specialized-short-circuit-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text("module: demo\n", encoding="utf-8")

    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("specialized config short-circuit should bypass language probing")
        ),
    )
    monkeypatch.setattr(probe_module, "_is_xpp_descriptor_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cfml_box_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        probe_module,
        "_is_purescript_bower_config_path",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(probe_module, "_is_rescript_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_moonbit_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_delphi_project_config_path", lambda *args, **kwargs: False)
    monkeypatch.setattr(probe_module, "_is_cue_module_config_path", lambda *args, **kwargs: True)
    path_selection_support.clear_repo_profile_config_path_cache()

    assert (
        probe_module._is_repo_profile_code_candidate(
            "cue.mod/module.cue",
            repo_path=repo_path,
        )
        is False
    )


def test_non_operational_profile_path_for_ecosystems_reuses_cached_path_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_counts = {"tokens": 0}
    original_profile_path_tokens = classification_support._profile_path_tokens

    def _counting_profile_path_tokens(path: str) -> set[str]:
        call_counts["tokens"] += 1
        return original_profile_path_tokens(path)

    monkeypatch.setattr(
        classification_support,
        "_profile_path_tokens",
        _counting_profile_path_tokens,
    )
    classification_support.clear_probe_language_for_path_cache()

    assert probe_module._is_non_operational_profile_path_for_ecosystems(
        "examples/main.py",
        ecosystems={"opencl"},
    ) is False
    assert probe_module._is_non_operational_profile_path_for_ecosystems(
        "examples/main.py",
        ecosystems={"opencl"},
    ) is False
    assert call_counts["tokens"] == 1


def test_profile_path_tokens_reuse_cached_path_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_normalize = probe_module.repository_service._normalize_repository_relative_path
    call_counts = {"normalize": 0}

    def _counting_normalize(path: str) -> str:
        call_counts["normalize"] += 1
        return original_normalize(path)

    monkeypatch.setattr(
        probe_module.repository_service,
        "_normalize_repository_relative_path",
        _counting_normalize,
    )
    classification_support.clear_probe_language_for_path_cache()

    first_tokens = classification_support._profile_path_tokens("src/examples/main.py")
    second_tokens = classification_support._profile_path_tokens("src/examples/main.py")

    assert first_tokens == second_tokens
    assert call_counts["normalize"] == 1


def test_repo_file_stat_cache_scope_reuses_stats_within_scope_and_clears_between_scopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "repo-file-stat-scope-repo"
    (repo_path / "src").mkdir(parents=True)
    tracked_file = repo_path / "src" / "main.py"
    tracked_file.write_text("print('ok')\n", encoding="utf-8")
    call_counts = {"stat": 0}
    original_stat = Path.stat

    def _counting_stat(self: Path, *args, **kwargs):
        if self == tracked_file:
            call_counts["stat"] += 1
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _counting_stat)
    classification_support.end_repo_file_stat_cache_scope()

    classification_support.begin_repo_file_stat_cache_scope()
    try:
        first_stat = classification_support._repo_file_stat(repo_path, "src/main.py")
        second_stat = classification_support._repo_file_stat(repo_path, "src/main.py")
    finally:
        classification_support.end_repo_file_stat_cache_scope()

    classification_support.begin_repo_file_stat_cache_scope()
    try:
        third_stat = classification_support._repo_file_stat(repo_path, "src/main.py")
    finally:
        classification_support.end_repo_file_stat_cache_scope()

    assert first_stat is not None
    assert second_stat is first_stat
    assert third_stat is not None
    assert call_counts["stat"] == 2


def test_git_repo_relative_files_cache_scope_wraps_repo_file_stat_cache_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classification_support.end_repo_file_stat_cache_scope()
    collection_support.end_git_repo_relative_files_cache_scope()
    events: list[str] = []

    monkeypatch.setattr(
        classification_support,
        "begin_repo_file_stat_cache_scope",
        lambda: events.append("begin"),
    )
    monkeypatch.setattr(
        classification_support,
        "end_repo_file_stat_cache_scope",
        lambda: events.append("end"),
    )

    collection_support.begin_git_repo_relative_files_cache_scope()
    collection_support.begin_git_repo_relative_files_cache_scope()
    collection_support.end_git_repo_relative_files_cache_scope()
    collection_support.end_git_repo_relative_files_cache_scope()

    assert events == ["begin", "end"]


def test_candidate_existing_paths_and_roots_reuse_scoped_repo_file_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "existing-paths-stat-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    tracked_file = repo_path / "src" / "main.py"
    tracked_file.write_text("print('ok')\n", encoding="utf-8")
    tracked_root = repo_path / "src"
    call_counts = {"file": 0, "root": 0}
    original_stat = Path.stat

    def _counting_stat(self: Path, *args, **kwargs):
        if self == tracked_file:
            call_counts["file"] += 1
        if self == tracked_root:
            call_counts["root"] += 1
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _counting_stat)
    classification_support.end_repo_file_stat_cache_scope()

    classification_support.begin_repo_file_stat_cache_scope()
    try:
        assert collection_support._candidate_existing_paths(
            repo_path,
            paths={"src/main.py", "src/main.py"},
        ) == ["src/main.py"]
        assert collection_support._candidate_existing_paths(
            repo_path,
            paths={"src/main.py"},
        ) == ["src/main.py"]
        assert collection_support._candidate_existing_roots(
            repo_path,
            roots={"src"},
        ) == ["src"]
        assert collection_support._candidate_existing_roots(
            repo_path,
            roots={"src"},
        ) == ["src"]
    finally:
        classification_support.end_repo_file_stat_cache_scope()

    assert call_counts["file"] == 1
    assert call_counts["root"] == 1


def test_repo_path_file_metadata_helpers_reuse_scoped_lstat_and_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "repo-path-metadata-cache-repo"
    (repo_path / "src").mkdir(parents=True)
    tracked_file = repo_path / "src" / "main.py"
    tracked_file.write_text("print('ok')\n", encoding="utf-8")
    symlink_path = repo_path / "src" / "main-link.py"
    symlink_path.symlink_to(tracked_file)
    call_counts = {"stat": 0, "lstat": 0}
    original_stat = Path.stat
    original_lstat = Path.lstat

    def _counting_stat(self: Path, *args, **kwargs):
        if self in {tracked_file, symlink_path}:
            call_counts["stat"] += 1
        return original_stat(self, *args, **kwargs)

    def _counting_lstat(self: Path, *args, **kwargs):
        if self in {tracked_file, symlink_path}:
            call_counts["lstat"] += 1
        return original_lstat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _counting_stat)
    monkeypatch.setattr(Path, "lstat", _counting_lstat)
    classification_support.end_repo_file_stat_cache_scope()

    classification_support.begin_repo_file_stat_cache_scope()
    try:
        assert classification_support._repo_path_is_regular_file(repo_path, "src/main.py") is True
        main_file_stat_calls = call_counts["stat"]
        assert classification_support._repo_path_is_regular_file(repo_path, "src/main.py") is True
        assert call_counts["stat"] == main_file_stat_calls
        assert classification_support._repo_path_is_symlink(repo_path, "src/main.py") is False
        main_file_lstat_calls = call_counts["lstat"]
        assert classification_support._repo_path_is_symlink(repo_path, "src/main.py") is False
        assert call_counts["lstat"] == main_file_lstat_calls
        assert classification_support._repo_path_is_regular_file(repo_path, "src/main-link.py") is True
        link_stat_calls = call_counts["stat"]
        assert classification_support._repo_path_is_regular_file(repo_path, "src/main-link.py") is True
        assert call_counts["stat"] == link_stat_calls
        assert classification_support._repo_path_is_symlink(repo_path, "src/main-link.py") is True
        link_lstat_calls = call_counts["lstat"]
        assert classification_support._repo_path_is_symlink(repo_path, "src/main-link.py") is True
        assert call_counts["lstat"] == link_lstat_calls
    finally:
        classification_support.end_repo_file_stat_cache_scope()

    assert call_counts["stat"] >= 2
    assert call_counts["lstat"] >= 2


def test_accumulate_detected_ecosystem_scores_caps_operational_path_scans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scores: Counter[str] = Counter()
    call_counts = {
        "entrypoint_candidate": 0,
        "normalize_root": 0,
    }
    original_normalize = probe_module.repository_service._normalize_repository_relative_path

    monkeypatch.setattr(
        probe_module,
        "_profile_signal_depth_score",
        lambda _path: 0,
    )
    monkeypatch.setattr(
        probe_module.repository_service,
        "_is_test_path",
        lambda _path: False,
    )
    monkeypatch.setattr(
        probe_module,
        "_is_non_operational_profile_path_for_ecosystems",
        lambda _path, *, ecosystems, repo_path=None: False,
    )
    monkeypatch.setattr(
        probe_module,
        "_is_operational_profile_entrypoint_candidate",
        lambda _path, repo_path=None: call_counts.__setitem__(
            "entrypoint_candidate",
            call_counts["entrypoint_candidate"] + 1,
        )
        or True,
    )

    def _counting_normalize(path: str) -> str:
        call_counts["normalize_root"] += 1
        return original_normalize(path)

    monkeypatch.setattr(
        probe_module.repository_service,
        "_normalize_repository_relative_path",
        _counting_normalize,
    )

    probe_module._accumulate_detected_ecosystem_scores(
        scores,
        ecosystems={"opencl"},
        config_path="CMakeLists.txt",
        entrypoints={f"src/kernel_{index}.cl" for index in range(12)},
        roots={f"src/root_{index}" for index in range(12)},
        configs={f"config_{index}" for index in range(6)},
    )

    assert scores["opencl"] == 68
    assert call_counts["entrypoint_candidate"] == 8
    assert call_counts["normalize_root"] == 8
