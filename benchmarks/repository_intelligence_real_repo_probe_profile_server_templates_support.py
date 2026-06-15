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


def _jinja_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    jinja_files: list[str] = []
    loaded_text_by_path: dict[str, str] = {}
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.j2",
        "index.jinja",
        "index.jinja2",
        "main.j2",
        "main.jinja",
        "main.jinja2",
    }
    support_dirs = {"jinja", "jinja2", "partials", "roles", "templates", "views"}
    library_like_parts = {"include", "includes", "macros", "partials", "shared", "snippets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "jinja"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.jinja_adapter.strip_comments(text)
        if not repository_service.jinja_adapter.is_probable_jinja_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        loaded_text_by_path[normalized_candidate] = text
        symbol_entries = repository_service.jinja_adapter.iter_symbol_entries(
            text,
            stripped_text=stripped_text,
        )
        jinja_files.append(normalized_candidate)
        for alias in repository_service.jinja_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
            stripped_text=stripped_text,
            symbol_entries=symbol_entries,
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
    for normalized_candidate in jinja_files:
        text = loaded_text_by_path.get(normalized_candidate)
        if text is None:
            continue
        for dependency in repository_service.jinja_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in jinja_files:
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
            for normalized_candidate in jinja_files
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


def _mako_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    mako_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.mako",
        "main.mako",
        "page.mako",
    }
    support_dirs = {"components", "fragments", "includes", "layouts", "partials", "templates", "views"}
    library_like_parts = {
        "common",
        "components",
        "fragments",
        "includes",
        "layouts",
        "macros",
        "partials",
        "shared",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "mako"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.mako_adapter.is_probable_mako_source(
            path=candidate_file,
            text=text,
        ):
            continue
        mako_files.append(normalized_candidate)
        for alias in repository_service.mako_adapter.module_aliases_for_path(
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
    for normalized_candidate in mako_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.mako_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in mako_files:
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
            for normalized_candidate in mako_files
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


def _liquid_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    liquid_files: list[str] = []
    liquid_text_by_path: dict[str, str] = {}
    liquid_stripped_text_by_path: dict[str, str] = {}
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.liquid",
        "main.liquid",
        "theme.liquid",
        "product.liquid",
        "collection.liquid",
        "article.liquid",
        "blog.liquid",
        "page.liquid",
    }
    support_dirs = {
        "includes",
        "layout",
        "layouts",
        "partials",
        "sections",
        "snippets",
        "templates",
        "_includes",
        "_layouts",
    }
    library_like_parts = {"includes", "partials", "snippets", "_includes"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "liquid"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.liquid_adapter.strip_comments(text)
        if not repository_service.liquid_adapter.is_probable_liquid_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        liquid_files.append(normalized_candidate)
        liquid_text_by_path[normalized_candidate] = text
        liquid_stripped_text_by_path[normalized_candidate] = stripped_text
        for alias in repository_service.liquid_adapter.module_aliases_for_path(
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
    for normalized_candidate in liquid_files:
        text = liquid_text_by_path.get(normalized_candidate)
        stripped_text = liquid_stripped_text_by_path.get(normalized_candidate)
        if text is None or stripped_text is None:
            continue
        for dependency in repository_service.liquid_adapter.parse_dependencies_only(
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
    for normalized_candidate in liquid_files:
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
            for normalized_candidate in liquid_files
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


def _handlebars_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    handlebars_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.hbs",
        "default.hbs",
        "home.hbs",
        "post.hbs",
        "page.hbs",
        "tag.hbs",
        "author.hbs",
        "error.hbs",
    }
    support_dirs = {"components", "includes", "layouts", "partials", "templates", "views"}
    library_like_parts = {"components", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "handlebars"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.handlebars_adapter.is_probable_handlebars_source(
            path=candidate_file,
            text=text,
        ):
            continue
        handlebars_files.append(normalized_candidate)
        for alias in repository_service.handlebars_adapter.module_aliases_for_path(
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
    for normalized_candidate in handlebars_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.handlebars_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in handlebars_files:
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
            for normalized_candidate in handlebars_files
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


def _mustache_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    mustache_files: list[str] = []
    loaded_candidate_text_by_path: dict[str, str] = {}
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "default.mustache",
        "error.mustache",
        "home.mustache",
        "index.mustache",
        "page.mustache",
        "post.mustache",
    }
    support_dirs = {"components", "includes", "layouts", "pages", "partials", "templates", "views"}
    library_like_parts = {"components", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "mustache"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        loaded_candidate_text_by_path[normalized_candidate] = text
        if not repository_service.mustache_adapter.is_probable_mustache_source(
            path=candidate_file,
            text=text,
        ):
            continue
        mustache_files.append(normalized_candidate)
        for alias in repository_service.mustache_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
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
    for normalized_candidate in mustache_files:
        text = loaded_candidate_text_by_path.get(normalized_candidate)
        if text is None:
            try:
                text = (repo_path / normalized_candidate).read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue
            loaded_candidate_text_by_path[normalized_candidate] = text
        for dependency in repository_service.mustache_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in mustache_files:
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
            for normalized_candidate in mustache_files
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


def _smarty_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    smarty_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "default.tpl",
        "home.tpl",
        "index.tpl",
        "layout.tpl",
        "page.tpl",
        "profiling.tpl",
    }
    support_dirs = {
        "_partials",
        "hooks",
        "layouts",
        "mails",
        "modules",
        "partials",
        "pdf",
        "templates",
        "themes",
        "views",
    }
    library_like_parts = {"_partials", "functions", "includes", "partials"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "smarty"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.smarty_adapter.is_probable_smarty_source(
            path=candidate_file,
            text=text,
        ):
            continue
        smarty_files.append(normalized_candidate)
        for alias in repository_service.smarty_adapter.module_aliases_for_path(
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
    for normalized_candidate in smarty_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.smarty_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in smarty_files:
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
            for normalized_candidate in smarty_files
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


def _nunjucks_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    nunjucks_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "index.njk",
        "index.nunj",
        "index.nunjucks",
        "main.njk",
        "main.nunj",
        "main.nunjucks",
        "base.njk",
        "layout.njk",
    }
    support_dirs = {
        "_components",
        "_includes",
        "_layouts",
        "components",
        "includes",
        "layouts",
        "partials",
        "snippets",
        "templates",
        "views",
    }
    library_like_parts = {"_components", "_includes", "components", "includes", "partials", "snippets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "nunjucks"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.nunjucks_adapter.is_probable_nunjucks_source(
            path=candidate_file,
            text=text,
        ):
            continue
        nunjucks_files.append(normalized_candidate)
        for alias in repository_service.nunjucks_adapter.module_aliases_for_path(
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
    for normalized_candidate in nunjucks_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.nunjucks_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in nunjucks_files:
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
            for normalized_candidate in nunjucks_files
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


def _twig_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    repository_service, _is_non_operational_profile_path, _probe_language_for_path = (
        _template_probe_deps()
    )

    twig_files: list[str] = []
    module_index: dict[str, str] = {}
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    preferred_basenames = {
        "base.html.twig",
        "default.html.twig",
        "index.html.twig",
        "layout.html.twig",
        "page.html.twig",
    }
    support_dirs = {
        "_components",
        "_includes",
        "_layouts",
        "blocks",
        "components",
        "includes",
        "layouts",
        "macros",
        "pages",
        "partials",
        "templates",
        "themes",
        "views",
    }
    library_like_parts = {
        "_components",
        "_includes",
        "blocks",
        "components",
        "includes",
        "macros",
        "partials",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "twig"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stripped_text = repository_service.twig_adapter._prepared_twig_source_text(
            path=candidate_file,
            text=text,
        )
        if stripped_text is None:
            continue
        twig_files.append(normalized_candidate)
        for alias in repository_service.twig_adapter.module_aliases_for_path(
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
    for normalized_candidate in twig_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.twig_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in twig_files:
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
            for normalized_candidate in twig_files
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
