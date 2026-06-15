from __future__ import annotations

from pathlib import Path, PurePosixPath

def _typst_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_non_operational_profile_path_for_ecosystems = (
        probe_module._is_non_operational_profile_path_for_ecosystems
    )
    _probe_language_for_path = probe_module._probe_language_for_path

    typst_files: list[str] = []
    typst_file_contents: dict[str, tuple[str, str]] = {}
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {
        "article.typ",
        "book.typ",
        "index.typ",
        "main.typ",
        "paper.typ",
        "presentation.typ",
        "report.typ",
        "slides.typ",
        "thesis.typ",
    }
    support_dirs = {
        "chapters",
        "content",
        "docs",
        "document",
        "documents",
        "figures",
        "images",
        "layouts",
        "packages",
        "shared",
        "styles",
        "templates",
        "themes",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        if candidate_name in repository_service.typst_adapter.TYPST_CONFIG_BASENAMES:
            stripped_text = repository_service.typst_adapter.strip_comments(text)
            if repository_service.typst_adapter.is_probable_typst_config(
                path=candidate_file,
                text=text,
                stripped_text=stripped_text,
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
                ecosystems={"typst"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "typst"
        ):
            continue
        stripped_text = repository_service.typst_adapter.strip_comments(text)
        if not repository_service.typst_adapter.is_probable_typst_source(
            path=candidate_file,
            text=text,
            stripped_text=stripped_text,
        ):
            continue
        typst_files.append(normalized_candidate)
        typst_file_contents[normalized_candidate] = (text, stripped_text)
        symbol_entries = repository_service.typst_adapter.iter_symbol_entries(
            text,
            stripped_text=stripped_text,
        )
        for alias in repository_service.typst_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
            text=text,
            stripped_text=stripped_text,
            symbol_entries=symbol_entries,
            validated_source=True,
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
    for normalized_candidate in typst_files:
        cached_source = typst_file_contents.get(normalized_candidate)
        if cached_source is None:
            continue
        text, stripped_text = cached_source
        for dependency in repository_service.typst_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
            stripped_text=stripped_text,
            validated_source=True,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
    for normalized_candidate in typst_files:
        path = PurePosixPath(normalized_candidate)
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(typst_files)[:12])
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _tex_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_non_operational_profile_path_for_ecosystems = (
        probe_module._is_non_operational_profile_path_for_ecosystems
    )
    _probe_language_for_path = probe_module._probe_language_for_path

    tex_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    config_paths: set[str] = set()
    preferred_basenames = {
        "article.tex",
        "cv.tex",
        "index.tex",
        "main.tex",
        "paper.tex",
        "presentation.tex",
        "report.tex",
        "resume.tex",
        "slides.tex",
        "thesis.tex",
    }
    support_dirs = {
        "appendix",
        "appendices",
        "chapter",
        "chapters",
        "content",
        "figures",
        "images",
        "partials",
        "section",
        "sections",
        "shared",
        "style",
        "styles",
        "template",
        "templates",
    }
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidate_name = PurePosixPath(normalized_candidate).name.lower()
        if candidate_name in repository_service.tex_adapter.TEX_CONFIG_BASENAMES:
            if repository_service.tex_adapter.is_probable_tex_config(
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
                ecosystems={"tex"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "tex"
        ):
            continue
        if not repository_service.tex_adapter.is_probable_tex_source(
            path=candidate_file,
            text=text,
        ):
            continue
        tex_files.append(normalized_candidate)
        for alias in repository_service.tex_adapter.module_aliases_for_path(
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
    for normalized_candidate in tex_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.tex_adapter.parse_dependencies_only(
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
    for normalized_candidate in tex_files:
        path = PurePosixPath(normalized_candidate)
        if path.suffix.lower() not in {".tex", ".ltx"}:
            continue
        candidate_parts = [part.lower() for part in path.parts[:-1]]
        if path.name.lower() in preferred_basenames:
            entrypoint_paths.add(normalized_candidate)
            continue
        if normalized_candidate not in imported_files and not any(
            part in support_dirs for part in candidate_parts
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        tex_document_files = sorted(
            normalized_candidate
            for normalized_candidate in tex_files
            if PurePosixPath(normalized_candidate).suffix.lower() in {".tex", ".ltx"}
        )
        entrypoint_paths.update(tex_document_files[:12] or sorted(tex_files)[:12])
    documentation_roots = {
        root
        for root in support_roots
        if PurePosixPath(root).name.lower()
        in (
            support_dirs
            | probe_module._DOCUMENTATION_OPERATIONAL_PATH_PARTS
        )
    }
    if documentation_roots:
        support_roots = {
            root
            for root in support_roots
            if not any(
                root != documentation_root
                and root.startswith(f"{documentation_root}/")
                for documentation_root in documentation_roots
            )
        }
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _rst_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_non_operational_profile_path_for_ecosystems = probe_module._is_non_operational_profile_path_for_ecosystems
    _probe_language_for_path = probe_module._probe_language_for_path

    rst_files: list[str] = []
    rst_text_by_path: dict[str, str] = {}
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"contents.rst", "guide.rst", "index.rst", "readme.rst", "reference.rst"}
    support_dirs = {
        "api",
        "doc",
        "docs",
        "documentation",
        "guide",
        "guides",
        "howto",
        "includes",
        "reference",
        "references",
        "source",
        "tutorial",
        "tutorials",
    }
    library_like_parts = {"_includes", "includes", "snippets"}

    def _rst_dependency_aliases(normalized_candidate: str) -> tuple[str, ...]:
        candidate_path = PurePosixPath(normalized_candidate)
        aliases = {
            normalized_candidate,
            candidate_path.name,
            str(candidate_path.with_suffix("")),
            str(candidate_path.with_suffix("")).replace("/", "."),
        }
        module_name = repository_service.rst_adapter.module_name_from_path(normalized_candidate)
        if module_name:
            aliases.add(module_name)
        return tuple(sorted(alias for alias in aliases if alias))

    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        candidate_path_obj = PurePosixPath(normalized_candidate)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"rst"},
                repo_path=repo_path,
            )
        ):
            continue
        if not repository_service.rst_adapter.has_rst_path_hints(candidate_path_obj) and (
            _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "rst"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.rst_adapter.is_probable_rst_source(path=candidate_file, text=text):
            continue
        rst_files.append(normalized_candidate)
        rst_text_by_path[normalized_candidate] = text
        for alias in _rst_dependency_aliases(normalized_candidate):
            module_index.setdefault(alias, normalized_candidate)
        candidate_parts = candidate_path_obj.parts
        lowered_parts = [part.lower() for part in candidate_parts[:-1]]
        for index, part in enumerate(lowered_parts):
            if part in support_dirs:
                support_roots.add("/".join(candidate_parts[: index + 1]))
        parent_dir = repository_service._normalize_repository_relative_path(str(candidate_path_obj.parent))
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in rst_files:
        text = rst_text_by_path.get(normalized_candidate)
        if text is None:
            continue
        for dependency in repository_service.rst_adapter.parse_dependencies_only(
            normalized_candidate,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ):
            if dependency.target_file and dependency.target_file != normalized_candidate:
                imported_files.add(dependency.target_file)
                parent_dir = repository_service._normalize_repository_relative_path(str(PurePosixPath(dependency.target_file).parent))
                if parent_dir:
                    support_roots.add(parent_dir)
    for normalized_candidate in rst_files:
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if candidate_parts.intersection(library_like_parts):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        rst_document_files = sorted(
            normalized_candidate for normalized_candidate in rst_files if PurePosixPath(normalized_candidate).name.lower() not in {"conf.py"}
        )
        entrypoint_paths.update(rst_document_files[:12] or sorted(rst_files)[:12])
    documentation_roots = {
        root
        for root in support_roots
        if PurePosixPath(root).name.lower() in support_dirs
    }
    if documentation_roots:
        support_roots = {
            root
            for root in support_roots
            if not any(
                root != documentation_root
                and root.startswith(f"{documentation_root}/")
                for documentation_root in documentation_roots
            )
        }
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _asciidoc_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_non_operational_profile_path_for_ecosystems = probe_module._is_non_operational_profile_path_for_ecosystems
    _probe_language_for_path = probe_module._probe_language_for_path

    asciidoc_files: list[str] = []
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {
        "contents.adoc",
        "contents.asciidoc",
        "guide.adoc",
        "guide.asciidoc",
        "index.adoc",
        "index.asciidoc",
        "readme.adoc",
        "readme.asciidoc",
        "reference.adoc",
        "reference.asciidoc",
    }
    support_dirs = {
        "api",
        "doc",
        "docs",
        "documentation",
        "guide",
        "guides",
        "howto",
        "includes",
        "modules",
        "partials",
        "reference",
        "references",
        "source",
        "tutorial",
        "tutorials",
    }
    library_like_parts = {"_includes", "attachments", "examples", "includes", "partials", "snippets"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"asciidoc"},
                repo_path=repo_path,
            )
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "asciidoc"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.asciidoc_adapter.is_probable_asciidoc_source(
            path=candidate_file,
            text=text,
        ):
            continue
        asciidoc_files.append(normalized_candidate)
        for alias in repository_service.asciidoc_adapter.module_aliases_for_path(
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
    documentation_roots = {
        root for root in support_roots if PurePosixPath(root).name.lower() in support_dirs
    }
    if documentation_roots:
        support_roots = {
            root
            for root in support_roots
            if not any(
                root != documentation_root
                and root.startswith(f"{documentation_root}/")
                for documentation_root in documentation_roots
            )
        }
    for normalized_candidate in asciidoc_files:
        try:
            text = (repo_path / normalized_candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dependency in repository_service.asciidoc_adapter.parse_dependencies_only(
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
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if candidate_parts.intersection(library_like_parts):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(asciidoc_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()


def _org_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    repository_service = probe_module.repository_service
    _is_non_operational_profile_path_for_ecosystems = probe_module._is_non_operational_profile_path_for_ecosystems

    org_files: list[str] = []
    loaded_candidate_text_by_path: dict[str, str] = {}
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {
        "contents.org",
        "guide.org",
        "index.org",
        "manual.org",
        "readme.org",
        "reference.org",
    }
    support_dirs = {
        "doc",
        "docs",
        "documentation",
        "guide",
        "guides",
        "includes",
        "manual",
        "manuals",
        "org",
        "reference",
        "references",
        "tutorial",
        "tutorials",
        "worg",
    }
    library_like_parts = {"_includes", "includes", "snippets", "styles"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(candidate_path)
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path_for_ecosystems(
                normalized_candidate,
                ecosystems={"org"},
                repo_path=repo_path,
            )
        ):
            continue
        if PurePosixPath(normalized_candidate).suffix.lower() not in repository_service.org_adapter.ORG_SUFFIXES:
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        loaded_candidate_text_by_path[normalized_candidate] = text
        if not repository_service.org_adapter.is_probable_org_source(path=candidate_file, text=text):
            continue
        org_files.append(normalized_candidate)
        for alias in repository_service.org_adapter.module_aliases_for_path(
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
    documentation_roots = {
        root for root in support_roots if PurePosixPath(root).name.lower() in support_dirs
    }
    if documentation_roots:
        support_roots = {
            root
            for root in support_roots
            if not any(
                root != documentation_root
                and root.startswith(f"{documentation_root}/")
                for documentation_root in documentation_roots
            )
        }
    for normalized_candidate in org_files:
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
        for dependency in repository_service.org_adapter.parse_dependencies_only(
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
        path = PurePosixPath(normalized_candidate)
        candidate_parts = {part.lower() for part in path.parts[:-1]}
        if candidate_parts.intersection(library_like_parts):
            continue
        if path.name.lower() in preferred_basenames or normalized_candidate not in imported_files:
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(org_files)[:12])
    return entrypoint_paths, {root for root in support_roots if root}, set()
