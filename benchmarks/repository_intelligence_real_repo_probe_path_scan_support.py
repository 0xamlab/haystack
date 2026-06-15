from __future__ import annotations

import os
import stat
from bisect import bisect_left
from collections import Counter
from pathlib import Path, PurePosixPath

_INCLUDE_PATTERN_SPEC_CACHE_LIMIT = 256
_INCLUDE_PATTERN_SPEC_CACHE: dict[tuple[str, ...], tuple[tuple[str, ...], bool]] = {}
_CANDIDATE_REPOSITORY_FILE_PATHS_CACHE_LIMIT = 256
_CANDIDATE_REPOSITORY_FILE_PATHS_CACHE: dict[
    tuple[
        str,
        tuple[str, ...],
        bool,
        tuple[str, ...],
        bool,
        tuple[str, ...],
        int,
    ],
    list[str],
] = {}
_PROBE_REPOSITORY_FILE_PATHS_CACHE_LIMIT = 256
_PROBE_REPOSITORY_FILE_PATHS_CACHE: dict[
    tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], int | None, int | None],
    list[str],
] = {}
_RANK_VALIDATION_OVERSCAN = 8
_FULL_RANK_VALIDATION_SCAN_LIMIT = 1024


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _repo_cache_key(repo_path: Path) -> str:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    return collection_support._repo_cache_key(repo_path)


def _path_segments(path: str) -> tuple[str, ...]:
    normalized_path = str(path).replace("\\", "/").strip("/")
    if not normalized_path:
        return ()
    return tuple(part for part in normalized_path.split("/") if part)


def _top_level_path_group(path: str) -> str | None:
    segments = _path_segments(path)
    if not segments:
        return None
    return segments[0]


def _is_regular_non_symlink_path(candidate: Path) -> bool:
    try:
        candidate_stat = candidate.lstat()
    except OSError:
        return False
    return stat.S_ISREG(candidate_stat.st_mode) and not stat.S_ISLNK(candidate_stat.st_mode)


def _is_regular_non_symlink_relative_path(
    repo_path: Path,
    relative_path: str,
) -> bool:
    from benchmarks import (
        repository_intelligence_real_repo_probe_profile_path_classification_support
        as classification_support,
    )

    candidate_stat = classification_support._repo_file_lstat(repo_path, relative_path)
    if candidate_stat is None:
        return False
    return stat.S_ISREG(candidate_stat.st_mode) and not stat.S_ISLNK(candidate_stat.st_mode)


def _include_pattern_spec(
    include_patterns: list[str],
) -> tuple[tuple[str, ...], bool]:
    repository_service = _probe_module().repository_service

    cache_key = tuple(str(pattern) for pattern in include_patterns if str(pattern).strip())
    cached_spec = _INCLUDE_PATTERN_SPEC_CACHE.get(cache_key)
    if cached_spec is not None:
        return cached_spec
    normalized_include_patterns = tuple(
        repository_service._normalize_repository_relative_path(pattern)
        for pattern in cache_key
    )
    include_patterns_match_all_files = any(
        pattern in {"*", "**/*"} for pattern in normalized_include_patterns
    )
    spec = (normalized_include_patterns, include_patterns_match_all_files)
    if len(_INCLUDE_PATTERN_SPEC_CACHE) >= _INCLUDE_PATTERN_SPEC_CACHE_LIMIT:
        oldest_key = next(iter(_INCLUDE_PATTERN_SPEC_CACHE))
        _INCLUDE_PATTERN_SPEC_CACHE.pop(oldest_key, None)
    _INCLUDE_PATTERN_SPEC_CACHE[cache_key] = spec
    return spec


def clear_probe_repository_file_paths_cache() -> None:
    _PROBE_REPOSITORY_FILE_PATHS_CACHE.clear()


def probe_repository_file_paths_cache_size() -> int:
    return len(_PROBE_REPOSITORY_FILE_PATHS_CACHE)


