from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

GLSL_SOURCE_SUFFIXES = frozenset(
    {".glsl", ".vert", ".frag", ".geom", ".tesc", ".tese", ".comp"}
)
GLSL_MARKER_RE = re.compile(
    r"(?im)^\s*#version\b|^\s*precision\b|^\s*layout\s*\(|\buniform\b|\bvec[234]\b|\bvoid\s+main\s*\("
)
GLSL_INCLUDE_RE = re.compile(r'(?im)^\s*#include\s*[<"](?P<target>[^">]+)[">]')
GLSLIFY_REQUIRE_RE = re.compile(
    r"""(?im)^\s*#pragma\s+glslify\s*:\s*
    (?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)?
    require\(\s*['"](?P<target>[^'"]+)['"]\s*\)""",
    re.VERBOSE,
)
GLSL_STRUCT_RE = re.compile(r"(?im)^\s*struct\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{")
GLSL_FUNCTION_RE = re.compile(
    r"""(?im)^\s*
    (?:[A-Za-z_][A-Za-z0-9_]*\s+)*
    (?P<return_type>[A-Za-z_][A-Za-z0-9_]*)\s+
    (?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*
    \([^;{}]*\)\s*
    \{""",
    re.VERBOSE,
)
GLSL_CALL_RE = re.compile(r"(?<![#.])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_RESERVED_CALL_NAMES = frozenset(
    {
        "else",
        "for",
        "if",
        "layout",
        "main",
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
        "bvec2",
        "bvec3",
        "bvec4",
        "double",
        "dmat2",
        "dmat3",
        "dmat4",
        "dvec2",
        "dvec3",
        "dvec4",
        "float",
        "int",
        "ivec2",
        "ivec3",
        "ivec4",
        "mat2",
        "mat3",
        "mat4",
        "sampler1D",
        "sampler2D",
        "sampler3D",
        "samplerCube",
        "uvec2",
        "uvec3",
        "uvec4",
        "uint",
        "vec2",
        "vec3",
        "vec4",
        "void",
    }
)


def strip_comments(text: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(
        lambda match: "\n" * match.group(0).count("\n"),
        text,
    )
    return _LINE_COMMENT_RE.sub("", without_block_comments)


def has_glsl_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in GLSL_SOURCE_SUFFIXES


def parse_include_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            str(match.group("target") or "").strip(),
            stripped_text.count("\n", 0, match.start()) + 1,
        )
        for match in GLSL_INCLUDE_RE.finditer(stripped_text)
        if str(match.group("target") or "").strip()
    )


def parse_glslify_require_statements(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            str(match.group("target") or "").strip(),
            str(match.group("alias") or "").strip() or None,
            stripped_text.count("\n", 0, match.start()) + 1,
        )
        for match in GLSLIFY_REQUIRE_RE.finditer(stripped_text)
        if str(match.group("target") or "").strip()
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    for pattern, kind in ((GLSL_STRUCT_RE, "struct"), (GLSL_FUNCTION_RE, "function")):
        for match in pattern.finditer(stripped_text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name:
                continue
            line_number = stripped_text.count("\n", 0, match.start()) + 1
            entries.append((symbol_name, kind, line_number))
    entries.sort(key=lambda entry: (entry[2], entry[0], entry[1]))
    return tuple(entries)


def iter_function_call_names(
    text: str,
    *,
    local_function_names: set[str] | None = None,
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    local_names = {name for name in (local_function_names or set()) if name}
    calls: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in GLSL_CALL_RE.finditer(stripped_text):
        call_name = str(match.group("name") or "").strip()
        if (
            not call_name
            or call_name in local_names
            or call_name in _RESERVED_CALL_NAMES
            or call_name in _TYPE_LIKE_NAMES
        ):
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        entry = (call_name, line_number)
        if entry in seen:
            continue
        seen.add(entry)
        calls.append(entry)
    return tuple(calls)
