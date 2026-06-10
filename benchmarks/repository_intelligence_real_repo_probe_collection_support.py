from __future__ import annotations

from pathlib import Path, PurePosixPath


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _git_repo_relative_files(repo_path: Path) -> list[str] | None:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    if not repository_service._is_git_repository(repo_path):
        return None
    commands = [
        ["git", "-C", str(repo_path), "ls-files"],
        ["git", "-C", str(repo_path), "ls-files", "--others", "--exclude-standard"],
    ]
    relative_paths: set[str] = set()
    for command in commands:
        output = str(repository_service._git_command(command, timeout=120.0))
        for line in output.splitlines():
            normalized = repository_service._normalize_repository_relative_path(line)
            if normalized:
                relative_paths.add(normalized)
    return sorted(relative_paths)


def _matches_focus_paths(relative_path: str, focus_paths: list[str]) -> bool:
    repository_service = _probe_module().repository_service

    if not focus_paths:
        return True
    for focus_path in focus_paths:
        normalized_focus = repository_service._normalize_repository_relative_path(focus_path)
        if not normalized_focus:
            continue
        if relative_path == normalized_focus or relative_path.startswith(f"{normalized_focus}/"):
            return True
    return False


def _probe_collection_rank(
    relative_path: str,
    *,
    repo_path: Path | None = None,
) -> tuple[int, int, int, int, str]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(relative_path)
    if not normalized_path:
        return (1, 1, 1, 1, relative_path)
    basename = PurePosixPath(normalized_path).name.lower()
    part_set = {part.lower() for part in PurePosixPath(normalized_path).parts}
    language = probe_module._probe_language_for_path(normalized_path, repo_path=repo_path)
    is_test = 1 if repository_service._is_test_path(normalized_path) else 0
    is_manifest = (
        0
        if probe_module._is_repo_profile_manifest_name(basename)
        or (
            repo_path is not None
            and probe_module._is_xpp_descriptor_config_path(repo_path, normalized_path)
        )
        or (
            repo_path is not None
            and probe_module._is_cfml_box_config_path(repo_path, normalized_path)
        )
        else 1
    )
    is_non_code = (
        1
        if language in repository_service._NON_CODE_GRAPH_LANGUAGES
        or language in {"unknown", "txt"}
        else 0
    )
    platform_noise = (
        1
        if (
            normalized_path.startswith(".github/")
            or normalized_path.startswith("docs/")
            or part_set & {"doc", "docs", "docs_src", "example", "examples", "sample", "samples"}
            or basename
            in {"readme.md", "changelog.md", "contributing.md", "license", "license.txt"}
        )
        else 0
    )
    template_surface_priority = (
        0
        if (
            language in probe_module._TEMPLATE_SURFACE_ECOSYSTEMS
            and part_set & probe_module._TEMPLATE_SURFACE_PARTS
        )
        else 1
    )
    return (
        is_test,
        min(is_non_code, is_manifest),
        template_surface_priority,
        platform_noise,
        normalized_path,
    )


def _candidate_existing_paths(
    repo_path: Path,
    *,
    paths: set[str],
) -> list[str]:
    repository_service = _probe_module().repository_service

    existing_paths: list[str] = []
    for raw_path in sorted(paths):
        normalized_path = repository_service._normalize_repository_relative_path(raw_path)
        if not normalized_path:
            continue
        candidate = repo_path / normalized_path
        if candidate.is_file():
            existing_paths.append(normalized_path)
    return existing_paths


def _candidate_existing_roots(
    repo_path: Path,
    *,
    roots: set[str],
) -> list[str]:
    repository_service = _probe_module().repository_service

    existing_roots: list[str] = []
    for raw_root in sorted(roots):
        normalized_root = repository_service._normalize_repository_relative_path(raw_root)
        if not normalized_root:
            continue
        candidate = repo_path / normalized_root
        if candidate.is_dir():
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
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_support_roots = {
        normalized_root
        for root in support_roots
        if (
            normalized_root := repository_service._normalize_repository_relative_path(root)
        )
    }
    if not normalized_support_roots:
        return set()
    leaf_support_roots = probe_module._leaf_support_roots(normalized_support_roots)
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
