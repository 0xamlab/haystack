from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)
from apps.api_server.services.repository_intelligence_adapters.line_numbers import (
    line_number_for_offset,
    line_start_offsets,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

TYPST_SUFFIXES = frozenset({".typ"})
TYPST_CONFIG_BASENAMES = frozenset({"typst.toml"})
_COMMON_MODULE_ROOTS = frozenset(
    {"book", "chapters", "content", "docs", "document", "documents", "examples", "notes", "pages", "paper", "papers", "presentation", "presentations", "report", "reports", "slides", "src", "template", "templates", "thesis"}  # noqa: E501
)
_LET_RE = re.compile(
    r"(?m)^\s*#let\s+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*(?:\([^)]*\))?\s*="
)
_INCLUDE_RE = re.compile(r'(?m)#include\s+(?P<target>"[^"\r\n]+")')
_IMPORT_RE = re.compile(
    r'(?m)#import\s+(?P<target>"[^"\r\n]+"|@[^\s:]+)\s*(?::\s*(?P<selectors>[^\n]+?))?(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_-]*))?\s*(?=$|\n)'  # noqa: E501
)
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![#\w-])(?P<owner>[A-Za-z_][A-Za-z0-9_-]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\("
)
_CALL_RE = re.compile(r"(?<![#.\w-])(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\s*\(")
_DECLARATION_LINE_RE = re.compile(r"(?m)^\s*#let\b")
_CONFIG_MARKER_RE = re.compile(
    r"(?m)^\s*(?:\[package(?:\.[^\]]+)?\]|\[template(?:\.[^\]]+)?\]|entrypoint\s*=)"
)
_RESERVED_CALL_NAMES = frozenset()


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _line_number(
    text: str,
    offset: int,
    *,
    starts: tuple[int, ...] | None = None,
) -> int:
    return line_number_for_offset(text, offset, starts=starts)


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


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _coerce_stripped_text(text: str, stripped_text: str | None = None) -> str:
    return strip_comments(text) if stripped_text is None else stripped_text


@lru_cache(maxsize=512)
def strip_comments(text: str) -> str:
    return _strip_comments_uncached(text)


def _strip_comments_uncached(text: str) -> str:
    if "//" not in text and "/*" not in text:
        return text
    characters: list[str] = []
    index = 0
    in_string = False
    string_delimiter = ""
    in_block_comment_depth = 0
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        previous_character = text[index - 1] if index > 0 else ""
        if in_block_comment_depth > 0:
            if character == "/" and next_character == "*":
                in_block_comment_depth += 1
                index += 2
                continue
            if character == "*" and next_character == "/":
                in_block_comment_depth -= 1
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
            in_block_comment_depth += 1
            index += 2
            continue
        characters.append(character)
        index += 1
    return "".join(characters)


def has_typst_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in TYPST_SUFFIXES
        or normalized_path.name.lower() in TYPST_CONFIG_BASENAMES
    )


def is_probable_typst_source(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in TYPST_SUFFIXES or not text or _looks_binaryish(text):
        return False
    return bool(_coerce_stripped_text(text, stripped_text).strip())


def is_probable_typst_config(
    *,
    path: Path | PurePosixPath,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.name.lower() not in TYPST_CONFIG_BASENAMES or not text:
        return False
    stripped_text = _coerce_stripped_text(text, stripped_text)
    return bool(stripped_text.strip()) and bool(_CONFIG_MARKER_RE.search(stripped_text))


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


def _normalize_import_target(raw_target: str) -> str:
    normalized_target = normalize_identifier(raw_target)
    if not normalized_target or normalized_target.startswith("@"):
        return ""
    normalized_target = _normalize_repository_relative_path(normalized_target)
    if not normalized_target:
        return ""
    if PurePosixPath(normalized_target).suffix.lower() != ".typ":
        normalized_target = f"{normalized_target}.typ"
    return normalized_target


def _selector_aliases(raw_selectors: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    selectors = str(raw_selectors or "").strip()
    if not selectors:
        return ()
    entries: list[tuple[str, tuple[str, ...]]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for raw_selector in selectors.split(","):
        selector = str(raw_selector or "").strip()
        if not selector or selector == "*":
            continue
        base_selector, _, alias_tail = selector.partition(" as ")
        symbol_name = normalize_identifier(base_selector)
        alias_name = normalize_identifier(alias_tail)
        if not symbol_name:
            continue
        item = (symbol_name, _ordered_names(alias_name, symbol_name))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_import_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    entries: list[tuple[str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int]] = []
    seen: set[tuple[str, tuple[tuple[str, tuple[str, ...]], ...], str | None, int]] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        target = _normalize_import_target(str(match.group("target") or ""))
        if not target:
            continue
        selectors = _selector_aliases(str(match.group("selectors") or ""))
        alias = normalize_identifier(str(match.group("alias") or "")) or None
        item = (target, selectors, alias, _line_number(stripped_text, match.start(), starts=starts))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def include_statements(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    statements: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _INCLUDE_RE.finditer(stripped_text):
        target = _normalize_import_target(str(match.group("target") or ""))
        if not target:
            continue
        item = (target, _line_number(stripped_text, match.start(), starts=starts))
        if item in seen:
            continue
        seen.add(item)
        statements.append(item)
    return tuple(statements)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _LET_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name:
            continue
        item = (symbol_name, "binding", _line_number(stripped_text, match.start(), starts=starts))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str | None, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    for pattern, owner_key in ((_QUALIFIED_CALL_RE, "owner"), (_CALL_RE, None)):
        for match in pattern.finditer(stripped_text):
            line_number = _line_number(stripped_text, match.start(), starts=starts)
            line_start = stripped_text.rfind("\n", 0, match.start()) + 1
            line_end = stripped_text.find("\n", match.start())
            if line_end < 0:
                line_end = len(stripped_text)
            raw_line = stripped_text[line_start:line_end]
            if _DECLARATION_LINE_RE.match(raw_line):
                continue
            owner = (
                normalize_identifier(str(match.group(owner_key) or "")) if owner_key else None
            )
            name = normalize_identifier(str(match.group("name") or ""))
            if not name or name in _RESERVED_CALL_NAMES:
                continue
            item = ("call", owner or None, name, line_number)
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    stripped_text: str | None = None,
    symbol_entries: tuple[tuple[str, str, int], ...] | None = None,
    include_symbol_aliases: bool = True,
    validated_source: bool = False,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in TYPST_SUFFIXES:
        return set()
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        module_name,
        module_name.replace("/", "."),
    }
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    loaded_text = text
    if loaded_text is None:
        try:
            loaded_text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            loaded_text = ""
    candidate_stripped_text = _coerce_stripped_text(loaded_text, stripped_text)
    if loaded_text and not validated_source and not is_probable_typst_source(
        path=path,
        text=loaded_text,
        stripped_text=candidate_stripped_text,
    ):
        return {alias for alias in aliases if alias}
    resolved_symbol_entries = symbol_entries
    if resolved_symbol_entries is None:
        resolved_symbol_entries = iter_symbol_entries(
            loaded_text,
            stripped_text=candidate_stripped_text,
        )
    for symbol_name, _symbol_kind, _line_number in resolved_symbol_entries:
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if current_dir:
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(f"/{PurePosixPath(candidate).name}" for candidate in candidate_keys),
    )


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for import_target, selectors, alias, _line_number in iter_import_entries(
        text,
        stripped_text=stripped_text,
    ):
        target_file = resolve_import(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        module_name = module_name_from_path(target_file)
        module_aliases = _ordered_names(
            alias or "",
            PurePosixPath(target_file).stem,
            module_name,
            module_name.split(".")[-1] if module_name else "",
        )
        if selectors:
            for symbol_name, alias_names in selectors:
                for alias_name in alias_names:
                    bindings.setdefault(
                        alias_name,
                        _ImportedSymbolBinding(
                            alias=alias_name,
                            target_file=target_file,
                            target_names=(symbol_name,),
                        ),
                    )
            continue
        for alias_name in module_aliases:
            bindings.setdefault(
                alias_name,
                _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=(),
                ),
            )
    return bindings


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
    symbol_entries: tuple[tuple[str, str, int], ...] | None = None,
) -> tuple[_Symbol, ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    module_name = module_name_from_path(file_path) or PurePosixPath(file_path).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "typst"},
        ),
        symbol_name=module_name,
        symbol_kind="typst",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"typst {module_name}",
    )
    symbols: list[_Symbol] = [module_symbol]
    resolved_symbol_entries = symbol_entries
    if resolved_symbol_entries is None:
        resolved_symbol_entries = iter_symbol_entries(
            text,
            stripped_text=stripped_text,
        )
    for symbol_name, symbol_kind, line_number in resolved_symbol_entries:
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "line": line_number,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol.symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    active_name: str | None = None
    active_line = -1
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line <= line_number and start_line >= active_line:
            active_name = symbol_name
            active_line = start_line
    return active_name
