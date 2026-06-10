from __future__ import annotations

import os
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
_QUOTED_SEGMENT_RE = _DeferredProbeAttr("_QUOTED_SEGMENT_RE")
_C_FAMILY_SOURCE_TOKEN_RE = _DeferredProbeAttr("_C_FAMILY_SOURCE_TOKEN_RE")
_POWERSHELL_MANIFEST_FIELD_RE = _DeferredProbeAttr("_POWERSHELL_MANIFEST_FIELD_RE")
_POWERSHELL_MANIFEST_LIST_RE = _DeferredProbeAttr("_POWERSHELL_MANIFEST_LIST_RE")
_ZIG_SOURCE_TOKEN_RE = _DeferredProbeAttr("_ZIG_SOURCE_TOKEN_RE")


def _normalize_gradle_project_root(project_name: str) -> str:
    normalized = project_name.strip().strip(":")
    if not normalized:
        return ""
    return normalized.replace(":", "/")


def _gradle_project_root_hints(project_root: str) -> tuple[set[str], set[str]]:
    root_prefix = "" if project_root in {"", "."} else f"{project_root}/"
    support_roots = {
        f"{root_prefix}src/main/java",
        f"{root_prefix}src/main/groovy",
        f"{root_prefix}src/main/kotlin",
    }
    entrypoint_paths = {
        f"{root_prefix}src/main/java/Application.java",
        f"{root_prefix}src/main/java/Main.java",
        f"{root_prefix}src/main/groovy/Application.groovy",
        f"{root_prefix}src/main/groovy/Main.groovy",
        f"{root_prefix}src/main/kotlin/Application.kt",
        f"{root_prefix}src/main/kotlin/Main.kt",
    }
    return entrypoint_paths, support_roots


def _iter_gradle_included_project_roots(text: str) -> tuple[str, ...]:
    project_roots: set[str] = set()
    lines = text.splitlines()
    line_index = 0
    while line_index < len(lines):
        stripped_line = lines[line_index].strip()
        if not (
            stripped_line == "include"
            or stripped_line.startswith("include ")
            or stripped_line.startswith("include(")
        ):
            line_index += 1
            continue
        block_lines = [stripped_line]
        line_index += 1
        while line_index < len(lines):
            continuation = lines[line_index].strip()
            if not continuation:
                break
            if continuation.startswith(("'", '"')) or continuation.startswith(","):
                block_lines.append(continuation)
                line_index += 1
                continue
            break
        block_text = " ".join(block_lines)
        for match in _QUOTED_SEGMENT_RE.finditer(block_text):
            normalized_root = _normalize_gradle_project_root(str(match.group("value") or ""))
            if normalized_root:
                project_roots.add(normalized_root)
    return tuple(sorted(project_roots))


def _gradle_profile_hints(
    repo_path: Path,
    gradle_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(gradle_path)
    if not normalized_path:
        return set(), set(), set()
    gradle_dir = PurePosixPath(normalized_path).parent
    project_root = "" if str(gradle_dir) in {"", "."} else str(gradle_dir)
    entrypoint_paths, support_roots = _gradle_project_root_hints(project_root)
    config_paths = {normalized_path}

    gradle_name = PurePosixPath(normalized_path).name.lower()
    if gradle_name not in {"settings.gradle", "settings.gradle.kts"}:
        return entrypoint_paths, support_roots, config_paths

    settings_path = repo_path / normalized_path
    if not settings_path.is_file():
        return entrypoint_paths, support_roots, config_paths

    settings_text = settings_path.read_text(encoding="utf-8", errors="replace")
    for included_root in _iter_gradle_included_project_roots(settings_text):
        included_entrypoints, included_support_roots = _gradle_project_root_hints(included_root)
        entrypoint_paths.update(included_entrypoints)
        support_roots.update(included_support_roots)
    return entrypoint_paths, support_roots, config_paths


def _qsharp_profile_hints(
    qsharp_config_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(qsharp_config_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}sample",
        f"{root_prefix}samples",
        f"{root_prefix}demo",
        f"{root_prefix}demos",
        f"{root_prefix}example",
        f"{root_prefix}examples",
    }
    entrypoint_paths = {
        f"{root_prefix}Main.qs",
        f"{root_prefix}Program.qs",
        f"{root_prefix}src/Main.qs",
        f"{root_prefix}src/Program.qs",
        f"{root_prefix}samples/Main.qs",
        f"{root_prefix}examples/Main.qs",
    }
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _cmake_like_profile_hints(
    *,
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}include",
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}sources",
        f"{root_prefix}lib",
        f"{root_prefix}libs",
    }
    entrypoint_paths = {
        f"{root_prefix}main.c",
        f"{root_prefix}main.cc",
        f"{root_prefix}main.cpp",
        f"{root_prefix}main.cxx",
        f"{root_prefix}main.m",
        f"{root_prefix}main.mm",
        f"{root_prefix}src/main.c",
        f"{root_prefix}src/main.cc",
        f"{root_prefix}src/main.cpp",
        f"{root_prefix}src/main.cxx",
        f"{root_prefix}src/main.m",
        f"{root_prefix}src/main.mm",
    }
    config_paths = {normalized_path}
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _C_FAMILY_SOURCE_TOKEN_RE.finditer(text):
        raw_path = match.group("path").strip()
        if not raw_path or raw_path.startswith(("$", "/")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / raw_path)
        )
        if not resolved_path or resolved_path.startswith("/"):
            continue
        entrypoint_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths


def _c_family_manifest_ecosystems(
    *,
    repo_path: Path,
    manifest_path: str,
) -> set[str]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return {"cpp"}
    manifest = repo_path / normalized_path
    try:
        text = manifest.read_text(encoding="utf-8")
    except OSError:
        return {"cpp"}

    manifest_ecosystems: set[str] = set()
    for match in _C_FAMILY_SOURCE_TOKEN_RE.finditer(text):
        suffix = PurePosixPath(str(match.group("path") or "").strip()).suffix.lower()
        if suffix == ".c":
            manifest_ecosystems.add("c")
        elif suffix in {".cc", ".cpp", ".cxx"}:
            manifest_ecosystems.add("cpp")
        elif suffix in {".vala", ".vapi"}:
            manifest_ecosystems.add("vala")
    if "vala" not in manifest_ecosystems:
        project_dir = PurePosixPath(normalized_path).parent
        for candidate_root in (
            repo_path / project_dir,
            repo_path / project_dir / "src",
            repo_path / project_dir / "lib",
        ):
            if not candidate_root.is_dir():
                continue
            try:
                has_vala_sources = any(candidate_root.rglob("*.vala")) or any(
                    candidate_root.rglob("*.vapi")
                )
            except OSError:
                continue
            if has_vala_sources:
                manifest_ecosystems.add("vala")
                break
    return manifest_ecosystems or {"cpp"}


def _cmake_profile_hints(
    repo_path: Path,
    cmake_path: str,
) -> tuple[set[str], set[str], set[str]]:
    return _cmake_like_profile_hints(repo_path=repo_path, manifest_path=cmake_path)


def _profile_root_from_glob_pattern(
    *,
    project_dir: PurePosixPath,
    raw_pattern: str,
) -> str | None:
    normalized_pattern = str(raw_pattern or "").strip().replace("\\", "/")
    if not normalized_pattern or normalized_pattern.startswith(("http://", "https://", "$")):
        return None
    normalized_pattern = normalized_pattern.split("{", 1)[0]
    for delimiter in ("**", "*", "[", "?"):
        if delimiter in normalized_pattern:
            normalized_pattern = normalized_pattern.split(delimiter, 1)[0]
            break
    normalized_pattern = normalized_pattern.rstrip("/")
    resolved_root = repository_service._normalize_repository_relative_path(
        str(project_dir / normalized_pattern)
    )
    if resolved_root:
        return resolved_root
    project_root = repository_service._normalize_repository_relative_path(str(project_dir))
    return project_root or None


