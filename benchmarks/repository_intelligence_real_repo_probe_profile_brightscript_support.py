from __future__ import annotations

from pathlib import Path, PurePosixPath


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _probe_deps():
    probe_module = _probe_module()
    return (
        probe_module.repository_service,
        probe_module._is_non_operational_profile_path,
        probe_module._probe_language_for_path,
    )


def _nearest_brightscript_manifest_paths(repo_path: Path, normalized_path: str) -> set[str]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = _probe_deps()
    del _is_non_operational_profile_path, _probe_language_for_path
    config_paths: set[str] = set()
    current = PurePosixPath(normalized_path).parent
    while True:
        candidate_path = repository_service._normalize_repository_relative_path(str(current / "manifest"))
        if candidate_path and (repo_path / candidate_path).is_file():
            try:
                text = (repo_path / candidate_path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            if repository_service.brightscript_adapter.is_probable_brightscript_config(
                path=repo_path / candidate_path,
                text=text,
            ):
                config_paths.add(candidate_path)
        if str(current) in {"", "."}:
            break
        current = current.parent
    return config_paths


def _brightscript_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = _probe_deps()

    brightscript_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {"main.brs", "app.brs"}
    support_dirs = {"source", "sources", "component", "components", "task", "tasks"}
    library_like_parts = {"lib", "libs", "library", "libraries", "util", "utils"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "brightscript"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.brightscript_adapter.is_probable_brightscript_source(
            path=candidate_file,
            text=text,
        ):
            continue
        brightscript_files.append(normalized_candidate)
        config_paths.update(_nearest_brightscript_manifest_paths(repo_path, normalized_candidate))
        for alias in repository_service.brightscript_adapter.module_aliases_for_path(
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
    for normalized_candidate in brightscript_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.brightscript_adapter.parse_dependencies_only(
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
    for normalized_candidate in brightscript_files:
        path = PurePosixPath(normalized_candidate)
        lowered_parts = {part.lower() for part in path.parts[:-1]}
        if path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate in imported_files:
            continue
        if lowered_parts & library_like_parts:
            continue
        if lowered_parts & {"source", "components", "component", "tasks", "task"}:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(brightscript_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths
