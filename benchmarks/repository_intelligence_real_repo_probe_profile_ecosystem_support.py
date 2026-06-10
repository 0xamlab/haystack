from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _moonbit_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_manifest_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_manifest_path:
        return set(), set(), set()
    manifest_parent = PurePosixPath(normalized_manifest_path).parent
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    moonbit_files: list[str] = []
    config_paths: set[str] = {normalized_manifest_path}
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"pkg.generated.mbti"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or (root_prefix and not normalized_candidate.startswith(root_prefix))
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        basename = PurePosixPath(normalized_candidate).name.lower()
        if basename in repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES:
            if repository_service.moonbit_adapter.is_probable_moonbit_config(
                path=Path(normalized_candidate),
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
            _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "moonbit"
            or not repository_service.moonbit_adapter.is_probable_moonbit_source(
                path=Path(normalized_candidate),
                text=text,
            )
        ):
            continue
        moonbit_files.append(normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        for alias in repository_service.moonbit_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for config_path in sorted(config_paths):
        try:
            text = (repo_path / config_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.moonbit_adapter.parse_dependencies_only(
            config_path,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file:
                imported_files.add(dependency.target_file)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in moonbit_files:
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        fallback_paths.add(normalized_candidate)
        basename = PurePosixPath(normalized_candidate).name.lower()
        package_alias = PurePosixPath(normalized_candidate).parent.name.lower()
        if _is_operational_profile_entrypoint_candidate(
            normalized_candidate,
            repo_path=repo_path,
        ) and (
            basename == f"{package_alias}.mbt"
            or basename in preferred_basenames
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:12])
    return entrypoint_paths, support_roots, config_paths


def _gleam_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path
    tomllib = probe_module.tomllib

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    project_dir = PurePosixPath(normalized_path).parent
    package_name = ""
    if tomllib is not None:
        try:
            manifest_payload = tomllib.loads(manifest_text)
        except (tomllib.TOMLDecodeError, TypeError, ValueError):
            manifest_payload = {}
        raw_package_name = manifest_payload.get("name")
        if isinstance(raw_package_name, str):
            package_name = raw_package_name.strip()
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    search_roots: list[Path] = []
    seen_search_roots: set[Path] = set()
    for candidate_root in (
        project_dir / "src",
        project_dir / "test",
        project_dir / "tests",
        project_dir / "app",
        project_dir,
    ):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
        search_root = repo_path / candidate_root
        resolved_search_root = search_root.resolve()
        if not search_root.exists() or resolved_search_root in seen_search_roots:
            continue
        seen_search_roots.add(resolved_search_root)
        search_roots.append(search_root)
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    preferred_names = {"main.gleam", "app.gleam"}
    if package_name:
        preferred_names.add(f"{package_name.replace('-', '_')}.gleam")
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob("*.gleam")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "gleam"
            ):
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if (
                repository_service._is_test_path(relative_path)
                or _is_non_operational_profile_path(relative_path)
            ):
                continue
            fallback_paths.add(relative_path)
            if probe_module._is_operational_profile_entrypoint_candidate(
                relative_path,
                repo_path=repo_path,
            ):
                if PurePosixPath(relative_path).name in preferred_names:
                    entrypoint_paths.add(relative_path)
                elif not entrypoint_paths:
                    entrypoint_paths.add(relative_path)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _janet_profile_hints(
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
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()

    def _record_existing_path(raw_value: str) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_value)
        )
        if not normalized_candidate:
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.exists() or candidate_file.is_symlink():
            return
        if candidate_file.is_dir():
            support_roots.add(normalized_candidate)
            return
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "janet":
            return
        fallback_paths.add(normalized_candidate)
        if _is_operational_profile_entrypoint_candidate(
            normalized_candidate,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(normalized_candidate)

    for match in re.finditer(r':main\s+"(?P<path>[^"]+)"', manifest_text):
        _record_existing_path(str(match.group("path") or "").strip())
    for match in re.finditer(r':source\s+@?\[(?P<body>[^\]]*)\]', manifest_text, re.DOTALL):
        for source_match in re.finditer(r'"(?P<path>[^"]+)"', str(match.group("body") or "")):
            _record_existing_path(str(source_match.group("path") or "").strip())
    for relative_root in ("src", "lib", "bin", "test", "tests", "examples", "tools"):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(project_dir / relative_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
    if not entrypoint_paths:
        preferred_basenames = {"init.janet", "main.janet"}
        for candidate_path in sorted(fallback_paths):
            if PurePosixPath(candidate_path).name.lower() in preferred_basenames:
                entrypoint_paths.add(candidate_path)
        if not entrypoint_paths and fallback_paths:
            entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _nextflow_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    manifest_path: str | None = None,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_manifest_path = repository_service._normalize_repository_relative_path(
        manifest_path or ""
    )
    manifest_parent = (
        PurePosixPath(normalized_manifest_path).parent
        if normalized_manifest_path
        else PurePosixPath(".")
    )
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    nextflow_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    config_paths: set[str] = {normalized_manifest_path} if normalized_manifest_path else set()
    preferred_basenames = {"main.nf", "workflow.nf"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate or (
            root_prefix and not normalized_candidate.startswith(root_prefix)
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        if candidate_name in repository_service.nextflow_adapter.NEXTFLOW_CONFIG_BASENAMES:
            if repository_service.nextflow_adapter.is_probable_nextflow_source(
                path=candidate_file,
                text=text,
            ):
                config_paths.add(normalized_candidate)
            continue
        if (
            _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "nextflow"
            or not repository_service.nextflow_adapter.is_probable_nextflow_source(
                path=candidate_file,
                text=text,
            )
        ):
            continue
        nextflow_files.append(normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        for alias in repository_service.nextflow_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in nextflow_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.nextflow_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file:
                imported_files.add(dependency.target_file)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for relative_root in ("modules", "subworkflows", "conf", "bin", "lib"):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(manifest_parent / relative_root)
        )
        if normalized_root and (repo_path / normalized_root).exists():
            support_roots.add(normalized_root)
    for normalized_candidate in nextflow_files:
        fallback_paths.add(normalized_candidate)
        if (
            _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            )
            and PurePosixPath(normalized_candidate).name.lower() in preferred_basenames
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        for normalized_candidate in nextflow_files:
            if _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(normalized_candidate)
        if not entrypoint_paths and fallback_paths:
            entrypoint_paths.update(sorted(fallback_paths)[:12])
    return entrypoint_paths, support_roots, config_paths


def _dhall_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_manifest_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_manifest_path:
        return set(), set(), set()
    manifest_parent = PurePosixPath(normalized_manifest_path).parent
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    dhall_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    preferred_basenames = {"package.dhall", "default.dhall", "defaults.dhall", "main.dhall"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or (root_prefix and not normalized_candidate.startswith(root_prefix))
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "dhall"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.dhall_adapter.is_probable_dhall_source(
            path=candidate_file,
            text=text,
        ):
            continue
        dhall_files.append(normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        for alias in repository_service.dhall_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in dhall_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fallback_paths.add(normalized_candidate)
        if (
            PurePosixPath(normalized_candidate).name.lower() in preferred_basenames
            and _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            )
        ):
            entrypoint_paths.add(normalized_candidate)
        for import_target, _line_number in repository_service.dhall_adapter.parse_import_statements(
            text
        ):
            target_file = repository_service.dhall_adapter.resolve_import(
                file_path=normalized_candidate,
                import_target=import_target,
                module_index=module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            imported_parent = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if imported_parent:
                support_roots.add(imported_parent)
    if normalized_manifest_path not in entrypoint_paths:
        entrypoint_paths.add(normalized_manifest_path)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:8])
    support_roots.update(
        repository_service._normalize_repository_relative_path(str(PurePosixPath(path).parent))
        for path in imported_files
    )
    return entrypoint_paths, {root for root in support_roots if root}, {normalized_manifest_path}


def _luau_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _probe_language_for_path = probe_module._probe_language_for_path
    lua_project_path_re = probe_module._LUAU_PROJECT_PATH_RE
    luau_wally_name_re = probe_module._LUAU_WALLY_NAME_RE

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    manifest_file = repo_path / normalized_path
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}modules",
        f"{root_prefix}scripts",
        f"{root_prefix}server",
        f"{root_prefix}client",
        f"{root_prefix}shared",
    }
    entrypoint_paths: set[str] = set()
    luau_files: list[str] = []
    preferred_basenames = {"init.lua", "init.luau", "main.lua", "main.luau", "module.luau"}
    package_name: str | None = None
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if PurePosixPath(normalized_path).name.lower() == "default.project.json":
        for match in lua_project_path_re.finditer(text):
            target_path = repository_service._normalize_repository_relative_path(
                str(project_dir / match.group("path"))
            )
            if not target_path:
                continue
            target_file = repo_path / target_path
            if target_file.is_file() and target_file.suffix.lower() in {".lua", ".luau"}:
                entrypoint_paths.add(target_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(target_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
            elif target_file.is_dir():
                support_roots.add(target_path)
    elif PurePosixPath(normalized_path).name.lower() == "wally.toml":
        package_match = luau_wally_name_re.search(text)
        if package_match is not None:
            package_name = str(package_match.group("name") or "").strip().rsplit("/", 1)[-1] or None
    search_roots = [
        repo_path / project_dir / name
        for name in ("src", "lib", "modules", "scripts", "server", "client", "shared", "app")
    ]
    search_roots.append(repo_path / project_dir)
    seen_files: set[str] = set()
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for suffix in ("*.luau", "*.lua"):
            for candidate in sorted(search_root.rglob(suffix)):
                if not candidate.is_file() or candidate.is_symlink():
                    continue
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or relative_path in seen_files
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or _probe_language_for_path(relative_path, repo_path=repo_path) != "luau"
                ):
                    continue
                seen_files.add(relative_path)
                luau_files.append(relative_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    if package_name:
        for candidate in (
            f"{root_prefix}src/{package_name}.luau",
            f"{root_prefix}src/{package_name}.lua",
            f"{root_prefix}src/init.luau",
            f"{root_prefix}src/init.lua",
        ):
            if candidate in seen_files:
                entrypoint_paths.add(candidate)
    for relative_path in luau_files:
        pure_path = PurePosixPath(relative_path)
        if pure_path.name.lower() in preferred_basenames or len(pure_path.parts) <= 2:
            entrypoint_paths.add(relative_path)
    if not entrypoint_paths:
        entrypoint_paths.update(luau_files[:8])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _solidity_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    foundry_string_field_re = probe_module._FOUNDRY_STRING_FIELD_RE
    foundry_list_field_re = probe_module._FOUNDRY_LIST_FIELD_RE
    quoted_segment_re = probe_module._QUOTED_SEGMENT_RE

    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}contracts",
        f"{root_prefix}src",
        f"{root_prefix}script",
        f"{root_prefix}scripts",
        f"{root_prefix}interfaces",
        f"{root_prefix}libraries",
    }
    entrypoint_paths: set[str] = set()
    search_roots = {
        repository_service._normalize_repository_relative_path(f"{root_prefix}contracts"),
        repository_service._normalize_repository_relative_path(f"{root_prefix}src"),
        repository_service._normalize_repository_relative_path(f"{root_prefix}script"),
        repository_service._normalize_repository_relative_path(f"{root_prefix}scripts"),
    }
    manifest_path = repo_path / normalized_path
    basename = PurePosixPath(normalized_path).name.lower()
    if basename == "foundry.toml":
        try:
            text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for match in foundry_string_field_re.finditer(text):
            raw_value = str(match.group("value") or "").strip()
            if not raw_value:
                continue
            resolved_root = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_value)
            )
            if resolved_root and match.group("field").lower() != "test":
                search_roots.add(resolved_root)
                support_roots.add(resolved_root)
        for match in foundry_list_field_re.finditer(text):
            for quoted_segment in quoted_segment_re.finditer(str(match.group("body") or "")):
                raw_value = str(quoted_segment.group("value") or "").strip()
                if not raw_value:
                    continue
                resolved_root = repository_service._normalize_repository_relative_path(
                    str(project_dir / raw_value)
                )
                if resolved_root:
                    support_roots.add(resolved_root)
    project_root = repo_path / project_dir
    for search_root in sorted(root for root in search_roots if root):
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        support_roots.add(search_root)
        for candidate in sorted(search_path.rglob("*.sol")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)
    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths
    for fallback_root in ("contracts", "src"):
        candidate_root = project_root / fallback_root
        if not candidate_root.is_dir():
            continue
        relative_root = repository_service._normalize_repository_relative_path(
            str(candidate_root.relative_to(repo_path))
        )
        if relative_root:
            support_roots.add(relative_root)
        for candidate in sorted(candidate_root.rglob("*.sol")):
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


