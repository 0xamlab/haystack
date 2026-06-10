from __future__ import annotations

import json
import re
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


def _logtalk_profile_hints_from_candidates(
    repo_path: Path,
    candidate_file_paths: list[str],
) -> tuple[set[str], set[str], set[str]]:
    logtalk_files: list[str] = []
    config_paths: set[str] = set()
    module_index: dict[str, str] = {}
    support_roots: set[str] = set()
    imported_files: set[str] = set()
    entrypoint_paths: set[str] = set()
    preferred_basenames = {"loader.lgt", "loader.logtalk", "main.lgt", "main.logtalk"}
    for candidate_path in sorted(candidate_file_paths):
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or repository_service._is_test_path(normalized_candidate)
            or _is_non_operational_profile_path(normalized_candidate)
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "logtalk"
        ):
            continue
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            continue
        try:
            text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not repository_service.logtalk_adapter.is_probable_logtalk_source(
            path=candidate_file,
            text=text,
        ):
            continue
        logtalk_files.append(normalized_candidate)
        for alias in repository_service.logtalk_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path=normalized_candidate,
            stable_identifier=repository_service._stable_identifier,
        ):
            module_index.setdefault(alias, normalized_candidate)
    for normalized_candidate in logtalk_files:
        try:
            text = (repo_path / normalized_candidate).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue
        for target_name, _imports, _line_no in (
            repository_service.logtalk_adapter.parse_uses_statements(text)
        ):
            target_file = repository_service.logtalk_adapter.resolve_import(
                normalized_candidate,
                target_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if target_file and target_file != normalized_candidate:
                imported_files.add(target_file)
        for target_name, _line_no in repository_service.logtalk_adapter.parse_load_statements(
            text
        ):
            target_file = repository_service.logtalk_adapter.resolve_import(
                normalized_candidate,
                target_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if target_file and target_file != normalized_candidate:
                imported_files.add(target_file)
        for target_name, _line_no in repository_service.logtalk_adapter.parse_relation_statements(
            text
        ):
            target_file = repository_service.logtalk_adapter.resolve_import(
                normalized_candidate,
                target_name,
                module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
            if target_file and target_file != normalized_candidate:
                imported_files.add(target_file)
    for imported_file in imported_files:
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(imported_file).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for normalized_candidate in logtalk_files:
        if (
            PurePosixPath(normalized_candidate).name.lower() in preferred_basenames
            or normalized_candidate not in imported_files
        ):
            entrypoint_paths.add(normalized_candidate)
    if not entrypoint_paths:
        entrypoint_paths.update(sorted(logtalk_files)[:8])
    if not support_roots:
        for entrypoint_path in entrypoint_paths:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(entrypoint_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _smalltalk_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    search_roots: list[Path] = []
    support_roots: set[str] = set()
    for source_root in ("src", "repository", "packages", "tonel"):
        candidate_root = repo_path / project_dir / source_root
        if not candidate_root.is_dir():
            continue
        search_roots.append(candidate_root)
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root.relative_to(repo_path))
        )
        if normalized_root:
            support_roots.add(normalized_root)
    if not search_roots:
        search_root = repo_path / project_dir
        if search_root.is_dir():
            search_roots.append(search_root)
            normalized_root = repository_service._normalize_repository_relative_path(
                str(search_root.relative_to(repo_path))
            )
            if normalized_root:
                support_roots.add(normalized_root)
    entrypoint_paths: set[str] = set()
    fallback_paths: list[str] = []
    seen_paths: set[str] = set()
    for search_root in search_roots:
        for candidate in sorted(search_root.rglob("*.st")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            normalized_candidate = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not normalized_candidate
                or normalized_candidate in seen_paths
                or _probe_language_for_path(normalized_candidate, repo_path=repo_path)
                != "smalltalk"
                or not _is_operational_profile_entrypoint_candidate(
                    normalized_candidate,
                    repo_path=repo_path,
                )
            ):
                continue
            seen_paths.add(normalized_candidate)
            basename = PurePosixPath(normalized_candidate).name
            if basename.startswith("BaselineOf") and basename.endswith(".class.st"):
                entrypoint_paths.add(normalized_candidate)
                continue
            if basename != "package.st":
                fallback_paths.append(normalized_candidate)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(fallback_paths[:8])
    return entrypoint_paths, support_roots, config_paths


def _coffeescript_profile_hints(
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
    if not repository_service.coffeescript_adapter.is_probable_coffeescript_source(
        path=Path(normalized_path),
        text=manifest_text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    root_candidates = (
        project_dir,
        project_dir / "src",
        project_dir / "lib",
        project_dir / "app",
        project_dir / "scripts",
    )
    support_roots: set[str] = set()
    search_roots: list[Path] = []
    seen_search_roots: set[Path] = set()
    for candidate_root in root_candidates:
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
    if _is_operational_profile_entrypoint_candidate(normalized_path, repo_path=repo_path):
        entrypoint_paths.add(normalized_path)
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for suffix in ("*.coffee", "*.litcoffee"):
            for candidate in sorted(search_root.rglob(suffix)):
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or _probe_language_for_path(relative_path, repo_path=repo_path)
                    != "coffeescript"
                ):
                    continue
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
                if _is_operational_profile_entrypoint_candidate(
                    relative_path,
                    repo_path=repo_path,
                ):
                    entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _haxe_profile_hints(
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
    if not repository_service.haxe_adapter.is_probable_haxe_source(
        path=Path(normalized_path),
        text=manifest_text,
    ):
        return set(), set(), config_paths
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    source_roots: set[str] = set()
    support_roots: set[str] = {root_prefix.rstrip("/")}
    entrypoint_modules: set[str] = set()
    if normalized_path.lower().endswith(".hxml"):
        for raw_line in manifest_text.splitlines():
            stripped_line = raw_line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue
            if stripped_line.startswith(("-cp ", "--class-path ")):
                class_path = stripped_line.split(maxsplit=1)[1].strip().strip("\"'")
                normalized_root = repository_service._normalize_repository_relative_path(
                    str(project_dir / class_path)
                )
                if normalized_root and (repo_path / normalized_root).exists():
                    source_roots.add(normalized_root)
                    support_roots.add(normalized_root)
            elif stripped_line.startswith(("-main ", "--main ")):
                module_name = stripped_line.split(maxsplit=1)[1].strip().strip("\"'")
                if module_name:
                    entrypoint_modules.add(module_name)
    else:
        source_path_re = re.compile(
            r'<source\b[^>]*path=["\'](?P<path>[^"\']+)["\']',
            re.IGNORECASE,
        )
        main_re = re.compile(
            r'<app\b[^>]*main=["\'](?P<main>[^"\']+)["\']',
            re.IGNORECASE,
        )
        for match in source_path_re.finditer(manifest_text):
            normalized_root = repository_service._normalize_repository_relative_path(
                str(project_dir / str(match.group("path") or "").strip())
            )
            if normalized_root and (repo_path / normalized_root).exists():
                source_roots.add(normalized_root)
                support_roots.add(normalized_root)
        for match in main_re.finditer(manifest_text):
            module_name = str(match.group("main") or "").strip()
            if module_name:
                entrypoint_modules.add(module_name)
    if not source_roots:
        for relative_root in ("src", "source", "sources", "haxe"):
            normalized_root = repository_service._normalize_repository_relative_path(
                str(project_dir / relative_root)
            )
            if normalized_root and (repo_path / normalized_root).exists():
                source_roots.add(normalized_root)
                support_roots.add(normalized_root)
    entrypoint_paths: set[str] = set()
    fallback_paths: list[str] = []
    seen_paths: set[str] = set()

    def _consider_candidate(candidate_path: str, *, prefer: bool) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if (
            not normalized_candidate
            or normalized_candidate in seen_paths
            or _probe_language_for_path(normalized_candidate, repo_path=repo_path) != "haxe"
            or not _is_operational_profile_entrypoint_candidate(
                normalized_candidate,
                repo_path=repo_path,
            )
        ):
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            return
        seen_paths.add(normalized_candidate)
        if prefer:
            entrypoint_paths.add(normalized_candidate)
        else:
            fallback_paths.append(normalized_candidate)

    for module_name in sorted(entrypoint_modules):
        module_relative_path = module_name.replace(".", "/") + ".hx"
        for source_root in sorted(source_roots):
            _consider_candidate(f"{source_root}/{module_relative_path}", prefer=True)
    for source_root in sorted(source_roots):
        source_dir = repo_path / source_root
        if not source_dir.is_dir():
            continue
        for candidate in sorted(source_dir.rglob("*.hx")):
            _consider_candidate(str(candidate.relative_to(repo_path)), prefer=False)
    if not entrypoint_paths:
        for fallback_path in fallback_paths:
            if PurePosixPath(fallback_path).name == "Main.hx":
                entrypoint_paths.add(fallback_path)
        if not entrypoint_paths:
            entrypoint_paths.update(fallback_paths[:8])
    return entrypoint_paths, {root for root in support_roots if root}, config_paths


def _mql5_profile_hints(
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
        manifest_text = ""
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    search_roots: list[Path] = []
    seen_search_roots: set[Path] = set()
    for candidate_root in (
        project_dir,
        project_dir / "Experts",
        project_dir / "Indicators",
        project_dir / "Scripts",
        project_dir / "Services",
        project_dir / "Include",
        project_dir / "Libraries",
        project_dir / "MQL5",
        project_dir / "MQL5" / "Include",
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
    discovered_paths: set[str] = set()

    def _register_path(candidate_path: str) -> None:
        normalized_candidate = repository_service._normalize_repository_relative_path(
            candidate_path
        )
        if not normalized_candidate:
            return
        candidate_file = repo_path / normalized_candidate
        if not candidate_file.is_file() or candidate_file.is_symlink():
            return
        discovered_paths.add(normalized_candidate)
        parent_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_candidate).parent)
        )
        if parent_path:
            support_roots.add(parent_path)

    for entry in repository_service.mql5_adapter.project_file_entries(manifest_text):
        _register_path(str(project_dir / entry))
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for suffix in ("*.mq5", "*.mqh"):
            for candidate in sorted(search_root.rglob(suffix)):
                if not candidate.is_file() or candidate.is_symlink():
                    continue
                resolved_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if not resolved_path or _probe_language_for_path(
                    resolved_path,
                    repo_path=repo_path,
                ) != "mql5":
                    continue
                _register_path(resolved_path)
    entrypoint_paths = {
        candidate_path
        for candidate_path in discovered_paths
        if PurePosixPath(candidate_path).suffix.lower() == ".mq5"
        and _is_operational_profile_entrypoint_candidate(candidate_path, repo_path=repo_path)
    }
    return entrypoint_paths, support_roots, config_paths


def _gams_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "gams"
    ):
        return set(), set(), set()
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    parent_parts = {part.lower() for part in PurePosixPath(normalized_path).parts[:-1]}
    parent_path = repository_service._normalize_repository_relative_path(
        str(PurePosixPath(normalized_path).parent)
    )
    if parent_path:
        support_roots.add(parent_path)
    if PurePosixPath(normalized_path).suffix.lower() == ".gms" and (
        not parent_parts.intersection({"include", "includes"})
    ) and (
        _is_operational_profile_entrypoint_candidate(normalized_path, repo_path=repo_path)
    ):
        entrypoint_paths.add(normalized_path)
    search_root = repo_path
    if search_root.is_dir():
        for candidate in sorted(search_root.rglob("*.inc")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "gams"
            ):
                continue
            candidate_parent = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if candidate_parent:
                support_roots.add(candidate_parent)
    return entrypoint_paths, support_roots, config_paths


def _openscad_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "openscad"
    ):
        return set(), set(), set()
    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    parent_path = repository_service._normalize_repository_relative_path(
        str(PurePosixPath(normalized_path).parent)
    )
    if parent_path:
        support_roots.add(parent_path)
    parent_parts = {part.lower() for part in PurePosixPath(normalized_path).parts[:-1]}
    include_like_parts = {
        "include",
        "includes",
        "lib",
        "libs",
        "library",
        "libraries",
    }
    if not parent_parts.intersection(include_like_parts):
        if _is_operational_profile_entrypoint_candidate(normalized_path, repo_path=repo_path):
            entrypoint_paths.add(normalized_path)
    if repo_path.is_dir():
        for candidate in sorted(repo_path.rglob("*.scad")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "openscad"
            ):
                continue
            candidate_parent = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(relative_path).parent)
            )
            if candidate_parent:
                support_roots.add(candidate_parent)
            candidate_parts = {
                part.lower() for part in PurePosixPath(relative_path).parts[:-1]
            }
            if candidate_parts.intersection(
                {"include", "includes", "lib", "libs", "library", "libraries"}
            ):
                continue
            if _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path):
                entrypoint_paths.add(relative_path)
    if not entrypoint_paths and _is_operational_profile_entrypoint_candidate(
        normalized_path,
        repo_path=repo_path,
    ):
        entrypoint_paths.add(normalized_path)
    return entrypoint_paths, support_roots, config_paths