def _podspec_profile_hints(
    repo_path: Path,
    podspec_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(podspec_path)
    if not normalized_path:
        return set(), set(), set()
    podspec = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}Classes",
        f"{root_prefix}Sources",
        f"{root_prefix}Source",
        f"{root_prefix}src",
        f"{root_prefix}include",
    }
    entrypoint_paths = {
        f"{root_prefix}main.m",
        f"{root_prefix}main.mm",
        f"{root_prefix}src/main.m",
        f"{root_prefix}src/main.mm",
        f"{root_prefix}Sources/main.m",
        f"{root_prefix}Sources/main.mm",
    }
    config_paths = {normalized_path}
    try:
        text = podspec.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _QUOTED_SEGMENT_RE.finditer(text):
        raw_pattern = str(match.group("value") or "").strip()
        lower_pattern = raw_pattern.lower()
        if not any(
            token in lower_pattern
            for token in (".h", ".m", ".mm", ".pch", "classes", "sources", "source", "src")
        ):
            continue
        derived_root = _profile_root_from_glob_pattern(
            project_dir=project_dir,
            raw_pattern=raw_pattern,
        )
        if derived_root and not _is_non_operational_project_path(derived_root):
            support_roots.add(derived_root)
        if any(token in raw_pattern for token in ("*", "?", "[", "{")):
            continue
        normalized_candidate = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_pattern)
        )
        if normalized_candidate and PurePosixPath(normalized_candidate).suffix.lower() in {
            ".h",
            ".m",
            ".mm",
            ".pch",
        }:
            entrypoint_paths.add(normalized_candidate)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(normalized_candidate).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
    return entrypoint_paths, support_roots, config_paths


def _meson_profile_hints(
    repo_path: Path,
    meson_path: str,
) -> tuple[set[str], set[str], set[str]]:
    return _cmake_like_profile_hints(repo_path=repo_path, manifest_path=meson_path)


def _qmake_profile_hints(
    repo_path: Path,
    qmake_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(qmake_path)
    if not normalized_path:
        return set(), set(), set()
    manifest = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}include",
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}sources",
        f"{root_prefix}lib",
        f"{root_prefix}libs",
    }
    entrypoint_paths = {
        f"{root_prefix}main.c",
        f"{root_prefix}main.cc",
        f"{root_prefix}main.cpp",
        f"{root_prefix}main.cxx",
        f"{root_prefix}main.m",
        f"{root_prefix}main.mm",
        f"{root_prefix}src/main.c",
        f"{root_prefix}src/main.cc",
        f"{root_prefix}src/main.cpp",
        f"{root_prefix}src/main.cxx",
        f"{root_prefix}src/main.m",
        f"{root_prefix}src/main.mm",
    }
    config_paths = {normalized_path}
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _C_FAMILY_SOURCE_TOKEN_RE.finditer(text):
        raw_path = match.group("path").strip()
        if not raw_path or raw_path.startswith(("$", "/")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / raw_path)
        )
        if not resolved_path or resolved_path.startswith("/"):
            continue
        entrypoint_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for include_target, _line_number in repository_service.qmake_adapter.iter_include_targets(text):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / include_target)
        )
        if not resolved_path or PurePosixPath(resolved_path).suffix.lower() not in {
            ".pro",
            ".pri",
            ".prf",
        }:
            continue
        config_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
    for _label, explicit_path, _depends, _line_number in repository_service.qmake_adapter.iter_subdir_entries(
        text
    ):
        subdir_target = explicit_path or ""
        if not subdir_target:
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / subdir_target)
        )
        if not resolved_path:
            continue
        resolved = repo_path / resolved_path
        if resolved.is_file() and resolved.suffix.lower() in {".pro", ".pri", ".prf"}:
            config_paths.add(resolved_path)
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(resolved_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            continue
        if resolved.is_dir():
            support_roots.add(resolved_path)
            child_name = PurePosixPath(resolved_path).name
            for candidate_name in (f"{child_name}.pro", f"{child_name}.pri", f"{child_name}.prf"):
                child_path = repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(resolved_path) / candidate_name)
                )
                if child_path and (repo_path / child_path).is_file():
                    config_paths.add(child_path)
                    break
    return entrypoint_paths, support_roots, config_paths


