from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from benchmarks.repository_intelligence_real_repo_probe_docs_support import (
    _asciidoc_profile_hints_from_candidates as _asciidoc_profile_hints_from_candidates_support,
    _org_profile_hints_from_candidates as _org_profile_hints_from_candidates_support,
    _rst_profile_hints_from_candidates as _rst_profile_hints_from_candidates_support,
    _tex_profile_hints_from_candidates as _tex_profile_hints_from_candidates_support,
    _typst_profile_hints_from_candidates as _typst_profile_hints_from_candidates_support,
)


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


class _DeferredProbeAttr:
    def __init__(self, name: str) -> None:
        self._name = name

    def _resolve(self):
        return getattr(_probe_module(), self._name)

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, attr: str):
        return getattr(self._resolve(), attr)


repository_service = _DeferredProbeAttr("repository_service")
_is_non_operational_profile_path = _DeferredProbeAttr("_is_non_operational_profile_path")
_is_non_operational_profile_path_for_ecosystems = _DeferredProbeAttr(
    "_is_non_operational_profile_path_for_ecosystems"
)
_probe_language_for_path = _DeferredProbeAttr("_probe_language_for_path")


def _iter_repository_relative_files(
    *,
    repo_path: Path,
    root_path: Path | None = None,
    relative_prefix: str = "",
) -> Iterator[str]:
    walk_root = repo_path if root_path is None else root_path
    if not walk_root.is_dir():
        return
    normalized_prefix = repository_service._normalize_repository_relative_path(relative_prefix)
    prefix_parts = () if not normalized_prefix else PurePosixPath(normalized_prefix).parts
    for current_root, dir_names, file_names in os.walk(walk_root, topdown=True, followlinks=False):
        current_root_path = Path(current_root)
        dir_names[:] = sorted(
            dir_name
            for dir_name in dir_names
            if not (current_root_path / dir_name).is_symlink()
        )
        file_names.sort()
        try:
            relative_dir = current_root_path.relative_to(walk_root)
        except ValueError:
            continue
        relative_dir_parts = tuple(PurePosixPath(*relative_dir.parts).parts)
        for file_name in file_names:
            candidate_file = current_root_path / file_name
            if candidate_file.is_symlink() or not candidate_file.is_file():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(*prefix_parts, *relative_dir_parts, file_name))
            )
            if relative_path:
                yield relative_path


def _robotframework_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    robot_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_basenames = {
        "resource.robot",
        "common.resource",
        "keywords.resource",
        "variables.resource",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path)
            != "robotframework"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.robotframework_adapter.is_probable_robotframework_source(
            path=candidate_file, text=text
        ):
            continue
        robot_files.append(normalized_candidate)
        for alias in repository_service.robotframework_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in robot_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.robotframework_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in robot_files:
        path = PurePosixPath(normalized_candidate)
        if (
            path.suffix.lower() != ".robot"
            or normalized_candidate in imported_files
            or path.name.lower() in support_basenames
        ):
            continue
        entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            sorted(path for path in robot_files if PurePosixPath(path).suffix.lower() == ".robot")
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _typst_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    return _typst_profile_hints_from_candidates_support(repo_path, candidate_file_paths)


def _tex_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    return _tex_profile_hints_from_candidates_support(repo_path, candidate_file_paths)


def _rst_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    return _rst_profile_hints_from_candidates_support(repo_path, candidate_file_paths)


def _asciidoc_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    return _asciidoc_profile_hints_from_candidates_support(repo_path, candidate_file_paths)


def _org_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    return _org_profile_hints_from_candidates_support(repo_path, candidate_file_paths)