def clear_candidate_repository_file_paths_cache() -> None:
    _CANDIDATE_REPOSITORY_FILE_PATHS_CACHE.clear()


def candidate_repository_file_paths_cache_size() -> int:
    return len(_CANDIDATE_REPOSITORY_FILE_PATHS_CACHE)


def _bounded_ranked_path_insert(
    ranked_candidates: list[tuple[tuple[int, int, int, int, str], str]],
    *,
    candidate: tuple[tuple[int, int, int, int, str], str],
    limit: int,
) -> None:
    if limit <= 0:
        return
    if len(ranked_candidates) < limit:
        ranked_candidates.append(candidate)
        if len(ranked_candidates) == limit:
            ranked_candidates.sort()
        return
    if candidate >= ranked_candidates[-1]:
        return
    insertion_index = bisect_left(ranked_candidates, candidate)
    ranked_candidates.insert(insertion_index, candidate)
    ranked_candidates.pop()


def _ranked_repository_relative_paths(
    relative_paths: list[str],
    *,
    repo_path: Path,
    max_files: int | None,
) -> list[str]:
    _probe_collection_rank = _probe_module()._probe_collection_rank
    if max_files is None or len(relative_paths) <= max_files:
        return sorted(
            relative_paths,
            key=lambda relative_path: _probe_collection_rank(
                relative_path,
                repo_path=repo_path,
            ),
        )
    ranked_candidates: list[tuple[tuple[int, int, int, int, str], str]] = []
    for relative_path in relative_paths:
        _bounded_ranked_path_insert(
            ranked_candidates,
            candidate=(
                _probe_collection_rank(
                    relative_path,
                    repo_path=repo_path,
                ),
                relative_path,
            ),
            limit=max_files,
        )
    if len(ranked_candidates) < max_files:
        ranked_candidates.sort()
    return [relative_path for _rank, relative_path in ranked_candidates]


def _matched_focus_path(
    relative_path: str,
    *,
    ordered_focus_paths: tuple[str, ...],
) -> str | None:
    return next(
        (
            focus_path
            for focus_path in ordered_focus_paths
            if relative_path == focus_path or relative_path.startswith(f"{focus_path}/")
        ),
        None,
    )


def _ranked_repository_relative_paths_by_focus(
    relative_paths: list[str],
    *,
    repo_path: Path,
    normalized_focus_paths: list[str],
    per_focus_limit: int,
) -> list[str]:
    _probe_collection_rank = _probe_module()._probe_collection_rank
    ordered_focus_paths = tuple(
        sorted(
            normalized_focus_paths,
            key=lambda path: (-len(path), path),
        )
    )
    ranked_candidates_by_focus_path: dict[
        str,
        list[tuple[tuple[int, int, int, int, str], str]],
    ] = {focus_path: [] for focus_path in normalized_focus_paths}
    for relative_path in relative_paths:
        matched_focus_path = _matched_focus_path(
            relative_path,
            ordered_focus_paths=ordered_focus_paths,
        )
        if matched_focus_path is None:
            continue
        _bounded_ranked_path_insert(
            ranked_candidates_by_focus_path[matched_focus_path],
            candidate=(
                _probe_collection_rank(
                    relative_path,
                    repo_path=repo_path,
                ),
                relative_path,
            ),
            limit=per_focus_limit,
        )
    ranked_paths: list[str] = []
    for focus_path in normalized_focus_paths:
        ranked_candidates = ranked_candidates_by_focus_path[focus_path]
        if len(ranked_candidates) < per_focus_limit:
            ranked_candidates.sort()
        ranked_paths.extend(relative_path for _rank, relative_path in ranked_candidates)
    return ranked_paths


