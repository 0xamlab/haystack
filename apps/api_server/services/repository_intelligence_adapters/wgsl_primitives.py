from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]

WGSL_SUFFIXES = frozenset({".wgsl"})
WGSL_MARKER_RE = re.compile(
    r"(?im)^\s*@(?:vertex|fragment|compute|group|binding|workgroup_size)\b|^\s*fn\s+[A-Za-z_][A-Za-z0-9_]*\s*\(|^\s*struct\s+[A-Za-z_][A-Za-z0-9_]*\s*\{|^\s*var\s*<[^>]+>\s*[A-Za-z_][A-Za-z0-9_]*\s*:|\bvec[234][A-Za-z0-9_]*\b|\bmat[234]x[234][A-Za-z0-9_]*\b"  # noqa: E501
)
WGSL_INCLUDE_RE = re.compile(r'(?im)^\s*#(?:include|import)\s*[<"](?P<target>[^">]+)[">]')
WGSL_IMPORT_RE = re.compile(
    r"""(?imx)
    ^\s*import
    (?:
        \s+(?P<clause>.+?)\s+from
    )?
    \s*["'](?P<target>[^"']+)["']
    \s*;?
    $
    """
)
WGSL_STRUCT_RE = re.compile(r"(?im)^\s*struct\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{")
WGSL_FUNCTION_RE = re.compile(
    r"""(?imsx)
    ^\s*
    (?:@[A-Za-z_][A-Za-z0-9_]*(?:\s*\([^)]*\))?\s*)*
    fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*
    \([^;{}]*\)\s*
    (?:->\s*(?:@[A-Za-z_][A-Za-z0-9_]*(?:\s*\([^)]*\))?\s*)*[A-Za-z_][A-Za-z0-9_<>, ]*)?
    \s*\{
    """
)
WGSL_CALL_RE = re.compile(r"(?<![#.@])\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_RESERVED_CALL_NAMES = frozenset(
    {
        "else",
        "fn",
        "for",
        "if",
        "loop",
        "return",
        "struct",
        "switch",
        "while",
    }
)
_TYPE_LIKE_NAMES = frozenset(
    {
        "array",
        "atomic",
        "bitcast",
        "bool",
        "f16",
        "f32",
        "i32",
        "mat2x2f",
        "mat3x3f",
        "mat4x4f",
        "ptr",
        "sampler",
        "sampler_comparison",
        "texture_1d",
        "texture_2d",
        "texture_2d_array",
        "texture_3d",
        "texture_cube",
        "u32",
        "vec2f",
        "vec2i",
        "vec2u",
        "vec3f",
        "vec3i",
        "vec3u",
        "vec4f",
        "vec4i",
        "vec4u",
        "void",
    }
)


def strip_comments(text: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(
        lambda match: "\n" * match.group(0).count("\n"),
        text,
    )
    return _LINE_COMMENT_RE.sub("", without_block_comments)


def has_wgsl_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in WGSL_SUFFIXES


def parse_include_statements(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            str(match.group("target") or "").strip(),
            stripped_text.count("\n", 0, match.start()) + 1,
        )
        for match in WGSL_INCLUDE_RE.finditer(stripped_text)
        if str(match.group("target") or "").strip()
    )


def parse_import_statements(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    imports: list[tuple[str, str | None, int]] = []
    for match in WGSL_IMPORT_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip()
        clause = str(match.group("clause") or "").strip()
        if not target:
            continue
        alias_name: str | None = None
        if clause and "{" not in clause:
            alias_name = clause.split(",", 1)[0].strip() or None
        imports.append(
            (
                target,
                alias_name,
                stripped_text.count("\n", 0, match.start()) + 1,
            )
        )
    return tuple(imports)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    for pattern, kind in ((WGSL_STRUCT_RE, "struct"), (WGSL_FUNCTION_RE, "function")):
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
    for match in WGSL_CALL_RE.finditer(stripped_text):
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
