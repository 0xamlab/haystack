from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

ANSWER_SET_PROGRAMMING_SUFFIXES = frozenset({".lp"})
_INCLUDE_RE = re.compile(
    r'(?im)^\s*#include\s*(?:"(?P<quoted>[^"]+)"|<(?P<angled>[^>]+)>)\s*\.?\s*$'
)
_PROGRAM_RE = re.compile(r"(?im)^\s*#program\s+(?P<name>[a-z][A-Za-z0-9_]*)\b")
_CONST_RE = re.compile(r"(?im)^\s*#const\s+(?P<name>[a-z][A-Za-z0-9_]*)\b")
_EXTERNAL_RE = re.compile(r"(?im)^\s*#external\s+(?P<body>.+)$")
_SHOW_RE = re.compile(r"(?im)^\s*#show\s+(?P<body>.+)$")
_DIRECTIVE_RE = re.compile(
    r"(?im)^\s*#(?:program|show|external|const|sum|count|min|max|minimize|maximize|"
    r"heuristic|edge|project|preference|theory)\b"
)
_RULE_MARKER_RE = re.compile(r":-|:~")
_CHOICE_OR_AGGREGATE_RE = re.compile(
    r"\{[^{}]*\}|#(?:sum|count|min|max|minimize|maximize)\s*\{"
)
_PREDICATE_RE = re.compile(
    r"(?<![#$@&])\b(?P<name>[a-z][A-Za-z0-9_]*)\b"
    r"(?=\s*(?:\(|$|[,{:;=<>!+\-*/\\]))"
)
_SHOW_TARGET_RE = re.compile(
    r"(?<![#$@&])\b(?P<name>[a-z][A-Za-z0-9_]*)\b(?=\s*(?:/|\(|$|[,{:;=<>!+\-*/\\]))"
)
_RESERVED_PREDICATE_NAMES = frozenset(
    {
        "false",
        "inf",
        "maximize",
        "minimize",
        "not",
        "sup",
        "true",
    }
)


def _line_number(text: str, index: int) -> int:
    bounded_index = max(0, min(index, len(text)))
    return text.count("\n", 0, bounded_index) + 1


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
    block_depth = 0
    while index < len(text):
        next_two = text[index : index + 2]
        character = text[index]
        if block_depth > 0:
            if next_two == "%*":
                block_depth += 1
                characters.extend("  ")
                index += 2
                continue
            if next_two == "*%":
                block_depth = max(0, block_depth - 1)
                characters.extend("  ")
                index += 2
                continue
            characters.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            characters.append(character)
            if character == '"' and (index == 0 or text[index - 1] != "\\"):
                in_string = False
            index += 1
            continue
        if next_two == "%*":
            block_depth = 1
            characters.extend("  ")
            index += 2
            continue
        if character == "%":
            while index < len(text) and text[index] != "\n":
                characters.append(" ")
                index += 1
            continue
        characters.append(character)
        if character == '"':
            in_string = True
        index += 1
    return "".join(characters).lstrip("\ufeff")


def has_answer_set_programming_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in ANSWER_SET_PROGRAMMING_SUFFIXES


def is_probable_answer_set_programming_source(
    *,
    path: Path | PurePosixPath | str,
    text: str,
) -> bool:
    if not has_answer_set_programming_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    has_period_terminated_statement = any(
        stripped_text[index] == "."
        and (index == 0 or stripped_text[index - 1] != ".")
        and (index + 1 >= len(stripped_text) or stripped_text[index + 1] != ".")
        for index in range(len(stripped_text))
    )
    if not has_period_terminated_statement:
        return False
    if (
        _DIRECTIVE_RE.search(stripped_text)
        or _RULE_MARKER_RE.search(stripped_text)
        or _CHOICE_OR_AGGREGATE_RE.search(stripped_text)
    ):
        return True
    statement_predicate_count = 0
    for statement, _statement_index in _iter_statements(stripped_text):
        if _predicate_names(statement):
            statement_predicate_count += 1
        if statement_predicate_count >= 2:
            return True
    return False


def _normalize_repository_relative_path(value: str) -> str:
    normalized_parts: list[str] = []
    for part in PurePosixPath(str(value or "").replace("\\", "/")).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def module_name_from_path(file_path: str) -> str:
    return PurePosixPath(file_path).stem


def path_aliases_for_file(file_path: str) -> set[str]:
    normalized_path = PurePosixPath(file_path)
    without_suffix = str(normalized_path.with_suffix(""))
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        without_suffix,
        without_suffix.replace("/", "."),
        module_name,
    }
    return {alias for alias in aliases if alias}


def resolve_target(
    current_file: str,
    target_name: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_repository_relative_path(target_name)
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    candidates = [
        normalized_target,
        _normalize_repository_relative_path(str(current_dir / normalized_target)),
    ]
    if PurePosixPath(normalized_target).suffix.lower() not in ANSWER_SET_PROGRAMMING_SUFFIXES:
        for suffix in ANSWER_SET_PROGRAMMING_SUFFIXES:
            candidates.append(f"{normalized_target}{suffix}")
            candidates.append(
                _normalize_repository_relative_path(str(current_dir / f"{normalized_target}{suffix}"))
            )
    for candidate in dict.fromkeys(candidate for candidate in candidates if candidate):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved
    suffixes = tuple(dict.fromkeys(candidate for candidate in candidates if candidate))
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes) if suffixes else None


def _iter_statements(text: str) -> tuple[tuple[str, int], ...]:
    statements: list[tuple[str, int]] = []
    characters: list[str] = []
    statement_start = 0
    in_string = False
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    for index, character in enumerate(text):
        characters.append(character)
        if character == '"' and (index == 0 or text[index - 1] != "\\"):
            in_string = not in_string
            continue
        if in_string:
            continue
        if character == "(":
            paren_depth += 1
            continue
        if character == ")":
            paren_depth = max(0, paren_depth - 1)
            continue
        if character == "{":
            brace_depth += 1
            continue
        if character == "}":
            brace_depth = max(0, brace_depth - 1)
            continue
        if character == "[":
            bracket_depth += 1
            continue
        if character == "]":
            bracket_depth = max(0, bracket_depth - 1)
            continue
        if (
            character == "."
            and paren_depth == 0
            and brace_depth == 0
            and bracket_depth == 0
            and (index == 0 or text[index - 1] != ".")
            and (index + 1 >= len(text) or text[index + 1] != ".")
        ):
            statement = "".join(characters).strip()
            if statement:
                statements.append((statement, statement_start))
            characters = []
            statement_start = index + 1
    trailing_statement = "".join(characters).strip()
    if trailing_statement:
        statements.append((trailing_statement, statement_start))
    return tuple(statements)


def _split_top_level(value: str, delimiter: str) -> tuple[str, ...]:
    parts: list[str] = []
    current: list[str] = []
    in_string = False
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    for index, character in enumerate(value):
        if character == '"' and (index == 0 or value[index - 1] != "\\"):
            in_string = not in_string
        elif not in_string:
            if character == "(":
                paren_depth += 1
            elif character == ")":
                paren_depth = max(0, paren_depth - 1)
            elif character == "{":
                brace_depth += 1
            elif character == "}":
                brace_depth = max(0, brace_depth - 1)
            elif character == "[":
                bracket_depth += 1
            elif character == "]":
                bracket_depth = max(0, bracket_depth - 1)
            elif (
                character == delimiter
                and paren_depth == 0
                and brace_depth == 0
                and bracket_depth == 0
            ):
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                continue
        current.append(character)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return tuple(parts)


def _first_top_level_index(value: str, target: str) -> int:
    in_string = False
    paren_depth = 0
    brace_depth = 0
    bracket_depth = 0
    for index, character in enumerate(value):
        if character == '"' and (index == 0 or value[index - 1] != "\\"):
            in_string = not in_string
        elif not in_string:
            if character == "(":
                paren_depth += 1
            elif character == ")":
                paren_depth = max(0, paren_depth - 1)
            elif character == "{":
                brace_depth += 1
            elif character == "}":
                brace_depth = max(0, brace_depth - 1)
            elif character == "[":
                bracket_depth += 1
            elif character == "]":
                bracket_depth = max(0, bracket_depth - 1)
            elif (
                character == target
                and paren_depth == 0
                and brace_depth == 0
                and bracket_depth == 0
            ):
                return index
    return -1


