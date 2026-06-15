from __future__ import annotations

import os
import re
import stat
from collections import Counter
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_language_priority import (
    canonical_repository_language,
    sort_repository_languages,
)
from apps.api_server.services import repository_intelligence as repository_service

_BEST_MATCHING_SUPPORT_ROOT_CACHE_LIMIT = 4096
_BEST_MATCHING_SUPPORT_ROOT_CACHE: dict[tuple[tuple[str, ...], str], str | None] = {}
_REPO_PROFILE_CONFIG_PATH_CACHE_LIMIT = 256
_REPO_PROFILE_CONFIG_PATH_CACHE: dict[tuple[str, tuple[str, ...]], tuple[str, ...]] = {}
_REPO_PROFILE_CODE_CANDIDATE_CACHE_LIMIT = 16384
_REPO_PROFILE_CODE_CANDIDATE_CACHE: dict[
    tuple[str, str, int | None, int | None],
    bool,
] = {}
_MOONBIT_CONFIG_BASENAMES = repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES
_RESCRIPT_CONFIG_BASENAMES = repository_service.rescript_adapter.RESCRIPT_CONFIG_BASENAMES
_NON_CODE_GRAPH_LANGUAGES = repository_service._NON_CODE_GRAPH_LANGUAGES
_ENTRYPOINT_DEMOTED_LANGUAGES = repository_service._ENTRYPOINT_DEMOTED_LANGUAGES


@lru_cache(maxsize=32768)
def _normalized_path_components(
    normalized_path: str,
) -> tuple[PurePosixPath, str, str, str, str, tuple[str, ...]]:
    candidate_path = PurePosixPath(normalized_path)
    return (
        candidate_path,
        candidate_path.name.lower(),
        candidate_path.suffix.lower(),
        candidate_path.stem.lower(),
        candidate_path.parent.name.lower(),
        candidate_path.parts,
    )


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _repo_cache_key(repo_path: Path) -> str:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    return collection_support._repo_cache_key(repo_path)


def clear_support_root_match_cache() -> None:
    _BEST_MATCHING_SUPPORT_ROOT_CACHE.clear()


def clear_repo_profile_config_path_cache() -> None:
    _REPO_PROFILE_CONFIG_PATH_CACHE.clear()
    _REPO_PROFILE_CODE_CANDIDATE_CACHE.clear()


def _best_matching_support_root_cache_key(
    path: str,
    *,
    support_roots: set[str],
) -> tuple[tuple[str, ...], str]:
    return (tuple(sorted(str(root) for root in support_roots)), path)


def _best_matching_support_root_uncached(
    normalized_path: str,
    *,
    normalized_support_roots: set[str],
) -> str | None:
    matched_roots = [
        normalized_root
        for normalized_root in normalized_support_roots
        if normalized_path == normalized_root or normalized_path.startswith(f"{normalized_root}/")
    ]
    if not matched_roots:
        return None
    return max(matched_roots, key=len)


def _repo_profile_candidate_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
) -> list[str]:
    probe_module = _probe_module()

    return probe_module._candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=[],
        bridge_paths=focus_paths,
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=min(max_files, 512),
    )


