from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

SQUIRREL_SUFFIXES = frozenset({".nut"})
_COMMON_MODULE_ROOTS = frozenset(
    {"code", "lib", "libs", "samples", "scripts", "source", "src", "support", "vscripts"}
)
_MARKER_RE = re.compile(
    r"(?im)^\s*(?:::)?[A-Za-z_][A-Za-z0-9_]*\s*<-\s*(?:function|class)\b|"
    r"^\s*(?:::)?[A-Za-z_][A-Za-z0-9_]*\s*<-\s*\{|"
    r"^\s*function\s+(?:[A-Za-z_][A-Za-z0-9_]*::)?[A-Za-z_][A-Za-z0-9_]*\s*\(|"
    r"^\s*class\s+[A-Za-z_][A-Za-z0-9_.]*\b|"
    r"\b(?:IncludeScript|DoIncludeScript|dofile|require)\s*\("
)
_LINE_COMMENT_RE = re.compile(r"//.*?$", re.MULTILINE)
_INCLUDE_RE = re.compile(
    r'(?im)\b(?:IncludeScript|DoIncludeScript|dofile|require)\s*\(\s*(?P<quote>[\"\'])'
    r"(?P<target>[^\"'\r\n]+)(?P=quote)"
)
_CLASS_RE = re.compile(r"(?im)^\s*class\s+(?P<name>[A-Za-z_][A-Za-z0-9_.]*)\b")
_ASSIGNED_CLASS_RE = re.compile(
    r"(?im)^\s*(?:::)?(?P<name>[A-Za-z_][A-Za-z0-9_.]*)\s*<-\s*class\b"
)
_FUNCTION_RE = re.compile(
    r"(?im)^\s*function\s+(?P<name>[A-Za-z_][A-Za-z0-9_.:]*?)\s*\("
)
_ASSIGNED_FUNCTION_RE = re.compile(
    r"(?im)^\s*(?:::)?(?P<name>[A-Za-z_][A-Za-z0-9_.]*)\s*<-\s*function\s*\("
)
_ASSIGNMENT_RE = re.compile(
    r"(?im)^\s*(?:::)?(?P<name>[A-Za-z_][A-Za-z0-9_.]*)\s*<-\s*(?!function\b|class\b)"
)
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![:.])(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_GLOBAL_CALL_RE = re.compile(r"(?<!:)(?:::)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_CALL_RE = re.compile(r"(?<![.:])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RESERVED_SYMBOL_NAMES = frozenset(
    {
        "base",
        "break",
        "case",
        "catch",
        "class",
        "clone",
        "const",
        "constructor",
        "continue",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "extends",
        "for",
        "foreach",
        "function",
        "if",
        "in",
        "instanceof",
        "local",
        "resume",
        "return",
        "switch",
        "this",
        "throw",
        "try",
        "typeof",
        "while",
        "yield",
    }
)
_BUILTIN_REFERENCE_NAMES = frozenset(
    {
        "abs",
        "assert",
        "array",
        "clone",
        "compilestring",
        "cos",
        "delete",
        "error",
        "fabs",
        "getroottable",
        "print",
        "printl",
        "regexp",
        "seterrorhandler",
        "setroottable",
        "sin",
        "sqrt",
        "suspend",
        "table",
        "typeof",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    local_start_line: int
    local_end_line: int


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


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
        if character in {"'", '"'}:
            in_string = True
            string_delimiter = character
            characters.append(character)
            index += 1
            continue
        if character == "/" and next_character == "*":
            in_block_comment = True
            index += 2
            continue
        if character == "/" and next_character == "/":
            while index < len(text) and text[index] != "\n":
                index += 1
            continue
        characters.append(character)
        index += 1
    return "".join(characters)


def has_squirrel_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in SQUIRREL_SUFFIXES


def is_probable_squirrel_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_squirrel_path_hints(normalized_path) or not text or _looks_binaryish(text):
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


def _canonical_symbol_name(raw_name: str) -> str:
    normalized = normalize_identifier(raw_name)
    if not normalized:
        return ""
    if "::" in normalized:
        normalized = normalized.split("::")[-1]
    return normalized


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    original_parts = list(without_suffix.parts)
    trimmed_parts = list(original_parts)
    while trimmed_parts and trimmed_parts[0].lower() in _COMMON_MODULE_ROOTS:
        trimmed_parts = trimmed_parts[1:]
    if len(trimmed_parts) >= 2 and trimmed_parts[0].lower() == "scripts" and trimmed_parts[1].lower() == "vscripts":
        trimmed_parts = trimmed_parts[2:]
    if len(trimmed_parts) >= 2:
        return ".".join(trimmed_parts)
    if len(trimmed_parts) == 1 and len(original_parts) > 1:
        return ".".join(original_parts)
    return ".".join(trimmed_parts) if trimmed_parts else without_suffix.name


def _normalize_include_target(raw_target: str) -> str:
    normalized_target = normalize_identifier(raw_target)
    if not normalized_target:
        return ""
    normalized_target = _normalize_repository_relative_path(normalized_target)
    if not normalized_target:
        return ""
    if PurePosixPath(normalized_target).suffix.lower() not in SQUIRREL_SUFFIXES:
        normalized_target = f"{normalized_target}.nut"
    return normalized_target


def import_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
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


def _symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    patterns = (
        (_CLASS_RE, "class"),
        (_ASSIGNED_CLASS_RE, "class"),
        (_FUNCTION_RE, "function"),
        (_ASSIGNED_FUNCTION_RE, "function"),
        (_ASSIGNMENT_RE, "value"),
    )
    for regex, symbol_kind in patterns:
        for match in regex.finditer(stripped_text):
            symbol_name = _canonical_symbol_name(str(match.group("name") or ""))
            if (
                not symbol_name
                or symbol_name in seen_names
                or symbol_name.casefold() in _RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_names.add(symbol_name)
            entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    return _symbol_entries(text)


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped_text = strip_comments(text)
    module_name = module_name_from_path(file_path)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": module_name,
                "symbol_kind": "module",
                "start_line": 1,
            },
        ),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"module {module_name}" if module_name else None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
        )
    ]
    for symbol_name, symbol_kind, start_line in _symbol_entries(stripped_text):
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start_line": start_line,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=symbol_name,
                ),
                local_start_line=start_line,
                local_end_line=start_line,
            )
        )
    final_line = _line_count(stripped_text)
    finalized_symbols: list[_Symbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        end_line = (
            max(collected_symbols[index + 1].local_start_line - 1, collected_symbol.local_start_line)
            if index + 1 < len(collected_symbols)
            else final_line
        )
        symbol = collected_symbol.symbol
        finalized_symbols.append(
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
    return tuple(finalized_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if not has_squirrel_path_hints(path):
        return set()
    aliases = {file_path, path.name, path.stem}
    without_suffix = str(path.with_suffix(""))
    if without_suffix:
        aliases.add(without_suffix)
        aliases.add(without_suffix.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    module_name = module_name_from_path(file_path)
    if module_name:
        aliases.add(module_name)
    for symbol in collect_symbols(file_path=file_path, text=text, stable_identifier=stable_identifier):
        symbol_name = symbol.symbol_name
        if not symbol_name:
            continue
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_include(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    direct_target = _normalize_include_target(import_target)
    current_parent = PurePosixPath(current_file).parent
    raw_candidates = [
        str(current_parent / direct_target),
        direct_target,
        str(PurePosixPath("scripts") / direct_target),
        str(PurePosixPath("scripts") / "vscripts" / direct_target),
        str(PurePosixPath("vscripts") / direct_target),
        str(PurePosixPath("src") / direct_target),
    ]
    candidate_keys: list[str] = []
    for raw_candidate in raw_candidates:
        normalized_candidate = normalize_repository_relative_path(raw_candidate)
        if normalized_candidate:
            candidate_keys.append(normalized_candidate)
    for candidate_key in tuple(dict.fromkeys(candidate_keys)):
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    target_name = PurePosixPath(direct_target).stem
    suffixes = tuple(
        dict.fromkeys(
            list(candidate_keys)
            + [f"/{direct_target}", f"/{target_name}.nut"]
            + ([f"/{target_name}/init.nut"] if target_name else [])
        )
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target, _line_number_value in import_statements(text):
        target_file = resolve_include(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_name = PurePosixPath(import_target).stem
        target_names = (target_name,) if target_name else ()
        if target_name:
            bindings[target_name] = _ImportedSymbolBinding(
                alias=target_name,
                target_file=target_file,
                target_names=target_names,
            )
    return bindings


__all__ = [
    "SQUIRREL_SUFFIXES",
    "StableIdentifier",
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "_BUILTIN_REFERENCE_NAMES",
    "_CALL_RE",
    "_GLOBAL_CALL_RE",
    "_QUALIFIED_CALL_RE",
    "_RESERVED_SYMBOL_NAMES",
    "_line_count",
    "collect_symbols",
    "has_squirrel_path_hints",
    "import_statements",
    "imported_symbol_bindings",
    "is_probable_squirrel_source",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "resolve_include",
    "strip_comments",
]
