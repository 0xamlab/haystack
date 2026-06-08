from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    prolog_primitives as repository_prolog_primitives,
)

_CALL_RE = repository_prolog_primitives._CALL_RE
_IMPORT_NAME_RE = repository_prolog_primitives._IMPORT_NAME_RE
_QUALIFIED_CALL_RE = repository_prolog_primitives._QUALIFIED_CALL_RE
_split_clauses = repository_prolog_primitives._split_clauses
_parse_clause_head = repository_prolog_primitives._parse_clause_head
normalize_identifier = repository_prolog_primitives.normalize_identifier
strip_comments = repository_prolog_primitives.strip_comments

_KNOWN_LOGTALK_SUFFIXES = (".lgt", ".logtalk")
_LOGTALK_SOURCE_ROOTS = ("source", "sources", "src", "lib", "examples", "contributions")
_ENTITY_RE = re.compile(
    r"^\s*:-\s*(?P<kind>object|protocol|category)\s*\(\s*(?P<name>[^,)]+)",
    re.IGNORECASE,
)
_VISIBILITY_RE = re.compile(
    r"^\s*:-\s*(?:public|protected|private)\s*\(\s*(?P<body>.+?)\s*\)\s*$",
    re.IGNORECASE,
)
_LOAD_RE = re.compile(
    r"^\s*:-\s*logtalk_load\s*\(\s*(?P<body>.+?)\s*\)\s*$",
    re.IGNORECASE,
)
_USES_RE = re.compile(
    r"^\s*:-\s*(?:uses|use_module)\s*\(\s*(?P<target>[^,)]+)"
    r"(?:\s*,\s*(?P<imports>\[[^\]]*\]))?",
    re.IGNORECASE,
)
_RELATION_RE = re.compile(
    r"\b(?:implements|imports|extends|instantiates|specializes|complements)\s*"
    r"\(\s*(?P<body>[^)]+)\)",
    re.IGNORECASE,
)
_MESSAGE_SEND_RE = re.compile(
    r"\b(?P<object>[a-z][A-Za-z0-9_]*)\s*::\s*(?P<name>[a-z][A-Za-z0-9_]*)\s*(?=\()"
)
_SUPER_SEND_RE = re.compile(r"\^\^\s*(?P<name>[a-z][A-Za-z0-9_]*)\s*(?=\()")


def _split_top_level_segments(raw_value: str) -> tuple[str, ...]:
    segments: list[str] = []
    current: list[str] = []
    paren_depth = 0
    bracket_depth = 0
    in_single = False
    in_double = False
    escaped = False
    for character in raw_value:
        if in_single or in_double:
            current.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif in_single and character == "'":
                in_single = False
            elif in_double and character == '"':
                in_double = False
            continue
        if character == "'":
            in_single = True
            current.append(character)
            continue
        if character == '"':
            in_double = True
            current.append(character)
            continue
        if character == "(":
            paren_depth += 1
            current.append(character)
            continue
        if character == ")":
            paren_depth = max(0, paren_depth - 1)
            current.append(character)
            continue
        if character == "[":
            bracket_depth += 1
            current.append(character)
            continue
        if character == "]":
            bracket_depth = max(0, bracket_depth - 1)
            current.append(character)
            continue
        if character == "," and paren_depth == 0 and bracket_depth == 0:
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
            continue
        current.append(character)
    segment = "".join(current).strip()
    if segment:
        segments.append(segment)
    return tuple(segments)


def _normalize_entity_name(raw_name: str) -> str:
    candidate = str(raw_name or "").strip().strip("'\"")
    if not candidate:
        return ""
    if "(" in candidate:
        candidate = candidate.split("(", 1)[0].strip()
    return normalize_identifier(candidate)


def has_logtalk_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(str(path).replace("\\", "/")).suffix.lower() in _KNOWN_LOGTALK_SUFFIXES


def has_logtalk_markers(text: str) -> bool:
    stripped_text = strip_comments(text)
    return any(
        matcher.search(stripped_text)
        for matcher in (_ENTITY_RE, _VISIBILITY_RE, _LOAD_RE, _USES_RE, _RELATION_RE)
    )


def is_probable_logtalk_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    return has_logtalk_path_hints(path) and has_logtalk_markers(text)


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    parts = list(path.with_suffix("").parts)
    if parts and parts[0].lower() in _LOGTALK_SOURCE_ROOTS:
        parts = parts[1:]
    return ".".join(part for part in parts if part)


