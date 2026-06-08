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

MOVE_SUFFIXES = frozenset({".move"})
MOVE_CONFIG_BASENAMES = frozenset({"move.toml"})
MOVE_INDEX_BASENAMES = frozenset({"main.move", "lib.move", "script.move"})
_COMMON_MODULE_ROOTS = frozenset(
    {"contracts", "examples", "move", "package", "packages", "script", "scripts", "source", "sources"}
)
_MODULE_DECL_RE = re.compile(
    r"(?m)^\s*module\s+(?P<name>[A-Za-z0-9_:@]+(?:::[A-Za-z_][A-Za-z0-9_]*)+)\s*\{"
)
_SCRIPT_DECL_RE = re.compile(r"(?m)^\s*script\s*\{")
_USE_RE = re.compile(
    r"(?m)^\s*use\s+(?P<target>[A-Za-z0-9_:@]+(?:::[A-Za-z_][A-Za-z0-9_]*)+)"
    r"(?P<imports>\s*::\s*\{[^}]*\})?\s*;"
)
_FRIEND_RE = re.compile(
    r"(?m)^\s*friend\s+(?P<target>[A-Za-z0-9_:@]+(?:::[A-Za-z_][A-Za-z0-9_]*)+)\s*;"
)
_STRUCT_RE = re.compile(
    r"(?m)^\s*(?:(?:public|friend|package)(?:\([^)]*\))?\s+)*(?:native\s+)?(?:resource\s+)?struct\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_FUN_RE = re.compile(
    r"(?m)^\s*(?:(?:public|friend|package)(?:\([^)]*\))?\s+)*(?:entry\s+)?(?:native\s+)?fun\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CONST_RE = re.compile(r"(?m)^\s*const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:")
_QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<owner>[A-Za-z_][A-Za-z0-9_]*)::(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CALL_RE = re.compile(r"(?<![:.])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(?m)//.*$")
_MOVE_CONFIG_MARKER_RE = re.compile(r"(?im)^\s*\[(?:package|addresses|dependencies)\]\s*$")
_MOVE_SOURCE_MARKER_RE = re.compile(
    r"(?im)^\s*(?:module|script)\b|\b(?:fun|struct|use|friend)\b"
)
_RESERVED_CALL_NAMES = frozenset(
    {
        "assert",
        "borrow_global",
        "borrow_global_mut",
        "copy",
        "exists",
        "freeze",
        "if",
        "loop",
        "move_from",
        "move_to",
        "return",
        "vector",
        "while",
    }
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _preserve_line_count_comment(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def strip_comments(text: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(_preserve_line_count_comment, text)
    return _LINE_COMMENT_RE.sub("", without_block_comments)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def has_move_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in MOVE_SUFFIXES
        or normalized_path.name.lower() in MOVE_CONFIG_BASENAMES
    )


def declared_module_name_from_text(text: str) -> str | None:
    match = _MODULE_DECL_RE.search(strip_comments(text))
    if match is None:
        return None
    return normalize_identifier(match.group("name"))


def is_probable_move_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() not in MOVE_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_MOVE_SOURCE_MARKER_RE.search(stripped_text))


def is_probable_move_config(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).name.lower() not in MOVE_CONFIG_BASENAMES or not text:
        return False
    stripped_text = strip_comments(text)
    return bool(_MOVE_CONFIG_MARKER_RE.search(stripped_text) or 'name = "' in stripped_text)


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    if parts and parts[-1].lower() in {"main", "lib"}:
        parts = parts[:-1]
    return "::".join(parts) if parts else without_suffix.stem


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_identifier(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _parse_use_import_items(raw_imports: str) -> tuple[str, ...]:
    normalized_imports = normalize_identifier(raw_imports)
    if not normalized_imports:
        return ()
    normalized_imports = normalized_imports.removeprefix("::").strip()
    if not (normalized_imports.startswith("{") and normalized_imports.endswith("}")):
        return ()
    return tuple(
        item
        for item in (
            normalize_identifier(candidate)
            for candidate in normalized_imports[1:-1].split(",")
        )
        if item
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    if declared_module_name := declared_module_name_from_text(stripped_text):
        module_line = stripped_text.count("\n", 0, stripped_text.find(declared_module_name)) + 1
        entries.append(("module", declared_module_name, module_line))
    elif _SCRIPT_DECL_RE.search(stripped_text):
        entries.append(("script", "script", 1))
    for pattern, kind in ((_STRUCT_RE, "struct"), (_FUN_RE, "function"), (_CONST_RE, "const")):
        for match in pattern.finditer(stripped_text):
            symbol_name = normalize_identifier(match.group("name"))
            if not symbol_name:
                continue
            line_number = stripped_text.count("\n", 0, match.start()) + 1
            entries.append((kind, symbol_name, line_number))
    entries.sort(key=lambda entry: (entry[2], entry[0], entry[1]))
    return tuple(entries)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, tuple[str, ...], int]] = []
    for match in _USE_RE.finditer(stripped_text):
        target = normalize_identifier(match.group("target"))
        if not target:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        entries.append(
            ("use", target, _parse_use_import_items(str(match.group("imports") or "")), line_number)
        )
    for match in _FRIEND_RE.finditer(stripped_text):
        target = normalize_identifier(match.group("target"))
        if not target:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        entries.append(("friend", target, (), line_number))
    return tuple(entries)


def resolve_module_target(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return None
    if normalized_target in module_index:
        return module_index[normalized_target]
    leaf_name = normalized_target.rsplit("::", 1)[-1]
    current_parent = PurePosixPath(current_file).parent
    local_candidate = normalize_repository_relative_path(str(current_parent / f"{leaf_name}.move"))
    if local_candidate and local_candidate in module_index.values():
        return local_candidate
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=(normalized_target, leaf_name, f"{leaf_name}.move", local_candidate),
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
    for dependency_kind, import_target, imported_items, _line_number in iter_dependency_entries(text):
        if dependency_kind != "use":
            continue
        target_file = resolve_module_target(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        module_leaf = import_target.rsplit("::", 1)[-1]
        aliases = imported_items or (module_leaf,)
        for alias in aliases:
            normalized_alias = module_leaf if alias.lower() == "self" else normalize_identifier(alias)
            if not normalized_alias or normalized_alias in bindings:
                continue
            target_names = () if normalized_alias == module_leaf else (normalized_alias,)
            bindings[normalized_alias] = _ImportedSymbolBinding(
                alias=normalized_alias,
                target_file=target_file,
                target_names=target_names,
            )
    return bindings


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_file_path = str(PurePosixPath(file_path))
    aliases = {
        normalized_file_path,
        PurePosixPath(normalized_file_path).stem,
        module_name_from_path(normalized_file_path),
    }
    resolved_path = root_path / normalized_file_path
    try:
        if resolved_path.is_file():
            text = resolved_path.read_text(encoding="utf-8", errors="replace")
            declared_module_name = declared_module_name_from_text(text)
            if declared_module_name:
                aliases.add(declared_module_name)
                aliases.add(declared_module_name.rsplit("::", 1)[-1])
    except OSError:
        pass
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped_text = strip_comments(text)
    module_name = (
        declared_module_name_from_text(stripped_text)
        or ("script" if _SCRIPT_DECL_RE.search(stripped_text) else module_name_from_path(file_path))
    )
    line_count = _line_count(text)
    module_kind = "move_script" if module_name == "script" else "move_module"
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "symbol",
            {"file_path": file_path, "symbol_name": module_name, "kind": module_kind},
        ),
        symbol_name=module_name,
        symbol_kind=module_kind,
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature=module_kind.replace("_", " "),
    )
    symbol_entries = [entry for entry in iter_symbol_entries(text) if entry[0] not in {"module", "script"}]
    symbols: list[_Symbol] = [module_symbol]
    for index, (symbol_kind, symbol_name, start_line) in enumerate(symbol_entries):
        end_line = symbol_entries[index + 1][2] - 1 if index + 1 < len(symbol_entries) else line_count
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
                start_line=start_line,
                end_line=max(start_line, end_line),
                parent_symbol_id=module_symbol.symbol_id,
                signature=_ordered_names(symbol_kind, symbol_name)[0],
            )
        )
    return tuple(symbols)


__all__ = [
    "MOVE_CONFIG_BASENAMES",
    "MOVE_INDEX_BASENAMES",
    "MOVE_SUFFIXES",
    "_CALL_RE",
    "_QUALIFIED_CALL_RE",
    "_RESERVED_CALL_NAMES",
    "StableIdentifier",
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "collect_symbols",
    "declared_module_name_from_text",
    "has_move_path_hints",
    "imported_symbol_bindings",
    "is_probable_move_config",
    "is_probable_move_source",
    "iter_dependency_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "resolve_module_target",
    "strip_comments",
]
