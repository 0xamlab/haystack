from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any


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


repository_service = _DeferredProbeAttr('repository_service')
_safe_load_toml_dict = _DeferredProbeAttr('_safe_load_toml_dict')
_is_non_operational_profile_path = _DeferredProbeAttr('_is_non_operational_profile_path')
_is_non_operational_project_path = _DeferredProbeAttr('_is_non_operational_project_path')
_probe_language_for_path = _DeferredProbeAttr('_probe_language_for_path')
_ruby_package_names_for_profile = _DeferredProbeAttr('_ruby_package_names_for_profile')
_ruby_package_entrypoint_paths = _DeferredProbeAttr('_ruby_package_entrypoint_paths')
_QUOTED_SEGMENT_RE = _DeferredProbeAttr('_QUOTED_SEGMENT_RE')
_ZIG_SOURCE_TOKEN_RE = _DeferredProbeAttr('_ZIG_SOURCE_TOKEN_RE')
_SLN_PROJECT_RE = _DeferredProbeAttr('_SLN_PROJECT_RE')
_HASKELL_SOURCE_EXTENSIONS = _DeferredProbeAttr('_HASKELL_SOURCE_EXTENSIONS')
_CLOJURE_MAIN_RE = _DeferredProbeAttr('_CLOJURE_MAIN_RE')
_CLOJURE_QUOTED_STRING_RE = _DeferredProbeAttr('_CLOJURE_QUOTED_STRING_RE')
_CLOJURE_VECTOR_FIELD_RE = _DeferredProbeAttr('_CLOJURE_VECTOR_FIELD_RE')
_C_FAMILY_SOURCE_TOKEN_RE = _DeferredProbeAttr('_C_FAMILY_SOURCE_TOKEN_RE')
_POWERSHELL_MANIFEST_FIELD_RE = _DeferredProbeAttr('_POWERSHELL_MANIFEST_FIELD_RE')
_POWERSHELL_MANIFEST_LIST_RE = _DeferredProbeAttr('_POWERSHELL_MANIFEST_LIST_RE')
from benchmarks.repository_intelligence_real_repo_probe_profile_manifest_ada_d_support import (
    _ada_profile_hints as _ada_profile_hints_support,
    _ada_project_quoted_values as _ada_project_quoted_values_support,
    _dub_profile_hints as _dub_profile_hints_support,
    _dub_sdl_quoted_values as _dub_sdl_quoted_values_support,
    _normalized_ada_unit_stem as _normalized_ada_unit_stem_support,
    _normalized_d_package_name as _normalized_d_package_name_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_manifest_systems_support import (
    _append_manifest_field_value as _append_manifest_field_value_support,
    _candidate_haskell_module_paths as _candidate_haskell_module_paths_support,
    _collect_manifest_field_values as _collect_manifest_field_values_support,
    _csproj_profile_hints as _csproj_profile_hints_support,
    _erlang_project_profile_hints as _erlang_project_profile_hints_support,
    _gemfile_profile_hints as _gemfile_profile_hints_support,
    _haskell_cabal_profile_hints as _haskell_cabal_profile_hints_support,
    _haskell_package_yaml_profile_hints as _haskell_package_yaml_profile_hints_support,
    _haskell_project_profile_hints as _haskell_project_profile_hints_support,
    _nim_project_profile_hints as _nim_project_profile_hints_support,
    _sln_profile_hints as _sln_profile_hints_support,
    _sln_project_paths as _sln_project_paths_support,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_manifest_build_support import (
    _c_family_manifest_ecosystems as _c_family_manifest_ecosystems_support,
    _cmake_like_profile_hints as _cmake_like_profile_hints_support,
    _cmake_profile_hints as _cmake_profile_hints_support,
    _composer_profile_hints as _composer_profile_hints_support,
    _gradle_profile_hints as _gradle_profile_hints_support,
    _gradle_project_root_hints as _gradle_project_root_hints_support,
    _iter_gradle_included_project_roots as _iter_gradle_included_project_roots_support,
    _meson_profile_hints as _meson_profile_hints_support,
    _mix_profile_hints as _mix_profile_hints_support,
    _normalize_gradle_project_root as _normalize_gradle_project_root_support,
    _podspec_profile_hints as _podspec_profile_hints_support,
    _powershell_profile_hints as _powershell_profile_hints_support,
    _profile_root_from_glob_pattern as _profile_root_from_glob_pattern_support,
    _qmake_profile_hints as _qmake_profile_hints_support,
    _qsharp_profile_hints as _qsharp_profile_hints_support,
    _scala_build_profile_hints as _scala_build_profile_hints_support,
    _scala_build_support_roots as _scala_build_support_roots_support,
    _swift_package_profile_hints as _swift_package_profile_hints_support,
    _zig_build_profile_hints as _zig_build_profile_hints_support,
)


def _package_json_export_targets(value: Any) -> set[str]:
    targets: set[str] = set()
    if isinstance(value, str):
        targets.add(value)
        return targets
    if isinstance(value, list):
        for item in value:
            targets.update(_package_json_export_targets(item))
        return targets
    if isinstance(value, dict):
        for item in value.values():
            targets.update(_package_json_export_targets(item))
    return targets


def _package_json_profile_hints(
    repo_path: Path,
    package_json_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(package_json_path)
    if not normalized_path:
        return set(), set(), set()
    package_json = repository_service._safe_load_jsonc_dict(repo_path / normalized_path)
    if package_json is None:
        return set(), set(), set()
    package_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(package_dir) in {"", "."} else f"{package_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
    }
    entrypoint_paths: set[str] = set()
    config_paths = {normalized_path}

    def _add_target_entrypoint(raw_target: str) -> None:
        normalized_target = repository_service._normalize_repository_relative_path(
            str(package_dir / raw_target.strip())
        )
        if not normalized_target:
            return
        entrypoint_paths.add(normalized_target)
        target_parent = PurePosixPath(normalized_target).parent
        normalized_parent = repository_service._normalize_repository_relative_path(
            str(target_parent)
        )
        if normalized_parent:
            support_roots.add(normalized_parent)

    for field in ("main", "module", "browser", "types", "typings", "source"):
        raw_value = package_json.get(field)
        if isinstance(raw_value, str) and raw_value.strip():
            _add_target_entrypoint(raw_value)
    raw_bin = package_json.get("bin")
    if isinstance(raw_bin, str) and raw_bin.strip():
        _add_target_entrypoint(raw_bin)
    elif isinstance(raw_bin, dict):
        for raw_value in raw_bin.values():
            if isinstance(raw_value, str) and raw_value.strip():
                _add_target_entrypoint(raw_value)
    for export_target in _package_json_export_targets(package_json.get("exports")):
        if export_target.strip().startswith("."):
            _add_target_entrypoint(export_target)
    scripts = package_json.get("scripts")
    if isinstance(scripts, dict):
        script_text = " ".join(
            str(value) for value in scripts.values() if isinstance(value, str) and value.strip()
        ).lower()
        frontend_tokens = ("vite", "react-scripts", "next", "nuxt", "astro", "vue-cli-service")
        if any(token in script_text for token in frontend_tokens):
            support_roots.update(
                f"{root_prefix}{name}" for name in ("app", "components", "composables", "layouts", "pages", "routes", "client", "views")
            )
            entrypoint_paths.update(
                {
                    f"{root_prefix}src/main.tsx",
                    f"{root_prefix}src/main.jsx",
                    f"{root_prefix}src/main.ts",
                    f"{root_prefix}src/main.js",
                    f"{root_prefix}src/index.tsx",
                    f"{root_prefix}src/index.jsx",
                    f"{root_prefix}src/index.ts",
                    f"{root_prefix}src/index.js",
                    f"{root_prefix}src/App.tsx",
                    f"{root_prefix}src/App.jsx",
                    f"{root_prefix}src/App.vue",
                    f"{root_prefix}src/app.vue",
                    f"{root_prefix}src/app/page.tsx",
                    f"{root_prefix}src/pages/Index.tsx",
                    f"{root_prefix}src/pages/index.vue",
                    f"{root_prefix}pages/index.vue",
                }
            )
        if any(token in script_text for token in ("node", "tsx", "ts-node", "nodemon")):
            support_roots.update(
                f"{root_prefix}{name}" for name in ("server", "routes", "client")
            )
            entrypoint_paths.update(
                {
                    f"{root_prefix}src/main.ts",
                    f"{root_prefix}src/index.ts",
                    f"{root_prefix}src/server.ts",
                    f"{root_prefix}src/server.js",
                    f"{root_prefix}server.ts",
                    f"{root_prefix}server.js",
                }
            )
    return entrypoint_paths, support_roots, config_paths


def _tsconfig_profile_hints(
    repo_path: Path,
    config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(config_path)
    if not normalized_path:
        return set(), set(), set()
    config_payload = repository_service._safe_load_jsonc_dict(repo_path / normalized_path)
    compiler_options = repository_service._resolved_tsconfig_compiler_options(
        root_path=repo_path,
        config_file_path=normalized_path,
    )
    config_dir = PurePosixPath(normalized_path).parent
    support_roots = {
        repository_service._normalize_repository_relative_path(str(config_dir)) or "",
    }
    entrypoint_paths: set[str] = set()
    config_paths = {normalized_path}
    base_url = compiler_options.get("baseUrl")
    if isinstance(base_url, str) and base_url.strip():
        support_roots.add(
            repository_service._normalize_repository_relative_pattern(
                str(config_dir / base_url.strip())
            )
        )
    raw_paths = compiler_options.get("paths")
    if isinstance(raw_paths, dict):
        for targets in raw_paths.values():
            target_values = targets if isinstance(targets, list) else [targets]
            for raw_target in target_values:
                if not isinstance(raw_target, str) or not raw_target.strip():
                    continue
                resolved_target = repository_service._normalize_repository_relative_pattern(
                    str(config_dir / raw_target.strip())
                )
                if not resolved_target:
                    continue
                support_roots.add(resolved_target.split("*", 1)[0].rstrip("/"))
    include_values = config_payload.get("include") if isinstance(config_payload, dict) else None
    if isinstance(include_values, list):
        for item in include_values:
            if not isinstance(item, str) or not item.strip():
                continue
            support_roots.add(
                repository_service._normalize_repository_relative_pattern(
                    str(config_dir / item.strip())
                ).split("*", 1)[0].rstrip("/")
            )
    entrypoint_paths.update(
        {
            str(config_dir / "src/main.ts"),
            str(config_dir / "src/main.tsx"),
            str(config_dir / "src/index.ts"),
            str(config_dir / "src/index.tsx"),
            str(config_dir / "src/App.tsx"),
            str(config_dir / "src/app/page.tsx"),
        }
    )
    return entrypoint_paths, support_roots, config_paths


def _pyproject_profile_hints(
    repo_path: Path,
    pyproject_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(pyproject_path)
    if not normalized_path:
        return set(), set(), set()
    payload = _safe_load_toml_dict(repo_path / normalized_path)
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}app",
    }
    entrypoint_paths = {
        f"{root_prefix}main.py",
        f"{root_prefix}app.py",
        f"{root_prefix}manage.py",
        f"{root_prefix}src/main.py",
        f"{root_prefix}src/__main__.py",
    }
    config_paths = {normalized_path}
    if not isinstance(payload, dict):
        return entrypoint_paths, support_roots, config_paths
    project = payload.get("project")
    if isinstance(project, dict):
        scripts = project.get("scripts")
        if isinstance(scripts, dict):
            for value in scripts.values():
                if not isinstance(value, str) or not value.strip():
                    continue
                module_name = value.split(":", 1)[0].strip()
                if not module_name:
                    continue
                entrypoint_paths.add(f"{root_prefix}{module_name.replace('.', '/')}.py")
                entrypoint_paths.add(f"{root_prefix}src/{module_name.replace('.', '/')}.py")
    return entrypoint_paths, support_roots, config_paths


def _pubspec_profile_hints(
    repo_path: Path,
    pubspec_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(pubspec_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}lib",
        f"{root_prefix}bin",
        f"{root_prefix}tool",
    }
    entrypoint_paths = {
        f"{root_prefix}lib/main.dart",
        f"{root_prefix}bin/main.dart",
    }
    config_paths = {normalized_path}
    package_name = repository_service._read_dart_pubspec_name(repo_path / normalized_path)
    if not package_name:
        return entrypoint_paths, support_roots, config_paths
    for candidate_name in {package_name, package_name.replace("-", "_")}:
        if not candidate_name:
            continue
        entrypoint_paths.add(f"{root_prefix}lib/{candidate_name}.dart")
        entrypoint_paths.add(f"{root_prefix}bin/{candidate_name}.dart")
    return entrypoint_paths, support_roots, config_paths


def _yaml_path_field_values(text: str, field_name: str) -> tuple[str, ...]:
    values: list[str] = []
    lines = text.splitlines()
    for index, raw_line in enumerate(lines):
        stripped_line = raw_line.strip()
        if not stripped_line.startswith(f"{field_name}:"):
            continue
        after_colon = stripped_line[len(field_name) + 1 :].strip()
        if after_colon.startswith("[") and "]" in after_colon:
            body = after_colon[1 : after_colon.index("]")]
            inline_values = [
                str(match.group("value") or "").strip()
                for match in _QUOTED_SEGMENT_RE.finditer(body)
            ]
            if not inline_values:
                inline_values = [
                    segment.strip().strip("'\"")
                    for segment in body.split(",")
                    if segment.strip()
                ]
            values.extend(value for value in inline_values if value)
            continue
        if after_colon and not after_colon.startswith("#"):
            scalar_value = after_colon.split("#", 1)[0].strip().strip("'\"")
            if scalar_value:
                values.append(scalar_value)
            continue
        base_indent = len(raw_line) - len(raw_line.lstrip(" "))
        for subline in lines[index + 1 :]:
            if not subline.strip():
                continue
            current_indent = len(subline) - len(subline.lstrip(" "))
            if current_indent <= base_indent:
                break
            stripped_subline = subline.strip()
            if not stripped_subline.startswith("-"):
                continue
            raw_value = stripped_subline[1:].strip().split("#", 1)[0].strip().strip("'\"")
            if raw_value:
                values.append(raw_value)
    return tuple(dict.fromkeys(value for value in values if value))


def _dbt_project_profile_hints(
    repo_path: Path,
    dbt_project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(dbt_project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    config_paths = {normalized_path}
    try:
        text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    model_roots = _yaml_path_field_values(text, "model-paths") or ("models",)
    analysis_roots = _yaml_path_field_values(text, "analysis-paths") or ("analyses",)
    snapshot_roots = _yaml_path_field_values(text, "snapshot-paths") or ("snapshots",)
    # Only the declared model/analysis/snapshot dirs are operational support roots. Do NOT seed
    # the project root itself: a bare repo-root support root makes every path "within" a support
    # root (so non-operational dirs like ``macro-paths`` leak into support_roots/entrypoints).
    support_roots: set[str] = set()
    entrypoint_paths: set[str] = set()

    for raw_root in (*model_roots, *analysis_roots, *snapshot_roots):
        normalized_root = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_root)
        )
        if normalized_root:
            support_roots.add(normalized_root)

    for raw_root in (*model_roots, *analysis_roots, *snapshot_roots):
        candidate_root = repo_path / project_dir / raw_root
        if not candidate_root.is_dir():
            continue
        try:
            sql_files = sorted(candidate_root.rglob("*.sql"))
        except OSError:
            sql_files = []
        for candidate_path in sql_files:
            relative_path = repository_service._normalize_repository_relative_path(
                str(candidate_path.relative_to(repo_path))
            )
            if (
                relative_path
                and not repository_service._is_test_path(relative_path)
                and not _is_non_operational_profile_path(relative_path)
            ):
                entrypoint_paths.add(relative_path)

    return entrypoint_paths, support_roots, config_paths


def _cargo_profile_hints(
    repo_path: Path,
    cargo_toml_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(cargo_toml_path)
    if not normalized_path:
        return set(), set(), set()
    payload = _safe_load_toml_dict(repo_path / normalized_path)
    cargo_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(cargo_dir) in {"", "."} else f"{cargo_dir}/"
    support_roots = {root_prefix.rstrip("/"), f"{root_prefix}src", f"{root_prefix}bin"}
    entrypoint_paths = {f"{root_prefix}src/main.rs", f"{root_prefix}src/lib.rs"}
    config_paths = {normalized_path}
    if not isinstance(payload, dict):
        return entrypoint_paths, support_roots, config_paths
    lib_payload = payload.get("lib")
    if isinstance(lib_payload, dict):
        lib_path = lib_payload.get("path")
        if isinstance(lib_path, str) and lib_path.strip():
            entrypoint_paths.add(str(cargo_dir / lib_path.strip()))
    bin_payload = payload.get("bin")
    if isinstance(bin_payload, list):
        for entry in bin_payload:
            if not isinstance(entry, dict):
                continue
            bin_path = entry.get("path")
            if isinstance(bin_path, str) and bin_path.strip():
                entrypoint_paths.add(str(cargo_dir / bin_path.strip()))
    return entrypoint_paths, support_roots, config_paths


def _fortran_fpm_profile_hints(
    repo_path: Path,
    fpm_toml_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(fpm_toml_path)
    if not normalized_path:
        return set(), set(), set()
    payload = _safe_load_toml_dict(repo_path / normalized_path)
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {root_prefix.rstrip("/"), f"{root_prefix}src", f"{root_prefix}app"}
    entrypoint_paths = {
        f"{root_prefix}src/main.f90",
        f"{root_prefix}src/main.f95",
        f"{root_prefix}src/main.f03",
        f"{root_prefix}src/main.f08",
        f"{root_prefix}src/main.f",
        f"{root_prefix}app/main.f90",
        f"{root_prefix}app/main.f95",
        f"{root_prefix}app/main.f03",
        f"{root_prefix}app/main.f08",
        f"{root_prefix}app/main.f",
    }
    config_paths = {normalized_path}
    package_name = payload.get("name") if isinstance(payload, dict) else None
    if isinstance(package_name, str) and package_name.strip():
        normalized_name = re.sub(r"[^a-z0-9_]+", "_", package_name.lower()).strip("_")
        if normalized_name:
            for suffix in (".f90", ".f95", ".f03", ".f08", ".f", ".for"):
                entrypoint_paths.add(f"{root_prefix}src/{normalized_name}{suffix}")
                entrypoint_paths.add(f"{root_prefix}app/{normalized_name}{suffix}")
    return entrypoint_paths, support_roots, config_paths


def _pascal_project_profile_hints(
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    stem = PurePosixPath(normalized_path).stem
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}lib",
        f"{root_prefix}units",
    }
    entrypoint_paths = {
        f"{root_prefix}{stem}.pas",
        f"{root_prefix}{stem}.pp",
        f"{root_prefix}{stem}.lpr",
        f"{root_prefix}{stem}.dpr",
        f"{root_prefix}{stem}.dpk",
        f"{root_prefix}main.lpr",
        f"{root_prefix}main.dpr",
        f"{root_prefix}program.lpr",
        f"{root_prefix}program.dpr",
        f"{root_prefix}src/{stem}.pas",
        f"{root_prefix}src/{stem}.pp",
        f"{root_prefix}source/{stem}.pas",
        f"{root_prefix}source/{stem}.pp",
    }
    return entrypoint_paths, support_roots, {normalized_path}


def _delphi_profile_hints(
    repo_path: Path,
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    stem = PurePosixPath(normalized_path).stem
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}source",
        f"{root_prefix}src",
        f"{root_prefix}packages",
        f"{root_prefix}runtime",
        f"{root_prefix}design",
    }
    entrypoint_paths = {
        f"{root_prefix}{stem}.dpr",
        f"{root_prefix}{stem}.dpk",
        f"{root_prefix}{stem}.pas",
        f"{root_prefix}main.dpr",
        f"{root_prefix}main.pas",
        f"{root_prefix}source/{stem}.pas",
        f"{root_prefix}src/{stem}.pas",
    }
    manifest_path = repo_path / normalized_path
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for match in re.finditer(
        r"<MainSource>\s*(?P<path>[^<]+?)\s*</MainSource>",
        text,
        flags=re.IGNORECASE,
    ):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / str(match.group("path") or "").strip())
        )
        if resolved_path:
            entrypoint_paths.add(resolved_path)
    return entrypoint_paths, support_roots, {normalized_path}


