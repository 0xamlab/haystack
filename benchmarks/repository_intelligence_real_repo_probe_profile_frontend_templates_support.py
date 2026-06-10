from __future__ import annotations

from pathlib import Path, PurePosixPath


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _template_probe_deps():
    probe_module = _probe_module()
    return (
        probe_module.repository_service,
        probe_module._is_non_operational_profile_path,
        probe_module._probe_language_for_path,
    )


def _haml_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    haml_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "application.html.haml",
        "index.html.haml",
        "home.html.haml",
        "show.html.haml",
        "page.html.haml",
    }
    support_dirs = {"app", "views", "layouts", "pages", "partials", "shared", "components", "templates"}
    library_like_parts = {"partials", "shared", "components"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "haml"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.haml_adapter.is_probable_haml_source(
            path=candidate_file,
            text=text,
        ):
            continue
        haml_files.append(normalized_candidate)
        for alias in repository_service.haml_adapter.module_aliases_for_path(
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
    for normalized_candidate in haml_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.haml_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in haml_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in haml_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _slim_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    slim_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "application.html.slim",
        "index.html.slim",
        "home.html.slim",
        "show.html.slim",
        "page.html.slim",
    }
    support_dirs = {"app", "views", "layouts", "pages", "partials", "shared", "components", "templates"}
    library_like_parts = {"partials", "shared", "components"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "slim"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.slim_adapter.is_probable_slim_source(
            path=candidate_file,
            text=text,
        ):
            continue
        slim_files.append(normalized_candidate)
        for alias in repository_service.slim_adapter.module_aliases_for_path(
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
    for normalized_candidate in slim_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.slim_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in slim_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in slim_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _erb_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    erb_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "application.html.erb",
        "index.html.erb",
        "home.html.erb",
        "show.html.erb",
        "page.html.erb",
    }
    support_dirs = {"app", "views", "layouts", "pages", "partials", "shared", "components", "templates"}
    library_like_parts = {"partials", "shared", "components"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "erb"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.erb_adapter.is_probable_erb_source(
            path=candidate_file,
            text=text,
        ):
            continue
        erb_files.append(normalized_candidate)
        for alias in repository_service.erb_adapter.module_aliases_for_path(
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
    for normalized_candidate in erb_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.erb_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in erb_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in erb_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _pug_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    pug_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.pug",
        "index.jade",
        "layout.pug",
        "layout.jade",
        "default.pug",
        "default.jade",
    }
    support_dirs = {
        "components",
        "includes",
        "layouts",
        "mixins",
        "pages",
        "partials",
        "templates",
        "views",
    }
    library_like_parts = {"components", "includes", "mixins", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "pug"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.pug_adapter.is_probable_pug_source(
            path=candidate_file,
            text=text,
        ):
            continue
        pug_files.append(normalized_candidate)
        for alias in repository_service.pug_adapter.module_aliases_for_path(
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
    for normalized_candidate in pug_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.pug_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in pug_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in pug_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _ejs_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    ejs_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.ejs",
        "layout.ejs",
        "default.ejs",
        "home.ejs",
        "page.ejs",
        "error.ejs",
    }
    support_dirs = {
        "components",
        "includes",
        "layouts",
        "pages",
        "partials",
        "templates",
        "views",
    }
    library_like_parts = {"components", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "ejs"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.ejs_adapter.is_probable_ejs_source(
            path=candidate_file,
            text=text,
        ):
            continue
        ejs_files.append(normalized_candidate)
        for alias in repository_service.ejs_adapter.module_aliases_for_path(
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
    for normalized_candidate in ejs_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.ejs_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in ejs_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in ejs_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _blade_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    blade_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "app.blade.php",
        "home.blade.php",
        "index.blade.php",
        "layout.blade.php",
        "welcome.blade.php",
    }
    support_dirs = {
        "components",
        "includes",
        "layouts",
        "partials",
        "resources",
        "sections",
        "views",
    }
    library_like_parts = {"components", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "blade"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.blade_adapter.is_probable_blade_source(
            path=candidate_file,
            text=text,
        ):
            continue
        blade_files.append(normalized_candidate)
        for alias in repository_service.blade_adapter.module_aliases_for_path(
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
    for normalized_candidate in blade_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.blade_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in blade_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in blade_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _vue_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    vue_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"App.vue", "app.vue", "Main.vue", "main.vue", "Index.vue", "index.vue"}
    support_dirs = {"components", "composables", "layouts", "pages", "views"}
    library_like_parts = {"components", "composables", "layouts"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "vue"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.vue_adapter.is_probable_vue_source(
            path=candidate_file,
            text=text,
        ):
            continue
        vue_files.append(normalized_candidate)
        for alias in repository_service.vue_adapter.module_aliases_for_path(
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
    for normalized_candidate in vue_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.vue_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in vue_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in vue_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _svelte_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    svelte_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "App.svelte",
        "app.svelte",
        "+page.svelte",
        "+layout.svelte",
        "+error.svelte",
    }
    support_dirs = {"src", "lib", "routes", "components"}
    library_like_parts = {"lib", "components"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "svelte"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.svelte_adapter.is_probable_svelte_source(
            path=candidate_file,
            text=text,
        ):
            continue
        svelte_files.append(normalized_candidate)
        for alias in repository_service.svelte_adapter.module_aliases_for_path(
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
    for normalized_candidate in svelte_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.svelte_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in svelte_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in svelte_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _astro_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    astro_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {"index.astro", "Index.astro", "404.astro"}
    support_dirs = {"src", "components", "layouts", "pages", "content"}
    library_like_parts = {"components", "layouts", "content"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "astro"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.astro_adapter.is_probable_astro_source(
            path=candidate_file,
            text=text,
        ):
            continue
        astro_files.append(normalized_candidate)
        for alias in repository_service.astro_adapter.module_aliases_for_path(
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
    for normalized_candidate in astro_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for dependency in repository_service.astro_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in astro_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if (
            repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or candidate_parts.intersection(library_like_parts)
        ):
            continue
        if path.name in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(
            normalized_candidate
            for normalized_candidate in astro_files
            if not set(map(str.lower, PurePosixPath(normalized_candidate).parts[:-1])).intersection(
                library_like_parts
            )
        )
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, set()
