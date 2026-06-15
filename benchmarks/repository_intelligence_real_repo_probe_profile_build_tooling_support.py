from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


@dataclass(frozen=True)
class _CachedEiffelSourceProfile:
    aliases: tuple[str, ...]
    dependency_targets: tuple[str, ...]


_EIFFEL_SOURCE_PROFILE_CACHE_LIMIT = 16384
_EIFFEL_SOURCE_PROFILE_CACHE: dict[
    tuple[str, str],
    _CachedEiffelSourceProfile | None,
] = {}
_EIFFEL_FAST_FALLBACK_MIN_CANDIDATES = 32
_EIFFEL_FAST_FALLBACK_ENTRYPOINT_LIMIT = 8
_EIFFEL_SOURCE_LIKE_ROOT_PARTS = frozenset({"src", "source"})
_EIFFEL_PREFERRED_ENTRYPOINT_BASENAMES = frozenset({"application.e", "main.e"})
_EIFFEL_SUPPORT_ROOT_LIMIT = 16
_EIFFEL_CONFIG_ROOT_PARTS = frozenset({"config", "configs", "ecf", "ace"})
_EIFFEL_PROFILE_HINTS_CACHE_LIMIT = 4096
_EIFFEL_PROFILE_HINTS_CACHE: dict[
    tuple[str, str],
    tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
] = {}
_EIFFEL_REPO_SOURCE_PATH_CACHE_LIMIT = 256
_EIFFEL_REPO_SOURCE_PATH_CACHE: dict[str, tuple[str, ...] | None] = {}
_EIFFEL_CANDIDATE_PATHS_CACHE_LIMIT = 1024
_EIFFEL_CANDIDATE_PATHS_CACHE: dict[
    tuple[str, tuple[str, ...]],
    tuple[str, ...],
] = {}


def _repo_cache_key(repo_path: Path) -> str:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    return collection_support._repo_cache_key(repo_path)


def clear_eiffel_source_profile_cache() -> None:
    _EIFFEL_SOURCE_PROFILE_CACHE.clear()
    _EIFFEL_PROFILE_HINTS_CACHE.clear()
    _EIFFEL_REPO_SOURCE_PATH_CACHE.clear()
    _EIFFEL_CANDIDATE_PATHS_CACHE.clear()
    _cached_eiffel_source_like_root_parts.cache_clear()


@lru_cache(maxsize=16384)
def _cached_eiffel_source_like_root_parts(path_parts: tuple[str, ...]) -> str | None:
    lowered_parts = [part.lower() for part in path_parts[:-1]]
    for index in range(len(lowered_parts) - 1, -1, -1):
        if lowered_parts[index] not in _EIFFEL_SOURCE_LIKE_ROOT_PARTS:
            continue
        return str(PurePosixPath(*path_parts[: index + 1]))
    return None


def _eiffel_source_like_root(path: PurePosixPath) -> str | None:
    return _cached_eiffel_source_like_root_parts(tuple(path.parts))


def _eiffel_support_root_for_file(path: str) -> str | None:
    pure_path = PurePosixPath(path)
    source_like_root = _eiffel_source_like_root(pure_path)
    if source_like_root:
        return source_like_root
    parent_dir = str(pure_path.parent)
    return parent_dir if parent_dir not in {"", "."} else None


def _rank_eiffel_support_root(root: str) -> tuple[int, int, str]:
    pure_root = PurePosixPath(root)
    has_source_like_root = _eiffel_source_like_root(PurePosixPath(*pure_root.parts, "__probe__.e"))
    return (
        0 if has_source_like_root else 1,
        len(pure_root.parts),
        root,
    )


def _normalize_eiffel_support_root(root: str) -> str | None:
    normalized_root = str(root or "").replace("\\", "/").strip().strip("/")
    if not normalized_root or normalized_root == ".":
        return None
    pure_root = PurePosixPath(normalized_root)
    source_like_root = _eiffel_source_like_root(PurePosixPath(*pure_root.parts, "__probe__.e"))
    if source_like_root:
        return source_like_root
    trimmed_parts = list(pure_root.parts)
    while trimmed_parts and trimmed_parts[-1].lower() in _EIFFEL_CONFIG_ROOT_PARTS:
        trimmed_parts.pop()
    if trimmed_parts:
        return str(PurePosixPath(*trimmed_parts))
    return normalized_root


