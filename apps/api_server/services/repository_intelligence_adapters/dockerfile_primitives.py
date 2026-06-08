from __future__ import annotations

import json
import re
import shlex
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

DOCKERFILE_SUFFIXES = frozenset({".dockerfile"})
DOCKERFILE_BASENAMES = frozenset({"dockerfile", "containerfile"})
_INSTRUCTION_RE = re.compile(r"^(?P<name>[A-Za-z]+)\b(?P<body>.*)$")
_INSTRUCTION_MARKER_RE = re.compile(
    r"(?im)^\s*(?:from|copy|add|run|cmd|entrypoint|workdir|env|arg|label|user|volume|shell)\b"
)
_FROM_ALIAS_RE = re.compile(r"(?i)\bas\s+(?P<alias>[A-Za-z_][A-Za-z0-9_.-]*)\s*$")
_RUN_DIRECT_PATH_RE = re.compile(r"(?<![\w./-])\./(?P<path>[A-Za-z0-9_./-]+)")
_RUN_SCRIPT_WRAPPER_RE = re.compile(
    r"(?<![\w./-])(?:bash|sh|python|python3|perl)\s+(?P<path>\.?/?[A-Za-z0-9_./-]+)"
)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        stripped_line = raw_line.lstrip()
        if stripped_line.startswith("#"):
            lines.append("")
            continue
        lines.append(raw_line)
    return "\n".join(lines)


def has_dockerfile_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in DOCKERFILE_SUFFIXES
        or normalized_path.name.lower() in DOCKERFILE_BASENAMES
    )


def is_probable_dockerfile_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_dockerfile_path_hints(path):
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and _INSTRUCTION_MARKER_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.suffix.lower() in DOCKERFILE_SUFFIXES:
        return str(path.with_suffix(""))
    return path.name if path.parent in {PurePosixPath("."), PurePosixPath("")} else str(path)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


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


def _tokenize_instruction_body(body: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(body, posix=True))
    except ValueError:
        return tuple(token for token in body.split() if token)


def _logical_instruction_lines(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    buffer: list[str] = []
    start_line = 1
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        normalized_line = raw_line.rstrip()
        if not buffer and not normalized_line.strip():
            continue
        if not buffer:
            start_line = line_number
        if normalized_line.strip():
            buffer.append(normalized_line.strip())
        if normalized_line.endswith("\\"):
            if buffer:
                buffer[-1] = buffer[-1][:-1].rstrip()
            continue
        logical_line = " ".join(segment for segment in buffer if segment).strip()
        if logical_line:
            entries.append((logical_line, start_line))
        buffer = []
    if buffer:
        logical_line = " ".join(segment for segment in buffer if segment).strip()
        if logical_line:
            entries.append((logical_line, start_line))
    return tuple(entries)


def iter_instruction_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    for logical_line, line_number in _logical_instruction_lines(text):
        match = _INSTRUCTION_RE.match(logical_line)
        if match is None:
            continue
        name = str(match.group("name") or "").strip().lower()
        body = str(match.group("body") or "").strip()
        if name and body:
            entries.append((name, body, line_number))
    return tuple(entries)


def iter_stage_entries(text: str) -> tuple[tuple[str, str, str | None, str, int], ...]:
    stages: list[tuple[str, str, str | None, str, int]] = []
    stage_index = 0
    for instruction_name, body, line_number in iter_instruction_entries(text):
        if instruction_name != "from":
            continue
        tokens = list(_tokenize_instruction_body(body))
        while tokens and tokens[0].startswith("--"):
            tokens.pop(0)
        if not tokens:
            continue
        image = tokens[0]
        alias_match = _FROM_ALIAS_RE.search(body)
        alias = str(alias_match.group("alias") or "").strip() or None if alias_match else None
        stage_key = str(stage_index)
        stage_name = alias or f"stage_{stage_key}"
        stages.append((stage_name, image, alias, stage_key, line_number))
        stage_index += 1
    return tuple(stages)


def _json_array_copy_sources(body: str) -> tuple[str, ...]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ()
    if not isinstance(payload, list) or len(payload) < 2:
        return ()
    return tuple(str(item).strip() for item in payload[:-1] if str(item).strip())


def _shell_copy_sources(body: str) -> tuple[str, str | None]:
    tokens = list(_tokenize_instruction_body(body))
    copy_from: str | None = None
    while tokens and tokens[0].startswith("--"):
        option = tokens.pop(0)
        if option.startswith("--from="):
            copy_from = option.partition("=")[2].strip() or None
        elif option == "--from" and tokens:
            copy_from = tokens.pop(0).strip() or None
    if len(tokens) < 2:
        return (), copy_from
    return tuple(str(token).strip() for token in tokens[:-1] if str(token).strip()), copy_from


def iter_copy_add_entries(text: str) -> tuple[tuple[str, str, str | None, int], ...]:
    entries: list[tuple[str, str, str | None, int]] = []
    seen: set[tuple[str, str, str | None, int]] = set()
    for instruction_name, body, line_number in iter_instruction_entries(text):
        if instruction_name not in {"copy", "add"}:
            continue
        stripped_body = body.strip()
        copy_from: str | None = None
        source_paths: tuple[str, ...]
        if stripped_body.startswith("["):
            source_paths = _json_array_copy_sources(stripped_body)
        else:
            source_paths, copy_from = _shell_copy_sources(stripped_body)
        if copy_from is None:
            match = re.search(r"(?<![\w-])--from=(?P<stage>[^\s]+)", stripped_body)
            copy_from = str(match.group("stage") or "").strip() or None if match else None
        for source_path in source_paths:
            item = (instruction_name, source_path, copy_from, line_number)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def _is_local_context_path(candidate: str) -> bool:
    normalized = str(candidate or "").strip()
    if (
        not normalized
        or normalized == "."
        or normalized.startswith(("/", "~", "http://", "https://"))
        or "$" in normalized
        or "*" in normalized
        or "?" in normalized
        or normalized.startswith("--")
    ):
        return False
    return True


def iter_run_local_path_entries(text: str) -> tuple[tuple[str, int], ...]:
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for instruction_name, body, line_number in iter_instruction_entries(text):
        if instruction_name != "run":
            continue
        for pattern in (_RUN_SCRIPT_WRAPPER_RE, _RUN_DIRECT_PATH_RE):
            for match in pattern.finditer(body):
                raw_path = str(match.group("path") or "").strip()
                normalized_path = raw_path if not raw_path.startswith("./") else raw_path[2:]
                if not _is_local_context_path(normalized_path):
                    continue
                item = (normalized_path, line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
    return tuple(entries)


def source_symbol_name_for_line(
    stage_entries: tuple[tuple[str, str, str | None, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    active_name: str | None = None
    active_line = -1
    for stage_name, _image, _alias, _stage_key, start_line in stage_entries:
        if start_line <= line_number and start_line >= active_line:
            active_name = stage_name
            active_line = start_line
    return active_name
