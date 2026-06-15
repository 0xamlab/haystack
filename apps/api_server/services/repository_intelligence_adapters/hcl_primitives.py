from __future__ import annotations

from bisect import bisect_right
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".tf", ".tfvars", ".hcl"})
_BLOCK_HEADER_RE = re.compile(
    r'(?m)^\s*(?P<kind>terraform|locals|module|resource|data|variable|output|provider)\b'
    r'(?:\s+"(?P<label1>[^"\n]+)")?(?:\s+"(?P<label2>[^"\n]+)")?\s*\{'
)
_LOCAL_ASSIGNMENT_RE = re.compile(r"(?m)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=")
_MODULE_SOURCE_RE = re.compile(r'(?m)^\s*source\s*=\s*"(?P<source>[^"\n]+)"')
_MODULE_REF_RE = re.compile(r"\bmodule\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_VAR_REF_RE = re.compile(r"\bvar\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_LOCAL_REF_RE = re.compile(r"\blocal\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_DATA_REF_RE = re.compile(
    r"\bdata\.(?P<type>[A-Za-z_][A-Za-z0-9_-]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b"
)
_RESOURCE_REF_RE = re.compile(
    r"\b(?P<type>[A-Za-z_][A-Za-z0-9_-]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b"
)
_ASSIGNMENT_RE = re.compile(r"(?m)^\s*[A-Za-z_][A-Za-z0-9_-]*\s*=")
_RESERVED_REFERENCE_ROOTS = frozenset(
    {
        "count",
        "data",
        "each",
        "false",
        "local",
        "module",
        "null",
        "path",
        "self",
        "terraform",
        "true",
        "var",
    }
)
_PREFERRED_DIRECTORY_ENTRY_BASENAMES = frozenset(
    {"main.tf", "main.hcl", "terragrunt.hcl", "versions.tf"}
)


@dataclass(frozen=True)
class _BlockEntry:
    kind: str
    label1: str
    label2: str
    start_line: int
    end_line: int
    body_start_line: int
    body_end_line: int
    body_text: str


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


def _line_number(text: str, offset: int) -> int:
    return _line_number_from_offsets(_line_offsets(text), offset)


@lru_cache(maxsize=1024)
def _line_offsets(text: str) -> tuple[int, ...]:
    offsets = [0]
    start = 0
    while True:
        newline_index = text.find("\n", start)
        if newline_index < 0:
            break
        offsets.append(newline_index + 1)
        start = newline_index + 1
    return tuple(offsets)


def _line_number_from_offsets(line_offsets: tuple[int, ...], offset: int) -> int:
    if offset <= 0:
        return 1
    return bisect_right(line_offsets, offset)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


@lru_cache(maxsize=1024)
def _strip_comments_cached(text: str) -> str:
    characters = list(text)
    index = 0
    in_string: str | None = None
    while index < len(characters):
        current = characters[index]
        next_char = characters[index + 1] if index + 1 < len(characters) else ""
        if in_string is not None:
            if current == "\\":
                index += 2
                continue
            if current == in_string:
                in_string = None
            index += 1
            continue
        if current in {'"', "'"}:
            in_string = current
            index += 1
            continue
        if current == "/" and next_char == "/":
            while index < len(characters) and characters[index] != "\n":
                characters[index] = " "
                index += 1
            continue
        if current == "/" and next_char == "*":
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
            while index + 1 < len(characters):
                if characters[index] == "*" and characters[index + 1] == "/":
                    characters[index] = " "
                    characters[index + 1] = " "
                    index += 2
                    break
                if characters[index] != "\n":
                    characters[index] = " "
                index += 1
            continue
        if current in {"#", ";"}:
            while index < len(characters) and characters[index] != "\n":
                characters[index] = " "
                index += 1
            continue
        index += 1
    return "".join(characters)


def strip_comments(text: str) -> str:
    return _strip_comments_cached(text)


def has_hcl_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_hcl_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_hcl_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_BLOCK_HEADER_RE.search(stripped_text) or _ASSIGNMENT_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    return str(path.with_suffix("")) if path.suffix else path.name


def _scan_block_end(text: str, open_brace_index: int) -> int:
    depth = 0
    in_string: str | None = None
    index = open_brace_index
    while index < len(text):
        current = text[index]
        if in_string is not None:
            if current == "\\":
                index += 2
                continue
            if current == in_string:
                in_string = None
            index += 1
            continue
        if current in {'"', "'"}:
            in_string = current
            index += 1
            continue
        if current == "{":
            depth += 1
        elif current == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return len(text) - 1


def iter_block_entries(text: str) -> tuple[_BlockEntry, ...]:
    stripped_text = strip_comments(text)
    line_offsets = _line_offsets(stripped_text)
    entries: list[_BlockEntry] = []
    for match in _BLOCK_HEADER_RE.finditer(stripped_text):
        open_brace_index = max(match.end() - 1, match.start())
        close_brace_index = _scan_block_end(stripped_text, open_brace_index)
        body_start = min(open_brace_index + 1, len(stripped_text))
        body_end = max(body_start, close_brace_index)
        entries.append(
            _BlockEntry(
                kind=str(match.group("kind") or "").strip(),
                label1=str(match.group("label1") or "").strip(),
                label2=str(match.group("label2") or "").strip(),
                start_line=_line_number_from_offsets(line_offsets, match.start()),
                end_line=_line_number_from_offsets(line_offsets, close_brace_index),
                body_start_line=_line_number_from_offsets(line_offsets, body_start),
                body_end_line=_line_number_from_offsets(line_offsets, body_end),
                body_text=stripped_text[body_start:body_end],
            )
        )
    return tuple(entries)


def iter_local_assignments(block: _BlockEntry) -> tuple[tuple[str, int], ...]:
    if block.kind != "locals":
        return ()
    line_offsets = _line_offsets(block.body_text)
    entries: list[tuple[str, int]] = []
    seen_names: set[str] = set()
    for match in _LOCAL_ASSIGNMENT_RE.finditer(block.body_text):
        name = str(match.group("name") or "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append(
            (
                name,
                _line_number_from_offsets(line_offsets, match.start("name"))
                + block.body_start_line
                - 1,
            )
        )
    return tuple(entries)


def iter_module_source_statements(block: _BlockEntry) -> tuple[tuple[str, int], ...]:
    if block.kind != "module":
        return ()
    line_offsets = _line_offsets(block.body_text)
    statements: list[tuple[str, int]] = []
    for match in _MODULE_SOURCE_RE.finditer(block.body_text):
        source_target = str(match.group("source") or "").strip()
        if not source_target:
            continue
        statements.append(
            (
                source_target,
                _line_number_from_offsets(line_offsets, match.start("source"))
                + block.body_start_line
                - 1,
            )
        )
    return tuple(statements)
