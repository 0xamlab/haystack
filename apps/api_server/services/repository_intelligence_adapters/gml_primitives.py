from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".gml"})
_TEST_PATH_PARTS = frozenset({"spec", "specs", "test", "tests"})
_TRAILING_COMMA_RE = re.compile(r",(?=\s*[}\]])")


def _normalize_name(raw_value: Any) -> str:
    return str(raw_value or "").strip()


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        normalized = _normalize_name(raw_value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def strip_comments(text: str) -> str:
    output: list[str] = []
    index = 0
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    escape = False
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                output.append(char)
            index += 1
            continue
        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
                continue
            if char == "\n":
                output.append(char)
            index += 1
            continue
        if escape:
            output.append(char)
            escape = False
            index += 1
            continue
        if char == "\\" and (in_single_quote or in_double_quote):
            output.append(char)
            escape = True
            index += 1
            continue
        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            output.append(char)
            index += 1
            continue
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            output.append(char)
            index += 1
            continue
        if not in_single_quote and not in_double_quote and char == "/" and next_char == "/":
            in_line_comment = True
            index += 2
            continue
        if not in_single_quote and not in_double_quote and char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue
        output.append(char)
        index += 1
    return "".join(output)


def load_game_maker_json(text: str) -> Any | None:
    candidate = str(text or "").strip()
    if not candidate:
        return None
    for _ in range(4):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            normalized = _TRAILING_COMMA_RE.sub("", candidate)
            if normalized == candidate:
                return None
            candidate = normalized
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def has_gml_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_gml_source(*, path: Path | PurePosixPath, text: str) -> bool:
    del text
    return has_gml_path_hints(path)


def is_probable_operational_entrypoint(*, path: Path | PurePosixPath, text: str) -> bool:
    del text
    candidate_path = PurePosixPath(path)
    if candidate_path.suffix.lower() not in _KNOWN_SUFFIXES:
        return False
    basename = candidate_path.name.lower()
    if basename.startswith("test_") or basename.endswith("_test.gml"):
        return False
    if {part.lower() for part in candidate_path.parts} & _TEST_PATH_PARTS:
        return False
    return True


def script_resource_name(file_path: str) -> str:
    path = PurePosixPath(file_path)
    lowered_parts = [part.lower() for part in path.parts]
    if "scripts" in lowered_parts:
        script_index = lowered_parts.index("scripts")
        if script_index + 1 < len(path.parts):
            return _normalize_name(path.parts[script_index + 1]) or path.stem
    return ""


def object_resource_name(file_path: str) -> str:
    path = PurePosixPath(file_path)
    lowered_parts = [part.lower() for part in path.parts]
    if "objects" in lowered_parts:
        object_index = lowered_parts.index("objects")
        if object_index + 1 < len(path.parts):
            return _normalize_name(path.parts[object_index + 1])
    return ""


def event_symbol_name(file_path: str) -> str:
    object_name = object_resource_name(file_path)
    if not object_name:
        return ""
    event_name = PurePosixPath(file_path).stem
    return _normalize_name(f"{object_name}.{event_name}")


def module_symbol_name(file_path: str) -> str:
    script_name = script_resource_name(file_path)
    if script_name:
        return script_name
    object_event_name = event_symbol_name(file_path)
    if object_event_name:
        return object_event_name
    return PurePosixPath(file_path).stem