def _composer_profile_hints(
    repo_path: Path,
    composer_json_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(composer_json_path)
    if not normalized_path:
        return set(), set(), set()
    payload = repository_service._safe_load_jsonc_dict(repo_path / normalized_path)
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}app",
        f"{root_prefix}src",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}artisan",
        f"{root_prefix}public/index.php",
        f"{root_prefix}server.php",
        f"{root_prefix}index.php",
    }
    config_paths = {normalized_path}
    if not isinstance(payload, dict):
        return entrypoint_paths, support_roots, config_paths
    for raw_bin in payload.get("bin") if isinstance(payload.get("bin"), list) else []:
        if isinstance(raw_bin, str) and raw_bin.strip():
            entrypoint_paths.add(str(project_dir / raw_bin.strip()))
    for autoload_key in ("autoload", "autoload-dev"):
        autoload = payload.get(autoload_key)
        if not isinstance(autoload, dict):
            continue
        for mapping_key in ("psr-4", "psr-0"):
            mapping = autoload.get(mapping_key)
            if not isinstance(mapping, dict):
                continue
            for target in mapping.values():
                target_values = target if isinstance(target, list) else [target]
                for raw_target in target_values:
                    if not isinstance(raw_target, str) or not raw_target.strip():
                        continue
                    support_roots.add(
                        repository_service._normalize_repository_relative_pattern(
                            str(project_dir / raw_target.strip())
                        ).split("*", 1)[0].rstrip("/")
                    )
        for file_key in ("files", "classmap"):
            mapping = autoload.get(file_key)
            if not isinstance(mapping, list):
                continue
            for raw_target in mapping:
                if isinstance(raw_target, str) and raw_target.strip():
                    entrypoint_paths.add(str(project_dir / raw_target.strip()))
    return entrypoint_paths, support_roots, config_paths


def _mix_profile_hints(
    repo_path: Path,
    mix_exs_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(mix_exs_path)
    if not normalized_path:
        return set(), set(), set()
    mix_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}lib",
        f"{root_prefix}config",
    }
    entrypoint_paths = {
        f"{root_prefix}lib/application.ex",
    }
    config_paths = {normalized_path}
    try:
        text = mix_path.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    app_match = re.search(r"app:\s*:([A-Za-z0-9_]+)", text)
    if app_match:
        app_name = app_match.group(1).strip()
        if app_name:
            entrypoint_paths.add(f"{root_prefix}lib/{app_name}.ex")
            entrypoint_paths.add(f"{root_prefix}lib/{app_name}/application.ex")
    return entrypoint_paths, support_roots, config_paths


def _swift_package_profile_hints(
    repo_path: Path,
    package_swift_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(package_swift_path)
    if not normalized_path:
        return set(), set(), set()
    package_path = repo_path / normalized_path
    package_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(package_dir) in {"", "."} else f"{package_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}Sources",
    }
    entrypoint_paths = {
        f"{root_prefix}Sources/main.swift",
    }
    config_paths = {normalized_path}
    try:
        text = package_path.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    name_match = re.search(r'name:\s*"([^"]+)"', text)
    if name_match:
        package_name = name_match.group(1).strip()
        if package_name:
            entrypoint_paths.add(f"{root_prefix}Sources/{package_name}/main.swift")
    return entrypoint_paths, support_roots, config_paths


def _powershell_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    manifest_stem = PurePosixPath(normalized_path).stem
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}source",
        f"{root_prefix}Public",
        f"{root_prefix}Private",
        f"{root_prefix}Classes",
    }
    entrypoint_paths = {
        f"{root_prefix}{manifest_stem}.psm1",
        f"{root_prefix}src/{manifest_stem}.psm1",
    }
    config_paths = {normalized_path}

    def _add_entrypoint(raw_target: str) -> None:
        normalized_target = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_target.strip())
        )
        if not normalized_target:
            return
        entrypoint_paths.add(normalized_target)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(normalized_target).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)

    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _POWERSHELL_MANIFEST_FIELD_RE.finditer(text):
        raw_target = str(match.group("value") or "").strip()
        if raw_target:
            _add_entrypoint(raw_target)
    for match in _POWERSHELL_MANIFEST_LIST_RE.finditer(text):
        for quoted_match in _QUOTED_SEGMENT_RE.finditer(str(match.group("body") or "")):
            raw_target = str(quoted_match.group("value") or "").strip()
            if raw_target:
                _add_entrypoint(raw_target)
    return entrypoint_paths, support_roots, config_paths


