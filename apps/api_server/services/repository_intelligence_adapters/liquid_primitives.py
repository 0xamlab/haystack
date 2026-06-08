from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

LIQUID_SUFFIXES = frozenset({".liquid"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "includes",
        "layout",
        "layouts",
        "liquid",
        "partials",
        "sections",
        "snippets",
        "template",
        "templates",
        "_includes",
        "_layouts",
    }
)
_STATEMENT_RE = re.compile(r"\{%-?\s*(?P<body>.*?)\s*-?%\}", re.S)
_EXPRESSION_RE = re.compile(r"\{\{(?P<body>.*?)\}\}", re.S)
_QUOTED_TARGET_RE = re.compile(r"""['"](?P<target>[^'"]+)['"]""")
_ASSIGN_RE = re.compile(
    r"\{%-?\s*(?:assign|capture)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.S,
)
_FILTER_RE = re.compile(r"\|\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
_IDENTIFIER_RE = re.compile(r"(?<![\w.])(?P<name>[A-Za-z_][A-Za-z0-9_]*)")
_REFERENCE_EXCLUDES = frozenset(
    {
        "true",
        "false",
        "nil",
        "blank",
        "empty",
        "and",
        "or",
        "contains",
        "if",
        "elsif",
        "else",
        "unless",
        "case",
        "when",
        "endcase",
        "endif",
        "endunless",
        "for",
        "endfor",
        "tablerow",
        "endtablerow",
        "increment",
        "decrement",
        "raw",
        "endraw",
        "comment",
        "endcomment",
        "schema",
        "endschema",
        "style",
        "endstyle",
        "javascript",
        "endjavascript",
        "render",
        "include",
        "section",
        "layout",
        "capture",
        "assign",
        "cycle",
    }
)
_RESOLVER_DIRS = (
    "snippets",
    "sections",
    "layout",
    "layouts",
    "templates",
    "partials",
    "includes",
    "_includes",
    "_layouts",
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    characters = list(text)
    index = 0
    while index < len(characters):
        statement_match = _STATEMENT_RE.match(text, index)
        if not statement_match:
            index += 1
            continue
        body = str(statement_match.group("body") or "").strip().lower()
        if body != "comment":
            index = statement_match.end()
            continue
        block_end = re.compile(r"\{%-?\s*endcomment\s*-?%\}", re.S).search(
            text, statement_match.end()
        )
        end_offset = block_end.end() if block_end else len(characters)
        for replace_index in range(index, min(end_offset, len(characters))):
            if characters[replace_index] != "\n":
                characters[replace_index] = " "
        index = end_offset
    return "".join(characters)


def has_liquid_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in LIQUID_SUFFIXES


def is_probable_liquid_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in LIQUID_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return any(marker in stripped_text for marker in ("{{", "{%"))


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
    if parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _STATEMENT_RE.finditer(stripped_text):
        body = str(match.group("body") or "").strip()
        if not body:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        lowered_body = body.lower()
        kind = None
        if lowered_body.startswith("render "):
            kind = "render"
        elif lowered_body.startswith("include "):
            kind = "include"
        elif lowered_body.startswith("section "):
            kind = "section"
        elif lowered_body.startswith("layout "):
            kind = "layout"
        if kind is None:
            continue
        target_match = _QUOTED_TARGET_RE.search(body)
        if not target_match:
            continue
        target = normalize_identifier(str(target_match.group("target") or ""))
        if not target:
            continue
        item = (kind, target, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _ASSIGN_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name:
            continue
        item = (symbol_name, "binding", stripped_text.count("\n", 0, match.start()) + 1)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _EXPRESSION_RE.finditer(stripped_text):
        body = str(match.group("body") or "")
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        for pattern in (_FILTER_RE, _IDENTIFIER_RE):
            for item_match in pattern.finditer(body):
                name = normalize_identifier(str(item_match.group("name") or ""))
                if not name or name.lower() in _REFERENCE_EXCLUDES:
                    continue
                item = (name, line_number)
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
    active_name: str | None = None
    active_line = -1
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line <= line_number and start_line >= active_line:
            active_name = symbol_name
            active_line = start_line
    return active_name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in LIQUID_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_liquid_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(file_path)
    aliases.add(module_name)
    aliases.add(module_name.replace("/", "."))
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    dependency_kind: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(import_target).replace("\\", "/")
    if not normalized_target:
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if current_dir:
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    if PurePosixPath(normalized_target).suffix.lower() not in LIQUID_SUFFIXES:
        if dependency_kind == "render" or dependency_kind == "include":
            candidate_keys.extend(f"{directory}/{normalized_target}.liquid" for directory in _RESOLVER_DIRS)
        elif dependency_kind == "section":
            candidate_keys.append(f"sections/{normalized_target}.liquid")
        elif dependency_kind == "layout":
            candidate_keys.extend(
                (f"layout/{normalized_target}.liquid", f"layouts/{normalized_target}.liquid")
            )
        candidate_keys.append(f"{normalized_target}.liquid")
    normalized_candidates = [
        normalize_repository_relative_path(candidate)
        for candidate in candidate_keys
        if normalize_repository_relative_path(candidate)
    ]
    seen_candidates: set[str] = set()
    for candidate in normalized_candidates:
        if candidate in seen_candidates:
            continue
        seen_candidates.add(candidate)
        direct_match = module_index.get(candidate)
        if direct_match:
            return direct_match
        suffix_match = resolve_suffix_match(
            module_index=module_index,
            suffixes=tuple(f"/{PurePosixPath(candidate).name}" for candidate in normalized_candidates),
        )
        if suffix_match:
            return suffix_match
    return None


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    symbols: list[_Symbol] = []
    module_symbol_name = module_name_from_path(file_path)
    symbols.append(
        _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "symbol_name": module_symbol_name,
                    "symbol_kind": "liquid",
                },
            ),
            symbol_name=module_symbol_name,
            symbol_kind="liquid",
            start_line=1,
            end_line=max(1, text.count("\n") + 1),
            parent_symbol_id=None,
            signature=f"liquid {module_symbol_name}",
        )
    )
    parent_symbol_id = symbols[0].symbol_id
    seen_symbol_names = {module_symbol_name}
    for symbol_name, symbol_kind, _line_number in iter_symbol_entries(text):
        if symbol_name in seen_symbol_names:
            continue
        seen_symbol_names.add(symbol_name)
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=1,
                end_line=max(1, text.count("\n") + 1),
                parent_symbol_id=parent_symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)