def _repo_profile_config_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
) -> list[str]:
    probe_module = _probe_module()
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    repository_service = probe_module.repository_service
    _cached_git_repo_relative_files = collection_support._cached_git_repo_relative_files
    _git_repo_relative_files = probe_module._git_repo_relative_files
    _git_repo_relative_files_for_focus_paths = probe_module._git_repo_relative_files_for_focus_paths
    _is_cfml_box_config_path = probe_module._is_cfml_box_config_path
    _is_cue_module_config_path = probe_module._is_cue_module_config_path
    _is_dm_project_config_path = probe_module._is_dm_project_config_path
    _is_eiffel_project_config_path = probe_module._is_eiffel_project_config_path
    _is_moonbit_config_path = probe_module._is_moonbit_config_path
    _is_odin_ols_config_path = probe_module._is_odin_ols_config_path
    _is_purescript_bower_config_path = probe_module._is_purescript_bower_config_path
    _is_puppet_metadata_config_path = probe_module._is_puppet_metadata_config_path
    _is_qmake_project_config_path = probe_module._is_qmake_project_config_path
    _is_repo_profile_manifest_name = probe_module._is_repo_profile_manifest_name
    _is_rescript_config_path = probe_module._is_rescript_config_path
    _is_xpp_descriptor_config_path = probe_module._is_xpp_descriptor_config_path
    _probe_collection_rank = probe_module._probe_collection_rank

    excluded_dirnames = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
    config_paths: set[str] = set()
    manifest_basenames = {
        str(name).lower() for name in probe_module._REPO_PROFILE_MANIFEST_BASENAMES
    }
    manifest_basenames.add("pkgindex.tcl")
    manifest_suffixes = (
        ".cabal",
        ".gemspec",
        ".podspec",
        ".rockspec",
        ".nimble",
        ".opam",
        ".core",
        ".mlb",
        ".cm",
        ".app.src",
        ".sbt",
        ".csproj",
        ".fsproj",
        ".vbproj",
        ".hxml",
        ".ipkg",
        ".vbp",
        ".yyp",
        ".wsf",
        ".asd",
        ".lvproj",
        ".lvlib",
        ".lvclass",
        ".gpr",
        ".dproj",
        ".lpi",
        ".lpk",
        ".sln",
        ".sqlproj",
        ".dbproj",
        ".psd1",
        ".mqproj",
        ".agda-lib",
        ".gms",
        ".scad",
    )
    rescript_config_basenames = repository_service.rescript_adapter.RESCRIPT_CONFIG_BASENAMES
    moonbit_config_basenames = repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES
    qmake_suffixes = repository_service.qmake_adapter.QMAKE_SUFFIXES
    qmake_config_basenames = repository_service.qmake_adapter.QMAKE_CONFIG_BASENAMES
    normalized_focus_paths = tuple(
        dict.fromkeys(
            normalized_focus_path
            for focus_path in focus_paths
            if (
                normalized_focus_path := repository_service._normalize_repository_relative_path(
                    focus_path
                )
            )
        )
    )
    cache_repo_key = _repo_cache_key(repo_path)
    cache_focus_key = tuple(sorted(normalized_focus_paths))
    cache_key = (cache_repo_key, cache_focus_key)
    cached_config_paths = _REPO_PROFILE_CONFIG_PATH_CACHE.get(cache_key)
    if cached_config_paths is not None:
        return list(cached_config_paths)

    def _matches_normalized_focus_paths(normalized_path: str) -> bool:
        if not normalized_focus_paths:
            return True
        for normalized_focus in normalized_focus_paths:
            if normalized_path == normalized_focus or normalized_path.startswith(
                f"{normalized_focus}/"
            ):
                return True
        return False

    def _focus_ancestor_directories() -> set[str]:
        focus_directories: set[str] = {"."}
        for normalized_focus_path in normalized_focus_paths:
            _path, _basename, _suffix, _stem, _parent_basename, parts = _normalized_path_components(
                normalized_focus_path
            )
            for index in range(1, len(parts) + 1):
                focus_directories.add("/".join(parts[:index]))
        return focus_directories

    focus_ancestor_directories = _focus_ancestor_directories()

    def _is_regular_non_symlink(candidate: Path) -> bool:
        try:
            candidate_stat = candidate.lstat()
        except OSError:
            return False
        return stat.S_ISREG(candidate_stat.st_mode) and not stat.S_ISLNK(candidate_stat.st_mode)

    def _config_path_relevant_to_focus(normalized_path: str) -> bool:
        if not normalized_focus_paths:
            return True
        if _matches_normalized_focus_paths(normalized_path):
            return True
        parent_path, _separator, _basename = normalized_path.rpartition("/")
        normalized_parent = parent_path or "."
        return normalized_parent in focus_ancestor_directories

    def _focus_ancestor_relative_files() -> list[str]:
        relative_paths: list[str] = []
        seen_relative_paths: set[str] = set()
        for focus_directory in sorted(focus_ancestor_directories):
            candidate_directory = repo_path if focus_directory == "." else repo_path / focus_directory
            try:
                with os.scandir(candidate_directory) as child_entries:
                    for child_entry in child_entries:
                        try:
                            if not child_entry.is_file(follow_symlinks=False):
                                continue
                        except OSError:
                            continue
                        relative_path = str(
                            Path(child_entry.path).relative_to(repo_path)
                        ).replace("\\", "/")
                        if relative_path in seen_relative_paths:
                            continue
                        seen_relative_paths.add(relative_path)
                        relative_paths.append(relative_path)
            except OSError:
                continue
        return relative_paths

    def _focus_ancestor_relative_files_from_listing(
        relative_paths: list[str],
    ) -> list[str]:
        matched_relative_paths: list[str] = []
        for relative_path in relative_paths:
            parent_path, _separator, _basename = relative_path.rpartition("/")
            normalized_parent = parent_path or "."
            if normalized_parent not in focus_ancestor_directories:
                continue
            matched_relative_paths.append(relative_path)
        return matched_relative_paths

    if normalized_focus_paths:
        unfocused_cache_key = (cache_repo_key, ())
        cached_unfocused_config_paths = _REPO_PROFILE_CONFIG_PATH_CACHE.get(unfocused_cache_key)
        if cached_unfocused_config_paths is not None:
            filtered_config_paths = tuple(
                config_path
                for config_path in cached_unfocused_config_paths
                if _config_path_relevant_to_focus(config_path)
            )
            if len(_REPO_PROFILE_CONFIG_PATH_CACHE) >= _REPO_PROFILE_CONFIG_PATH_CACHE_LIMIT:
                oldest_key = next(iter(_REPO_PROFILE_CONFIG_PATH_CACHE))
                _REPO_PROFILE_CONFIG_PATH_CACHE.pop(oldest_key, None)
            _REPO_PROFILE_CONFIG_PATH_CACHE[cache_key] = filtered_config_paths
            return list(filtered_config_paths)

    if normalized_focus_paths:
        git_relative_files = _git_repo_relative_files_for_focus_paths(
            repo_path,
            focus_paths=list(normalized_focus_paths),
        )
    else:
        git_relative_files = _git_repo_relative_files(repo_path)

    def _add_if_config(normalized_path: str) -> None:
        if not normalized_path:
            return
        path_parts = normalized_path.split("/")
        if any(part in excluded_dirnames for part in path_parts[:-1]):
            return
        parent_path, _separator, basename = normalized_path.rpartition("/")
        basename = basename.lower()
        suffix = f".{basename.rsplit('.', 1)[1]}" if "." in basename else ""
        parent_name = parent_path.rsplit("/", 1)[-1].lower() if parent_path else ""
        manifest_candidate = (
            basename in manifest_basenames
            or basename.endswith(manifest_suffixes)
            or (
                basename.endswith(".json")
                and (basename.startswith("tsconfig.") or basename.startswith("jsconfig."))
            )
        )
        is_manifest_name = (
            _is_repo_profile_manifest_name(basename) if manifest_candidate else False
        )
        if not (
            is_manifest_name
            or basename == "box.json"
            or suffix == ".dme"
            or (suffix == ".xml" and parent_name == "descriptor")
            or suffix in {".ecf", ".ace"}
            or basename == "ols.json"
            or (basename == "module.cue" and parent_name == "cue.mod")
            or basename == "bower.json"
            or basename in rescript_config_basenames
            or basename in moonbit_config_basenames
            or basename == "metadata.json"
            or suffix in qmake_suffixes
            or basename in qmake_config_basenames
        ):
            return
        if not _config_path_relevant_to_focus(normalized_path):
            return
        candidate = repo_path / normalized_path
        if not _is_regular_non_symlink(candidate):
            return
        is_config_path = is_manifest_name
        if not is_config_path and basename == "box.json":
            is_config_path = _is_cfml_box_config_path(repo_path, normalized_path)
        if not is_config_path and suffix == ".dme":
            is_config_path = _is_dm_project_config_path(repo_path, normalized_path)
        if not is_config_path and suffix == ".xml" and parent_name == "descriptor":
            is_config_path = _is_xpp_descriptor_config_path(repo_path, normalized_path)
        if not is_config_path and suffix in {".ecf", ".ace"}:
            is_config_path = _is_eiffel_project_config_path(repo_path, normalized_path)
        if not is_config_path and basename == "ols.json":
            is_config_path = _is_odin_ols_config_path(repo_path, normalized_path)
        if not is_config_path and basename == "module.cue" and parent_name == "cue.mod":
            is_config_path = _is_cue_module_config_path(repo_path, normalized_path)
        if not is_config_path and basename == "bower.json":
            is_config_path = _is_purescript_bower_config_path(repo_path, normalized_path)
        if not is_config_path and basename in rescript_config_basenames:
            is_config_path = _is_rescript_config_path(repo_path, normalized_path)
        if not is_config_path and basename in moonbit_config_basenames:
            is_config_path = _is_moonbit_config_path(repo_path, normalized_path)
        if not is_config_path and basename == "metadata.json":
            is_config_path = _is_puppet_metadata_config_path(repo_path, normalized_path)
        if not is_config_path and (
            suffix in qmake_suffixes or basename in qmake_config_basenames
        ):
            is_config_path = _is_qmake_project_config_path(repo_path, normalized_path)
        if not is_config_path:
            return
        config_paths.add(normalized_path)

    if git_relative_files is not None:
        for relative_path in git_relative_files:
            _add_if_config(relative_path)
        if normalized_focus_paths:
            has_cached_repo_relative_files, cached_repo_relative_files = (
                _cached_git_repo_relative_files(repo_path)
            )
            ancestor_relative_files = (
                _focus_ancestor_relative_files_from_listing(cached_repo_relative_files)
                if has_cached_repo_relative_files and cached_repo_relative_files is not None
                else _focus_ancestor_relative_files()
            )
            for relative_path in ancestor_relative_files:
                _add_if_config(relative_path)
    else:
        seen: set[Path] = set()
        for dirpath, dirnames, filenames in os.walk(repo_path):
            dirnames[:] = [name for name in dirnames if name not in excluded_dirnames]
            for filename in filenames:
                candidate = Path(dirpath) / filename
                if candidate in seen or not _is_regular_non_symlink(candidate):
                    continue
                seen.add(candidate)
                relative_path = str(candidate.relative_to(repo_path)).replace("\\", "/")
                _add_if_config(relative_path)

    ordered_config_paths = sorted(
        config_paths,
        key=lambda relative_path: _probe_collection_rank(relative_path, repo_path=repo_path),
    )
    final_config_paths = tuple(sorted(ordered_config_paths[:512]))
    if len(_REPO_PROFILE_CONFIG_PATH_CACHE) >= _REPO_PROFILE_CONFIG_PATH_CACHE_LIMIT:
        oldest_key = next(iter(_REPO_PROFILE_CONFIG_PATH_CACHE))
        _REPO_PROFILE_CONFIG_PATH_CACHE.pop(oldest_key, None)
    _REPO_PROFILE_CONFIG_PATH_CACHE[cache_key] = final_config_paths
    return list(final_config_paths)


