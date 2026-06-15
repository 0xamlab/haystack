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

_KNOWN_SUFFIXES = frozenset({".agda", ".lagda", ".agda-lib"})
_KNOWN_COMPOUND_SUFFIXES = (
    ".lagda.md",
    ".lagda.rst",
    ".lagda.tex",
    ".lagda.org",
)
_MODULE_RE = re.compile(
    r"^\s*module\s+(?P<name>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\b",
    re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"^\s*(?:open\s+)?import\s+"
    r"(?P<target>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)"
    r"(?:\s+as\s+(?P<alias>[A-Z][A-Za-z0-9_']*))?"
    r"(?P<rest>.*)$",
    re.MULTILINE,
)
_DATA_RE = re.compile(r"^\s*data\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b", re.MULTILINE)
_RECORD_RE = re.compile(r"^\s*record\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b", re.MULTILINE)
_MODULE_DECL_RE = re.compile(r"^\s*module\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b", re.MULTILINE)
_POSTULATE_LINE_RE = re.compile(
    r"^\s*postulate\s+(?P<body>.+)$",
    re.MULTILINE,
)
_FUNCTION_SIG_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_']*)\s*:",
    re.MULTILINE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\.(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b"
)
_TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_']*)\b")
_CALL_RE = re.compile(
    r"(?<![.'])\b(?P<name>[a-z_][A-Za-z0-9_']*)\b(?=\s*(?:\{|[A-Za-z_(]))"
)
_USING_RE = re.compile(r"\busing\s*\((?P<body>[^)]*)\)")
_RENAMING_RE = re.compile(r"\brenaming\s*\((?P<body>[^)]*)\)")
_RENAME_ENTRY_RE = re.compile(
    r"(?P<source>[A-Za-z_][A-Za-z0-9_']*)\s+to\s+(?P<target>[A-Za-z_][A-Za-z0-9_']*)"
)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abstract",
        "data",
        "field",
        "import",
        "in",
        "let",
        "module",
        "mutual",
        "open",
        "pattern",
        "postulate",
        "private",
        "record",
        "renaming",
        "syntax",
        "using",
        "variable",
        "where",
        "with",
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


def _strip_compound_suffix(path: PurePosixPath) -> str:
    normalized = str(path)
    lower_normalized = normalized.lower()
    for suffix in _KNOWN_COMPOUND_SUFFIXES:
        if lower_normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    if path.suffix:
        return str(path.with_suffix(""))
    return normalized


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
    if "--" not in text and "{-" not in text:
        return text
    if "{-" not in text and '"' not in text:
        stripped_lines: list[str] = []
        for line in text.splitlines(keepends=True):
            line_ending = ""
            content = line
            if line.endswith("\r\n"):
                line_ending = "\r\n"
                content = line[:-2]
            elif line.endswith("\n") or line.endswith("\r"):
                line_ending = line[-1]
                content = line[:-1]
            comment_index = content.find("--")
            if comment_index < 0:
                stripped_lines.append(line)
                continue
            stripped_lines.append(
                content[:comment_index]
                + (" " * (len(content) - comment_index))
                + line_ending
            )
        return "".join(stripped_lines)
    result: list[str] = []
    in_block_comment = 0
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if in_block_comment:
            if character == "{" and next_character == "-":
                in_block_comment += 1
                result.extend((" ", " "))
                index += 2
                continue
            if character == "-" and next_character == "}":
                in_block_comment = max(0, in_block_comment - 1)
                result.extend((" ", " "))
                index += 2
                continue
            result.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            result.append(character)
            index += 1
            continue
        if character == "-" and next_character == "-":
            while index < len(text) and text[index] != "\n":
                result.append(" ")
                index += 1
            continue
        if character == "{" and next_character == "-":
            in_block_comment = 1
            result.extend((" ", " "))
            index += 2
            continue
        result.append(character)
        index += 1
    return "".join(result)


def has_agda_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = str(PurePosixPath(path)).lower()
    return (
        PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES
        or any(normalized_path.endswith(suffix) for suffix in _KNOWN_COMPOUND_SUFFIXES)
    )


def is_probable_agda_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    if not has_agda_path_hints(path):
        return False
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    if not candidate_stripped_text.strip():
        return False
    if str(PurePosixPath(path)).lower().endswith(".agda-lib"):
        lowered_text = candidate_stripped_text.lower()
        return "include:" in lowered_text or "name:" in lowered_text
    return bool(_MODULE_RE.search(candidate_stripped_text) or _IMPORT_RE.search(candidate_stripped_text))


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    for source_root in ("src", "lib", "test", "tests"):
        if source_root not in path.parts:
            continue
        root_index = path.parts.index(source_root)
        module_parts = list(path.parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(
            _strip_compound_suffix(PurePosixPath(module_parts[-1]))
        ).name
        return ".".join(part for part in module_parts if part)
    stripped_name = PurePosixPath(_strip_compound_suffix(path)).name
    return stripped_name


def parse_import_names(raw_value: str) -> tuple[str, ...]:
    normalized = str(raw_value or "").strip()
    if not normalized:
        return ()
    names: list[str] = []
    using_match = _USING_RE.search(normalized)
    if using_match is not None:
        for raw_item in re.split(r"[;,]", str(using_match.group("body") or "")):
            candidate = raw_item.strip()
            if not candidate or not _IDENTIFIER_RE.match(candidate):
                continue
            names.append(candidate)
    renaming_match = _RENAMING_RE.search(normalized)
    if renaming_match is not None:
        for rename_match in _RENAME_ENTRY_RE.finditer(str(renaming_match.group("body") or "")):
            target_name = str(rename_match.group("target") or "").strip()
            if target_name and _IDENTIFIER_RE.match(target_name):
                names.append(target_name)
    return tuple(dict.fromkeys(names))


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    candidate_stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for regex, symbol_kind in (
        (_DATA_RE, "data"),
        (_RECORD_RE, "record"),
        (_MODULE_DECL_RE, "module"),
        (_FUNCTION_SIG_RE, "function"),
    ):
        for match in regex.finditer(candidate_stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if (
                not symbol_name
                or symbol_name in seen_names
                or symbol_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append(
                (symbol_name, symbol_kind, _line_number(candidate_stripped_text, match.start()))
            )
    for match in _POSTULATE_LINE_RE.finditer(candidate_stripped_text):
        body = str(match.group("body") or "")
        for candidate_match in re.finditer(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b", body):
            symbol_name = str(candidate_match.group("name") or "").strip()
            if (
                not symbol_name
                or symbol_name in seen_names
                or symbol_name in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append(
                (
                    symbol_name,
                    "postulate",
                    _line_number(candidate_stripped_text, match.start()),
                )
            )
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))
