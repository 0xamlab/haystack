from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset[str]()
MESON_CONFIG_BASENAMES = frozenset({"meson.build"})
_SIGNAL_CALLS = frozenset(
    {
        "both_libraries",
        "custom_target",
        "dependency",
        "executable",
        "import",
        "library",
        "project",
        "run_target",
        "shared_library",
        "shared_module",
        "static_library",
        "subdir",
    }
)
_SYMBOL_CALL_KINDS = {
    "project": "project",
    "library": "target",
    "static_library": "target",
    "shared_library": "target",
    "shared_module": "target",
    "both_libraries": "target",
    "executable": "target",
    "custom_target": "target",
    "run_target": "target",
}
_TARGET_CALLS = frozenset(
    call_name for call_name, symbol_kind in _SYMBOL_CALL_KINDS.items() if symbol_kind == "target"
)
_REFERENCE_KEYWORDS = frozenset({"dependencies", "link_with"})
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_:+.\-]*$")
_REFERENCE_TOKEN_RE = re.compile(r"""(?P<quoted>['"](?P<qval>[^'"]+)['"])|(?P<ident>[A-Za-z_][A-Za-z0-9_:+.\-]*)""")
_IGNORED_REFERENCE_TOKENS = frozenset(
    {
        "declare_dependency",
        "dependencies",
        "dependency",
        "disabler",
        "false",
        "files",
        "import",
        "include_directories",
        "link_with",
        "true",
    }
)
_SOURCE_SUFFIXES = (
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".m",
    ".mm",
    ".rs",
    ".s",
    ".S",
)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        in_quote: str | None = None
        escaped = False
        result: list[str] = []
        for char in raw_line:
            if char in {'"', "'"} and not escaped:
                in_quote = None if in_quote == char else char
            if char == "#" and in_quote is None:
                break
            result.append(char)
            escaped = char == "\\" and not escaped
        lines.append("".join(result))
    return "\n".join(lines)


def has_meson_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).name.lower() in MESON_CONFIG_BASENAMES


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _split_top_level_arguments(raw_arguments: str) -> tuple[str, ...]:
    arguments: list[str] = []
    buffer: list[str] = []
    quote_char: str | None = None
    escaped = False
    depth = 0
    for char in raw_arguments:
        if quote_char is not None:
            buffer.append(char)
            if char == quote_char and not escaped:
                quote_char = None
            escaped = char == "\\" and not escaped
            continue
        if char in {'"', "'"}:
            quote_char = char
            buffer.append(char)
            escaped = False
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}" and depth > 0:
            depth -= 1
        if char == "," and depth == 0:
            argument = "".join(buffer).strip()
            if argument:
                arguments.append(argument)
            buffer = []
            escaped = False
            continue
        buffer.append(char)
        escaped = char == "\\" and not escaped
    argument = "".join(buffer).strip()
    if argument:
        arguments.append(argument)
    return tuple(arguments)


def _split_keyword_argument(argument: str) -> tuple[str | None, str]:
    quote_char: str | None = None
    escaped = False
    depth = 0
    for index, char in enumerate(argument):
        if quote_char is not None:
            if char == quote_char and not escaped:
                quote_char = None
            escaped = char == "\\" and not escaped
            continue
        if char in {'"', "'"}:
            quote_char = char
            escaped = False
            continue
        if char in "([{":
            depth += 1
            continue
        if char in ")]}" and depth > 0:
            depth -= 1
            continue
        if char == ":" and depth == 0:
            keyword = argument[:index].strip().lower()
            if _IDENTIFIER_RE.match(keyword):
                return keyword, argument[index + 1 :].strip()
            break
    return None, argument.strip()


