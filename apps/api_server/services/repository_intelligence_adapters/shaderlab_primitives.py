from __future__ import annotations

import bisect
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    hlsl_primitives as repository_hlsl_primitives,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

SHADERLAB_SOURCE_SUFFIXES = frozenset({".shader"})
SHADERLAB_MARKER_RE = re.compile(
    r'(?im)^\s*Shader\s+"[^"]+"|^\s*SubShader\b|^\s*Pass\b|^\s*(?:CG|HLSL)(?:PROGRAM|INCLUDE)\b'
)
SHADERLAB_SHADER_RE = re.compile(r'(?im)^\s*Shader\s+"(?P<name>[^"]+)"')
SHADERLAB_USEPASS_RE = re.compile(r'(?im)^\s*UsePass\s+"(?P<name>[^"]+)"')
SHADERLAB_FALLBACK_RE = re.compile(r'(?im)^\s*Fallback\s+"(?P<name>[^"]+)"')
_PROGRAM_BLOCK_START_RE = re.compile(r"(?im)^\s*(?:CG|HLSL)(?:PROGRAM|INCLUDE)\b")
_PROGRAM_BLOCK_END_RE = re.compile(r"(?im)^\s*END(?:CG|HLSL)\b")

strip_comments = repository_hlsl_primitives.strip_comments
iter_function_call_names = repository_hlsl_primitives.iter_function_call_names
parse_include_statements = repository_hlsl_primitives.parse_include_statements


def _coerce_stripped_text(text: str, stripped_text: str | None) -> str:
    if isinstance(stripped_text, str):
        return stripped_text
    return strip_comments(text)


def _build_line_starts(text: str) -> tuple[int, ...]:
    starts = [0]
    search_start = 0
    while True:
        newline_index = text.find("\n", search_start)
        if newline_index < 0:
            break
        starts.append(newline_index + 1)
        search_start = newline_index + 1
    return tuple(starts)


@lru_cache(maxsize=256)
def _line_starts(text: str) -> tuple[int, ...]:
    return _build_line_starts(text)


def _line_number_for_offset(line_starts: tuple[int, ...], offset: int) -> int:
    return max(1, bisect.bisect_right(line_starts, offset))


def has_shaderlab_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in SHADERLAB_SOURCE_SUFFIXES


def iter_program_blocks(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    return _cached_program_blocks(stripped_text)


@lru_cache(maxsize=128)
def _cached_program_blocks(stripped_text: str) -> tuple[tuple[str, int], ...]:
    blocks: list[tuple[str, int]] = []
    current_lines: list[str] = []
    current_start_line: int | None = None
    in_block = False
    for line_number, line in enumerate(stripped_text.splitlines(), start=1):
        if not in_block:
            if _PROGRAM_BLOCK_START_RE.match(line):
                in_block = True
                current_lines = []
                current_start_line = None
            continue
        if _PROGRAM_BLOCK_END_RE.match(line):
            blocks.append(("\n".join(current_lines), current_start_line or line_number))
            in_block = False
            current_lines = []
            current_start_line = None
            continue
        if current_start_line is None:
            current_start_line = line_number
        current_lines.append(line)
    if in_block:
        blocks.append(("\n".join(current_lines), current_start_line or 1))
    return tuple(blocks)


@lru_cache(maxsize=128)
def _cached_shader_declarations(stripped_text: str) -> tuple[tuple[str, int], ...]:
    line_starts = _line_starts(stripped_text)
    return tuple(
        (
            shader_name,
            _line_number_for_offset(line_starts, match.start("name")),
        )
        for match in SHADERLAB_SHADER_RE.finditer(stripped_text)
        if (shader_name := str(match.group("name") or "").strip())
    )


@lru_cache(maxsize=128)
def _cached_shader_names(stripped_text: str) -> tuple[str, ...]:
    return tuple(
        shader_name
        for match in SHADERLAB_SHADER_RE.finditer(stripped_text)
        if (shader_name := str(match.group("name") or "").strip())
    )


def iter_shader_declarations(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    if line_starts is None:
        return _cached_shader_declarations(stripped_text)
    return tuple(
        (
            shader_name,
            _line_number_for_offset(line_starts, match.start("name")),
        )
        for match in SHADERLAB_SHADER_RE.finditer(stripped_text)
        if (shader_name := str(match.group("name") or "").strip())
    )


def iter_shader_names(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[str, ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    return _cached_shader_names(stripped_text)


def iter_usepass_targets(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    line_starts = line_starts if line_starts is not None else _line_starts(stripped_text)
    return tuple(
        (
            target_name,
            _line_number_for_offset(line_starts, match.start("name")),
        )
        for match in SHADERLAB_USEPASS_RE.finditer(stripped_text)
        if (target_name := str(match.group("name") or "").strip())
    )


def iter_fallback_targets(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    line_starts = line_starts if line_starts is not None else _line_starts(stripped_text)
    return tuple(
        (
            target_name,
            _line_number_for_offset(line_starts, match.start("name")),
        )
        for match in SHADERLAB_FALLBACK_RE.finditer(stripped_text)
        if (target_name := str(match.group("name") or "").strip())
    )


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    if line_starts is None:
        return _cached_symbol_entries(stripped_text)
    line_starts = line_starts if line_starts is not None else _line_starts(stripped_text)
    entries = [
        (name, "module", line_number)
        for name, line_number in iter_shader_declarations(
            text,
            stripped_text=stripped_text,
            line_starts=line_starts,
        )
    ]
    for block_text, block_start_line in iter_program_blocks(text, stripped_text=stripped_text):
        block_line_starts = repository_hlsl_primitives._line_starts(block_text)
        for symbol_name, symbol_kind, relative_line in repository_hlsl_primitives.iter_symbol_entries(
            block_text,
            stripped_text=block_text,
            line_starts=block_line_starts,
        ):
            entries.append((symbol_name, symbol_kind, block_start_line + relative_line - 1))
    entries.sort(key=lambda entry: (entry[2], entry[0], entry[1]))
    return tuple(entries)


@lru_cache(maxsize=128)
def _cached_symbol_entries(stripped_text: str) -> tuple[tuple[str, str, int], ...]:
    entries = [
        (name, "module", line_number)
        for name, line_number in _cached_shader_declarations(stripped_text)
    ]
    for block_text, block_start_line in _cached_program_blocks(stripped_text):
        for symbol_name, symbol_kind, relative_line in repository_hlsl_primitives.iter_symbol_entries(
            block_text,
            stripped_text=block_text,
        ):
            entries.append((symbol_name, symbol_kind, block_start_line + relative_line - 1))
    entries.sort(key=lambda entry: (entry[2], entry[0], entry[1]))
    return tuple(entries)
