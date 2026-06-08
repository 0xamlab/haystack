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

_KNOWN_SUFFIXES = frozenset({".cue"})
_PACKAGE_RE = re.compile(r"(?m)^\s*package\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_MODULE_RE = re.compile(r'(?m)^\s*module\s*:\s*"(?P<name>[^"\n]+)"')
_IMPORT_RE = re.compile(
    r'(?m)^\s*import(?:\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?\s+"(?P<target>[^"\n]+)"\s*$'
)
_IMPORT_BLOCK_RE = re.compile(r"(?ms)^\s*import\s*\((?P<body>.*?)^\s*\)")
_IMPORT_BLOCK_ITEM_RE = re.compile(
    r'(?m)^\s*(?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s+)?\"(?P<target>[^\"]+)\"'
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>#?[A-Za-z_][A-Za-z0-9_#-]*)\b"
)
_UNQUALIFIED_REFERENCE_RE = re.compile(r"\b#?[A-Za-z_][A-Za-z0-9_#-]*\b")
_DECLARATION_RE = re.compile(
    r"^\s*(?P<name>#?[A-Za-z_][A-Za-z0-9_#-]*)\s*(?:\?|!)?\s*(?P<separator>::|:|=)\s*"
)
_LET_DECLARATION_RE = re.compile(r"^\s*let\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=")
_MARKER_RE = re.compile(r"\b(?:package|import|let)\b|^\s*#?[A-Za-z_][A-Za-z0-9_#-]*\s*(?:\?|!)?\s*(?::|=)", re.MULTILINE)  # noqa: E501
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "_",
        "for",
        "if",
        "import",
        "in",
        "let",
        "null",
        "package",
        "true",
        "false",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


@dataclass(frozen=True)
class _ImportStatement:
    alias: str | None
    target: str
    selector: str | None
    line_number: int


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


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


def strip_comments(text: str) -> str:
    characters = list(text)
    index = 0
    in_string = False
    escape = False
    while index < len(characters):
        current = characters[index]
        next_char = characters[index + 1] if index + 1 < len(characters) else ""
        if in_string:
            if escape:
                escape = False
            elif current == "\\":
                escape = True
            elif current == '"':
                in_string = False
            index += 1
            continue
        if current == '"':
            in_string = True
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
        index += 1
    return "".join(characters)


def has_cue_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def package_name_from_text(text: str) -> str:
    match = _PACKAGE_RE.search(strip_comments(text))
    return str(match.group("name") or "").strip() if match is not None else ""


def cue_module_name_from_text(text: str) -> str:
    match = _MODULE_RE.search(strip_comments(text))
    return str(match.group("name") or "").strip() if match is not None else ""


def is_probable_cue_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_cue_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


def _split_import_target(target: str) -> tuple[str, str | None]:
    normalized_target = str(target or "").strip()
    if not normalized_target:
        return "", None
    path_part, separator, selector = normalized_target.rpartition(":")
    if separator and selector:
        return path_part.strip(), selector.strip() or None
    return normalized_target, None


def parse_import_statements(text: str) -> tuple[_ImportStatement, ...]:
    stripped_text = strip_comments(text)
    statements: list[_ImportStatement] = []
    seen: set[tuple[str | None, str, str | None, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        target, selector = _split_import_target(str(match.group("target") or ""))
        item = (
            str(match.group("alias") or "").strip() or None,
            target,
            selector,
            _line_number(stripped_text, match.start()),
        )
        if item[1] and item not in seen:
            seen.add(item)
            statements.append(_ImportStatement(*item))
    for block_match in _IMPORT_BLOCK_RE.finditer(stripped_text):
        body = str(block_match.group("body") or "")
        for item_match in _IMPORT_BLOCK_ITEM_RE.finditer(body):
            target, selector = _split_import_target(str(item_match.group("target") or ""))
            item = (
                str(item_match.group("alias") or "").strip() or None,
                target,
                selector,
                _line_number(body, item_match.start()) + _line_number(stripped_text, block_match.start()) - 1,  # noqa: E501
            )
            if item[1] and item not in seen:
                seen.add(item)
                statements.append(_ImportStatement(*item))
    return tuple(statements)


def _brace_delta(line: str) -> int:
    delta = 0
    in_string = False
    escape = False
    for character in line:
        if in_string:
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character in "{[(":
            delta += 1
        elif character in "}])":
            delta -= 1
    return delta


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    depth = 0
    for line_number, line in enumerate(stripped_text.splitlines(), start=1):
        line_delta = _brace_delta(line)
        line_stripped = line.strip()
        if depth == 0 and line_stripped and not line_stripped.startswith(("package ", "import ")):
            let_match = _LET_DECLARATION_RE.match(line)
            if let_match is not None:
                name = str(let_match.group("name") or "").strip()
                if name and name not in seen_names and name not in _RESERVED_SYMBOL_NAMES:
                    seen_names.add(name)
                    entries.append(("binding", name, line_number))
            else:
                declaration_match = _DECLARATION_RE.match(line)
                if declaration_match is not None:
                    name = str(declaration_match.group("name") or "").strip()
                    separator = str(declaration_match.group("separator") or "").strip()
                    if name and name not in seen_names and name not in _RESERVED_SYMBOL_NAMES:
                        seen_names.add(name)
                        symbol_kind = "definition" if name.startswith("#") else ("binding" if separator == "=" else "field")  # noqa: E501
                        entries.append((symbol_kind, name, line_number))
        depth = max(0, depth + line_delta)
    return tuple(entries)


def parse_reference_targets(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        item = (
            str(match.group("alias") or "").strip(),
            str(match.group("name") or "").strip(),
            _line_number(stripped_text, match.start()),
        )
        if item[0] and item[1] and item not in seen:
            seen.add(item)
            references.append(item)
    return tuple(references)


def parse_unqualified_reference_targets(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _UNQUALIFIED_REFERENCE_RE.finditer(stripped_text):
        name = str(match.group(0) or "").strip()
        if not name or name in _RESERVED_SYMBOL_NAMES:
            continue
        item = (name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            references.append(item)
    return tuple(references)
