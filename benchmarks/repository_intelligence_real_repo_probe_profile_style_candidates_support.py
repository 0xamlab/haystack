from __future__ import annotations

from pathlib import Path, PurePosixPath

_STYLE_PROFILE_BUCKET_CACHE_LIMIT = 256
_STYLE_PROFILE_BUCKET_CACHE: dict[
    tuple[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
] = {}
_STYLE_PROFILE_LANGUAGES = frozenset({"less", "scss", "stylus"})


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
_probe_language_for_path = _DeferredProbeAttr("_probe_language_for_path")


def _style_profile_candidate_buckets(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> dict[str, tuple[str, ...]]:
    repo_key = str(repo_path)
    normalized_candidates = tuple(
        sorted(
            {
                normalized_candidate
                for candidate_path in candidate_file_paths
                if (
                    normalized_candidate := repository_service._normalize_repository_relative_path(
                        candidate_path
                    )
                )
            }
        )
    )
    cache_key = (repo_key, normalized_candidates)
    cached_buckets = _STYLE_PROFILE_BUCKET_CACHE.get(cache_key)
    if cached_buckets is not None:
        return {
            language: tuple(paths)
            for language, paths in cached_buckets.items()
        }
    buckets: dict[str, list[str]] = {language: [] for language in _STYLE_PROFILE_LANGUAGES}
    for normalized_candidate in normalized_candidates:
        language = _probe_language_for_path(normalized_candidate, repo_path=repo_path)
        if language not in _STYLE_PROFILE_LANGUAGES:
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        buckets[language].append(normalized_candidate)
    frozen_buckets = {
        language: tuple(paths)
        for language, paths in buckets.items()
    }
    if len(_STYLE_PROFILE_BUCKET_CACHE) >= _STYLE_PROFILE_BUCKET_CACHE_LIMIT:
        oldest_key = next(iter(_STYLE_PROFILE_BUCKET_CACHE))
        _STYLE_PROFILE_BUCKET_CACHE.pop(oldest_key, None)
    _STYLE_PROFILE_BUCKET_CACHE[cache_key] = frozen_buckets
    return {
        language: tuple(paths)
        for language, paths in frozen_buckets.items()
    }


def _sass_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    sass_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "app.sass",
        "application.sass",
        "bootstrap.sass",
        "index.sass",
        "main.sass",
        "style.sass",
        "styles.sass",
        "theme.sass",
    }
    support_dirs = {"assets", "sass", "scss", "styles", "stylesheets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "sass"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.sass_adapter.is_probable_sass_source(
            path=candidate_file,
            text=text,
        ):
            continue
        sass_files.append(normalized_candidate)
        for alias in repository_service.sass_adapter.module_aliases_for_path(
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
    for normalized_candidate in sass_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.sass_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in sass_files:
        path = PurePosixPath(normalized_candidate)
        if (
            path.name.startswith("_")
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in sass_files
            if not PurePosixPath(normalized_candidate).name.startswith("_")
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _qsharp_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    qsharp_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {
        "app.qs",
        "demo.qs",
        "index.qs",
        "main.qs",
        "program.qs",
        "sample.qs",
    }
    support_dirs = {"demo", "demos", "examples", "qsharp", "quantum", "samples", "src"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        candidate_parts = PurePosixPath(normalized_candidate).parts
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            PurePosixPath(normalized_candidate).name.lower()
            in repository_service.qsharp_adapter.QSHARP_CONFIG_BASENAMES
        ):
            if repository_service.qsharp_adapter.is_probable_qsharp_config(
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
            _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "qsharp"
            or not repository_service.qsharp_adapter.is_probable_qsharp_source(
                path=candidate_file,
                text=text,
            )
        ):
            continue
        qsharp_files.append(normalized_candidate)
        for alias in repository_service.qsharp_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in qsharp_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.qsharp_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in qsharp_files:
        pure_path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if pure_path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in qsharp_files
            if not repository_service._is_test_path(normalized_candidate)
        )
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _al_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    al_files: list[str] = []
    support_roots: set[str] = set()
    support_dirs = {
        "al",
        "app",
        "apps",
        "codeunit",
        "codeunits",
        "enum",
        "enums",
        "extension",
        "extensions",
        "page",
        "pages",
        "profile",
        "profiles",
        "query",
        "queries",
        "report",
        "reports",
        "src",
        "table",
        "tables",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "al"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.al_adapter.is_probable_al_source(path=candidate_file, text=text):
            continue
        al_files.append(normalized_candidate)
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
    entrypoint_paths = {
        normalized_candidate
        for normalized_candidate in al_files
        if not repository_service._is_test_path(normalized_candidate)
        and not _is_non_operational_profile_path(normalized_candidate)
    }
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _scss_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    style_candidate_buckets = _style_profile_candidate_buckets(repo_path, candidate_file_paths)
    scss_files: list[str] = []
    scss_file_text: dict[str, str] = {}
    scss_file_stripped_text: dict[str, str] = {}
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "app.scss",
        "application.scss",
        "bootstrap.scss",
        "index.scss",
        "main.scss",
        "style.scss",
        "styles.scss",
        "theme.scss",
    }
    support_dirs = {"assets", "sass", "scss", "styles", "stylesheets"}
    for normalized_candidate in style_candidate_buckets["scss"]:
        candidate_file = repo_path / normalized_candidate
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.scss_adapter.strip_comments(text)
        if not repository_service.scss_adapter.is_probable_scss_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        scss_files.append(normalized_candidate)
        scss_file_text[normalized_candidate] = text
        scss_file_stripped_text[normalized_candidate] = stripped_text
        for alias in repository_service.scss_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
            stripped_text=stripped_text,
            include_symbol_aliases=False,
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
    for normalized_candidate in scss_files:
        text = scss_file_text.get(normalized_candidate)
        stripped_text = scss_file_stripped_text.get(normalized_candidate)
        if text is None or stripped_text is None:
            continue
        for dependency in repository_service.scss_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
            stripped_text=stripped_text,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in scss_files:
        path = PurePosixPath(normalized_candidate)
        if (
            path.name.startswith("_")
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in scss_files
            if not PurePosixPath(normalized_candidate).name.startswith("_")
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _less_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    style_candidate_buckets = _style_profile_candidate_buckets(repo_path, candidate_file_paths)
    less_files: list[str] = []
    less_file_text: dict[str, str] = {}
    less_file_stripped_text: dict[str, str] = {}
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "app.less",
        "application.less",
        "index.less",
        "main.less",
        "style.less",
        "styles.less",
        "theme.less",
        "variables.less",
    }
    support_dirs = {"assets", "less", "src", "styles", "stylesheets", "themes"}
    for normalized_candidate in style_candidate_buckets["less"]:
        candidate_file = repo_path / normalized_candidate
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.less_adapter.strip_comments(text)
        if not repository_service.less_adapter.is_probable_less_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        less_files.append(normalized_candidate)
        less_file_text[normalized_candidate] = text
        less_file_stripped_text[normalized_candidate] = stripped_text
        for alias in repository_service.less_adapter.module_aliases_for_path(
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
    for normalized_candidate in less_files:
        text = less_file_text.get(normalized_candidate)
        stripped_text = less_file_stripped_text.get(normalized_candidate)
        if text is None or stripped_text is None:
            continue
        for dependency in repository_service.less_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
            stripped_text=stripped_text,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in less_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(less_files)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _stylus_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    style_candidate_buckets = _style_profile_candidate_buckets(repo_path, candidate_file_paths)
    stylus_files: list[str] = []
    stylus_file_text: dict[str, str] = {}
    stylus_file_stripped_text: dict[str, str] = {}
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "app.styl",
        "application.styl",
        "index.styl",
        "main.styl",
        "style.styl",
        "styles.styl",
        "theme.styl",
        "variables.styl",
    }
    support_dirs = {"assets", "src", "styl", "stylus", "styles", "stylesheets", "themes"}
    for normalized_candidate in style_candidate_buckets["stylus"]:
        candidate_file = repo_path / normalized_candidate
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.stylus_adapter.strip_comments(text)
        if not repository_service.stylus_adapter.is_probable_stylus_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        stylus_files.append(normalized_candidate)
        stylus_file_text[normalized_candidate] = text
        stylus_file_stripped_text[normalized_candidate] = stripped_text
        for alias in repository_service.stylus_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
            stripped_text=stripped_text,
            include_symbol_aliases=False,
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
    for normalized_candidate in stylus_files:
        text = stylus_file_text.get(normalized_candidate)
        stripped_text = stylus_file_stripped_text.get(normalized_candidate)
        if text is None or stripped_text is None:
            continue
        for dependency in repository_service.stylus_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
            stripped_text=stripped_text,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in stylus_files:
        path = PurePosixPath(normalized_candidate)
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(stylus_files)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()
