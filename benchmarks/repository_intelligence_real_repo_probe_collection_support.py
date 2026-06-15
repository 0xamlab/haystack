from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath

from apps.api_server.services import (
    repository_intelligence_repository_source as repository_source,
)
from apps.api_server.services.repository_intelligence_contracts import RepositoryIntelligenceError
from benchmarks.repository_intelligence_real_repo_probe_repo_hint_support import (
    clear_ambiguous_as_repo_hint_cache,
    clear_ambiguous_v_repo_hint_cache,
    probe_ambiguous_as_repo_hint_language,
    probe_ambiguous_v_repo_hint_language,
)

_FOCUS_PATH_MATCH_SPEC_CACHE_LIMIT = 1024
_FOCUS_PATH_MATCH_SPEC_CACHE: dict[tuple[str, ...], tuple[bool, tuple[str, ...]]] = {}
_MAX_COLLAPSIBLE_SIBLING_FOCUS_PATHS = 4
_GIT_REPO_RELATIVE_FILES_CACHE_LIMIT = 128
_GIT_REPO_RELATIVE_FILES_CACHE: dict[str, list[str] | None] = {}
_GIT_REPO_RELATIVE_FOCUS_FILES_CACHE: dict[
    tuple[str, tuple[str, ...]], list[str] | None
] = {}
_GIT_REPO_ASSUME_CLEAN_CLONE_CACHE: set[str] = set()
_GIT_REPO_RELATIVE_FILES_CACHE_SCOPE_DEPTH = 0
_PROBE_COLLECTION_RANK_CACHE_LIMIT = 262_144
_PROBE_COLLECTION_RANK_CACHE: dict[
    tuple[str, str],
    tuple[int, int, int, int, str],
] = {}
_PROBE_COLLECTION_REPO_HINT_CACHE_LIMIT = 512
_PROBE_COLLECTION_REPO_HINT_CACHE: dict[tuple[str, str], str] = {}
_SCANNABLE_SUPPORT_ROOTS_CACHE_LIMIT = 512
_SCANNABLE_SUPPORT_ROOTS_CACHE: dict[tuple[str, ...], tuple[str, ...]] = {}
_SPARSE_CHECKOUT_ROOTS_CACHE_LIMIT = 128
_SPARSE_CHECKOUT_ROOTS_CACHE: dict[str, tuple[str, ...] | None] = {}
_PROBE_COLLECTION_CODELIKE_BASIC_SUFFIXES = frozenset(
    {".bas", ".bi", ".cls", ".ctl", ".frm", ".vbp"}
)
_PROBE_COLLECTION_GENERIC_CODELIKE_SUFFIX_RE = re.compile(r"^\.[a-z0-9][a-z0-9_+-]{0,11}$")
_PROBE_COLLECTION_DOCLIKE_PARTS = frozenset(
    {"doc", "docs", "docs_src", "example", "examples", "sample", "samples"}
)
_PROBE_COLLECTION_STATIC_NON_CODE_SUFFIXES = frozenset(
    {
        ".avif",
        ".bmp",
        ".dir",
        ".dll",
        ".exe",
        ".exp",
        ".frx",
        ".gif",
        ".htm",
        ".html",
        ".ico",
        ".ini",
        ".jpeg",
        ".jpg",
        ".lib",
        ".log",
        ".lvw",
        ".mp3",
        ".mp4",
        ".ogg",
        ".pack",
        ".pdf",
        ".png",
        ".promisor",
        ".reg",
        ".rev",
        ".svg",
        ".tar",
        ".tlb",
        ".tif",
        ".tiff",
        ".txt",
        ".vbg",
        ".vbw",
        ".wav",
        ".webm",
        ".webp",
        ".zip",
    }
)
_PROBE_COLLECTION_STRUCTURED_DATA_SUFFIXES = frozenset(
    {
        ".cfg",
        ".cnf",
        ".conf",
        ".config",
        ".csv",
        ".env",
        ".ini",
        ".json",
        ".json5",
        ".jsonc",
        ".lock",
        ".plist",
        ".properties",
        ".toml",
        ".tsv",
        ".xml",
        ".yaml",
        ".yml",
    }
)
_PROBE_COLLECTION_SUFFIXLESS_NON_CODE_BASENAMES = frozenset(
    {
        ".dockerignore",
        ".editorconfig",
        ".gitattributes",
        ".gitignore",
        ".gitmodules",
        ".mailmap",
        ".markdownlintignore",
        ".npmignore",
        ".prettierignore",
        ".stylelintignore",
        "authors",
        "changelog",
        "copying",
        "copyright",
        "licence",
        "license",
        "notice",
        "readme",
        "status",
        "unlicense",
    }
)
_PROBE_COLLECTION_SUFFIXLESS_NON_CODE_PREFIXES = (
    "copying-",
    "copying_",
    "licence-",
    "licence_",
    "license-",
    "license_",
    "notice-",
    "notice_",
)


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


@dataclass(frozen=True)
class _ProbeCollectionRuntimeDeps:
    normalize_repository_relative_path: object
    is_test_path: object
    direct_text_suffix_language_map: dict[str, str]
    non_code_graph_languages: frozenset[str]
    is_xpp_descriptor_config_path: object
    is_cfml_box_config_path: object
    is_repo_profile_manifest_name: object
    probe_language_for_path: object
    template_surface_ecosystems: frozenset[str]
    template_surface_parts: frozenset[str]