def _tsql_profile_hints(
    repo_path: Path,
    project_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(project_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    if _is_non_operational_project_path(str(project_dir)):
        return set(), set(), {normalized_path}
    project_root = repo_path / project_dir
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {root_prefix.rstrip("/")}
    entrypoint_paths: set[str] = set()
    manifest_path = repo_path / normalized_path
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for included_path in repository_service.tsql_adapter.project_included_paths(
        text=text,
        project_file_path=normalized_path,
    ):
        if (
            included_path
            and not repository_service._is_test_path(included_path)
            and not _is_non_operational_profile_path(included_path)
        ):
            entrypoint_paths.add(included_path)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(included_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    for folder_path in repository_service.tsql_adapter.project_folder_paths(
        text=text,
        project_file_path=normalized_path,
    ):
        if folder_path and not _is_non_operational_profile_path(folder_path):
            support_roots.add(folder_path)
    if project_root.is_dir():
        for child in sorted(project_root.iterdir()):
            if not child.is_dir():
                continue
            relative_child = repository_service._normalize_repository_relative_path(
                str(child.relative_to(repo_path))
            )
            if (
                relative_child
                and not _is_non_operational_profile_path(relative_child)
                and repository_service.tsql_adapter.has_tsql_path_hints(child)
            ):
                support_roots.add(relative_child)
        if not entrypoint_paths:
            for candidate in sorted(project_root.rglob("*.sql")):
                if not candidate.is_file() or candidate.is_symlink():
                    continue
                relative_path = repository_service._normalize_repository_relative_path(
                    str(candidate.relative_to(repo_path))
                )
                if (
                    not relative_path
                    or repository_service._is_test_path(relative_path)
                    or _is_non_operational_profile_path(relative_path)
                    or _probe_language_for_path(relative_path, repo_path=repo_path) != "tsql"
                ):
                    continue
                entrypoint_paths.add(relative_path)
                parent_dir = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(relative_path).parent)
                )
                if parent_dir:
                    support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, {normalized_path}


def _go_module_profile_hints(go_mod_path: str) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(go_mod_path)
    if not normalized_path:
        return set(), set(), set()
    module_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(module_dir) in {"", "."} else f"{module_dir}/"
    support_roots = {root_prefix.rstrip("/"), f"{root_prefix}cmd", f"{root_prefix}internal"}
    entrypoint_paths = {f"{root_prefix}main.go"}
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _candidate_clojure_module_paths(
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
    module_path = "/".join(segment.replace("-", "_") for segment in normalized_module.split("."))
    candidate_paths: list[str] = []
    for extension in (".clj", ".cljc", ".cljs"):
        relative_candidate = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(source_prefix or "") / f"{module_path}{extension}")
        )
        if relative_candidate:
            candidate_paths.append(relative_candidate)
    return tuple(dict.fromkeys(candidate_paths))


def _collect_clojure_vector_field_values(
    text: str,
    *,
    field_names: set[str],
) -> dict[str, list[str]]:
    values_by_field = {field_name: [] for field_name in field_names}
    for match in _CLOJURE_VECTOR_FIELD_RE.finditer(text):
        field_name = match.group("field").lstrip(":").lower()
        if field_name not in values_by_field:
            continue
        values_by_field[field_name].extend(
            quoted_match.group("value").strip()
            for quoted_match in _CLOJURE_QUOTED_STRING_RE.finditer(match.group("body"))
            if quoted_match.group("value").strip()
        )
    return values_by_field


def _clojure_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}src/main/clojure",
        f"{root_prefix}src/clj",
        f"{root_prefix}src/cljc",
        f"{root_prefix}src/cljs",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}src/core.clj",
        f"{root_prefix}src/main.clj",
        f"{root_prefix}src/main/clojure/core.clj",
        f"{root_prefix}src/main/clojure/main.clj",
        f"{root_prefix}src/clj/core.clj",
        f"{root_prefix}src/cljc/core.cljc",
        f"{root_prefix}src/cljs/core.cljs",
    }
    config_paths = {normalized_path}
    try:
        text = (repo_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    field_values = _collect_clojure_vector_field_values(
        text,
        field_names={"paths", "source-paths", "src-dirs"},
    )
    raw_source_dirs = [
        source_dir
        for source_dir in (
            field_values["paths"] + field_values["source-paths"] + field_values["src-dirs"]
        )
        if source_dir and not _is_non_operational_profile_path(source_dir)
    ] or ["src"]
    for source_dir in raw_source_dirs:
        normalized_source_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / source_dir)
        )
        if normalized_source_dir and not _is_non_operational_profile_path(normalized_source_dir):
            support_roots.add(normalized_source_dir)
    for match in _CLOJURE_MAIN_RE.finditer(text):
        main_target = match.group("target").strip()
        if not main_target:
            continue
        for source_dir in raw_source_dirs:
            entrypoint_paths.update(
                _candidate_clojure_module_paths(
                    project_dir=project_dir,
                    source_dir=source_dir,
                    module_name=main_target,
                )
            )
    return entrypoint_paths, support_roots, config_paths