def module_name_from_text(text: str) -> str:
    stripped_text = strip_comments(text)
    for _line_no, clause in _split_clauses(stripped_text):
        match = _ENTITY_RE.match(clause.strip())
        if match is not None:
            return _normalize_entity_name(str(match.group("name") or ""))
    return ""


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def parse_load_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _LOAD_RE.finditer(stripped_text):
        raw_body = str(match.group("body") or "").strip()
        if raw_body.startswith("[") and raw_body.endswith("]"):
            raw_targets = _split_top_level_segments(raw_body[1:-1])
        else:
            raw_targets = (raw_body.split(",", 1)[0].strip(),)
        for raw_target in raw_targets:
            normalized_target = _normalize_entity_name(raw_target)
            if not normalized_target:
                continue
            item = (normalized_target, _line_number(stripped_text, match.start()))
            if item not in seen:
                seen.add(item)
                statements.append(item)
    return tuple(statements)


def parse_uses_statements(text: str) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, tuple[str, ...], int]] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()
    for match in _USES_RE.finditer(stripped_text):
        normalized_target = _normalize_entity_name(str(match.group("target") or ""))
        if not normalized_target:
            continue
        imports = tuple(
            normalized_name
            for import_match in _IMPORT_NAME_RE.finditer(str(match.group("imports") or ""))
            if (normalized_name := normalize_identifier(str(import_match.group("name") or "")))
        )
        item = (
            normalized_target,
            imports,
            _line_number(stripped_text, match.start()),
        )
        if item not in seen:
            seen.add(item)
            statements.append(item)
    return tuple(statements)


def parse_relation_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    statements: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _RELATION_RE.finditer(stripped_text):
        for raw_target in _split_top_level_segments(str(match.group("body") or "")):
            normalized_target = _normalize_entity_name(raw_target)
            if not normalized_target:
                continue
            item = (normalized_target, _line_number(stripped_text, match.start()))
            if item not in seen:
                seen.add(item)
                statements.append(item)
    return tuple(statements)


def iter_symbol_entries(text: str, *, file_path: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    module_name = module_name_from_text(stripped_text) or module_name_from_path(file_path)
    if module_name:
        item = (module_name, "module", 1)
        seen.add(item)
        entries.append(item)
    for match in _ENTITY_RE.finditer(stripped_text):
        symbol_name = _normalize_entity_name(str(match.group("name") or ""))
        symbol_kind = normalize_identifier(str(match.group("kind") or "")) or "module"
        item = (symbol_name, symbol_kind, _line_number(stripped_text, match.start()))
        if symbol_name and item not in seen:
            seen.add(item)
            entries.append(item)
    for match in _VISIBILITY_RE.finditer(stripped_text):
        line_no = _line_number(stripped_text, match.start())
        for name_match in _IMPORT_NAME_RE.finditer(str(match.group("body") or "")):
            symbol_name = normalize_identifier(str(name_match.group("name") or ""))
            item = (symbol_name, "function", line_no)
            if symbol_name and item not in seen:
                seen.add(item)
                entries.append(item)
    for line_no, clause in _split_clauses(stripped_text):
        _declared_module, symbol_name, _signature = _parse_clause_head(clause.strip())
        item = (symbol_name, "function", line_no)
        if symbol_name and item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(sorted(entries, key=lambda item: (item[2], item[0], item[1])))


def parse_reference_targets(text: str) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    references: list[tuple[str, tuple[str, ...], int]] = []
    seen: set[tuple[str, tuple[str, ...], int]] = set()
    for match in _MESSAGE_SEND_RE.finditer(stripped_text):
        object_name = normalize_identifier(str(match.group("object") or ""))
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not object_name or not symbol_name:
            continue
        item = (
            object_name,
            (symbol_name, f"{object_name}.{symbol_name}", f"{object_name}:{symbol_name}"),
            _line_number(stripped_text, match.start()),
        )
        if item not in seen:
            seen.add(item)
            references.append(item)
    for match in _SUPER_SEND_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name:
            continue
        item = (symbol_name, (symbol_name,), _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            references.append(item)
    for match in _CALL_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name:
            continue
        item = (symbol_name, (symbol_name,), _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            references.append(item)
    return tuple(references)
