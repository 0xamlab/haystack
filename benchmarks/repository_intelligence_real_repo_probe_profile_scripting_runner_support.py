from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath


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

    def __iter__(self):
        return iter(self._resolve())

    def __contains__(self, item):
        return item in self._resolve()

    def __getitem__(self, key):
        return self._resolve()[key]

    def __len__(self) -> int:
        return len(self._resolve())

    def __bool__(self) -> bool:
        return bool(self._resolve())


repository_service = _DeferredProbeAttr("repository_service")
_is_non_operational_profile_path = _DeferredProbeAttr("_is_non_operational_profile_path")
_probe_language_for_path = _DeferredProbeAttr("_probe_language_for_path")


def _batchfile_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    entrypoint_dirs = {"bin", "cmd", "scripts", "tools"}
    support_dirs = entrypoint_dirs | {"build", "deploy", "install"}
    preferred_basenames = {
        "bootstrap.bat",
        "bootstrap.cmd",
        "build.bat",
        "build.cmd",
        "install.bat",
        "install.cmd",
        "main.bat",
        "main.cmd",
        "run.bat",
        "run.cmd",
        "setup.bat",
        "setup.cmd",
    }
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path)
            != "batchfile"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = lowered_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in preferred_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
            continue
        if not any(part in support_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _makefile_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    entrypoint_basenames = {"Makefile", "makefile", "GNUmakefile"}
    support_dirs = {"build", "config", "make", "mk", "rules", "scripts", "tools"}
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "makefile"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = candidate_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in entrypoint_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
            continue
        if not any(part in support_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _just_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    entrypoint_basenames = {"justfile", "Justfile", ".justfile"}
    support_dirs = {"build", "config", "just", "scripts", "tasks", "tools"}
    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "just"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        basename = candidate_parts[-1]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        if basename in entrypoint_basenames or len(candidate_parts) == 1:
            entrypoint_paths.add(normalized_candidate)
            continue
        if not any(part in support_dirs for part in lowered_parts[:-1]):
            entrypoint_paths.add(normalized_candidate)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _dockerfile_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    from benchmarks import (
        repository_intelligence_real_repo_probe_profile_path_classification_support
        as classification_support,
    )

    dockerfile_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    dependency_files: set[str] = set()
    support_dirs = {"build", "container", "containers", "docker", "images", "scripts", "tools"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        candidate_stat = classification_support._repo_file_stat(repo_path, normalized_candidate)
        candidate_lstat = classification_support._repo_file_lstat(repo_path, normalized_candidate)
        if (
            candidate_stat is not None
            and stat.S_ISREG(candidate_stat.st_mode)
            and not (
                candidate_lstat is not None and stat.S_ISLNK(candidate_lstat.st_mode)
            )
        ):
            module_index.setdefault(normalized_candidate, normalized_candidate)
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "dockerfile"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        candidate_stat = classification_support._repo_file_stat(repo_path, normalized_candidate)
        candidate_lstat = classification_support._repo_file_lstat(repo_path, normalized_candidate)
        if (
            candidate_stat is None
            or not stat.S_ISREG(candidate_stat.st_mode)
            or (candidate_lstat is not None and stat.S_ISLNK(candidate_lstat.st_mode))
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.dockerfile_adapter.is_probable_dockerfile_source(
            path=candidate_file,
            text=text,
        ):
            continue
        dockerfile_files.append(normalized_candidate)
        for alias in repository_service.dockerfile_adapter.module_aliases_for_path(
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
    for normalized_candidate in dockerfile_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.dockerfile_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            dependency_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in dockerfile_files:
        parent_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if (
            not any(part in support_dirs for part in parent_parts)
            or normalized_candidate in dependency_files
        ):
            entrypoint_paths.add(normalized_candidate)
            continue
        if PurePosixPath(normalized_candidate).name.lower() in {"dockerfile", "containerfile"}:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(dockerfile_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()
