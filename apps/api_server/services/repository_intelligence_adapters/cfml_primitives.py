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

_KNOWN_SUFFIXES = frozenset({".cfc", ".cfm", ".cfml"})
_CFML_KEYWORD_RE = re.compile(
    r"<cf(?:component|function|include|set|script)\b"
    r"|\bcomponent\b"
    r"|\bfunction\b"
    r"|\binclude\b"
    r"|\bcreateObject\s*\(",
    re.IGNORECASE,
)
_TAG_COMMENT_RE = re.compile(r"<!---(?P<body>.*?)--->", re.IGNORECASE | re.DOTALL)
_BLOCK_COMMENT_RE = re.compile(r"/\*(?P<body>.*?)\*/", re.DOTALL)
_ATTRIBUTE_RE = re.compile(
    r"(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_TAG_COMPONENT_RE = re.compile(r"<cfcomponent\b(?P<attrs>[^>]*)>", re.IGNORECASE)
_SCRIPT_COMPONENT_RE = re.compile(
    r"^\s*component\b(?P<attrs>[^{\n]*)\{",
    re.IGNORECASE | re.MULTILINE,
)
_TAG_FUNCTION_BLOCK_RE = re.compile(
    r"<cffunction\b(?P<attrs>[^>]*)>(?P<body>.*?)</cffunction>",
    re.IGNORECASE | re.DOTALL,
)
# NOTE: keyword alternatives require trailing '\s+' so the modifier list cannot
# share a prefix with a catch-all '\w+'-style branch (those overlapping parse
# paths are what triggered py/redos). A single trailing token before 'function'
# captures the optional return type without a quantified outer group.
_SCRIPT_FUNCTION_RE = re.compile(
    r"^\s*(?:(?:public|private|remote|package|static|final|abstract)\s+)*"
    r"(?:[A-Za-z_]\w{0,64}\s+)?function\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\(",
    re.IGNORECASE | re.MULTILINE,
)
_TAG_INCLUDE_RE = re.compile(r"<cfinclude\b(?P<attrs>[^>]*)>", re.IGNORECASE)
_SCRIPT_INCLUDE_RE = re.compile(
    r"\binclude\b\s*(?:template\s*=\s*)?(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)",
    re.IGNORECASE,
)
_CREATE_OBJECT_LITERAL_RE = re.compile(
    r"createObject\s*\(\s*(?P<kind_quote>['\"])component(?P=kind_quote)\s*,\s*"
    r"(?P<target_quote>['\"])(?P<target>[^'\"]+)(?P=target_quote)\s*\)"
    r"(?:\s*\.\s*(?P<method>[A-Za-z_][A-Za-z0-9_]*)\s*\()?",
    re.IGNORECASE,
)
_NEW_EXPRESSION_RE = re.compile(
    r"\bnew\s+(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\s*\([^)]*\)"
    r"(?:\s*\.\s*(?P<method>[A-Za-z_][A-Za-z0-9_]*)\s*\()?",
    re.IGNORECASE,
)
_CREATE_OBJECT_BINDING_RE = re.compile(
    r"(?P<alias>[A-Za-z_][A-Za-z0-9_.]*)\s*=\s*"
    r"createObject\s*\(\s*(?P<kind_quote>['\"])component(?P=kind_quote)\s*,\s*"
    r"(?P<target_quote>['\"])(?P<target>[^'\"]+)(?P=target_quote)\s*\)",
    re.IGNORECASE,
)
_NEW_BINDING_RE = re.compile(
    r"(?P<alias>[A-Za-z_][A-Za-z0-9_.]*)\s*=\s*new\s+"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_.]*)\s*\(",
    re.IGNORECASE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_.]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_UNQUALIFIED_CALL_RE = re.compile(
    r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE,
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "break",
        "case",
        "catch",
        "component",
        "createobject",
        "do",
        "else",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "import",
        "include",
        "new",
        "not",
        "null",
        "or",
        "package",
        "private",
        "public",
        "remote",
        "return",
        "static",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "var",
        "while",
    }
)
_BUILTIN_QUALIFIED_ROOTS = frozenset(
    {
        "application",
        "arguments",
        "attributes",
        "cgi",
        "client",
        "cookie",
        "form",
        "local",
        "request",
        "server",
        "session",
        "super",
        "this",
        "url",
        "variables",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int


def _preserve_multiline_replacement(match: re.Match[str]) -> str:
    return "\n" * str(match.group(0)).count("\n")


def _strip_inline_script_comment(raw_line: str) -> str:
    chars: list[str] = []
    index = 0
    in_single = False
    in_double = False
    while index < len(raw_line):
        character = raw_line[index]
        if character == "'" and not in_double:
            in_single = not in_single
            chars.append(character)
            index += 1
            continue
        if character == '"' and not in_single:
            in_double = not in_double
            chars.append(character)
            index += 1
            continue
        if (
            character == "/"
            and not in_single
            and not in_double
            and index + 1 < len(raw_line)
            and raw_line[index + 1] == "/"
        ):
            break
        chars.append(character)
        index += 1
    return "".join(chars)


def strip_comments(text: str) -> str:
    without_tag_comments = _TAG_COMMENT_RE.sub(_preserve_multiline_replacement, text)
    without_block_comments = _BLOCK_COMMENT_RE.sub(
        _preserve_multiline_replacement,
        without_tag_comments,
    )
    return "\n".join(
        _strip_inline_script_comment(line)
        for line in without_block_comments.splitlines()
    )


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _parse_attrs(attrs_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in _ATTRIBUTE_RE.finditer(attrs_text):
        attrs[str(match.group("name") or "").strip().lower()] = str(
            match.group("value") or ""
        ).strip()
    return attrs


def has_cfml_path_hints(path: Path) -> bool:
    return path.suffix.lower() in _KNOWN_SUFFIXES


def is_probable_cfml_source(*, path: Path, text: str) -> bool:
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return False
    return bool(text.strip()) if not _CFML_KEYWORD_RE.search(text) else True


def _normalize_target(value: str) -> str:
    normalized = str(value or "").strip().strip('"').strip("'")
    if not normalized or "#" in normalized:
        return ""
    normalized = normalized.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip()


def component_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    without_suffix_path = str(path.with_suffix(""))
    dotted_path = without_suffix_path.replace("/", ".").strip(".")
    return dotted_path or path.stem


def declared_component_name(*, text: str, file_path: str) -> str:
    stripped_text = strip_comments(text)
    for match in (
        _TAG_COMPONENT_RE.search(stripped_text),
        _SCRIPT_COMPONENT_RE.search(stripped_text),
    ):
        if match is None:
            continue
        attrs = _parse_attrs(str(match.group("attrs") or ""))
        explicit_name = _normalize_target(attrs.get("name", ""))
        if explicit_name:
            return explicit_name.replace("/", ".")
    return component_name_from_path(file_path)


def component_extends_targets(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    targets: list[str] = []
    for match in (
        _TAG_COMPONENT_RE.search(stripped_text),
        _SCRIPT_COMPONENT_RE.search(stripped_text),
    ):
        if match is None:
            continue
        attrs = _parse_attrs(str(match.group("attrs") or ""))
        extends_target = _normalize_target(attrs.get("extends", ""))
        if extends_target:
            targets.append(extends_target.replace("/", "."))
    return tuple(dict.fromkeys(targets))


def import_targets_for_text(text: str) -> tuple[str, ...]:
    stripped_text = strip_comments(text)
    targets: list[str] = []
    for match in _TAG_INCLUDE_RE.finditer(stripped_text):
        attrs = _parse_attrs(str(match.group("attrs") or ""))
        target = _normalize_target(attrs.get("template", ""))
        if target:
            targets.append(target)
    for match in _SCRIPT_INCLUDE_RE.finditer(stripped_text):
        target = _normalize_target(match.group("path") or "")
        if target:
            targets.append(target)
    return tuple(dict.fromkeys(targets))


def iter_function_entries(text: str) -> tuple[tuple[str, int, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int, int]] = []
    for match in _TAG_FUNCTION_BLOCK_RE.finditer(stripped_text):
        attrs = _parse_attrs(str(match.group("attrs") or ""))
        name = _normalize_target(attrs.get("name", ""))
        if not name:
            continue
        start_line = _line_number(stripped_text, match.start())
        end_line = _line_number(stripped_text, match.end())
        entries.append((name, start_line, end_line))
    for match in _SCRIPT_FUNCTION_RE.finditer(stripped_text):
        name = _normalize_target(match.group("name") or "")
        if not name:
            continue
        start_line = _line_number(stripped_text, match.start())
        entries.append((name, start_line, start_line))
    return tuple(
        sorted(
            dict.fromkeys(entries),
            key=lambda item: (item[1], item[2], item[0].lower()),
        )
    )


def iter_create_object_targets(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    targets: list[tuple[str, str | None, int]] = []
    for match in _CREATE_OBJECT_LITERAL_RE.finditer(stripped_text):
        target = _normalize_target(match.group("target") or "")
        if not target:
            continue
        method_name = _normalize_target(match.group("method") or "")
        line_number = _line_number(stripped_text, match.start())
        targets.append((target.replace("/", "."), method_name or None, line_number))
    return tuple(targets)


def iter_new_expression_targets(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    targets: list[tuple[str, str | None, int]] = []
    for match in _NEW_EXPRESSION_RE.finditer(stripped_text):
        target = _normalize_target(match.group("target") or "")
        if not target:
            continue
        method_name = _normalize_target(match.group("method") or "")
        line_number = _line_number(stripped_text, match.start())
        targets.append((target.replace("/", "."), method_name or None, line_number))
    return tuple(targets)


def is_operational_reference_name(name: str) -> bool:
    normalized_name = str(name or "").strip()
    return bool(normalized_name) and normalized_name.lower() not in _RESERVED_SYMBOL_NAMES