def _seeded_repo_profile_candidate_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    max_files: int,
    entrypoint_candidates: set[str],
    support_root_candidates: set[str],
    config_paths: list[str],
    detected_ecosystems: set[str],
    detected_ecosystem_scores: Counter[str] | None = None,
) -> list[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _balanced_profile_paths = probe_module._balanced_profile_paths
    _candidate_existing_leaf_roots = probe_module._candidate_existing_leaf_roots
    _candidate_existing_paths = probe_module._candidate_existing_paths
    _is_non_operational_profile_path_for_ecosystems = (
        probe_module._is_non_operational_profile_path_for_ecosystems
    )
    _is_repo_profile_code_candidate = probe_module._is_repo_profile_code_candidate
    _profile_entrypoint_target_count = probe_module._profile_entrypoint_target_count
    _repo_profile_candidate_paths = probe_module._repo_profile_candidate_paths
    _should_use_seeded_profile_candidate_scan = (
        probe_module._should_use_seeded_profile_candidate_scan
    )

    existing_entrypoints = [
        path
        for path in _candidate_existing_paths(
            repo_path,
            paths=entrypoint_candidates,
        )
        if _is_repo_profile_code_candidate(path, repo_path=repo_path)
        and not repository_service._is_test_path(path)
        and not _is_non_operational_profile_path_for_ecosystems(
            path,
            ecosystems=detected_ecosystems,
            repo_path=repo_path,
        )
    ]
    existing_support_roots = _candidate_existing_leaf_roots(
        repo_path,
        roots=support_root_candidates,
        entrypoint_paths=set(existing_entrypoints),
    )
    bridge_roots = list(existing_support_roots)
    if not bridge_roots:
        config_parent_roots = {
            normalized_parent
            for config_path in config_paths
            if (
                normalized_parent := repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(config_path).parent)
                )
            )
        }
        bridge_roots = _candidate_existing_leaf_roots(
            repo_path,
            roots=config_parent_roots,
            entrypoint_paths=set(existing_entrypoints),
        )
    if not bridge_roots and not existing_entrypoints:
        return []
    support_roots = set(existing_support_roots or bridge_roots)
    seed_paths = _balanced_profile_paths(
        paths=existing_entrypoints,
        detected_ecosystems=detected_ecosystems,
        repo_path=repo_path,
        support_roots=support_roots,
        limit=_profile_entrypoint_target_count(detected_ecosystems),
        ecosystem_scores=detected_ecosystem_scores,
    )
    if not _should_use_seeded_profile_candidate_scan(
        seed_paths=seed_paths,
        bridge_paths=bridge_roots,
    ):
        return []
    seeded_candidate_paths = probe_module._candidate_repository_file_paths(
        repo_path=repo_path,
        seed_paths=seed_paths,
        bridge_paths=bridge_roots,
        include_patterns=probe_module.DEFAULT_INCLUDE_PATTERNS,
        max_files=min(max_files, 512),
    )
    if seeded_candidate_paths:
        return seeded_candidate_paths
    if seed_paths:
        return list(seed_paths)
    return _repo_profile_candidate_paths(
        repo_path=repo_path,
        focus_paths=focus_paths,
        max_files=max_files,
    )


