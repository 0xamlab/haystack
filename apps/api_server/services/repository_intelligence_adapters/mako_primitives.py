from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

MAKO_SUFFIXES = frozenset({".mako"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "components",
        "fragments",
        "includes",
        "layouts",
        "macros",
        "pages",
        "partials",
        "templates",
        "views",
    }
)
_DOC_COMMENT_RE = re.compile(r"<%doc>.*?</%doc>", re.I | re.S)
_LINE_COMMENT_RE = re.compile(r"(?m)^[ \t]*##.*?$")
_INCLUDE_RE = re.compile(r"""(?is)<%include\s+[^>]*file=["'](?P<target>[^"'<>]+)["'][^>]*/?>""")
_INHERIT_RE = re.compile(r"""(?is)<%inherit\s+[^>]*file=["'](?P<target>[^"'<>]+)["'][^>]*/?>""")
_NAMESPACE_RE = re.compile(
    r"""(?is)<%namespace\s+[^>]*name=["'](?P<alias>[A-Za-z_][A-Za-z0-9_]*)["'][^>]*file=["'](?P<target_a>[^"'<>]+)["'][^>]*/?>|<%namespace\s+[^>]*file=["'](?P<target_b>[^"'<>]+)["'][^>]*name=["'](?P<alias_b>[A-Za-z_][A-Za-z0-9_]*)["'][^>]*/?>"""
)
_DEF_RE = re.compile(r"""(?is)<%def\s+[^>]*name=["'](?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(""")
_BLOCK_RE = re.compile(r"""(?is)<%block\s+[^>]*name=["'](?P<name>[A-Za-z_][A-Za-z0-9_]*)["']""")
_EXPRESSION_RE = re.compile(r"\$\{(?P<body>.*?)\}", re.S)
_QUALIFIED_CALL_RE = re.compile(
    r"(?<![.\w])(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CALL_RE = re.compile(r"(?<![.\w])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_RESERVED_CALL_NAMES = frozenset({"context", "next", "loop", "str", "len", "min", "max"})


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _preserve_line_count(match: re.Match[str]) -> str:
    return "".join("\n" if character == "\n" else " " for character in match.group(0))


def strip_comments(text: str) -> str:
    without_doc_comments = _DOC_COMMENT_RE.sub(_preserve_line_count, text)
    return _LINE_COMMENT_RE.sub("", without_doc_comments)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


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


def has_mako_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in MAKO_SUFFIXES


def is_probable_mako_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_mako_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return any(marker in stripped_text for marker in ("${", "<%", "% if", "% for", "% endif"))


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    trim_index = 0
    for index, part in enumerate(parts):
        if part.lower() in _COMMON_MODULE_ROOTS:
            trim_index = index + 1
    trimmed_parts = parts[trim_index:]
    return ".".join(trimmed_parts) if trimmed_parts else without_suffix.name


def _normalize_import_target(value: str) -> str:
    normalized = normalize_identifier(value)
    if normalized.startswith("file:"):
        normalized = normalized[len("file:") :]
    return normalized.lstrip("/")


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, str | None, int]] = []
    seen: set[tuple[str, str, str | None, int]] = set()
    for kind, pattern in (("include", _INCLUDE_RE), ("inherit", _INHERIT_RE)):
        for match in pattern.finditer(stripped_text):
            target = _normalize_import_target(str(match.group("target") or ""))
            if not target:
                continue
            item = (kind, target, None, _line_number(stripped_text, match.start()))
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    for match in _NAMESPACE_RE.finditer(stripped_text):
        target = _normalize_import_target(
            str(match.group("target_a") or match.group("target_b") or "")
        )
        alias = normalize_identifier(str(match.group("alias") or match.group("alias_b") or ""))
        if not target or not alias:
            continue
        item = ("namespace", target, alias, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for kind, pattern in (("def", _DEF_RE), ("block", _BLOCK_RE)):
        for match in pattern.finditer(stripped_text):
            name = normalize_identifier(str(match.group("name") or ""))
            if not name:
                continue
            item = (name, kind, _line_number(stripped_text, match.start()))
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    for expression_match in _EXPRESSION_RE.finditer(stripped_text):
        body = str(expression_match.group("body") or "")
        line_number = _line_number(stripped_text, expression_match.start())
        for match in _QUALIFIED_CALL_RE.finditer(body):
            owner = normalize_identifier(str(match.group("owner") or ""))
            name = normalize_identifier(str(match.group("name") or ""))
            item = ("call", owner or None, name, line_number)
            if not owner or not name or item in seen:
                continue
            seen.add(item)
            entries.append(item)
        for match in _CALL_RE.finditer(body):
            name = normalize_identifier(str(match.group("name") or ""))
            if not name or name in _RESERVED_CALL_NAMES:
                continue
            item = ("call", None, name, line_number)
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line <= line_number:
            current_name = symbol_name
    return current_name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in MAKO_SUFFIXES:
        return set()
    normalized_path = _normalize_repository_relative_path(file_path)
    if not normalized_path:
        return set()
    aliases = {
        normalized_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_mako_source(path=path, text=text):
        return set()
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.split(".")[-1])
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
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
        if candidate_key in module_index:
            return module_index[candidate_key]
        resolved_target = resolve_suffix_match(
            module_index=module_index,
            suffixes=(candidate_key, PurePosixPath(candidate_key).name),
        )
        if resolved_target is not None:
            return resolved_target
    return None


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for dependency_kind, import_target, alias, _line_number in iter_dependency_entries(text):
        if dependency_kind != "namespace" or not alias:
            continue
        target_file = resolve_import(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        bindings.setdefault(
            alias,
            _ImportedSymbolBinding(
                alias=alias,
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
) -> tuple[Any, ...]:
    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "mako"},
            ),
            symbol_name=module_name,
            symbol_kind="mako",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"mako {module_name}",
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