def _pom_profile_hints(
    repo_path: Path,
    pom_xml_path: str,
) -> tuple[set[str], set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(pom_xml_path)
    if not normalized_path:
        return set(), set(), set(), set()
    pom_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(pom_dir) in {"", "."} else f"{pom_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}src/main/java",
        f"{root_prefix}src/main/kotlin",
    }
    entrypoint_paths = {
        f"{root_prefix}src/main/java/Application.java",
        f"{root_prefix}src/main/java/Main.java",
        f"{root_prefix}src/main/kotlin/Application.kt",
        f"{root_prefix}src/main/kotlin/Main.kt",
    }
    config_paths = {normalized_path}
    preferred_ecosystems: set[str] = set()

    clojure_source_dirs: list[str] = []
    for source_dir in ("src/main/clojure", "src/clj", "src/cljc"):
        normalized_source_dir = repository_service._normalize_repository_relative_path(
            str(pom_dir / source_dir)
        )
        if normalized_source_dir and (repo_path / normalized_source_dir).is_dir():
            support_roots.add(normalized_source_dir)
            clojure_source_dirs.append(source_dir)
    if not clojure_source_dirs:
        return entrypoint_paths, support_roots, config_paths, preferred_ecosystems

    clojure_file_count = 0
    for source_dir in clojure_source_dirs:
        normalized_source_dir = repository_service._normalize_repository_relative_path(
            str(pom_dir / source_dir)
        )
        if not normalized_source_dir:
            continue
        source_path = repo_path / normalized_source_dir
        for candidate in source_path.rglob("*"):
            if (
                not candidate.is_file()
                or candidate.is_symlink()
                or candidate.suffix.lower() not in {".clj", ".cljc", ".cljs"}
            ):
                continue
            clojure_file_count += 1
            relative_candidate = repository_service._normalize_repository_relative_path(
                str(candidate.relative_to(repo_path))
            )
            if relative_candidate and relative_candidate.endswith(
                (
                    "/core.clj",
                    "/core.cljc",
                    "/core.cljs",
                    "/main.clj",
                    "/main.cljc",
                    "/main.cljs",
                )
            ):
                entrypoint_paths.add(relative_candidate)
            if clojure_file_count >= 128:
                break
        if clojure_file_count >= 128:
            break

    if clojure_file_count >= 8:
        preferred_ecosystems.add("clojure")
        for source_dir in clojure_source_dirs:
            entrypoint_paths.update(
                _candidate_clojure_module_paths(
                    project_dir=pom_dir,
                    source_dir=source_dir,
                    module_name="clojure.core",
                )
            )
            entrypoint_paths.update(
                _candidate_clojure_module_paths(
                    project_dir=pom_dir,
                    source_dir=source_dir,
                    module_name="clojure.main",
                )
            )

    return entrypoint_paths, support_roots, config_paths, preferred_ecosystems


