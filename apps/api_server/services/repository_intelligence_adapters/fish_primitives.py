from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".fish"})
_FISH_RUNTIME_DIRECTORIES = frozenset({"functions", "conf.d", "completions", "themes"})
_SHEBANG_RE = re.compile(r"^#!.*\bfish(?:\s|$)")
_FUNCTION_RE = re.compile(
    r"(?im)^\s*function\s+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b"
)
_ALIAS_RE = re.compile(
    r"(?im)^\s*alias\s+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b"
)
_SOURCE_RE = re.compile(
    r"(?im)^\s*source\s+(?P<target>(?:\"[^\"]+\"|'[^']+'|[^\s#;|]+))"
)
_COMMAND_SUBSTITUTION_RE = re.compile(
    r"\(\s*(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b"
)
_COMMAND_NAME_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b")
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:function|alias|abbr|source|set|complete|status|switch|for|if)\b"
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "begin",
        "break",
        "builtin",
        "case",
        "command",
        "continue",
        "else",
        "end",
        "eval",
        "for",
        "function",
        "if",
        "in",
        "not",
        "or",
        "return",
        "set",
        "source",
        "status",
        "switch",
        "test",
        "while",
    }
)
_BUILTIN_COMMAND_NAMES = frozenset(
    {
        "abbr",
        "alias",
        "argparse",
        "bg",
        "bind",
        "builtin",
        "cd",
        "command",
        "complete",
        "contains",
        "count",
        "disown",
        "echo",
        "emit",
        "eval",
        "exec",
        "exit",
        "fg",
        "functions",
        "history",
        "jobs",
        "math",
        "printf",
        "pwd",
        "read",
        "return",
        "set",
        "set_color",
        "source",
        "status",
        "string",
        "test",
        "type",
        "wait",
    }
)


def strip_comments(text: str) -> str:
    characters: list[str] = []
    in_single = False
    in_double = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_single:
            characters.append(character)
            if character == "'" and (index == 0 or text[index - 1] != "\\"):
                in_single = False
            index += 1
            continue
        if in_double:
            characters.append(character)
            if character == '"' and (index == 0 or text[index - 1] != "\\"):
                in_double = False
            index += 1
            continue
        if character == "#":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character == "'":
            in_single = True
        elif character == '"':
            in_double = True
        index += 1
    return "".join(characters)


def has_fish_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_fish_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if has_fish_path_hints(path):
        stripped_text = strip_comments(text)
        return bool(stripped_text.strip()) or bool(_SHEBANG_RE.match(text))
    if _SHEBANG_RE.match(text):
        return True
    lowered_parts = {part.lower() for part in PurePosixPath(path).parts[:-1]}
    if not lowered_parts.intersection(_FISH_RUNTIME_DIRECTORIES):
        return False
    stripped_text = strip_comments(text)
    return bool(_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0] in {"functions", "conf.d", "completions", "themes"}:
        parts = parts[1:]
    return "/".join(part for part in parts if part)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


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


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for regex, symbol_kind in ((_FUNCTION_RE, "function"), (_ALIAS_RE, "alias")):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if (
                not symbol_name
                or symbol_name in _RESERVED_SYMBOL_NAMES
                or symbol_name in _BUILTIN_COMMAND_NAMES
            ):
                continue
            line_number = _line_number(stripped_text, match.start())
            item = (symbol_name, symbol_kind, line_number)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_source_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _SOURCE_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip().strip("\"'")
        if not target:
            continue
        item = (target, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            statements.append(item)
    return tuple(statements)


def is_operational_reference_name(name: str) -> bool:
    normalized_name = name.strip()
    if not normalized_name:
        return False
    lower_name = normalized_name.lower()
    return (
        lower_name not in _RESERVED_SYMBOL_NAMES
        and lower_name not in _BUILTIN_COMMAND_NAMES
    )


def iter_reference_names(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _COMMAND_SUBSTITUTION_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not is_operational_reference_name(name):
            continue
        item = (name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            references.append(item)
    for raw_line in stripped_text.splitlines():
        line = raw_line.strip()
        if not line or _FUNCTION_RE.match(line) or _SOURCE_RE.match(line):
            continue
        for segment in re.split(r"\s*(?:;|\||&&)\s*", line):
            command_segment = segment.strip()
            if not command_segment:
                continue
            while True:
                stripped_segment = command_segment.lstrip()
                prefix_removed = False
                for prefix in ("and", "begin", "builtin", "command", "not", "or"):
                    if stripped_segment.startswith(f"{prefix} "):
                        command_segment = stripped_segment[len(prefix) :].lstrip()
                        prefix_removed = True
                        break
                if not prefix_removed:
                    break
            command_match = _COMMAND_NAME_RE.match(command_segment)
            if command_match is None:
                continue
            name = str(command_match.group("name") or "").strip()
            if not is_operational_reference_name(name):
                continue
            line_number = stripped_text.count("\n", 0, text.find(raw_line)) + 1
            item = (name, line_number)
            if item not in seen:
                seen.add(item)
                references.append(item)
    return tuple(references)
