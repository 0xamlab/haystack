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


repository_service = _DeferredProbeAttr("repository_service")
_is_non_operational_profile_path = _DeferredProbeAttr("_is_non_operational_profile_path")
_is_non_operational_profile_path_for_ecosystems = _DeferredProbeAttr(
    "_is_non_operational_profile_path_for_ecosystems"
)
_probe_language_for_path = _DeferredProbeAttr("_probe_language_for_path")

_SHADERLAB_FAST_FALLBACK_MIN_CANDIDATES = 24
_SHADERLAB_FAST_FALLBACK_ENTRYPOINT_LIMIT = 8
_SHADERLAB_PREFERRED_BASENAMES = frozenset({"main.shader"})
_SHADERLAB_LIBRARY_LIKE_PARTS = frozenset(
    {"editor", "sample", "samples", "test", "tests", "example", "examples"}
)


def _shaderlab_fast_fallback_entrypoints(
    shader_files: list[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    prioritized_candidates = sorted(
        shader_files,
        key=lambda candidate: (
            0 if PurePosixPath(candidate).name.lower() in _SHADERLAB_PREFERRED_BASENAMES else 1,
            0
            if not {
                part.lower() for part in PurePosixPath(candidate).parts[:-1]
            }.intersection(_SHADERLAB_LIBRARY_LIKE_PARTS)
            else 1,
            len(PurePosixPath(candidate).name),
            candidate,
        ),
    )
    entrypoints: list[str] = []
    support_roots: list[str] = []
    seen_entrypoints: set[str] = set()
    seen_support_roots: set[str] = set()

    def _remember(candidate: str) -> None:
        if candidate in seen_entrypoints:
            return
        seen_entrypoints.add(candidate)
        entrypoints.append(candidate)
        support_root = str(PurePosixPath(candidate).parent)
        if support_root and support_root not in seen_support_roots:
            seen_support_roots.add(support_root)
            support_roots.append(support_root)

    for candidate in prioritized_candidates:
        support_root = str(PurePosixPath(candidate).parent)
        if support_root in seen_support_roots:
            continue
        _remember(candidate)
        if len(entrypoints) >= _SHADERLAB_FAST_FALLBACK_ENTRYPOINT_LIMIT:
            return tuple(entrypoints), tuple(support_roots)

    for candidate in prioritized_candidates:
        _remember(candidate)
        if len(entrypoints) >= _SHADERLAB_FAST_FALLBACK_ENTRYPOINT_LIMIT:
            return tuple(entrypoints), tuple(support_roots)

    return tuple(entrypoints), tuple(support_roots)


def _rego_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = set()
    rego_files: list[str] = []
    file_texts: dict[str, str] = {}
    module_index: dict[str, str] = {}
    preferred_basenames = {"allow.rego", "deny.rego", "library.rego", "main.rego", "policy.rego"}
    support_dir_names = {"inputs", "lib", "libs", "policies", "policy", "rules"}

    def _is_rego_test_path(path: str) -> bool:
        candidate = PurePosixPath(path)
        stem = candidate.stem.lower()
        return (
            repository_service._is_test_path(path)
            or stem.startswith("test")
            or stem.endswith("_test")
            or ".test." in path.lower()
        )

    for candidate_path in candidate_file_paths:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _is_rego_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "rego"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rego_files.append(normalized_candidate)
        file_texts[normalized_candidate] = text
        for alias in repository_service.rego_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = PurePosixPath(normalized_candidate).parts
        lowered_parts = [part.lower() for part in candidate_parts]
        for index, part in enumerate(lowered_parts[:-1]):
            if part in support_dir_names:
                support_roots.add("/".join(candidate_parts[: index + 1]))

    imported_targets: set[str] = set()
    for normalized_candidate in rego_files:
        for import_target, _alias, _line in repository_service.rego_adapter.parse_import_statements(
            file_texts[normalized_candidate]
        ):
            target_file = repository_service.rego_adapter.resolve_import(
                import_target,
                module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if not target_file or target_file == normalized_candidate:
                continue
            imported_targets.add(target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for normalized_candidate in rego_files:
        if normalized_candidate in imported_targets:
            continue
        basename = PurePosixPath(normalized_candidate).name.lower()
        if basename in preferred_basenames or len(PurePosixPath(normalized_candidate).parts) <= 2:
            entrypoint_paths.add(normalized_candidate)
            continue
        candidate_parts = [part.lower() for part in PurePosixPath(normalized_candidate).parts[:-1]]
        if not any(part in {"inputs", "lib", "libs", "rules"} for part in candidate_parts):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(rego_files)[:8])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _yara_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    yara_files: list[str] = []
    module_index: dict[str, str] = {}
    imported_files: set[str] = set()
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"index.yar", "index.yara"}

    def _is_yara_test_path(path: str) -> bool:
        pure_path = PurePosixPath(path)
        stem = pure_path.stem.lower()
        return (
            repository_service._is_test_path(path)
            or stem.startswith("test")
            or stem.endswith("_test")
            or ".test." in pure_path.name.lower()
        )

    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _is_yara_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "yara"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.yara_adapter.is_probable_yara_source(
            path=candidate_file,
            text=text,
        ):
            continue
        yara_files.append(normalized_candidate)
        for alias in repository_service.yara_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)

    for normalized_candidate in yara_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for include_target, _line in repository_service.yara_adapter.parse_include_statements(text):
            target_file = repository_service.yara_adapter.resolve_include(
                include_target,
                normalized_candidate,
                module_index,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
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

    for normalized_candidate in yara_files:
        pure_path = PurePosixPath(normalized_candidate)
        if (
            pure_path.name.lower() in preferred_basenames
            or pure_path.stem.lower().endswith("_index")
        ):
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(sorted(yara_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _glsl_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    shader_files: list[str] = []
    file_texts: dict[str, str] = {}
    stripped_texts: dict[str, str] = {}
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.glsl", "main.frag", "main.vert", "index.glsl"}
    library_like_parts = {"common", "include", "includes", "lib", "libs", "shaderlib", "shaders"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "glsl"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.glsl_adapter.is_probable_glsl_source(
            path=candidate_file,
            text=text,
        ):
            continue
        shader_files.append(normalized_candidate)
        for alias in repository_service.glsl_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)

    for normalized_candidate in shader_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.glsl_adapter.parse_dependencies_only(
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

    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _opencl_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    from benchmarks import (
        repository_intelligence_real_repo_probe_profile_path_classification_support
        as classification_support,
    )

    shader_files: list[str] = []
    file_texts: dict[str, str] = {}
    stripped_texts: dict[str, str] = {}
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.cl", "main.clh", "index.cl", "kernel.cl"}
    library_like_parts = {"common", "include", "includes", "inc", "lib", "libs", "shared"}
    support_dirs = {"include", "includes", "kernel", "kernels", "src", "source", "sources"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"opencl"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "opencl"
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
        stripped_text = repository_service.opencl_adapter.strip_comments(text)
        if not repository_service.opencl_adapter.is_probable_opencl_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        shader_files.append(normalized_candidate)
        file_texts[normalized_candidate] = text
        stripped_texts[normalized_candidate] = stripped_text
        for alias in repository_service.opencl_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
            stripped_text=stripped_text,
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

    for normalized_candidate in shader_files:
        text = file_texts.get(normalized_candidate)
        stripped_text = stripped_texts.get(normalized_candidate)
        if text is None or stripped_text is None:
            continue
        for dependency in repository_service.opencl_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            resolve_include=lambda **kwargs: repository_service.opencl_adapter.resolve_include(
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
                **kwargs,
            ),
            stripped_text=stripped_text,
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.suffix.lower() != ".cl":
            continue
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files or not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in shader_files
            if PurePosixPath(normalized_candidate).suffix.lower() == ".cl"
        )
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _metal_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    shader_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.metal", "index.metal", "shader.metal"}
    library_like_parts = {"common", "include", "includes", "lib", "libs", "shaderlib", "shaders"}
    support_dirs = {"include", "includes", "shader", "shaders", "src", "source", "sources", "lib"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "metal"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.metal_adapter.is_probable_metal_source(
            path=candidate_file,
            text=text,
        ):
            continue
        shader_files.append(normalized_candidate)
        for alias in repository_service.metal_adapter.module_aliases_for_path(
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

    for normalized_candidate in shader_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.metal_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            resolve_include=lambda **kwargs: repository_service.metal_adapter.resolve_include(
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
                **kwargs,
            ),
        ):
            if not dependency.target_file or dependency.target_file == normalized_candidate:
                continue
            imported_files.add(dependency.target_file)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(dependency.target_file).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)

    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        if pure_path.suffix.lower() != ".metal":
            continue
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files or not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in shader_files
            if PurePosixPath(normalized_candidate).suffix.lower() == ".metal"
        )
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _hlsl_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    shader_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {
        "main.hlsl",
        "main.fx",
        "main.compute",
        "main.cs.hlsl",
        "index.hlsl",
    }
    library_like_parts = {"common", "include", "includes", "inc", "lib", "libs", "shaderlab"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "hlsl"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.hlsl_adapter.is_probable_hlsl_source(
            path=candidate_file,
            text=text,
        ):
            continue
        shader_files.append(normalized_candidate)
        for alias in repository_service.hlsl_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)

    for normalized_candidate in shader_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.hlsl_adapter.parse_dependencies_only(
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

    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _wgsl_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    shader_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"main.wgsl", "index.wgsl", "shader.wgsl"}
    library_like_parts = {"common", "include", "includes", "lib", "libs", "shaderlib", "shaders"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "wgsl"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.wgsl_adapter.is_probable_wgsl_source(
            path=candidate_file,
            text=text,
        ):
            continue
        shader_files.append(normalized_candidate)
        for alias in repository_service.wgsl_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)

    for normalized_candidate in shader_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.wgsl_adapter.parse_dependencies_only(
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

    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)

    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _shaderlab_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    shader_files: list[str] = []
    shader_stripped_text_by_path: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    shader_text_by_path: dict[str, str] = {}
    shader_files_with_named_targets: set[str] = set()
    preferred_basenames = set(_SHADERLAB_PREFERRED_BASENAMES)
    library_like_parts = set(_SHADERLAB_LIBRARY_LIKE_PARTS)
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "shaderlab"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        shader_files.append(normalized_candidate)
    if len(shader_files) >= _SHADERLAB_FAST_FALLBACK_MIN_CANDIDATES:
        fast_entrypoints, fast_support_roots = _shaderlab_fast_fallback_entrypoints(
            shader_files
        )
        if fast_entrypoints:
            return set(fast_entrypoints), {root for root in fast_support_roots if root}, set()
    for normalized_candidate in shader_files:
        candidate_file = repo_path / normalized_candidate
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.shaderlab_adapter.strip_comments(text)
        if not repository_service.shaderlab_adapter.is_probable_shaderlab_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        shader_text_by_path[normalized_candidate] = text
        shader_stripped_text_by_path[normalized_candidate] = stripped_text
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    if len(shader_files) <= 16:
        module_index: dict[str, str] = {}
        for normalized_candidate in shader_files:
            candidate_path = PurePosixPath(normalized_candidate)
            for alias in (
                normalized_candidate,
                str(candidate_path.with_suffix("")),
                candidate_path.stem,
            ):
                if alias:
                    module_index.setdefault(alias, normalized_candidate)
            text = shader_text_by_path.get(normalized_candidate)
            stripped_text = shader_stripped_text_by_path.get(normalized_candidate)
            if text is None or stripped_text is None:
                continue
            if repository_service.shaderlab_adapter.iter_usepass_targets(
                text,
                stripped_text=stripped_text,
            ) or repository_service.shaderlab_adapter.iter_fallback_targets(
                text,
                stripped_text=stripped_text,
            ):
                shader_files_with_named_targets.add(normalized_candidate)
        if shader_files_with_named_targets:
            for normalized_candidate in shader_files:
                text = shader_text_by_path.get(normalized_candidate)
                stripped_text = shader_stripped_text_by_path.get(normalized_candidate)
                if text is None or stripped_text is None:
                    continue
                for alias in repository_service.shaderlab_adapter.iter_shader_names(
                    text,
                    stripped_text=stripped_text,
                ):
                    module_index.setdefault(alias, normalized_candidate)
        for normalized_candidate in shader_files:
            text = shader_text_by_path.get(normalized_candidate)
            stripped_text = shader_stripped_text_by_path.get(normalized_candidate)
            if text is None or stripped_text is None:
                continue
            for dependency in repository_service.shaderlab_adapter.parse_dependencies_only(
                normalized_candidate,
                text,
                module_index,
                stable_identifier=repository_service._stable_identifier,
                normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
                resolve_suffix_match=repository_service._resolve_suffix_match,
                stripped_text=stripped_text,
            ):
                if not dependency.target_file or dependency.target_file == normalized_candidate:
                    continue
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(dependency.target_file).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in shader_files:
        pure_path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in pure_path.parts[:-1]}
        if pure_path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not candidate_parts.intersection(
            library_like_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(shader_files)[:8])
    return entrypoint_paths, {root for root in support_roots if root}, set()
