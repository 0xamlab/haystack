from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

_ML_PROFILE_HINTS_CACHE_LIMIT = 4096
_ML_PROFILE_HINTS_CACHE: dict[
    tuple[str, str, int, int],
    tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]],
] = {}


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _repo_cache_key(repo_path: Path) -> str:
    from benchmarks import repository_intelligence_real_repo_probe_collection_support as collection_support

    return collection_support._repo_cache_key(repo_path)


def clear_ml_profile_hint_cache() -> None:
    _ML_PROFILE_HINTS_CACHE.clear()


def _remember_ml_profile_hints(
    cache_key: tuple[str, str, int, int],
    entrypoint_paths: set[str],
    support_roots: set[str],
    config_paths: set[str],
) -> tuple[set[str], set[str], set[str]]:
    if len(_ML_PROFILE_HINTS_CACHE) >= _ML_PROFILE_HINTS_CACHE_LIMIT:
        oldest_key = next(iter(_ML_PROFILE_HINTS_CACHE))
        _ML_PROFILE_HINTS_CACHE.pop(oldest_key, None)
    cached_result = (
        tuple(sorted(entrypoint_paths)),
        tuple(sorted(support_roots)),
        tuple(sorted(config_paths)),
    )
    _ML_PROFILE_HINTS_CACHE[cache_key] = cached_result
    cached_entrypoints, cached_roots, cached_configs = cached_result
    return set(cached_entrypoints), set(cached_roots), set(cached_configs)


