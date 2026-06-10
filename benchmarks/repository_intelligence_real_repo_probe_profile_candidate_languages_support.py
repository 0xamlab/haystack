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
_is_non_operational_profile_path_for_ecosystems = _DeferredProbeAttr(
    "_is_non_operational_profile_path_for_ecosystems"
)
_probe_language_for_path = _DeferredProbeAttr("_probe_language_for_path")


def _rescript_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    rescript_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {"main.res", "index.res", "app.res", "lib.res"}
    support_dirs = {"src", "lib", "examples", "scripts"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate:
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if candidate_file.name.lower() in repository_service.rescript_adapter.RESCRIPT_CONFIG_BASENAMES:
            if repository_service.rescript_adapter.is_probable_rescript_config(
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
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"rescript"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "rescript"
            or not repository_service.rescript_adapter.is_probable_rescript_source(
                path=candidate_file,
                text=text,
            )
        ):
            continue
        rescript_files.append(normalized_candidate)
        for alias in repository_service.rescript_adapter.module_aliases_for_path(
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
    for normalized_candidate in rescript_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.rescript_adapter.parse_dependencies_only(
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
    for normalized_candidate in rescript_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(rescript_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _roc_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    roc_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    excluded_parts = {"fixture", "fixtures", "snapshot", "snapshots", "test", "tests"}
    preferred_basenames = {"app.roc", "build.roc", "main.roc"}
    support_dirs = {"app", "apps", "ci", "example", "examples", "platform", "src"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate:
            continue
        path = PurePosixPath(normalized_candidate)
        if {part.lower() for part in path.parts} & excluded_parts:
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "roc"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.roc_adapter.is_probable_roc_source(path=candidate_file, text=text):
            continue
        roc_files.append(normalized_candidate)
        for alias in repository_service.roc_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = path.parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(path.parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in roc_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.roc_adapter.parse_dependencies_only(
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
    for normalized_candidate in roc_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(roc_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _modelica_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    modelica_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    excluded_parts = {
        "benchmark",
        "benchmarks",
        "doc",
        "docs",
        "example",
        "examples",
        "fixture",
        "fixtures",
        "sample",
        "samples",
        "snapshot",
        "snapshots",
        "test",
        "tests",
        "testsuite",
        "tutorial",
        "tutorials",
    }
    preferred_basenames = {"main.mo", "package.mo"}
    support_dirs = {"library", "libraries", "modelica", "models", "package", "packages", "src"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if not normalized_candidate:
            continue
        path = PurePosixPath(normalized_candidate)
        if {part.lower() for part in path.parts} & excluded_parts:
            continue
        candidate_file = repo_path / normalized_candidate
        if (
            not candidate_file.is_file()
            or candidate_file.is_symlink()
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "modelica"
        ):
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.modelica_adapter.is_probable_modelica_source(
            path=candidate_file,
            text=text,
        ):
            continue
        modelica_files.append(normalized_candidate)
        for alias in repository_service.modelica_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = path.parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(path.parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in modelica_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.modelica_adapter.parse_dependencies_only(
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
    for normalized_candidate in modelica_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(modelica_files)[:16])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _cython_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    cython_files: list[str] = []
    pyx_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"__init__.pyx", "core.pyx", "main.pyx"}
    library_like_parts = {"include", "includes", "lib", "libs", "tests", "vendor"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "cython"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.cython_adapter.is_probable_cython_source(
            path=candidate_file,
            text=text,
        ):
            continue
        cython_files.append(normalized_candidate)
        if PurePosixPath(normalized_candidate).suffix.lower() == ".pyx":
            pyx_files.append(normalized_candidate)
        for alias in repository_service.cython_adapter.module_aliases_for_path(
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
    for normalized_candidate in cython_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.cython_adapter.parse_dependencies_only(
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
    for normalized_candidate in pyx_files:
        candidate_name = PurePosixPath(normalized_candidate).name
        candidate_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if candidate_name in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in library_like_parts for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(pyx_files or cython_files)[:8])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _stan_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    stan_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"main.stan", "model.stan"}
    library_like_parts = {"functions", "include", "includes", "lib", "libs", "test", "tests"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "stan"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.stan_adapter.is_probable_stan_source(
            path=candidate_file,
            text=text,
        ):
            continue
        stan_files.append(normalized_candidate)
        for alias in repository_service.stan_adapter.module_aliases_for_path(
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
    for normalized_candidate in stan_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.stan_adapter.parse_dependencies_only(
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
    for normalized_candidate in stan_files:
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        candidate_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if candidate_name in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in library_like_parts for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(stan_files)[:8])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _protobuf_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    protobuf_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"api.proto", "main.proto", "service.proto"}
    library_like_parts = {
        "buf",
        "google",
        "internal",
        "proto",
        "protos",
        "schema",
        "schemas",
        "test",
        "tests",
        "third_party",
        "vendor",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate or repository_service._is_test_path(normalized_candidate):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        if candidate_name in repository_service.protobuf_adapter.PROTOBUF_CONFIG_BASENAMES:
            if repository_service.protobuf_adapter.is_probable_protobuf_config(
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
            _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "protobuf"
            or not repository_service.protobuf_adapter.is_probable_protobuf_source(
                path=candidate_file,
                text=text,
            )
        ):
            continue
        protobuf_files.append(normalized_candidate)
        for alias in repository_service.protobuf_adapter.module_aliases_for_path(
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
    for normalized_candidate in protobuf_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.protobuf_adapter.parse_dependencies_only(
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
    for normalized_candidate in protobuf_files:
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        candidate_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if candidate_name in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in library_like_parts for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(protobuf_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths
