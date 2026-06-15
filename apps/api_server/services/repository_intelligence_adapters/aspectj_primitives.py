from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    jvm as repository_jvm,
)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

ASPECTJ_SUFFIXES = frozenset({".aj"})
ASPECTJ_PATH_PARTS = frozenset({"aspect", "aspects", "aop"})

PACKAGE_RE = repository_jvm.PACKAGE_RE
IMPORT_RE = repository_jvm.IMPORT_RE
TYPE_DECL_RE = repository_jvm.TYPE_DECL_RE
TYPE_REFERENCE_RE = repository_jvm.TYPE_REFERENCE_RE

ASPECT_DECL_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|abstract|final|static|strictfp|privileged)\s+)*"
    r"aspect\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
POINTCUT_DECL_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|abstract|final|static)\s+)*"
    r"pointcut\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_ASPECTJ_MARKER_RE = re.compile(
    r"(?m)^\s*(?:"
    r"(?:(?:public|protected|private|abstract|final|static|strictfp|privileged)\s+)*aspect\s+[A-Z][A-Za-z0-9_]*|"
    r"(?:(?:public|protected|private|abstract|final|static)\s+)*pointcut\s+[A-Za-z_][A-Za-z0-9_]*\s*\(|"
    r"(?:before|after|around)\s*\([^)]*\)\s*:|"
    r"declare\s+(?:warning|error|parents|precedence|soft)\s*:|"
    r"percflow(?:below)?\s*\(|"
    r"per(?:this|target|typewithin)\s*\("
    r")"
)
POINTCUT_REFERENCE_RE = re.compile(r"\b(?P<name>[a-z][A-Za-z0-9_]*)\s*\(")
POINTCUT_REFERENCE_EXCLUSIONS = frozenset(
    {
        "adviceexecution",
        "after",
        "around",
        "args",
        "before",
        "call",
        "cflow",
        "cflowbelow",
        "execution",
        "get",
        "handler",
        "if",
        "initialization",
        "new",
        "percflow",
        "percflowbelow",
        "pertarget",
        "perthis",
        "pertypewithin",
        "preinitialization",
        "proceed",
        "set",
        "staticinitialization",
        "super",
        "target",
        "this",
        "withincode",
        "within",
    }
)


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _line_count(text: str) -> int:
    return max(text.count("\n") + 1, 1)


def has_aspectj_path_hints(*, path: Path | PurePosixPath | str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() in ASPECTJ_SUFFIXES:
        return True
    return any(part.lower() in ASPECTJ_PATH_PARTS for part in normalized_path.parts)


def is_probable_aspectj_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in ASPECTJ_SUFFIXES:
        return False
    stripped_text = text.strip()
    if not stripped_text:
        return False
    if _ASPECTJ_MARKER_RE.search(stripped_text):
        return True
    return bool(
        PACKAGE_RE.search(stripped_text)
        or IMPORT_RE.search(stripped_text)
        or TYPE_DECL_RE.search(stripped_text)
    )


def iter_declared_type_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    entries: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in ((ASPECT_DECL_RE, "aspect"), (TYPE_DECL_RE, "type")):
        for match in regex.finditer(text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name or symbol_name in seen_names:
                continue
            seen_names.add(symbol_name)
            start_line = _line_number(text, match.start())
            entries.append(
                {
                    "symbol_id": stable_identifier(
                        "symbol",
                        {
                            "file_path": file_path,
                            "kind": symbol_kind,
                            "name": symbol_name,
                            "line": start_line,
                        },
                    ),
                    "symbol_name": symbol_name,
                    "symbol_kind": symbol_kind,
                    "start_line": start_line,
                    "end_line": start_line,
                    "signature": match.group(0).strip(),
                }
            )
    return tuple(
        sorted(entries, key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
    )


def iter_pointcut_entries(text: str) -> tuple[tuple[str, int], ...]:
    return tuple(
        (
            str(match.group("name") or "").strip(),
            _line_number(text, match.start()),
        )
        for match in POINTCUT_DECL_RE.finditer(text)
        if str(match.group("name") or "").strip()
    )


def iter_pointcut_reference_names(text: str) -> tuple[tuple[str, int], ...]:
    declaration_lines = {line_number for _name, line_number in iter_pointcut_entries(text)}
    references: list[tuple[str, int]] = []
    for match in POINTCUT_REFERENCE_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in POINTCUT_REFERENCE_EXCLUSIONS:
            continue
        line_number = _line_number(text, match.start())
        if line_number in declaration_lines:
            continue
        references.append((symbol_name, line_number))
    return tuple(references)


def path_aliases_for_file(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    aliases = {
        file_path,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    return {alias for alias in aliases if alias and alias != "."}


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    normalized_path = normalized_target.replace(".", "/")
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_path,
            f"{normalized_path}.aj",
            f"{normalized_path}.java",
            f"{normalized_path}.groovy",
            f"{normalized_path}.kt",
            f"{normalized_path}.kts",
            f"{normalized_path}.scala",
        ],
    )
