from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".ahk"})
_MARKER_RE = re.compile(
    r"(?im)^\s*#include(?:again)?\b|"
    r"^\s*class\s+[A-Za-z_][A-Za-z0-9_]*\b|"
    r"^\s*[A-Za-z_#@$?][A-Za-z0-9_#@$?]*\s*\([^)\n]*\)\s*\{|"
    r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*:\s*$|"
    r"::"
)
_INCLUDE_RE = re.compile(
    r"(?im)^\s*#include(?:again)?\s+(?P<target><[^>\r\n]+>|[^;\r\n]+)"
)
_CLASS_RE = re.compile(r"(?im)^\s*class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_FUNCTION_RE = re.compile(
    r"(?im)^\s*(?P<name>[A-Za-z_#@$?][A-Za-z0-9_#@$?]*)\s*\([^)\n]*\)\s*\{"
)
_LABEL_RE = re.compile(r"(?im)^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*$")
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![:#])\b(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_#@$?][A-Za-z0-9_#@$?]*)\s*\("
)
_NEW_RE = re.compile(r"(?im)\bnew\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b")
_CALL_RE = re.compile(r"(?<![.#])\b(?P<name>[A-Za-z_#@$?][A-Za-z0-9_#@$?]*)\s*\(")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "as",
        "base",
        "break",
        "case",
        "catch",
        "class",
        "continue",
        "default",
        "else",
        "extends",
        "false",
        "finally",
        "for",
        "global",
        "goto",
        "if",
        "in",
        "is",
        "local",
        "loop",
        "new",
        "not",
        "or",
        "return",
        "static",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "unset",
        "until",
        "while",
    }
)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    characters: list[str] = []
    index = 0
    in_string = False
    string_delimiter = ""
    in_block_comment = False
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        previous_character = text[index - 1] if index > 0 else "\n"
        if in_block_comment:
            if character == "*" and next_character == "/":
                in_block_comment = False
                index += 2
                continue
            if character == "\n":
                characters.append("\n")
            index += 1
            continue
        if in_string:
            characters.append(character)
            if character == string_delimiter and previous_character != "`":
                in_string = False
                string_delimiter = ""
            index += 1
            continue
        if character in {'"', "'"}:
            in_string = True
            string_delimiter = character
            characters.append(character)
            index += 1
            continue
        if character == "/" and next_character == "*":
            in_block_comment = True
            index += 2
            continue
        if character == ";" and previous_character.isspace():
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        characters.append(character)
        index += 1
    return "".join(characters)


def has_autohotkey_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_autohotkey_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_autohotkey_path_hints(normalized_path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_MARKER_RE.search(stripped_text))


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


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def module_name_from_path(path: str) -> str:
    normalized_path = PurePosixPath(path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[0].lower() == "lib":
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def _normalize_include_target(raw_target: str) -> str:
    normalized_target = normalize_identifier(raw_target)
    if not normalized_target:
        return ""
    if normalized_target.startswith("<") and normalized_target.endswith(">"):
        library_name = normalize_identifier(normalized_target[1:-1])
        if not library_name:
            return ""
        return f"Lib/{library_name}.ahk"
    normalized_target = _normalize_repository_relative_path(normalized_target)
    if not normalized_target:
        return ""
    if PurePosixPath(normalized_target).suffix.lower() != ".ahk":
        normalized_target = f"{normalized_target}.ahk"
    return normalized_target


def import_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        target = _normalize_include_target(str(match.group("target") or ""))
        if not target:
            continue
        line_number = _line_number(stripped_text, match.start())
        item = (target, line_number)
        if item in seen:
            continue
        seen.add(item)
        statements.append(item)
    return tuple(statements)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    symbol_patterns = (
        (_CLASS_RE, "type"),
        (_FUNCTION_RE, "function"),
        (_LABEL_RE, "label"),
    )
    for regex, symbol_kind in symbol_patterns:
        for match in regex.finditer(stripped_text):
            name = normalize_identifier(str(match.group("name") or ""))
            if not name:
                continue
            line_number = _line_number(stripped_text, match.start())
            item = (name, symbol_kind, line_number)
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    entries.sort(key=lambda item: item[2])
    return tuple(entries)


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    if not is_probable_autohotkey_source(path=Path(file_path), text=text):
        return ()
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
    final_line = _line_count(stripped_text)
    symbols: list[tuple[_Symbol, int]] = [
        (
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": module_name,
                        "symbol_kind": "module",
                        "start": 1,
                    },
                ),
                symbol_name=module_name,
                symbol_kind="module",
                start_line=1,
                end_line=final_line,
                parent_symbol_id=None,
                signature=f"module {module_name}",
            ),
            1,
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(stripped_text):
        symbols.append(
            (
                _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start": start_line,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=symbols[0][0].symbol_id,
                    signature=symbol_name,
                ),
                start_line,
            )
        )
    finalized: list[_Symbol] = []
    for index, (symbol, start_line) in enumerate(symbols):
        next_start = symbols[index + 1][1] if index + 1 < len(symbols) else None
        end_line = final_line if next_start is None else max(start_line, next_start - 1)
        finalized.append(
            _Symbol(
                symbol_id=symbol.symbol_id,
                symbol_name=symbol.symbol_name,
                symbol_kind=symbol.symbol_kind,
                start_line=symbol.start_line,
                end_line=end_line,
                parent_symbol_id=symbol.parent_symbol_id,
                signature=symbol.signature,
            )
        )
    return tuple(finalized)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_autohotkey_path_hints(path):
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
        path.stem,
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for symbol in collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        if symbol.symbol_kind == "module":
            continue
        aliases.add(symbol.symbol_name)
        aliases.add(f"{path.stem}.{symbol.symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_include(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_include_target(import_target)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    candidates = [
        normalize_repository_relative_path(normalized_target),
        normalize_repository_relative_path(str(current_dir / normalized_target)),
    ]
    for candidate in tuple(dict.fromkeys(path for path in candidates if path)):
        resolved = module_index.get(candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[path for path in dict.fromkeys(candidates) if path],
    )


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target, _line_number in import_statements(text):
        target_file = resolve_include(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        target_aliases = sorted(
            alias for alias, path in module_index.items() if path == target_file
        )
        stem = PurePosixPath(target_file).stem
        for alias in {stem, *target_aliases}:
            normalized_alias = normalize_identifier(alias)
            if not normalized_alias:
                continue
            bindings[normalized_alias] = _ImportedSymbolBinding(
                alias=normalized_alias,
                target_file=target_file,
                target_names=(normalized_alias,),
            )
    return bindings
