from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path

from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
)

_DEFAULT_EXCLUDED_PATH_PARTS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".next",
        ".turbo",
        ".venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".pixi",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "dist_fresh",
        "node_modules",
        "target",
        "vendor",
        "venv",
    }
)

_DART_PUBSPEC_NAME_RE = re.compile(
    r"^\s*name\s*:\s*(?P<name>[A-Za-z0-9_-]+)\s*$",
    re.MULTILINE,
)


def _read_dart_pubspec_name(pubspec_path: Path) -> str | None:
    try:
        text = pubspec_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _DART_PUBSPEC_NAME_RE.search(text)
    if match is None:
        return None
    package_name = str(match.group("name") or "").strip()
    return package_name or None


def _build_workspace_package_index(root_path: Path) -> dict[str, tuple[str, ...]]:
    index: defaultdict[str, list[str]] = defaultdict(list)
    for current_root, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [
            name for name in sorted(dirnames) if name not in _DEFAULT_EXCLUDED_PATH_PARTS
        ]
        if "package.json" not in filenames:
            continue
        package_json_path = Path(current_root) / "package.json"
        try:
            payload = json.loads(package_json_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        package_name = payload.get("name")
        if not isinstance(package_name, str) or not package_name.strip():
            continue
        relative_root = _normalize_repository_relative_path(
            str(Path(current_root).relative_to(root_path))
        )
        index[package_name.strip()].append(relative_root)
    return {
        package_name: tuple(sorted(set(relative_roots)))
        for package_name, relative_roots in sorted(index.items())
    }


def _build_workspace_dart_package_index(root_path: Path) -> dict[str, tuple[str, ...]]:
    index: defaultdict[str, list[str]] = defaultdict(list)
    for current_root, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [
            name for name in sorted(dirnames) if name not in _DEFAULT_EXCLUDED_PATH_PARTS
        ]
        if "pubspec.yaml" not in filenames:
            continue
        pubspec_path = Path(current_root) / "pubspec.yaml"
        package_name = _read_dart_pubspec_name(pubspec_path)
        if not package_name:
            continue
        relative_root = _normalize_repository_relative_path(
            str(Path(current_root).relative_to(root_path))
        )
        index[package_name].append(relative_root)
    return {
        package_name: tuple(sorted(set(relative_roots)))
        for package_name, relative_roots in sorted(index.items())
    }


def _build_workspace_go_module_index(root_path: Path) -> dict[str, tuple[str, ...]]:
    index: defaultdict[str, list[str]] = defaultdict(list)
    for current_root, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [
            name for name in sorted(dirnames) if name not in _DEFAULT_EXCLUDED_PATH_PARTS
        ]
        if "go.mod" not in filenames:
            continue
        go_mod_path = Path(current_root) / "go.mod"
        try:
            lines = go_mod_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        module_name = None
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith("module "):
                continue
            candidate = stripped.removeprefix("module ").strip()
            if candidate:
                module_name = candidate
                break
        if not module_name:
            continue
        relative_root = _normalize_repository_relative_path(
            str(Path(current_root).relative_to(root_path))
        )
        index[module_name].append(relative_root)
    return {
        module_name: tuple(sorted(set(relative_roots)))
        for module_name, relative_roots in sorted(index.items())
    }