def _validated_ranked_repository_relative_paths(
    relative_paths: list[str],
    *,
    repo_path: Path,
    max_files: int | None,
) -> list[str]:
    def _validated_from_ordered_paths(ordered_paths: list[str]) -> list[str]:
        validated_paths: list[str] = []
        for relative_path in ordered_paths:
            if _is_regular_non_symlink_relative_path(repo_path, relative_path):
                validated_paths.append(relative_path)
                if max_files is not None and len(validated_paths) >= max_files:
                    break
        return validated_paths

    if max_files is None:
        ordered_paths = _ranked_repository_relative_paths(
            relative_paths,
            repo_path=repo_path,
            max_files=None,
        )
        return _validated_from_ordered_paths(ordered_paths)
    if max_files <= 0:
        return []
    if len(relative_paths) <= _FULL_RANK_VALIDATION_SCAN_LIMIT:
        ordered_paths = _ranked_repository_relative_paths(
            relative_paths,
            repo_path=repo_path,
            max_files=None,
        )
        return _validated_from_ordered_paths(ordered_paths)
    validated_paths: list[str] = []
    appended_paths: set[str] = set()
    validation_cache: dict[str, bool] = {}
    candidate_limit = min(len(relative_paths), max_files + _RANK_VALIDATION_OVERSCAN)
    while candidate_limit > 0:
        ranked_paths = _ranked_repository_relative_paths(
            relative_paths,
            repo_path=repo_path,
            max_files=candidate_limit,
        )
        for relative_path in ranked_paths:
            if relative_path in appended_paths:
                continue
            is_regular = validation_cache.get(relative_path)
            if is_regular is None:
                is_regular = _is_regular_non_symlink_relative_path(repo_path, relative_path)
                validation_cache[relative_path] = is_regular
            if not is_regular:
                continue
            appended_paths.add(relative_path)
            validated_paths.append(relative_path)
            if len(validated_paths) >= max_files:
                return validated_paths
        if candidate_limit >= len(relative_paths) or len(ranked_paths) < candidate_limit:
            return validated_paths
        candidate_limit = min(
            len(relative_paths),
            candidate_limit + max(_RANK_VALIDATION_OVERSCAN, max_files - len(validated_paths)),
        )
    return validated_paths


def _validated_ranked_repository_relative_paths_by_focus(
    relative_paths: list[str],
    *,
    repo_path: Path,
    normalized_focus_paths: list[str],
    per_focus_limit: int,
) -> list[str]:
    ordered_focus_paths = tuple(
        sorted(
            normalized_focus_paths,
            key=lambda path: (-len(path), path),
        )
    )
    if per_focus_limit <= 0:
        return []
    validated_by_focus_path: dict[str, list[str]] = {
        focus_path: [] for focus_path in normalized_focus_paths
    }
    appended_by_focus_path: dict[str, set[str]] = {
        focus_path: set() for focus_path in normalized_focus_paths
    }
    validation_cache: dict[str, bool] = {}
    candidate_per_focus_limit = per_focus_limit + _RANK_VALIDATION_OVERSCAN
    while candidate_per_focus_limit > 0:
        ranked_paths = _ranked_repository_relative_paths_by_focus(
            relative_paths,
            repo_path=repo_path,
            normalized_focus_paths=normalized_focus_paths,
            per_focus_limit=candidate_per_focus_limit,
        )
        candidate_paths_by_focus_path: dict[str, list[str]] = {
            focus_path: [] for focus_path in normalized_focus_paths
        }
        for relative_path in ranked_paths:
            matched_focus_path = _matched_focus_path(
                relative_path,
                ordered_focus_paths=ordered_focus_paths,
            )
            if matched_focus_path is None:
                continue
            candidate_paths_by_focus_path[matched_focus_path].append(relative_path)
        for focus_path in normalized_focus_paths:
            if len(validated_by_focus_path[focus_path]) >= per_focus_limit:
                continue
            for relative_path in candidate_paths_by_focus_path[focus_path]:
                if relative_path in appended_by_focus_path[focus_path]:
                    continue
                is_regular = validation_cache.get(relative_path)
                if is_regular is None:
                    is_regular = _is_regular_non_symlink_relative_path(repo_path, relative_path)
                    validation_cache[relative_path] = is_regular
                if not is_regular:
                    continue
                appended_by_focus_path[focus_path].add(relative_path)
                validated_by_focus_path[focus_path].append(relative_path)
                if len(validated_by_focus_path[focus_path]) >= per_focus_limit:
                    break
        if all(
            len(validated_by_focus_path[focus_path]) >= per_focus_limit
            for focus_path in normalized_focus_paths
        ):
            break
        if all(
            len(candidate_paths_by_focus_path[focus_path]) < candidate_per_focus_limit
            for focus_path in normalized_focus_paths
            if len(validated_by_focus_path[focus_path]) < per_focus_limit
        ):
            break
        candidate_per_focus_limit += _RANK_VALIDATION_OVERSCAN
    ranked_paths: list[str] = []
    for focus_path in normalized_focus_paths:
        ranked_paths.extend(validated_by_focus_path[focus_path])
    return ranked_paths