def _finalize_eiffel_support_roots(roots: set[str]) -> set[str]:
    normalized_roots = {
        normalized_root
        for root in roots
        if (normalized_root := _normalize_eiffel_support_root(root))
    }
    return {
        root
        for root in sorted(
            normalized_roots,
            key=_rank_eiffel_support_root,
        )[:_EIFFEL_SUPPORT_ROOT_LIMIT]
        if root
    }


def _eiffel_fast_fallback_entrypoints(
    filtered_candidates: list[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    entrypoints: list[str] = []
    support_roots: list[str] = []
    seen_entrypoints: set[str] = set()
    seen_support_roots: set[str] = set()
    prioritized_candidates: list[tuple[str, str | None]] = [
        (candidate, _eiffel_source_like_root(PurePosixPath(candidate)))
        for candidate in filtered_candidates
    ]

    def _remember(candidate: str, source_root: str | None) -> None:
        if candidate in seen_entrypoints:
            return
        seen_entrypoints.add(candidate)
        entrypoints.append(candidate)
        support_root = source_root or str(PurePosixPath(candidate).parent)
        if support_root and support_root not in seen_support_roots:
            seen_support_roots.add(support_root)
            support_roots.append(support_root)

    for candidate, source_root in prioritized_candidates:
        if PurePosixPath(candidate).name.lower() not in _EIFFEL_PREFERRED_ENTRYPOINT_BASENAMES:
            continue
        _remember(candidate, source_root)
        if len(entrypoints) >= _EIFFEL_FAST_FALLBACK_ENTRYPOINT_LIMIT:
            return tuple(entrypoints), tuple(support_roots)

    for candidate, source_root in prioritized_candidates:
        if source_root is None or source_root in seen_support_roots:
            continue
        _remember(candidate, source_root)
        if len(entrypoints) >= _EIFFEL_FAST_FALLBACK_ENTRYPOINT_LIMIT:
            return tuple(entrypoints), tuple(support_roots)

    for candidate, source_root in prioritized_candidates:
        if source_root is None:
            continue
        _remember(candidate, source_root)
        if len(entrypoints) >= _EIFFEL_FAST_FALLBACK_ENTRYPOINT_LIMIT:
            return tuple(entrypoints), tuple(support_roots)

    return tuple(entrypoints), tuple(support_roots)


def _cached_eiffel_source_profile(
    repo_path: Path,
    normalized_candidate: str,
) -> _CachedEiffelSourceProfile | None:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    cache_key = (_repo_cache_key(repo_path), normalized_candidate)
    if cache_key in _EIFFEL_SOURCE_PROFILE_CACHE:
        return _EIFFEL_SOURCE_PROFILE_CACHE[cache_key]

    def _remember(result: _CachedEiffelSourceProfile | None) -> _CachedEiffelSourceProfile | None:
        if len(_EIFFEL_SOURCE_PROFILE_CACHE) >= _EIFFEL_SOURCE_PROFILE_CACHE_LIMIT:
            oldest_key = next(iter(_EIFFEL_SOURCE_PROFILE_CACHE))
            _EIFFEL_SOURCE_PROFILE_CACHE.pop(oldest_key, None)
        _EIFFEL_SOURCE_PROFILE_CACHE[cache_key] = result
        return result

    candidate_file = repo_path / normalized_candidate
    if (
        not candidate_file.is_file()
        or candidate_file.is_symlink()
        or candidate_file.suffix.lower() != ".e"
    ):
        return _remember(None)
    try:
        text = candidate_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _remember(None)
    stripped_text = repository_service.eiffel_adapter.strip_comments(text)
    if not repository_service.eiffel_adapter.is_probable_eiffel_source(
        path=Path(normalized_candidate),
        text=text,
        stripped_text=stripped_text,
    ):
        return _remember(None)
    pure_path = PurePosixPath(normalized_candidate)
    class_name = repository_service.eiffel_adapter.class_name_from_text(
        text,
        file_path=normalized_candidate,
        stripped_text=stripped_text,
    )
    aliases = {
        normalized_candidate,
        str(pure_path.with_suffix("")),
        pure_path.stem,
        class_name,
    }
    dependency_targets = repository_service.eiffel_adapter.parse_dependency_targets(
        text,
        file_path=normalized_candidate,
        stripped_text=stripped_text,
        current_class=class_name,
    )
    return _remember(
        _CachedEiffelSourceProfile(
            aliases=tuple(sorted(alias for alias in aliases if alias)),
            dependency_targets=tuple(dependency_targets),
        )
    )


def _cached_eiffel_candidate_paths(
    repo_path: Path,
    *,
    normalized_search_roots: tuple[str, ...],
) -> tuple[str, ...]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    cache_key = (_repo_cache_key(repo_path), normalized_search_roots)
    cached_paths = _EIFFEL_CANDIDATE_PATHS_CACHE.get(cache_key)
    if cached_paths is not None:
        return cached_paths

    def _remember(paths: tuple[str, ...]) -> tuple[str, ...]:
        if len(_EIFFEL_CANDIDATE_PATHS_CACHE) >= _EIFFEL_CANDIDATE_PATHS_CACHE_LIMIT:
            oldest_key = next(iter(_EIFFEL_CANDIDATE_PATHS_CACHE))
            _EIFFEL_CANDIDATE_PATHS_CACHE.pop(oldest_key, None)
        _EIFFEL_CANDIDATE_PATHS_CACHE[cache_key] = paths
        return paths

    def _within_search_roots(relative_path: str) -> bool:
        return any(
            not search_root
            or relative_path == search_root
            or relative_path.startswith(f"{search_root}/")
            for search_root in normalized_search_roots
        )

    candidate_file_paths: list[str] = []
    seen_candidates: set[str] = set()
    repo_cache_key = _repo_cache_key(repo_path)
    cached_repo_source_paths = _EIFFEL_REPO_SOURCE_PATH_CACHE.get(repo_cache_key)
    if cached_repo_source_paths is None and repo_cache_key not in _EIFFEL_REPO_SOURCE_PATH_CACHE:
        git_relative_files = collection_support._git_repo_relative_files(repo_path)
        if git_relative_files is None:
            cached_repo_source_paths = None
        else:
            cached_repo_source_paths = tuple(
                relative_path
                for relative_path in git_relative_files
                if relative_path.lower().endswith(".e")
            )
        if len(_EIFFEL_REPO_SOURCE_PATH_CACHE) >= _EIFFEL_REPO_SOURCE_PATH_CACHE_LIMIT:
            oldest_key = next(iter(_EIFFEL_REPO_SOURCE_PATH_CACHE))
            _EIFFEL_REPO_SOURCE_PATH_CACHE.pop(oldest_key, None)
        _EIFFEL_REPO_SOURCE_PATH_CACHE[repo_cache_key] = cached_repo_source_paths
    else:
        cached_repo_source_paths = _EIFFEL_REPO_SOURCE_PATH_CACHE.get(repo_cache_key)

    if cached_repo_source_paths is not None:
        for relative_path in cached_repo_source_paths:
            if not _within_search_roots(relative_path):
                continue
            candidate_file = repo_path / relative_path
            if not candidate_file.is_file() or candidate_file.is_symlink():
                continue
            if relative_path in seen_candidates:
                continue
            seen_candidates.add(relative_path)
            candidate_file_paths.append(relative_path)
        return _remember(tuple(candidate_file_paths))

    for search_root in normalized_search_roots:
        search_path = repo_path / search_root if search_root else repo_path
        if not search_path.is_dir():
            continue
        for candidate_file in sorted(search_path.rglob("*.e")):
            if not candidate_file.is_file() or candidate_file.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_file.relative_to(repo_path))
            )
            if not relative_path or relative_path in seen_candidates:
                continue
            seen_candidates.add(relative_path)
            candidate_file_paths.append(relative_path)
    return _remember(tuple(candidate_file_paths))


