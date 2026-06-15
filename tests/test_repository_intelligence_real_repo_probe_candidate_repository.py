"""Tests for repository_intelligence_real_repo_probe: candidate_repository.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from benchmarks import repository_intelligence_real_repo_probe_path_scan_support as path_scan_support
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


def test_candidate_repository_file_paths_reuses_grouped_probe_for_spread_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "candidate-grouped-spread-repo"
    repo_path.mkdir()
    probe_calls: list[tuple[list[str], int | None, int | None]] = []

    def _fake_probe_repository_file_paths(
        *,
        repo_path: Path,
        focus_paths: list[str],
        include_patterns: list[str],
        exclude_dirnames: set[str],
        max_files: int | None,
        per_focus_limit: int | None = None,
    ) -> list[str]:
        probe_calls.append((list(focus_paths), max_files, per_focus_limit))
        candidate_paths: list[str] = []
        target_focus_paths = focus_paths or ["fallback"]
        for focus_path in target_focus_paths:
            for index in range(3):
                candidate_paths.append(f"{focus_path}/worker_{index}.ts")
        return candidate_paths

    monkeypatch.setattr(
        path_scan_support,
        "_probe_repository_file_paths",
        _fake_probe_repository_file_paths,
    )

    bridge_paths = ["alpha", "beta", "gamma", "delta", "epsilon"]
    ordered_bridge_paths = sorted(bridge_paths)
    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=bridge_paths,
        include_patterns=["**/*.ts"],
        max_files=10,
    )

    assert probe_calls == [(ordered_bridge_paths, 10, 2)]
    assert candidate_paths == [
        "alpha/worker_0.ts",
        "alpha/worker_1.ts",
        "beta/worker_0.ts",
        "beta/worker_1.ts",
        "delta/worker_0.ts",
        "delta/worker_1.ts",
        "epsilon/worker_0.ts",
        "epsilon/worker_1.ts",
        "gamma/worker_0.ts",
        "gamma/worker_1.ts",
    ]


def test_candidate_repository_file_paths_reuses_prefetched_bridge_candidates_for_followup_collect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "candidate-prefetched-bridge-reuse-repo"
    repo_path.mkdir()
    probe_calls: list[tuple[list[str], int | None, int | None]] = []

    def _fake_probe_repository_file_paths(
        *,
        repo_path: Path,
        focus_paths: list[str],
        include_patterns: list[str],
        exclude_dirnames: set[str],
        max_files: int | None,
        per_focus_limit: int | None = None,
    ) -> list[str]:
        probe_calls.append((list(focus_paths), max_files, per_focus_limit))
        if per_focus_limit is None:
            raise AssertionError("followup bridge collect should reuse prefetched grouped results")
        candidate_paths: list[str] = []
        for focus_path in focus_paths:
            for index in range(7):
                candidate_paths.append(f"{focus_path}/worker_{index}.ts")
        return candidate_paths

    def _rank(
        relative_path: str,
        *,
        repo_path: Path | None = None,
    ) -> tuple[int, int, int, int, str]:
        return (0, 0, 0, 0, relative_path)

    monkeypatch.setattr(
        path_scan_support,
        "_probe_repository_file_paths",
        _fake_probe_repository_file_paths,
    )
    monkeypatch.setattr(probe_module, "_probe_collection_rank", _rank)

    bridge_paths = ["alpha", "beta", "gamma", "delta", "epsilon"]
    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=bridge_paths,
        include_patterns=["**/*.ts"],
        max_files=32,
    )

    assert probe_calls == [(sorted(bridge_paths), 35, 7)]
    assert len(candidate_paths) == 32
    assert candidate_paths[:8] == [
        "alpha/worker_0.ts",
        "alpha/worker_1.ts",
        "alpha/worker_2.ts",
        "alpha/worker_3.ts",
        "beta/worker_0.ts",
        "beta/worker_1.ts",
        "beta/worker_2.ts",
        "beta/worker_3.ts",
    ]
    assert len(set(candidate_paths)) == 32


def test_probe_repository_file_paths_grouped_focus_limit_keeps_full_order_cache_separate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "probe-grouped-focus-limit-repo"
    (repo_path / "alpha").mkdir(parents=True)
    (repo_path / "beta").mkdir(parents=True)
    for relative_path in ("alpha/a.ts", "alpha/z.ts", "beta/a.ts", "beta/b.ts"):
        candidate_path = repo_path / relative_path
        candidate_path.write_text("export const value = 1;\n", encoding="utf-8")
    _init_git_repo(repo_path)
    path_scan_support.clear_probe_repository_file_paths_cache()

    def _rank(relative_path: str, *, repo_path: Path | None = None) -> tuple[int, int, int, int, str]:
        rank_map = {
            "alpha/a.ts": (1, 1, 1, 1, "alpha/a.ts"),
            "alpha/z.ts": (0, 0, 0, 0, "alpha/z.ts"),
            "beta/a.ts": (0, 0, 0, 1, "beta/a.ts"),
            "beta/b.ts": (0, 0, 1, 0, "beta/b.ts"),
        }
        return rank_map[relative_path]

    monkeypatch.setattr(probe_module, "_probe_collection_rank", _rank)

    grouped_paths = path_scan_support._probe_repository_file_paths(
        repo_path=repo_path,
        focus_paths=["alpha", "beta"],
        include_patterns=["**/*.ts"],
        exclude_dirnames=set(),
        max_files=8,
        per_focus_limit=1,
    )

    full_paths = path_scan_support._probe_repository_file_paths(
        repo_path=repo_path,
        focus_paths=["alpha", "beta"],
        include_patterns=["**/*.ts"],
        exclude_dirnames=set(),
        max_files=None,
    )

    assert grouped_paths == ["alpha/z.ts", "beta/a.ts"]
    assert full_paths == ["alpha/z.ts", "beta/a.ts", "beta/b.ts", "alpha/a.ts"]


def test_probe_repository_file_paths_reuses_grouped_cache_for_single_best_global_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "probe-grouped-single-best-cache-repo"
    (repo_path / "alpha").mkdir(parents=True)
    (repo_path / "beta").mkdir(parents=True)
    for relative_path in ("alpha/a.ts", "alpha/z.ts", "beta/a.ts", "beta/b.ts"):
        candidate_path = repo_path / relative_path
        candidate_path.write_text("export const value = 1;\n", encoding="utf-8")
    _init_git_repo(repo_path)
    path_scan_support.clear_probe_repository_file_paths_cache()

    def _rank(relative_path: str, *, repo_path: Path | None = None) -> tuple[int, int, int, int, str]:
        rank_map = {
            "alpha/a.ts": (1, 1, 1, 1, "alpha/a.ts"),
            "alpha/z.ts": (0, 0, 0, 0, "alpha/z.ts"),
            "beta/a.ts": (0, 0, 0, 1, "beta/a.ts"),
            "beta/b.ts": (0, 0, 1, 0, "beta/b.ts"),
        }
        return rank_map[relative_path]

    monkeypatch.setattr(probe_module, "_probe_collection_rank", _rank)

    grouped_paths = path_scan_support._probe_repository_file_paths(
        repo_path=repo_path,
        focus_paths=["alpha", "beta"],
        include_patterns=["**/*.ts"],
        exclude_dirnames=set(),
        max_files=8,
        per_focus_limit=1,
    )

    def _unexpected_git_relative_files_for_focus_paths(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("single-best lookup should reuse grouped cache instead of rescanning")

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files_for_focus_paths",
        _unexpected_git_relative_files_for_focus_paths,
    )

    best_path = path_scan_support._probe_repository_file_paths(
        repo_path=repo_path,
        focus_paths=["alpha", "beta"],
        include_patterns=["**/*.ts"],
        exclude_dirnames=set(),
        max_files=1,
    )

    assert grouped_paths == ["alpha/z.ts", "beta/a.ts"]
    assert best_path == ["alpha/z.ts"]


def test_probe_repository_file_paths_grouped_git_listing_validates_each_candidate_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "probe-grouped-git-listing-lazy-validation-repo"
    repo_path.mkdir()
    path_scan_support.clear_probe_repository_file_paths_cache()
    validation_calls: list[str] = []

    def _focused_git_relative_files(
        _repo_path: Path,
        *,
        focus_paths: list[str],
    ) -> list[str]:
        assert focus_paths == ["alpha", "beta"]
        return [
            "alpha/2.ts",
            "alpha/1.ts",
            "alpha/0.ts",
            "beta/2.ts",
            "beta/1.ts",
            "beta/0.ts",
        ]

    def _rank(relative_path: str, *, repo_path: Path | None = None) -> tuple[int, int, int, int, str]:
        rank_map = {
            "alpha/0.ts": (0, 0, 0, 0, "alpha/0.ts"),
            "alpha/1.ts": (0, 0, 0, 1, "alpha/1.ts"),
            "alpha/2.ts": (0, 0, 0, 2, "alpha/2.ts"),
            "beta/0.ts": (0, 0, 0, 0, "beta/0.ts"),
            "beta/1.ts": (0, 0, 0, 1, "beta/1.ts"),
            "beta/2.ts": (0, 0, 0, 2, "beta/2.ts"),
        }
        return rank_map[relative_path]

    def _is_regular_non_symlink_relative_path(
        _repo_path: Path,
        relative_path: str,
    ) -> bool:
        if not relative_path.endswith(".ts"):
            return False
        validation_calls.append(relative_path)
        return True

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files_for_focus_paths",
        _focused_git_relative_files,
    )
    monkeypatch.setattr(probe_module, "_probe_collection_rank", _rank)
    monkeypatch.setattr(
        path_scan_support,
        "_is_regular_non_symlink_relative_path",
        _is_regular_non_symlink_relative_path,
    )

    grouped_paths = path_scan_support._probe_repository_file_paths(
        repo_path=repo_path,
        focus_paths=["alpha", "beta"],
        include_patterns=["**/*.ts"],
        exclude_dirnames=set(),
        max_files=4,
        per_focus_limit=1,
    )

    assert grouped_paths == ["alpha/0.ts", "beta/0.ts"]
    assert validation_calls == ["alpha/0.ts", "beta/0.ts"]


def test_validated_ranked_repository_relative_paths_stops_after_filling_requested_slice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "validated-ranked-top-slice-repo"
    repo_path.mkdir()
    validation_calls: list[str] = []

    def _rank(relative_path: str, *, repo_path: Path | None = None) -> tuple[int, int, int, int, str]:
        index = int(relative_path.rsplit("/", 1)[1].split(".", 1)[0])
        return (0, 0, 0, index, relative_path)

    def _is_regular_non_symlink_relative_path(
        _repo_path: Path,
        relative_path: str,
    ) -> bool:
        validation_calls.append(relative_path)
        return True

    monkeypatch.setattr(probe_module, "_probe_collection_rank", _rank)
    monkeypatch.setattr(
        path_scan_support,
        "_is_regular_non_symlink_relative_path",
        _is_regular_non_symlink_relative_path,
    )

    ranked_paths = path_scan_support._validated_ranked_repository_relative_paths(
        [f"pkg/{index}.ts" for index in range(16)],
        repo_path=repo_path,
        max_files=2,
    )

    assert ranked_paths == ["pkg/0.ts", "pkg/1.ts"]
    assert validation_calls == ["pkg/0.ts", "pkg/1.ts"]


def test_validated_ranked_repository_relative_paths_expands_when_top_ranked_paths_are_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "validated-ranked-invalid-top-repo"
    repo_path.mkdir()
    validation_calls: list[str] = []

    def _rank(relative_path: str, *, repo_path: Path | None = None) -> tuple[int, int, int, int, str]:
        index = int(relative_path.rsplit("/", 1)[1].split(".", 1)[0])
        return (0, 0, 0, index, relative_path)

    def _is_regular_non_symlink_relative_path(
        _repo_path: Path,
        relative_path: str,
    ) -> bool:
        validation_calls.append(relative_path)
        return relative_path not in {"pkg/0.ts", "pkg/1.ts"}

    monkeypatch.setattr(probe_module, "_probe_collection_rank", _rank)
    monkeypatch.setattr(
        path_scan_support,
        "_is_regular_non_symlink_relative_path",
        _is_regular_non_symlink_relative_path,
    )

    ranked_paths = path_scan_support._validated_ranked_repository_relative_paths(
        [f"pkg/{index}.ts" for index in range(16)],
        repo_path=repo_path,
        max_files=2,
    )

    assert ranked_paths == ["pkg/2.ts", "pkg/3.ts"]
    assert validation_calls == ["pkg/0.ts", "pkg/1.ts", "pkg/2.ts", "pkg/3.ts"]


def test_validated_ranked_repository_relative_paths_small_candidate_sets_rank_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "validated-ranked-single-pass-repo"
    repo_path.mkdir()
    rank_calls: list[int | None] = []
    validation_calls: list[str] = []
    original_ranked_repository_relative_paths = (
        path_scan_support._ranked_repository_relative_paths
    )

    def _rank(relative_path: str, *, repo_path: Path | None = None) -> tuple[int, int, int, int, str]:
        index = int(relative_path.rsplit("/", 1)[1].split(".", 1)[0])
        return (0, 0, 0, index, relative_path)

    def _recording_ranked_repository_relative_paths(
        relative_paths: list[str],
        *,
        repo_path: Path,
        max_files: int | None,
    ) -> list[str]:
        rank_calls.append(max_files)
        return original_ranked_repository_relative_paths(
            relative_paths,
            repo_path=repo_path,
            max_files=max_files,
        )

    def _is_regular_non_symlink_relative_path(
        _repo_path: Path,
        relative_path: str,
    ) -> bool:
        validation_calls.append(relative_path)
        return relative_path not in {"pkg/0.ts", "pkg/1.ts"}

    monkeypatch.setattr(probe_module, "_probe_collection_rank", _rank)
    monkeypatch.setattr(
        path_scan_support,
        "_ranked_repository_relative_paths",
        _recording_ranked_repository_relative_paths,
    )
    monkeypatch.setattr(
        path_scan_support,
        "_is_regular_non_symlink_relative_path",
        _is_regular_non_symlink_relative_path,
    )

    ranked_paths = path_scan_support._validated_ranked_repository_relative_paths(
        [f"pkg/{index}.ts" for index in range(16)],
        repo_path=repo_path,
        max_files=2,
    )

    assert ranked_paths == ["pkg/2.ts", "pkg/3.ts"]
    assert validation_calls == ["pkg/0.ts", "pkg/1.ts", "pkg/2.ts", "pkg/3.ts"]
    assert rank_calls == [None]


def test_probe_repository_file_paths_grouped_git_listing_skips_invalid_top_ranked_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "probe-grouped-git-listing-invalid-top-ranked-repo"
    repo_path.mkdir()
    path_scan_support.clear_probe_repository_file_paths_cache()

    def _focused_git_relative_files(
        _repo_path: Path,
        *,
        focus_paths: list[str],
    ) -> list[str]:
        assert focus_paths == ["alpha", "beta"]
        return [
            "alpha/0.ts",
            "alpha/1.ts",
            "beta/0.ts",
            "beta/1.ts",
        ]

    def _rank(relative_path: str, *, repo_path: Path | None = None) -> tuple[int, int, int, int, str]:
        rank_map = {
            "alpha/0.ts": (0, 0, 0, 0, "alpha/0.ts"),
            "alpha/1.ts": (0, 0, 0, 1, "alpha/1.ts"),
            "beta/0.ts": (0, 0, 0, 0, "beta/0.ts"),
            "beta/1.ts": (0, 0, 0, 1, "beta/1.ts"),
        }
        return rank_map[relative_path]

    def _is_regular_non_symlink_relative_path(
        _repo_path: Path,
        relative_path: str,
    ) -> bool:
        return relative_path not in {"alpha/0.ts", "beta/0.ts"}

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files_for_focus_paths",
        _focused_git_relative_files,
    )
    monkeypatch.setattr(probe_module, "_probe_collection_rank", _rank)
    monkeypatch.setattr(
        path_scan_support,
        "_is_regular_non_symlink_relative_path",
        _is_regular_non_symlink_relative_path,
    )

    grouped_paths = path_scan_support._probe_repository_file_paths(
        repo_path=repo_path,
        focus_paths=["alpha", "beta"],
        include_patterns=["**/*.ts"],
        exclude_dirnames=set(),
        max_files=4,
        per_focus_limit=1,
    )

    assert grouped_paths == ["alpha/1.ts", "beta/1.ts"]


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


def test_candidate_repository_file_paths_skips_redundant_pattern_matching_for_catch_all(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "candidate-catch-all-pattern-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    def _unexpected_matches_repository_pattern(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("catch-all include patterns should bypass per-file glob matching")

    monkeypatch.setattr(
        repository_service,
        "_matches_repository_pattern",
        _unexpected_matches_repository_pattern,
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=["src"],
        include_patterns=["**/*"],
        max_files=32,
    )

    assert candidate_paths == ["src/main.ts"]


def test_normalized_candidate_file_paths_skip_pattern_matching_for_catch_all(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "normalized-catch-all-pattern-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )

    def _unexpected_matches_repository_pattern(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("catch-all include patterns should bypass per-file glob matching")

    monkeypatch.setattr(
        repository_service,
        "_matches_repository_pattern",
        _unexpected_matches_repository_pattern,
    )

    candidate_paths = path_scan_support._normalized_candidate_file_paths(
        repo_path=repo_path,
        candidate_file_paths=["src/main.ts"],
        include_patterns=["**/*"],
        max_files=32,
    )

    assert candidate_paths == ["src/main.ts"]


def test_candidate_repository_file_paths_uses_direct_concrete_focus_files_without_git_listing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "candidate-direct-focus-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    def _unexpected_git_relative_files(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("concrete file focus should bypass git-wide probe enumeration")

    def _unexpected_iter_repository_files(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("concrete file focus should bypass repository tree walk")

    monkeypatch.setattr(probe_module, "_git_repo_relative_files", _unexpected_git_relative_files)
    monkeypatch.setattr(repository_service, "_iter_repository_files", _unexpected_iter_repository_files)

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=["src/main.ts"],
        bridge_paths=[],
        include_patterns=["src/**/*.ts"],
        max_files=32,
    )

    assert candidate_paths == ["src/main.ts"]


def test_candidate_repository_file_paths_direct_focus_fast_path_avoids_focus_resolve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "candidate-direct-focus-resolve-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.ts").write_text(
        "export const run = (): string => 'ok';\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    original_path_resolve = Path.resolve

    def _guarded_resolve(self: Path, *args, **kwargs) -> Path:
        if self == repo_path / "src" / "main.ts":
            raise AssertionError("direct concrete focus path should not call Path.resolve()")
        return original_path_resolve(self, *args, **kwargs)

    monkeypatch.setattr(path_scan_support, "_repo_cache_key", lambda _repo_path: "repo-cache-key")
    monkeypatch.setattr(Path, "resolve", _guarded_resolve)

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=["src/main.ts"],
        bridge_paths=[],
        include_patterns=["src/**/*.ts"],
        max_files=32,
    )

    assert candidate_paths == ["src/main.ts"]


def test_candidate_repository_file_paths_uses_focused_git_listing_for_bridge_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "candidate-focused-git-listing-repo"
    (repo_path / "src").mkdir(parents=True)
    for index in range(40):
        (repo_path / "src" / f"worker_{index}.ts").write_text(
            f"export const worker{index} = (): number => {index};\n",
            encoding="utf-8",
        )
    _init_git_repo(repo_path)
    focused_git_calls: list[list[str]] = []

    def _unexpected_git_relative_files(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("bridge-path scans should avoid whole-repo git listing")

    def _focused_git_relative_files(
        _repo_path: Path,
        *,
        focus_paths: list[str],
    ) -> list[str]:
        focused_git_calls.append(list(focus_paths))
        return [f"src/worker_{index}.ts" for index in range(40)]

    monkeypatch.setattr(probe_module, "_git_repo_relative_files", _unexpected_git_relative_files)
    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files_for_focus_paths",
        _focused_git_relative_files,
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=["src"],
        include_patterns=["src/**/*.ts"],
        max_files=32,
    )

    assert len(candidate_paths) == 32
    assert candidate_paths[0] == "src/worker_0.ts"
    assert focused_git_calls == [["src"]]


def test_candidate_repository_file_paths_skips_root_fallback_after_sufficient_focused_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "candidate-skip-root-fallback-repo"
    repo_path.mkdir()
    probe_calls: list[tuple[list[str], int | None, int | None]] = []

    def _fake_probe_repository_file_paths(
        *,
        repo_path: Path,
        focus_paths: list[str],
        include_patterns: list[str],
        exclude_dirnames: set[str],
        max_files: int | None,
        per_focus_limit: int | None = None,
    ) -> list[str]:
        probe_calls.append((list(focus_paths), max_files, per_focus_limit))
        if not focus_paths:
            raise AssertionError("root fallback should not run after sufficient focused results")
        if per_focus_limit is not None:
            return [
                f"{focus_path}/worker_{index}.ts"
                for focus_path in focus_paths
                for index in range(6)
            ]
        return [
            f"{focus_path}/worker_{index}.ts"
            for focus_path in focus_paths
            for index in range(3)
        ]

    monkeypatch.setattr(
        path_scan_support,
        "_probe_repository_file_paths",
        _fake_probe_repository_file_paths,
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=["alpha", "beta"],
        bridge_paths=["gamma", "delta"],
        include_patterns=["**/*.ts"],
        max_files=32,
    )

    assert probe_calls
    assert all(focus_paths for focus_paths, _max_files, _per_focus_limit in probe_calls)
    assert any(
        focus_paths == ["alpha", "beta"]
        for focus_paths, _max_files, _per_focus_limit in probe_calls
    )
    assert any(
        set(focus_paths) == {"gamma", "delta"}
        for focus_paths, _max_files, _per_focus_limit in probe_calls
    )
    assert len(candidate_paths) >= 12


def test_candidate_repository_file_paths_preserves_probe_repository_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "candidate-order-repo"
    repo_path.mkdir()

    def _ordered_probe_repository_file_paths(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return ["src/main.ts", "src/helper.ts"]

    def _unexpected_probe_collection_rank(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("candidate collection should not rerank preordered probe paths")

    monkeypatch.setattr(
        path_scan_support,
        "_probe_repository_file_paths",
        _ordered_probe_repository_file_paths,
    )
    monkeypatch.setattr(
        probe_module,
        "_probe_collection_rank",
        _unexpected_probe_collection_rank,
    )

    candidate_paths = _candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=["src"],
        bridge_paths=[],
        include_patterns=["src/**/*.ts"],
        max_files=2,
    )

    assert candidate_paths == ["src/main.ts", "src/helper.ts"]
