from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    jvm as repository_jvm,
)

StableIdentifier = Callable[[str, Any], str]

GROOVY_SUFFIXES = frozenset({".groovy", ".gradle"})
GROOVY_CONFIG_BASENAMES = frozenset({"build.gradle", "settings.gradle", "init.gradle"})

PACKAGE_RE = repository_jvm.PACKAGE_RE
IMPORT_RE = repository_jvm.IMPORT_RE
TYPE_DECL_RE = repository_jvm.TYPE_DECL_RE
TYPE_REFERENCE_RE = repository_jvm.TYPE_REFERENCE_RE

_GROOVY_SOURCE_MARKER_RE = re.compile(
    r"(?m)^\s*(?:package\s+[A-Za-z_][A-Za-z0-9_\.]*|"
    r"import\s+[A-Za-z_][A-Za-z0-9_\.]*|"
    r"(?:(?:public|protected|private|abstract|final|static)\s+)*"
    r"(?:class|trait|interface|enum)\s+[A-Z][A-Za-z0-9_]*|"
    r"def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(|@Grab\b)"
)
_GROOVY_BUILD_MARKER_RE = re.compile(
    r"(?m)^\s*(?:plugins\s*\{|dependencies\s*\{|repositories\s*\{|subprojects\s*\{|"
    r"allprojects\s*\{|task\s+[A-Za-z_][A-Za-z0-9_]*\b|apply\s+plugin\s*:|rootProject\b|"
    r"include\s+['\"])"
)


def has_groovy_path_hints(*, path: Path | PurePosixPath | str) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in GROOVY_SUFFIXES
        or normalized_path.name.lower() in GROOVY_CONFIG_BASENAMES
    )


def is_probable_groovy_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    stripped_text = text.strip()
    if not stripped_text:
        return False
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() == ".gradle" or normalized_path.name.lower() in GROOVY_CONFIG_BASENAMES:
        return bool(_GROOVY_BUILD_MARKER_RE.search(stripped_text))
    if normalized_path.suffix.lower() == ".groovy":
        return bool(_GROOVY_SOURCE_MARKER_RE.search(stripped_text))
    return False


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier | None = None,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    aliases = {
        file_path,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    if path.name.lower() in GROOVY_CONFIG_BASENAMES:
        aliases.add(path.name.lower())
    aliases.update(
        repository_jvm.declared_type_aliases_for_path(
            root_path=root_path,
            file_path=file_path,
        )
    )
    return {alias for alias in aliases if alias}


resolve_import = repository_jvm.resolve_import