def _bitbake_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path

    bitbake_files: list[str] = []
    bitbake_file_text: dict[str, str] = {}
    config_paths: set[str] = set()
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_like_parts = {"classes", "classes-recipe", "conf", "include", "files"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        pure_path = PurePosixPath(normalized_candidate)
        basename = pure_path.name.lower()
        suffix = pure_path.suffix.lower()
        if basename in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES:
            config_paths.add(normalized_candidate)
        if not repository_service.bitbake_adapter.has_bitbake_path_hints(pure_path):
            continue
        language = (
            "bitbake"
            if suffix in {".bb", ".bbappend", ".bbclass"}
            or basename in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES
            else _probe_language_for_path(normalized_candidate, repo_path=repo_path)
        )
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or language != "bitbake"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.bitbake_adapter.is_probable_bitbake_source(
            path=candidate_file,
            text=text,
        ):
            continue
        bitbake_files.append(normalized_candidate)
        bitbake_file_text[normalized_candidate] = text
        for alias in repository_service.bitbake_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in bitbake_files:
        text = bitbake_file_text.get(normalized_candidate)
        if text is None:
            continue
        for dependency in repository_service.bitbake_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in bitbake_files:
        pure_path = PurePosixPath(normalized_candidate)
        lowered_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.suffix.lower() != ".bb":
            parent_dir = repository_service._normalize_repository_relative_path(
                str(pure_path.parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            continue
        if normalized_candidate not in imported_files and not lowered_parts.intersection(
            support_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            path for path in bitbake_files if PurePosixPath(path).suffix.lower() == ".bb"
        )
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _bitbake_profile_candidate_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    config_paths: list[str],
    max_files: int,
) -> list[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _git_repo_relative_files = probe_module._git_repo_relative_files

    excluded_parts = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
    normalized_focus_paths = [
        normalized_path
        for path in focus_paths
        if (
            normalized_path := repository_service._normalize_repository_relative_path(path)
        )
    ]
    layer_roots: list[str] = []
    seen_layer_roots: set[str] = set()
    for config_path in config_paths:
        normalized_config = repository_service._normalize_repository_relative_path(config_path)
        if not normalized_config:
            continue
        config_pure = PurePosixPath(normalized_config)
        if (
            config_pure.name.lower()
            not in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES
        ):
            continue
        if config_pure.parent.name.lower() == "conf":
            raw_layer_root = str(config_pure.parent.parent)
        else:
            raw_layer_root = str(config_pure.parent)
        normalized_layer_root = repository_service._normalize_repository_relative_path(
            raw_layer_root
        )
        if normalized_layer_root is None:
            normalized_layer_root = ""
        if normalized_layer_root in seen_layer_roots:
            continue
        seen_layer_roots.add(normalized_layer_root)
        layer_roots.append(normalized_layer_root)
    if not layer_roots:
        return []

    def _is_within_layer_root(relative_path: str) -> bool:
        return any(
            not layer_root
            or relative_path == layer_root
            or relative_path.startswith(f"{layer_root}/")
            for layer_root in layer_roots
        )

    def _matches_requested_focus(relative_path: str) -> bool:
        if not normalized_focus_paths:
            return True
        return any(
            relative_path == focus_root or relative_path.startswith(f"{focus_root}/")
            for focus_root in normalized_focus_paths
        )

    def _bitbake_candidate_rank(relative_path: str) -> tuple[int, int, int, int, str]:
        normalized_path = (
            repository_service._normalize_repository_relative_path(relative_path) or ""
        )
        pure_path = PurePosixPath(normalized_path)
        basename = pure_path.name.lower()
        suffix = pure_path.suffix.lower()
        support_like_parts = {"classes", "classes-recipe", "conf", "files", "include"}
        suffix_rank = {
            ".bb": 0,
            ".bbclass": 1,
            ".inc": 2,
            ".bbappend": 3,
        }.get(suffix, 4)
        support_rank = int(
            bool({part.lower() for part in pure_path.parts[:-1]}.intersection(support_like_parts))
        )
        return (
            0 if basename in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES else 1,
            suffix_rank,
            support_rank if suffix == ".bb" else 0,
            1 if repository_service._is_test_path(normalized_path) else 0,
            normalized_path,
        )

    candidate_paths: list[str] = []
    git_relative_files = _git_repo_relative_files(repo_path)
    if git_relative_files is not None:
        for relative_path in git_relative_files:
            if any(part in excluded_parts for part in PurePosixPath(relative_path).parts[:-1]):
                continue
            if (
                not _is_within_layer_root(relative_path)
                or not _matches_requested_focus(relative_path)
            ):
                continue
            pure_path = PurePosixPath(relative_path)
            if not repository_service.bitbake_adapter.has_bitbake_path_hints(pure_path):
                continue
            candidate = repo_path / relative_path
            if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
                continue
            candidate_paths.append(relative_path)
    else:
        seen_paths: set[str] = set()
        for layer_root in layer_roots:
            root = repo_path / layer_root if layer_root else repo_path
            if not root.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if name not in excluded_parts]
                for filename in filenames:
                    candidate = Path(dirpath) / filename
                    if not candidate.is_file() or candidate.is_symlink():
                        continue
                    relative_path = str(candidate.relative_to(repo_path)).replace("\\", "/")
                    if relative_path in seen_paths or not _matches_requested_focus(relative_path):
                        continue
                    seen_paths.add(relative_path)
                    if repository_service.bitbake_adapter.has_bitbake_path_hints(
                        PurePosixPath(relative_path)
                    ):
                        candidate_paths.append(relative_path)
    ordered_candidate_paths = sorted(candidate_paths, key=_bitbake_candidate_rank)
    return ordered_candidate_paths[: min(max_files, 512)]


def _hcl_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path

    hcl_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.tf", "main.hcl", "terragrunt.hcl", "versions.tf"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "hcl"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.hcl_adapter.is_probable_hcl_source(
            path=candidate_file,
            text=text,
        ):
            continue
        hcl_files.append(normalized_candidate)
        for alias in repository_service.hcl_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in hcl_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for block in repository_service.hcl_adapter.iter_block_entries(text):
            source_statements = repository_service.hcl_adapter.iter_module_source_statements(block)
            for source_target, _line in source_statements:
                target_file = repository_service.hcl_adapter.resolve_module_source(
                    source_target,
                    normalized_candidate,
                    module_index,
                    normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                    resolve_suffix_match=repository_service._resolve_suffix_match,
                )
                if not target_file or target_file == normalized_candidate:
                    continue
                imported_files.add(target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in hcl_files:
        pure_path = PurePosixPath(normalized_candidate)
        if pure_path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(hcl_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _bicep_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path

    bicep_files: list[str] = []
    config_paths: set[str] = set()
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    text_by_path: dict[str, str] = {}
    stripped_text_by_path: dict[str, str] = {}
    preferred_basenames = {"main.bicep"}

    def _is_bicep_test_path(path: str) -> bool:
        lowered = path.lower()
        return (
            lowered.endswith(".test.bicep")
            or "/test/" in lowered
            or "/tests/" in lowered
            or "/e2e/" in lowered
        )

    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        if PurePosixPath(normalized_candidate).name.lower() == "bicepconfig.json":
            config_paths.add(normalized_candidate)
        if (
            _is_bicep_test_path(normalized_candidate)
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "bicep"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.bicep_adapter.strip_comments(text)
        if not repository_service.bicep_adapter.is_probable_bicep_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        bicep_files.append(normalized_candidate)
        text_by_path[normalized_candidate] = text
        stripped_text_by_path[normalized_candidate] = stripped_text
        for alias in repository_service.bicep_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
            stripped_text=stripped_text,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in bicep_files:
        text = text_by_path.get(normalized_candidate)
        stripped_text = stripped_text_by_path.get(normalized_candidate)
        if text is None or stripped_text is None:
            continue
        module_statements = repository_service.bicep_adapter.parse_module_statements(
            text,
            stripped_text=stripped_text,
        )
        for _module_name, source_target, _line in module_statements:
            target_file = repository_service.bicep_adapter.resolve_module_source(
                source_target,
                normalized_candidate,
                module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in bicep_files:
        pure_path = PurePosixPath(normalized_candidate)
        if pure_path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(bicep_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _tlaplus_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path

    tla_files: list[str] = []
    loaded_text_by_path: dict[str, str] = {}
    stripped_text_by_path: dict[str, str] = {}
    config_paths: set[str] = set()
    cfg_stems: set[str] = set()
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        if PurePosixPath(normalized_candidate).suffix.lower() == ".cfg":
            config_paths.add(normalized_candidate)
            cfg_stems.add(PurePosixPath(normalized_candidate).stem)
            continue
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "tlaplus"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.tlaplus_adapter.strip_comments(text)
        if not repository_service.tlaplus_adapter.is_probable_tlaplus_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        loaded_text_by_path[normalized_candidate] = text
        stripped_text_by_path[normalized_candidate] = stripped_text
        tla_files.append(normalized_candidate)
        for alias in repository_service.tlaplus_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
            stripped_text=stripped_text,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in tla_files:
        text = loaded_text_by_path.get(normalized_candidate)
        stripped_text = stripped_text_by_path.get(normalized_candidate)
        if text is None:
            continue
        for module_name, _line in repository_service.tlaplus_adapter.parse_extended_modules(
            text,
            stripped_text=stripped_text,
        ):
            target_file = repository_service.tlaplus_adapter.resolve_module_source(
                module_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
        for _alias, module_name, _line in repository_service.tlaplus_adapter.parse_instance_statements(
            text,
            stripped_text=stripped_text,
        ):
            target_file = repository_service.tlaplus_adapter.resolve_module_source(
                module_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in tla_files:
        stem = PurePosixPath(normalized_candidate).stem
        if stem.startswith(("MC", "AP")) or stem in cfg_stems or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(tla_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _chapel_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _chapel_profile_hints_from_candidates = probe_module._chapel_profile_hints_from_candidates
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _safe_load_toml_dict = probe_module._safe_load_toml_dict

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    payload = _safe_load_toml_dict(repo_path / normalized_path) or {}
    brick = payload.get("brick") if isinstance(payload.get("brick"), dict) else {}
    package_name = str(brick.get("name") or "").strip()
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    for candidate_root in (project_dir / "src", project_dir / "examples", project_dir / "example"):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if (
            normalized_root
            and not _is_non_operational_profile_path(normalized_root)
            and (repo_path / normalized_root).exists()
        ):
            support_roots.add(normalized_root)
    candidate_file_paths: list[str] = []
    search_root = repo_path / project_dir
    if search_root.exists():
        for candidate_file in sorted(search_root.rglob("*.chpl")):
            if not candidate_file.is_file() or candidate_file.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_file.relative_to(repo_path))
            )
            if relative_path:
                candidate_file_paths.append(relative_path)
    entrypoints, inferred_roots, _ = _chapel_profile_hints_from_candidates(
        repo_path,
        candidate_file_paths,
    )
    support_roots.update(inferred_roots)
    named_candidates = [
        str(project_dir / "src" / f"{package_name}.chpl") if package_name else "",
        str(project_dir / f"{package_name}.chpl") if package_name else "",
        str(project_dir / "src" / "main.chpl"),
        str(project_dir / "main.chpl"),
    ]
    for candidate in named_candidates:
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate)
        if (
            normalized_candidate
            and _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            )
            and (repo_path / normalized_candidate).exists()
        ):
            entrypoints.add(normalized_candidate)
    return entrypoints, {root for root in support_roots if root}, config_paths


def _resolve_eiffel_config_target(
    *,
    manifest_path: str,
    raw_target: str,
    variables: dict[str, str],
) -> str | None:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    candidate_value = str(raw_target or "").strip()
    if not candidate_value or "://" in candidate_value:
        return None
    for _ in range(4):
        updated_value = re.sub(
            r"\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)\}",
            lambda match: variables.get(str(match.group("name") or "").strip(), match.group(0)),
            candidate_value,
        )
        if updated_value == candidate_value:
            break
        candidate_value = updated_value
    return repository_service._normalize_repository_relative_path(
        str(PurePosixPath(manifest_path).parent / candidate_value)
    )


def _eiffel_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _eiffel_profile_hints_from_candidates = probe_module._eiffel_profile_hints_from_candidates
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    cache_key = (_repo_cache_key(repo_path), normalized_path)
    cached_result = _EIFFEL_PROFILE_HINTS_CACHE.get(cache_key)
    if cached_result is not None:
        cached_entrypoints, cached_support_roots, cached_config_paths = cached_result
        return set(cached_entrypoints), set(cached_support_roots), set(cached_config_paths)

    def _remember(
        entrypoints: set[str],
        support_roots: set[str],
        config_paths: set[str],
    ) -> tuple[set[str], set[str], set[str]]:
        if len(_EIFFEL_PROFILE_HINTS_CACHE) >= _EIFFEL_PROFILE_HINTS_CACHE_LIMIT:
            oldest_key = next(iter(_EIFFEL_PROFILE_HINTS_CACHE))
            _EIFFEL_PROFILE_HINTS_CACHE.pop(oldest_key, None)
        _EIFFEL_PROFILE_HINTS_CACHE[cache_key] = (
            tuple(sorted(entrypoints)),
            tuple(sorted(support_roots)),
            tuple(sorted(config_paths)),
        )
        return entrypoints, support_roots, config_paths

    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _remember(set(), set(), config_paths)
    stripped_text = repository_service.eiffel_adapter.strip_comments(text)
    if not repository_service.eiffel_adapter.is_probable_eiffel_source(
        path=Path(normalized_path),
        text=text,
        stripped_text=stripped_text,
    ):
        return _remember(set(), set(), config_paths)
    project_dir = PurePosixPath(normalized_path).parent
    variables = repository_service.eiffel_adapter.parse_config_variables(
        text,
        stripped_text=stripped_text,
    )
    root_class_names = repository_service.eiffel_adapter.parse_root_class_names(
        text,
        stripped_text=stripped_text,
    )
    project_root = repository_service._normalize_repository_relative_path(
        _normalize_eiffel_support_root(str(project_dir)) or ""
    )
    support_roots = {
        root
        for root in (project_root,)
        if root and not _is_non_operational_profile_path(root)
    }
    search_roots = [project_dir]
    for raw_target in repository_service.eiffel_adapter.parse_config_location_targets(
        text,
        stripped_text=stripped_text,
    ):
        resolved_target = _resolve_eiffel_config_target(
            manifest_path=normalized_path,
            raw_target=raw_target,
            variables=variables,
        )
        if not resolved_target:
            continue
        candidate = repo_path / resolved_target
        if candidate.is_file():
            config_paths.add(resolved_target)
            parent_dir = repository_service._normalize_repository_relative_path(
                _normalize_eiffel_support_root(str(PurePosixPath(resolved_target).parent)) or ""
            )
            if parent_dir and not _is_non_operational_profile_path(parent_dir):
                support_roots.add(parent_dir)
                search_roots.append(PurePosixPath(parent_dir))
            continue
        if candidate.is_dir():
            normalized_root = repository_service._normalize_repository_relative_path(
                _normalize_eiffel_support_root(resolved_target) or ""
            )
            if normalized_root and not _is_non_operational_profile_path(normalized_root):
                support_roots.add(normalized_root)
                search_roots.append(PurePosixPath(normalized_root))
    normalized_search_roots: list[str] = []
    seen_search_roots: set[str] = set()
    for search_root in search_roots:
        normalized_search_root = repository_service._normalize_repository_relative_path(
            str(search_root)
        )
        if normalized_search_root is None:
            normalized_search_root = ""
        if normalized_search_root in seen_search_roots:
            continue
        seen_search_roots.add(normalized_search_root)
        normalized_search_roots.append(normalized_search_root)

    candidate_file_paths = list(
        _cached_eiffel_candidate_paths(
            repo_path,
            normalized_search_roots=tuple(normalized_search_roots),
        )
    )
    entrypoints, inferred_roots, _ = _eiffel_profile_hints_from_candidates(
        repo_path,
        candidate_file_paths,
        preferred_root_class_names=root_class_names,
    )
    support_roots.update(inferred_roots)
    return _remember(
        entrypoints,
        _finalize_eiffel_support_roots(support_roots),
        config_paths,
    )


def _eiffel_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    preferred_root_class_names: tuple[str, ...] = (),
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path

    eiffel_files: list[str] = []
    eiffel_source_profiles: dict[str, _CachedEiffelSourceProfile] = {}
    module_index: dict[str, str] = {}
    support_root_candidates: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    candidate_alias_index: dict[str, str] = {}
    filtered_candidates: list[str] = []
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        pure_path = PurePosixPath(normalized_candidate)
        if (
            not normalized_candidate
            or pure_path.suffix.lower() != ".e"
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        filtered_candidates.append(normalized_candidate)
        for alias in (
            normalized_candidate,
            str(pure_path.with_suffix("")),
            pure_path.stem,
            pure_path.stem.upper(),
            pure_path.stem.lower(),
        ):
            if alias:
                candidate_alias_index.setdefault(alias, normalized_candidate)

    if (
        not preferred_root_class_names
        and len(filtered_candidates) >= _EIFFEL_FAST_FALLBACK_MIN_CANDIDATES
    ):
        fast_entrypoints, fast_support_roots = _eiffel_fast_fallback_entrypoints(
            filtered_candidates
        )
        if fast_entrypoints:
            return set(fast_entrypoints), {root for root in fast_support_roots if root}, set()

    def _resolve_candidate_target(target_name: str) -> str | None:
        normalized_target = str(target_name or "").strip()
        if not normalized_target:
            return None
        return candidate_alias_index.get(
            normalized_target
        ) or repository_service._resolve_suffix_match(
            module_index=candidate_alias_index,
            suffixes=(
                normalized_target,
                f"{normalized_target}.e",
                f"{normalized_target.lower()}.e",
            ),
        )

    def _load_source_profile(normalized_candidate: str) -> _CachedEiffelSourceProfile | None:
        source_profile = eiffel_source_profiles.get(normalized_candidate)
        if source_profile is not None:
            return source_profile
        source_profile = _cached_eiffel_source_profile(repo_path, normalized_candidate)
        if source_profile is None:
            return None
        eiffel_source_profiles[normalized_candidate] = source_profile
        eiffel_files.append(normalized_candidate)
        for alias in source_profile.aliases:
            module_index.setdefault(alias, normalized_candidate)
        return source_profile

    if preferred_root_class_names:
        queued_candidates = [
            target_file
            for root_class_name in preferred_root_class_names
            if (target_file := _resolve_candidate_target(root_class_name))
        ]
        if queued_candidates:
            visited_candidates: set[str] = set()
            while queued_candidates:
                normalized_candidate = queued_candidates.pop(0)
                if normalized_candidate in visited_candidates:
                    continue
                source_profile = _load_source_profile(normalized_candidate)
                if source_profile is None:
                    continue
                visited_candidates.add(normalized_candidate)
                for dependency_target in source_profile.dependency_targets:
                    target_file = module_index.get(
                        dependency_target
                    ) or _resolve_candidate_target(dependency_target)
                    if not target_file or target_file == normalized_candidate:
                        continue
                    imported_files.add(target_file)
                    support_root = repository_service._normalize_repository_relative_path(
                        _eiffel_support_root_for_file(target_file) or ""
                    )
                    if support_root:
                        support_root_candidates.add(support_root)
                    if target_file not in visited_candidates:
                        queued_candidates.append(target_file)
            if visited_candidates:
                entrypoint_paths.update(
                    target_file
                    for root_class_name in preferred_root_class_names
                    if (target_file := _resolve_candidate_target(root_class_name))
                )
                if not support_root_candidates:
                    for entrypoint_path in entrypoint_paths:
                        support_root = repository_service._normalize_repository_relative_path(
                            _eiffel_support_root_for_file(entrypoint_path) or ""
                        )
                        if support_root:
                            support_root_candidates.add(support_root)
                support_roots = _finalize_eiffel_support_roots(support_root_candidates)
                return entrypoint_paths, support_roots, set()

    for normalized_candidate in filtered_candidates:
        source_profile = _load_source_profile(normalized_candidate)
        if source_profile is None:
            continue
    for root_class_name in preferred_root_class_names:
        target_file = module_index.get(root_class_name) or repository_service._resolve_suffix_match(
            module_index=module_index,
            suffixes=(root_class_name, f"{root_class_name}.e", f"{root_class_name.lower()}.e"),
        )
        if target_file:
            entrypoint_paths.add(target_file)
    for normalized_candidate in eiffel_files:
        source_profile = eiffel_source_profiles.get(normalized_candidate)
        if source_profile is None:
            continue
        for dependency_target in source_profile.dependency_targets:
            target_file = module_index.get(
                dependency_target
            ) or repository_service._resolve_suffix_match(
                module_index=module_index,
                suffixes=(
                    dependency_target,
                    f"{dependency_target}.e",
                    f"{dependency_target.lower()}.e",
                ),
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            support_root = repository_service._normalize_repository_relative_path(
                _eiffel_support_root_for_file(target_file) or ""
            )
            if support_root:
                support_root_candidates.add(support_root)
    for normalized_candidate in eiffel_files:
        basename = PurePosixPath(normalized_candidate).name.lower()
        if (
            basename in _EIFFEL_PREFERRED_ENTRYPOINT_BASENAMES
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(eiffel_files)[:8])
    if not support_root_candidates:
        for entrypoint_path in entrypoint_paths:
            support_root = repository_service._normalize_repository_relative_path(
                _eiffel_support_root_for_file(entrypoint_path) or ""
            )
            if support_root:
                support_root_candidates.add(support_root)
    support_roots = _finalize_eiffel_support_roots(support_root_candidates)
    return entrypoint_paths, support_roots, set()