@lru_cache(maxsize=1)
def _probe_collection_runtime_deps() -> _ProbeCollectionRuntimeDeps:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    return _ProbeCollectionRuntimeDeps(
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        is_test_path=repository_service._is_test_path,
        direct_text_suffix_language_map=getattr(
            repository_service,
            "_DIRECT_TEXT_SUFFIX_LANGUAGE_MAP",
            {},
        ),
        non_code_graph_languages=frozenset(repository_service._NON_CODE_GRAPH_LANGUAGES),
        is_xpp_descriptor_config_path=probe_module._is_xpp_descriptor_config_path,
        is_cfml_box_config_path=probe_module._is_cfml_box_config_path,
        is_repo_profile_manifest_name=probe_module._is_repo_profile_manifest_name,
        probe_language_for_path=probe_module._probe_language_for_path,
        template_surface_ecosystems=frozenset(probe_module._TEMPLATE_SURFACE_ECOSYSTEMS),
        template_surface_parts=frozenset(probe_module._TEMPLATE_SURFACE_PARTS),
    )


def _strip_probe_path_wrappers(value: str) -> str:
    normalized_value = str(value or "").strip()
    while (
        len(normalized_value) >= 2
        and normalized_value[0] == normalized_value[-1]
        and normalized_value[0] in {'"', "'"}
    ):
        normalized_value = normalized_value[1:-1].strip()
    return normalized_value


@lru_cache(maxsize=512)
def _repo_cache_key(repo_path: Path) -> str:
    return str(repo_path.resolve())


@lru_cache(maxsize=1)
def _probe_collection_special_no_text_basenames() -> frozenset[str]:
    repository_service = _probe_module().repository_service
    starlark_basenames = {
        str(name).lower()
        for name in repository_service.starlark_adapter._KNOWN_BASENAMES
    }
    return frozenset(
        set(repository_service._SHELL_FILE_BASENAMES)
        | {str(name).lower() for name in repository_service.makefile_adapter.MAKEFILE_BASENAMES}
        | {
            str(name).lower()
            for name in repository_service.dockerfile_adapter.DOCKERFILE_BASENAMES
        }
        | {str(name).lower() for name in repository_service.cmake_adapter.CMAKE_CONFIG_BASENAMES}
        | starlark_basenames
        | {"v.mod"}
    )


def _probe_collection_static_no_text_language_hint_key(
    basename: str,
    suffix: str,
) -> str:
    normalized_basename = str(basename).lower()
    normalized_suffix = str(suffix).lower()
    return (
        normalized_basename
        if normalized_basename in _probe_collection_special_no_text_basenames()
        or not normalized_suffix
        else f"sample{normalized_suffix}"
    )


@lru_cache(maxsize=4096)
def _probe_collection_static_no_text_language_hint(
    hint_key: str,
) -> str:
    repository_service = _probe_module().repository_service
    return repository_service._language_for_path(
        Path(hint_key),
        text=None,
        repo_root=None,
    )


def _probe_collection_suffixless_non_code_language_hint(
    *,
    normalized_path: str,
    basename: str,
    suffix: str,
) -> str | None:
    if suffix:
        return None
    if normalized_path.startswith(".fossil-settings/"):
        return "txt"
    if basename in _PROBE_COLLECTION_SUFFIXLESS_NON_CODE_BASENAMES:
        return "txt"
    if basename.startswith(_PROBE_COLLECTION_SUFFIXLESS_NON_CODE_PREFIXES):
        return "txt"
    return None


def _normalize_git_listing_lines(
    raw_lines: list[str],
    *,
    normalize_path,
) -> list[str]:
    ordered_relative_paths: list[str] = []
    already_strictly_sorted = True
    previous_path: str | None = None
    for line in raw_lines:
        normalized = str(line).replace("\\", "/").strip()
        normalized = normalized.lstrip("/")
        if not (
            normalized
            and not normalized.endswith("/")
            and not normalized.startswith(("./", "../"))
            and normalized not in {".", ".."}
            and "//" not in normalized
            and "/./" not in normalized
            and "/../" not in normalized
            and not normalized.endswith("/.")
            and not normalized.endswith("/..")
        ):
            normalized = normalize_path(line)
        if not normalized:
            continue
        if previous_path is not None and normalized <= previous_path:
            already_strictly_sorted = False
        ordered_relative_paths.append(normalized)
        previous_path = normalized
    if already_strictly_sorted:
        return ordered_relative_paths
    return sorted(set(ordered_relative_paths))


def clear_git_repo_relative_files_cache() -> None:
    _GIT_REPO_RELATIVE_FILES_CACHE.clear()
    _GIT_REPO_RELATIVE_FOCUS_FILES_CACHE.clear()
    _GIT_REPO_ASSUME_CLEAN_CLONE_CACHE.clear()


def git_repo_relative_files_cache_size() -> int:
    return len(_GIT_REPO_RELATIVE_FILES_CACHE)


def seed_git_repo_relative_files_cache(
    repo_path: Path,
    relative_paths: list[str],
    *,
    relative_paths_are_canonical: bool = False,
) -> None:
    repository_service = _probe_module().repository_service

    cache_key = _repo_cache_key(repo_path)
    if relative_paths_are_canonical:
        normalized_relative_paths = list(relative_paths)
    else:
        normalized_relative_paths = _normalize_git_listing_lines(
            [str(relative_path) for relative_path in relative_paths],
            normalize_path=repository_service._normalize_repository_relative_path,
        )
    if len(_GIT_REPO_RELATIVE_FILES_CACHE) >= _GIT_REPO_RELATIVE_FILES_CACHE_LIMIT:
        oldest_key = next(iter(_GIT_REPO_RELATIVE_FILES_CACHE))
        _GIT_REPO_RELATIVE_FILES_CACHE.pop(oldest_key, None)
    _GIT_REPO_RELATIVE_FILES_CACHE[cache_key] = normalized_relative_paths


