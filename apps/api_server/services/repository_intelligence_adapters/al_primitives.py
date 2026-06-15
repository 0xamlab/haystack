from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters.line_numbers import (
    line_number_for_offset,
    line_start_offsets,
)
from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

AL_SUFFIXES = frozenset({".al"})
AL_OBJECT_KINDS = frozenset(
    {
        "codeunit",
        "enum",
        "enumextension",
        "interface",
        "page",
        "pageextension",
        "permissionset",
        "permissionsetextension",
        "profile",
        "profileextension",
        "query",
        "report",
        "reportextension",
        "table",
        "tableextension",
        "xmlport",
    }
)
_OBJECT_DECL_RE = re.compile(
    r'(?mi)^\s*(?P<kind>tableextension|table|pageextension|page|reportextension|report|codeunit|enumextension|enum|query|xmlport|interface|permissionsetextension|permissionset|profileextension|profile)\s+\d+\s+(?P<name>"[^"\n]+"|[A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+(?P<extends>"[^"\n]+"|[A-Za-z_][A-Za-z0-9_]*))?'
)
_PROCEDURE_RE = re.compile(
    r"(?mi)^\s*(?:(?:local|internal|protected|public|private)\s+)*procedure\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_TRIGGER_RE = re.compile(r"(?mi)^\s*trigger\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CALL_RE = re.compile(r"(?<![.:])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(?m)//.*$")
_DECLARATION_LINE_RE = re.compile(r"(?mi)^\s*(?:trigger|(?:local|internal|protected|public|private)\s+procedure|procedure|[a-z]+extension\s+\d+|table\s+\d+|page\s+\d+|report\s+\d+|codeunit\s+\d+|enum\s+\d+|query\s+\d+|xmlport\s+\d+|interface\s+\d+|permissionset\s+\d+|profile\s+\d+)")
_AL_SOURCE_MARKER_RE = re.compile(
    r"(?mi)^\s*(?:tableextension|table|pageextension|page|reportextension|report|codeunit|enumextension|enum|query|xmlport|interface|permissionsetextension|permissionset|profileextension|profile)\s+\d+\s+|^\s*(?:local|internal|protected|public|private\s+)?procedure\s+|^\s*trigger\s+"
)
_RESERVED_CALL_NAMES = frozenset(
    {
        "action",
        "begin",
        "case",
        "codeunit",
        "else",
        "end",
        "enum",
        "error",
        "exit",
        "field",
        "filtergroup",
        "if",
        "message",
        "modify",
        "page",
        "query",
        "record",
        "repeat",
        "report",
        "reset",
        "setfilter",
        "setrange",
        "table",
        "trigger",
        "until",
        "validate",
        "while",
        "with",
        "xmlport",
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


def _strip_comments_uncached(text: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(_preserve_line_count_comment, text)
    return _LINE_COMMENT_RE.sub("", without_block_comments)


@lru_cache(maxsize=512)
def strip_comments(text: str) -> str:
    return _strip_comments_uncached(text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip()


def clean_object_name(value: str) -> str:
    return normalize_identifier(value).strip('"').strip("'").strip()


def has_al_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in AL_SUFFIXES


def is_probable_al_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in AL_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return bool(_AL_SOURCE_MARKER_RE.search(stripped_text))


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _line_number_from_index(
    text: str,
    offset: int,
    *,
    starts: tuple[int, ...] | None = None,
) -> int:
    return line_number_for_offset(text, offset, starts=starts)


def _coerce_stripped_text(text: str, stripped_text: str | None = None) -> str:
    return strip_comments(text) if stripped_text is None else stripped_text


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


def declared_object_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    entries: list[tuple[str, str, str | None, int]] = []
    for match in _OBJECT_DECL_RE.finditer(stripped_text):
        kind = normalize_identifier(match.group("kind")).lower()
        name = clean_object_name(match.group("name"))
        extends_name = clean_object_name(match.group("extends") or "") or None
        if kind not in AL_OBJECT_KINDS or not name:
            continue
        entries.append(
            (
                kind,
                name,
                extends_name,
                _line_number_from_index(stripped_text, match.start("kind"), starts=starts),
            )
        )
    return tuple(entries)


def declared_object_name_from_text(text: str) -> str | None:
    entries = declared_object_entries(text)
    return entries[0][1] if entries else None


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for kind, name, _extends_name, line_number in declared_object_entries(
        text,
        stripped_text=stripped_text,
    ):
        item = (kind, name, line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    for pattern, kind in ((_PROCEDURE_RE, "procedure"), (_TRIGGER_RE, "trigger")):
        for match in pattern.finditer(stripped_text):
            name = normalize_identifier(match.group("name"))
            if not name:
                continue
            item = (
                kind,
                name,
                _line_number_from_index(stripped_text, match.start("name"), starts=starts),
            )
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def iter_dependency_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for kind, _name, extends_name, line_number in declared_object_entries(
        text,
        stripped_text=stripped_text,
    ):
        if kind.endswith("extension") and extends_name:
            item = ("extends", extends_name, line_number)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def iter_reference_entries(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    starts = line_start_offsets(stripped_text)
    entries: list[tuple[str | None, str, int]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for match in _QUALIFIED_CALL_RE.finditer(stripped_text):
        owner = normalize_identifier(match.group("owner"))
        name = normalize_identifier(match.group("name"))
        if not owner or not name:
            continue
        item = (
            owner,
            name,
            _line_number_from_index(stripped_text, match.start("name"), starts=starts),
        )
        if item not in seen:
            seen.add(item)
            entries.append(item)
    for match in _CALL_RE.finditer(stripped_text):
        line_number = _line_number_from_index(
            stripped_text,
            match.start("name"),
            starts=starts,
        )
        line_start = stripped_text.rfind("\n", 0, match.start()) + 1
        line_end = stripped_text.find("\n", match.start())
        if line_end < 0:
            line_end = len(stripped_text)
        raw_line = stripped_text[line_start:line_end]
        name = normalize_identifier(match.group("name"))
        if (
            not name
            or name in _RESERVED_CALL_NAMES
            or _DECLARATION_LINE_RE.match(raw_line)
        ):
            continue
        item = (None, name, line_number)
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    active_name: str | None = None
    active_line = -1
    for _kind, name, symbol_line in symbol_entries:
        if symbol_line > line_number:
            break
        if symbol_line >= active_line:
            active_name = name
            active_line = symbol_line
    return active_name


def resolve_object_target(
    *,
    dependency_target: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = clean_object_name(dependency_target)
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=(normalized_target, f"/{normalized_target}.al"),
    )


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_file_path = str(PurePosixPath(file_path))
    normalized_path = PurePosixPath(normalized_file_path)
    aliases = {
        normalized_file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(normalized_file_path),
    }
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_al_source(path=normalized_path, text=text):
        return {alias for alias in aliases if alias}
    stripped_text = strip_comments(text)
    for kind, name, _extends_name, _line_number in declared_object_entries(
        text,
        stripped_text=stripped_text,
    ):
        aliases.add(name)
        aliases.add(f"{kind}:{name}")
    for _kind, _name, extends_name, _line_number in declared_object_entries(
        text,
        stripped_text=stripped_text,
    ):
        if extends_name:
            aliases.add(extends_name)
    for _kind, symbol_name, _line_number in iter_symbol_entries(
        text,
        stripped_text=stripped_text,
    ):
        aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped_text = strip_comments(text)
    object_entries = declared_object_entries(text, stripped_text=stripped_text)
    object_name = object_entries[0][1] if object_entries else module_name_from_path(file_path)
    line_count = _line_count(text)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "symbol",
            {"file_path": file_path, "symbol_name": object_name, "kind": "al"},
        ),
        symbol_name=object_name,
        symbol_kind="al",
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature=f"al {object_name}",
    )
    symbol_entries = iter_symbol_entries(text, stripped_text=stripped_text)
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
    "AL_OBJECT_KINDS",
    "AL_SUFFIXES",
    "NormalizeRepositoryRelativePath",
    "ResolveSuffixMatch",
    "StableIdentifier",
    "_CALL_RE",
    "_QUALIFIED_CALL_RE",
    "_RESERVED_CALL_NAMES",
    "clean_object_name",
    "collect_symbols",
    "declared_object_entries",
    "declared_object_name_from_text",
    "has_al_path_hints",
    "is_probable_al_source",
    "iter_dependency_entries",
    "iter_reference_entries",
    "iter_symbol_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "resolve_object_target",
    "source_symbol_name_for_line",
    "strip_comments",
]