def _elm_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    source_roots: list[str] = []
    raw_source_directories = payload.get("source-directories")
    if isinstance(raw_source_directories, list):
        for raw_source_root in raw_source_directories:
            if not isinstance(raw_source_root, str) or not raw_source_root.strip():
                continue
            resolved_path = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_source_root.strip())
            )
            if not resolved_path:
                continue
            absolute_path = repo_path / resolved_path
            if absolute_path.is_dir():
                support_roots.add(resolved_path)
                source_roots.append(resolved_path)
                continue
            if (
                absolute_path.is_file()
                and _probe_language_for_path(resolved_path, repo_path=repo_path) == "elm"
            ):
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(resolved_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
                    source_roots.append(parent_dir)
                if _is_operational_profile_entrypoint_candidate(
                    resolved_path,
                    repo_path=repo_path,
                ):
                    entrypoint_paths.add(resolved_path)

    if not source_roots:
        for fallback_dir in ("src", "app", "examples", "example"):
            candidate_dir = repository_service._normalize_repository_relative_path(
                str(project_dir / fallback_dir)
            )
            if candidate_dir and (repo_path / candidate_dir).is_dir():
                support_roots.add(candidate_dir)
                source_roots.append(candidate_dir)

    def _iter_module_names(value: Any) -> list[str]:
        if isinstance(value, str):
            normalized = value.strip()
            return [normalized] if normalized else []
        if isinstance(value, list):
            module_names: list[str] = []
            for item in value:
                module_names.extend(_iter_module_names(item))
            return module_names
        if isinstance(value, dict):
            module_names: list[str] = []
            for item in value.values():
                module_names.extend(_iter_module_names(item))
            return module_names
        return []

    for module_name in _iter_module_names(payload.get("exposed-modules")):
        module_relative_path = module_name.replace(".", "/") + ".elm"
        candidate_roots = source_roots or [
            repository_service._normalize_repository_relative_path(str(project_dir / "src"))
        ]
        for source_root in candidate_roots:
            normalized_root = repository_service._normalize_repository_relative_path(source_root)
            if not normalized_root:
                continue
            resolved_path = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(normalized_root) / module_relative_path)
            )
            if (
                not resolved_path
                or not (repo_path / resolved_path).is_file()
                or _probe_language_for_path(resolved_path, repo_path=repo_path) != "elm"
            ):
                continue
            support_roots.add(normalized_root)
            if _is_operational_profile_entrypoint_candidate(
                resolved_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(resolved_path)

    for source_root in source_roots:
        main_module_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(source_root) / "Main.elm")
        )
        if (
            not main_module_path
            or not (repo_path / main_module_path).is_file()
            or _probe_language_for_path(main_module_path, repo_path=repo_path) != "elm"
        ):
            continue
        if _is_operational_profile_entrypoint_candidate(
            main_module_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(main_module_path)

    if entrypoint_paths or not source_roots:
        return entrypoint_paths, support_roots, config_paths

    for source_root in source_roots:
        source_dir = repo_path / source_root
        if not source_dir.is_dir():
            continue
        for candidate in sorted(source_dir.rglob("*.elm")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and _is_operational_profile_entrypoint_candidate(
                    relative_path,
                    repo_path=repo_path,
                )
            ):
                entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _ocaml_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path

    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}bin",
        f"{root_prefix}app",
    }
    entrypoint_paths: set[str] = set()
    project_root = repo_path / project_dir
    search_roots: list[Path] = []
    config_name = PurePosixPath(normalized_path).name.lower()
    if config_name == "dune":
        search_roots.append(project_root)
    elif config_name == "dune-project":
        for dune_file in sorted(project_root.rglob("dune")):
            if not dune_file.is_file():
                continue
            relative_dune = repository_service._normalize_repository_relative_path(
                str(dune_file.relative_to(repo_path))
            )
            if not relative_dune or _is_non_operational_profile_path(relative_dune):
                continue
            search_roots.append(dune_file.parent)
            relative_root = repository_service._normalize_repository_relative_path(
                str(dune_file.parent.relative_to(repo_path))
            )
            if relative_root:
                support_roots.add(relative_root)
    else:
        search_roots.extend(project_root / subdir for subdir in ("src", "lib", "bin", "app"))
        search_roots.append(project_root)
    seen_roots: set[str] = set()
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        relative_root = repository_service._normalize_repository_relative_path(
            str(search_root.relative_to(repo_path))
        )
        if relative_root in seen_roots:
            continue
        seen_roots.add(relative_root or "")
        if relative_root:
            support_roots.add(relative_root)
        for extension in ("*.ml", "*.mli"):
            if config_name == "dune":
                iterator = search_root.glob(extension)
            else:
                iterator = search_root.rglob(extension)
            for candidate in sorted(iterator):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    relative_path
                    and not repository_service._is_test_path(relative_path)
                    and not _is_non_operational_profile_path(relative_path)
                ):
                    entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _ml_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    ml_manifest_path_re = probe_module._ML_MANIFEST_PATH_RE
    ml_source_extensions = probe_module._ML_SOURCE_EXTENSIONS
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_non_operational_project_path = probe_module._is_non_operational_project_path

    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    try:
        manifest_stat = manifest_path.stat()
    except OSError:
        manifest_stat = None
    cache_key = (
        _repo_cache_key(repo_path),
        normalized_path,
        int(manifest_stat.st_mtime_ns) if manifest_stat is not None else -1,
        int(manifest_stat.st_size) if manifest_stat is not None else -1,
    )
    cached_result = _ML_PROFILE_HINTS_CACHE.get(cache_key)
    if cached_result is not None:
        cached_entrypoints, cached_roots, cached_configs = cached_result
        return set(cached_entrypoints), set(cached_roots), set(cached_configs)
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}basis",
        f"{root_prefix}compiler",
    }
    entrypoint_paths = {
        f"{root_prefix}main.sml",
        f"{root_prefix}src/main.sml",
        f"{root_prefix}lib/main.sml",
    }
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _remember_ml_profile_hints(cache_key, entrypoint_paths, support_roots, config_paths)

    discovered_paths: list[str] = []
    for match in ml_manifest_path_re.finditer(text):
        raw_path = str(match.group("path") or "").strip()
        if not raw_path or raw_path.startswith(("$", "/")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_path)
        )
        if not resolved_path or resolved_path.startswith("/"):
            continue
        discovered_paths.append(resolved_path)

    if manifest_path.suffix.lower() == ".cm" and not discovered_paths:
        return _remember_ml_profile_hints(cache_key, set(), set(), set())

    for resolved_path in discovered_paths:
        if _is_non_operational_profile_path(resolved_path):
            continue
        suffix = PurePosixPath(resolved_path).suffix.lower()
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if suffix in {".mlb", ".cm"}:
            config_paths.add(resolved_path)
            if parent_dir:
                support_roots.add(parent_dir)
            continue
        if suffix not in ml_source_extensions or repository_service._is_test_path(resolved_path):
            continue
        if parent_dir:
            support_roots.add(parent_dir)
        entrypoint_paths.add(resolved_path)
    return _remember_ml_profile_hints(cache_key, entrypoint_paths, support_roots, config_paths)