def _is_repo_profile_code_candidate(
    path: str,
    *,
    repo_path: Path | None = None,
) -> bool:
    probe_module = _probe_module()
    from benchmarks import (
        repository_intelligence_real_repo_probe_profile_path_classification_support
        as classification_support,
    )
    _is_cfml_box_config_path = probe_module._is_cfml_box_config_path
    _is_cue_module_config_path = probe_module._is_cue_module_config_path
    _is_delphi_project_config_path = probe_module._is_delphi_project_config_path
    _is_dm_project_config_path = probe_module._is_dm_project_config_path
    _is_moonbit_config_path = probe_module._is_moonbit_config_path
    _is_purescript_bower_config_path = probe_module._is_purescript_bower_config_path
    _is_repo_profile_manifest_name = probe_module._is_repo_profile_manifest_name
    _is_rescript_config_path = probe_module._is_rescript_config_path
    _is_xpp_descriptor_config_path = probe_module._is_xpp_descriptor_config_path
    _candidate_ecosystems_for_path = probe_module._candidate_ecosystems_for_path

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    (
        _normalized_path_parts,
        basename,
        suffix,
        _stem,
        parent_basename,
        _parts,
    ) = _normalized_path_components(normalized_path)
    direct_language_hint = classification_support._direct_probe_language_hint(
        basename=basename,
        suffix=suffix,
    )
    cache_key = ("", normalized_path, None, None)
    if direct_language_hint is None and repo_path is not None:
        candidate_stat = classification_support._repo_file_stat(repo_path, normalized_path)
        if candidate_stat is not None:
            cache_key = (
                str(repo_path),
                normalized_path,
                candidate_stat.st_mtime_ns,
                candidate_stat.st_size,
            )
        else:
            cache_key = (str(repo_path), normalized_path, None, None)
    cached_result = _REPO_PROFILE_CODE_CANDIDATE_CACHE.get(cache_key)
    if cached_result is not None:
        return cached_result

    def _remember(result: bool) -> bool:
        if len(_REPO_PROFILE_CODE_CANDIDATE_CACHE) >= _REPO_PROFILE_CODE_CANDIDATE_CACHE_LIMIT:
            oldest_key = next(iter(_REPO_PROFILE_CODE_CANDIDATE_CACHE))
            _REPO_PROFILE_CODE_CANDIDATE_CACHE.pop(oldest_key, None)
        _REPO_PROFILE_CODE_CANDIDATE_CACHE[cache_key] = result
        return result

    if (
        repo_path is not None
        and suffix == ".xml"
        and parent_basename == "descriptor"
        and _is_xpp_descriptor_config_path(repo_path, normalized_path)
    ):
        return _remember(False)
    if repo_path is not None and basename == "box.json" and _is_cfml_box_config_path(
        repo_path,
        normalized_path,
    ):
        return _remember(False)
    if repo_path is not None and basename == "bower.json" and _is_purescript_bower_config_path(
        repo_path,
        normalized_path,
    ):
        return _remember(False)
    if (
        repo_path is not None
        and basename in _RESCRIPT_CONFIG_BASENAMES
        and _is_rescript_config_path(repo_path, normalized_path)
    ):
        return _remember(False)
    if (
        repo_path is not None
        and basename in _MOONBIT_CONFIG_BASENAMES
        and _is_moonbit_config_path(repo_path, normalized_path)
    ):
        return _remember(False)
    if (
        repo_path is not None
        and suffix == ".dproj"
        and _is_delphi_project_config_path(repo_path, normalized_path)
    ):
        return _remember(False)
    if (
        repo_path is not None
        and suffix == ".dme"
        and _is_dm_project_config_path(repo_path, normalized_path)
    ):
        return _remember(False)
    if (
        repo_path is not None
        and basename == "module.cue"
        and parent_basename == "cue.mod"
        and _is_cue_module_config_path(repo_path, normalized_path)
    ):
        return _remember(False)
    # ``candidate_ecosystems_for_path`` always re-derives its own static language hint and
    # ignores an injected ``language=`` whenever that static hint fires — which is exactly the
    # ``direct_language_hint is not None`` case here. Passing ``language=`` is therefore dead
    # weight, and it breaks callers that pass a narrower ``(path, repo_path=...)`` seam. Always
    # use the repo-context call so the static/content-aware resolution stays authoritative.
    matched_ecosystems = sort_repository_languages(
        _candidate_ecosystems_for_path(
            normalized_path,
            repo_path=repo_path,
        )
    )
    language = matched_ecosystems[0] if matched_ecosystems else "unknown"
    if _is_repo_profile_manifest_name(basename) and not (
        (language == "dhall" and basename == "package.dhall")
        or (language == "dockerfile" and basename in {"dockerfile", "containerfile"})
        or (language == "gams" and suffix == ".gms")
        or (language == "openscad" and suffix == ".scad")
        or (language == "nix" and suffix == ".nix")
        or (language == "v" and basename == "v.mod")
        or (language == "vbscript" and suffix == ".wsf")
        or (language == "labview" and suffix in {".lvclass", ".lvlib"})
        or (
            language == "starlark"
            and basename
            in {"build", "build.bazel", "module.bazel", "workspace", "workspace.bazel"}
        )
    ):
        return _remember(False)
    return _remember(
        suffix != ".hrl"
        and language not in _NON_CODE_GRAPH_LANGUAGES
        and language not in _ENTRYPOINT_DEMOTED_LANGUAGES
        and language not in {"unknown", "txt"}
    )