def _nix_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "nix"
    ):
        return set(), set(), set()
    manifest_parent = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    config_paths = {normalized_path}
    entrypoint_paths: set[str] = set()
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}nix",
        f"{root_prefix}modules",
        f"{root_prefix}overlays",
        f"{root_prefix}pkgs",
        f"{root_prefix}lib",
        f"{root_prefix}homeModules",
        f"{root_prefix}nixosModules",
    }
    for sibling_name in ("flake.nix", "default.nix", "shell.nix"):
        sibling_path = repository_service._normalize_repository_relative_path(
            str(manifest_parent / sibling_name)
        )
        if sibling_path and (repo_path / sibling_path).is_file():
            config_paths.add(sibling_path)
            if _is_operational_profile_entrypoint_candidate(
                sibling_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(sibling_path)
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for import_target in repository_service.nix_adapter.import_targets_for_text(text):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(manifest_parent / import_target)
        )
        if (
            not resolved_path
            or not (repo_path / resolved_path).is_file()
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "nix"
        ):
            continue
        support_root = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if support_root:
            support_roots.add(support_root)
        if _is_operational_profile_entrypoint_candidate(resolved_path, repo_path=repo_path):
            entrypoint_paths.add(resolved_path)
    return entrypoint_paths, support_roots, config_paths


