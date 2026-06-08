from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

_KNOWN_SUFFIXES = frozenset({".sv", ".svh", ".v", ".vh"})
_DIRECT_SYSTEMVERILOG_SUFFIXES = frozenset({".sv", ".svh"})
_AMBIGUOUS_SYSTEMVERILOG_SUFFIXES = frozenset({".v", ".vh"})
_PATH_HINT_PARTS = frozenset(
    {
        "dv",
        "hdl",
        "rtl",
        "sim",
        "sv",
        "tb",
        "testbench",
        "uvm",
        "verilog",
    }
)
_PATH_HINT_BASENAMES = frozenset(
    {
        "bender.yml",
        "bender.yaml",
        "fusesoc.conf",
    }
)
_PRIMARY_TOKEN_RE = re.compile(
    r"^\s*(?:(?:virtual|automatic)\s+)*(?:(?P<kind>module|interface|package|program|class)\s+"
    r"(?:(?:automatic)\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\b|"
    r"(?P<end>endmodule|endinterface|endpackage|endprogram|endclass)\b)",
    re.IGNORECASE | re.MULTILINE,
)
_ROUTINE_DECL_RE = re.compile(
    r"^\s*(?P<kind>function|task)\b(?P<header>[^\n]*)",
    re.IGNORECASE | re.MULTILINE,
)
_INCLUDE_RE = re.compile(
    r"^\s*`include\s+[\"<](?P<target>[^\">]+)[\">]",
    re.IGNORECASE | re.MULTILINE,
)
_IMPORT_RE = re.compile(
    r"\bimport\s+(?P<body>[A-Za-z_][A-Za-z0-9_$]*::(?:\*|[A-Za-z_][A-Za-z0-9_$]*)"
    r"(?:\s*,\s*[A-Za-z_][A-Za-z0-9_$]*::(?:\*|[A-Za-z_][A-Za-z0-9_$]*))*)\s*;",
    re.IGNORECASE,
)
_IMPORT_ITEM_RE = re.compile(
    r"(?P<package>[A-Za-z_][A-Za-z0-9_$]*)::(?P<name>\*|[A-Za-z_][A-Za-z0-9_$]*)"
)
_QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<package>[A-Za-z_][A-Za-z0-9_$]*)::(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\b"
)
_INSTANTIATION_RE = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_$]*)"
    r"\s*(?:#\s*\([^;]*?\))?\s+(?P<instance>[A-Za-z_][A-Za-z0-9_$]*)\s*\(",
)
_PROBABLE_SYSTEMVERILOG_RE = re.compile(
    r"(?im)^\s*(?:"
    r"`(?:include|define|ifdef|ifndef|elsif|else|endif|timescale)\b|"
    r"(?:module|interface|package|program)\s+[A-Za-z_][A-Za-z0-9_$]*\b|"
    r"(?:virtual\s+)?class\s+[A-Za-z_][A-Za-z0-9_$]*\b|"
    r"end(?:module|interface|package|program|class)\b|"
    r"import\s+[A-Za-z_][A-Za-z0-9_$]*::(?:\*|[A-Za-z_][A-Za-z0-9_$]*)\s*;"
    r")"
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "always",
        "always_comb",
        "always_ff",
        "always_latch",
        "and",
        "assign",
        "automatic",
        "begin",
        "bit",
        "byte",
        "case",
        "class",
        "clocking",
        "const",
        "cover",
        "default",
        "disable",
        "do",
        "else",
        "end",
        "endcase",
        "endclass",
        "endfunction",
        "endmodule",
        "endinterface",
        "endpackage",
        "endprogram",
        "endtask",
        "enum",
        "event",
        "final",
        "for",
        "forever",
        "fork",
        "function",
        "generate",
        "genvar",
        "if",
        "import",
        "initial",
        "inout",
        "input",
        "int",
        "integer",
        "interface",
        "localparam",
        "logic",
        "module",
        "negedge",
        "or",
        "output",
        "package",
        "parameter",
        "posedge",
        "program",
        "property",
        "rand",
        "randc",
        "reg",
        "repeat",
        "return",
        "sequence",
        "signed",
        "static",
        "string",
        "struct",
        "task",
        "typedef",
        "union",
        "unsigned",
        "virtual",
        "void",
        "wait",
        "while",
        "wire",
    }
)
_END_TOKEN_TO_KIND = {
    "endclass": "class",
    "endmodule": "module",
    "endinterface": "interface",
    "endpackage": "package",
    "endprogram": "program",
}
_PRIMARY_SYMBOL_KINDS = frozenset({"class", "interface", "module", "package", "program"})
_ROUTINE_MODIFIERS = frozenset(
    {
        "automatic",
        "extern",
        "local",
        "protected",
        "pure",
        "static",
        "virtual",
    }
)


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


def strip_comments(text: str) -> str:
    chars: list[str] = []
    index = 0
    in_double = False
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if character == '"':
            escaped = index > 0 and text[index - 1] == "\\"
            if not escaped:
                in_double = not in_double
            chars.append(character)
            index += 1
            continue
        if not in_double and character == "/" and next_character == "/":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        if not in_double and character == "/" and next_character == "*":
            index += 2
            while index < len(text):
                block_character = text[index]
                block_next = text[index + 1] if index + 1 < len(text) else ""
                if block_character == "\n":
                    chars.append("\n")
                if block_character == "*" and block_next == "/":
                    index += 2
                    break
                index += 1
            continue
        chars.append(character)
        index += 1
    return "".join(chars)