def _probe_repository_file_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    include_patterns: list[str],
    exclude_dirnames: set[str],
    max_files: int | None,
    per_focus_limit: int | None = None,
) -> list[str]:
    probe_module = _probe_module()
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    repository_service = probe_module.repository_service
    _git_repo_relative_files_for_focus_paths = probe_module._git_repo_relative_files_for_focus_paths
    _git_repo_relative_files = probe_module._git_repo_relative_files
    normalized_include_patterns, include_patterns_match_all_files = _include_pattern_spec(
        include_patterns
    )
    has_repo_root_focus_path, normalized_focus_paths = collection_support._focus_path_match_spec(
        focus_paths
    )
    normalized_exclude_dirnames = tuple(sorted(str(dirname) for dirname in exclude_dirnames))
    cache_key = (
        _repo_cache_key(repo_path),
        () if has_repo_root_focus_path or not normalized_focus_paths else normalized_focus_paths,
        normalized_include_patterns,
        normalized_exclude_dirnames,
        max_files,
        per_focus_limit,
    )
    def _cache_and_return(ordered_paths: list[str]) -> list[str]:
        if len(_PROBE_REPOSITORY_FILE_PATHS_CACHE) >= _PROBE_REPOSITORY_FILE_PATHS_CACHE_LIMIT:
            oldest_key = next(iter(_PROBE_REPOSITORY_FILE_PATHS_CACHE))
            _PROBE_REPOSITORY_FILE_PATHS_CACHE.pop(oldest_key, None)
        _PROBE_REPOSITORY_FILE_PATHS_CACHE[cache_key] = list(ordered_paths)
        return list(ordered_paths)

    cached_paths = _PROBE_REPOSITORY_FILE_PATHS_CACHE.get(cache_key)
    if cached_paths is not None:
        return list(cached_paths)
    if max_files == 1 and per_focus_limit is None and normalized_focus_paths and not has_repo_root_focus_path:
        grouped_cache_paths: list[str] | None = None
        grouped_cache_limit: int | None = None
        for cached_key, cached_grouped_paths in _PROBE_REPOSITORY_FILE_PATHS_CACHE.items():
            (
                cached_repo_key,
                cached_focus_paths,
                cached_include_patterns,
                cached_exclude_dirnames,
                _cached_max_files,
                cached_per_focus_limit,
            ) = cached_key
            if (
                cached_repo_key != cache_key[0]
                or cached_focus_paths != cache_key[1]
                or cached_include_patterns != cache_key[2]
                or cached_exclude_dirnames != cache_key[3]
                or cached_per_focus_limit is None
                or not cached_grouped_paths
            ):
                continue
            if grouped_cache_limit is None or cached_per_focus_limit > grouped_cache_limit:
                grouped_cache_paths = list(cached_grouped_paths)
                grouped_cache_limit = cached_per_focus_limit
        if grouped_cache_paths:
            return _cache_and_return(
                _ranked_repository_relative_paths(
                    grouped_cache_paths,
                    repo_path=repo_path,
                    max_files=1,
                )
            )

    def _matches_normalized_focus_paths(relative_path: str) -> bool:
        if has_repo_root_focus_path or not normalized_focus_paths:
            return True
        for normalized_focus in normalized_focus_paths:
            if relative_path == normalized_focus or relative_path.startswith(f"{normalized_focus}/"):
                return True
        return False

    concrete_focus_files: list[str] = []
    if focus_paths:
        all_focus_paths_are_concrete_files = True
        for raw_focus_path in focus_paths:
            normalized_focus_path = repository_service._normalize_repository_relative_path(
                raw_focus_path
            )
            # A focus path only qualifies for the direct concrete-file fast path when it is a
            # regular (non-symlink) file AND survives the exclude/include-pattern filter. A
            # regular file that fails the filter (e.g. a directory focus like ``alpha`` against
            # ``**/*.ts``) must fall through to the git listing rather than empty the result.
            if not (
                normalized_focus_path
                and _is_regular_non_symlink_relative_path(repo_path, normalized_focus_path)
                and not any(
                    part in exclude_dirnames
                    for part in _path_segments(normalized_focus_path)[:-1]
                )
                and (
                    include_patterns_match_all_files
                    or not normalized_include_patterns
                    or any(
                        repository_service._matches_repository_pattern(
                            normalized_focus_path, pattern
                        )
                        for pattern in normalized_include_patterns
                    )
                )
            ):
                all_focus_paths_are_concrete_files = False
                break
            concrete_focus_files.append(normalized_focus_path)
        if all_focus_paths_are_concrete_files:
            return _cache_and_return(sorted(concrete_focus_files))

    using_focused_git_listing = bool(normalized_focus_paths) and not has_repo_root_focus_path
    git_relative_files = (
        _git_repo_relative_files_for_focus_paths(
            repo_path,
            focus_paths=focus_paths,
        )
        if using_focused_git_listing
        else _git_repo_relative_files(repo_path)
    )
    if git_relative_files is not None:
        collected: list[str] = []
        for relative in git_relative_files:
            relative_segments = _path_segments(relative)
            if any(part in exclude_dirnames for part in relative_segments[:-1]):
                continue
            if not using_focused_git_listing and not _matches_normalized_focus_paths(relative):
                continue
            if normalized_include_patterns and not include_patterns_match_all_files and not any(
                repository_service._matches_repository_pattern(relative, pattern)
                for pattern in normalized_include_patterns
            ):
                continue
            collected.append(relative)
        if per_focus_limit is not None and normalized_focus_paths and not has_repo_root_focus_path:
            ordered = _validated_ranked_repository_relative_paths_by_focus(
                collected,
                repo_path=repo_path,
                normalized_focus_paths=list(normalized_focus_paths),
                per_focus_limit=per_focus_limit,
            )
        elif max_files is not None:
            ordered = _validated_ranked_repository_relative_paths(
                collected,
                repo_path=repo_path,
                max_files=max_files,
            )
        else:
            ordered = [
                relative_path
                for relative_path in _ranked_repository_relative_paths(
                    collected,
                    repo_path=repo_path,
                    max_files=None,
                )
                if _is_regular_non_symlink_relative_path(repo_path, relative_path)
            ]
        return _cache_and_return(ordered)

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
            if normalized_include_patterns and not include_patterns_match_all_files and not any(
                repository_service._matches_repository_pattern(relative, pattern)
                for pattern in normalized_include_patterns
            ):
                continue
            collected_paths.append(relative)
    if per_focus_limit is not None and normalized_focus_paths and not has_repo_root_focus_path:
        ordered = _ranked_repository_relative_paths_by_focus(
            collected_paths,
            repo_path=repo_path,
            normalized_focus_paths=list(normalized_focus_paths),
            per_focus_limit=per_focus_limit,
        )
    else:
        ordered = _ranked_repository_relative_paths(
            collected_paths,
            repo_path=repo_path,
            max_files=max_files,
        )
    return _cache_and_return(ordered)


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
    normalized_include_patterns, _include_patterns_match_all_files = _include_pattern_spec(
        include_patterns
    )

    def _normalized_focus_path_spec(
        paths: list[str],
    ) -> tuple[tuple[str, ...], bool]:
        normalized_paths = tuple(
            sorted(
                {
                    normalized_path
                    for raw_path in paths
                    if str(raw_path).strip()
                    and (
                        normalized_path := repository_service._normalize_repository_relative_path(
                            raw_path
                        )
                    )
                }
            )
        )
        has_repo_root_path = any(
            str(raw_path).strip().strip("./") == ""
            for raw_path in paths
        )
        return normalized_paths, has_repo_root_path

    cache_seed_paths, has_repo_root_seed_path = _normalized_focus_path_spec(seed_paths)
    cache_bridge_paths, has_repo_root_bridge_path = _normalized_focus_path_spec(bridge_paths)
    cache_key = (
        _repo_cache_key(repo_path),
        cache_seed_paths,
        has_repo_root_seed_path,
        cache_bridge_paths,
        has_repo_root_bridge_path,
        normalized_include_patterns,
        max_files,
    )
    cached_paths = _CANDIDATE_REPOSITORY_FILE_PATHS_CACHE.get(cache_key)
    if cached_paths is not None:
        return list(cached_paths)

    collected: list[str] = []
    seen: set[str] = set()
    prefetched_candidate_paths_by_focus_key: dict[tuple[str, ...], list[str]] = {}

    def _is_repo_root_focus_path(raw_path: str) -> bool:
        normalized_path = repository_service._normalize_repository_relative_path(raw_path)
        if normalized_path:
            return False
        return str(raw_path).strip().strip("./") == ""

    def _bridge_root_top_level_group_count(bridge_paths: list[str]) -> int:
        top_level_groups: set[str] = set()
        for bridge_path in bridge_paths:
            normalized_path = repository_service._normalize_repository_relative_path(bridge_path)
            if not normalized_path:
                continue
            top_level_group = _top_level_path_group(normalized_path)
            if top_level_group is not None:
                top_level_groups.add(top_level_group)
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

    def _collect_per_focus_path(
        focus_paths: list[str],
        *,
        per_focus_limit: int,
        total_limit: int,
        prefetch_remaining_files: int = 0,
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
        remaining_total = total_limit - len(collected)
        if remaining_total <= 0:
            return
        candidate_limit = min(remaining_total, max(per_focus_limit, 1))
        grouped_focus_limit = None
        ordered_focus_paths = tuple(
            sorted(
                normalized_focus_paths,
                key=lambda path: (-len(path), path),
            )
        )
        if len(normalized_focus_paths) > 1:
            seen_focus_counts: Counter[str] = Counter()
            for relative_path in seen:
                matched_focus_path = _matched_focus_path(
                    relative_path,
                    ordered_focus_paths=ordered_focus_paths,
                )
                if matched_focus_path is not None:
                    seen_focus_counts[matched_focus_path] += 1
            grouped_focus_limit = per_focus_limit + max(seen_focus_counts.values(), default=0)
            if (
                prefetch_remaining_files > 0
                and len(normalized_focus_paths) <= 8
            ):
                grouped_focus_limit += (
                    prefetch_remaining_files + len(normalized_focus_paths) - 1
                ) // len(normalized_focus_paths)
            candidate_limit = grouped_focus_limit * len(normalized_focus_paths)
        candidate_file_paths = _probe_repository_file_paths(
            repo_path=repo_path,
            focus_paths=normalized_focus_paths,
            include_patterns=include_patterns,
            exclude_dirnames=set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS),
            max_files=candidate_limit,
            per_focus_limit=grouped_focus_limit,
        )
        if (
            grouped_focus_limit is not None
            and grouped_focus_limit > per_focus_limit
        ):
            prefetched_candidate_paths_by_focus_key[tuple(normalized_focus_paths)] = list(
                candidate_file_paths
            )
        candidate_paths_by_focus_path: dict[str, list[str]] = {
            focus_path: [] for focus_path in normalized_focus_paths
        }
        for relative_path in candidate_file_paths:
            matched_focus_path = _matched_focus_path(
                relative_path,
                ordered_focus_paths=ordered_focus_paths,
            )
            if matched_focus_path is None:
                continue
            candidate_paths_by_focus_path[matched_focus_path].append(relative_path)
        per_focus_counts: Counter[str] = Counter()
        for focus_path in normalized_focus_paths:
            for relative_path in candidate_paths_by_focus_path.get(focus_path, []):
                if relative_path in seen:
                    continue
                seen.add(relative_path)
                collected.append(relative_path)
                per_focus_counts[focus_path] += 1
                if len(collected) >= total_limit:
                    return
                if per_focus_counts[focus_path] >= per_focus_limit:
                    break

    def _collect(focus_paths: list[str], remaining_files: int) -> None:
        if remaining_files <= 0:
            return
        normalized_focus_paths = tuple(
            dict.fromkeys(
                repository_service._normalize_repository_relative_path(path)
                for path in focus_paths
                if str(path).strip()
            )
        )
        normalized_focus_paths = tuple(path for path in normalized_focus_paths if path)
        prefetched_candidate_paths = prefetched_candidate_paths_by_focus_key.get(
            normalized_focus_paths
        )
        if prefetched_candidate_paths is not None:
            for relative_path in _ranked_repository_relative_paths(
                list(prefetched_candidate_paths),
                repo_path=repo_path,
                max_files=None,
            ):
                if relative_path in seen:
                    continue
                seen.add(relative_path)
                collected.append(relative_path)
                if len(collected) >= max_files:
                    return
                remaining_files -= 1
                if remaining_files <= 0:
                    return
        candidate_file_paths = _probe_repository_file_paths(
            repo_path=repo_path,
            focus_paths=focus_paths,
            include_patterns=include_patterns,
            exclude_dirnames=set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS),
            max_files=remaining_files,
        )
        for relative_path in candidate_file_paths:
            if relative_path in seen:
                continue
            seen.add(relative_path)
            collected.append(relative_path)
            if len(collected) >= max_files:
                return

    def _should_run_root_fallback() -> bool:
        if concrete_seed_only:
            return False
        if has_repo_root_bridge_path or has_repo_root_seed_path:
            return True
        explicit_focus_count = len(normalized_seed_paths) + len(normalized_bridge_paths)
        if explicit_focus_count <= 0:
            return True
        focused_collection_floor = max(8, min(16, explicit_focus_count * 2))
        return len(collected) < min(focused_collection_floor, max_files)

    normalized_seed_paths = list(cache_seed_paths)
    normalized_bridge_paths = list(cache_bridge_paths)
    concrete_seed_paths = [
        path for path in normalized_seed_paths if path and _looks_like_concrete_file_seed(path)
    ]
    concrete_seed_only = (
        bool(normalized_seed_paths)
        and len(concrete_seed_paths) == len([path for path in normalized_seed_paths if path])
        and not normalized_bridge_paths
        and not has_repo_root_seed_path
        and not has_repo_root_bridge_path
    )
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
        bridge_paths_require_distributed_followup = (
            bridge_path_count >= 24
            and _bridge_root_top_level_group_count(normalized_bridge_paths) >= 8
        )
        if bridge_path_count > 1:
            bridge_spread_limit = _bridge_root_spread_limit(
                remaining_files=remaining_files,
                bridge_path_count=bridge_path_count,
            )
            reserved_bridge_budget = min(
                remaining_files,
                bridge_spread_limit * bridge_path_count,
            )
            bridge_remaining_after_spread = max(0, remaining_files - reserved_bridge_budget)
            predicted_bridge_budget = min(
                bridge_remaining_after_spread,
                max(min(96, max_files), min(256, max(max_files // 4, 1))),
            )
            _collect_per_focus_path(
                normalized_bridge_paths,
                per_focus_limit=bridge_spread_limit,
                total_limit=len(collected) + reserved_bridge_budget,
                prefetch_remaining_files=(
                    0 if bridge_paths_require_distributed_followup else predicted_bridge_budget
                ),
            )
            remaining_files = max_files - len(collected)
        bridge_budget = min(
            remaining_files,
            max(min(96, max_files), min(256, max(max_files // 4, 1))),
        )
        if (
            bridge_budget > 0
            and bridge_paths_require_distributed_followup
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
    if remaining_files > 0 and (has_repo_root_bridge_path or has_repo_root_seed_path):
        root_budget = min(
            remaining_files,
            max(min(96, max_files), min(256, max(max_files // 4, 1))),
        )
        _collect([], root_budget)
        remaining_files = max_files - len(collected)
    if remaining_files > 0 and len(collected) < min(32, max_files) and _should_run_root_fallback():
        fallback_budget = min(
            remaining_files,
            max(min(64, max_files), min(128, max(max_files // 8, 1))),
        )
        _collect([], fallback_budget)
    if len(_CANDIDATE_REPOSITORY_FILE_PATHS_CACHE) >= _CANDIDATE_REPOSITORY_FILE_PATHS_CACHE_LIMIT:
        oldest_key = next(iter(_CANDIDATE_REPOSITORY_FILE_PATHS_CACHE))
        _CANDIDATE_REPOSITORY_FILE_PATHS_CACHE.pop(oldest_key, None)
    _CANDIDATE_REPOSITORY_FILE_PATHS_CACHE[cache_key] = list(collected)
    return list(collected)


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
        path_segments = _path_segments(path)
        if not path_segments:
            return False
        basename = path_segments[-1].lower()
        if basename == "src" or basename.startswith("src-"):
            return True
        return (
            len(path_segments) >= 3
            and path_segments[-2].lower() == "main"
            and path_segments[-3].lower() == "src"
        )

    top_level_group_count = len(
        {
            top_level_group
            for path in normalized_focus_paths
            if (top_level_group := _top_level_path_group(path)) is not None
        }
    )
    if focus_path_count >= 24:
        return True
    if focus_path_count >= 20 and top_level_group_count <= 2:
        return True
    if focus_path_count >= 8 and top_level_group_count == 1:
        return True
    if focus_path_count >= 4 and top_level_group_count <= 2 and any(
        not repository_service._is_test_path(path) and not _is_non_operational_profile_path(path)
        for path in normalized_focus_paths
    ):
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
            top_level_group
            for path in normalized_bridge_paths
            if (top_level_group := _top_level_path_group(path)) is not None
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

    normalized_include_patterns, include_patterns_match_all_files = _include_pattern_spec(
        include_patterns
    )
    normalized_paths: list[str] = []
    seen: set[str] = set()
    excluded_parts = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
    for raw_path in candidate_file_paths:
        normalized_path = repository_service._normalize_repository_relative_path(raw_path)
        if not normalized_path or normalized_path in seen:
            continue
        normalized_segments = _path_segments(normalized_path)
        if any(part in excluded_parts for part in normalized_segments[:-1]):
            continue
        candidate = repo_path / normalized_path
        if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
            continue
        if (
            normalized_include_patterns
            and not include_patterns_match_all_files
            and not any(
                repository_service._matches_repository_pattern(normalized_path, pattern)
                for pattern in normalized_include_patterns
            )
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
