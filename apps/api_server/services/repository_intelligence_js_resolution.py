from __future__ import annotations

from pathlib import PurePosixPath

from apps.api_server.services.repository_intelligence_indexing import (
    _JS_LIKE_SUFFIXES,
    _normalize_repository_relative_path,
)


def _candidate_js_like_module_keys(base_path: str) -> tuple[str, ...]:
    normalized_base = _normalize_repository_relative_path(base_path)
    if not normalized_base:
        return ()
    if PurePosixPath(normalized_base).suffix:
        return (normalized_base,)
    candidates = [normalized_base]
    candidates.extend(f"{normalized_base}{suffix}" for suffix in _JS_LIKE_SUFFIXES)
    candidates.extend(f"{normalized_base}/index{suffix}" for suffix in _JS_LIKE_SUFFIXES)
    return tuple(dict.fromkeys(candidates))


def _resolve_workspace_package_import(
    *,
    import_target: str,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
) -> str | None:
    for package_name in sorted(workspace_package_index, key=len, reverse=True):
        if import_target != package_name and not import_target.startswith(f"{package_name}/"):
            continue
        subpath = import_target[len(package_name) :].lstrip("/")
        for package_root in workspace_package_index[package_name]:
            candidate_bases = (
                [f"{package_root}/{subpath}", f"{package_root}/src/{subpath}"]
                if subpath
                else [f"{package_root}/src/index", f"{package_root}/index"]
            )
            for candidate_base in candidate_bases:
                for candidate_key in _candidate_js_like_module_keys(candidate_base):
                    resolved = module_index.get(candidate_key)
                    if resolved is not None:
                        return resolved
    return None


def _resolve_js_like_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
) -> str | None:
    direct_match = module_index.get(import_target)
    if direct_match is not None:
        return direct_match
    if import_target.startswith("."):
        current_dir = _normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
        relative_base = _normalize_repository_relative_path(
            str(PurePosixPath(current_dir) / import_target)
        )
        for candidate_key in _candidate_js_like_module_keys(relative_base):
            resolved = module_index.get(candidate_key)
            if resolved is not None:
                return resolved
        return None
    return _resolve_workspace_package_import(
        import_target=import_target,
        module_index=module_index,
        workspace_package_index=workspace_package_index,
    )
