from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

_SYSTEMVERILOG_MANIFEST_SOURCE_SUFFIXES = frozenset({".sv", ".svh", ".v", ".vh"})
_SYSTEMVERILOG_MANIFEST_HEADER_SUFFIXES = frozenset({".svh", ".vh"})


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _actionscript_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        payload = json.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    compiler_options = payload.get("compilerOptions", {})
    if not isinstance(compiler_options, dict):
        compiler_options = {}

    def _iter_string_values(value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list):
            return tuple(item for item in value if isinstance(item, str))
        return ()

    source_roots: list[str] = []
    for raw_source_root in (
        *_iter_string_values(payload.get("source-path")),
        *_iter_string_values(payload.get("include-sources")),
        *_iter_string_values(compiler_options.get("source-path")),
        *_iter_string_values(compiler_options.get("include-sources")),
    ):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_source_root)
        )
        if not resolved_path or not (repo_path / resolved_path).exists():
            continue
        if (repo_path / resolved_path).is_dir():
            support_roots.add(resolved_path)
            source_roots.append(resolved_path)
            continue
        if (
            not (repo_path / resolved_path).is_file()
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "actionscript"
        ):
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
            source_roots.append(parent_dir)
        if _is_operational_profile_entrypoint_candidate(
            resolved_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(resolved_path)

    for raw_file_path in _iter_string_values(payload.get("files")):
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_file_path)
        )
        if (
            not resolved_path
            or not (repo_path / resolved_path).is_file()
            or _probe_language_for_path(resolved_path, repo_path=repo_path) != "actionscript"
        ):
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir and not source_roots:
            support_roots.add(parent_dir)
        if _is_operational_profile_entrypoint_candidate(
            resolved_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(resolved_path)

    main_class = ""
    for candidate_value in (payload.get("mainClass"), compiler_options.get("mainClass")):
        if isinstance(candidate_value, str) and candidate_value.strip():
            main_class = candidate_value.strip()
            break
    if main_class:
        main_class_path = main_class.replace(".", "/") + ".as"
        candidate_roots = source_roots or [
            repository_service._normalize_repository_relative_path(str(project_dir / "src")),
            repository_service._normalize_repository_relative_path(str(project_dir / "source")),
            repository_service._normalize_repository_relative_path(str(project_dir)),
        ]
        for candidate_root in candidate_roots:
            normalized_root = repository_service._normalize_repository_relative_path(candidate_root)
            if not normalized_root:
                continue
            resolved_path = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(normalized_root) / main_class_path)
            )
            if (
                not resolved_path
                or not (repo_path / resolved_path).is_file()
                or _probe_language_for_path(resolved_path, repo_path=repo_path) != "actionscript"
            ):
                continue
            support_roots.add(normalized_root)
            if _is_operational_profile_entrypoint_candidate(
                resolved_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(resolved_path)

    if support_roots:
        return entrypoint_paths, support_roots, config_paths

    for fallback_dir in ("src", "source", "as3", "actionscript"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths


def _systemverilog_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    systemverilog_manifest_path_re = probe_module._SYSTEMVERILOG_MANIFEST_PATH_RE
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""

    seen_paths: set[str] = set()
    for match in systemverilog_manifest_path_re.finditer(manifest_text):
        raw_path = str(match.group("path") or "").strip()
        if not raw_path or raw_path.startswith(("$", "/", "+")):
            continue
        resolved_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_path)
        )
        if not resolved_path or resolved_path.startswith("/"):
            continue
        if resolved_path in seen_paths:
            continue
        seen_paths.add(resolved_path)
        suffix = PurePosixPath(resolved_path).suffix.lower()
        if suffix not in _SYSTEMVERILOG_MANIFEST_SOURCE_SUFFIXES:
            continue
        if not (repo_path / resolved_path).is_file():
            continue
        if _is_non_operational_profile_path(resolved_path):
            continue
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        if (
            suffix not in _SYSTEMVERILOG_MANIFEST_HEADER_SUFFIXES
            and not repository_service._is_test_path(resolved_path)
        ):
            entrypoint_paths.add(resolved_path)

    if support_roots:
        return entrypoint_paths, support_roots, config_paths

    for fallback_dir in ("rtl", "src", "hdl", "verilog", "tb", "dv"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths


def _gml_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _probe_language_for_path = probe_module._probe_language_for_path

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""
    payload = repository_service.gml_adapter.load_game_maker_json(manifest_text)
    if not isinstance(payload, dict):
        payload = {}

    resource_entries = payload.get("resources")
    if not isinstance(resource_entries, list):
        resource_entries = []

    resolved_resource_paths: set[str] = set()
    for resource_entry in resource_entries:
        if not isinstance(resource_entry, dict):
            continue
        resource_id = resource_entry.get("id")
        raw_path = ""
        if isinstance(resource_id, dict):
            raw_path = str(resource_id.get("path") or "").strip()
        if not raw_path:
            raw_path = str(resource_entry.get("path") or "").strip()
        if not raw_path:
            continue
        resolved_resource_path = repository_service._normalize_repository_relative_path(
            str(project_dir / raw_path)
        )
        if (
            not resolved_resource_path
            or not (repo_path / resolved_resource_path).is_file()
            or resolved_resource_path in resolved_resource_paths
        ):
            continue
        resolved_resource_paths.add(resolved_resource_path)
        resource_path = PurePosixPath(resolved_resource_path)
        resource_parent = repository_service._normalize_repository_relative_path(
            str(resource_path.parent)
        )
        if resource_parent:
            support_roots.add(resource_parent)
        top_level_dir = resource_path.parts[0] if resource_path.parts else ""
        if top_level_dir:
            support_roots.add(top_level_dir)

        if top_level_dir == "scripts":
            script_code_path = repository_service._normalize_repository_relative_path(
                str(resource_path.parent / f"{resource_path.stem}.gml")
            )
            if (
                not script_code_path
                or not (repo_path / script_code_path).is_file()
                or _probe_language_for_path(script_code_path, repo_path=repo_path) != "gml"
            ):
                continue
            if _is_operational_profile_entrypoint_candidate(
                script_code_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(script_code_path)
            continue

        if top_level_dir != "objects" or not resource_parent:
            continue
        object_dir = repo_path / resource_parent
        if not object_dir.is_dir():
            continue
        for child_path in sorted(object_dir.glob("*.gml")):
            child_relative_path = repository_service._normalize_repository_relative_path(
                str(child_path.relative_to(repo_path))
            )
            if (
                not child_relative_path
                or _probe_language_for_path(child_relative_path, repo_path=repo_path) != "gml"
            ):
                continue
            if _is_operational_profile_entrypoint_candidate(
                child_relative_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(child_relative_path)

    if support_roots:
        return entrypoint_paths, support_roots, config_paths

    for fallback_dir in ("scripts", "objects", "rooms", "sequences", "timelines"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths


def _gdscript_project_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    gdscript_resource_re = probe_module._GDSCRIPT_RESOURCE_RE
    gdscript_scene_script_re = probe_module._GDSCRIPT_SCENE_SCRIPT_RE
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    try:
        manifest_text = manifest_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        manifest_text = ""

    def _resolve_godot_resource(raw_value: str) -> str | None:
        match = gdscript_resource_re.search(str(raw_value or ""))
        if match is None:
            return None
        resource_path = repository_service._normalize_repository_relative_path(
            str(project_dir / str(match.group("path") or ""))
        )
        if not resource_path:
            return None
        return resource_path

    def _scene_script_paths(raw_scene_path: str) -> set[str]:
        if str(raw_scene_path).startswith("res://"):
            resolved_scene_path = _resolve_godot_resource(raw_scene_path)
        else:
            resolved_scene_path = repository_service._normalize_repository_relative_path(
                str(raw_scene_path)
            )
        if not resolved_scene_path or not (repo_path / resolved_scene_path).is_file():
            return set()
        if PurePosixPath(resolved_scene_path).suffix.lower() == ".gd":
            return {resolved_scene_path}
        if PurePosixPath(resolved_scene_path).suffix.lower() not in {".tscn", ".scn"}:
            return set()
        try:
            scene_text = (repo_path / resolved_scene_path).read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return set()
        script_paths: set[str] = set()
        for match in gdscript_scene_script_re.finditer(scene_text):
            resource_path = _resolve_godot_resource(str(match.group("path") or ""))
            if resource_path and (repo_path / resource_path).is_file():
                script_paths.add(resource_path)
        return script_paths

    main_scene_value: str | None = None
    in_autoload_section = False
    for raw_line in manifest_text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith(";"):
            continue
        if stripped_line.startswith("[") and stripped_line.endswith("]"):
            in_autoload_section = stripped_line.casefold() == "[autoload]"
            continue
        if stripped_line.startswith("run/main_scene="):
            main_scene_value = stripped_line.split("=", 1)[1]
            continue
        if not in_autoload_section:
            continue
        resource_path = _resolve_godot_resource(stripped_line)
        if resource_path is None or not (repo_path / resource_path).exists():
            continue
        if resource_path.endswith(".gd") and _is_operational_profile_entrypoint_candidate(
            resource_path,
            repo_path=repo_path,
        ):
            entrypoint_paths.add(resource_path)
        else:
            entrypoint_paths.update(_scene_script_paths(resource_path))
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resource_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)

    if main_scene_value is not None:
        resolved_main_scene = _resolve_godot_resource(main_scene_value)
        if resolved_main_scene:
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(resolved_main_scene).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if resolved_main_scene.endswith(".gd") and _is_operational_profile_entrypoint_candidate(
                resolved_main_scene,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(resolved_main_scene)
            else:
                entrypoint_paths.update(_scene_script_paths(resolved_main_scene))

    for resolved_path in tuple(entrypoint_paths):
        parent_dir = repository_service._normalize_repository_relative_path(
            str(PurePosixPath(resolved_path).parent)
        )
        if parent_dir:
            support_roots.add(parent_dir)
        resolved_parts = PurePosixPath(resolved_path).parts
        top_level_dir = resolved_parts[0] if resolved_parts else ""
        if top_level_dir:
            support_roots.add(top_level_dir)

    if support_roots:
        return entrypoint_paths, support_roots, config_paths

    for fallback_dir in ("src", "scripts", "addons", "autoload", "Scenes", "scenes"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths


def _vhdl_profile_hints(
    repo_path: Path,
    manifest_path: str,
) -> tuple[set[str], set[str], set[str]]:
    probe_module = _probe_module()
    repository_service = probe_module.repository_service
    _is_operational_profile_entrypoint_candidate = (
        probe_module._is_operational_profile_entrypoint_candidate
    )
    _probe_language_for_path = probe_module._probe_language_for_path
    _profile_path_tokens = probe_module._profile_path_tokens
    tomllib = probe_module.tomllib

    normalized_path = repository_service._normalize_repository_relative_path(manifest_path)
    if not normalized_path:
        return set(), set(), set()
    manifest_file = repo_path / normalized_path
    project_dir = PurePosixPath(normalized_path).parent
    config_paths = {normalized_path}
    support_roots = {
        str(project_dir)
        for project_dir in (project_dir,)
        if str(project_dir) not in {"", "."}
    }
    entrypoint_paths: set[str] = set()
    if tomllib is None:
        return entrypoint_paths, support_roots, config_paths
    try:
        payload = tomllib.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
    except (OSError, tomllib.TOMLDecodeError):
        payload = {}
    for library_config in payload.get("libraries", {}).values():
        if not isinstance(library_config, dict):
            continue
        for raw_path in library_config.get("files", ()):
            if not isinstance(raw_path, str):
                continue
            resolved_path = repository_service._normalize_repository_relative_path(
                str(project_dir / raw_path)
            )
            if not resolved_path or not (repo_path / resolved_path).is_file():
                continue
            if _probe_language_for_path(resolved_path, repo_path=repo_path) != "vhdl":
                continue
            basename = PurePosixPath(resolved_path).name.lower()
            if (
                _profile_path_tokens(resolved_path) & {"tb", "testbench"}
                or basename.endswith(("_tb.vhd", "_tb.vhdl", "_test.vhd", "_test.vhdl"))
            ):
                continue
            parent_dir = repository_service._normalize_repository_relative_path(
                str(PurePosixPath(resolved_path).parent)
            )
            if parent_dir:
                support_roots.add(parent_dir)
            if _is_operational_profile_entrypoint_candidate(
                resolved_path,
                repo_path=repo_path,
            ):
                entrypoint_paths.add(resolved_path)
    if support_roots:
        return entrypoint_paths, support_roots, config_paths
    for fallback_dir in ("rtl", "src", "hdl", "vhdl", "tb", "sim"):
        candidate_dir = repository_service._normalize_repository_relative_path(
            str(project_dir / fallback_dir)
        )
        if candidate_dir and (repo_path / candidate_dir).is_dir():
            support_roots.add(candidate_dir)
    return entrypoint_paths, support_roots, config_paths
