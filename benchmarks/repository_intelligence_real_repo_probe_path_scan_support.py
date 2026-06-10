from __future__ import annotations

import os
from collections import Counter
from pathlib import Path, PurePosixPath


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _probe_repository_file_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    include_patterns: list[str],
    exclude_dirnames: set[str],
    max_files: int | None,
) -> list[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _git_repo_relative_files = probe_module._git_repo_relative_files
    _matches_focus_paths = probe_module._matches_focus_paths
    _probe_collection_rank = probe_module._probe_collection_rank

    git_relative_files = _git_repo_relative_files(repo_path)
    if git_relative_files is not None:
        collected: list[str] = []
        for relative in git_relative_files:
            if any(part in exclude_dirnames for part in Path(relative).parts[:-1]):
                continue
            if not _matches_focus_paths(relative, focus_paths):
                continue
            if include_patterns and not any(
                repository_service._matches_repository_pattern(relative, pattern)
                for pattern in include_patterns
            ):
                continue
            candidate = repo_path / relative
            if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
                continue
            collected.append(relative)
        ordered = sorted(
            collected,
            key=lambda relative_path: _probe_collection_rank(
                relative_path,
                repo_path=repo_path,
            ),
        )
        if max_files is not None:
            return ordered[:max_files]
        return ordered

    roots = [repo_path / path for path in focus_paths] if focus_paths else [repo_path]
    collected_paths: list[str] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            candidates = [root]
        else:
            candidates = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if name not in exclude_dirnames]
                candidates.extend(Path(dirpath) / name for name in filenames)
        for candidate in candidates:
            if candidate in seen or not candidate.is_file() or candidate.is_symlink():
                continue
            seen.add(candidate)
            relative = str(candidate.relative_to(repo_path)).replace("\\", "/")
            if include_patterns and not any(
                repository_service._matches_repository_pattern(relative, pattern)
                for pattern in include_patterns
            ):
                continue
            collected_paths.append(relative)
    ordered = sorted(
        collected_paths,
        key=lambda relative_path: _probe_collection_rank(
            relative_path,
            repo_path=repo_path,
        ),
    )
    if max_files is not None:
        return ordered[:max_files]
    return ordered