def _cached_git_repo_relative_files(repo_path: Path) -> tuple[bool, list[str] | None]:
    cache_key = _repo_cache_key(repo_path)
    if cache_key not in _GIT_REPO_RELATIVE_FILES_CACHE:
        return False, None
    cached_relative_paths = _GIT_REPO_RELATIVE_FILES_CACHE[cache_key]
    return True, None if cached_relative_paths is None else list(cached_relative_paths)


def set_git_repo_assume_clean_clone(repo_path: Path, assume_clean_git_clone: bool) -> None:
    cache_key = _repo_cache_key(repo_path)
    if assume_clean_git_clone:
        _GIT_REPO_ASSUME_CLEAN_CLONE_CACHE.add(cache_key)
        return
    _GIT_REPO_ASSUME_CLEAN_CLONE_CACHE.discard(cache_key)


def _repo_assume_clean_git_clone(repo_path: Path) -> bool:
    return _repo_cache_key(repo_path) in _GIT_REPO_ASSUME_CLEAN_CLONE_CACHE


def clear_probe_collection_rank_cache() -> None:
    _PROBE_COLLECTION_RANK_CACHE.clear()
    _probe_collection_static_no_text_language_hint.cache_clear()
    _probe_collection_runtime_deps.cache_clear()


def probe_collection_rank_cache_size() -> int:
    return len(_PROBE_COLLECTION_RANK_CACHE)


def clear_probe_collection_repo_hint_cache() -> None:
    _PROBE_COLLECTION_REPO_HINT_CACHE.clear()
    clear_ambiguous_as_repo_hint_cache()
    clear_ambiguous_v_repo_hint_cache()


def clear_support_root_caches() -> None:
    _SCANNABLE_SUPPORT_ROOTS_CACHE.clear()
    _SPARSE_CHECKOUT_ROOTS_CACHE.clear()


def _support_root_cache_key(
    support_roots: list[str] | set[str],
) -> tuple[str, ...]:
    return tuple(sorted(str(root) for root in support_roots))


def _sparse_checkout_materialized_roots(repo_path: Path) -> tuple[str, ...] | None:
    cache_key = _repo_cache_key(repo_path)
    if cache_key in _SPARSE_CHECKOUT_ROOTS_CACHE:
        return _SPARSE_CHECKOUT_ROOTS_CACHE[cache_key]

    sparse_checkout_path = repo_path / ".git" / "info" / "sparse-checkout"
    result: tuple[str, ...] | None = None
    try:
        raw_lines = sparse_checkout_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        raw_lines = []
    if raw_lines:
        parsed_roots: list[str] = []
        parseable = True
        for raw_line in raw_lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line in {"/*", "/"} or line.startswith("!"):
                parseable = False
                break
            if line.endswith("/**"):
                line = line[:-3]
            normalized = line.strip("/")
            if not normalized or "*" in normalized:
                parseable = False
                break
            parsed_roots.append(normalized)
        if parseable and parsed_roots:
            result = tuple(sorted(dict.fromkeys(parsed_roots)))

    if len(_SPARSE_CHECKOUT_ROOTS_CACHE) >= _SPARSE_CHECKOUT_ROOTS_CACHE_LIMIT:
        oldest_key = next(iter(_SPARSE_CHECKOUT_ROOTS_CACHE))
        _SPARSE_CHECKOUT_ROOTS_CACHE.pop(oldest_key, None)
    _SPARSE_CHECKOUT_ROOTS_CACHE[cache_key] = result
    return result


def _materialized_repository_relative_files(
    repo_path: Path,
    *,
    roots: tuple[str, ...] | None = None,
) -> list[str]:
    candidate_roots = [repo_path] if not roots else [repo_path / root for root in roots]
    relative_paths: list[str] = []
    for candidate_root in candidate_roots:
        if not candidate_root.exists():
            continue
        if candidate_root.is_file():
            relative_paths.append(
                str(candidate_root.relative_to(repo_path)).replace("\\", "/")
            )
            continue
        for dirpath, dirnames, filenames in os.walk(candidate_root):
            dirnames[:] = [dirname for dirname in dirnames if dirname != ".git"]
            for filename in filenames:
                candidate = Path(dirpath) / filename
                relative_paths.append(str(candidate.relative_to(repo_path)).replace("\\", "/"))
    return sorted(dict.fromkeys(relative_paths))


def begin_git_repo_relative_files_cache_scope() -> None:
    global _GIT_REPO_RELATIVE_FILES_CACHE_SCOPE_DEPTH

    if _GIT_REPO_RELATIVE_FILES_CACHE_SCOPE_DEPTH == 0:
        from benchmarks import repository_intelligence_real_repo_probe_path_scan_support as path_scan_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_build_tooling_support as build_tooling_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_manifest_build_support as manifest_build_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_project_family_support as project_family_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_path_selection_support as path_selection_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_path_classification_support as classification_support

        repository_source.begin_git_command_cache_scope()
        clear_git_repo_relative_files_cache()
        clear_probe_collection_rank_cache()
        clear_probe_collection_repo_hint_cache()
        clear_support_root_caches()
        project_family_support.clear_smalltalk_profile_hint_cache()
        path_scan_support.clear_candidate_repository_file_paths_cache()
        path_scan_support.clear_probe_repository_file_paths_cache()
        path_selection_support.clear_support_root_match_cache()
        path_selection_support.clear_repo_profile_config_path_cache()
        classification_support.clear_probe_language_for_path_cache()
        classification_support.begin_repo_file_stat_cache_scope()
        manifest_build_support.clear_c_family_manifest_ecosystem_cache()
        build_tooling_support.clear_eiffel_source_profile_cache()
    _GIT_REPO_RELATIVE_FILES_CACHE_SCOPE_DEPTH += 1