def _scala_build_profile_hints(
    repo_path: Path,
    scala_build_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(scala_build_path)
    if not normalized_path:
        return set(), set(), set()
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}project",
    }
    support_roots.update(
        _scala_build_support_roots(
            repo_path=repo_path,
            project_dir=project_dir,
        )
    )
    entrypoint_paths = {
        f"{root_prefix}src/main/scala/Main.scala",
        f"{root_prefix}src/main/java/Main.java",
    }
    config_paths = {normalized_path}
    return entrypoint_paths, support_roots, config_paths


def _scala_build_support_roots(
    *,
    repo_path: Path,
    project_dir: PurePosixPath,
) -> set[str]:
    base_dir = repo_path / project_dir
    if not base_dir.exists() or not base_dir.is_dir():
        return set()
    excluded_dirnames = set(repository_service._DEFAULT_EXCLUDED_PATH_PARTS)
    support_roots: set[str] = set()
    for dirpath, dirnames, _filenames in os.walk(base_dir):
        current_dir = Path(dirpath)
        dirnames[:] = [name for name in dirnames if name not in excluded_dirnames]
        try:
            relative_path = current_dir.relative_to(repo_path)
        except ValueError:
            dirnames[:] = []
            continue
        normalized_path = repository_service._normalize_repository_relative_path(
            str(relative_path)
        )
        if not normalized_path:
            continue
        if repository_service._is_test_path(normalized_path) or _is_non_operational_profile_path(
            normalized_path
        ):
            dirnames[:] = []
            continue
        relative_depth = len(current_dir.relative_to(base_dir).parts)
        if relative_depth >= 5:
            dirnames[:] = []
        parts = PurePosixPath(normalized_path).parts
        basename = parts[-1].lower() if parts else ""
        if basename == "src" or basename.startswith("src-"):
            support_roots.add(normalized_path)
            continue
        if len(parts) >= 3 and basename in {"scala", "java"}:
            if parts[-2].lower() == "main" and parts[-3].lower() == "src":
                support_roots.add(normalized_path)
    return support_roots


def _zig_build_profile_hints(
    repo_path: Path,
    build_zig_path: str,
) -> tuple[set[str], set[str], set[str]]:
    normalized_path = repository_service._normalize_repository_relative_path(build_zig_path)
    if not normalized_path:
        return set(), set(), set()
    build_path = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    root_prefix = "" if str(project_dir) in {"", "."} else f"{project_dir}/"
    support_roots = {
        root_prefix.rstrip("/"),
        f"{root_prefix}src",
        f"{root_prefix}lib",
    }
    entrypoint_paths = {
        f"{root_prefix}src/main.zig",
        f"{root_prefix}src/root.zig",
        f"{root_prefix}main.zig",
        f"{root_prefix}root.zig",
    }
    config_paths = {normalized_path}
    try:
        text = build_path.read_text(encoding="utf-8")
    except OSError:
        return entrypoint_paths, support_roots, config_paths
    for match in _ZIG_SOURCE_TOKEN_RE.finditer(text):
        raw_path = match.group("path").strip()
        if not raw_path or raw_path.startswith(("$", "/")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(project_dir) / raw_path)
        )
        if (
            not resolved_path
            or resolved_path.startswith("/")
            or repository_service._is_test_path(resolved_path)
            or _is_non_operational_profile_path(resolved_path)
        ):
            continue
        entrypoint_paths.add(resolved_path)
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        sibling_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).with_suffix(""))
        )
        if sibling_dir and (repo_path / sibling_dir).is_dir():
            support_roots.add(sibling_dir)
    return entrypoint_paths, support_roots, config_paths