def _predicate_names(fragment: str, *, pattern: re.Pattern[str] = _PREDICATE_RE) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            match.group("name")
            for match in pattern.finditer(fragment)
            if match.group("name").lower() not in _RESERVED_PREDICATE_NAMES
        )
    )


def _declared_predicate_names(head_fragment: str) -> tuple[str, ...]:
    normalized_head = head_fragment.strip()
    if not normalized_head:
        return ()
    choice_match = re.search(r"\{(?P<body>.*)\}", normalized_head)
    if choice_match is not None:
        declared_names: list[str] = []
        for item in _split_top_level(choice_match.group("body"), ";"):
            predicate_fragment = item.split(":", 1)[0]
            declared_names.extend(_predicate_names(predicate_fragment))
        return tuple(dict.fromkeys(declared_names))
    declared_names: list[str] = []
    for item in _split_top_level(normalized_head, "|"):
        for subitem in _split_top_level(item, ";"):
            declared_names.extend(_predicate_names(subitem.split(":", 1)[0]))
    return tuple(dict.fromkeys(declared_names))


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    for statement, statement_index in _iter_statements(stripped_text):
        match = _INCLUDE_RE.match(statement)
        if match is None:
            continue
        target_name = match.group("quoted") or match.group("angled") or ""
        if not target_name:
            continue
        entries.append(("includes", target_name, _line_number(stripped_text, statement_index)))
    return tuple(entries)


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    stripped_text = strip_comments(text)
    entries: list[dict[str, object]] = []
    seen_symbol_keys: set[tuple[str, int, str]] = set()
    for statement, statement_index in _iter_statements(stripped_text):
        line_number = _line_number(stripped_text, statement_index)
        symbol_candidates: list[tuple[str, str, str]] = []
        if program_match := _PROGRAM_RE.match(statement):
            symbol_name = program_match.group("name")
            symbol_candidates.append((symbol_name, "program", program_match.group(0).strip()))
        elif const_match := _CONST_RE.match(statement):
            symbol_name = const_match.group("name")
            symbol_candidates.append((symbol_name, "constant", const_match.group(0).strip()))
        elif external_match := _EXTERNAL_RE.match(statement):
            for symbol_name in _predicate_names(external_match.group("body")):
                symbol_candidates.append((symbol_name, "external", external_match.group(0).strip()))
        else:
            head_fragment = statement
            for rule_marker in (":-", ":~"):
                marker_index = _first_top_level_index(statement, ":")
                if marker_index >= 0 and statement[marker_index : marker_index + 2] == rule_marker:
                    head_fragment = statement[:marker_index]
                    break
            for symbol_name in _declared_predicate_names(head_fragment):
                symbol_candidates.append((symbol_name, "predicate", head_fragment.strip()))
        for symbol_name, symbol_kind, signature in symbol_candidates:
            symbol_key = (symbol_name, line_number, symbol_kind)
            if not symbol_name or symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
            entries.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_kind": symbol_kind,
                            "symbol_name": symbol_name,
                            "line": line_number,
                        },
                    ),
                    "symbol_name": symbol_name,
                    "symbol_kind": symbol_kind,
                    "start_line": line_number,
                    "end_line": line_number,
                    "signature": signature,
                }
            )
    entries.sort(key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[tuple[str, ...], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[tuple[str, ...], int]] = []
    seen_entries: set[tuple[tuple[str, ...], int]] = set()
    for statement, statement_index in _iter_statements(stripped_text):
        line_number = _line_number(stripped_text, statement_index)
        reference_names: list[str] = []
        if external_match := _EXTERNAL_RE.match(statement):
            body = external_match.group("body")
            if ":" in body:
                reference_names.extend(_predicate_names(body.split(":", 1)[1]))
        elif show_match := _SHOW_RE.match(statement):
            reference_names.extend(_predicate_names(show_match.group("body"), pattern=_SHOW_TARGET_RE))
        else:
            body_fragment = ""
            marker_index = _first_top_level_index(statement, ":")
            if marker_index >= 0 and statement[marker_index : marker_index + 2] in {":-", ":~"}:
                body_fragment = statement[marker_index + 2 :]
            if body_fragment:
                reference_names.extend(_predicate_names(body_fragment))
        for reference_name in dict.fromkeys(reference_names):
            entry = ((reference_name,), line_number)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
    return tuple(entries)