def end_git_repo_relative_files_cache_scope() -> None:
    global _GIT_REPO_RELATIVE_FILES_CACHE_SCOPE_DEPTH

    if _GIT_REPO_RELATIVE_FILES_CACHE_SCOPE_DEPTH <= 0:
        from benchmarks import repository_intelligence_real_repo_probe_path_scan_support as path_scan_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_build_tooling_support as build_tooling_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_manifest_build_support as manifest_build_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_project_family_support as project_family_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_path_selection_support as path_selection_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_path_classification_support as classification_support

        repository_source.end_git_command_cache_scope()
        clear_git_repo_relative_files_cache()
        clear_probe_collection_rank_cache()
        clear_probe_collection_repo_hint_cache()
        clear_support_root_caches()
        project_family_support.clear_smalltalk_profile_hint_cache()
        project_family_support.clear_starlark_profile_hint_cache()
        path_scan_support.clear_candidate_repository_file_paths_cache()
        path_scan_support.clear_probe_repository_file_paths_cache()
        path_selection_support.clear_support_root_match_cache()
        path_selection_support.clear_repo_profile_config_path_cache()
        classification_support.clear_probe_language_for_path_cache()
        classification_support.end_repo_file_stat_cache_scope()
        manifest_build_support.clear_c_family_manifest_ecosystem_cache()
        build_tooling_support.clear_eiffel_source_profile_cache()
        _GIT_REPO_RELATIVE_FILES_CACHE_SCOPE_DEPTH = 0
        return
    _GIT_REPO_RELATIVE_FILES_CACHE_SCOPE_DEPTH -= 1
    if _GIT_REPO_RELATIVE_FILES_CACHE_SCOPE_DEPTH == 0:
        from benchmarks import repository_intelligence_real_repo_probe_path_scan_support as path_scan_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_build_tooling_support as build_tooling_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_manifest_build_support as manifest_build_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_project_family_support as project_family_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_path_selection_support as path_selection_support
        from benchmarks import repository_intelligence_real_repo_probe_profile_path_classification_support as classification_support

        repository_source.end_git_command_cache_scope()
        clear_git_repo_relative_files_cache()
        clear_probe_collection_rank_cache()
        clear_probe_collection_repo_hint_cache()
        clear_support_root_caches()
        project_family_support.clear_smalltalk_profile_hint_cache()
        project_family_support.clear_starlark_profile_hint_cache()
        path_scan_support.clear_candidate_repository_file_paths_cache()
        path_scan_support.clear_probe_repository_file_paths_cache()
        path_selection_support.clear_support_root_match_cache()
        path_selection_support.clear_repo_profile_config_path_cache()
        classification_support.clear_probe_language_for_path_cache()
        classification_support.end_repo_file_stat_cache_scope()
        manifest_build_support.clear_c_family_manifest_ecosystem_cache()
        build_tooling_support.clear_eiffel_source_profile_cache()


def _git_repo_relative_files(repo_path: Path) -> list[str] | None:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    cache_key = _repo_cache_key(repo_path)
    assume_clean_git_clone = _repo_assume_clean_git_clone(repo_path)
    if cache_key in _GIT_REPO_RELATIVE_FILES_CACHE:
        cached_relative_paths = _GIT_REPO_RELATIVE_FILES_CACHE[cache_key]
        return None if cached_relative_paths is None else list(cached_relative_paths)
    sparse_roots = _sparse_checkout_materialized_roots(repo_path)
    if sparse_roots is not None:
        cached_sparse_relative_paths = _sparse_relative_paths_from_cached_focus_listing(
            cache_key,
            sparse_roots,
        )
        if cached_sparse_relative_paths is not None:
            if len(_GIT_REPO_RELATIVE_FILES_CACHE) >= _GIT_REPO_RELATIVE_FILES_CACHE_LIMIT:
                oldest_key = next(iter(_GIT_REPO_RELATIVE_FILES_CACHE))
                _GIT_REPO_RELATIVE_FILES_CACHE.pop(oldest_key, None)
            _GIT_REPO_RELATIVE_FILES_CACHE[cache_key] = cached_sparse_relative_paths
            return list(cached_sparse_relative_paths)
        try:
            output = str(
                repository_service._git_command(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "ls-files",
                    *(
                        ["--cached"]
                        if assume_clean_git_clone
                        else ["--cached", "--others", "--exclude-standard"]
                    ),
                    "--",
                    *sparse_roots,
                ],
                    timeout=120.0,
                )
            )
        except RepositoryIntelligenceError:
            ordered_relative_paths = _materialized_repository_relative_files(
                repo_path,
                roots=sparse_roots,
            )
        else:
            ordered_relative_paths = _normalize_git_listing_lines(
                output.splitlines(),
                normalize_path=repository_service._normalize_repository_relative_path,
            )
        if len(_GIT_REPO_RELATIVE_FILES_CACHE) >= _GIT_REPO_RELATIVE_FILES_CACHE_LIMIT:
            oldest_key = next(iter(_GIT_REPO_RELATIVE_FILES_CACHE))
            _GIT_REPO_RELATIVE_FILES_CACHE.pop(oldest_key, None)
        _GIT_REPO_RELATIVE_FILES_CACHE[cache_key] = ordered_relative_paths
        return list(ordered_relative_paths)
    try:
        output = str(
            repository_service._git_command(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "ls-files",
                    *(
                        ["--cached"]
                        if assume_clean_git_clone
                        else ["--cached", "--others", "--exclude-standard"]
                    ),
                ],
                timeout=120.0,
            )
        )
    except RepositoryIntelligenceError:
        if len(_GIT_REPO_RELATIVE_FILES_CACHE) >= _GIT_REPO_RELATIVE_FILES_CACHE_LIMIT:
            oldest_key = next(iter(_GIT_REPO_RELATIVE_FILES_CACHE))
            _GIT_REPO_RELATIVE_FILES_CACHE.pop(oldest_key, None)
        _GIT_REPO_RELATIVE_FILES_CACHE[cache_key] = None
        return None
    ordered_relative_paths = _normalize_git_listing_lines(
        output.splitlines(),
        normalize_path=repository_service._normalize_repository_relative_path,
    )
    if len(_GIT_REPO_RELATIVE_FILES_CACHE) >= _GIT_REPO_RELATIVE_FILES_CACHE_LIMIT:
        oldest_key = next(iter(_GIT_REPO_RELATIVE_FILES_CACHE))
        _GIT_REPO_RELATIVE_FILES_CACHE.pop(oldest_key, None)
    _GIT_REPO_RELATIVE_FILES_CACHE[cache_key] = ordered_relative_paths
    return list(ordered_relative_paths)


def _git_repo_relative_files_for_focus_paths(
    repo_path: Path,
    *,
    focus_paths: list[str],
) -> list[str] | None:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    assume_clean_git_clone = _repo_assume_clean_git_clone(repo_path)

    has_repo_root_focus_path, normalized_focus_paths = _focus_path_match_spec(focus_paths)
    if has_repo_root_focus_path or not normalized_focus_paths:
        return _git_repo_relative_files(repo_path)
    normalized_focus_paths = _compact_focus_paths_for_git_listing(normalized_focus_paths)

    repo_cache_key = _repo_cache_key(repo_path)
    cache_key = (repo_cache_key, normalized_focus_paths)
    if cache_key in _GIT_REPO_RELATIVE_FOCUS_FILES_CACHE:
        cached_relative_paths = _GIT_REPO_RELATIVE_FOCUS_FILES_CACHE[cache_key]
        return None if cached_relative_paths is None else list(cached_relative_paths)
    focused_relative_paths = _focused_relative_paths_from_cached_focus_listing(
        repo_cache_key,
        normalized_focus_paths,
    )
    if focused_relative_paths is not None:
        _cache_focused_relative_paths(cache_key, focused_relative_paths)
        return list(focused_relative_paths)
    if repo_cache_key in _GIT_REPO_RELATIVE_FILES_CACHE:
        cached_repo_relative_paths = _GIT_REPO_RELATIVE_FILES_CACHE[repo_cache_key]
        if cached_repo_relative_paths is None:
            return None
        focused_relative_paths = [
            relative_path
            for relative_path in cached_repo_relative_paths
            if any(
                relative_path == normalized_focus_path
                or relative_path.startswith(f"{normalized_focus_path}/")
                for normalized_focus_path in normalized_focus_paths
            )
        ]
        _cache_focused_relative_paths(cache_key, focused_relative_paths)
        return list(focused_relative_paths)
    try:
        output = str(
            repository_service._git_command(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "ls-files",
                    *(
                        ["--cached"]
                        if assume_clean_git_clone
                        else ["--cached", "--others", "--exclude-standard"]
                    ),
                    "--",
                    *normalized_focus_paths,
                ],
                timeout=120.0,
            )
        )
    except RepositoryIntelligenceError:
        _cache_focused_relative_paths(cache_key, None)
        return None
    ordered_relative_paths = _normalize_git_listing_lines(
        output.splitlines(),
        normalize_path=repository_service._normalize_repository_relative_path,
    )
    _cache_focused_relative_paths(cache_key, ordered_relative_paths)
    return list(ordered_relative_paths)


def _cache_focused_relative_paths(
    cache_key: tuple[str, tuple[str, ...]],
    relative_paths: list[str] | None,
) -> None:
    if len(_GIT_REPO_RELATIVE_FOCUS_FILES_CACHE) >= _GIT_REPO_RELATIVE_FILES_CACHE_LIMIT:
        oldest_key = next(iter(_GIT_REPO_RELATIVE_FOCUS_FILES_CACHE))
        _GIT_REPO_RELATIVE_FOCUS_FILES_CACHE.pop(oldest_key, None)
    _GIT_REPO_RELATIVE_FOCUS_FILES_CACHE[cache_key] = relative_paths


def _focused_relative_paths_from_cached_focus_listing(
    repo_cache_key: str,
    normalized_focus_paths: tuple[str, ...],
) -> list[str] | None:
    for (cached_repo_key, cached_focus_paths), cached_relative_paths in (
        _GIT_REPO_RELATIVE_FOCUS_FILES_CACHE.items()
    ):
        if cached_repo_key != repo_cache_key or cached_relative_paths is None:
            continue
        if not _cached_focus_paths_cover_requested_paths(
            cached_focus_paths,
            normalized_focus_paths,
        ):
            continue
        return [
            relative_path
            for relative_path in cached_relative_paths
            if any(
                relative_path == normalized_focus_path
                or relative_path.startswith(f"{normalized_focus_path}/")
                for normalized_focus_path in normalized_focus_paths
            )
        ]
    return None


