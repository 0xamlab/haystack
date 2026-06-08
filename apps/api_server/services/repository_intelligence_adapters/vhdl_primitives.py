from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

_KNOWN_SUFFIXES = frozenset({".vhd", ".vhdl"})
_NAME_RE = r"[A-Za-z][A-Za-z0-9_]*"
_PATH_HINT_PARTS = frozenset({"hdl", "rtl", "tb", "testbench", "sim", "vhdl"})
_PACKAGE_DECL_RE = re.compile(
    rf"^\s*package\s+(?!body\b)(?P<name>{_NAME_RE})\s+is\b",
    re.IGNORECASE | re.MULTILINE,
)
_PACKAGE_BODY_RE = re.compile(
    rf"^\s*package\s+body\s+(?P<name>{_NAME_RE})\s+is\b",
    re.IGNORECASE | re.MULTILINE,
)
_ENTITY_DECL_RE = re.compile(
    rf"^\s*entity\s+(?P<name>{_NAME_RE})\s+is\b",
    re.IGNORECASE | re.MULTILINE,
)
_ARCHITECTURE_DECL_RE = re.compile(
    rf"^\s*architecture\s+(?P<arch>{_NAME_RE})\s+of\s+(?P<entity>{_NAME_RE})\s+is\b",
    re.IGNORECASE | re.MULTILINE,
)
_FUNCTION_DECL_RE = re.compile(
    rf"^\s*(?:impure\s+|pure\s+)?function\s+(?P<name>{_NAME_RE})\b",
    re.IGNORECASE | re.MULTILINE,
)
_PROCEDURE_DECL_RE = re.compile(
    rf"^\s*procedure\s+(?P<name>{_NAME_RE})\b",
    re.IGNORECASE | re.MULTILINE,
)
_USE_RE = re.compile(r"^\s*use\s+(?P<body>[^;]+);", re.IGNORECASE | re.MULTILINE)
_QUALIFIED_REFERENCE_RE = re.compile(
    rf"\b(?P<prefix>{_NAME_RE})\.(?P<name>{_NAME_RE})\b",
    re.IGNORECASE,
)
_INSTANTIATION_RE = re.compile(
    rf"^\s*(?P<label>{_NAME_RE})\s*:\s*"
    rf"(?:(?:entity\s+(?:(?P<library>{_NAME_RE})\.)?)?(?P<name>{_NAME_RE})(?:\s*\([^)]+\))?)"
    r"\s+(?:generic\s+map|port\s+map)\b",
    re.IGNORECASE | re.MULTILINE,
)
_OPERATIONAL_ENTRYPOINT_RE = re.compile(
    rf"(?im)^\s*(?:entity\s+{_NAME_RE}\s+is|architecture\s+{_NAME_RE}\s+of\s+{_NAME_RE}\s+is)\b"
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "after",
        "alias",
        "all",
        "and",
        "architecture",
        "array",
        "assert",
        "attribute",
        "begin",
        "block",
        "body",
        "buffer",
        "bus",
        "case",
        "component",
        "configuration",
        "constant",
        "disconnect",
        "downto",
        "else",
        "elsif",
        "end",
        "entity",
        "exit",
        "file",
        "for",
        "function",
        "generate",
        "generic",
        "guarded",
        "if",
        "in",
        "inertial",
        "inout",
        "is",
        "label",
        "library",
        "linkage",
        "literal",
        "loop",
        "map",
        "mod",
        "nand",
        "new",
        "next",
        "nor",
        "not",
        "null",
        "of",
        "on",
        "open",
        "or",
        "others",
        "out",
        "package",
        "port",
        "procedure",
        "process",
        "range",
        "record",
        "register",
        "report",
        "return",
        "select",
        "severity",
        "signal",
        "subtype",
        "then",
        "to",
        "transport",
        "type",
        "units",
        "until",
        "use",
        "variable",
        "wait",
        "when",
        "while",
        "with",
        "xnor",
        "xor",
    }
)
_PRIMARY_SYMBOL_KINDS = frozenset({"architecture", "entity", "package", "package_body"})


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    aliases: tuple[str, ...]
    start_line: int
    end_line: int


def _normalize_name(raw_name: str) -> str:
    return str(raw_name or "").strip().lower()


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def strip_comments(text: str) -> str:
    return re.sub(r"--.*$", "", text, flags=re.MULTILINE)


def has_vhdl_path_hints(path: Path | PurePosixPath) -> bool:
    pure_path = PurePosixPath(path)
    lowered_parts = {part.lower() for part in pure_path.parts}
    return bool(lowered_parts & _PATH_HINT_PARTS)


def is_probable_vhdl_source(*, path: Path | PurePosixPath, text: str) -> bool:
    del text
    pure_path = PurePosixPath(path)
    if pure_path.suffix.lower() in _KNOWN_SUFFIXES:
        return True
    return has_vhdl_path_hints(pure_path)


