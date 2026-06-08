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

_KNOWN_SUFFIXES = frozenset({".bzl", ".star"})
_KNOWN_BASENAMES = frozenset(
    {
        "BUILD",
        "BUILD.bazel",
        "MODULE.bazel",
        "WORKSPACE",
        "WORKSPACE.bazel",
    }
)
_LOAD_RE = re.compile(
    r"^\s*load\(\s*(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)(?P<body>.*?)\)",
    re.MULTILINE | re.DOTALL,
)
_LOAD_ALIAS_RE = re.compile(
    r"(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*['\"](?P<name>[A-Za-z_][A-Za-z0-9_]*)['\"]"
)
_LOAD_SYMBOL_RE = re.compile(r"['\"](?P<name>[A-Za-z_][A-Za-z0-9_]*)['\"]")
_DEF_RE = re.compile(r"^def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE)
_ASSIGNMENT_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=", re.MULTILINE)
_CALL_RE = re.compile(r"(?<![.'])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?=\s*\()")
_TOP_LEVEL_CALL_RE = re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*\(", re.MULTILINE)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "break",
        "continue",
        "def",
        "elif",
        "else",
        "for",
        "if",
        "in",
        "lambda",
        "load",
        "native",
        "not",
        "or",
        "pass",
        "return",
    }
)
_BUILTIN_REFERENCE_NAMES = frozenset(
    {
        "alias",
        "allow_empty",
        "attr",
        "attrs",
        "depset",
        "dict",
        "exports_files",
        "fail",
        "glob",
        "json",
        "len",
        "list",
        "package",
        "print",
        "provider",
        "repository_rule",
        "rule",
        "select",
        "sorted",
        "str",
        "struct",
        "tuple",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def strip_comments(text: str) -> str:
    stripped_lines: list[str] = []
    for raw_line in text.splitlines():
        quote: str | None = None
        escaped = False
        output_chars: list[str] = []
        for character in raw_line:
            if quote is None:
                if character == "#":
                    break
                if character in {"'", '"'}:
                    quote = character
                output_chars.append(character)
                continue
            output_chars.append(character)
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == quote:
                quote = None
        stripped_lines.append("".join(output_chars).rstrip())
    return "\n".join(stripped_lines)


def has_starlark_path_hints(path: Path | PurePosixPath) -> bool:
    posix_path = PurePosixPath(path)
    return (
        posix_path.suffix.lower() in _KNOWN_SUFFIXES
        or posix_path.name in _KNOWN_BASENAMES
    )


def is_probable_starlark_source(*, path: Path | PurePosixPath, text: str) -> bool:
    posix_path = PurePosixPath(path)
    if not has_starlark_path_hints(posix_path):
        return False
    stripped_text = strip_comments(text)
    return bool(
        _LOAD_RE.search(stripped_text)
        or _DEF_RE.search(stripped_text)
        or _ASSIGNMENT_RE.search(stripped_text)
        or _TOP_LEVEL_CALL_RE.search(stripped_text)
    )


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    basename = path.name
    parent = path.parent
    if basename in {"BUILD", "BUILD.bazel"}:
        return f"//{parent}" if str(parent) not in {"", "."} else "//"
    if basename in {"WORKSPACE", "WORKSPACE.bazel"}:
        return "WORKSPACE"
    if basename == "MODULE.bazel":
        return "MODULE"
    if path.suffix:
        return str(path.with_suffix("")).replace("/", ".")
    return basename


def target_label_for_path(path: PurePosixPath) -> str:
    parent = path.parent
    package = f"//{parent}" if str(parent) not in {"", "."} else "//"
    return f"{package}:{path.name}"


def iter_load_statements(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            str(match.group("target") or "").strip(),
            str(match.group("body") or ""),
            _line_number(stripped_text, match.start()),
        )
        for match in _LOAD_RE.finditer(stripped_text)
        if str(match.group("target") or "").strip()
    )


def parse_loaded_symbols(raw_body: str) -> tuple[tuple[str, str], ...]:
    body = str(raw_body or "")
    parsed: list[tuple[str, str]] = []
    seen_aliases: set[str] = set()
    for match in _LOAD_ALIAS_RE.finditer(body):
        alias = str(match.group("alias") or "").strip()
        target_name = str(match.group("name") or "").strip()
        if not alias or not target_name or alias in seen_aliases:
            continue
        seen_aliases.add(alias)
        parsed.append((alias, target_name))
    body_without_aliases = _LOAD_ALIAS_RE.sub("", body)
    for match in _LOAD_SYMBOL_RE.finditer(body_without_aliases):
        name = str(match.group("name") or "").strip()
        if not name or name in seen_aliases:
            continue
        seen_aliases.add(name)
        parsed.append((name, name))
    return tuple(parsed)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in ((_DEF_RE, "function"), (_ASSIGNMENT_RE, "value")):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if (
                not symbol_name
                or symbol_name in seen_names
                or symbol_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))