def _cached_focus_paths_cover_requested_paths(
    cached_focus_paths: tuple[str, ...],
    requested_focus_paths: tuple[str, ...],
) -> bool:
    for requested_focus_path in requested_focus_paths:
        if not any(
            requested_focus_path == cached_focus_path
            or requested_focus_path.startswith(f"{cached_focus_path}/")
            for cached_focus_path in cached_focus_paths
        ):
            return False
    return True


def _sparse_relative_paths_from_cached_focus_listing(
    repo_cache_key: str,
    sparse_roots: tuple[str, ...],
) -> list[str] | None:
    for (cached_repo_key, cached_focus_paths), cached_relative_paths in (
        _GIT_REPO_RELATIVE_FOCUS_FILES_CACHE.items()
    ):
        if cached_repo_key != repo_cache_key or cached_relative_paths is None:
            continue
        if not _cached_focus_paths_cover_requested_paths(
            cached_focus_paths,
            sparse_roots,
        ):
            continue
        return list(cached_relative_paths)
    return None


def _matches_focus_paths(relative_path: str, focus_paths: list[str]) -> bool:
    repository_service = _probe_module().repository_service

    has_repo_root_focus_path, normalized_focus_paths = _focus_path_match_spec(focus_paths)
    if has_repo_root_focus_path or not normalized_focus_paths:
        return True
    for normalized_focus in normalized_focus_paths:
        if relative_path == normalized_focus or relative_path.startswith(f"{normalized_focus}/"):
            return True
    return False


def _focus_path_match_spec(focus_paths: list[str]) -> tuple[bool, tuple[str, ...]]:
    repository_service = _probe_module().repository_service

    if not focus_paths:
        return True, ()
    cache_key = tuple(
        sorted(
            {
                "."
                if str(focus_path).strip() in {"", ".", "./"}
                else str(focus_path)
                for focus_path in focus_paths
            }
        )
    )
    cached_spec = _FOCUS_PATH_MATCH_SPEC_CACHE.get(cache_key)
    if cached_spec is not None:
        return cached_spec
    has_repo_root_focus_path = "." in cache_key
    normalized_focus_paths = tuple(
        sorted(
            {
                normalized_focus
                for focus_path in focus_paths
                if (
                    normalized_focus := repository_service._normalize_repository_relative_path(
                        focus_path
                    )
                )
            }
        )
    )
    spec = (has_repo_root_focus_path, normalized_focus_paths)
    if len(_FOCUS_PATH_MATCH_SPEC_CACHE) >= _FOCUS_PATH_MATCH_SPEC_CACHE_LIMIT:
        oldest_key = next(iter(_FOCUS_PATH_MATCH_SPEC_CACHE))
        _FOCUS_PATH_MATCH_SPEC_CACHE.pop(oldest_key, None)
    _FOCUS_PATH_MATCH_SPEC_CACHE[cache_key] = spec
    return spec


def _compact_focus_paths_for_git_listing(
    focus_paths: tuple[str, ...],
) -> tuple[str, ...]:
    if len(focus_paths) < 2:
        return focus_paths
    compacted_focus_paths = set(focus_paths)
    while True:
        grouped_by_parent: dict[str, list[str]] = {}
        for focus_path in compacted_focus_paths:
            parent_path = str(PurePosixPath(focus_path).parent)
            if parent_path in {"", "."}:
                continue
            grouped_by_parent.setdefault(parent_path, []).append(focus_path)
        collapsed = False
        for parent_path, child_paths in grouped_by_parent.items():
            if (
                len(child_paths) < 2
                or len(child_paths) > _MAX_COLLAPSIBLE_SIBLING_FOCUS_PATHS
            ):
                continue
            compacted_focus_paths.difference_update(child_paths)
            compacted_focus_paths.add(parent_path)
            collapsed = True
        if not collapsed:
            break
    ordered_focus_paths = sorted(compacted_focus_paths, key=lambda path: (len(path), path))
    compacted: list[str] = []
    for focus_path in ordered_focus_paths:
        if any(
            focus_path == existing_path or focus_path.startswith(f"{existing_path}/")
            for existing_path in compacted
        ):
            continue
        compacted.append(focus_path)
    return tuple(compacted)


