from __future__ import annotations

from pathlib import Path, PurePosixPath

from benchmarks import (
    repository_intelligence_real_repo_probe_profile_path_classification_support as classification_support,
)


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _qml_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    qml_files: list[str] = []
    qml_text_by_path: dict[str, str] = {}
    qml_parent_parts_by_path: dict[str, tuple[str, ...]] = {}
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = frozenset({"main.qml", "app.qml", "application.qml"})
    library_like_parts = frozenset(
        {"components", "controls", "lib", "libs", "modules", "shared", "widgets"}
    )
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        candidate_parts = PurePosixPath(normalized_candidate) if normalized_candidate else None
        candidate_basename = candidate_parts.name.lower() if candidate_parts is not None else ""
        candidate_suffix = candidate_parts.suffix.lower() if candidate_parts is not None else ""
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or probe_module._is_non_operational_profile_path(normalized_candidate)
            or (candidate_basename != "qmldir" and candidate_suffix != ".qml")
        ):
            continue
        if (
            not classification_support._repo_path_is_regular_file(repo_path, normalized_candidate)
            or classification_support._repo_path_is_symlink(repo_path, normalized_candidate)
        ):
            continue
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.qml_adapter.is_probable_qml_source(
            path=candidate_parts,
            text=text,
        ):
            continue
        qml_files.append(normalized_candidate)
        qml_text_by_path[normalized_candidate] = text
        qml_parent_parts_by_path[normalized_candidate] = tuple(
            part.lower() for part in candidate_parts.parts[:-1]
        )
        if candidate_basename == "qmldir":
            config_paths.add(normalized_candidate)
        for alias in repository_service.qml_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
        ):
            module_index.setdefault(alias, normalized_candidate)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(candidate_parts.parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in qml_files:
        text = qml_text_by_path.get(normalized_candidate)
        if text is None:
            continue
        for dependency in repository_service.qml_adapter.parse_dependencies_only(
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
    for normalized_candidate in qml_files:
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        candidate_parts = qml_parent_parts_by_path.get(normalized_candidate, ())
        if candidate_name == "qmldir":
            continue
        if candidate_name in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in library_like_parts for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            path for path in sorted(qml_files)[:8] if PurePosixPath(path).name.lower() != "qmldir"
        )
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _chapel_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service

    chapel_files: list[str] = []
    chapel_text_by_path: dict[str, str] = {}
    chapel_stripped_text_by_path: dict[str, str] = {}
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.chpl"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        candidate_parts = PurePosixPath(normalized_candidate) if normalized_candidate else None
        candidate_basename = candidate_parts.name.lower() if candidate_parts is not None else ""
        candidate_suffix = candidate_parts.suffix.lower() if candidate_parts is not None else ""
        if (
            not normalized_candidate
            or (candidate_basename != "mason.toml" and candidate_suffix != ".chpl")
        ):
            continue
        if candidate_suffix != ".chpl":
            continue
        if (
            repository_service._is_test_path(normalized_candidate)
            or probe_module._is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if (
            not classification_support._repo_path_is_regular_file(repo_path, normalized_candidate)
            or classification_support._repo_path_is_symlink(repo_path, normalized_candidate)
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.chapel_adapter.strip_comments(text)
        if not repository_service.chapel_adapter.is_probable_chapel_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        chapel_files.append(normalized_candidate)
        chapel_text_by_path[normalized_candidate] = text
        chapel_stripped_text_by_path[normalized_candidate] = stripped_text
        for alias in repository_service.chapel_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
            stripped_text=stripped_text,
            include_symbol_aliases=False,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in chapel_files:
        text = chapel_text_by_path.get(normalized_candidate)
        stripped_text = chapel_stripped_text_by_path.get(normalized_candidate)
        if text is None or stripped_text is None:
            continue
        for _kind, import_target, _alias, _line_no in (
            repository_service.chapel_adapter.parse_use_import_statements(
                text,
                stripped_text=stripped_text,
            )
        ):
            target_file = repository_service.chapel_adapter.resolve_import(
                import_target,
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
    for normalized_candidate in chapel_files:
        basename = PurePosixPath(normalized_candidate).name.lower()
        if basename in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(chapel_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()
