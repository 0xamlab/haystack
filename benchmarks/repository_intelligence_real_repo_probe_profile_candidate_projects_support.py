from __future__ import annotations

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


repository_service = _DeferredProbeAttr("repository_service")
_is_non_operational_profile_path = _DeferredProbeAttr("_is_non_operational_profile_path")
_is_operational_profile_entrypoint_candidate = _DeferredProbeAttr(
    "_is_operational_profile_entrypoint_candidate"
)
_probe_language_for_path = _DeferredProbeAttr("_probe_language_for_path")


def _odin_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    manifest_file = repo_path / normalized_path
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set(), set(), config_paths
    if not repository_service.odin_adapter.is_probable_odin_source(
        path=Path(normalized_path),
        text=manifest_text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    search_roots: list[PurePosixPath] = [project_dir]
    for raw_target in (
        *repository_service.odin_adapter.parse_ols_checker_paths(manifest_text),
        *repository_service.odin_adapter.parse_ols_collections(manifest_text),
    ):
        normalized_target = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_target)
        )
        if not normalized_target:
            continue
        candidate = repo_path / normalized_target
        if candidate.is_dir():
            support_roots.add(normalized_target)
            search_roots.append(PurePosixPath(normalized_target))
        elif candidate.is_file():
            config_paths.add(normalized_target)
    candidate_file_paths: list[str] = []
    seen_candidates: set[str] = set()
    for search_root in search_roots:
        search_path = repo_path / search_root
        if not search_path.is_dir():
            continue
        for candidate_file in sorted(search_path.rglob("*.odin")):
            if not candidate_file.is_file() or candidate_file.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_file.relative_to(repo_path))
            )
            if not relative_path or relative_path in seen_candidates:
                continue
            seen_candidates.add(relative_path)
            candidate_file_paths.append(relative_path)
    entrypoints, inferred_roots, _ = _odin_profile_hints_from_candidates(
        repo_path,
        candidate_file_paths,
    )
    support_roots.update(inferred_roots)
    for candidate in (
        str(project_dir / "main.odin"),
        str(project_dir / "src" / "main.odin"),
    ):
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


def _odin_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    odin_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.odin", "app.odin"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "odin"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or candidate_file.suffix.lower() != ".odin"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.odin_adapter.is_probable_odin_source(
            path=candidate_file,
            text=text,
        ):
            continue
        odin_files.append(normalized_candidate)
        for alias in repository_service.odin_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in odin_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for import_target, _alias, _line_number in (
            repository_service.odin_adapter.parse_import_statements(text)
        ):
            target_file = repository_service.odin_adapter.resolve_import(
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
    for normalized_candidate in odin_files:
        basename = PurePosixPath(normalized_candidate).name.lower()
        if basename in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(odin_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _factor_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    factor_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.factor", "app.factor", "run.factor"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "factor"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or candidate_file.suffix.lower() != ".factor"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.factor_adapter.is_probable_factor_source(
            path=candidate_file,
            text=text,
        ):
            continue
        factor_files.append(normalized_candidate)
        for alias in repository_service.factor_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in factor_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for import_statement in repository_service.factor_adapter.parse_import_statements(text):
            target_file = repository_service.factor_adapter.resolve_import(
                import_statement.target,
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
    for normalized_candidate in factor_files:
        path = PurePosixPath(normalized_candidate)
        basename = path.name.lower()
        if (
            basename in preferred_basenames
            or path.parent.name.lower() == path.stem.lower()
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(factor_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _cue_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
    *,
    manifest_path: str | None = None,
) -> tuple[set[str], set[str], set[str]]:
    cue_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    config_paths: set[str] = {manifest_path} if manifest_path else set()
    preferred_basenames = {"main.cue", "schema.cue", "tool.cue"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "cue"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or candidate_file.suffix.lower() != ".cue"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.cue_adapter.is_probable_cue_source(
            path=candidate_file,
            text=text,
        ):
            continue
        cue_files.append(normalized_candidate)
        for alias in repository_service.cue_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        if "/cue.mod/" in normalized_candidate.replace("\\", "/"):
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(normalized_candidate).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in cue_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for import_statement in repository_service.cue_adapter.parse_import_statements(text):
            target_file = repository_service.cue_adapter.resolve_import(
                file_path=normalized_candidate,
                import_target=import_statement.target,
                module_index=module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
                root_path=repo_path,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_files.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for normalized_candidate in cue_files:
        lowered_path = normalized_candidate.lower().replace("\\", "/")
        basename = PurePosixPath(normalized_candidate).name.lower()
        if "/cue.mod/" in lowered_path:
            continue
        if basename in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in sorted(cue_files)[:8]
            if "/cue.mod/" not in normalized_candidate.lower().replace("\\", "/")
        )
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths
