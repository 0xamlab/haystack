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

_KNOWN_SUFFIXES = frozenset({".au3"})
_MARKER_RE = re.compile(
    r"(?im)^\s*#include\b|"
    r"^\s*#autoit3wrapper_[A-Za-z0-9_]+\b|"
    r"^\s*func\s+[A-Za-z_][A-Za-z0-9_]*\s*\("
)
_INCLUDE_RE = re.compile(
    r'(?im)^\s*#include\s+(?P<target><[^>\r\n]+>|"[^"\r\n]+"|[^;\r\n]+)'
)
_FUNCTION_RE = re.compile(
    r"(?im)^\s*func\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![:#])\b(?P<owner>[A-Za-z_$][A-Za-z0-9_$]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CALL_RE = re.compile(r"(?<![.$])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "byref",
        "case",
        "const",
        "continuecase",
        "continueloop",
        "default",
        "dim",
        "do",
        "else",
        "elseif",
        "endfunc",
        "endif",
        "endselect",
        "endswitch",
        "endwith",
        "enum",
        "exit",
        "exitloop",
        "false",
        "for",
        "func",
        "global",
        "if",
        "in",
        "local",
        "next",
        "null",
        "redim",
        "return",
        "select",
        "static",
        "step",
        "switch",
        "then",
        "to",
        "true",
        "until",
        "volatile",
        "wend",
        "while",
        "with",
    }
)
_COMMENT_BLOCK_START_RE = re.compile(r"(?im)^\s*#cs\b")
_COMMENT_BLOCK_END_RE = re.compile(r"(?im)^\s*#ce\b")
_COMMON_MODULE_ROOTS = frozenset({"include", "includes", "lib", "support"})


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
    line_start = True
    while index < len(text):
        character = text[index]
        previous_character = text[index - 1] if index > 0 else "\n"
        remaining_text = text[index:]
        if in_block_comment:
            block_end_match = _COMMENT_BLOCK_END_RE.match(remaining_text)
            if block_end_match is not None:
                index += block_end_match.end()
                in_block_comment = False
                line_start = False
                continue
            if character == "\n":
                characters.append("\n")
                line_start = True
            index += 1
            continue
        if line_start:
            block_start_match = _COMMENT_BLOCK_START_RE.match(remaining_text)
            if block_start_match is not None:
                index += block_start_match.end()
                in_block_comment = True
                line_start = False
                continue
        if in_string:
            characters.append(character)
            if character == string_delimiter and previous_character != '"':
                in_string = False
                string_delimiter = ""
            if character == "\n":
                line_start = True
            else:
                line_start = False
            index += 1
            continue
        if character == '"':
            in_string = True
            string_delimiter = character
            characters.append(character)
            line_start = False
            index += 1
            continue
        if character == ";":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        characters.append(character)
        line_start = character == "\n"
        index += 1
    return "".join(characters)


def has_autoit_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_autoit_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_autoit_path_hints(normalized_path) or not text or _looks_binaryish(text):
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
    if PurePosixPath(normalized_target).suffix.lower() != ".au3":
        normalized_target = f"{normalized_target}.au3"
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
    for match in _FUNCTION_RE.finditer(stripped_text):
        name = normalize_identifier(str(match.group("name") or ""))
        if not name:
            continue
        line_number = _line_number(stripped_text, match.start())
        item = (name, "function", line_number)
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
    if not is_probable_autoit_source(path=Path(file_path), text=text):
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
    if not has_autoit_path_hints(path):
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
    prefixed_targets = [
        normalized_target,
        str(current_dir / normalized_target),
        *(
            str(PurePosixPath(prefix) / normalized_target)
            for prefix in ("Include", "Includes", "Lib", "Support", "include", "includes", "lib", "support")
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