def _cuda_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_qmake_project_config_path = probe_module._is_qmake_project_config_path
    _is_repo_profile_manifest_name = probe_module._is_repo_profile_manifest_name

    cuda_files = sorted(
        {
            normalized_path
            for candidate_path in candidate_file_paths
            if (
                normalized_path := repository_service._normalize_repository_relative_path(
                    candidate_path
                )
            )
            and PurePosixPath(normalized_path).suffix.lower() in {".cu", ".cuh"}
        }
    )
    if not cuda_files:
        return set(), set(), set()
    entrypoint_paths = {
        path
        for path in cuda_files
        if PurePosixPath(path).suffix.lower() == ".cu"
        and not repository_service._is_test_path(path)
        and not _is_non_operational_profile_path(path)
    }
    prioritized_entrypoints = {
        path
        for path in entrypoint_paths
        if PurePosixPath(path).name.lower()
        in {"app.cu", "example.cu", "index.cu", "main.cu", "sample.cu"}
        or "main" in PurePosixPath(path).stem.lower()
    }
    if prioritized_entrypoints:
        entrypoint_paths = prioritized_entrypoints
    if not entrypoint_paths:
        entrypoint_paths = {
            path
            for path in cuda_files
            if PurePosixPath(path).suffix.lower() == ".cu"
            and not repository_service._is_test_path(path)
        }
    support_roots = {
        repository_service._normalize_repository_relative_path(str(PurePosixPath(path).parent))
        for path in cuda_files
    }
    support_roots.update(
        repository_service._normalize_repository_relative_path(str(PurePosixPath(path).parts[0]))
        for path in cuda_files
        if PurePosixPath(path).parts
    )
    config_paths: set[str] = set()
    candidate_config_dirs: set[str] = set()
    for entrypoint_path in entrypoint_paths:
        parent = PurePosixPath(entrypoint_path).parent
        for candidate_dir in (parent, parent.parent):
            normalized_dir = repository_service._normalize_repository_relative_path(
                str(candidate_dir)
            )
            if normalized_dir:
                candidate_config_dirs.add(normalized_dir)
    for normalized_dir in sorted(candidate_config_dirs):
        directory = repo_path / normalized_dir
        if not directory.is_dir():
            continue
        try:
            child_paths = sorted(directory.iterdir(), key=lambda path: path.name.lower())
        except OSError:
            continue
        for child_path in child_paths:
            if not child_path.is_file() or child_path.is_symlink():
                continue
            child_name = child_path.name
            if not (
                _is_repo_profile_manifest_name(child_name)
                or _is_qmake_project_config_path(
                    repo_path,
                    repository_service._normalize_repository_relative_path(
                        str(child_path.relative_to(repo_path))
                    )
                    or "",
                )
            ):
                continue
            normalized_child = repository_service._normalize_repository_relative_path(
                str(child_path.relative_to(repo_path))
            )
            if normalized_child:
                config_paths.add(normalized_child)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _accumulate_detected_ecosystem_scores(
    scores: Counter[str],
    *,
    ecosystems: set[str],
    config_path: str,
    repo_path: Path | None = None,
    entrypoints: set[str],
    roots: set[str],
    configs: set[str],
    preferred_ecosystems: set[str] | None = None,
) -> None:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path_for_ecosystems = (
        probe_module._is_non_operational_profile_path_for_ecosystems
    )
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _profile_signal_depth_score = probe_module._profile_signal_depth_score

    canonical_ecosystems = {
        canonical_repository_language(ecosystem)
        for ecosystem in ecosystems
        if canonical_repository_language(ecosystem)
    }
    if not canonical_ecosystems or _is_non_operational_profile_path_for_ecosystems(
        config_path,
        ecosystems=canonical_ecosystems,
        repo_path=repo_path,
    ):
        return

    def _is_operational_entrypoint(path: str) -> bool:
        return bool(
            path
            and not repository_service._is_test_path(path)
            and not _is_non_operational_profile_path_for_ecosystems(
                path,
                ecosystems=canonical_ecosystems,
                repo_path=repo_path,
            )
            and _is_operational_profile_entrypoint_candidate(path, repo_path=repo_path)
        )

    def _is_operational_root(root: str) -> bool:
        normalized_root = repository_service._normalize_repository_relative_path(root)
        return bool(
            normalized_root
            and not _is_non_operational_profile_path_for_ecosystems(
                normalized_root,
                ecosystems=canonical_ecosystems,
                repo_path=repo_path,
            )
        )

    operational_entrypoint_count = _count_capped_matching_values(
        entrypoints,
        limit=8,
        predicate=_is_operational_entrypoint,
    )
    operational_root_count = _count_capped_matching_values(
        roots,
        limit=8,
        predicate=_is_operational_root,
    )
    signal_score = (
        _profile_signal_depth_score(config_path) * 4
        + operational_entrypoint_count * 5
        + operational_root_count * 3
        + min(len(configs), 4)
    )
    if signal_score <= 0:
        return
    for ecosystem in canonical_ecosystems:
        scores[ecosystem] += signal_score
    if preferred_ecosystems:
        preferred_canonical = {
            canonical_repository_language(ecosystem)
            for ecosystem in preferred_ecosystems
            if canonical_repository_language(ecosystem) in canonical_ecosystems
        }
        for ecosystem in preferred_canonical:
            scores[ecosystem] += max(1, signal_score // 4)


def _count_capped_matching_values(
    values: Iterable[str],
    *,
    limit: int,
    predicate: Callable[[str], bool],
) -> int:
    if limit <= 0:
        return 0
    match_count = 0
    for value in values:
        if not predicate(value):
            continue
        match_count += 1
        if match_count >= limit:
            return limit
    return match_count


def _normalized_package_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _ruby_package_names_for_profile(
    *,
    repo_path: Path,
    normalized_path: str,
) -> tuple[str, ...]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    package_names: set[str] = set()
    basename = PurePosixPath(normalized_path).name
    if basename.lower().endswith(".gemspec"):
        package_names.add(PurePosixPath(basename).stem)
    repo_name = re.sub(r"[^a-z0-9_]+", "_", repo_path.name.lower()).strip("_")
    if repo_name:
        package_names.add(repo_name)
    try:
        text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text:
        for match in re.finditer(r"""\.name\s*=\s*["'](?P<name>[^"']+)["']""", text):
            raw_name = match.group("name").strip()
            if raw_name:
                package_names.add(raw_name)
    return tuple(sorted(name for name in package_names if name.strip()))


def _ruby_package_entrypoint_paths(
    *,
    repo_path: Path,
    project_dir: PurePosixPath,
    package_names: tuple[str, ...],
) -> set[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _normalized_package_identifier = probe_module._normalized_package_identifier

    entrypoint_paths: set[str] = set()
    if not package_names:
        return entrypoint_paths
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    normalized_package_ids = {
        _normalized_package_identifier(package_name)
        for package_name in package_names
        if package_name.strip()
    }
    for package_name in package_names:
        if not package_name.strip():
            continue
        normalized_package_name = package_name.strip().replace("-", "_")
        entrypoint_paths.update(
            {
                f"{root_prefix}bin/{normalized_package_name}",
                f"{root_prefix}exe/{normalized_package_name}",
                f"{root_prefix}lib/{normalized_package_name}.rb",
            }
        )
    lib_dir = repo_path / project_dir / "lib"
    if lib_dir.is_dir():
        try:
            ruby_candidates = sorted(lib_dir.glob("*.rb"))
        except OSError:
            ruby_candidates = []
        for candidate in ruby_candidates:
            normalized_stem = _normalized_package_identifier(candidate.stem)
            if not normalized_stem or normalized_stem not in normalized_package_ids:
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if relative_path:
                entrypoint_paths.add(relative_path)
    return entrypoint_paths


def _balanced_profile_paths(
    *,
    paths: list[str],
    detected_ecosystems: set[str],
    repo_path: Path | None = None,
    support_roots: set[str],
    limit: int,
    ecosystem_scores: Counter[str] | None = None,
) -> list[str]:
    probe_module = _probe_module()
    _candidate_ecosystems_for_path = probe_module._candidate_ecosystems_for_path
    _diversify_paths_by_support_root = probe_module._diversify_paths_by_support_root
    _ordered_operational_ecosystems = probe_module._ordered_operational_ecosystems
    _rank_repo_profile_seed_path = probe_module._rank_repo_profile_seed_path

    if limit <= 0:
        return []
    ranked_paths = sorted(
        dict.fromkeys(path for path in paths if path),
        key=lambda candidate_path: _rank_repo_profile_seed_path(
            candidate_path,
            repo_path=repo_path,
            support_roots=support_roots,
        ),
    )
    ranked_paths = _diversify_paths_by_support_root(
        paths=ranked_paths,
        support_roots=support_roots,
    )
    if len(ranked_paths) <= limit or len(detected_ecosystems) <= 1:
        return ranked_paths[:limit]
    bucket_order = _ordered_operational_ecosystems(
        detected_ecosystems,
        ecosystem_scores=ecosystem_scores,
    )
    buckets: dict[str, list[str]] = {ecosystem: [] for ecosystem in bucket_order}
    overflow_paths: list[str] = []
    for candidate_path in ranked_paths:
        matched_ecosystems = [
            ecosystem
            for ecosystem in bucket_order
            if ecosystem in _candidate_ecosystems_for_path(candidate_path, repo_path=repo_path)
        ]
        if matched_ecosystems:
            buckets[matched_ecosystems[0]].append(candidate_path)
            continue
        overflow_paths.append(candidate_path)
    for ecosystem in bucket_order:
        buckets[ecosystem] = _diversify_paths_by_support_root(
            paths=buckets[ecosystem],
            support_roots=support_roots,
        )
    selected_paths: list[str] = []
    seen_paths: set[str] = set()
    while len(selected_paths) < limit:
        progress = False
        for ecosystem in bucket_order:
            bucket = buckets[ecosystem]
            while bucket:
                candidate_path = bucket.pop(0)
                if candidate_path in seen_paths:
                    continue
                seen_paths.add(candidate_path)
                selected_paths.append(candidate_path)
                progress = True
                if len(selected_paths) >= limit:
                    return selected_paths
                break
        if not progress:
            break
    for candidate_path in overflow_paths + ranked_paths:
        if candidate_path in seen_paths:
            continue
        seen_paths.add(candidate_path)
        selected_paths.append(candidate_path)
        if len(selected_paths) >= limit:
            break
    return selected_paths[:limit]


def _leaf_support_roots(support_roots: set[str]) -> set[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_roots = {
        normalized_root
        for root in support_roots
        if (normalized_root := repository_service._normalize_repository_relative_path(root))
    }
    if not normalized_roots:
        return set()
    ordered_roots = sorted(normalized_roots)
    leaf_roots: set[str] = set()
    for index, root in enumerate(ordered_roots):
        next_root = ordered_roots[index + 1] if index + 1 < len(ordered_roots) else None
        if next_root is not None and next_root.startswith(f"{root}/"):
            continue
        leaf_roots.add(root)
    return leaf_roots or normalized_roots


def _best_matching_support_root(path: str, *, support_roots: set[str]) -> str | None:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _normalized_scannable_support_roots = probe_module._normalized_scannable_support_roots

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return None
    cache_key = _best_matching_support_root_cache_key(
        normalized_path,
        support_roots=support_roots,
    )
    if cache_key in _BEST_MATCHING_SUPPORT_ROOT_CACHE:
        return _BEST_MATCHING_SUPPORT_ROOT_CACHE[cache_key]
    matched_root = _best_matching_support_root_uncached(
        normalized_path,
        normalized_support_roots=_normalized_scannable_support_roots(support_roots),
    )
    if len(_BEST_MATCHING_SUPPORT_ROOT_CACHE) >= _BEST_MATCHING_SUPPORT_ROOT_CACHE_LIMIT:
        oldest_key = next(iter(_BEST_MATCHING_SUPPORT_ROOT_CACHE))
        _BEST_MATCHING_SUPPORT_ROOT_CACHE.pop(oldest_key, None)
    _BEST_MATCHING_SUPPORT_ROOT_CACHE[cache_key] = matched_root
    return matched_root


def _diversify_paths_by_support_root(
    *,
    paths: list[str],
    support_roots: set[str],
) -> list[str]:
    probe_module = _probe_module()
    _best_matching_support_root = probe_module._best_matching_support_root

    if not paths or not support_roots:
        return list(paths)
    root_buckets: dict[str, list[str]] = {}
    bucket_order: list[str] = []
    overflow_paths: list[str] = []
    for candidate_path in paths:
        matched_root = _best_matching_support_root(
            candidate_path,
            support_roots=support_roots,
        )
        if matched_root is None:
            overflow_paths.append(candidate_path)
            continue
        if matched_root not in root_buckets:
            root_buckets[matched_root] = []
            bucket_order.append(matched_root)
        root_buckets[matched_root].append(candidate_path)
    ordered_paths: list[str] = []
    while True:
        progress = False
        for root in bucket_order:
            bucket = root_buckets[root]
            if not bucket:
                continue
            ordered_paths.append(bucket.pop(0))
            progress = True
        if not progress:
            break
    ordered_paths.extend(overflow_paths)
    return ordered_paths


def _path_within_support_roots(path: str, *, support_roots: set[str]) -> bool:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return False
    # A bare repo-root support root ("." / "") otherwise matches every path, neutralizing
    # support-root scoping. When narrower declared roots coexist, the repo-root should only
    # cover root-level (depth-0) files, so passive sibling dirs (e.g. an ``app/`` root pulled
    # in by a passive package.json next to a ``src``-scoped manifest) are not swept in.
    narrower_roots = {
        root for root in support_roots if str(root).strip().strip("./") != ""
    }
    for root in support_roots:
        if str(root).strip().strip("./") == "":
            if narrower_roots:
                if "/" not in normalized_path:
                    return True
                continue
            return True
        normalized_root = repository_service._normalize_repository_relative_path(root)
        if not normalized_root:
            continue
        if normalized_path == normalized_root or normalized_path.startswith(f"{normalized_root}/"):
            return True
    return False


def _support_roots_requiring_expansion(
    *,
    candidate_file_paths: list[str],
    support_roots: list[str] | set[str],
) -> list[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _normalized_scannable_support_roots = probe_module._normalized_scannable_support_roots

    normalized_support_roots = _normalized_scannable_support_roots(support_roots)
    if not normalized_support_roots:
        return []
    match_order = sorted(
        normalized_support_roots,
        key=lambda path: (-len(path), path),
    )
    covered_roots: set[str] = set()
    for candidate_path in candidate_file_paths:
        normalized_candidate_path = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate_path:
            continue
        matched_root = next(
            (
                root
                for root in match_order
                if normalized_candidate_path == root
                or normalized_candidate_path.startswith(f"{root}/")
            ),
            None,
        )
        if matched_root is None:
            continue
        covered_roots.add(matched_root)
        if len(covered_roots) == len(normalized_support_roots):
            return []
    return sorted(root for root in normalized_support_roots if root not in covered_roots)


def _support_roots_need_expansion(
    *,
    candidate_file_paths: list[str],
    support_roots: list[str] | set[str],
) -> bool:
    probe_module = _probe_module()

    return bool(
        probe_module._support_roots_requiring_expansion(
            candidate_file_paths=candidate_file_paths,
            support_roots=support_roots,
        )
    )


def _scala_support_root_from_candidate_path(path: str) -> str | None:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path

    normalized_path = repository_service._normalize_repository_relative_path(path)
    if not normalized_path:
        return None
    if repository_service._language_for_path(Path(normalized_path)) != "scala":
        return None
    if repository_service._is_test_path(normalized_path) or _is_non_operational_profile_path(
        normalized_path
    ):
        return None
    parts = list(PurePosixPath(normalized_path).parts)
    if "src" not in parts:
        return None
    src_index = parts.index("src")
    intermediate_parts = parts[src_index + 1 : -1]
    if not intermediate_parts:
        return "/".join(parts[: src_index + 1])
    first_part = intermediate_parts[0].lower()
    if first_part in {"main", "shared"} and len(intermediate_parts) >= 2:
        second_part = intermediate_parts[1].lower()
        if second_part == "java" or second_part.startswith("scala"):
            return "/".join(parts[: src_index + 3])
    if first_part == "java" or first_part.startswith("scala"):
        return "/".join(parts[: src_index + 2])
    if first_part in {"test", "tests", "it"}:
        return None
    return "/".join(parts[: src_index + 2])


def _scala_support_roots_from_candidates(candidate_file_paths: list[str]) -> set[str]:
    probe_module = _probe_module()
    _scala_support_root_from_candidate_path = probe_module._scala_support_root_from_candidate_path

    support_roots: set[str] = set()
    for candidate_path in candidate_file_paths:
        derived_root = _scala_support_root_from_candidate_path(candidate_path)
        if derived_root:
            support_roots.add(derived_root)
    return support_roots


def _profile_entrypoint_target_count(detected_ecosystems: set[str]) -> int:
    if detected_ecosystems & {
        "abap",
        "assembly",
        "clojure",
        "crystal",
        "cobol",
        "d",
        "php",
        "plsql",
        "foxpro",
        "prolog",
        "sas",
        "elixir",
        "fortran",
        "ruby",
        "swift",
        "dart",
        "dotnet",
        "erlang",
        "lisp",
        "gdscript",
        "gml",
        "java",
        "lua",
        "luau",
        "ocaml",
        "scala",
        "haskell",
        "fsharp",
        "groovy",
        "aspectj",
        "matlab",
        "sml",
        "objectivec",
        "perl",
        "powershell",
        "r",
        "rpg",
        "actionscript",
        "autohotkey",
        "autoit",
        "awk",
        "cfml",
        "elm",
        "haxe",
        "vimscript",
        "scratch",
        "julia",
        "agda",
        "apex",
        "wolfram",
        "vb6",
        "vbscript",
        "solidity",
        "systemverilog",
        "vhdl",
        "xpp",
        "tcl",
        "ladder",
        "labview",
    }:
        return 8
    if detected_ecosystems & {"c", "cpp"}:
        return 8
    if detected_ecosystems & {
        "ada",
        "node",
        "typescript",
        "python",
        "rust",
        "go",
        "zig",
        "nim",
    }:
        return 6
    return 4


def _prefer_non_text_control_profile_candidates(
    *,
    paths: list[str],
    repo_path: Path | None = None,
) -> list[str]:
    probe_module = _probe_module()
    _candidate_ecosystems_for_path = probe_module._candidate_ecosystems_for_path

    ordered_paths = list(dict.fromkeys(path for path in paths if path))
    if not ordered_paths:
        return []
    text_control_ecosystems = {"batchfile", "makefile"}
    non_text_control_paths = [
        path
        for path in ordered_paths
        if not (_candidate_ecosystems_for_path(path, repo_path=repo_path) & text_control_ecosystems)
    ]
    return non_text_control_paths or ordered_paths


def _expand_profile_entrypoints(
    *,
    ranked_candidates: list[str],
    repo_path: Path,
    support_roots: list[str],
    existing_entrypoints: list[str],
    detected_ecosystems: set[str],
    ecosystem_scores: Counter[str] | None = None,
) -> list[str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _balanced_profile_paths = probe_module._balanced_profile_paths
    _candidate_ecosystems_for_path = probe_module._candidate_ecosystems_for_path
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _normalized_scannable_support_roots = probe_module._normalized_scannable_support_roots
    _path_within_support_roots = probe_module._path_within_support_roots
    _prefer_non_text_control_profile_candidates = (
        probe_module._prefer_non_text_control_profile_candidates
    )
    _profile_entrypoint_target_count = probe_module._profile_entrypoint_target_count

    target_count = _profile_entrypoint_target_count(detected_ecosystems)
    normalized_support_roots = _normalized_scannable_support_roots(support_roots)
    sanitized_existing_entrypoints = [
        normalized_path
        for candidate_path in existing_entrypoints
        if (
            normalized_path := repository_service._normalize_repository_relative_path(
                candidate_path
            )
        )
        and _is_operational_profile_entrypoint_candidate(
            normalized_path,
            repo_path=repo_path,
        )
    ]
    sanitized_existing_entrypoints = _prefer_non_text_control_profile_candidates(
        paths=sanitized_existing_entrypoints,
        repo_path=repo_path,
    )
    qualifying_candidates: list[str] = []
    for candidate_path in ranked_candidates:
        normalized_candidate_path = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate_path:
            continue
        if not _is_operational_profile_entrypoint_candidate(
            normalized_candidate_path,
            repo_path=repo_path,
        ):
            continue
        if normalized_support_roots and not _path_within_support_roots(
            normalized_candidate_path,
            support_roots=normalized_support_roots,
        ):
            continue
        qualifying_candidates.append(normalized_candidate_path)
    qualifying_candidates = _prefer_non_text_control_profile_candidates(
        paths=qualifying_candidates,
        repo_path=repo_path,
    )
    balance_ecosystems = (
        {
            ecosystem
            for candidate_path in sanitized_existing_entrypoints
            for ecosystem in _candidate_ecosystems_for_path(
                candidate_path,
                repo_path=repo_path,
            )
        }
        or detected_ecosystems
    )
    selected_entrypoints = _balanced_profile_paths(
        paths=sanitized_existing_entrypoints,
        detected_ecosystems=balance_ecosystems,
        repo_path=repo_path,
        support_roots=normalized_support_roots,
        limit=target_count,
        ecosystem_scores=ecosystem_scores,
    )
    if len(selected_entrypoints) >= target_count:
        return selected_entrypoints
    selected_path_set = set(selected_entrypoints)
    filled_candidates = _balanced_profile_paths(
        paths=[
            candidate_path
            for candidate_path in qualifying_candidates
            if candidate_path not in selected_path_set
        ],
        detected_ecosystems=detected_ecosystems,
        repo_path=repo_path,
        support_roots=normalized_support_roots,
        limit=target_count - len(selected_entrypoints),
        ecosystem_scores=ecosystem_scores,
    )
    return selected_entrypoints + filled_candidates