def _apex_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    try:
        manifest_payload = json.loads(manifest_text) if manifest_text.strip() else {}
    except json.JSONDecodeError:
        manifest_payload = {}

    package_roots: list[str] = []
    for raw_entry in manifest_payload.get("packageDirectories", ()):
        if not isinstance(raw_entry, dict):
            continue
        raw_path = str(raw_entry.get("path") or "").strip()
        if not raw_path:
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_path)
        )
        if resolved_path and resolved_path not in package_roots:
            package_roots.append(resolved_path)
    if not package_roots:
        for fallback_path in (
            repository_service._normalize_repository_relative_path(str(project_dir / "force-app")),
            repository_service._normalize_repository_relative_path(str(project_dir / "src")),
            repository_service._normalize_repository_relative_path(str(project_dir / "classes")),
            repository_service._normalize_repository_relative_path(str(project_dir / "triggers")),
        ):
            if fallback_path and fallback_path not in package_roots:
                package_roots.append(fallback_path)

    search_roots: list[str] = []
    for package_root in package_roots:
        for candidate_root in (
            package_root,
            repository_service._normalize_repository_relative_path(
                f"{package_root}/main/default/classes"
            ),
            repository_service._normalize_repository_relative_path(
                f"{package_root}/main/default/triggers"
            ),
            repository_service._normalize_repository_relative_path(f"{package_root}/classes"),
            repository_service._normalize_repository_relative_path(f"{package_root}/triggers"),
        ):
            if not candidate_root or candidate_root in search_roots:
                continue
            if (repo_path / candidate_root).exists():
                search_roots.append(candidate_root)

    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    for search_root in search_roots:
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        support_roots.add(search_root)
        apex_candidates = sorted(search_path.rglob("*.cls")) + sorted(
            search_path.rglob("*.trigger")
        )
        for candidate_path in apex_candidates:
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_path.relative_to(repo_path))
            )
            if not relative_path or _is_non_operational_profile_path(relative_path):
                continue
            try:
                text = candidate_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not repository_service.apex_adapter.is_probable_apex_source(
                path=Path(relative_path),
                text=text,
            ):
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if repository_service.apex_adapter.is_probable_test_source(
                path=Path(relative_path),
                text=text,
            ):
                continue
            entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _wolfram_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.wolfram_adapter.is_probable_wolfram_source(
        path=Path(normalized_path),
        text=text,
    ):
        return set(), set(), config_paths

    project_dir = PurePosixPath(normalized_path).parent
    search_roots: list[str] = []
    support_roots: set[str] = set()
    context_entrypoint_stems: set[str] = set()
    for entry in repository_service.wolfram_adapter.paclet_kernel_entries(
        text,
        manifest_path=normalized_path,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
    ):
        root_path = str(entry.get("root_path") or "").strip()
        if root_path and root_path not in search_roots and (repo_path / root_path).is_dir():
            search_roots.append(root_path)
            support_roots.add(root_path)
        for context_name in entry.get("contexts", ()):
            normalized_context = repository_service.wolfram_adapter.normalize_context_name(
                str(context_name or "")
            )
            if normalized_context:
                context_entrypoint_stems.add(normalized_context.rstrip("`").split("`")[-1])

    for default_root in ("Kernel", "Resources", "Packages", "Applications"):
        candidate_root = repository_service._normalize_repository_relative_path(
            str(project_dir / default_root)
        )
        if (
            candidate_root
            and candidate_root not in search_roots
            and (repo_path / candidate_root).is_dir()
        ):
            search_roots.append(candidate_root)
            support_roots.add(candidate_root)

    project_dir_name = project_dir.name
    entrypoint_paths: set[str] = set()
    if project_dir_name:
        for suffix in (".wl", ".wls", ".m"):
            candidate_path = repository_service._normalize_repository_relative_path(
                str(project_dir / f"{project_dir_name}{suffix}")
            )
            if not candidate_path or not (repo_path / candidate_path).is_file():
                continue
            try:
                candidate_text = (repo_path / candidate_path).read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue
            if not repository_service.wolfram_adapter.is_probable_wolfram_source(
                path=Path(candidate_path),
                text=candidate_text,
            ):
                continue
            entrypoint_paths.add(candidate_path)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(candidate_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for search_root in search_roots:
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        for suffix in ("*.wl", "*.wls", "*.m"):
            for candidate_path in sorted(search_path.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate_path.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or _is_non_operational_profile_path(relative_path)
                    or PurePosixPath(relative_path).name.lower()
                    in {"pacletinfo.m", "pacletinfo.wl"}
                ):
                    continue
                try:
                    candidate_text = candidate_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )
                except OSError:
                    continue
                if not repository_service.wolfram_adapter.is_probable_wolfram_source(
                    path=Path(relative_path),
                    text=candidate_text,
                ):
                    continue
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
                lowered_name = PurePosixPath(relative_path).name.lower()
                if lowered_name in {"init.m", "init.wl", "init.wls"}:
                    entrypoint_paths.add(relative_path)
                    continue
                if PurePosixPath(relative_path).stem in context_entrypoint_stems:
                    entrypoint_paths.add(relative_path)

    if entrypoint_paths:
        return entrypoint_paths, support_roots, config_paths

    fallback_entrypoints: set[str] = set()
    for search_root in search_roots:
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        for suffix in ("*.wl", "*.wls", "*.m"):
            for candidate_path in sorted(search_path.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate_path.relative_to(repo_path))
                )
                if (
                    relative_path
                    and not _is_non_operational_profile_path(relative_path)
                    and PurePosixPath(relative_path).name.lower()
                    not in {"pacletinfo.m", "pacletinfo.wl"}
                ):
                    fallback_entrypoints.add(relative_path)
    return fallback_entrypoints, support_roots, config_paths
