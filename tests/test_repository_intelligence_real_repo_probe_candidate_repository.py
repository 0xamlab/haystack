"""Tests for repository_intelligence_real_repo_probe: candidate_repository.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_candidate_repository_file_paths_uses_git_listing_without_iter_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_path = tmp_path / "git-listing-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    def _unexpected_iter_repository_files(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("git listing should avoid repository tree walk in the probe")

    monkeypatch.setattr(repository_service, "_iter_repository_files", _unexpected_iter_repository_files)

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=32,
    )

    assert candidate_paths == ["services/app/src/main.ts"]


def test_candidate_repository_file_paths_prioritizes_operational_files_over_tests(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-priority-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.test.ts").write_text(
        "export const testRun = (): string => 'ok';\n",
        encoding="utf-8",
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=[],
        include_patterns=["services/**/*.ts"],
        max_files=1,
    )

    assert candidate_paths == ["services/app/src/main.ts"]


def test_candidate_repository_file_paths_caps_bridge_directory_expansion(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-bridge-budget-repo"
    source_dir = repo_path / "services" / "app" / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )
    for index in range(600):
        (source_dir / f"worker_{index}.ts").write_text(
            f"export const worker{index} = (): number => {index};\n",
            encoding="utf-8",
        )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=["services/app/src/main.ts"],
        bridge_paths=["services/app"],
        include_patterns=["services/**/*.ts"],
        max_files=1024,
    )

    assert "services/app/src/main.ts" in candidate_paths
    assert len(candidate_paths) == 256


def test_candidate_repository_file_paths_distributes_budget_across_bridge_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-bridge-roots-repo"
    alpha_dir = repo_path / "pkgs" / "alpha" / "lib"
    omega_dir = repo_path / "pkgs" / "omega" / "lib"
    alpha_dir.mkdir(parents=True)
    omega_dir.mkdir(parents=True)
    for index in range(20):
        (alpha_dir / f"worker_{index}.dart").write_text(
            f"int worker{index}() => {index};\n",
            encoding="utf-8",
        )
    (omega_dir / "omega.dart").write_text(
        "int omega() => 1;\n",
        encoding="utf-8",
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=["pkgs/alpha", "pkgs/omega"],
        include_patterns=["pkgs/**/*.dart"],
        max_files=4,
    )

    assert "pkgs/omega/lib/omega.dart" in candidate_paths


def test_candidate_repository_file_paths_tightens_spread_for_many_bridge_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-many-bridge-roots-repo"
    bridge_paths: list[str] = []
    for index in range(32):
        module_dir = repo_path / f"pkg_{index}" / "src"
        module_dir.mkdir(parents=True)
        bridge_paths.append(f"pkg_{index}")
        for file_index in range(12):
            (module_dir / f"worker_{file_index}.ts").write_text(
                f"export const worker{file_index} = (): number => {index + file_index};\n",
                encoding="utf-8",
            )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=bridge_paths,
        include_patterns=["pkg_*/**/*.ts"],
        max_files=512,
    )

    counts_by_root: dict[str, int] = {}
    for candidate_path in candidate_paths:
        root_path = candidate_path.split("/src/", 1)[0]
        counts_by_root[root_path] = counts_by_root.get(root_path, 0) + 1

    assert 160 <= len(candidate_paths) < 224
    assert len(counts_by_root) == 32
    assert max(counts_by_root.values()) == 6
    assert min(counts_by_root.values()) >= 3
    assert "pkg_0/src/worker_0.ts" in candidate_paths
    assert "pkg_31/src/worker_0.ts" in candidate_paths


def test_candidate_repository_file_paths_shared_parent_roots_keep_broad_collect(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "candidate-shared-parent-roots-repo"
    bridge_paths: list[str] = []
    for index in range(32):
        module_dir = repo_path / "pkgs" / f"pkg_{index}" / "lib"
        module_dir.mkdir(parents=True)
        bridge_paths.append(f"pkgs/pkg_{index}")
        for file_index in range(12):
            (module_dir / f"worker_{file_index}.dart").write_text(
                f"int worker{file_index}() => {index + file_index};\n",
                encoding="utf-8",
            )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=bridge_paths,
        include_patterns=["pkgs/**/*.dart"],
        max_files=512,
    )

    counts_by_root: dict[str, int] = {}
    for candidate_path in candidate_paths:
        root_path = candidate_path.split("/lib/", 1)[0]
        counts_by_root[root_path] = counts_by_root.get(root_path, 0) + 1

    assert len(candidate_paths) > 160
    assert len(counts_by_root) == 32
    assert max(counts_by_root.values()) > 6
    assert min(counts_by_root.values()) >= 2