def _candidate_repository_file_paths(
    *,
    repo_path: Path,
    seed_paths: list[str],
    bridge_paths: list[str],
    include_patterns: list[str],
    max_files: int,
) -> list[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _looks_like_concrete_file_seed = probe_module._looks_like_concrete_file_seed
    _probe_collection_rank = probe_module._probe_collection_rank
    _should_group_focus_path_scan = probe_module._should_group_focus_path_scan

    collected: list[str] = []
    seen: set[str] = set()

    def _bridge_root_top_level_group_count(bridge_paths: list[str]) -> int:
        top_level_groups: set[str] = set()
        for bridge_path in bridge_paths:
            normalized_path = repository_service._normalize_repository_relative_path(bridge_path)
            if not normalized_path:
                continue
            top_level_groups.add(PurePosixPath(normalized_path).parts[0])
        return len(top_level_groups)

    def _bridge_root_spread_limit(*, remaining_files: int, bridge_path_count: int) -> int:
        if remaining_files <= 0 or bridge_path_count <= 0:
            return 0
        per_bridge_limit = max(1, min(4, (remaining_files // bridge_path_count) or 1))
        if bridge_path_count >= 48:
            return min(per_bridge_limit, 1)
        if bridge_path_count >= 24:
            return min(per_bridge_limit, 3)
        return per_bridge_limit

    def _ordered_file_paths(file_paths: list[str]) -> list[str]:
        return sorted(file_paths, key=_probe_collection_rank)

    def _collect_per_focus_path(
        focus_paths: list[str],
        *,
        per_focus_limit: int,
        total_limit: int,
    ) -> None:
        if per_focus_limit <= 0 or total_limit <= len(collected):
            return
        normalized_focus_paths = list(
            dict.fromkeys(
                repository_service._normalize_repository_relative_path(path)
                for path in focus_paths
                if str(path).strip()
            )
        )
        normalized_focus_paths = [path for path in normalized_focus_paths if path]
        if not normalized_focus_paths:
            return
        if not _should_group_focus_path_scan(normalized_focus_paths):
            for focus_path in normalized_focus_paths:
                if len(collected) >= total_limit:
                    return
                _collect(
                    [focus_path],
                    min(per_focus_limit, total_limit - len(collected)),
                )
            return
        remaining_total = total_limit - len(collected)
        if remaining_total <= 0:
            return
        candidate_file_paths = _probe_repository_file_paths(
            repo_path=repo_path,
            focus_paths=normalized_focus_paths,
            include_patterns=include_patterns,
            exclude_dirnames=set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS),
            max_files=None if len(normalized_focus_paths) > 1 else remaining_total,
        )
        ordered_focus_paths = sorted(
            normalized_focus_paths,
            key=lambda path: (-len(path), path),
        )
        per_focus_counts: Counter[str] = Counter()
        for relative_path in _ordered_file_paths(candidate_file_paths):
            matched_focus_path = next(
                (
                    focus_path
                    for focus_path in ordered_focus_paths
                    if relative_path == focus_path or relative_path.startswith(f"{focus_path}/")
                ),
                None,
            )
            if matched_focus_path is None:
                continue
            if per_focus_counts[matched_focus_path] >= per_focus_limit:
                continue
            if relative_path in seen:
                continue
            seen.add(relative_path)
            collected.append(relative_path)
            per_focus_counts[matched_focus_path] += 1
            if len(collected) >= total_limit:
                return

    def _collect(focus_paths: list[str], remaining_files: int) -> None:
        if remaining_files <= 0:
            return
        candidate_file_paths = _probe_repository_file_paths(
            repo_path=repo_path,
            focus_paths=focus_paths,
            include_patterns=include_patterns,
            exclude_dirnames=set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS),
            max_files=remaining_files,
        )
        for relative_path in _ordered_file_paths(candidate_file_paths):
            if relative_path in seen:
                continue
            seen.add(relative_path)
            collected.append(relative_path)
            if len(collected) >= max_files:
                return

    normalized_seed_paths = [
        repository_service._normalize_repository_relative_path(path)
        for path in seed_paths
        if str(path).strip()
    ]
    normalized_bridge_paths = [
        repository_service._normalize_repository_relative_path(path)
        for path in bridge_paths
        if str(path).strip()
    ]
    concrete_seed_paths = [
        path for path in normalized_seed_paths if path and _looks_like_concrete_file_seed(path)
    ]
    if normalized_seed_paths:
        seed_budget = min(
            max_files,
            max(
                len(concrete_seed_paths) * 12,
                len(normalized_seed_paths) * 6,
                min(64, max_files),
            ),
        )
        _collect(normalized_seed_paths, seed_budget)
    remaining_files = max_files - len(collected)
    if remaining_files > 0 and normalized_bridge_paths:
        bridge_path_count = len(normalized_bridge_paths)
        bridge_spread_limit = 0
        if bridge_path_count > 1:
            bridge_spread_limit = _bridge_root_spread_limit(
                remaining_files=remaining_files,
                bridge_path_count=bridge_path_count,
            )
            reserved_bridge_budget = min(
                remaining_files,
                bridge_spread_limit * bridge_path_count,
            )
            _collect_per_focus_path(
                normalized_bridge_paths,
                per_focus_limit=bridge_spread_limit,
                total_limit=len(collected) + reserved_bridge_budget,
            )
            remaining_files = max_files - len(collected)
        bridge_budget = min(
            remaining_files,
            max(min(96, max_files), min(256, max(max_files // 4, 1))),
        )
        if (
            bridge_budget > 0
            and bridge_path_count >= 24
            and _bridge_root_top_level_group_count(normalized_bridge_paths) >= 8
        ):
            distributed_bridge_limit = _bridge_root_spread_limit(
                remaining_files=bridge_budget,
                bridge_path_count=bridge_path_count,
            )
            distributed_bridge_budget = min(
                bridge_budget,
                distributed_bridge_limit * bridge_path_count,
            )
            _collect_per_focus_path(
                normalized_bridge_paths,
                per_focus_limit=distributed_bridge_limit,
                total_limit=len(collected) + distributed_bridge_budget,
            )
        else:
            _collect(normalized_bridge_paths, bridge_budget)
        remaining_files = max_files - len(collected)
    if remaining_files > 0 and len(collected) < min(32, max_files):
        fallback_budget = min(
            remaining_files,
            max(min(64, max_files), min(128, max(max_files // 8, 1))),
        )
        _collect([], fallback_budget)
    return collected


def _should_group_focus_path_scan(focus_paths: list[str]) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path

    normalized_focus_paths = list(
        dict.fromkeys(
            repository_service._normalize_repository_relative_path(path)
            for path in focus_paths
            if str(path).strip()
        )
    )
    normalized_focus_paths = [path for path in normalized_focus_paths if path]
    focus_path_count = len(normalized_focus_paths)
    if focus_path_count < 2:
        return False

    def _is_source_root_focus_path(path: str) -> bool:
        if repository_service._is_test_path(path) or _is_non_operational_profile_path(path):
            return False
        parts = PurePosixPath(path).parts
        if not parts:
            return False
        basename = parts[-1].lower()
        if basename == "src" or basename.startswith("src-"):
            return True
        return (
            len(parts) >= 3
            and parts[-2].lower() == "main"
            and parts[-3].lower() == "src"
        )

    top_level_group_count = len(
        {
            PurePosixPath(path).parts[0]
            for path in normalized_focus_paths
            if PurePosixPath(path).parts
        }
    )
    if focus_path_count >= 24:
        return True
    if focus_path_count >= 20 and top_level_group_count <= 2:
        return True
    return focus_path_count >= 5 and all(
        _is_source_root_focus_path(path)
        for path in normalized_focus_paths
    )


def _should_use_seeded_profile_candidate_scan(
    *,
    seed_paths: list[str],
    bridge_paths: list[str],
) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_seed_paths = [
        normalized_path
        for path in seed_paths
        if (
            normalized_path := repository_service._normalize_repository_relative_path(path)
        )
    ]
    if normalized_seed_paths:
        return True
    normalized_bridge_paths = [
        normalized_path
        for path in bridge_paths
        if (
            normalized_path := repository_service._normalize_repository_relative_path(path)
        )
    ]
    if not normalized_bridge_paths:
        return False
    top_level_group_count = len(
        {
            PurePosixPath(path).parts[0]
            for path in normalized_bridge_paths
            if PurePosixPath(path).parts
        }
    )
    return not (len(normalized_bridge_paths) <= 10 and top_level_group_count > 2)


def _normalized_candidate_file_paths(
    *,
    repo_path: Path,
    candidate_file_paths: list[str],
    include_patterns: list[str],
    max_files: int,
) -> list[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _probe_collection_rank = probe_module._probe_collection_rank

    normalized_paths: list[str] = []
    seen: set[str] = set()
    excluded_parts = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
    for raw_path in candidate_file_paths:
        normalized_path = repository_service._normalize_repository_relative_path(raw_path)
        if not normalized_path or normalized_path in seen:
            continue
        if any(part in excluded_parts for part in PurePosixPath(normalized_path).parts[:-1]):
            continue
        candidate = repo_path / normalized_path
        if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
            continue
        if include_patterns and not any(
            repository_service._matches_repository_pattern(normalized_path, pattern)
            for pattern in include_patterns
        ):
            continue
        seen.add(normalized_path)
        normalized_paths.append(normalized_path)
    ordered_paths = sorted(normalized_paths, key=_probe_collection_rank)
    return ordered_paths[:max_files]


def _looks_like_concrete_file_seed(path: str) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    basename = PurePosixPath(normalized_path).name
    if not basename:
        return False
    return bool(PurePosixPath(basename).suffix) or (
        basename in repository_service._TEXT_FILE_BASENAMES
    )


def _connected_map_candidate_file_limit(
    *,
    max_files: int,
    max_connected_files: int,
    concrete_seed_count: int,
) -> int:
    if concrete_seed_count >= 8:
        return min(max_files, max(256, max_connected_files))
    if concrete_seed_count >= 3:
        return min(max_files, max(320, max_connected_files + (max_connected_files // 2)))
    return min(max_files, max(800, max_connected_files * 4))


def _seed_dependency_files(
    *,
    candidate_file_paths: list[str],
    seed_paths: list[str],
    max_connected_files: int,
) -> list[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    seeds: list[str] = []
    seen: set[str] = set()
    candidate_lookup = set(candidate_file_paths)
    for seed_path in seed_paths:
        normalized_seed = repository_service._normalize_repository_relative_path(seed_path)
        if not normalized_seed:
            continue
        if normalized_seed in candidate_lookup and normalized_seed not in seen:
            seen.add(normalized_seed)
            seeds.append(normalized_seed)
            continue
        scoped_matches = [
            file_path
            for file_path in candidate_file_paths
            if file_path == normalized_seed or file_path.startswith(f"{normalized_seed}/")
        ]
        for scoped_match in scoped_matches:
            if scoped_match in seen:
                continue
            seen.add(scoped_match)
            seeds.append(scoped_match)
            if len(seeds) >= max_connected_files:
                return seeds
    return seeds