def _probe_collection_rank(
    relative_path: str,
    *,
    repo_path: Path | None = None,
) -> tuple[int, int, int, int, str]:
    probe_module = _probe_module()
    runtime_deps = _probe_collection_runtime_deps()

    cache_repo_key = str(repo_path or "")
    raw_cache_key = (cache_repo_key, str(relative_path))
    cached_rank = _PROBE_COLLECTION_RANK_CACHE.get(raw_cache_key)
    if cached_rank is not None:
        return cached_rank
    normalize_repository_relative_path = runtime_deps.normalize_repository_relative_path
    normalized_path = normalize_repository_relative_path(relative_path)
    stripped_path = _strip_probe_path_wrappers(normalized_path)
    if stripped_path != normalized_path:
        normalized_path = normalize_repository_relative_path(stripped_path)
    if not normalized_path:
        return (1, 1, 1, 1, relative_path)
    normalized_cache_key = (cache_repo_key, normalized_path)
    cached_rank = _PROBE_COLLECTION_RANK_CACHE.get(normalized_cache_key)
    if cached_rank is not None:
        _PROBE_COLLECTION_RANK_CACHE[raw_cache_key] = cached_rank
        return cached_rank
    basename = normalized_path.rsplit("/", 1)[-1].lower()
    parent_path, _separator, _basename = normalized_path.rpartition("/")
    parent_name = parent_path.rsplit("/", 1)[-1].lower() if parent_path else ""
    suffix = f".{basename.rsplit('.', 1)[1]}" if "." in basename else ""
    path_parts = tuple(part.lower() for part in normalized_path.split("/") if part)
    direct_text_suffix_language_map = runtime_deps.direct_text_suffix_language_map
    suffixless_non_code_language = _probe_collection_suffixless_non_code_language_hint(
        normalized_path=normalized_path,
        basename=basename,
        suffix=suffix,
    )
    hint_language = (
        suffixless_non_code_language
        if suffixless_non_code_language is not None
        else (
            direct_text_suffix_language_map.get(suffix)
            if suffix in direct_text_suffix_language_map
            else _probe_collection_static_no_text_language_hint(
                _probe_collection_static_no_text_language_hint_key(basename, suffix)
            )
        )
    )
    language = hint_language
    if language == "unknown" and suffix == ".v":
        language = _probe_collection_repo_hint_language(
            normalized_path,
            repo_path=repo_path,
        )
    if language == "unknown" and (
        suffix in _PROBE_COLLECTION_CODELIKE_BASIC_SUFFIXES
        or (
            suffix not in _PROBE_COLLECTION_STATIC_NON_CODE_SUFFIXES
            and suffix not in _PROBE_COLLECTION_STRUCTURED_DATA_SUFFIXES
            and _PROBE_COLLECTION_GENERIC_CODELIKE_SUFFIX_RE.match(suffix) is not None
        )
    ):
        language = "__code_like__"
    if language == "unknown" and suffix not in _PROBE_COLLECTION_STATIC_NON_CODE_SUFFIXES:
        language = runtime_deps.probe_language_for_path(normalized_path, repo_path=repo_path)
    is_test = 1 if runtime_deps.is_test_path(normalized_path) else 0
    is_xpp_descriptor = (
        repo_path is not None
        and suffix == ".xml"
        and parent_name == "descriptor"
        and runtime_deps.is_xpp_descriptor_config_path(repo_path, normalized_path)
    )
    is_cfml_box = (
        repo_path is not None
        and basename == "box.json"
        and runtime_deps.is_cfml_box_config_path(repo_path, normalized_path)
    )
    is_manifest = (
        0
        if runtime_deps.is_repo_profile_manifest_name(basename)
        or is_xpp_descriptor
        or is_cfml_box
        else 1
    )
    is_non_code = (
        1
        if language in runtime_deps.non_code_graph_languages
        or language in {"unknown", "txt"}
        else 0
    )
    has_doclike_part = any(part in _PROBE_COLLECTION_DOCLIKE_PARTS for part in path_parts)
    platform_noise = (
        1
        if (
            normalized_path.startswith(".github/")
            or normalized_path.startswith("docs/")
            or has_doclike_part
            or basename
            in {"readme.md", "changelog.md", "contributing.md", "license", "license.txt"}
        )
        else 0
    )
    has_template_surface_part = language in runtime_deps.template_surface_ecosystems and any(
        part in runtime_deps.template_surface_parts for part in path_parts
    )
    template_surface_priority = (
        0 if has_template_surface_part else 1
    )
    rank = (
        is_test,
        min(is_non_code, is_manifest),
        template_surface_priority,
        platform_noise,
        normalized_path,
    )
    if len(_PROBE_COLLECTION_RANK_CACHE) >= _PROBE_COLLECTION_RANK_CACHE_LIMIT:
        oldest_key = next(iter(_PROBE_COLLECTION_RANK_CACHE))
        _PROBE_COLLECTION_RANK_CACHE.pop(oldest_key, None)
    _PROBE_COLLECTION_RANK_CACHE[normalized_cache_key] = rank
    if raw_cache_key != normalized_cache_key:
        _PROBE_COLLECTION_RANK_CACHE[raw_cache_key] = rank
    return rank


def _probe_collection_repo_hint_language(
    normalized_path: str,
    *,
    repo_path: Path | None,
) -> str:
    if repo_path is None:
        return "unknown"

    suffix = PurePosixPath(normalized_path).suffix.lower()
    if suffix not in {".as", ".v"}:
        return "unknown"

    cache_key = (_repo_cache_key(repo_path), suffix)
    cached_language = _PROBE_COLLECTION_REPO_HINT_CACHE.get(cache_key)
    if cached_language is not None:
        return cached_language

    if suffix == ".as":
        language = probe_ambiguous_as_repo_hint_language(repo_path)
    else:
        language = probe_ambiguous_v_repo_hint_language(repo_path)

    if len(_PROBE_COLLECTION_REPO_HINT_CACHE) >= _PROBE_COLLECTION_REPO_HINT_CACHE_LIMIT:
        oldest_key = next(iter(_PROBE_COLLECTION_REPO_HINT_CACHE))
        _PROBE_COLLECTION_REPO_HINT_CACHE.pop(oldest_key, None)
    _PROBE_COLLECTION_REPO_HINT_CACHE[cache_key] = language
    return language


