from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".tcl", ".tm"})
_PACKAGE_NAME = r"[A-Za-z0-9_:+.-]+"
_PACKAGE_PROVIDE_RE = re.compile(
    rf"^\s*package\s+provide\s+(?P<name>{_PACKAGE_NAME})\b",
    re.IGNORECASE | re.MULTILINE,
)
_PACKAGE_REQUIRE_RE = re.compile(
    rf"^\s*package\s+require(?:\s+-exact)?\s+(?P<name>{_PACKAGE_NAME})\b",
    re.IGNORECASE | re.MULTILINE,
)
_PACKAGE_IFNEEDED_RE = re.compile(
    rf"^\s*package\s+ifneeded\s+(?P<name>{_PACKAGE_NAME})\b(?P<body>.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_SHEBANG_RE = re.compile(r"(?im)^#!.*\b(?:tclsh|wish)\b")
_SOURCE_RE = re.compile(r"^\s*source\s+(?P<target>.+)$", re.IGNORECASE | re.MULTILINE)
_NAMESPACE_EVAL_RE = re.compile(
    r"^\s*namespace\s+eval\s+(?P<name>::?[A-Za-z_][A-Za-z0-9_:]*)\b",
    re.IGNORECASE | re.MULTILINE,
)
_NAMESPACE_IMPORT_RE = re.compile(
    r"^\s*namespace\s+import\s+(?P<target>.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_PROC_DECL_RE = re.compile(
    r"^\s*proc\s+(?P<name>::?[A-Za-z_][A-Za-z0-9_:]*)\s+\{",
    re.IGNORECASE | re.MULTILINE,
)
_FILE_TARGET_RE = re.compile(r"(?P<path>[A-Za-z0-9_./-]+\.(?:tcl|tm))\b", re.IGNORECASE)
_QUALIFIED_COMMAND_RE = re.compile(
    r"(?<![$\w:])(?P<name>::?[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)+)\b"
)
_RESERVED_COMMANDS = frozenset(
    {
        "append",
        "array",
        "break",
        "catch",
        "continue",
        "dict",
        "else",
        "elseif",
        "error",
        "eval",
        "expr",
        "file",
        "for",
        "foreach",
        "format",
        "global",
        "if",
        "incr",
        "interp",
        "join",
        "lappend",
        "lassign",
        "lindex",
        "list",
        "llength",
        "namespace",
        "package",
        "proc",
        "puts",
        "regexp",
        "regsub",
        "rename",
        "return",
        "set",
        "source",
        "string",
        "subst",
        "switch",
        "trace",
        "unset",
        "uplevel",
        "upvar",
        "variable",
        "while",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int


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


def _normalize_namespace(raw_name: str) -> str:
    return str(raw_name or "").strip().lstrip(":").strip()


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        normalized = str(raw_value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _strip_comment_lines(text: str) -> str:
    stripped_lines = []
    for raw_line in text.splitlines():
        if raw_line.lstrip().startswith("#"):
            stripped_lines.append("")
            continue
        stripped_lines.append(raw_line)
    return "\n".join(stripped_lines)


def _extract_file_targets(raw_value: str) -> tuple[str, ...]:
    return _ordered_names(*(match.group("path") for match in _FILE_TARGET_RE.finditer(raw_value)))


def _namespace_symbol_name(namespace_name: str) -> str:
    normalized = _normalize_namespace(namespace_name)
    if not normalized:
        return ""
    return normalized.split("::")[-1]


def _iter_package_provides(text: str) -> tuple[tuple[str, int], ...]:
    provides: list[tuple[str, int]] = []
    for match in _PACKAGE_PROVIDE_RE.finditer(text):
        normalized = _normalize_namespace(str(match.group("name") or ""))
        if not normalized:
            continue
        provides.append((normalized, _line_number(text, match.start())))
    return tuple(provides)


def _iter_namespace_declarations(text: str) -> tuple[tuple[str, int], ...]:
    namespaces: list[tuple[str, int]] = []
    for match in _NAMESPACE_EVAL_RE.finditer(text):
        normalized = _normalize_namespace(str(match.group("name") or ""))
        if not normalized:
            continue
        namespaces.append((normalized, _line_number(text, match.start())))
    return tuple(namespaces)


def is_probable_tcl_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES:
        return True
    if _SHEBANG_RE.match(text):
        return True
    return bool(
        _PACKAGE_PROVIDE_RE.search(text)
        or _PACKAGE_REQUIRE_RE.search(text)
        or _PACKAGE_IFNEEDED_RE.search(text)
        or _NAMESPACE_EVAL_RE.search(text)
        or _PROC_DECL_RE.search(text)
    )
