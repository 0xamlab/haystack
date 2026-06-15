from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

THRIFT_SUFFIXES = frozenset({".thrift"})
_COMMON_MODULE_ROOTS = frozenset({"idl", "idsl", "proto", "protos", "schema", "schemas", "src", "thrift"})
_NAMESPACE_RE = re.compile(r"(?m)^\s*namespace\s+\w+\s+(?P<name>[A-Za-z_][A-Za-z0-9_.]*)")
_INCLUDE_RE = re.compile(r'(?m)^\s*include\s+"(?P<target>[^"\r\n]+)"')
_TYPE_DECL_RE = re.compile(
    r"(?m)^\s*(?P<kind>struct|service|enum|union|exception|typedef|const)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
_FIELD_TYPE_RE = re.compile(
    r"(?m)^\s*(?:\d+\s*:\s*)?(?:required|optional)?\s*(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\b"
)
_RETURN_TYPE_RE = re.compile(
    r"(?m)^\s*(?P<type>[A-Za-z_][A-Za-z0-9_.<>]*)\s+[A-Za-z_][A-Za-z0-9_]*\s*\("
)
_ARG_TYPE_RE = re.compile(
    r"(?m)(?:^|[(,])\s*(?:\d+\s*:\s*)?(?:required|optional)?\s*(?P<type>[A-Za-z_][A-Za-z0-9_.]*)\b"
)
_SOURCE_MARKER_RE = re.compile(
    r"(?m)^\s*(?:namespace\s+\w+\s+|include\s+\"|struct\s+|service\s+|enum\s+|union\s+|exception\s+|typedef\s+|const\s+)"
)
_COMMENT_LINE_RE = re.compile(r"//.*?$|#.*?$", re.MULTILINE)
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_RESERVED_TYPE_NAMES = frozenset(
    {
        "binary",
        "bool",
        "byte",
        "double",
        "i16",
        "i32",
        "i64",
        "list",
        "map",
        "set",
        "slist",
        "string",
        "uuid",
        "void",
    }
)


def _preserve_line_count(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def strip_comments(text: str) -> str:
    without_blocks = _COMMENT_BLOCK_RE.sub(_preserve_line_count, text)
    return _COMMENT_LINE_RE.sub("", without_blocks)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").lstrip(".")


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def has_thrift_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in THRIFT_SUFFIXES


def is_probable_thrift_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_thrift_path_hints(path) or not text:
        return False
    return bool(_SOURCE_MARKER_RE.search(strip_comments(text)))


def namespace_name_from_text(text: str) -> str | None:
    match = _NAMESPACE_RE.search(strip_comments(text))
    if match is None:
        return None
    name = normalize_identifier(match.group("name") or "")
    return name or None


def module_name_from_path(file_path: str, *, namespace_name: str | None = None) -> str:
    if namespace_name:
        return namespace_name
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def _normalize_import_target(raw_target: str) -> str:
    normalized_target = normalize_identifier(raw_target)
    if not normalized_target:
        return ""
    normalized_target = str(PurePosixPath(normalized_target))
    if PurePosixPath(normalized_target).suffix.lower() != ".thrift":
        normalized_target = f"{normalized_target}.thrift"
    return normalized_target


def iter_import_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (_normalize_import_target(str(match.group("target") or "")), _line_number(stripped_text, match.start()))
        for match in _INCLUDE_RE.finditer(stripped_text)
        if _normalize_import_target(str(match.group("target") or ""))
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _TYPE_DECL_RE.finditer(stripped_text):
        symbol_kind = normalize_identifier(match.group("kind") or "")
        symbol_name = normalize_identifier(match.group("name") or "")
        if not symbol_name or symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
        entries.append((symbol_name, symbol_kind, _line_number(stripped_text, match.start())))
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    local_symbol_names: set[str],
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for pattern in (_FIELD_TYPE_RE, _RETURN_TYPE_RE, _ARG_TYPE_RE):
        for match in pattern.finditer(stripped_text):
            type_name = normalize_identifier((match.group("type") or "").split("<", 1)[0])
            short_name = type_name.split(".")[-1]
            if not short_name or short_name in _RESERVED_TYPE_NAMES or short_name not in local_symbol_names:
                continue
            entry = (short_name, _line_number(stripped_text, match.start()))
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
    text: str | None = None,
) -> set[str]:
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in THRIFT_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
    }
    loaded_text = text
    if loaded_text is None:
        try:
            loaded_text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            loaded_text = ""
    namespace_name = namespace_name_from_text(loaded_text)
    aliases.add(module_name_from_path(file_path, namespace_name=namespace_name))
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    namespace_name = namespace_name_from_text(text)
    module_name = module_name_from_path(file_path, namespace_name=namespace_name)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "thrift"},
            ),
            symbol_name=module_name,
            symbol_kind="thrift",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"thrift {module_name}",
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": symbol_name, "kind": symbol_kind},
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)


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
    current_dir = PurePosixPath(current_file).parent
    raw_candidates = [normalized_target]
    if normalized_target.startswith(".") or "/" in normalized_target:
        raw_candidates.append(str(current_dir / normalized_target))
    candidate_keys: list[str] = []
    seen_candidates: set[str] = set()
    for raw_candidate in raw_candidates:
        normalized_candidate = normalize_repository_relative_path(raw_candidate)
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        candidate_keys.append(normalized_candidate)
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    basename = PurePosixPath(normalized_target).name
    return resolve_suffix_match(module_index=module_index, suffixes=[*candidate_keys, basename])


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    best_name: str | None = None
    best_line = -1
    for name, _kind, symbol_line in symbol_entries:
        if symbol_line <= line_number and symbol_line >= best_line:
            best_name = name
            best_line = symbol_line
    return best_name
