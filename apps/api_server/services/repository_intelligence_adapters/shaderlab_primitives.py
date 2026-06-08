from __future__ import annotations

import re
from collections.abc import Callable
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

strip_comments = repository_hlsl_primitives.strip_comments
iter_function_call_names = repository_hlsl_primitives.iter_function_call_names
parse_include_statements = repository_hlsl_primitives.parse_include_statements


def has_shaderlab_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in SHADERLAB_SOURCE_SUFFIXES


def iter_shader_declarations(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            shader_name,
            stripped_text.count("\n", 0, match.start()) + 1,
        )
        for match in SHADERLAB_SHADER_RE.finditer(stripped_text)
        if (shader_name := str(match.group("name") or "").strip())
    )


def iter_usepass_targets(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            target_name,
            stripped_text.count("\n", 0, match.start()) + 1,
        )
        for match in SHADERLAB_USEPASS_RE.finditer(stripped_text)
        if (target_name := str(match.group("name") or "").strip())
    )


def iter_fallback_targets(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    return tuple(
        (
            target_name,
            stripped_text.count("\n", 0, match.start()) + 1,
        )
        for match in SHADERLAB_FALLBACK_RE.finditer(stripped_text)
        if (target_name := str(match.group("name") or "").strip())
    )


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries = [(name, "module", line_number) for name, line_number in iter_shader_declarations(text)]
    entries.extend(repository_hlsl_primitives.iter_symbol_entries(text))
    entries.sort(key=lambda entry: (entry[2], entry[0], entry[1]))
    return tuple(entries)