def _classic_visual_basic_profile_hints(
    repo_path: Path,
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), set()
    if not repository_service.classic_visual_basic_adapter.is_probable_classic_visual_basic_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    config_paths = {normalized_path}
    entrypoint_paths: set[str] = set()
    form_paths: list[str] = []
    fallback_paths: list[str] = []
    startup_name = repository_service.classic_visual_basic_adapter.project_startup_name(
        text
    ).lower()
    for entry in repository_service.classic_visual_basic_adapter.project_component_entries(
        text,
        manifest_path=normalized_path,
    ):
        resolved_path = repository_service._normalize_repository_relative_path(str(entry["path"]))
        if not resolved_path or repository_service._is_test_path(resolved_path):
            continue
        if not (repo_path / resolved_path).is_file():
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        component_kind = str(entry["component_kind"]).lower()
        component_name = str(entry["component_name"]).lower()
        if startup_name and startup_name == component_name:
            entrypoint_paths.add(resolved_path)
            continue
        if component_kind in {"form", "mdiform"}:
            form_paths.append(resolved_path)
            continue
        if component_kind == "module" and startup_name in {"main", "sub main"}:
            entrypoint_paths.add(resolved_path)
            continue
        fallback_paths.append(resolved_path)
    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths
    if form_paths:
        entrypoint_paths.update(form_paths)
        return entrypoint_paths, support_roots, config_paths
    entrypoint_paths.update(fallback_paths)
    return entrypoint_paths, support_roots, config_paths


def _xpp_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_repo_profile_code_candidate = probe_module._is_repo_profile_code_candidate
    _is_xpp_descriptor_config_path = probe_module._is_xpp_descriptor_config_path

    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path or not _is_xpp_descriptor_config_path(repo_path, normalized_path):
        return set(), set(), set()
    descriptor_path = PurePosixPath(normalized_path)
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()

    module_container = descriptor_path.parent.parent
    model_name = descriptor_path.stem
    candidate_roots: list[PurePosixPath] = []
    if str(module_container) not in {"", "."}:
        support_roots.add(str(module_container))
        candidate_roots.append(module_container / model_name)
        candidate_roots.append(module_container)

    seen_roots: set[str] = set()
    ordered_roots: list[str] = []
    for candidate_root in candidate_roots:
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if (
            not normalized_root
            or normalized_root in seen_roots
            or not (repo_path / normalized_root).is_dir()
        ):
            continue
        seen_roots.add(normalized_root)
        ordered_roots.append(normalized_root)
        support_roots.add(normalized_root)

    for root in ordered_roots:
        root_path = repo_path / root
        for suffix in ("*.xml", "*.xpp", "*.xpo"):
            for candidate in sorted(root_path.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or not _is_repo_profile_code_candidate(relative_path, repo_path=repo_path)
                ):
                    continue
                entrypoint_paths.add(relative_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths


def _cfml_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_cfml_box_config_path = probe_module._is_cfml_box_config_path
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path or not _is_cfml_box_config_path(repo_path, normalized_path):
        return set(), set(), set()
    manifest_path = PurePosixPath(normalized_path)
    project_dir = manifest_path.parent
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()

    candidate_roots: list[str] = []
    for raw_root in (
        "",
        "api",
        "handlers",
        "models",
        "controllers",
        "views",
        "config",
        "modules",
        "modules_app",
        "public",
        "services",
        "src",
    ):
        resolved_root = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_root)
        )
        if not resolved_root or not (repo_path / resolved_root).is_dir():
            continue
        support_roots.add(resolved_root)
        candidate_roots.append(resolved_root)

    for raw_entrypoint in (
        "Application.cfc",
        "Application.cfm",
        "index.cfm",
        "public/Application.cfc",
        "public/index.cfm",
    ):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_entrypoint)
        )
        if (
            not resolved_path
            or not (repo_path / resolved_path).is_file()
            or repository_service._is_test_path(resolved_path)
            or _is_non_operational_profile_path(resolved_path)
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "cfml"
        ):
            continue
        entrypoint_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)

    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths

    scan_roots = candidate_roots or [
        repository_service._normalize_repository_relative_path(str(project_dir))
    ]
    for scan_root in scan_roots:
        if not scan_root:
            continue
        scan_root_path = repo_path / scan_root
        if not scan_root_path.is_dir():
            continue
        for suffix in ("*.cfc", "*.cfm", "*.cfml"):
            for candidate in sorted(scan_root_path.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or _probe_language_for_path(relative_path, repo_path=repo_path) != "cfml"
                ):
                    continue
                entrypoint_paths.add(relative_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths
