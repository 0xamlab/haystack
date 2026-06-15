from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    jvm as repository_jvm,
)

StableIdentifier = Callable[[str, Any], str]

XTEND_SUFFIXES = frozenset({".xtend"})
PACKAGE_RE = repository_jvm.PACKAGE_RE
IMPORT_RE = repository_jvm.IMPORT_RE
TYPE_DECL_RE = repository_jvm.TYPE_DECL_RE
TYPE_REFERENCE_RE = repository_jvm.TYPE_REFERENCE_RE
_XTEND_SOURCE_MARKER_RE = re.compile(
    r"(?m)^\s*(?:package\s+[A-Za-z_][A-Za-z0-9_\.]*|"
    r"import\s+[A-Za-z_][A-Za-z0-9_\.]*|"
    r"(?:(?:public|protected|private|abstract|final|static)\s+)*"
    r"(?:class|interface|enum|annotation)\s+[A-Z][A-Za-z0-9_]*|"
    r"(?:def|dispatch)\s+[A-Za-z_][A-Za-z0-9_]*\s*\(|"
    r"extension\s+[A-Za-z_][A-Za-z0-9_\.]*)"
)


def has_xtend_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in XTEND_SUFFIXES


def is_probable_xtend_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    if not has_xtend_path_hints(path):
        return False
    stripped_text = text.strip()
    if not stripped_text:
        return False
    return bool(_XTEND_SOURCE_MARKER_RE.search(stripped_text))


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier | None = None,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in XTEND_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    package_match = PACKAGE_RE.search(text)
    current_package = str(package_match.group("target") or "").strip() if package_match else ""
    for match in TYPE_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name:
            continue
        if current_package:
            aliases.add(f"{current_package}.{symbol_name}")
        else:
            aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


resolve_import = repository_jvm.resolve_import
