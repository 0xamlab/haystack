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

_KNOWN_SUFFIXES = frozenset({".applescript", ".scpt"})
_APPLESCRIPT_MARKER_RE = re.compile(
    r"(?im)^\s*(?:on|to)\s+[A-Za-z_][A-Za-z0-9_]*\b|"
    r"^\s*script\s+[A-Za-z_][A-Za-z0-9_]*\b|"
    r"\b(?:tell\s+(?:application|script)|load\s+script|run\s+script|"
    r"do\s+shell\s+script|use\s+scripting\s+additions|display\s+dialog)\b"
)
_HANDLER_DECL_RE = re.compile(
    r"^\s*(?P<kind>on|to)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
_SCRIPT_DECL_RE = re.compile(
    r"^\s*script\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
_SET_LOAD_BINDING_RE = re.compile(
    r"^\s*set\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s+to\s+load\s+script\b(?P<target>[^\n]+)",
    re.MULTILINE | re.IGNORECASE,
)
_PROPERTY_LOAD_BINDING_RE = re.compile(
    r"^\s*property\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*load\s+script\b(?P<target>[^\n]+)",
    re.MULTILINE | re.IGNORECASE,
)
_LOAD_SCRIPT_LINE_RE = re.compile(
    r"\bload\s+script\b(?P<target>[^\n]+)",
    re.IGNORECASE,
)
_QUOTED_SEGMENT_RE = re.compile(r"""["'](?P<value>[^"']+)["']""")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "alias",
        "application",
        "considering",
        "copy",
        "do",
        "else",
        "end",
        "false",
        "file",
        "global",
        "ignoring",
        "if",
        "load",
        "local",
        "me",
        "missing",
        "my",
        "of",
        "on",
        "path",
        "posix",
        "property",
        "repeat",
        "return",
        "script",
        "set",
        "tell",
        "then",
        "to",
        "true",
        "use",
        "with",
        "without",
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


def strip_comments(text: str) -> str:
    characters: list[str] = []
    index = 0
    in_string = False
    escaped = False
    block_depth = 0
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if block_depth > 0:
            if character == "(" and next_character == "*":
                block_depth += 1
                index += 2
                continue
            if character == "*" and next_character == ")":
                block_depth -= 1
                index += 2
                continue
            if character == "\n":
                characters.append("\n")
            index += 1
            continue
        if in_string:
            characters.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            characters.append(character)
            in_string = True
            index += 1
            continue
        if character == "(" and next_character == "*":
            block_depth = 1
            index += 2
            continue
        if character == "-" and next_character == "-":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        characters.append(character)
        index += 1
    return "".join(characters)


def has_applescript_path_hints(path: Path) -> bool:
    return path.suffix.lower() in _KNOWN_SUFFIXES


def _looks_binaryish(text: str) -> bool:
    if not text:
        return False
    sample = text[:2048]
    control_characters = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_characters > max(2, len(sample) // 32)


def is_probable_applescript_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if suffix == ".applescript":
        return True
    return bool(_APPLESCRIPT_MARKER_RE.search(stripped_text))


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


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def _normalize_import_target(raw_target: str) -> str:
    normalized_target = str(raw_target or "").strip()
    if not normalized_target:
        return ""
    quoted_matches = [
        match.group("value") or "" for match in _QUOTED_SEGMENT_RE.finditer(normalized_target)
    ]
    if quoted_matches:
        normalized_target = quoted_matches[-1]
    else:
        lowered_target = normalized_target.lower()
        for prefix in ("posix file", "alias", "file"):
            if lowered_target.startswith(prefix):
                normalized_target = normalized_target[len(prefix) :].strip()
                lowered_target = normalized_target.lower()
    normalized_target = normalize_identifier(normalized_target)
    if ":" in normalized_target and "/" not in normalized_target:
        normalized_target = normalized_target.lstrip(":").replace(":", "/")
    return _normalize_repository_relative_path(normalized_target)


def import_targets_for_text(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    targets: list[str] = []
    seen_targets: set[str] = set()
    for match in _LOAD_SCRIPT_LINE_RE.finditer(stripped_text):
        normalized_target = _normalize_import_target(str(match.group("target") or ""))
        if not normalized_target or normalized_target in seen_targets:
            continue
        seen_targets.add(normalized_target)
        targets.append(normalized_target)
    return tuple(targets)


def _module_symbol_name(file_path: str) -> str:
    path = PurePosixPath(file_path)
    return path.stem or path.name


def _iter_declared_symbols(text: str) -> Iterable[tuple[str, str, int]]:
    stripped_text = strip_comments(text)
    matches: list[tuple[int, str, str]] = []
    for match in _SCRIPT_DECL_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(match.group("name") or "")
        if not symbol_name or symbol_name.lower() in _RESERVED_SYMBOL_NAMES:
            continue
        matches.append((match.start(), "script", symbol_name))
    for match in _HANDLER_DECL_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(match.group("name") or "")
        if not symbol_name or symbol_name.lower() in _RESERVED_SYMBOL_NAMES:
            continue
        matches.append((match.start(), "function", symbol_name))
    for start_offset, kind, symbol_name in sorted(matches):
        yield kind, symbol_name, start_offset


def collect_symbol_entries(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = strip_comments(text)
    final_line = _line_count(stripped_text)
    module_name = _module_symbol_name(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "name": module_name,
                "kind": "module",
                "line": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=final_line,
        parent_symbol_id=None,
        signature=None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=final_line,
        )
    ]
    entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int, str]] = set()
    for kind, symbol_name, start_offset in _iter_declared_symbols(stripped_text):
        start_line = _line_number(stripped_text, start_offset)
        symbol_key = (symbol_name.lower(), start_line, kind)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        entries.append(
            {
                "kind": kind,
                "name": symbol_name,
                "start_line": start_line,
            }
        )
    for index, entry in enumerate(entries):
        next_start_line = (
            entries[index + 1]["start_line"] if index + 1 < len(entries) else final_line + 1
        )
        end_line = max(entry["start_line"], next_start_line - 1)
        symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "name": entry["name"],
                    "kind": entry["kind"],
                    "line": entry["start_line"],
                },
            ),
            symbol_name=entry["name"],
            symbol_kind=entry["kind"],
            start_line=entry["start_line"],
            end_line=end_line,
            parent_symbol_id=module_symbol.symbol_id,
            signature=entry["name"],
        )
        collected_symbols.append(
            _CollectedSymbol(
                symbol=symbol,
                local_start_line=entry["start_line"],
                local_end_line=end_line,
            )
        )
    return tuple(
        sorted(
            collected_symbols,
            key=lambda item: (
                item.local_start_line,
                item.local_end_line,
                0 if item.symbol.symbol_kind == "module" else 1,
                item.symbol.symbol_name.lower(),
            ),
        )
    )