def iter_call_entries(text: str) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, tuple[str, ...], int]] = []
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
        call_name = stripped_text[start:index].lower()
        probe_index = index
        while probe_index < length and stripped_text[probe_index].isspace():
            probe_index += 1
        if probe_index >= length or stripped_text[probe_index] != "(":
            index = probe_index
            continue
        depth = 1
        probe_index += 1
        argument_start = probe_index
        quote_char: str | None = None
        escaped = False
        while probe_index < length and depth > 0:
            current = stripped_text[probe_index]
            if quote_char is not None:
                if current == quote_char and not escaped:
                    quote_char = None
                escaped = current == "\\" and not escaped
                probe_index += 1
                continue
            if current in {'"', "'"}:
                quote_char = current
            elif current in "([{":
                depth += 1
            elif current in ")]}":
                depth -= 1
            escaped = current == "\\" and not escaped
            probe_index += 1
        if depth != 0:
            break
        entries.append(
            (
                call_name,
                _split_top_level_arguments(stripped_text[argument_start : probe_index - 1]),
                _line_number(stripped_text, start),
            )
        )
        index = probe_index
    return tuple(entries)


def is_probable_meson_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_meson_path_hints(path):
        return False
    return any(call_name in _SIGNAL_CALLS for call_name, _arguments, _line_number in iter_call_entries(text))


def _normalize_name(raw_value: str) -> str:
    candidate = str(raw_value or "").strip()
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {'"', "'"}:
        candidate = candidate[1:-1].strip()
    return candidate


def _is_symbol_name(candidate: str) -> bool:
    normalized = _normalize_name(candidate)
    return (
        bool(normalized)
        and "/" not in normalized
        and "\\" not in normalized
        and normalized.lower() not in _IGNORED_REFERENCE_TOKENS
        and _IDENTIFIER_RE.match(normalized) is not None
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for call_name, arguments, line_number in iter_call_entries(text):
        symbol_kind = _SYMBOL_CALL_KINDS.get(call_name)
        if symbol_kind is None or not arguments:
            continue
        symbol_name = _normalize_name(arguments[0])
        if not _is_symbol_name(symbol_name):
            continue
        item = (symbol_name, symbol_kind, line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def _iter_string_argument_targets(text: str, call_name: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    pattern = re.compile(rf"""\b{re.escape(call_name)}\s*\(\s*(['"])([^'"]+)\1""")
    targets: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in pattern.finditer(stripped_text):
        target_name = match.group(2).strip()
        if not target_name:
            continue
        item = (target_name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            targets.append(item)
    return tuple(targets)


def iter_subdir_targets(text: str) -> tuple[tuple[str, int], ...]:
    return _iter_string_argument_targets(text, "subdir")


def iter_import_targets(text: str) -> tuple[tuple[str, int], ...]:
    return _iter_string_argument_targets(text, "import")


def iter_dependency_targets(text: str) -> tuple[tuple[str, int], ...]:
    return _iter_string_argument_targets(text, "dependency")


def _iter_reference_tokens(raw_value: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for match in _REFERENCE_TOKEN_RE.finditer(raw_value):
        token = match.group("qval") if match.group("quoted") is not None else match.group("ident")
        if not token:
            continue
        if "/" in token or "\\" in token or token.endswith(_SOURCE_SUFFIXES):
            continue
        if token.lower() in _IGNORED_REFERENCE_TOKENS:
            continue
        if match.group("ident") is not None:
            suffix = raw_value[match.end() :].lstrip()
            if suffix.startswith("("):
                continue
        normalized = _normalize_name(token)
        if not _is_symbol_name(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def iter_reference_names(text: str) -> tuple[tuple[str, str, int], ...]:
    references: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for call_name, arguments, line_number in iter_call_entries(text):
        if call_name not in _TARGET_CALLS or not arguments:
            continue
        source_target = _normalize_name(arguments[0])
        if not _is_symbol_name(source_target):
            continue
        for argument in arguments[1:]:
            keyword, value = _split_keyword_argument(argument)
            if keyword not in _REFERENCE_KEYWORDS or not value:
                continue
            for target_name in _iter_reference_tokens(value):
                item = (source_target, target_name, line_number)
                if item not in seen:
                    seen.add(item)
                    references.append(item)
    return tuple(references)