def _candidate_existing_paths(
    repo_path: Path,
    *,
    paths: set[str],
) -> list[str]:
    from benchmarks import (
        repository_intelligence_real_repo_probe_profile_path_classification_support
        as classification_support,
    )

    repository_service = _probe_module().repository_service

    existing_paths: list[str] = []
    for raw_path in sorted(paths):
        normalized_path = repository_service._normalize_repository_relative_path(raw_path)
        if not normalized_path:
            continue
        candidate_stat = classification_support._repo_file_stat(repo_path, normalized_path)
        if candidate_stat is not None and stat.S_ISREG(candidate_stat.st_mode):
            existing_paths.append(normalized_path)
    return existing_paths


def _candidate_existing_roots(
    repo_path: Path,
    *,
    roots: set[str],
) -> list[str]:
    from benchmarks import (
        repository_intelligence_real_repo_probe_profile_path_classification_support
        as classification_support,
    )

    repository_service = _probe_module().repository_service

    existing_roots: list[str] = []
    for raw_root in sorted(roots):
        normalized_root = repository_service._normalize_repository_relative_path(raw_root)
        if not normalized_root:
            if str(raw_root).strip().strip("./") == "" and repo_path.is_dir():
                existing_roots.append(".")
            continue
        candidate_stat = classification_support._repo_file_stat(repo_path, normalized_root)
        if candidate_stat is not None and stat.S_ISDIR(candidate_stat.st_mode):
            existing_roots.append(normalized_root)
    return existing_roots


def _candidate_existing_leaf_roots(
    repo_path: Path,
    *,
    roots: set[str],
    entrypoint_paths: set[str] | None = None,
) -> list[str]:
    existing_roots = _candidate_existing_roots(repo_path, roots=roots)
    scannable_roots = _normalized_scannable_support_roots(existing_roots)
    if entrypoint_paths:
        scannable_roots = _prune_top_level_auxiliary_roots_without_entrypoints(
            support_roots=scannable_roots,
            entrypoint_paths=entrypoint_paths,
        )
    return sorted(scannable_roots)


def _normalized_scannable_support_roots(
    support_roots: list[str] | set[str],
) -> set[str]:
    cache_key = _support_root_cache_key(support_roots)
    cached_roots = _SCANNABLE_SUPPORT_ROOTS_CACHE.get(cache_key)
    if cached_roots is not None:
        return set(cached_roots)
    normalized_roots = _normalized_scannable_support_roots_uncached(support_roots)
    if len(_SCANNABLE_SUPPORT_ROOTS_CACHE) >= _SCANNABLE_SUPPORT_ROOTS_CACHE_LIMIT:
        oldest_key = next(iter(_SCANNABLE_SUPPORT_ROOTS_CACHE))
        _SCANNABLE_SUPPORT_ROOTS_CACHE.pop(oldest_key, None)
    _SCANNABLE_SUPPORT_ROOTS_CACHE[cache_key] = tuple(sorted(normalized_roots))
    return set(normalized_roots)


def _normalized_scannable_support_roots_uncached(
    support_roots: list[str] | set[str],
) -> set[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    has_repo_root = any(str(root).strip().strip("./") == "" for root in support_roots)
    normalized_support_roots = {
        normalized_root
        for root in support_roots
        if (
            normalized_root := repository_service._normalize_repository_relative_path(root)
        )
    }
    if has_repo_root:
        normalized_support_roots.add(".")
    if not normalized_support_roots:
        return set()
    repo_root_requested = "." in normalized_support_roots
    non_root_support_roots = normalized_support_roots - {"."}
    leaf_support_roots = probe_module._leaf_support_roots(non_root_support_roots)
    if repo_root_requested:
        leaf_support_roots.add(".")
    if not leaf_support_roots:
        return set()

    auxiliary_root_basenames = {"bin", "exe"}
    roots_by_parent: dict[str, list[str]] = {}
    for root in leaf_support_roots:
        parent = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(root).parent)
        )
        roots_by_parent.setdefault(parent or "", []).append(root)

    pruned_support_roots = set(leaf_support_roots)
    for sibling_roots in roots_by_parent.values():
        if not any(
            PurePosixPath(root).name.lower() not in auxiliary_root_basenames
            for root in sibling_roots
        ):
            continue
        for root in sibling_roots:
            if PurePosixPath(root).name.lower() in auxiliary_root_basenames:
                pruned_support_roots.discard(root)
    return pruned_support_roots or leaf_support_roots


def _prune_top_level_auxiliary_roots_without_entrypoints(
    *,
    support_roots: set[str],
    entrypoint_paths: set[str],
) -> set[str]:
    repository_service = _probe_module().repository_service

    normalized_entrypoints = {
        normalized_path
        for path in entrypoint_paths
        if (
            normalized_path := repository_service._normalize_repository_relative_path(path)
        )
    }
    if not normalized_entrypoints:
        return set(support_roots)
    auxiliary_root_basenames = {"bin", "exe"}
    if not any(
        PurePosixPath(root).name.lower() not in auxiliary_root_basenames
        for root in support_roots
    ):
        return set(support_roots)

    pruned_support_roots = set(support_roots)
    for root in support_roots:
        root_parts = PurePosixPath(root).parts
        if len(root_parts) != 1:
            continue
        if root_parts[-1].lower() not in auxiliary_root_basenames:
            continue
        if any(
            entrypoint == root or entrypoint.startswith(f"{root}/")
            for entrypoint in normalized_entrypoints
        ):
            continue
        pruned_support_roots.discard(root)
    return pruned_support_roots or set(support_roots)
