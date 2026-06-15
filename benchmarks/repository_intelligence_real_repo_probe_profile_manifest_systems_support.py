from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree


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

    def __iter__(self):
        return iter(self._resolve())

    def __contains__(self, item):
        return item in self._resolve()

    def __getitem__(self, key):
        return self._resolve()[key]

    def __len__(self) -> int:
        return len(self._resolve())

    def __bool__(self) -> bool:
        return bool(self._resolve())


repository_service = _DeferredProbeAttr("repository_service")
_is_non_operational_profile_path = _DeferredProbeAttr("_is_non_operational_profile_path")
_is_non_operational_project_path = _DeferredProbeAttr("_is_non_operational_project_path")
_ruby_package_names_for_profile = _DeferredProbeAttr("_ruby_package_names_for_profile")
_ruby_package_entrypoint_paths = _DeferredProbeAttr("_ruby_package_entrypoint_paths")
_HASKELL_SOURCE_EXTENSIONS = _DeferredProbeAttr("_HASKELL_SOURCE_EXTENSIONS")
_SLN_PROJECT_RE = _DeferredProbeAttr("_SLN_PROJECT_RE")


def _append_manifest_field_value(
    *,
    values_by_field: dict[str, list[str]],
    field_name: str,
    raw_value: str,
) -> None:
    normalized_value = raw_value.strip()
    if not normalized_value:
        return
    if field_name in {"main", "main-is"}:
        values_by_field[field_name].append(normalized_value)
        return
    tokens = [
        token.strip()
        for comma_group in normalized_value.split(",")
        for token in comma_group.split()
        if token.strip()
    ]
    values_by_field[field_name].extend(tokens)


def _collect_manifest_field_values(
    text: str,
    *,
    field_names: set[str],
) -> dict[str, list[str]]:
    values_by_field = {field_name: [] for field_name in field_names}
    active_field: str | None = None
    active_indent: int | None = None
    for raw_line in text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith(("--", "#")):
            continue
        indented_line = raw_line.lstrip()
        current_indent = len(raw_line) - len(indented_line)
        field_match = re.match(r"^(?P<field>[A-Za-z0-9_-]+)\s*:\s*(?P<value>.*)$", indented_line)
        if field_match is not None:
            field_name = field_match.group("field").lower()
            if field_name in values_by_field:
                active_field = field_name
                active_indent = current_indent
                _append_manifest_field_value(
                    values_by_field=values_by_field,
                    field_name=field_name,
                    raw_value=field_match.group("value"),
                )
            else:
                active_field = None
                active_indent = None
            continue
        if active_field is None or active_indent is None or current_indent <= active_indent:
            active_field = None
            active_indent = None
            continue
        continuation = indented_line
        if continuation.startswith("- "):
            continuation = continuation[2:].strip()
        _append_manifest_field_value(
            values_by_field=values_by_field,
            field_name=active_field,
            raw_value=continuation,
        )
    return values_by_field


def _candidate_haskell_module_paths(
    *,
    project_dir: PurePosixPath,
    source_dir: str,
    module_name: str,
) -> tuple[str, ...]:
    normalized_module = module_name.strip()
    if not normalized_module:
        return ()
    source_prefix = repository_service._normalize_repository_relative_path(
        str(project_dir / source_dir)
    )
    module_path = normalized_module.replace(".", "/")
    candidate_paths: list[str] = []
    for extension in _HASKELL_SOURCE_EXTENSIONS:
        relative_candidate = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(source_prefix or "") / f"{module_path}{extension}")
        )
        if relative_candidate:
            candidate_paths.append(relative_candidate)
    return tuple(dict.fromkeys(candidate_paths))


def _haskell_cabal_profile_hints(
    repo_path: Path,
    cabal_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(cabal_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}app",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}app/Main.hs",
        f"{root_prefix}src/Main.hs",
        f"{root_prefix}lib/Main.hs",
    }
    config_paths = {normalized_path}
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    field_values = _collect_manifest_field_values(
        text,
        field_names={"hs-source-dirs", "main-is", "exposed-modules", "other-modules"},
    )
    raw_source_dirs = [
        source_dir
        for source_dir in field_values["hs-source-dirs"]
        if source_dir and not _is_non_operational_profile_path(source_dir)
    ] or ["."]
    for source_dir in raw_source_dirs:
        normalized_source_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / source_dir)
        )
        if normalized_source_dir and not _is_non_operational_profile_path(normalized_source_dir):
            support_roots.add(normalized_source_dir)
    for main_path in field_values["main-is"]:
        for source_dir in raw_source_dirs:
            resolved_path = repository_service._normalize_repository_relative_path(
                str(project_dir / source_dir / main_path)
            )
            if resolved_path:
                entrypoint_paths.add(resolved_path)
    for module_name in field_values["exposed-modules"] + field_values["other-modules"]:
        for source_dir in raw_source_dirs:
            entrypoint_paths.update(
                _candidate_haskell_module_paths(
                    project_dir=project_dir,
                    source_dir=source_dir,
                    module_name=module_name,
                )
            )
    return entrypoint_paths, support_roots, config_paths


def _haskell_package_yaml_profile_hints(
    repo_path: Path,
    package_yaml_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(package_yaml_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}app",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}app/Main.hs",
        f"{root_prefix}src/Main.hs",
        f"{root_prefix}lib/Main.hs",
    }
    config_paths = {normalized_path}
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    field_values = _collect_manifest_field_values(
        text,
        field_names={"source-dirs", "main", "exposed-modules", "other-modules"},
    )
    raw_source_dirs = [
        source_dir
        for source_dir in field_values["source-dirs"]
        if source_dir and not _is_non_operational_profile_path(source_dir)
    ] or ["src", "app", "lib"]
    for source_dir in raw_source_dirs:
        normalized_source_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / source_dir)
        )
        if normalized_source_dir and not _is_non_operational_profile_path(normalized_source_dir):
            support_roots.add(normalized_source_dir)
    for main_path in field_values["main"]:
        for source_dir in raw_source_dirs:
            resolved_path = repository_service._normalize_repository_relative_path(
                str(project_dir / source_dir / main_path)
            )
            if resolved_path:
                entrypoint_paths.add(resolved_path)
    for module_name in field_values["exposed-modules"] + field_values["other-modules"]:
        for source_dir in raw_source_dirs:
            entrypoint_paths.update(
                _candidate_haskell_module_paths(
                    project_dir=project_dir,
                    source_dir=source_dir,
                    module_name=module_name,
                )
            )
    return entrypoint_paths, support_roots, config_paths


