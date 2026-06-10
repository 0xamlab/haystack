from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


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
_is_non_operational_project_path = _DeferredProbeAttr("_is_non_operational_project_path")
_ADA_PROJECT_FIELD_RE = _DeferredProbeAttr("_ADA_PROJECT_FIELD_RE")
_QUOTED_SEGMENT_RE = _DeferredProbeAttr("_QUOTED_SEGMENT_RE")


def _normalized_ada_unit_stem(raw_name: str | None) -> str | None:
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None
    normalized_name = re.sub(r"[^a-z0-9]+", "-", raw_name.lower()).strip("-")
    return normalized_name or None


def _ada_project_quoted_values(text: str, field: str) -> tuple[str, ...]:
    values: list[str] = []
    for match in _ADA_PROJECT_FIELD_RE.finditer(text):
        current_field = str(match.group("field") or "").strip().lower()
        if current_field != field.lower():
            continue
        values.extend(
            segment.group("value")
            for segment in _QUOTED_SEGMENT_RE.finditer(str(match.group("body") or ""))
        )
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def _ada_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}ada",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}main.adb",
        f"{root_prefix}src/main.adb",
        f"{root_prefix}source/main.adb",
        f"{root_prefix}ada/main.adb",
    }
    config_paths = {normalized_path}
    unit_stems: set[str] = set()

    if manifest_path.name.lower() == "alire.toml":
        if tomllib is not None:
            try:
                payload = tomllib.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, tomllib.TOMLDecodeError):
                payload = {}
        else:
            payload = {}
        if isinstance(payload, dict):
            normalized_name = _normalized_ada_unit_stem(payload.get("name"))
            if normalized_name:
                unit_stems.add(normalized_name)
            raw_executables = payload.get("executables")
            if isinstance(raw_executables, list):
                for executable in raw_executables:
                    normalized_executable = _normalized_ada_unit_stem(executable)
                    if normalized_executable:
                        unit_stems.add(normalized_executable)
            raw_project_files = payload.get("project-files")
            if isinstance(raw_project_files, list):
                for project_file in raw_project_files:
                    if not isinstance(project_file, str) or not project_file.strip():
                        continue
                    resolved_project_path = repository_service._normalize_repository_relative_path(
                        str(project_dir / project_file.strip())
                    )
                    if resolved_project_path and (repo_path / resolved_project_path).is_file():
                        config_paths.add(resolved_project_path)
    else:
        try:
            project_text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            project_text = ""
        for raw_source_dir in _ada_project_quoted_values(project_text, "source_dirs"):
            normalized_root = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_source_dir)
            )
            if normalized_root:
                support_roots.add(normalized_root)
        for raw_main_file in _ada_project_quoted_values(project_text, "main"):
            normalized_main_path = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_main_file)
            )
            if normalized_main_path:
                entrypoint_paths.add(normalized_main_path)
        for raw_source_file in _ada_project_quoted_values(project_text, "source_files"):
            normalized_source_path = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_source_file)
            )
            if normalized_source_path:
                entrypoint_paths.add(normalized_source_path)
        normalized_name = _normalized_ada_unit_stem(PurePosixPath(normalized_path).stem)
        if normalized_name:
            unit_stems.add(normalized_name)

    for support_root in tuple(sorted(support_roots)):
        normalized_support_root = repository_service._normalize_repository_relative_path(
            support_root
        )
        if not normalized_support_root:
            continue
        support_roots.add(normalized_support_root)
        for unit_stem in unit_stems:
            entrypoint_paths.add(f"{normalized_support_root}/{unit_stem}.adb")
            entrypoint_paths.add(f"{normalized_support_root}/{unit_stem}.ads")
            entrypoint_paths.add(f"{normalized_support_root}/{unit_stem}.ada")

    return entrypoint_paths, support_roots, config_paths


def _dub_sdl_quoted_values(text: str, key: str) -> tuple[str, ...]:
    values: list[str] = []
    for raw_line in text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("//"):
            continue
        if not stripped_line.startswith(f"{key} "):
            continue
        values.extend(match.group(1) for match in re.finditer(r'"([^"]+)"', stripped_line))
    return tuple(values)


def _normalized_d_package_name(raw_name: str | None) -> str | None:
    if not isinstance(raw_name, str) or not raw_name.strip():
        return None
    normalized_name = re.sub(r"[^a-z0-9_]+", "_", raw_name.lower()).strip("_")
    return normalized_name or None