def _starlark_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if (
        not manifest_file.is_file()
        or manifest_file.is_symlink()
        or _probe_language_for_path(normalized_path, repo_path=repo_path) != "starlark"
    ):
        return set(), set(), set()
    manifest_parent = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(manifest_parent) in {"", "."} else f"{manifest_parent}/"
    config_paths = {normalized_path}
    entrypoint_paths: set[str] = set()
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}bazel",
        f"{root_prefix}bzl",
        f"{root_prefix}defs",
        f"{root_prefix}extensions",
        f"{root_prefix}lib",
        f"{root_prefix}private",
        f"{root_prefix}rules",
        f"{root_prefix}toolchains",
    }
    if _is_operational_profile_entrypoint_candidate(normalized_path, repo_path=repo_path):
        entrypoint_paths.add(normalized_path)
    for sibling_name in (
        "BUILD",
        "BUILD.bazel",
        "MODULE.bazel",
        "WORKSPACE",
        "WORKSPACE.bazel",
    ):
        sibling_path = repository_service._normalize_repository_relative_path(
            str(manifest_parent / sibling_name)
        )
        if not sibling_path or not (repo_path / sibling_path).is_file():
            continue
        config_paths.add(sibling_path)
        if _is_operational_profile_entrypoint_candidate(sibling_path, repo_path=repo_path):
            entrypoint_paths.add(sibling_path)
    try:
        text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    starlark_module_index: dict[str, str] = {}
    for pattern in (
        "*.bzl",
        "*.star",
        "BUILD",
        "BUILD.bazel",
        "MODULE.bazel",
        "WORKSPACE",
        "WORKSPACE.bazel",
    ):
        for candidate in sorted(repo_path.rglob(pattern)):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if relative_path:
                starlark_module_index[relative_path] = relative_path
    include_like_parts = {"bzl", "defs", "extensions", "include", "lib", "private", "rules"}
    for load_target, _body, _line in repository_service.starlark_adapter.iter_load_statements(text):
        resolved_path = repository_service.starlark_adapter.resolve_load_target(
            current_file=normalized_path,
            import_target=load_target,
            module_index=starlark_module_index,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        )
        if (
            not resolved_path
            or not (repo_path / resolved_path).is_file()
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "starlark"
        ):
            continue
        support_root = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if support_root:
            support_roots.add(support_root)
        if _is_operational_profile_entrypoint_candidate(
            resolved_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(resolved_path)
    for candidate in sorted((repo_path / manifest_parent).rglob("*.bzl")):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        relative_path = repository_service._normalize_repository_relative_path(
            str(candidate.relative_to(repo_path))
        )
        if (
            not relative_path
            or _probe_language_for_path(relative_path, repo_path=repo_path) != "starlark"
        ):
            continue
        support_root = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(relative_path).parent)
        )
        if support_root:
            support_roots.add(support_root)
        parent_parts = {part.lower() for part in PurePosixPath(relative_path).parts[:-1]}
        if parent_parts.intersection(include_like_parts):
            continue
        if _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path):
            entrypoint_paths.add(relative_path)
        if len(entrypoint_paths) >= 8:
            break
    return entrypoint_paths, support_roots, config_paths


def _purescript_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    config_paths = {normalized_path}
    project_dir = PurePosixPath(normalized_path).parent
    support_roots: set[str] = set()
    search_roots: list[Path] = []
    seen_search_roots: set[Path] = set()
    for candidate_root in (
        project_dir / "src",
        project_dir / "app",
        project_dir / "test",
        project_dir / "tests",
        project_dir / "examples",
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
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob("*.purs")):
            if not candidate.is_file() or candidate.is_symlink():
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "purescript"
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
            if _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path):
                entrypoint_paths.add(relative_path)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths


def _rescript_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    if not manifest_file.is_file() or manifest_file.is_symlink():
        return set(), set(), set()
    try:
        manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        manifest_payload = {}
    project_dir = PurePosixPath(normalized_path).parent
    source_roots: list[PurePosixPath] = []
    raw_sources = manifest_payload.get("sources")
    if isinstance(raw_sources, list):
        for raw_source in raw_sources:
            if isinstance(raw_source, str):
                source_roots.append(project_dir / raw_source)
                continue
            if not isinstance(raw_source, dict):
                continue
            raw_dir = raw_source.get("dir")
            if isinstance(raw_dir, str) and raw_dir.strip():
                source_roots.append(project_dir / raw_dir.strip())
    if not source_roots:
        source_roots = [
            project_dir / "src",
            project_dir / "lib",
            project_dir / "test",
            project_dir / "tests",
            project_dir / "examples",
            project_dir / "scripts",
            project_dir,
        ]

    config_paths = {normalized_path}
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()
    fallback_paths: set[str] = set()
    seen_search_roots: set[Path] = set()
    for candidate_root in source_roots:
        normalized_root = repository_service._normalize_repository_relative_path(
            str(candidate_root)
        )
        search_root = repo_path / candidate_root
        resolved_search_root = search_root.resolve()
        if normalized_root and search_root.exists():
            support_roots.add(normalized_root)
        if not search_root.exists() or resolved_search_root in seen_search_roots:
            continue
        seen_search_roots.add(resolved_search_root)
        if not search_root.is_dir():
            continue
        for candidate in sorted(search_root.rglob("*")):
            if (
                not candidate.is_file()
                or candidate.is_symlink()
                or candidate.suffix.lower()
                not in repository_service.rescript_adapter.RESCRIPT_SUFFIXES
            ):
                continue
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                not relative_path
                or _probe_language_for_path(relative_path, repo_path=repo_path) != "rescript"
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
            if _is_operational_profile_entrypoint_candidate(relative_path, repo_path=repo_path):
                entrypoint_paths.add(relative_path)
    if not entrypoint_paths and fallback_paths:
        entrypoint_paths.update(sorted(fallback_paths)[:8])
    return entrypoint_paths, support_roots, config_paths