def _haskell_project_profile_hints(
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}app",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}app/Main.hs",
        f"{root_prefix}src/Main.hs",
        f"{root_prefix}lib/Main.hs",
    }
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _csproj_profile_hints(
    csproj_path: str,
    *,
    repo_path: Path | None = None,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(csproj_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {root_prefix.rstrip("/")} if root_prefix else set()
    entrypoint_paths: set[str] = set()
    config_paths = {normalized_path}
    explicit_compile_entries = False
    if repo_path is not None:
        manifest_path = repo_path / normalized_path
        try:
            root = ElementTree.fromstring(manifest_path.read_text(encoding="utf-8", errors="replace"))
        except (ElementTree.ParseError, OSError):
            root = None
        if root is not None:
            for element in root.iter():
                include_value = str(element.attrib.get("Include") or "").strip()
                if not include_value:
                    continue
                resolved_path = repository_service._normalize_repository_relative_path(
                    str(project_dir / include_value.replace("\\", "/"))
                )
                if not resolved_path:
                    continue
                local_name = _xml_local_name(element.tag)
                if local_name == "Compile":
                    if _is_non_operational_profile_path(resolved_path):
                        continue
                    explicit_compile_entries = True
                    entrypoint_paths.add(resolved_path)
                    parent_dir = repository_service._normalize_repository_relative_path(
                        str(PurePosixPath(resolved_path).parent)
                    )
                    if parent_dir:
                        support_roots.add(parent_dir)
                    continue
                if local_name == "ProjectReference":
                    if _is_non_operational_profile_path(resolved_path):
                        continue
                    config_paths.add(resolved_path)
                    parent_dir = repository_service._normalize_repository_relative_path(
                        str(PurePosixPath(resolved_path).parent)
                    )
                    if parent_dir:
                        support_roots.add(parent_dir)
    if not explicit_compile_entries:
        support_roots.add(f"{root_prefix}src")
        entrypoint_paths.update(
            {
                f"{root_prefix}Program.cs",
                f"{root_prefix}Program.fs",
                f"{root_prefix}Program.vb",
                f"{root_prefix}Main.cs",
                f"{root_prefix}Main.fs",
                f"{root_prefix}Main.vb",
                f"{root_prefix}Startup.cs",
                f"{root_prefix}Startup.fs",
                f"{root_prefix}Startup.vb",
                f"{root_prefix}App.xaml.cs",
                f"{root_prefix}App.fs",
                f"{root_prefix}App.xaml.vb",
                f"{root_prefix}Application.vb",
            }
        )
    return entrypoint_paths, support_roots, config_paths


def _sln_project_paths(
    repo_path: Path,
    sln_path: str,
) -> tuple[str, ...]:
    normalized_path = repository_service._normalize_repository_relative_path(sln_path)
    if not normalized_path:
        return ()
    solution_path = repo_path / normalized_path
    try:
        text = solution_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    solution_dir = PurePosixPath(normalized_path).parent
    project_paths: list[str] = []
    seen: set[str] = set()
    for match in _SLN_PROJECT_RE.finditer(text):
        raw_project_path = match.group("path").replace("\\", "/").strip()
        if not raw_project_path:
            continue
        normalized_project_path = repository_service._normalize_repository_relative_path(
            str(solution_dir / raw_project_path)
        )
        if not normalized_project_path or normalized_project_path in seen:
            continue
        seen.add(normalized_project_path)
        project_paths.append(normalized_project_path)
    return tuple(project_paths)


def _sln_profile_hints(
    repo_path: Path,
    sln_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(sln_path)
    if not normalized_path:
        return set(), set(), set()
    entrypoint_paths: set[str] = set()
    support_roots: set[str] = set()
    config_paths: set[str] = {normalized_path}
    project_paths = _sln_project_paths(repo_path, normalized_path)
    for project_path in project_paths:
        project_entrypoints, project_roots, project_configs = _csproj_profile_hints(
            project_path,
            repo_path=repo_path,
        )
        entrypoint_paths.update(project_entrypoints)
        support_roots.update(project_roots)
        config_paths.update(project_configs)
    if entrypoint_paths or support_roots or len(config_paths) > 1:
        return entrypoint_paths, support_roots, config_paths
    return _csproj_profile_hints(normalized_path, repo_path=repo_path)


def _gemfile_profile_hints(
    repo_path: Path,
    gemfile_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(gemfile_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}lib",
        f"{root_prefix}app",
        f"{root_prefix}bin",
        f"{root_prefix}exe",
    }
    package_names = _ruby_package_names_for_profile(
        repo_path=repo_path,
        normalized_path=normalized_path,
    )
    entrypoint_paths = _ruby_package_entrypoint_paths(
        repo_path=repo_path,
        project_dir=project_dir,
        package_names=package_names,
    )
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _erlang_project_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    config_posix_path = PurePosixPath(normalized_path)
    project_dir = config_posix_path.parent
    if config_posix_path.name.lower().endswith(".app.src") and project_dir.name == "src":
        project_dir = project_dir.parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}include",
    }
    entrypoint_paths: set[str] = set()
    project_root = repo_path / project_dir
    source_root = project_root / "src"
    if source_root.is_dir():
        for candidate in sorted(source_root.glob("*.erl")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if relative_path and not repository_service._is_test_path(relative_path):
                entrypoint_paths.add(relative_path)
    apps_root = project_root / "apps"
    if apps_root.is_dir():
        support_roots.add(f"{root_prefix}apps")
        for app_dir in sorted(child for child in apps_root.iterdir() if child.is_dir()):
            for subdir_name in ("src", "include"):
                subdir = app_dir / subdir_name
                if not subdir.is_dir():
                    continue
                relative_root = repository_service._normalize_repository_relative_path(
                    str(subdir.relative_to(repo_path))
                )
                if relative_root:
                    support_roots.add(relative_root)
                if subdir_name != "src":
                    continue
                for candidate in sorted(subdir.glob("*.erl")):
                    relative_path = repository_service._normalize_repository_relative_path(
                        str(candidate.relative_to(repo_path))
                    )
                    if relative_path and not repository_service._is_test_path(relative_path):
                        entrypoint_paths.add(relative_path)
    return entrypoint_paths, support_roots, config_paths


def _nim_project_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
        f"{root_prefix}source",
    }
    entrypoint_paths: set[str] = set()
    project_root = repo_path / project_dir
    source_dirs = [project_root / "src", project_root / "lib", project_root / "source"]
    for source_dir in source_dirs:
        if not source_dir.is_dir():
            continue
        relative_root = repository_service._normalize_repository_relative_path(
            str(source_dir.relative_to(repo_path))
        )
        if relative_root:
            support_roots.add(relative_root)
        for candidate in sorted(source_dir.rglob("*.nim")):
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)

    package_roots: list[Path] = []
    config_basename = PurePosixPath(normalized_path).name.lower()
    if config_basename.endswith(".nimble"):
        package_candidates = {
            PurePosixPath(normalized_path).stem,
            re.sub(r"[^a-z0-9_]+", "_", repo_path.name.lower()).strip("_"),
        }
        for package_name in sorted(name for name in package_candidates if name):
            root_module = project_root / f"{package_name}.nim"
            if root_module.is_file():
                relative_path = repository_service._normalize_repository_relative_path(
                    str(root_module.relative_to(repo_path))
                )
                if (
                    relative_path
                    and not repository_service._is_test_path(relative_path)
                    and not _is_non_operational_profile_path(relative_path)
                ):
                    entrypoint_paths.add(relative_path)
            package_root = project_root / package_name
            if not package_root.is_dir():
                continue
            package_roots.append(package_root)
    for package_root in package_roots:
        relative_root = repository_service._normalize_repository_relative_path(
            str(package_root.relative_to(repo_path))
        )
        if relative_root:
            support_roots.add(relative_root)
        for candidate in sorted(package_root.rglob("*.nim")):
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
    for candidate in sorted(project_root.glob("*.nim")):
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