def _gherkin_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    gherkin_files: list[str] = []
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {
        "index.feature",
        "login.feature",
        "readme.feature",
    }
    support_dirs = {"acceptance", "bdd", "feature", "features", "spec", "specs"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"gherkin"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "gherkin"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.gherkin_adapter.is_probable_gherkin_source(
            path=candidate_file,
            text=text,
        ):
            continue
        gherkin_files.append(normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if PurePosixPath(normalized_candidate).name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(gherkin_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _antlr_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    antlr_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    preferred_basenames = {"grammar.g4", "index.g4", "lexer.g4", "parser.g4"}
    support_dirs = {
        "antlr",
        "antlr4",
        "grammar",
        "grammars",
        "lexer",
        "lexers",
        "parser",
        "parsers",
        "syntax",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"antlr"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "antlr"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.antlr_adapter.is_probable_antlr_source(
            path=candidate_file,
            text=text,
        ):
            continue
        antlr_files.append(normalized_candidate)
        for alias in repository_service.antlr_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in antlr_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.antlr_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in antlr_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(antlr_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _supplement_candidate_file_paths_for_suffix_roots(
    *,
    repo_path: Path,
    candidate_file_paths: list[str],
    suffixes: set[str],
    root_names: tuple[str, ...],
    max_extra_files: int,
) -> list[str]:
    normalized_suffixes = {suffix.lower() for suffix in suffixes}
    merged_paths = list(dict.fromkeys(candidate_file_paths))
    seen_paths = set(merged_paths)
    extra_files = 0
    for root_name in root_names:
        normalized_root = repository_service._normalize_repository_relative_path(root_name)
        if not normalized_root:
            continue
        root_path = repo_path / normalized_root
        for relative_path in _iter_repository_relative_files(
            repo_path=repo_path,
            root_path=root_path,
            relative_prefix=normalized_root,
        ):
            if extra_files >= max_extra_files:
                return merged_paths
            if (
                not relative_path
                or relative_path in seen_paths
                or repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
                or PurePosixPath(relative_path).suffix.lower() not in normalized_suffixes
            ):
                continue
            merged_paths.append(relative_path)
            seen_paths.add(relative_path)
            extra_files += 1
    return merged_paths


def _supplement_candidate_file_paths_for_surface_dir_parts(
    *,
    repo_path: Path,
    candidate_file_paths: list[str],
    suffixes: set[str],
    directory_parts: set[str],
    max_extra_files: int,
) -> list[str]:
    normalized_suffixes = {suffix.lower() for suffix in suffixes if suffix}
    normalized_directory_parts = {part.lower() for part in directory_parts if part}
    if not normalized_suffixes or not normalized_directory_parts or max_extra_files <= 0:
        return list(dict.fromkeys(candidate_file_paths))
    merged_paths = list(dict.fromkeys(candidate_file_paths))
    seen_paths = set(merged_paths)
    extra_files = 0
    for relative_path in _iter_repository_relative_files(repo_path=repo_path):
        if extra_files >= max_extra_files:
            break
        if not relative_path or relative_path in seen_paths:
            continue
        pure_path = PurePosixPath(relative_path)
        if pure_path.suffix.lower() not in normalized_suffixes:
            continue
        if repository_service._is_test_path(relative_path) or _is_non_operational_profile_path(
            relative_path
        ):
            continue
        if not ({part.lower() for part in pure_path.parts[:-1]} & normalized_directory_parts):
            continue
        merged_paths.append(relative_path)
        seen_paths.add(relative_path)
        extra_files += 1
    return merged_paths


def _move_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    move_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {"main.move", "lib.move", "script.move"}
    support_dirs = {"contracts", "examples", "move", "script", "scripts", "source", "sources"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate or repository_service._is_test_path(normalized_candidate):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if candidate_file.name.lower() in repository_service.move_adapter.MOVE_CONFIG_BASENAMES:
            if repository_service.move_adapter.is_probable_move_config(
                path=candidate_file,
                text=text,
            ):
                config_paths.add(normalized_candidate)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(normalized_candidate).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
            continue
        if (
            _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"move"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "move"
            or not repository_service.move_adapter.is_probable_move_source(
                path=candidate_file,
                text=text,
            )
        ):
            continue
        move_files.append(normalized_candidate)
        for alias in repository_service.move_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in move_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.move_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(dependency.target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in move_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(move_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths
