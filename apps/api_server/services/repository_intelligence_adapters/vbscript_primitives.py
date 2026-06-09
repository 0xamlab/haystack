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

_KNOWN_SUFFIXES = frozenset({".vbs", ".vbe", ".wsf"})
_VB_KEYWORD_RE = re.compile(r"\b(option\s+explicit|function|sub|class|set|createobject)\b", re.I)
# Closing tag uses \s* before > to tolerate browser-permissive malformed end tags
# like </script > or </script\n>. Fixes py/bad-tag-filter (CodeQL).
_SCRIPT_TAG_RE = re.compile(
    r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script\s*>",
    re.IGNORECASE | re.DOTALL,
)
_SCRIPT_ATTR_RE = re.compile(
    r"(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_CLASS_DECL_RE = re.compile(
    r"^\s*(?:Public|Private|Friend)?\s*Class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
_FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:Public|Private|Friend)?\s*Function\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
_SUB_DECL_RE = re.compile(
    r"^\s*(?:Public|Private|Friend)?\s*Sub\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
_SET_NEW_BINDING_RE = re.compile(
    r"\bSet\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*New\s+"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_NEW_REFERENCE_RE = re.compile(
    r"\bNew\s+(?P<target>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
_CALL_RE = re.compile(r"(?<!\.)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b\s*(?=\()", re.IGNORECASE)
_CALL_STATEMENT_RE = re.compile(
    r"^\s*Call\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "array",
        "byref",
        "byval",
        "call",
        "case",
        "class",
        "const",
        "createobject",
        "date",
        "dim",
        "do",
        "each",
        "else",
        "elseif",
        "empty",
        "end",
        "err",
        "eval",
        "execute",
        "executeglobal",
        "exit",
        "false",
        "for",
        "function",
        "getobject",
        "if",
        "in",
        "inputbox",
        "is",
        "isarray",
        "isdate",
        "isempty",
        "isnull",
        "isnumeric",
        "join",
        "lbound",
        "left",
        "len",
        "loop",
        "me",
        "mid",
        "msgbox",
        "new",
        "next",
        "nothing",
        "not",
        "now",
        "option",
        "or",
        "preserve",
        "private",
        "public",
        "redim",
        "rem",
        "replace",
        "resume",
        "return",
        "right",
        "scriptengine",
        "select",
        "set",
        "split",
        "step",
        "string",
        "sub",
        "then",
        "time",
        "timer",
        "to",
        "trim",
        "true",
        "ubound",
        "ucase",
        "until",
        "wend",
        "while",
        "with",
        "wscript",
        "xor",
    }
)
_BUILTIN_OBJECT_NAMES = frozenset(
    {
        "application",
        "document",
        "err",
        "request",
        "response",
        "server",
        "session",
        "window",
        "wscript",
    }
)


@dataclass(frozen=True)
class _ScriptUnit:
    text: str
    start_line: int


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int
    unit_index: int


def _strip_inline_comment(raw_line: str) -> str:
    if raw_line.lstrip().lower().startswith("rem "):
        return ""
    chars: list[str] = []
    index = 0
    in_string = False
    while index < len(raw_line):
        character = raw_line[index]
        if character == '"':
            chars.append(character)
            if in_string and index + 1 < len(raw_line) and raw_line[index + 1] == '"':
                chars.append('"')
                index += 2
                continue
            in_string = not in_string
            index += 1
            continue
        if character == "'" and not in_string:
            break
        chars.append(character)
        index += 1
    return "".join(chars)


def strip_comments(text: str) -> str:
    return "\n".join(_strip_inline_comment(line) for line in text.splitlines())


def _parse_script_attrs(attrs_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in _SCRIPT_ATTR_RE.finditer(attrs_text):
        attrs[str(match.group("name") or "").strip().lower()] = str(
            match.group("value") or ""
        ).strip()
    return attrs


def _looks_like_vbscript(text: str) -> bool:
    return bool(_VB_KEYWORD_RE.search(text))


def _script_tag_is_vbscript(*, attrs: dict[str, str], body: str) -> bool:
    language = attrs.get("language", "").strip().lower()
    src = attrs.get("src", "").strip().lower()
    if "vbscript" in language:
        return True
    if src.endswith((".vbs", ".vbe")):
        return True
    return not src and _looks_like_vbscript(body)


def is_probable_vbscript_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix in {".vbs", ".vbe"}:
        return True
    if suffix != ".wsf":
        return False
    for match in _SCRIPT_TAG_RE.finditer(text):
        attrs = _parse_script_attrs(str(match.group("attrs") or ""))
        body = str(match.group("body") or "")
        if _script_tag_is_vbscript(attrs=attrs, body=body):
            return True
    return False


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


def _normalize_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip('"').strip("'").strip()


def _script_units_for_text(*, path: PurePosixPath, text: str) -> tuple[_ScriptUnit, ...]:
    if path.suffix.lower() in {".vbs", ".vbe"}:
        return (_ScriptUnit(text=strip_comments(text), start_line=1),)
    if path.suffix.lower() != ".wsf":
        return ()
    units: list[_ScriptUnit] = []
    for match in _SCRIPT_TAG_RE.finditer(text):
        attrs = _parse_script_attrs(str(match.group("attrs") or ""))
        body = str(match.group("body") or "")
        if not _script_tag_is_vbscript(attrs=attrs, body=body) or attrs.get("src"):
            continue
        units.append(
            _ScriptUnit(
                text=strip_comments(body),
                start_line=text.count("\n", 0, match.start("body")) + 1,
            )
        )
    return tuple(units)


def import_targets_for_text(*, path: PurePosixPath, text: str) -> tuple[str, ...]:
    if path.suffix.lower() != ".wsf":
        return ()
    targets: list[str] = []
    seen: set[str] = set()
    for match in _SCRIPT_TAG_RE.finditer(text):
        attrs = _parse_script_attrs(str(match.group("attrs") or ""))
        body = str(match.group("body") or "")
        if not _script_tag_is_vbscript(attrs=attrs, body=body):
            continue
        src_target = _normalize_target(attrs.get("src", ""))
        if not src_target or src_target in seen:
            continue
        seen.add(src_target)
        targets.append(src_target)
    return tuple(targets)


def _iter_declared_symbols(text: str) -> Iterable[tuple[str, str, int]]:
    matches: list[tuple[int, str, str]] = []
    for kind, pattern in (
        ("class", _CLASS_DECL_RE),
        ("function", _FUNCTION_DECL_RE),
        ("function", _SUB_DECL_RE),
    ):
        for match in pattern.finditer(text):
            symbol_name = _normalize_target(match.group("name") or "")
            if not symbol_name or symbol_name.lower() in _RESERVED_SYMBOL_NAMES:
                continue
            matches.append((match.start(), kind, symbol_name))
    for start_offset, kind, symbol_name in sorted(matches):
        yield kind, symbol_name, start_offset


def _collect_symbols_for_unit(
    *,
    file_path: str,
    unit_text: str,
    unit_start_line: int,
    unit_index: int,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    entries: list[dict[str, Any]] = []
    seen_symbol_names: set[tuple[str, int]] = set()
    unit_lines = unit_text.splitlines()
    final_line = unit_start_line + max(len(unit_lines) - 1, 0)
    for kind, symbol_name, start_offset in _iter_declared_symbols(unit_text):
        local_line = unit_text.count("\n", 0, start_offset) + 1
        key = (symbol_name.lower(), local_line)
        if key in seen_symbol_names:
            continue
        seen_symbol_names.add(key)
        start_line = unit_start_line + local_line - 1
        entries.append(
            {
                "symbol": _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": symbol_name,
                            "line": start_line,
                            "kind": kind,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=kind,
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=None,
                    signature=symbol_name,
                ),
                "local_start_line": local_line,
                "local_end_line": local_line,
                "unit_index": unit_index,
            }
        )
    for index, entry in enumerate(entries):
        next_start = (
            entries[index + 1]["symbol"].start_line
            if index + 1 < len(entries)
            else final_line + 1
        )
        entry["symbol"] = _Symbol(
            symbol_id=entry["symbol"].symbol_id,
            symbol_name=entry["symbol"].symbol_name,
            symbol_kind=entry["symbol"].symbol_kind,
            start_line=entry["symbol"].start_line,
            end_line=max(next_start - 1, entry["symbol"].start_line),
            parent_symbol_id=None,
            signature=entry["symbol"].signature,
        )
        entry["local_end_line"] = max(
            int(entry["symbol"].end_line) - unit_start_line + 1,
            int(entry["local_start_line"]),
        )
    return tuple(
        _CollectedSymbol(
            symbol=entry["symbol"],
            local_start_line=int(entry["local_start_line"]),
            local_end_line=int(entry["local_end_line"]),
            unit_index=int(entry["unit_index"]),
        )
        for entry in entries
    )
