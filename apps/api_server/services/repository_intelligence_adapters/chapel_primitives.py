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

_KNOWN_SUFFIXES = frozenset({".chpl"})
_MODULE_RE = re.compile(r"(?m)^\s*module\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_USE_IMPORT_RE = re.compile(
    r"(?m)^\s*(?:(?:public|private)\s+)?(?P<kind>use|import)\s+(?P<targets>[^;\n]+);"
)
_SYMBOL_RE = re.compile(
    r"(?m)^\s*(?:(?:public|private|override|inline|export|extern|required|config|param|type|ref|const|var)\s+)*"
    r"(?P<kind>proc|iter|class|record|union|enum|interface|operator)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*|[^\s(]+)"
)
_VARIABLE_RE = re.compile(
    r"(?m)^\s*(?:(?:public|private)\s+)?(?:(?:config|param|const|var|type)\s+)+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_UNQUALIFIED_CALL_RE = re.compile(r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_MARKER_RE = re.compile(r"\b(?:module|use|import|proc|iter|class|record|enum)\b")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "align",
        "as",
        "begin",
        "borrowed",
        "break",
        "by",
        "catch",
        "class",
        "coforall",
        "config",
        "const",
        "continue",
        "delete",
        "dmapped",
        "do",
        "domain",
        "else",
        "enum",
        "except",
        "export",
        "extern",
        "for",
        "forall",
        "if",
        "implements",
        "import",
        "in",
        "index",
        "inline",
        "interface",
        "iter",
        "label",
        "lambda",
        "let",
        "local",
        "module",
        "new",
        "nil",
        "noinit",
        "on",
        "only",
        "operator",
        "otherwise",
        "override",
        "owned",
        "param",
        "private",
        "proc",
        "public",
        "record",
        "reduce",
        "ref",
        "return",
        "scan",
        "select",
        "serial",
        "shared",
        "single",
        "sparse",
        "subdomain",
        "sync",
        "then",
        "throw",
        "throws",
        "try",
        "type",
        "union",
        "unmanaged",
        "use",
        "var",
        "when",
        "where",
        "while",
        "with",
        "yield",
        "zip",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    qualified_names: tuple[str, ...]


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
    string_delimiter = ""
    while index < len(characters):
        current = characters[index]
        next_char = characters[index + 1] if index + 1 < len(characters) else ""
        if in_string:
            if current == "\\":
                index += 2
                continue
            if current == string_delimiter:
                in_string = False
                string_delimiter = ""
            index += 1
            continue
        if current in {'"', "'"}:
            in_string = True
            string_delimiter = current
            index += 1
            continue
        if current == "/" and next_char == "/":
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
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


def has_chapel_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def module_name_from_path(file_path: str) -> str:
    return PurePosixPath(file_path).stem


def module_name_from_text(text: str, *, file_path: str) -> str:
    stripped_text = strip_comments(text)
    match = _MODULE_RE.search(stripped_text)
    if match is not None:
        module_name = str(match.group("name") or "").strip()
        if module_name:
            return module_name
    return module_name_from_path(file_path)


def is_probable_chapel_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_chapel_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


def _split_target_segments(raw_targets: str) -> tuple[str, ...]:
    segments: list[str] = []
    current: list[str] = []
    brace_depth = 0
    for character in raw_targets:
        if character == "{":
            brace_depth += 1
        elif character == "}":
            brace_depth = max(0, brace_depth - 1)
        if character == "," and brace_depth == 0:
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
            continue
        current.append(character)
    tail = "".join(current).strip()
    if tail:
        segments.append(tail)
    return tuple(segments)


def _normalize_import_target(raw_target: str) -> tuple[str, str | None]:
    normalized_target = str(raw_target or "").strip()
    if not normalized_target:
        return "", None
    alias: str | None = None
    alias_match = re.search(r"\bas\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*$", normalized_target)
    if alias_match is not None:
        alias = str(alias_match.group("alias") or "").strip() or None
        normalized_target = normalized_target[: alias_match.start()].strip()
    for separator in (" only ", " except "):
        lowered = normalized_target.lower()
        index = lowered.find(separator)
        if index >= 0:
            normalized_target = normalized_target[:index].strip()
            break
    normalized_target = normalized_target.split("{", 1)[0].strip().rstrip(".")
    return normalized_target, alias


def parse_use_import_statements(text: str) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, str, str | None, int]] = []
    seen: set[tuple[str, str, str | None, int]] = set()
    for match in _USE_IMPORT_RE.finditer(stripped_text):
        statement_kind = str(match.group("kind") or "").strip()
        line_number = _line_number(stripped_text, match.start())
        for segment in _split_target_segments(str(match.group("targets") or "")):
            import_target, alias = _normalize_import_target(segment)
            if not import_target:
                continue
            item = (statement_kind, import_target, alias, line_number)
            if item in seen:
                continue
            seen.add(item)
            statements.append(item)
    return tuple(statements)


def iter_symbol_entries(text: str, *, file_path: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_text(stripped_text, file_path=file_path)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, kind_group, name_group, default_kind in (
        (_SYMBOL_RE, "kind", "name", ""),
        (_VARIABLE_RE, "", "name", "variable"),
    ):
        for match in regex.finditer(stripped_text):
            symbol_name = str(match.group(name_group) or "").strip()
            symbol_kind = (
                str(match.group(kind_group) or "").strip().lower()
                if kind_group
                else default_kind
            )
            if (
                not symbol_name
                or symbol_name == module_name
                or symbol_name in seen_names
                or symbol_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def parse_reference_targets(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        alias = str(match.group("alias") or "").strip()
        symbol_name = str(match.group("name") or "").strip()
        if (
            not alias
            or not symbol_name
            or alias in _RESERVED_SYMBOL_NAMES
            or symbol_name in _RESERVED_SYMBOL_NAMES
        ):
            continue
        item = (alias, symbol_name, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        references.append(item)
    for match in _UNQUALIFIED_CALL_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in _RESERVED_SYMBOL_NAMES:
            continue
        item = (None, symbol_name, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        references.append(item)
    return tuple(references)