def has_systemverilog_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    parts = {part.lower() for part in normalized_path.parts}
    if parts & _PATH_HINT_PARTS:
        return True
    return normalized_path.name.lower() in _PATH_HINT_BASENAMES


def is_probable_systemverilog_source(*, path: Path | PurePosixPath, text: str) -> bool:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix not in _KNOWN_SUFFIXES:
        return False
    if suffix in _DIRECT_SYSTEMVERILOG_SUFFIXES:
        return True
    stripped_text = strip_comments(text)
    if _PROBABLE_SYSTEMVERILOG_RE.search(stripped_text):
        return True
    return has_systemverilog_path_hints(path)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _normalized_path_aliases(path: PurePosixPath) -> set[str]:
    return {
        str(path),
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }


def _collect_primary_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    final_line = len(text.splitlines()) if text else 1
    entries: list[dict[str, Any]] = []
    stack: list[int] = []
    for match in _PRIMARY_TOKEN_RE.finditer(text):
        raw_end = str(match.group("end") or "").lower()
        if raw_end:
            end_kind = _END_TOKEN_TO_KIND.get(raw_end)
            if end_kind is None:
                continue
            line_no = _line_number(text, match.start())
            for stack_index in range(len(stack) - 1, -1, -1):
                entry_index = stack[stack_index]
                if str(entries[entry_index]["symbol_kind"]) != end_kind:
                    continue
                entries[entry_index]["end_line"] = line_no
                del stack[stack_index:]
                break
            continue
        symbol_kind = str(match.group("kind") or "").lower()
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name:
            continue
        line_no = _line_number(text, match.start())
        parent_symbol_id = None
        if stack:
            parent_symbol_id = str(entries[stack[-1]]["symbol_id"])
        entry = {
            "symbol_id": stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "name": symbol_name,
                    "kind": symbol_kind,
                    "line": line_no,
                },
            ),
            "symbol_name": symbol_name,
            "symbol_kind": symbol_kind,
            "start_line": line_no,
            "end_line": final_line,
            "parent_symbol_id": parent_symbol_id,
            "signature": symbol_name,
        }
        entries.append(entry)
        stack.append(len(entries) - 1)
    return tuple(
        _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=(
                str(entry["parent_symbol_id"])
                if entry["parent_symbol_id"] is not None
                else None
            ),
            signature=str(entry["signature"]),
        )
        for entry in entries
    )


def _routine_name_from_header(header: str) -> str:
    normalized_header = re.sub(r"//.*$", "", header).strip().rstrip(";")
    normalized_header = re.sub(
        r"^(function|task)\b",
        "",
        normalized_header,
        flags=re.IGNORECASE,
    ).strip()
    while True:
        match = re.match(r"^(?P<modifier>[A-Za-z_][A-Za-z0-9_$]*)\b", normalized_header)
        if match is None:
            break
        modifier = str(match.group("modifier") or "").lower()
        if modifier not in _ROUTINE_MODIFIERS:
            break
        normalized_header = normalized_header[match.end() :].strip()
    normalized_header = normalized_header.split("(", 1)[0].split(";", 1)[0].strip()
    match = re.search(r"(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*$", normalized_header)
    if match is None:
        return ""
    return str(match.group("name") or "").strip()


def _containing_primary_symbol_id(
    *,
    line_no: int,
    symbols: Sequence[_Symbol],
) -> str | None:
    matches = [
        symbol
        for symbol in symbols
        if symbol.symbol_kind in _PRIMARY_SYMBOL_KINDS
        and symbol.start_line <= line_no <= symbol.end_line
    ]
    if not matches:
        return None
    ranked_matches = sorted(
        matches,
        key=lambda symbol: (
            symbol.start_line,
            -(symbol.end_line - symbol.start_line),
            symbol.symbol_id,
        ),
        reverse=True,
    )
    return ranked_matches[0].symbol_id


def _collect_routine_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    primary_symbols: Sequence[_Symbol],
) -> tuple[_Symbol, ...]:
    routine_symbols: list[_Symbol] = []
    seen_routines: set[tuple[str, int, str]] = set()
    for match in _ROUTINE_DECL_RE.finditer(text):
        symbol_kind = str(match.group("kind") or "").lower()
        symbol_name = _routine_name_from_header(str(match.group("header") or ""))
        if not symbol_name:
            continue
        line_no = _line_number(text, match.start())
        symbol_key = (symbol_name, line_no, symbol_kind)
        if symbol_key in seen_routines:
            continue
        seen_routines.add(symbol_key)
        routine_symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "kind": symbol_kind,
                        "line": line_no,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_no,
                end_line=line_no,
                parent_symbol_id=_containing_primary_symbol_id(
                    line_no=line_no,
                    symbols=primary_symbols,
                ),
                signature=symbol_name,
            )
        )
    return tuple(routine_symbols)


def _ordered_symbols(
    primary_symbols: Sequence[_Symbol],
    routine_symbols: Sequence[_Symbol],
) -> tuple[_Symbol, ...]:
    return tuple(
        sorted(
            (*primary_symbols, *routine_symbols),
            key=lambda symbol: (
                symbol.start_line,
                0 if symbol.parent_symbol_id is None else 1,
                symbol.symbol_kind,
                symbol.symbol_name,
                symbol.symbol_id,
            ),
        )
    )
