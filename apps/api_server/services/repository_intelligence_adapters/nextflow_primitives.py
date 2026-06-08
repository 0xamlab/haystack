from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

NEXTFLOW_SOURCE_SUFFIXES = frozenset({".nf"})
NEXTFLOW_CONFIG_BASENAMES = frozenset({"nextflow.config"})
_PROCESS_RE = re.compile(r"^\s*process\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
_WORKFLOW_RE = re.compile(
    r"^\s*workflow(?:\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*))?\s*\{",
    re.MULTILINE,
)
_FUNCTION_RE = re.compile(r"^\s*def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
_INCLUDE_RE = re.compile(
    r"^\s*include\s*\{(?P<body>.*?)\}\s*from\s*(?P<quote>['\"])(?P<target>.+?)(?P=quote)",
    re.MULTILINE | re.DOTALL,
)
_INCLUDE_CONFIG_RE = re.compile(
    r"^\s*includeConfig\s+(?P<quote>['\"])(?P<target>.+?)(?P=quote)",
    re.MULTILINE,
)
_MODULE_SYMBOL_RE = re.compile(
    r"(?<![\w.])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
)
_SOURCE_MARKER_RE = re.compile(
    r"(?m)(?:^\s*process\s+[A-Za-z_][A-Za-z0-9_]*\b|^\s*workflow(?:\s+[A-Za-z_][A-Za-z0-9_]*)?\s*\{|^\s*include\s*\{|^\s*def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(|\bnextflow\.enable\.dsl\b|^\s*params(?:\.|\s*\{)|^\s*profiles\s*\{|^\s*manifest\s*\{)"
)
_CONFIG_MARKER_RE = re.compile(
    r"(?m)(?:^\s*includeConfig\b|\bnextflow\.enable\.dsl\b|^\s*params\s*\{|^\s*profiles\s*\{|^\s*manifest\s*\{|^\s*process\s*\{)"
)
_COMMENT_MARKER_RE = re.compile(r"^\s*#")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "as",
        "def",
        "else",
        "emit",
        "from",
        "if",
        "include",
        "includeConfig",
        "main",
        "process",
        "script",
        "shell",
        "stub",
        "take",
        "then",
        "when",
        "workflow",
    }
)


@dataclass(frozen=True)
class _SymbolEntry:
    name: str
    kind: str
    start_line: int
    qualified_names: tuple[str, ...]


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _ordered_names(*raw_names: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_names:
        candidate = str(raw_name or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)
    return tuple(ordered)


def strip_comments(text: str) -> str:
    characters: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    block_depth = 0
    line_start = True
    index = 0
    while index < len(text):
        character = text[index]
        next_two = text[index : index + 2]
        if block_depth:
            if next_two == "/*":
                block_depth += 1
                characters.extend("  ")
                index += 2
                continue
            if next_two == "*/":
                block_depth -= 1
                characters.extend("  ")
                index += 2
                continue
            characters.append("\n" if character == "\n" else " ")
            line_start = character == "\n"
            index += 1
            continue
        if in_single or in_double:
            characters.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif in_single and character == "'":
                in_single = False
            elif in_double and character == '"':
                in_double = False
            line_start = character == "\n"
            index += 1
            continue
        if next_two == "/*":
            block_depth = 1
            characters.extend("  ")
            index += 2
            continue
        if next_two == "//":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        if line_start and _COMMENT_MARKER_RE.match(text[index:]):
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character == "'":
            in_single = True
        elif character == '"':
            in_double = True
        line_start = character == "\n"
        index += 1
    return "".join(characters)


def has_nextflow_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in NEXTFLOW_SOURCE_SUFFIXES
        or normalized_path.name.lower() in NEXTFLOW_CONFIG_BASENAMES
    )


def is_probable_nextflow_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_nextflow_path_hints(normalized_path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if normalized_path.name.lower() in NEXTFLOW_CONFIG_BASENAMES:
        return bool(_CONFIG_MARKER_RE.search(stripped_text))
    return bool(_SOURCE_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.name.lower() in NEXTFLOW_CONFIG_BASENAMES:
        parts = list(path.parent.parts)
    else:
        parts = list(path.with_suffix("").parts)
    while parts and parts[0] in {"modules", "subworkflows", "workflows", "pipelines", "scripts", "bin", "lib", "src"}:
        parts = parts[1:]
    if parts and parts[-1] in {"main", "workflow"}:
        parts = parts[:-1] or parts
    return "/".join(part for part in parts if part)


def _parse_include_body(raw_body: str) -> tuple[tuple[str, str | None], ...]:
    normalized_body = raw_body.replace("\n", ";")
    parsed: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for segment in normalized_body.split(";"):
        candidate = segment.strip().rstrip(",")
        if not candidate:
            continue
        match = re.fullmatch(
            r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?",
            candidate,
        )
        if match is None:
            continue
        name = str(match.group("name") or "").strip()
        alias = str(match.group("alias") or "").strip() or None
        if not name or name in _RESERVED_SYMBOL_NAMES:
            continue
        item = (name, alias)
        if item not in seen:
            seen.add(item)
            parsed.append(item)
    return tuple(parsed)


def parse_include_entries(
    text: str,
) -> tuple[tuple[str, tuple[tuple[str, str | None], ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, tuple[tuple[str, str | None], ...], int]] = []
    seen: set[tuple[str, tuple[tuple[str, str | None], ...], int]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip()
        if not target:
            continue
        parsed_symbols = _parse_include_body(str(match.group("body") or ""))
        item = (target, parsed_symbols, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def parse_config_include_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _INCLUDE_CONFIG_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip()
        if not target:
            continue
        item = (target, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def collect_symbol_entries(file_path: str, text: str) -> tuple[_SymbolEntry, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
    entries: list[_SymbolEntry] = []
    seen: set[tuple[str, str, int]] = set()

    def _append_symbol(name: str, kind: str, offset: int) -> None:
        normalized_name = str(name or "").strip()
        if not normalized_name or normalized_name in _RESERVED_SYMBOL_NAMES:
            return
        line = _line_number(stripped_text, offset)
        key = (normalized_name, kind, line)
        if key in seen:
            return
        seen.add(key)
        entries.append(
            _SymbolEntry(
                name=normalized_name,
                kind=kind,
                start_line=line,
                qualified_names=_ordered_names(
                    normalized_name,
                    f"{module_name.replace('/', '.')}.{normalized_name}" if module_name else "",
                    f"{module_name}/{normalized_name}" if module_name else "",
                ),
            )
        )

    for match in _PROCESS_RE.finditer(stripped_text):
        _append_symbol(str(match.group("name") or ""), "process", match.start())
    for match in _WORKFLOW_RE.finditer(stripped_text):
        workflow_name = str(match.group("name") or "").strip() or "workflow"
        _append_symbol(workflow_name, "workflow", match.start())
    for match in _FUNCTION_RE.finditer(stripped_text):
        _append_symbol(str(match.group("name") or ""), "function", match.start())
    return tuple(sorted(entries, key=lambda item: (item.start_line, item.name, item.kind)))
