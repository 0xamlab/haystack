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

STAN_SUFFIXES = frozenset({".stan"})
_COMMON_MODULE_ROOTS = frozenset(
    {"example", "examples", "include", "includes", "lib", "libs", "model", "models", "src"}
)
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:functions|data|transformed\s+data|parameters|transformed\s+parameters|model|generated\s+quantities)\s*\{"  # noqa: E501
)
_INCLUDE_RE = re.compile(
    r'(?im)^\s*#include\s+(?P<target>"[^"\r\n]+"|<[^>\r\n]+>)'
)
# NOTE: inner char class deliberately omits \s so it cannot overlap with the
# required '\s+' separator between qualifiers - prevents py/redos exponential
# backtracking on inputs like '\tA\tA\tA...'.
_FUNCTION_HEAD_RE = re.compile(
    r"(?m)^\s*(?:[A-Za-z_][A-Za-z0-9_\[\],<>]*\s+)+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*\{"
)
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![:.])\b(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CALL_RE = re.compile(r"(?<![.:])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "array",
        "break",
        "continue",
        "data",
        "else",
        "for",
        "functions",
        "generated_quantities",
        "generated",
        "if",
        "in",
        "int",
        "matrix",
        "model",
        "parameters",
        "print",
        "real",
        "reject",
        "return",
        "row_vector",
        "target",
        "transformed",
        "vector",
        "void",
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
        previous_character = text[index - 1] if index > 0 else ""
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
            if character == string_delimiter and previous_character != "\\":
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
        if character == "/" and next_character == "/":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        if character == "/" and next_character == "*":
            in_block_comment = True
            index += 2
            continue
        characters.append(character)
        index += 1
    return "".join(characters)


def _prepared_stan_source_text(*, path: Path | PurePosixPath, text: str) -> str | None:
    normalized_path = PurePosixPath(path)
    if not has_stan_path_hints(normalized_path) or not text or _looks_binaryish(text):
        return None
    stripped_text = strip_comments(text)
    if not stripped_text.strip() or not _MARKER_RE.search(stripped_text):
        return None
    return stripped_text


def has_stan_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in STAN_SUFFIXES


def is_probable_stan_source(*, path: Path | PurePosixPath, text: str) -> bool:
    return _prepared_stan_source_text(path=path, text=text) is not None


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


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


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def _normalize_include_target(raw_target: str) -> str:
    normalized_target = normalize_identifier(raw_target)
    if not normalized_target:
        return ""
    if normalized_target.startswith("<") and normalized_target.endswith(">"):
        normalized_target = normalize_identifier(normalized_target[1:-1])
    normalized_target = _normalize_repository_relative_path(normalized_target)
    if not normalized_target:
        return ""
    if PurePosixPath(normalized_target).suffix.lower() != ".stan":
        normalized_target = f"{normalized_target}.stan"
    return normalized_target


def _include_statements_from_stripped_text(stripped_text: str) -> tuple[tuple[str, int], ...]:
    statements: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        target = _normalize_include_target(str(match.group("target") or ""))
        if not target:
            continue
        item = (target, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        statements.append(item)
    return tuple(statements)


def include_statements(text: str) -> tuple[tuple[str, int], ...]:
    return _include_statements_from_stripped_text(strip_comments(text))


def _iter_block_ranges(text: str, block_name: str) -> tuple[tuple[int, int], ...]:
    lowered_text = text.lower()
    marker = block_name.lower()
    ranges: list[tuple[int, int]] = []
    index = 0
    while True:
        match = re.search(rf"(?im)^\s*{re.escape(marker)}\s*\{{", text[index:])
        if match is None:
            break
        block_start = index + match.start()
        open_brace = text.find("{", block_start)
        if open_brace < 0:
            break
        depth = 1
        cursor = open_brace + 1
        in_string = False
        string_delimiter = ""
        while cursor < len(text) and depth > 0:
            character = text[cursor]
            previous_character = text[cursor - 1] if cursor > 0 else ""
            if in_string:
                if character == string_delimiter and previous_character != "\\":
                    in_string = False
                    string_delimiter = ""
                cursor += 1
                continue
            if character in {'"', "'"}:
                in_string = True
                string_delimiter = character
                cursor += 1
                continue
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
            cursor += 1
        if depth == 0:
            ranges.append((open_brace + 1, max(open_brace + 1, cursor - 1)))
        index = max(cursor, block_start + 1)
        if index >= len(lowered_text):
            break
    return tuple(ranges)


def _iter_symbol_entries_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for block_start, block_end in _iter_block_ranges(stripped_text, "functions"):
        block_text = stripped_text[block_start:block_end]
        for match in _FUNCTION_HEAD_RE.finditer(block_text):
            symbol_name = normalize_identifier(str(match.group("name") or ""))
            if (
                not symbol_name
                or symbol_name in seen_names
                or symbol_name.casefold() in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append(
                (
                    symbol_name,
                    "function",
                    _line_number(stripped_text, block_start + match.start()),
                )
            )
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    return _iter_symbol_entries_from_stripped_text(strip_comments(text))


def _collect_symbols_from_stripped_text(
    *,
    file_path: str,
    stripped_text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
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
    for symbol_name, symbol_kind, start_line in _iter_symbol_entries_from_stripped_text(
        stripped_text
    ):
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


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped_text = _prepared_stan_source_text(path=Path(file_path), text=text)
    if stripped_text is None:
        return ()
    return _collect_symbols_from_stripped_text(
        file_path=file_path,
        stripped_text=stripped_text,
        stable_identifier=stable_identifier,
    )


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_stan_path_hints(path):
        return set()
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        module_name,
        path.stem,
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    stripped_text = _prepared_stan_source_text(path=path, text=text)
    symbols = (
        _collect_symbols_from_stripped_text(
            file_path=file_path,
            stripped_text=stripped_text,
            stable_identifier=stable_identifier,
        )
        if stripped_text is not None
        else ()
    )
    for symbol in symbols:
        if symbol.symbol_kind == "module":
            continue
        aliases.add(symbol.symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol.symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_include(
    *,
    current_file: str,
    include_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_include_target(include_target)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    prefixed_targets = [
        normalized_target,
        str(current_dir / normalized_target),
        *(
            str(PurePosixPath(prefix) / normalized_target)
            for prefix in (
                "include",
                "includes",
                "lib",
                "libs",
                "model",
                "models",
                "src",
            )
        ),
    ]
    candidates = [
        normalize_repository_relative_path(candidate)
        for candidate in prefixed_targets
        if candidate
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
    include_entries = _include_statements_from_stripped_text(strip_comments(text))
    return _imported_symbol_bindings_from_include_statements(
        current_file=current_file,
        include_entries=include_entries,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )


def _imported_symbol_bindings_from_include_statements(
    *,
    current_file: str,
    include_entries: tuple[tuple[str, int], ...],
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for include_target, _line_number_value in include_entries:
        target_file = resolve_include(
            current_file=current_file,
            include_target=include_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        target_aliases = sorted(alias for alias, path in module_index.items() if path == target_file)
        target_names = tuple(
            alias
            for alias in target_aliases
            if alias
            and "." not in alias
            and "/" not in alias
            and PurePosixPath(alias).suffix.lower() not in STAN_SUFFIXES
        )
        stem = PurePosixPath(target_file).stem
        for alias in {stem, *target_names}:
            normalized_alias = normalize_identifier(alias)
            if not normalized_alias:
                continue
            bindings[normalized_alias] = _ImportedSymbolBinding(
                alias=normalized_alias,
                target_file=target_file,
                target_names=(normalized_alias,),
            )
    return bindings


__all__ = [
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "STAN_SUFFIXES",
    "StableIdentifier",
    "_CALL_RE",
    "_QUALIFIED_CALL_RE",
    "_RESERVED_SYMBOL_NAMES",
    "collect_symbols",
    "has_stan_path_hints",
    "imported_symbol_bindings",
    "include_statements",
    "is_probable_stan_source",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "resolve_include",
    "strip_comments",
]
