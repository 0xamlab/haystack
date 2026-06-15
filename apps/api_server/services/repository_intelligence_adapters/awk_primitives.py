from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".awk", ".auk", ".gawk", ".mawk", ".nawk"})
_SHEBANG_AWK_RE = re.compile(r"^#![^\n]*\b(?:gawk|mawk|nawk|awk)\b", re.IGNORECASE)
_INCLUDE_RE = re.compile(
    r"^\s*@include\s+(?P<target>\"[^\"]+\"|'[^']+'|<[^>]+>)",
    re.MULTILINE,
)
_FUNCTION_DECL_RE = re.compile(
    r"^\s*function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_BLOCK_DECL_RE = re.compile(
    r"^\s*(?P<name>BEGINFILE|ENDFILE|BEGIN|END)\b[^\n{]*\{",
    re.MULTILINE,
)
_RAW_SOURCE_MARKER_RE = re.compile(
    r"(?m)^\s*(?:function\s+[A-Za-z_][A-Za-z0-9_]*\s*\(|BEGINFILE|ENDFILE|BEGIN|END\b|@include\b)"
)
_CALL_RE = re.compile(r"(?<![@$.A-Za-z0-9_])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "begin",
        "beginfile",
        "break",
        "close",
        "continue",
        "delete",
        "do",
        "else",
        "end",
        "endfile",
        "exit",
        "for",
        "function",
        "getline",
        "if",
        "in",
        "next",
        "nextfile",
        "or",
        "print",
        "printf",
        "return",
        "switch",
        "while",
    }
)
_BUILTIN_FUNCTION_NAMES = frozenset(
    {
        "asort",
        "asorti",
        "atan2",
        "bindtextdomain",
        "compl",
        "cos",
        "dcgettext",
        "dcngettext",
        "exp",
        "gensub",
        "gsub",
        "index",
        "int",
        "isarray",
        "length",
        "log",
        "lshift",
        "match",
        "mktime",
        "or",
        "patsplit",
        "rand",
        "rshift",
        "sin",
        "split",
        "sprintf",
        "sqrt",
        "srand",
        "strftime",
        "strtonum",
        "sub",
        "substr",
        "systime",
        "tolower",
        "toupper",
        "xor",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _strip_inline_comment(raw_line: str) -> str:
    chars: list[str] = []
    in_string = False
    escaped = False
    for character in raw_line:
        if in_string:
            chars.append(character)
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == '"':
                in_string = False
            continue
        if character == '"':
            chars.append(character)
            in_string = True
            continue
        if character == "#":
            break
        chars.append(character)
    return "".join(chars)


def strip_comments(text: str) -> str:
    return "\n".join(_strip_inline_comment(line) for line in text.splitlines())


def has_awk_shebang(text: str) -> bool:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    return bool(_SHEBANG_AWK_RE.search(first_line))


def has_awk_source_markers(text: str) -> bool:
    return bool(_RAW_SOURCE_MARKER_RE.search(text))


def is_probable_awk_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix in _KNOWN_SUFFIXES:
        return True
    if has_awk_shebang(text):
        return True
    if not has_awk_source_markers(text):
        return False
    stripped_text = strip_comments(text)
    return bool(
        _FUNCTION_DECL_RE.search(stripped_text)
        or _BLOCK_DECL_RE.search(stripped_text)
        or _INCLUDE_RE.search(stripped_text)
    )


def module_symbol_name(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.suffix:
        return path.stem or path.name
    return path.name


def _normalize_import_target(raw_target: str) -> str:
    normalized_target = str(raw_target or "").strip()
    if not normalized_target:
        return ""
    if normalized_target[0] in {'"', "'", "<"} and normalized_target[-1] in {'"', "'", ">"}:
        normalized_target = normalized_target[1:-1].strip()
    return normalized_target.replace("\\", "/")


def import_targets_for_text(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    for match in _INCLUDE_RE.finditer(text):
        normalized_target = _normalize_import_target(str(match.group("target") or ""))
        if not normalized_target or normalized_target in seen_targets:
            continue
        seen_targets.add(normalized_target)
        targets.append(normalized_target)
    return tuple(targets)


def _find_symbol_end_line(text: str, open_brace_index: int) -> int:
    if open_brace_index < 0 or open_brace_index >= len(text):
        return _line_count(text)
    depth = 0
    in_string = False
    escaped = False
    for index in range(open_brace_index, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character == "{":
            depth += 1
            continue
        if character == "}":
            depth -= 1
            if depth == 0:
                return _line_number(text, index)
    return _line_count(text)


def _iter_function_entries(text: str) -> Iterable[tuple[str, int, int]]:
    for match in _FUNCTION_DECL_RE.finditer(text):
        function_name = str(match.group("name") or "").strip()
        if not function_name:
            continue
        start_line = _line_number(text, match.start())
        open_brace_index = text.find("{", match.end())
        end_line = (
            _find_symbol_end_line(text, open_brace_index)
            if open_brace_index != -1
            else start_line
        )
        yield function_name, start_line, end_line


def _iter_block_entries(text: str) -> Iterable[tuple[str, int, int]]:
    for match in _BLOCK_DECL_RE.finditer(text):
        block_name = str(match.group("name") or "").strip().upper()
        if not block_name:
            continue
        start_line = _line_number(text, match.start())
        open_brace_index = text.find("{", match.start(), match.end())
        if open_brace_index == -1:
            open_brace_index = match.end() - 1
        end_line = _find_symbol_end_line(text, open_brace_index)
        yield block_name, start_line, end_line


def is_operational_reference_name(name: str) -> bool:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        return False
    lowered_name = normalized_name.lower()
    return (
        lowered_name not in _RESERVED_SYMBOL_NAMES
        and lowered_name not in _BUILTIN_FUNCTION_NAMES
    )