def is_probable_operational_entrypoint(*, path: Path | PurePosixPath, text: str) -> bool:
    if not is_probable_vhdl_source(path=path, text=text):
        return False
    return _OPERATIONAL_ENTRYPOINT_RE.search(strip_comments(text)) is not None


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        normalized_value = _normalize_name(raw_value)
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        ordered.append(normalized_value)
    return tuple(ordered)


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[tuple[_Symbol, ...], tuple[_CollectedSymbol, ...]]:
    stripped_text = strip_comments(text)
    raw_symbols: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int, str]] = set()
    final_line = max(len(stripped_text.splitlines()), 1)
    for pattern, symbol_kind in (
        (_PACKAGE_DECL_RE, "package"),
        (_PACKAGE_BODY_RE, "package_body"),
        (_ENTITY_DECL_RE, "entity"),
        (_ARCHITECTURE_DECL_RE, "architecture"),
        (_FUNCTION_DECL_RE, "function"),
        (_PROCEDURE_DECL_RE, "procedure"),
    ):
        for match in pattern.finditer(stripped_text):
            if symbol_kind == "architecture":
                entity_name = _normalize_name(str(match.group("entity") or ""))
                architecture_name = _normalize_name(str(match.group("arch") or ""))
                symbol_name = (
                    f"{entity_name}.{architecture_name}"
                    if entity_name
                    else architecture_name
                )
                aliases = _ordered_names(
                    symbol_name,
                    architecture_name,
                    f"architecture:{symbol_name}",
                    f"architecture:{architecture_name}",
                    entity_name,
                    f"entity:{entity_name}",
                    f"work.{entity_name}",
                )
            else:
                symbol_name = _normalize_name(str(match.group("name") or ""))
                aliases = _ordered_names(
                    symbol_name,
                    f"{symbol_kind}:{symbol_name}",
                    f"work.{symbol_name}",
                )
            if not symbol_name:
                continue
            line_no = _line_number(stripped_text, match.start())
            symbol_key = (symbol_kind, line_no, symbol_name)
            if symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
            raw_symbols.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "kind": symbol_kind,
                            "line": line_no,
                            "name": symbol_name,
                        },
                    ),
                    "symbol_name": symbol_name,
                    "symbol_kind": symbol_kind,
                    "start_line": line_no,
                    "end_line": line_no,
                    "aliases": aliases,
                    "signature": symbol_name,
                    "parent_symbol_id": None,
                }
            )
    raw_symbols.sort(
        key=lambda entry: (
            int(entry["start_line"]),
            int(str(entry["symbol_kind"]) not in _PRIMARY_SYMBOL_KINDS),
        )
    )
    for index, entry in enumerate(raw_symbols):
        if index + 1 < len(raw_symbols):
            entry["end_line"] = max(
                int(raw_symbols[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    primary_symbols = [
        entry
        for entry in raw_symbols
        if str(entry["symbol_kind"]) in _PRIMARY_SYMBOL_KINDS
    ]
    for entry in raw_symbols:
        if str(entry["symbol_kind"]) in _PRIMARY_SYMBOL_KINDS:
            continue
        entry_line = int(entry["start_line"])
        parent_entry = None
        for candidate in primary_symbols:
            if int(candidate["start_line"]) <= entry_line <= int(candidate["end_line"]):
                parent_entry = candidate
        if parent_entry is None:
            for candidate in reversed(primary_symbols):
                if int(candidate["start_line"]) <= entry_line:
                    parent_entry = candidate
                    break
        if parent_entry is None:
            continue
        entry["parent_symbol_id"] = parent_entry["symbol_id"]
        qualified_aliases = list(entry["aliases"])
        qualified_prefix = _normalize_name(str(parent_entry["symbol_name"]))
        symbol_name = _normalize_name(str(entry["symbol_name"]))
        if qualified_prefix and symbol_name:
            qualified_aliases.extend(
                _ordered_names(
                    f"{qualified_prefix}.{symbol_name}",
                    f"work.{qualified_prefix}.{symbol_name}",
                )
            )
        entry["aliases"] = _ordered_names(*qualified_aliases)
    symbols = tuple(
        _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=str(entry["parent_symbol_id"])
            if entry["parent_symbol_id"] is not None
            else None,
            signature=str(entry["signature"]) if entry["signature"] is not None else None,
        )
        for entry in raw_symbols
    )
    collected_symbols = tuple(
        _CollectedSymbol(
            symbol=symbol,
            aliases=_ordered_names(*entry["aliases"]),
            start_line=symbol.start_line,
            end_line=symbol.end_line,
        )
        for symbol, entry in zip(symbols, raw_symbols, strict=False)
    )
    return symbols, collected_symbols


def _source_symbol_id_for_line(
    *,
    line_no: int,
    collected_symbols: tuple[_CollectedSymbol, ...],
) -> str | None:
    matching_symbols = [
        collected_symbol
        for collected_symbol in collected_symbols
        if collected_symbol.start_line <= line_no <= collected_symbol.end_line
        and collected_symbol.symbol.symbol_kind
        in {"architecture", "entity", "package", "package_body"}
    ]
    if not matching_symbols:
        return None
    matching_symbols.sort(
        key=lambda collected_symbol: (
            collected_symbol.start_line,
            collected_symbol.end_line - collected_symbol.start_line,
        )
    )
    return matching_symbols[-1].symbol.symbol_id
