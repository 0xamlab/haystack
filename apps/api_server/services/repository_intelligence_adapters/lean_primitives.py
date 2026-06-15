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

_KNOWN_SUFFIXES = frozenset({".lean"})
LEAN_CONFIG_BASENAMES = frozenset({"lean-toolchain", "lakefile.lean", "lakefile.toml"})
_MODULE_SEGMENT_RE = r"(?:«[^»]+»|[A-Z][A-Za-z0-9_']*)"
_IDENTIFIER_SEGMENT_RE = r"(?:«[^»]+»|[A-Za-z_][A-Za-z0-9_']*)"
_IMPORT_RE = re.compile(
    rf"(?m)^\s*import\s+(?P<modules>{_MODULE_SEGMENT_RE}(?:\.{_MODULE_SEGMENT_RE})*(?:\s+{_MODULE_SEGMENT_RE}(?:\.{_MODULE_SEGMENT_RE})*)*)\s*$"
)
_ATTR_PREFIX_RE = r"(?:@\[[^\n]+\]\s*)*"
_DECL_RE = re.compile(
    rf"(?m)^\s*{_ATTR_PREFIX_RE}(?P<kind>abbrev|axiom|class|def|example|inductive|instance|lemma|macro|opaque|structure|syntax|theorem)\s+"
    rf"(?P<name>{_IDENTIFIER_SEGMENT_RE})\b"
)
_PACKAGE_RE = re.compile(r"(?m)^\s*package\s+(?P<name>«[^»]+»|[A-Za-z_][A-Za-z0-9_-]*)\b")
_LEAN_LIB_RE = re.compile(r"(?m)^\s*lean_lib\s+(?P<name>«[^»]+»|[A-Za-z_][A-Za-z0-9_-]*)\b")
_TOML_NAME_RE = re.compile(
    r"(?ms)^\s*\[package\]\s.*?^\s*name\s*=\s*['\"](?P<name>[^'\"]+)['\"]"
)
_QUALIFIED_REFERENCE_RE = re.compile(
    rf"\b(?P<module>{_MODULE_SEGMENT_RE}(?:\.{_MODULE_SEGMENT_RE})*)\.(?P<name>{_IDENTIFIER_SEGMENT_RE})\b"
)
_IDENTIFIER_RE = re.compile(rf"\b(?P<name>{_IDENTIFIER_SEGMENT_RE})\b")
_LINE_COMMENT_RE = re.compile(r"(?m)--.*$")
_PROBABLE_SOURCE_MARKERS = (
    "import ",
    "theorem ",
    "lemma ",
    "inductive ",
    "structure ",
    "namespace ",
    "def ",
)
_CONFIG_MARKERS = ("package ", "lean_lib ", "[package]", "name =", "leanprover/lean4:")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abbrev",
        "axiom",
        "class",
        "def",
        "do",
        "else",
        "example",
        "if",
        "import",
        "inductive",
        "in",
        "instance",
        "lemma",
        "let",
        "macro",
        "match",
        "namespace",
        "opaque",
        "open",
        "package",
        "section",
        "structure",
        "syntax",
        "theorem",
        "variable",
        "where",
        "with",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _normalize_name(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized.startswith("«") and normalized.endswith("»"):
        return normalized[1:-1].strip()
    return normalized


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_name(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def strip_comments(text: str) -> str:
    characters = list(text)
    depth = 0
    index = 0
    while index < len(characters):
        current = characters[index]
        next_character = characters[index + 1] if index + 1 < len(characters) else ""
        if current == "/" and next_character == "-":
            depth += 1
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
            continue
        if depth > 0:
            if current == "-" and next_character == "/":
                depth = max(0, depth - 1)
                characters[index] = " "
                characters[index + 1] = " "
                index += 2
                continue
            if current != "\n":
                characters[index] = " "
            index += 1
            continue
        index += 1
    return _LINE_COMMENT_RE.sub("", "".join(characters))


def has_lean_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in _KNOWN_SUFFIXES
        or normalized_path.name.lower() in LEAN_CONFIG_BASENAMES
    )


def is_probable_lean_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_lean_path_hints(normalized_path):
        return False
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not stripped_text.strip():
        return False
    if normalized_path.name.lower() in LEAN_CONFIG_BASENAMES:
        return any(marker in stripped_text for marker in _CONFIG_MARKERS)
    return any(marker in stripped_text for marker in _PROBABLE_SOURCE_MARKERS) or bool(
        _IMPORT_RE.search(stripped_text) or _DECL_RE.search(stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    stem_parts = list(path.with_suffix("").parts)
    for root_name in (
        "Lean",
        "Mathlib",
        "Batteries",
        "Std",
        "src",
        "Source",
        "source",
        "library",
        "lib",
        "examples",
        "Examples",
        "test",
        "tests",
    ):
        if root_name not in stem_parts:
            continue
        root_index = stem_parts.index(root_name)
        tail_parts = stem_parts[root_index:]
        if tail_parts:
            return ".".join(_normalize_name(part) for part in tail_parts if part)
    return ".".join(_normalize_name(part) for part in stem_parts if part)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _DECL_RE.finditer(stripped_text):
        symbol_name = _normalize_name(match.group("name") or "")
        if (
            not symbol_name
            or symbol_name in seen_names
            or symbol_name in _RESERVED_SYMBOL_NAMES
        ):
            continue
        seen_names.add(symbol_name)
        symbol_kind = str(match.group("kind") or "").strip().lower()
        start_line = stripped_text.count("\n", 0, match.start()) + 1
        entries.append((symbol_name, symbol_kind, start_line))
    return tuple(entries)


def parse_import_modules(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    imports: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        modules_value = str(match.group("modules") or "").strip()
        if not modules_value:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        for module_name in modules_value.split():
            normalized_name = _normalize_name(module_name)
            key = (normalized_name, line_number)
            if not normalized_name or key in seen:
                continue
            seen.add(key)
            imports.append((normalized_name, line_number))
    return tuple(imports)


def parse_package_names(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[str, ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    names: list[str] = []
    seen: set[str] = set()
    for regex in (_PACKAGE_RE, _LEAN_LIB_RE, _TOML_NAME_RE):
        for match in regex.finditer(stripped_text):
            normalized_name = _normalize_name(match.group("name") or "").replace("-", "")
            if not normalized_name or normalized_name in seen:
                continue
            seen.add(normalized_name)
            names.append(normalized_name)
    return tuple(names)