def _dub_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_path = repo_path / normalized_path
    package_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(package_dir) in {"", "."} else f"{package_dir}/"
    config_paths = {normalized_path}
    package_name: str | None = None
    source_roots: set[str] = set()
    configuration_names: set[str] = set()

    if manifest_path.name == "dub.json":
        payload = repository_service._safe_load_jsonc_dict(manifest_path)
        if payload is None:
            return set(), set(), set()
        package_name = payload.get("name") if isinstance(payload.get("name"), str) else None
        for field in ("sourcePaths", "importPaths"):
            raw_value = payload.get(field)
            raw_values = raw_value if isinstance(raw_value, list) else [raw_value]
            for item in raw_values:
                if isinstance(item, str) and item.strip():
                    normalized_root = repository_service._normalize_repository_relative_path(
                        str(package_dir / item.strip())
                    )
                    if normalized_root:
                        source_roots.add(normalized_root)
        raw_configurations = payload.get("configurations")
        if isinstance(raw_configurations, list):
            for entry in raw_configurations:
                if not isinstance(entry, dict):
                    continue
                for field in ("name", "targetName"):
                    raw_value = entry.get(field)
                    if isinstance(raw_value, str) and raw_value.strip():
                        configuration_names.add(raw_value.strip())
        raw_subpackages = payload.get("subPackages")
        if isinstance(raw_subpackages, list):
            for raw_value in raw_subpackages:
                if not isinstance(raw_value, str) or not raw_value.strip():
                    continue
                subpackage_dir = repository_service._normalize_repository_relative_path(
                    str(package_dir / raw_value.strip())
                )
                if not subpackage_dir:
                    continue
                for manifest_name in ("dub.json", "dub.sdl"):
                    candidate_manifest = repository_service._normalize_repository_relative_path(
                        f"{subpackage_dir}/{manifest_name}"
                    )
                    if candidate_manifest and (repo_path / candidate_manifest).is_file():
                        config_paths.add(candidate_manifest)
                for candidate_root in ("src", "source"):
                    normalized_root = repository_service._normalize_repository_relative_path(
                        f"{subpackage_dir}/{candidate_root}"
                    )
                    if normalized_root:
                        source_roots.add(normalized_root)
    else:
        try:
            sdl_text = manifest_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return set(), set(), set()
        package_name = next(iter(_dub_sdl_quoted_values(sdl_text, "name")), None)
        for field in ("sourcePaths", "importPaths"):
            for raw_value in _dub_sdl_quoted_values(sdl_text, field):
                normalized_root = repository_service._normalize_repository_relative_path(
                    str(package_dir / raw_value.strip())
                )
                if normalized_root:
                    source_roots.add(normalized_root)
        configuration_names.update(_dub_sdl_quoted_values(sdl_text, "targetName"))

    if not source_roots:
        for candidate_root in ("src", "source"):
            normalized_root = repository_service._normalize_repository_relative_path(
                f"{root_prefix}{candidate_root}"
            )
            if normalized_root:
                source_roots.add(normalized_root)

    support_roots = set(source_roots)
    entrypoint_paths: set[str] = set()
    normalized_name = _normalized_d_package_name(package_name)
    for source_root in sorted(source_roots):
        entrypoint_paths.add(f"{source_root}/main.d")
        entrypoint_paths.add(f"{source_root}/app.d")
        if normalized_name:
            entrypoint_paths.add(f"{source_root}/{normalized_name}.d")
            entrypoint_paths.add(f"{source_root}/{normalized_name}/main.d")
            entrypoint_paths.add(f"{source_root}/{normalized_name}/{normalized_name}.d")
        for configuration_name in sorted(configuration_names):
            normalized_configuration = _normalized_d_package_name(configuration_name)
            if not normalized_configuration:
                continue
            entrypoint_paths.add(f"{source_root}/{normalized_configuration}.d")
            entrypoint_paths.add(f"{source_root}/{normalized_configuration}/main.d")
            if normalized_name:
                entrypoint_paths.add(f"{source_root}/{normalized_name}/{normalized_configuration}.d")
                entrypoint_paths.add(
                    f"{source_root}/{normalized_name}/{normalized_configuration}/main.d"
                )
    return entrypoint_paths, support_roots, config_paths
