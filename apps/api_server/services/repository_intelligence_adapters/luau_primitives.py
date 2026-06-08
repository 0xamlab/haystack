from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".luau", ".lua"})
REQUIRE_RE = re.compile(
    r"\brequire\b\s*\(\s*['\"](?P<target>[^'\"]+)['\"]\s*\)",
    re.MULTILINE,
)
REQUIRE_BINDING_RE = re.compile(
    r"^\s*(?:local\s+)?(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"require\b\s*\(\s*['\"](?P<target>[^'\"]+)['\"]\s*\)"
    r"(?:\.(?P<member>[A-Za-z_][A-Za-z0-9_]*))?",
    re.MULTILINE,
)
SCRIPT_REQUIRE_RE = re.compile(
    r"\brequire\b\s*\(\s*(?P<target>script(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*\)",
    re.MULTILINE,
)
SCRIPT_REQUIRE_BINDING_RE = re.compile(
    r"^\s*(?:local\s+)?(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"require\b\s*\(\s*(?P<target>script(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*\)"
    r"(?:\.(?P<member>[A-Za-z_][A-Za-z0-9_]*))?",
    re.MULTILINE,
)
TS_IMPORT_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\.import\s*\(\s*script\s*,\s*script\s*,\s*['\"](?P<target>[^'\"]+)['\"]\s*\)",
    re.MULTILINE,
)
TS_IMPORT_BINDING_RE = re.compile(
    r"^\s*(?:local\s+)?(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"[A-Za-z_][A-Za-z0-9_]*\.import\s*\(\s*script\s*,\s*script\s*,\s*['\"](?P<target>[^'\"]+)['\"]\s*\)",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:local\s+)?function\s+"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:[.:][A-Za-z_][A-Za-z0-9_]*)*)\s*\(",
    re.MULTILINE,
)
FUNCTION_ASSIGN_RE = re.compile(
    r"^\s*(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:[.:][A-Za-z_][A-Za-z0-9_]*)*)\s*=\s*function\s*\(",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:export\s+)?type\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)[.:](?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
IMPORTED_CALL_RE = re.compile(r"(?<![.:])\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
TYPE_MARKER_RE = re.compile(r"(?m)^\s*(?:export\s+)?type\s+[A-Za-z_][A-Za-z0-9_]*\b")
DIRECTIVE_RE = re.compile(r"(?m)^\s*--![A-Za-z0-9_! -]+$")
MARKER_RE = re.compile(
    r"\b(?:require|export\s+type|type\s+[A-Za-z_]|script\.Parent|TS\.import|game:GetService)\b"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "break",
        "continue",
        "do",
        "else",
        "elseif",
        "end",
        "export",
        "false",
        "for",
        "function",
        "if",
        "in",
        "local",
        "nil",
        "not",
        "or",
        "repeat",
        "return",
        "self",
        "then",
        "true",
        "type",
        "until",
        "while",
    }
)


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
        if current == "-" and next_char == "-":
            if (
                index + 3 < len(characters)
                and characters[index + 2] == "["
                and characters[index + 3] == "["
            ):
                characters[index] = " "
                characters[index + 1] = " "
                characters[index + 2] = " "
                characters[index + 3] = " "
                index += 4
                while index + 1 < len(characters):
                    if characters[index] == "]" and characters[index + 1] == "]":
                        characters[index] = " "
                        characters[index + 1] = " "
                        index += 2
                        break
                    if characters[index] != "\n":
                        characters[index] = " "
                    index += 1
                continue
            if index + 2 < len(characters) and characters[index + 2] == "!":
                index += 1
                while index < len(characters) and characters[index] != "\n":
                    index += 1
                continue
            characters[index] = " "
            characters[index + 1] = " "
            index += 2
            while index < len(characters) and characters[index] != "\n":
                characters[index] = " "
                index += 1
            continue
        index += 1
    return "".join(characters)


def has_luau_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_luau_source(*, path: Path | PurePosixPath, text: str) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix == ".luau":
        return bool(text.strip())
    if suffix != ".lua":
        return False
    if DIRECTIVE_RE.search(text):
        return True
    stripped_text = strip_comments(text)
    return bool(TYPE_MARKER_RE.search(stripped_text) or MARKER_RE.search(stripped_text))


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    matches = [
        *((match.start(), match.group("target"), "function") for match in FUNCTION_DECL_RE.finditer(text)),
        *((match.start(), match.group("target"), "function") for match in FUNCTION_ASSIGN_RE.finditer(text)),
        *((match.start(), match.group("name"), "type") for match in TYPE_DECL_RE.finditer(text)),
    ]
    for offset, raw_target, symbol_kind in sorted(matches):
        normalized_target = str(raw_target or "").strip()
        if not normalized_target:
            continue
        symbol_name = re.split(r"[.:]", normalized_target)[-1].strip()
        if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES:
            continue
        line_no = text.count("\n", 0, offset) + 1
        symbol_key = (symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "line": line_no,
                        "kind": symbol_kind,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": line_no,
                "signature": normalized_target,
            }
        )
    final_line = len(text.splitlines()) if text else 1
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries
