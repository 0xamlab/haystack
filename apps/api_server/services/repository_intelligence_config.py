from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _TsconfigPathAliasMapping,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _JS_LIKE_SUFFIXES,
    _normalize_repository_relative_path,
    _normalize_repository_relative_pattern,
)
from apps.api_server.services.repository_intelligence_inventory import (
    _build_workspace_dart_package_index,
)
from apps.api_server.services.repository_intelligence_js_resolution import (
    _candidate_js_like_module_keys,
)

_JSON_ROOT_DIR_RE = re.compile(r'("rootDir"\s*:\s*")(?P<value>[^"]*)(")')
_ZIG_BUILD_MODULE_RE = re.compile(
    r'addModule\(\s*"(?P<name>[^"]+)"[\s\S]{0,600}?root_source_file\s*=\s*b\.path\(\s*"(?P<path>[^"]+\.zig)"\s*\)',
    re.MULTILINE,
)
_UnsupportedHandler = Callable[..., None]


def _raise_unsupported(
    *,
    unsupported_handler: _UnsupportedHandler | None,
    message: str,
    details: dict[str, Any],
) -> None:
    if unsupported_handler is not None:
        unsupported_handler(message=message, details=details)
    raise ValueError(message)


def _strip_jsonc_comments(text: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"(?m)^\s*//.*$", "", without_block_comments)


def _safe_load_jsonc_dict(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(_strip_jsonc_comments(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_jsonc_object(
    *,
    file_path: str,
    text: str,
    unsupported_handler: _UnsupportedHandler | None = None,
) -> dict[str, Any]:
    try:
        payload = json.loads(_strip_jsonc_comments(text))
    except json.JSONDecodeError as exc:
        _raise_unsupported(
            unsupported_handler=unsupported_handler,
            message=(
                "Deterministic local repository planner only supports JSON/JSONC tsconfig "
                f"files that can be parsed safely; failed to parse '{file_path}'."
            ),
            details={"file_path": file_path, "json_error": str(exc)},
        )
    if not isinstance(payload, dict):
        _raise_unsupported(
            unsupported_handler=unsupported_handler,
            message=(
                "Deterministic local repository planner requires tsconfig files to parse "
                f"to JSON objects; '{file_path}' did not."
            ),
            details={"file_path": file_path},
        )
    return payload


def _tsconfig_root_dir_from_payload(payload: dict[str, Any]) -> str | None:
    compiler_options = payload.get("compilerOptions")
    if not isinstance(compiler_options, dict):
        return None
    root_dir = compiler_options.get("rootDir")
    if isinstance(root_dir, str) and root_dir.strip():
        return root_dir.strip()
    return None


def _resolve_tsconfig_extends_path(
    *,
    root_path: Path,
    project_file_path: str,
    extends_value: str | None,
) -> str | None:
    if not extends_value:
        return None
    raw_path = extends_value.strip()
    if not raw_path:
        return None
    if raw_path.startswith(".") or raw_path.startswith(".."):
        root_abs = root_path.resolve()
        project_abs = (root_abs / project_file_path).resolve()
        base_candidate = project_abs.parent / raw_path
        candidates = [base_candidate]
        if base_candidate.suffix == "":
            candidates.append(base_candidate.with_suffix(".json"))
            candidates.append(base_candidate / "tsconfig.json")
        for candidate in candidates:
            candidate_abs = candidate.resolve()
            if candidate_abs == root_abs or root_abs in candidate_abs.parents:
                return _normalize_repository_relative_path(
                    candidate_abs.relative_to(root_abs).as_posix()
                )
    return None


def _update_tsconfig_root_dir_text(
    *,
    file_path: str,
    text: str,
    new_root_dir: str,
    unsupported_handler: _UnsupportedHandler | None = None,
) -> tuple[str, str | None]:
    root_dir_matches = list(_JSON_ROOT_DIR_RE.finditer(text))
    if len(root_dir_matches) != 1:
        _raise_unsupported(
            unsupported_handler=unsupported_handler,
            message=(
                "Deterministic local repository planner requires exactly one rootDir entry "
                f"in '{file_path}'."
            ),
            details={
                "file_path": file_path,
                "root_dir_match_count": len(root_dir_matches),
                "new_root_dir": new_root_dir,
            },
        )
    match = root_dir_matches[0]
    current_root_dir = str(match.group("value"))
    if current_root_dir == new_root_dir:
        _raise_unsupported(
            unsupported_handler=unsupported_handler,
            message=(
                "Deterministic local repository planner found that the tsconfig rootDir in "
                f"'{file_path}' is already '{new_root_dir}'."
            ),
            details={"file_path": file_path, "root_dir": new_root_dir},
        )
    updated_text = (
        f"{text[:match.start('value')]}{new_root_dir}{text[match.end('value') :]}"
    )
    return updated_text, current_root_dir


def _relative_root_dir(from_dir: Path, target_dir: Path) -> str:
    relative = os.path.relpath(target_dir, from_dir)
    normalized = relative.replace("\\", "/")
    return "." if normalized == "." else normalized


def _resolved_tsconfig_compiler_options(
    *,
    root_path: Path,
    config_file_path: str,
    _seen: set[str] | None = None,
) -> dict[str, Any]:
    seen = _seen or set()
    normalized_config_path = _normalize_repository_relative_path(config_file_path)
    if not normalized_config_path or normalized_config_path in seen:
        return {}
    seen.add(normalized_config_path)
    config_path = (root_path / normalized_config_path).resolve()
    payload = _safe_load_jsonc_dict(config_path)
    if payload is None:
        return {}
    compiler_options: dict[str, Any] = {}
    extends_path = _resolve_tsconfig_extends_path(
        root_path=root_path,
        project_file_path=normalized_config_path,
        extends_value=payload.get("extends") if isinstance(payload.get("extends"), str) else None,
    )
    if extends_path:
        compiler_options.update(
            _resolved_tsconfig_compiler_options(
                root_path=root_path,
                config_file_path=extends_path,
                _seen=seen,
            )
        )
    payload_compiler_options = payload.get("compilerOptions")
    if isinstance(payload_compiler_options, dict):
        compiler_options.update(payload_compiler_options)
    return compiler_options


def _tsconfig_module_candidates(file_path: str) -> tuple[str, ...]:
    path = PurePosixPath(file_path)
    candidates = [str(path), str(path.with_suffix(""))]
    if path.suffix in _JS_LIKE_SUFFIXES and path.stem == "index":
        parent = str(path.parent)
        if parent and parent != ".":
            candidates.append(parent)
    return tuple(
        dict.fromkeys(
            _normalize_repository_relative_path(candidate)
            for candidate in candidates
            if candidate
        )
    )


def _extend_module_index_with_tsconfig_aliases(
    *,
    root_path: Path,
    file_paths: Sequence[str],
    index: dict[str, str],
) -> None:
    config_file_set = {
        file_path
        for file_path in file_paths
        if PurePosixPath(file_path).name in {"tsconfig.json", "jsconfig.json"}
        or (
            PurePosixPath(file_path).suffix == ".json"
            and PurePosixPath(file_path).name.startswith("tsconfig.")
        )
    }
    candidate_dirs = {""}
    for file_path in file_paths:
        parent = PurePosixPath(file_path).parent
        while str(parent) not in {"", "."}:
            candidate_dirs.add(_normalize_repository_relative_path(str(parent)))
            parent = parent.parent
    for candidate_dir in sorted(candidate_dirs):
        base_dir = root_path / candidate_dir if candidate_dir else root_path
        for pattern in ("tsconfig*.json", "jsconfig*.json"):
            for candidate in sorted(base_dir.glob(pattern)):
                if not candidate.is_file():
                    continue
                normalized_candidate = _normalize_repository_relative_path(
                    str(candidate.relative_to(root_path))
                )
                if normalized_candidate:
                    config_file_set.add(normalized_candidate)
    config_files = sorted(config_file_set)
    if not config_files:
        return

    normalized_file_paths = tuple(
        _normalize_repository_relative_path(file_path) for file_path in file_paths
    )
    candidate_keys_by_file = {
        file_path: _tsconfig_module_candidates(file_path) for file_path in normalized_file_paths
    }

    for config_file_path in config_files:
        compiler_options = _resolved_tsconfig_compiler_options(
            root_path=root_path,
            config_file_path=config_file_path,
        )
        config_dir = _normalize_repository_relative_path(
            str(PurePosixPath(config_file_path).parent)
        )
        base_url_value = compiler_options.get("baseUrl")
        base_dir = config_dir
        if isinstance(base_url_value, str) and base_url_value.strip():
            base_dir = _normalize_repository_relative_pattern(
                str(PurePosixPath(config_dir) / base_url_value.strip())
            )

        if base_dir:
            base_prefix = f"{base_dir}/"
            for file_path, candidate_keys in candidate_keys_by_file.items():
                for candidate_key in candidate_keys:
                    if candidate_key == base_dir:
                        continue
                    if candidate_key.startswith(base_prefix):
                        alias = candidate_key[len(base_prefix) :]
                        if alias:
                            index.setdefault(alias, file_path)

        raw_paths = compiler_options.get("paths")
        if not isinstance(raw_paths, dict):
            continue
        mappings: list[_TsconfigPathAliasMapping] = []
        for alias_pattern, raw_targets in raw_paths.items():
            if not isinstance(alias_pattern, str) or not alias_pattern.strip():
                continue
            target_values = raw_targets if isinstance(raw_targets, list) else [raw_targets]
            for raw_target in target_values:
                if not isinstance(raw_target, str) or not raw_target.strip():
                    continue
                resolved_target_pattern = _normalize_repository_relative_pattern(
                    str(PurePosixPath(base_dir) / raw_target.strip())
                )
                if resolved_target_pattern:
                    mappings.append(
                        _TsconfigPathAliasMapping(
                            alias_pattern=alias_pattern.strip(),
                            target_pattern=resolved_target_pattern,
                        )
                    )
        for mapping in mappings:
            if "*" in mapping.alias_pattern:
                alias_prefix, alias_suffix = mapping.alias_pattern.split("*", 1)
                if "*" not in mapping.target_pattern:
                    continue
                target_prefix, target_suffix = mapping.target_pattern.split("*", 1)
                for file_path, candidate_keys in candidate_keys_by_file.items():
                    for candidate_key in candidate_keys:
                        if not candidate_key.startswith(target_prefix):
                            continue
                        if target_suffix and not candidate_key.endswith(target_suffix):
                            continue
                        wildcard_value = candidate_key[len(target_prefix) :]
                        if target_suffix:
                            wildcard_value = wildcard_value[: -len(target_suffix)]
                        alias = f"{alias_prefix}{wildcard_value}{alias_suffix}"
                        if alias:
                            index.setdefault(alias, file_path)
                continue
            for candidate_key in _candidate_js_like_module_keys(mapping.target_pattern):
                resolved = index.get(candidate_key)
                if resolved is not None:
                    index.setdefault(mapping.alias_pattern, resolved)
                    break


def _extend_module_index_with_zig_build_aliases(
    *,
    root_path: Path,
    file_paths: Sequence[str] | None = None,
    index: dict[str, str],
) -> None:
    del file_paths
    build_zig_path = root_path / "build.zig"
    if not build_zig_path.is_file():
        return
    try:
        text = build_zig_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for match in _ZIG_BUILD_MODULE_RE.finditer(text):
        module_name = match.group("name").strip()
        target_path = _normalize_repository_relative_path(match.group("path"))
        if not module_name or not target_path:
            continue
        resolved = index.get(target_path)
        if resolved is None:
            continue
        index.setdefault(module_name, resolved)


def _extend_module_index_with_dart_package_aliases(
    *,
    root_path: Path,
    file_paths: Sequence[str],
    index: dict[str, str],
) -> None:
    workspace_dart_package_index = _build_workspace_dart_package_index(root_path)
    if not workspace_dart_package_index:
        return
    for package_name, package_roots in workspace_dart_package_index.items():
        for package_root in package_roots:
            lib_prefix = _normalize_repository_relative_path(
                str(PurePosixPath(package_root) / "lib") if package_root else "lib"
            )
            if not lib_prefix:
                continue
            lib_prefix_with_sep = f"{lib_prefix}/"
            for file_path in file_paths:
                if not file_path.startswith(lib_prefix_with_sep):
                    continue
                relative_lib_path = file_path[len(lib_prefix_with_sep) :]
                if not relative_lib_path or not relative_lib_path.endswith(".dart"):
                    continue
                index.setdefault(f"package:{package_name}/{relative_lib_path}", file_path)
