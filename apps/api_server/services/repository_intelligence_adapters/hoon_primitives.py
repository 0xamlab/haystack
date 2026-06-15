from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

HOON_SUFFIXES = frozenset({".hoon"})
_COMMON_MODULE_ROOTS = frozenset({"app", "lib", "mar", "sur", "sys", "test", "tests"})
_COMMENT_RE = re.compile(r"(?m)::.*$")
_ARM_RE = re.compile(r"(?m)^\s*\+\+\s+(?P<name>[a-z][a-z0-9-]*)\b")
_IMPORT_LINE_RE = re.compile(r"(?m)^\s*/\+\s+(?P<imports>.+)$")
_PAREN_CALL_RE = re.compile(r"\((?P<name>[a-z][a-z0-9-]*)\b")
_CORE_CALL_RE = re.compile(r"(?m)^\s*[%!;:=|^]+[+-]?\s+(?P<name>[a-z][a-z0-9-]*)\b")
_PROBABLE_SOURCE_RE = re.compile(
    r"(?m)^\s*(?:/\+|\|%|\+\+|--$|=,|\^-|\|=|::|[%!;:][+-]?)"
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "byts",
        "det",
        "in",
        "is",
        "node",
        "out",
        "test",
        "vault",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t\f"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip(",").strip("*")


def has_hoon_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in HOON_SUFFIXES


def is_probable_hoon_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_hoon_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _PROBABLE_SOURCE_RE.search(text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.stem


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for match in _IMPORT_LINE_RE.finditer(stripped_text):
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        raw_imports = str(match.group("imports") or "")
        for raw_token in re.split(r"[,\s]+", raw_imports):
            token = normalize_identifier(raw_token)
            if not token:
                continue
            entry = (token, line_number)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append((token, "imports", line_number))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _ARM_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "arm", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("++") or line.startswith("/+"):
            continue
        for pattern in (_PAREN_CALL_RE, _CORE_CALL_RE):
            for match in pattern.finditer(line):
                name = normalize_identifier(match.group("name") or "")
                if not name or name in _RESERVED_REFERENCE_NAMES:
                    continue
                entry = (name, line_number)
                if entry in seen_entries:
                    continue
                seen_entries.add(entry)
                entries.append(entry)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in HOON_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for symbol_name, _kind, _line in iter_symbol_entries(text):
        aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "hoon"},
            ),
            symbol_name=module_name,
            symbol_kind="hoon",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"hoon {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "kind": symbol_kind,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}".strip(),
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line > line_number:
            break
        current_name = symbol_name
    return current_name
