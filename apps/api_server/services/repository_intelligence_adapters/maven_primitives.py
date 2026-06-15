from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

MAVEN_PROJECT_BASENAMES = frozenset({"pom.xml"})
MAVEN_CONFIG_BASENAMES = frozenset({"maven.config"})
_XML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


@dataclass(frozen=True)
class MavenPomDocument:
    group_id: str | None
    artifact_id: str | None
    packaging: str | None
    model_version: str | None
    modules: tuple[str, ...]
    parent_relative_path: str | None
    dependencies: tuple[str, ...]


def _preserve_line_count(match: re.Match[str]) -> str:
    return "".join("\n" if character == "\n" else " " for character in match.group(0))


def strip_comments(text: str) -> str:
    return _XML_COMMENT_RE.sub(_preserve_line_count, text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_maven_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    lower_name = normalized_path.name.lower()
    if lower_name in MAVEN_PROJECT_BASENAMES:
        return True
    return lower_name in MAVEN_CONFIG_BASENAMES and any(
        part.lower() == ".mvn" for part in normalized_path.parts
    )


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1].lower()


def _child_text(element: ET.Element, child_name: str) -> str | None:
    for child in list(element):
        if _local_name(child.tag) != child_name:
            continue
        value = normalize_identifier(child.text or "")
        return value or None
    return None


def _child_texts(element: ET.Element, parent_name: str, child_name: str) -> tuple[str, ...]:
    for child in list(element):
        if _local_name(child.tag) != parent_name:
            continue
        values: list[str] = []
        for nested_child in list(child):
            if _local_name(nested_child.tag) != child_name:
                continue
            value = normalize_identifier(nested_child.text or "")
            if value:
                values.append(value)
        return tuple(values)
    return ()


def parse_maven_pom(text: str) -> MavenPomDocument | None:
    try:
        root = ET.fromstring(strip_comments(text))
    except ET.ParseError:
        return None
    if _local_name(root.tag) != "project":
        return None
    artifact_id = _child_text(root, "artifactid")
    group_id = _child_text(root, "groupid")
    packaging = _child_text(root, "packaging")
    model_version = _child_text(root, "modelversion")
    modules = _child_texts(root, "modules", "module")
    parent_relative_path: str | None = None
    dependencies: list[str] = []
    for child in list(root):
        child_name = _local_name(child.tag)
        if child_name == "parent":
            parent_relative_path = _child_text(child, "relativepath")
        if child_name != "dependencies":
            continue
        for dependency in list(child):
            if _local_name(dependency.tag) != "dependency":
                continue
            dependency_group_id = _child_text(dependency, "groupid")
            dependency_artifact_id = _child_text(dependency, "artifactid")
            if not dependency_group_id or not dependency_artifact_id:
                continue
            dependencies.append(f"{dependency_group_id}:{dependency_artifact_id}")
    return MavenPomDocument(
        group_id=group_id,
        artifact_id=artifact_id,
        packaging=packaging,
        model_version=model_version,
        modules=modules,
        parent_relative_path=normalize_identifier(parent_relative_path or "") or None,
        dependencies=tuple(dict.fromkeys(dependencies)),
    )


def is_probable_maven_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    lower_name = normalized_path.name.lower()
    if lower_name in MAVEN_PROJECT_BASENAMES:
        document = parse_maven_pom(text)
        return document is not None and (
            # ``modelVersion`` is the canonical, required element of every Maven POM, so a
            # parsed ``<project>`` carrying it is a Maven POM even when the coordinates
            # (groupId/artifactId) are inherited from a parent and omitted here.
            document.model_version is not None
            or document.artifact_id is not None
            or document.group_id is not None
            or document.modules
            or document.dependencies
        )
    if lower_name in MAVEN_CONFIG_BASENAMES and has_maven_path_hints(normalized_path):
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            return line.startswith("-")
    return False


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    if normalized_path.name.lower() == "pom.xml":
        return normalized_path.parent.name or "pom"
    return normalized_path.name


def _normalize_repository_relative_path(value: str) -> str:
    raw_parts = PurePosixPath(str(value).replace("\\", "/")).parts
    normalized_parts: list[str] = []
    for part in raw_parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if not has_maven_path_hints(path):
        return set()
    aliases = {
        _normalize_repository_relative_path(file_path),
        path.name,
        module_name_from_path(file_path),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not text or not is_probable_maven_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    if path.name.lower() == "pom.xml":
        document = parse_maven_pom(text)
        if document and document.artifact_id:
            aliases.add(document.artifact_id)
            if document.group_id:
                aliases.add(f"{document.group_id}:{document.artifact_id}")
    return {alias for alias in aliases if alias}


def resolve_project_path(
    *,
    current_file: str,
    project_path: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(project_path)
    if not normalized_target:
        return None
    current_parent = PurePosixPath(current_file).parent
    candidate_path = PurePosixPath(normalized_target)
    if candidate_path.name.lower() != "pom.xml":
        candidate_path = candidate_path / "pom.xml"
    normalized_candidate = normalize_repository_relative_path(str(current_parent / candidate_path))
    if normalized_candidate in module_index:
        return module_index[normalized_candidate]
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=(normalized_candidate, PurePosixPath(normalized_candidate).name),
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[Any, ...]:
    from apps.api_server.services.repository_intelligence_contracts import _Dependency

    normalized_path = PurePosixPath(file_path)
    if not is_probable_maven_source(path=normalized_path, text=text):
        return ()
    if normalized_path.name.lower() != "pom.xml":
        return ()
    document = parse_maven_pom(text)
    if document is None:
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str, str]] = set()
    for module_path in document.modules:
        target_file = resolve_project_path(
            current_file=file_path,
            project_path=module_path,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, module_path, "module")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": module_path,
                        "kind": "module",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=PurePosixPath(module_path).name or None,
                dependency_type="module",
            )
        )
    if document.parent_relative_path:
        target_file = resolve_project_path(
            current_file=file_path,
            project_path=document.parent_relative_path,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, document.parent_relative_path, "parent")
        if dependency_key not in seen_dependencies:
            seen_dependencies.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": document.parent_relative_path,
                            "kind": "parent",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol="parent",
                    dependency_type="parent",
                )
            )
    for dependency_coordinate in document.dependencies:
        dependency_key = (None, dependency_coordinate, "dependency")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": dependency_coordinate,
                        "kind": "dependency",
                    },
                ),
                source_file=file_path,
                target_file=None,
                target_symbol=dependency_coordinate,
                dependency_type="dependency",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Symbol, ...], tuple[Any, ...], tuple[Any, ...]]:
    normalized_path = PurePosixPath(file_path)
    if not is_probable_maven_source(path=normalized_path, text=text):
        return (), (), ()
    line_count = max(1, text.count("\n") + 1)
    symbols: list[_Symbol] = []
    if normalized_path.name.lower() == "pom.xml":
        document = parse_maven_pom(text)
        if document is None:
            return (), (), ()
        module_name = document.artifact_id or module_name_from_path(file_path)
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": module_name, "kind": "maven_project"},
                ),
                symbol_name=module_name,
                symbol_kind="maven_project",
                start_line=1,
                end_line=line_count,
                parent_symbol_id=None,
                signature=f"maven_project {module_name}",
            )
        )
    else:
        module_name = module_name_from_path(file_path)
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": module_name, "kind": "maven_config"},
                ),
                symbol_name=module_name,
                symbol_kind="maven_config",
                start_line=1,
                end_line=line_count,
                parent_symbol_id=None,
                signature=f"maven_config {module_name}",
            )
        )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    return tuple(symbols), dependencies, ()
