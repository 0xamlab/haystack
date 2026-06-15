from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

ODIN_FILE_SUFFIXES = frozenset({".odin"})
ODIN_CONFIG_BASENAMES = frozenset({"ols.json"})

PACKAGE_RE = re.compile(r"(?m)^\s*package\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
IMPORT_RE = re.compile(
    r'(?m)^\s*import\s+(?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s+)?\"(?P<target>[^\"]+)\"'
)
DECLARATION_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*::\s*(?P<kind>proc|struct|union|enum|bit_set|distinct)\b"
)
CONST_DECLARATION_RE = re.compile(r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:=")
VARIABLE_DECLARATION_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?![:=])"
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<qualifier>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
UNQUALIFIED_CALL_RE = re.compile(
    r"(?<![.:])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
ODIN_MARKER_RE = re.compile(
    r"\b(?:package|import|proc|struct|union|enum|bit_set|distinct)\b"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "align_of",
        "asm",
        "auto_cast",
        "bit_set",
        "break",
        "case",
        "cast",
        "context",
        "continue",
        "defer",
        "distinct",
        "do",
        "dynamic",
        "else",
        "enum",
        "fallthrough",
        "for",
        "foreign",
        "if",
        "import",
        "in",
        "len",
        "make",
        "map",
        "matrix",
        "not_in",
        "offset_of",
        "or_else",
        "package",
        "proc",
        "return",
        "size_of",
        "struct",
        "switch",
        "transmute",
        "type_of",
        "union",
        "using",
        "when",
        "where",
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
    block_depth = 0
    in_string = False
    string_delimiter = ""
    while index < len(characters):
        current = characters[index]
        next_char = characters[index + 1] if index + 1 < len(characters) else ""
        if in_string:
            if string_delimiter == '"' and current == "\\":
                index += 2
                continue
            if current == string_delimiter:
                in_string = False
                string_delimiter = ""
            index += 1
            continue
        if block_depth > 0:
            if current == "/" and next_char == "*":
                characters[index] = " "
                characters[index + 1] = " "
                block_depth += 1
                index += 2
                continue
            if current == "*" and next_char == "/":
                characters[index] = " "
                characters[index + 1] = " "
                block_depth -= 1
                index += 2
                continue
            if current != "\n":
                characters[index] = " "
            index += 1
            continue
        if current == "`":
            in_string = True
            string_delimiter = "`"
            index += 1
            continue
        if current == '"':
            in_string = True
            string_delimiter = '"'
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
            block_depth = 1
            index += 2
            continue
        index += 1
    return "".join(characters)


def has_odin_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in ODIN_FILE_SUFFIXES
        or normalized_path.name.lower() in ODIN_CONFIG_BASENAMES
    )


def _is_probable_ols_config(text: str) -> bool:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return any(
        key in payload
        for key in (
            "collections",
            "profiles",
            "profile",
            "checker_path",
            "odin_command",
        )
    )


def is_probable_odin_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    basename = normalized_path.name.lower()
    if basename in ODIN_CONFIG_BASENAMES:
        return _is_probable_ols_config(text)
    if normalized_path.suffix.lower() not in ODIN_FILE_SUFFIXES:
        return False
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(ODIN_MARKER_RE.search(stripped_text))


def package_name_from_text(
    text: str,
    *,
    file_path: str,
    stripped_text: str | None = None,
) -> str:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    match = PACKAGE_RE.search(stripped_text)
    if match is not None:
        package_name = str(match.group("name") or "").strip()
        if package_name:
            return package_name
    return PurePosixPath(file_path).stem


def default_import_alias(import_target: str) -> str:
    normalized_target = str(import_target or "").strip().rstrip("/")
    if not normalized_target:
        return ""
    if ":" in normalized_target:
        normalized_target = normalized_target.split(":", 1)[1]
    return normalized_target.rsplit("/", 1)[-1].strip()


def parse_import_statements(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    imports: list[tuple[str, str | None, int]] = []
    seen: set[tuple[str, str | None, int]] = set()
    for match in IMPORT_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip()
        alias = str(match.group("alias") or "").strip() or None
        if not target:
            continue
        item = (target, alias, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        imports.append(item)
    return tuple(imports)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    symbols: list[tuple[str, str, int]] = []
    seen_names: set[tuple[str, str, int]] = set()
    brace_depth = 0
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        line = raw_line.strip()
        if brace_depth == 0:
            declaration_match = DECLARATION_RE.match(line)
            if declaration_match is not None:
                item = (
                    str(declaration_match.group("name") or "").strip(),
                    str(declaration_match.group("kind") or "").strip(),
                    line_number,
                )
                if item[0] and item not in seen_names:
                    seen_names.add(item)
                    symbols.append(item)
            else:
                const_match = CONST_DECLARATION_RE.match(line)
                if const_match is not None:
                    item = (
                        str(const_match.group("name") or "").strip(),
                        "constant",
                        line_number,
                    )
                    if item[0] and item not in seen_names:
                        seen_names.add(item)
                        symbols.append(item)
                else:
                    variable_match = VARIABLE_DECLARATION_RE.match(line)
                    if variable_match is not None:
                        item = (
                            str(variable_match.group("name") or "").strip(),
                            "variable",
                            line_number,
                        )
                        if item[0] and item not in seen_names:
                            seen_names.add(item)
                            symbols.append(item)
        brace_depth += raw_line.count("{")
        brace_depth -= raw_line.count("}")
        if brace_depth < 0:
            brace_depth = 0
    return tuple(symbols)


def parse_reference_targets(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith(("package ", "import ")):
            continue
        for match in QUALIFIED_REFERENCE_RE.finditer(raw_line):
            qualifier = str(match.group("qualifier") or "").strip()
            name = str(match.group("name") or "").strip()
            if (
                not qualifier
                or not name
                or qualifier in RESERVED_SYMBOL_NAMES
                or name in RESERVED_SYMBOL_NAMES
            ):
                continue
            item = (qualifier, name, line_number)
            if item in seen:
                continue
            seen.add(item)
            references.append(item)
        for match in UNQUALIFIED_CALL_RE.finditer(raw_line):
            name = str(match.group("name") or "").strip()
            if not name or name in RESERVED_SYMBOL_NAMES:
                continue
            item = (None, name, line_number)
            if item in seen:
                continue
            seen.add(item)
            references.append(item)
    return tuple(references)
