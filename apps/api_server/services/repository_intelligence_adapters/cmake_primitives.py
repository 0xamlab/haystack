from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".cmake"})
_CMAKE_CONFIG_BASENAMES = frozenset({"cmakelists.txt"})
_SIGNAL_COMMANDS = frozenset(
    {
        "add_custom_target",
        "add_dependencies",
        "add_executable",
        "add_library",
        "add_subdirectory",
        "find_package",
        "function",
        "include",
        "macro",
        "project",
        "target_link_libraries",
    }
)
_SYMBOL_COMMAND_KINDS = {
    "project": "project",
    "add_library": "target",
    "add_executable": "target",
    "add_custom_target": "target",
    "function": "function",
    "macro": "macro",
}
_REFERENCE_COMMANDS = frozenset({"target_link_libraries", "add_dependencies"})
_REFERENCE_QUALIFIERS = frozenset(
    {
        "PRIVATE",
        "PUBLIC",
        "INTERFACE",
        "LINK_PRIVATE",
        "LINK_PUBLIC",
        "optimized",
        "debug",
        "general",
    }
)
_TARGET_NAME_RE = re.compile(r"^[A-Za-z0-9_:+.\-]+$")


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        in_quote = False
        escaped = False
        result: list[str] = []
        for char in raw_line:
            if char == '"' and not escaped:
                in_quote = not in_quote
            if char == "#" and not in_quote:
                break
            result.append(char)
            escaped = char == "\\" and not escaped
        lines.append("".join(result))
    return "\n".join(lines)


def has_cmake_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in _KNOWN_SUFFIXES
        or normalized_path.name.lower() in _CMAKE_CONFIG_BASENAMES
    )


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _normalize_token(raw_token: str) -> str:
    return str(raw_token or "").strip().strip('"').strip("'")


def _tokenize_arguments(raw_arguments: str) -> tuple[str, ...]:
    tokens: list[str] = []
    buffer: list[str] = []
    in_quote = False
    escaped = False
    for char in raw_arguments:
        if char == '"' and not escaped:
            in_quote = not in_quote
            continue
        if not in_quote and (char.isspace() or char == ";"):
            token = _normalize_token("".join(buffer))
            if token:
                tokens.append(token)
            buffer = []
            escaped = False
            continue
        buffer.append(char)
        escaped = char == "\\" and not escaped
    token = _normalize_token("".join(buffer))
    if token:
        tokens.append(token)
    return tuple(tokens)


def iter_command_entries(text: str) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    commands: list[tuple[str, tuple[str, ...], int]] = []
    length = len(stripped_text)
    index = 0
    while index < length:
        char = stripped_text[index]
        if not (char.isalpha() or char == "_"):
            index += 1
            continue
        start = index
        index += 1
        while index < length and (stripped_text[index].isalnum() or stripped_text[index] == "_"):
            index += 1
        command_name = stripped_text[start:index].lower()
        probe_index = index
        while probe_index < length and stripped_text[probe_index].isspace():
            probe_index += 1
        if probe_index >= length or stripped_text[probe_index] != "(":
            index = probe_index
            continue
        depth = 1
        probe_index += 1
        argument_start = probe_index
        in_quote = False
        escaped = False
        while probe_index < length and depth > 0:
            current = stripped_text[probe_index]
            if current == '"' and not escaped:
                in_quote = not in_quote
            elif not in_quote:
                if current == "(":
                    depth += 1
                elif current == ")":
                    depth -= 1
            escaped = current == "\\" and not escaped
            probe_index += 1
        if depth != 0:
            break
        raw_arguments = stripped_text[argument_start : probe_index - 1]
        commands.append(
            (
                command_name,
                _tokenize_arguments(raw_arguments),
                _line_number(stripped_text, start),
            )
        )
        index = probe_index
    return tuple(commands)


def is_probable_cmake_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_cmake_path_hints(normalized_path):
        return False
    return any(command_name in _SIGNAL_COMMANDS for command_name, _args, _line in iter_command_entries(text))


def _is_target_name(token: str) -> bool:
    normalized = _normalize_token(token)
    return bool(normalized) and "$" not in normalized and _TARGET_NAME_RE.match(normalized) is not None


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for command_name, arguments, line_number in iter_command_entries(text):
        symbol_kind = _SYMBOL_COMMAND_KINDS.get(command_name)
        if symbol_kind is None or not arguments:
            continue
        symbol_name = _normalize_token(arguments[0])
        if not _is_target_name(symbol_name):
            continue
        item = (symbol_name, symbol_kind, line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_include_targets(text: str) -> tuple[tuple[str, int], ...]:
    includes: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for command_name, arguments, line_number in iter_command_entries(text):
        if command_name != "include" or not arguments:
            continue
        target = _normalize_token(arguments[0])
        if not target or "$" in target:
            continue
        item = (target, line_number)
        if item not in seen:
            seen.add(item)
            includes.append(item)
    return tuple(includes)


def iter_subdirectory_targets(text: str) -> tuple[tuple[str, int], ...]:
    subdirectories: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for command_name, arguments, line_number in iter_command_entries(text):
        if command_name != "add_subdirectory" or not arguments:
            continue
        target = _normalize_token(arguments[0])
        if not target or target.startswith("$"):
            continue
        item = (target, line_number)
        if item not in seen:
            seen.add(item)
            subdirectories.append(item)
    return tuple(subdirectories)


def iter_package_targets(text: str) -> tuple[tuple[str, int], ...]:
    packages: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for command_name, arguments, line_number in iter_command_entries(text):
        if command_name != "find_package" or not arguments:
            continue
        package_name = _normalize_token(arguments[0])
        if not _is_target_name(package_name):
            continue
        item = (package_name, line_number)
        if item not in seen:
            seen.add(item)
            packages.append(item)
    return tuple(packages)


def iter_reference_names(text: str) -> tuple[tuple[str, str, int], ...]:
    references: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for command_name, arguments, line_number in iter_command_entries(text):
        if command_name not in _REFERENCE_COMMANDS or len(arguments) < 2:
            continue
        source_target = _normalize_token(arguments[0])
        if not _is_target_name(source_target):
            continue
        for raw_target in arguments[1:]:
            target_name = _normalize_token(raw_target)
            if (
                not _is_target_name(target_name)
                or target_name.upper() in _REFERENCE_QUALIFIERS
                or target_name == source_target
            ):
                continue
            item = (source_target, target_name, line_number)
            if item not in seen:
                seen.add(item)
                references.append(item)
    return tuple(references)