_normalize_gradle_project_root = _normalize_gradle_project_root_support
_gradle_project_root_hints = _gradle_project_root_hints_support
_iter_gradle_included_project_roots = _iter_gradle_included_project_roots_support
_gradle_profile_hints = _gradle_profile_hints_support
_qsharp_profile_hints = _qsharp_profile_hints_support
_cmake_like_profile_hints = _cmake_like_profile_hints_support
_c_family_manifest_ecosystems = _c_family_manifest_ecosystems_support
_cmake_profile_hints = _cmake_profile_hints_support
_profile_root_from_glob_pattern = _profile_root_from_glob_pattern_support
_podspec_profile_hints = _podspec_profile_hints_support
_meson_profile_hints = _meson_profile_hints_support
_qmake_profile_hints = _qmake_profile_hints_support
_composer_profile_hints = _composer_profile_hints_support
_mix_profile_hints = _mix_profile_hints_support
_swift_package_profile_hints = _swift_package_profile_hints_support
_powershell_profile_hints = _powershell_profile_hints_support
_scala_build_profile_hints = _scala_build_profile_hints_support
_scala_build_support_roots = _scala_build_support_roots_support
_zig_build_profile_hints = _zig_build_profile_hints_support


_normalized_ada_unit_stem = _normalized_ada_unit_stem_support
_ada_project_quoted_values = _ada_project_quoted_values_support
_ada_profile_hints = _ada_profile_hints_support
_dub_sdl_quoted_values = _dub_sdl_quoted_values_support
_normalized_d_package_name = _normalized_d_package_name_support
_dub_profile_hints = _dub_profile_hints_support
_append_manifest_field_value = _append_manifest_field_value_support
_collect_manifest_field_values = _collect_manifest_field_values_support
_candidate_haskell_module_paths = _candidate_haskell_module_paths_support
_haskell_cabal_profile_hints = _haskell_cabal_profile_hints_support
_haskell_package_yaml_profile_hints = _haskell_package_yaml_profile_hints_support
_haskell_project_profile_hints = _haskell_project_profile_hints_support
_csproj_profile_hints = _csproj_profile_hints_support
_sln_project_paths = _sln_project_paths_support
_sln_profile_hints = _sln_profile_hints_support
_gemfile_profile_hints = _gemfile_profile_hints_support
_erlang_project_profile_hints = _erlang_project_profile_hints_support
_nim_project_profile_hints = _nim_project_profile_hints_support
