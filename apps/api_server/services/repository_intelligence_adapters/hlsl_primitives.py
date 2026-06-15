from __future__ import annotations

import bisect
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

HLSL_SOURCE_SUFFIXES = frozenset({".hlsl", ".hlsli", ".fx", ".fxh", ".cginc", ".compute"})
HLSL_MARKER_RE = re.compile(
    r"(?im)^\s*cbuffer\b|^\s*Texture[123]?D\b|^\s*SamplerState\b|^\s*RWTexture[123]?D\b|^\s*\[numthreads\s*\(|\bSV_[A-Za-z0-9_]+\b|^\s*#include\s*[<\"]"
)
HLSL_INCLUDE_RE = re.compile(r'(?im)^\s*#include\s*[<"](?P<target>[^">]+)[">]')
HLSL_STRUCT_RE = re.compile(r"(?im)^\s*struct\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{")
HLSL_CBUFFER_RE = re.compile(r"(?im)^\s*cbuffer\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{")
HLSL_FUNCTION_RE = re.compile(
    r"""(?im)^\s*
    (?:\[[^\]]+\]\s*)*
    (?:[A-Za-z_][A-Za-z0-9_<>]*\s+)*
    (?P<return_type>[A-Za-z_][A-Za-z0-9_<>]*)\s+
    (?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*
    \([^;{}]*\)
    (?:\s*:\s*[A-Za-z_][A-Za-z0-9_<>]*)?
    \s*\{""",
    re.VERBOSE,
)
HLSL_CALL_RE = re.compile(r"(?<![#.])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_RESERVED_CALL_NAMES = frozenset(
    {
        "cbuffer",
        "else",
        "for",
        "if",
        "register",
        "return",
        "sizeof",
        "struct",
        "switch",
        "while",
    }
)
_TYPE_LIKE_NAMES = frozenset(
    {
        "bool",
        "Buffer",
        "ByteAddressBuffer",
        "double",
        "float",
        "float2",
        "float3",
        "float4",
        "float4x4",
        "half",
        "half2",
        "half3",
        "half4",
        "int",
        "int2",
        "int3",
        "int4",
        "matrix",
        "RWBuffer",
        "RWStructuredBuffer",
        "RWTexture1D",
        "RWTexture2D",
        "RWTexture3D",
        "SamplerComparisonState",
        "SamplerState",
        "StructuredBuffer",
        "Texture1D",
        "Texture2D",
        "Texture2DArray",
        "Texture3D",
        "TextureCube",
        "uint",
        "uint2",
        "uint3",
        "uint4",
        "vector",
        "void",
    }
)


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


@lru_cache(maxsize=512)
def _line_starts(text: str) -> tuple[int, ...]:
    return _build_line_starts(text)


def _line_number_for_offset(line_starts: tuple[int, ...], offset: int) -> int:
    return max(1, bisect.bisect_right(line_starts, offset))


@lru_cache(maxsize=512)
def strip_comments(text: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(
        lambda match: "\n" * match.group(0).count("\n"),
        text,
    )
    return _LINE_COMMENT_RE.sub("", without_block_comments)


def has_hlsl_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in HLSL_SOURCE_SUFFIXES


def parse_include_statements(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    line_starts = line_starts if line_starts is not None else _line_starts(stripped_text)
    return tuple(
        (
            str(match.group("target") or "").strip(),
            _line_number_for_offset(line_starts, match.start("target")),
        )
        for match in HLSL_INCLUDE_RE.finditer(stripped_text)
        if str(match.group("target") or "").strip()
    )


@lru_cache(maxsize=256)
def _cached_symbol_entries(stripped_text: str) -> tuple[tuple[str, str, int], ...]:
    line_starts = _line_starts(stripped_text)
    entries: list[tuple[str, str, int]] = []
    for pattern, kind in (
        (HLSL_STRUCT_RE, "struct"),
        (HLSL_CBUFFER_RE, "buffer"),
        (HLSL_FUNCTION_RE, "function"),
    ):
        for match in pattern.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name:
                continue
            line_number = _line_number_for_offset(line_starts, match.start("name"))
            entries.append((symbol_name, kind, line_number))
    entries.sort(key=lambda entry: (entry[2], entry[0], entry[1]))
    return tuple(entries)


def iter_symbol_entries(
    text: str,
    *,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    if line_starts is None:
        return _cached_symbol_entries(stripped_text)
    entries: list[tuple[str, str, int]] = []
    for pattern, kind in (
        (HLSL_STRUCT_RE, "struct"),
        (HLSL_CBUFFER_RE, "buffer"),
        (HLSL_FUNCTION_RE, "function"),
    ):
        for match in pattern.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name:
                continue
            line_number = _line_number_for_offset(line_starts, match.start("name"))
            entries.append((symbol_name, kind, line_number))
    entries.sort(key=lambda entry: (entry[2], entry[0], entry[1]))
    return tuple(entries)


def iter_function_call_names(
    text: str,
    *,
    local_function_names: set[str] | None = None,
    stripped_text: str | None = None,
    line_starts: tuple[int, ...] | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = _coerce_stripped_text(text, stripped_text)
    line_starts = line_starts if line_starts is not None else _line_starts(stripped_text)
    local_names = {name for name in (local_function_names or set()) if name}
    calls: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in HLSL_CALL_RE.finditer(stripped_text):
        call_name = str(match.group("name") or "").strip()
        if (
            not call_name
            or call_name in local_names
            or call_name in _RESERVED_CALL_NAMES
            or call_name in _TYPE_LIKE_NAMES
        ):
            continue
        line_number = _line_number_for_offset(line_starts, match.start("name"))
        entry = (call_name, line_number)
        if entry in seen:
            continue
        seen.add(entry)
        calls.append(entry)
    return tuple(calls)
